import pytest


def audit(client, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get("/api/audit" + (f"?{q}" if q else "")).json()


def entry_body(account_id, **patch):
    return {"account_id": account_id, "to_account_id": None, "name": "Miete", "category": "Wohnen", "kind": "recurring",
            "amount": -120000, "start_date": "2026-01-01", "end_date": None, "interval_months": 1, "note": "", **patch}


@pytest.fixture
def acc(seed):
    return seed.account("Giro")


@pytest.fixture
def ent(seed, acc):
    return seed.entry(acc["id"], "Miete", -120000, "2026-01-01")


# ---------------------------------------------------------------------------- create

@pytest.mark.contract("API-RES-001")
def test_create_entry(client, acc):
    """API-RES-001: POST /api/entries with a valid body -> 200 and the created entry (id, updated_at)."""
    r = client.post("/api/entries", json=entry_body(acc["id"]))
    assert r.status_code == 200
    row = r.json()
    assert isinstance(row["id"], int) and row["updated_at"] and row["name"] == "Miete" and row["amount"] == -120000


@pytest.mark.contract("API-RES-001")
def test_create_adjustment_and_checkpoint(client, ent, acc):
    """API-RES-001: adjustments and checkpoints are created through the same generic route."""
    a = client.post("/api/adjustments", json={"entry_id": ent["id"], "effective_date": "2026-03-01", "mode": "set",
                                               "amount": -130000, "note": "", "repeat_yearly": False})
    c = client.post("/api/checkpoints", json={"account_id": acc["id"], "date": "2026-02-20", "balance": 500000, "note": ""})
    assert a.status_code == 200 and a.json()["entry_id"] == ent["id"]
    assert c.status_code == 200 and c.json()["balance"] == 500000


@pytest.mark.contract("API-RES-002")
@pytest.mark.parametrize("table", ["widgets", "audit_log", "ACCOUNTS", "sqlite_master"])
def test_unknown_table_on_create(client, table):
    """API-RES-002: a non-whitelisted table -> 404 {code: unknown_table, params: {table}}."""
    r = client.post(f"/api/{table}", json={"name": "x"})
    assert r.status_code == 404 and r.json() == {"code": "unknown_table", "params": {"table": table}}


@pytest.mark.contract("API-RES-002")
def test_unknown_table_on_update(client):
    """API-RES-002: PUT on a non-whitelisted table -> 404 unknown_table."""
    r = client.put("/api/widgets/1", json={"name": "x"})
    assert r.status_code == 404 and r.json()["code"] == "unknown_table"


@pytest.mark.contract("API-RES-003")
@pytest.mark.parametrize("make", [
    lambda a, e: ("entries", entry_body(a, amount=0)),
    lambda a, e: ("entries", entry_body(a, to_account_id=a, amount=100)),
    lambda a, e: ("entries", entry_body(a, name="")),
    lambda a, e: ("adjustments", {"entry_id": e, "effective_date": "2026-03-01", "mode": "set", "note": ""}),
    lambda a, e: ("checkpoints", {"account_id": a, "date": "kaputt", "balance": 1, "note": ""}),
])
def test_invalid_body_is_422_and_creates_nothing(client, seed, acc, ent, make):
    """API-RES-003: a body failing validation -> 422 validation_error and nothing is created."""
    before = seed.state()
    table, body = make(acc["id"], ent["id"])
    r = client.post(f"/api/{table}", json=body)
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert seed.state() == before


@pytest.mark.contract("API-RES-004")
@pytest.mark.parametrize("table,patch,field", [
    ("entries", {"account_id": 999999}, "account_id"),
    ("entries", {"to_account_id": 999999, "amount": 100}, "to_account_id"),
    ("checkpoints", {"account_id": 999999}, "account_id"),
    ("adjustments", {"entry_id": 999999}, "entry_id"),
])
def test_missing_reference_is_ref_not_found(client, seed, acc, ent, table, patch, field):
    """API-RES-004: a non-existent referenced id -> 422 ref_not_found {field, id}; nothing created."""
    base = {"entries": entry_body(acc["id"]),
            "checkpoints": {"account_id": acc["id"], "date": "2026-02-01", "balance": 1, "note": ""},
            "adjustments": {"entry_id": ent["id"], "effective_date": "2026-03-01", "mode": "set", "amount": 5,
                            "note": "", "repeat_yearly": False}}[table]
    before = seed.state()
    r = client.post(f"/api/{table}", json={**base, **patch})
    assert r.status_code == 422
    assert r.json() == {"code": "ref_not_found", "params": {"field": field, "id": 999999}}
    assert seed.state() == before


@pytest.mark.contract("API-RES-005")
def test_create_writes_one_audit_row_and_bumps_version_by_one(client, seed, acc):
    """API-RES-005: a successful create writes exactly one 'create' audit row; data_version +1."""
    v = seed.state()["data_version"]
    e = client.post("/api/entries", json=entry_body(acc["id"])).json()
    assert seed.state()["data_version"] == v + 1
    rows = audit(client, entity="entries", entity_id=e["id"])
    assert [r["action"] for r in rows] == ["create"]


@pytest.mark.contract("API-RES-006")
def test_transfer_keeps_the_positive_amount(client, seed):
    """API-RES-006: a transfer is stored with the positive amount as given."""
    a, b = seed.account("A"), seed.account("B")
    e = seed.entry(a["id"], "Sparen", 50000, "2026-02-05", to_account_id=b["id"])
    assert e["amount"] == 50000
    assert [x["amount"] for x in seed.state()["entries"]] == [50000]


# ---------------------------------------------------------------------------- update

@pytest.mark.contract("API-RES-007")
def test_put_with_matching_expected_updated_at(client, ent, acc):
    """API-RES-007: PUT with the current updated_at applies the change and returns the updated row."""
    r = client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="Neu", expected_updated_at=ent["updated_at"]))
    assert r.status_code == 200 and r.json()["name"] == "Neu" and r.json()["updated_at"] != ent["updated_at"]


@pytest.mark.contract("API-RES-008")
def test_put_with_stale_expected_updated_at_conflicts(client, seed, ent, acc):
    """API-RES-008: a stale expected_updated_at -> 409 conflict and nothing changes."""
    client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="First", expected_updated_at=ent["updated_at"]))
    before = seed.state()
    r = client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="Second", expected_updated_at=ent["updated_at"]))
    assert r.status_code == 409 and r.json()["code"] == "conflict"
    assert seed.state() == before and before["entries"][0]["name"] == "First"


@pytest.mark.contract("API-RES-009")
@pytest.mark.parametrize("table,body", [
    ("accounts", {"name": "x", "kind": "checking"}),
    ("entries", None), ("checkpoints", {"account_id": 1, "date": "2026-01-01", "balance": 0}),
])
def test_put_on_missing_id_is_404_not_found(client, acc, table, body):
    """API-RES-009: PUT on a non-existent id -> 404 {code: not_found, params: {entity, id}}."""
    body = body or entry_body(acc["id"])
    r = client.put(f"/api/{table}/987654", json=body)
    assert r.status_code == 404 and r.json() == {"code": "not_found", "params": {"entity": table, "id": 987654}}


@pytest.mark.contract("API-RES-010")
def test_put_validates_like_create(client, seed, ent, acc):
    """API-RES-010: PUT applies the create-time validation (422 validation_error) and changes nothing."""
    before = seed.state()
    r = client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], amount=0))
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert seed.state() == before


@pytest.mark.contract("API-RES-010")
def test_put_checks_references(client, seed, ent):
    """API-RES-010: PUT with a non-existent account_id -> 422 ref_not_found."""
    before = seed.state()
    r = client.put(f"/api/entries/{ent['id']}", json=entry_body(999999))
    assert r.status_code == 422 and r.json()["code"] == "ref_not_found"
    assert seed.state() == before


@pytest.mark.contract("API-RES-011")
def test_update_writes_one_audit_row_with_before_and_after(client, ent, acc):
    """API-RES-011: a successful update writes one 'update' row capturing before/after."""
    client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="Neu"))
    rows = audit(client, entity="entries", entity_id=ent["id"])
    assert [r["action"] for r in rows] == ["update", "create"]
    assert rows[0]["before"]["name"] == "Miete" and rows[0]["after"]["name"] == "Neu"


@pytest.mark.contract("API-RES-011")
def test_noop_update_returns_row_without_audit_row(client, seed, ent, acc):
    """API-RES-011: a PUT that changes nothing returns the row and writes no audit row."""
    v = seed.state()["data_version"]
    r = client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], category=""))
    assert r.status_code == 200 and r.json()["name"] == "Miete"
    assert seed.state()["data_version"] == v


@pytest.mark.contract("API-RES-012")
def test_put_without_expected_updated_at_is_last_writer_wins(client, ent, acc):
    """API-RES-012: without expected_updated_at the change always applies."""
    client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="A"))
    r = client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="B"))
    assert r.status_code == 200 and r.json()["name"] == "B"


@pytest.mark.contract("API-RES-011", "API-RES-007")
def test_comment_and_expected_updated_at_are_not_written_to_the_row(client, seed, ent, acc):
    """API-RES-007/011: comment/expected_updated_at are not data columns; the comment goes to the audit row."""
    client.put(f"/api/entries/{ent['id']}", json=entry_body(acc["id"], name="Neu", comment="Tippfehler", expected_updated_at=ent["updated_at"]))
    assert "comment" not in seed.state()["entries"][0] and "expected_updated_at" not in seed.state()["entries"][0]
    assert audit(client, entity="entries", entity_id=ent["id"])[0]["comment"] == "Tippfehler"


# ---------------------------------------------------------------------------- archive / restore

@pytest.mark.contract("API-RES-013")
@pytest.mark.parametrize("table", ["accounts", "entries", "checkpoints", "adjustments"])
def test_archive_flips_flag_and_logs(client, seed, ent, table):
    """API-RES-013: archive sets archived=true, returns the row and writes an 'archive' audit row."""
    adj = seed.adjustment(ent["id"], "2026-03-01", amount=-1)
    row_id = {"accounts": ent["account_id"], "entries": ent["id"], "adjustments": adj["id"],
              "checkpoints": seed.state()["checkpoints"][0]["id"]}[table]
    r = client.post(f"/api/{table}/{row_id}/archive", json={})
    assert r.status_code == 200 and r.json()["id"] == row_id and r.json()["archived"] in (True, 1)
    assert audit(client, entity=table, entity_id=row_id)[0]["action"] == "archive"
    assert [x for x in seed.state()[table] if x["id"] == row_id][0]["archived"] is True


@pytest.mark.contract("API-RES-014")
def test_restore_flips_flag_back_and_logs(client, seed, ent):
    """API-RES-014: restore sets archived=false and writes a 'restore' audit row."""
    client.post(f"/api/entries/{ent['id']}/archive", json={})
    r = client.post(f"/api/entries/{ent['id']}/restore", json={})
    assert r.status_code == 200 and not r.json()["archived"]
    assert audit(client, entity="entries", entity_id=ent["id"])[0]["action"] == "restore"
    assert seed.state()["entries"][0]["archived"] is False


@pytest.mark.contract("API-RES-015")
@pytest.mark.parametrize("action", ["archive", "restore"])
def test_archive_restore_on_unknown_table_is_404(client, action):
    """API-RES-015: archive/restore for a non-whitelisted table -> 404 (body shape not specified, OQ #9)."""
    assert client.post(f"/api/widgets/1/{action}", json={}).status_code == 404


@pytest.mark.contract("API-RES-016")
@pytest.mark.parametrize("action", ["archive", "restore"])
def test_archive_restore_on_missing_id_is_not_found(client, action):
    """API-RES-016: archive/restore on a non-existent id -> 404 {code: not_found}."""
    r = client.post(f"/api/entries/987654/{action}", json={})
    assert r.status_code == 404 and r.json()["code"] == "not_found"


@pytest.mark.contract("API-RES-017")
def test_archive_comment_is_stored_on_the_audit_row(client, ent):
    """API-RES-017: the optional comment is stored on the archive/restore audit rows."""
    client.post(f"/api/entries/{ent['id']}/archive", json={"comment": "nicht mehr aktuell"})
    client.post(f"/api/entries/{ent['id']}/restore", json={"comment": "doch wieder"})
    rows = audit(client, entity="entries", entity_id=ent["id"])
    assert [r["comment"] for r in rows[:2]] == ["doch wieder", "nicht mehr aktuell"]


@pytest.mark.contract("API-RES-017")
def test_archive_comment_of_500_chars_is_stored_in_full(client, ent):
    """API-RES-017: a 500-character comment is accepted and stored unchanged."""
    text = "ü" * 500
    client.post(f"/api/entries/{ent['id']}/archive", json={"comment": text})
    assert audit(client, entity="entries", entity_id=ent["id"])[0]["comment"] == text


@pytest.mark.contract("API-RES-017")
def test_archive_comment_over_500_is_truncated_or_rejected(client, ent):
    """API-RES-017: a 501+ character comment is truncated (clause) - rejection is also tolerated (F-22)."""
    r = client.post(f"/api/entries/{ent['id']}/archive", json={"comment": "x" * 600})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert len(audit(client, entity="entries", entity_id=ent["id"])[0]["comment"]) <= 500


@pytest.mark.skip(reason="Open question #3 (possible bug): archive/restore are not optimistic-locked; behavior not asserted pending resolution")
@pytest.mark.contract("API-RES-018")
def test_archive_restore_take_no_expected_updated_at():
    """API-RES-018: skipped, see OPEN_QUESTIONS #3."""


@pytest.mark.contract("API-RES-019")
@pytest.mark.parametrize("table", ["accounts", "entries", "checkpoints", "adjustments"])
def test_there_is_no_delete_over_http(client, seed, ent, table):
    """API-RES-019: DELETE is not offered for any resource; the record stays."""
    adj = seed.adjustment(ent["id"], "2026-03-01", amount=-1)
    ids = {"accounts": ent["account_id"], "entries": ent["id"], "adjustments": adj["id"],
           "checkpoints": seed.state()["checkpoints"][0]["id"]}
    before = seed.state()
    assert client.delete(f"/api/{table}/{ids[table]}").status_code in (404, 405)
    assert seed.state() == before


@pytest.mark.contract("API-RES-019")
def test_archive_keeps_the_record_in_state(client, seed, ent):
    """API-RES-019: archived records remain in /api/state (archive is the only removal)."""
    client.post(f"/api/entries/{ent['id']}/archive", json={})
    assert [e["id"] for e in seed.state()["entries"]] == [ent["id"]]


@pytest.mark.contract("API-RES-020")
def test_archiving_a_referenced_account_is_allowed_and_drops_it_from_the_forecast(client, seed):
    """API-RES-020: an account with active entries/checkpoints can be archived; the forecast drops it."""
    a = seed.account("Giro")
    seed.entry(a["id"], "Miete", -1000, "2026-02-01")
    r = client.post(f"/api/accounts/{a['id']}/archive", json={})
    assert r.status_code == 200
    assert seed.forecast("2026-01", 3)["accounts"] == []
