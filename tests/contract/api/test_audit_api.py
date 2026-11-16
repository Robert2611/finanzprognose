import pytest

KEYS = {"id", "ts", "action", "entity", "entity_id", "before", "after", "comment", "reverts_id"}


@pytest.fixture
def acc(seed):
    return seed.account("X")


def rename(client, acc, name, **extra):
    return client.put(f"/api/accounts/{acc['id']}", json={"name": name, "kind": "checking", **extra})


@pytest.mark.contract("API-AUDIT-001")
def test_filter_by_entity_and_entity_id_newest_first(client, acc):
    """API-AUDIT-001: ?entity=accounts&entity_id=<id> returns that account's rows, newest first."""
    rename(client, acc, "Y")
    rename(client, acc, "Z")
    rows = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()
    assert [r["action"] for r in rows] == ["update", "update", "create"]
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)
    assert all(r["entity"] == "accounts" and r["entity_id"] == acc["id"] for r in rows)


@pytest.mark.contract("API-AUDIT-002")
def test_audit_objects_have_exactly_the_documented_keys(client, acc):
    """API-AUDIT-002: each audit object has exactly {id, ts, action, entity, entity_id, before, after, comment, reverts_id}."""
    rename(client, acc, "Y")
    rows = client.get("/api/audit").json()
    assert rows and all(set(r) == KEYS for r in rows)


@pytest.mark.contract("API-AUDIT-003")
def test_create_row_has_no_before_update_row_has_both(client, acc):
    """API-AUDIT-003: create -> before null, after the row; update -> both reflect the change."""
    rename(client, acc, "Y")
    upd, create = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()
    assert create["before"] is None and create["after"]["name"] == "X"
    assert upd["before"]["name"] == "X" and upd["after"]["name"] == "Y"
    assert isinstance(upd["before"], dict) and isinstance(upd["after"], dict)


@pytest.mark.contract("API-AUDIT-004")
def test_limit_caps_the_page_and_defaults_to_200(client, seed, acc):
    """API-AUDIT-004: limit caps the result; the default page is 200 rows."""
    for i in range(210):
        rename(client, acc, f"n{i}")
    assert len(client.get("/api/audit").json()) == 200
    assert len(client.get("/api/audit?limit=5").json()) == 5
    assert len(client.get("/api/audit?limit=1000").json()) == 212


@pytest.mark.contract("API-AUDIT-004")
@pytest.mark.parametrize("limit", [1001, 5000])
def test_limit_above_1000_is_rejected(client, limit):
    """API-AUDIT-004: limit > 1000 -> 422."""
    assert client.get(f"/api/audit?limit={limit}").status_code == 422


@pytest.mark.contract("API-AUDIT-005")
def test_before_id_pages_toward_older_rows(client, acc):
    """API-AUDIT-005: successive before_id calls walk toward older entries; a short page ends the walk."""
    for i in range(6):
        rename(client, acc, f"n{i}")
    seen, before = [], None
    while True:
        url = "/api/audit?limit=4" + (f"&before_id={before}" if before else "")
        page = client.get(url).json()
        seen += [r["id"] for r in page]
        if len(page) < 4:
            break
        before = page[-1]["id"]
    assert seen == sorted(seen, reverse=True) and len(seen) == len(set(seen)) == 8   # account + checkpoint + 6 updates


@pytest.mark.contract("API-AUDIT-006")
def test_entity_and_entity_id_scope_to_one_record(client, seed):
    """API-AUDIT-006: entity + entity_id combine (AND) to one record's history."""
    a, b = seed.account("A"), seed.account("B")
    rename(client, a, "A2")
    rows = client.get(f"/api/audit?entity=accounts&entity_id={a['id']}").json()
    assert len(rows) == 2 and {r["entity_id"] for r in rows} == {a["id"]}
    assert client.get("/api/audit?entity=accounts&entity_id=999999").json() == []
    ents = client.get("/api/audit?entity=checkpoints").json()
    assert {r["entity"] for r in ents} == {"checkpoints"} and len(ents) == 2


@pytest.mark.contract("API-AUDIT-007")
def test_revert_update_restores_record_and_logs_revert(client, acc):
    """API-AUDIT-007: reverting an update returns the restored record; the newest row is a 'revert' of it."""
    upd = rename(client, acc, "Y")
    assert upd.status_code == 200
    audit_id = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()[0]["id"]
    r = client.post(f"/api/audit/{audit_id}/revert")
    assert r.status_code == 200 and r.json()["name"] == "X"
    newest = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()[0]
    assert newest["action"] == "revert" and newest["reverts_id"] == audit_id
    assert [a["name"] for a in client.get("/api/state").json()["accounts"]] == ["X"]


@pytest.mark.contract("API-AUDIT-007")
def test_revert_advances_data_version_and_keeps_history(client, seed, acc):
    """API-AUDIT-007: a revert is a new forward change: data_version rises and old rows are untouched."""
    rename(client, acc, "Y")
    before = client.get("/api/audit?limit=1000").json()
    v = seed.state()["data_version"]
    client.post(f"/api/audit/{before[0]['id']}/revert")
    assert seed.state()["data_version"] == v + 1
    after = client.get("/api/audit?limit=1000").json()
    assert after[1:] == before


@pytest.mark.contract("API-AUDIT-008")
def test_revert_of_create_archives_the_record(client, seed):
    """API-AUDIT-008: reverting a create row archives the record and writes a revert row."""
    a = seed.account("A")
    e = seed.entry(a["id"], "E", -5)
    create = client.get(f"/api/audit?entity=entries&entity_id={e['id']}").json()[-1]
    r = client.post(f"/api/audit/{create['id']}/revert")
    assert r.status_code == 200
    assert [x for x in seed.state()["entries"] if x["id"] == e["id"]][0]["archived"] is True
    newest = client.get("/api/audit?limit=1").json()[0]
    assert newest["action"] == "revert" and newest["reverts_id"] == create["id"]


@pytest.mark.contract("API-AUDIT-009")
def test_revert_unknown_audit_id_is_404(client):
    """API-AUDIT-009: reverting a non-existent audit id -> 404 not_found {entity: audit_log, id}."""
    r = client.post("/api/audit/999999/revert")
    assert r.status_code == 404
    assert r.json() == {"code": "not_found", "params": {"entity": "audit_log", "id": 999999}}


@pytest.mark.contract("API-AUDIT-010")
@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_audit_rows_cannot_be_edited_or_deleted_over_http(client, acc, method):
    """API-AUDIT-010: there is no endpoint to edit or delete audit rows."""
    before = client.get("/api/audit?limit=1000").json()
    rid = before[0]["id"]
    kwargs = {"json": {"comment": "tampered"}} if method != "delete" else {}
    r = getattr(client, method)(f"/api/audit/{rid}", **kwargs)
    assert r.status_code in (404, 405)
    assert client.get("/api/audit?limit=1000").json() == before
