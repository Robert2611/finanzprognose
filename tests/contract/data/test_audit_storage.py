import json

import pytest

from tests.contract.helpers.sqlite_view import open_db, scalar


@pytest.mark.contract("DATA-010")
def test_audit_before_after_are_nullable_text(fresh_db):
    """DATA-010: audit_log.before and .after are nullable TEXT columns."""
    with open_db(fresh_db) as c:
        info = {r["name"]: r for r in c.execute("PRAGMA table_info(audit_log)")}
    for col in ("before", "after"):
        assert info[col]["type"].upper() == "TEXT" and info[col]["notnull"] == 0


@pytest.mark.contract("DATA-010")
def test_audit_snapshots_are_json_text_in_same_database(client, db_path, seed):
    """DATA-010: create/update snapshots are JSON text stored in the same database."""
    a = seed.account("X")
    client.put(f"/api/accounts/{a['id']}", json={"name": "Y", "kind": "checking", "expected_updated_at": a["updated_at"]})
    with open_db(db_path) as c:
        rows = c.execute("SELECT before, after, typeof(before) tb, typeof(after) ta FROM audit_log "
                         "WHERE entity='accounts' ORDER BY id").fetchall()
    create, update = rows[0], rows[-1]
    assert create["before"] is None and create["ta"] == "text" and json.loads(create["after"])["name"] == "X"
    assert update["tb"] == "text" and json.loads(update["before"])["name"] == "X"
    assert json.loads(update["after"])["name"] == "Y"


@pytest.mark.contract("DATA-010")
def test_rejected_write_leaves_no_audit_row(client, db_path, seed):
    """DATA-010: a change and its audit row commit together; a rejected change leaves neither."""
    a = seed.account("X")
    before = scalar(db_path, "SELECT COUNT(*) FROM audit_log")
    r = client.post("/api/entries", json={"account_id": a["id"], "name": "bad", "kind": "once", "amount": 0, "start_date": "2026-01-01"})
    assert r.status_code == 422
    r = client.post("/api/entries", json={"account_id": 99999, "name": "bad", "kind": "once", "amount": 5, "start_date": "2026-01-01"})
    assert r.status_code == 422
    assert scalar(db_path, "SELECT COUNT(*) FROM audit_log") == before
    assert scalar(db_path, "SELECT COUNT(*) FROM entries") == 0


@pytest.mark.contract("DATA-010")
def test_each_accepted_change_has_exactly_one_audit_row(client, db_path, seed):
    """DATA-010: every accepted create writes its audit row in the same step."""
    a = seed.account("X")           # account + start checkpoint = 2 changes
    assert scalar(db_path, "SELECT COUNT(*) FROM audit_log") == 2
    seed.entry(a["id"], amount=-5)
    assert scalar(db_path, "SELECT COUNT(*) FROM audit_log") == 3
