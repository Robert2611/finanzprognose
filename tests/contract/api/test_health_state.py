import pytest

ACCOUNT_KEYS = {"id", "name", "kind", "note", "archived", "updated_at"}
ENTRY_KEYS = {"id", "account_id", "to_account_id", "name", "category", "kind", "amount", "start_date", "end_date",
              "interval_months", "estimated", "note", "archived", "updated_at"}
ADJ_KEYS = {"id", "entry_id", "effective_date", "mode", "amount", "percent", "repeat_yearly", "note", "archived", "updated_at"}
CP_KEYS = {"id", "account_id", "date", "balance", "note", "archived", "updated_at"}


@pytest.mark.contract("API-STATE-001")
def test_healthz(client):
    """API-STATE-001: GET /healthz -> 200 {"ok": true}."""
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


@pytest.mark.contract("API-STATE-001")
@pytest.mark.app_settings(app_password="pw")
def test_healthz_needs_no_authentication(anon_client):
    """API-STATE-001: /healthz never requires authentication."""
    assert anon_client.get("/healthz").json() == {"ok": True}


@pytest.mark.contract("API-STATE-002")
def test_state_has_four_arrays_and_data_version(seed):
    """API-STATE-002: /api/state returns the four table arrays plus an integer data_version."""
    seed.standard_world()
    s = seed.state()
    assert set(s) == {"accounts", "entries", "adjustments", "checkpoints", "data_version"}
    assert all(isinstance(s[k], list) for k in ("accounts", "entries", "adjustments", "checkpoints"))
    assert isinstance(s["data_version"], int) and not isinstance(s["data_version"], bool)


@pytest.mark.contract("API-STATE-003")
def test_account_objects_have_exactly_the_public_keys(seed):
    """API-STATE-003: each account has exactly {id, name, kind, note, archived, updated_at}."""
    seed.account("Giro")
    assert all(set(a) == ACCOUNT_KEYS for a in seed.state()["accounts"])


@pytest.mark.contract("API-STATE-003")
def test_other_objects_have_their_documented_keys(seed):
    """API-STATE-003 (shape): entries, adjustments and checkpoints expose exactly their documented fields."""
    a = seed.account("Giro")
    e = seed.entry(a["id"], amount=-100)
    seed.adjustment(e["id"], "2026-02-01", amount=-200)
    s = seed.state()
    assert all(set(x) == ENTRY_KEYS for x in s["entries"])
    assert all(set(x) == ADJ_KEYS for x in s["adjustments"])
    assert all(set(x) == CP_KEYS for x in s["checkpoints"])


@pytest.mark.contract("API-STATE-004")
def test_archived_is_a_json_boolean(seed, client):
    """API-STATE-004: archived is true/false, not 0/1."""
    a = seed.account("Giro")
    assert seed.state()["accounts"][0]["archived"] is False
    client.post(f"/api/accounts/{a['id']}/archive", json={})
    assert seed.state()["accounts"][0]["archived"] is True


@pytest.mark.contract("API-STATE-005")
def test_columns_added_to_a_table_do_not_leak(seed, db_path):
    """API-STATE-005: a column added directly to a table does not appear in /api/state."""
    import sqlite3
    seed.account("Giro")
    c = sqlite3.connect(db_path)
    c.execute("ALTER TABLE accounts ADD COLUMN secret_extra TEXT")
    c.commit()
    c.close()
    assert set(seed.state()["accounts"][0]) == ACCOUNT_KEYS


@pytest.mark.contract("API-STATE-006")
def test_money_is_integer_cents_and_percent_a_number(seed):
    """API-STATE-006: amount/balance are integers; percent is a number or null."""
    a = seed.account("Giro", 123456)
    e = seed.entry(a["id"], amount=-98765)
    seed.adjustment(e["id"], "2026-02-01", mode="percent", percent=2.5)
    seed.adjustment(e["id"], "2026-03-01", mode="set", amount=-5)
    s = seed.state()
    assert [c["balance"] for c in s["checkpoints"]] == [123456] and type(s["checkpoints"][0]["balance"]) is int
    assert type(s["entries"][0]["amount"]) is int and s["entries"][0]["amount"] == -98765
    by_mode = {x["mode"]: x for x in s["adjustments"]}
    assert by_mode["percent"]["percent"] == 2.5 and by_mode["percent"]["amount"] is None
    assert by_mode["set"]["percent"] is None and type(by_mode["set"]["amount"]) is int


@pytest.mark.contract("API-STATE-007")
def test_rows_are_ordered_by_ascending_id_including_archived(seed, client):
    """API-STATE-007: each array is ascending by id, archived rows included."""
    ids = [seed.account(n)["id"] for n in ("c", "a", "b")]
    client.post(f"/api/accounts/{ids[1]}/archive", json={})
    got = [a["id"] for a in seed.state()["accounts"]]
    assert got == sorted(ids) and len(got) == 3


@pytest.mark.contract("API-STATE-008")
def test_data_version_tracks_changes(seed, client):
    """API-STATE-008: data_version increases as data changes."""
    v0 = seed.state()["data_version"]
    a = seed.account("Giro")
    v1 = seed.state()["data_version"]
    client.put(f"/api/accounts/{a['id']}", json={"name": "Neu", "kind": "checking"})
    v2 = seed.state()["data_version"]
    assert v0 < v1 < v2


@pytest.mark.contract("API-STATE-008")
def test_data_version_matches_newest_audit_id(seed, client):
    """API-STATE-008: data_version equals the newest audit row id."""
    seed.standard_world()
    newest = client.get("/api/audit?limit=1").json()[0]["id"]
    assert seed.state()["data_version"] == newest


@pytest.mark.contract("API-STATE-009")
def test_empty_database_state(client):
    """API-STATE-009: empty DB -> four empty arrays and data_version 0."""
    assert client.get("/api/state").json() == {"accounts": [], "entries": [], "adjustments": [], "checkpoints": [], "data_version": 0}
