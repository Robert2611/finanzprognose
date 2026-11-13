import os
import sqlite3
import tempfile

import pytest

from fastapi.testclient import TestClient

from app import backup, db, forecast
from app.main import create_app
from app.settings import Settings

_tmp = tempfile.mkdtemp()
# Explicit settings, independent of the ambient environment (the dev container sets
# BACKUP_REQUIRE_MARKER=0 for local runs). No scheduler thread in tests.
S = Settings(db_path=os.path.join(_tmp, "data", "finanzen.sqlite"), backup_dir=os.path.join(_tmp, "backup"),
             backup_require_marker=True, backup_scheduler=False, app_password="")


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(S)) as c:
        yield c


def test_full_flow(client):
    giro = client.post("/api/accounts", json={"name": "Checking", "kind": "checking", "start_balance": 100000, "start_date": "2026-01-15"}).json()
    tg = client.post("/api/accounts", json={"name": "Savings", "kind": "savings", "start_balance": 0, "start_date": "2026-01-15"}).json()
    sal = client.post("/api/entries", json={"account_id": giro["id"], "name": "Salary", "kind": "recurring", "amount": 300000,
                                            "start_date": "2026-01-31", "interval_months": 1}).json()
    client.post("/api/entries", json={"account_id": giro["id"], "name": "Rent", "kind": "recurring", "amount": -120000,
                                      "start_date": "2026-01-01", "interval_months": 1})
    client.post("/api/entries", json={"account_id": giro["id"], "to_account_id": tg["id"], "name": "Saving", "kind": "recurring",
                                      "amount": 50000, "start_date": "2026-02-05"})
    client.post("/api/entries", json={"account_id": giro["id"], "name": "Vacation", "kind": "once", "amount": -200000, "start_date": "2026-03-10"})
    r = client.post("/api/adjustments", json={"entry_id": sal["id"], "effective_date": "2026-03-01", "mode": "set", "amount": 320000, "note": "Raise"})
    assert r.status_code == 200, r.text

    fc = client.get("/api/forecast?start=2026-01&months=4").json()
    m = {x["month"]: x for x in fc["months"]}
    g = str(giro["id"])
    # Jan: start 1000 on Jan 15, rent on Jan 1 ignored (before start), salary on Jan 31 +3000
    assert m["2026-01"]["accounts"][g]["closing"] == 400000
    # Feb: -1200 rent, +3000 salary (Feb 28), -500 savings
    assert m["2026-02"]["accounts"][g]["closing"] == 400000 - 120000 + 300000 - 50000
    assert m["2026-02"]["accounts"][str(tg["id"])]["closing"] == 50000
    # Feb salary falls on Feb 28 (last day of the month)
    assert any(i["date"] == "2026-02-28" and i["label"] == "Salary" for i in m["2026-02"]["accounts"][g]["items"])
    # Mar: salary 3200 with explanation, vacation
    sal_mar = [i for i in m["2026-03"]["accounts"][g]["items"] if i["label"] == "Salary"][0]
    assert sal_mar["amount"] == 320000
    assert any(e["code"] == "set_amount" for e in sal_mar["explanation"])

    # Checkpoint with deviation
    client.post("/api/checkpoints", json={"account_id": giro["id"], "date": "2026-02-20", "balance": 500000})
    fc = client.get("/api/forecast?start=2026-02&months=1").json()
    cp = [i for i in fc["months"][0]["accounts"][g]["items"] if i["type"] == "checkpoint"][0]
    assert cp["expected"] == 400000 - 120000 - 50000 and cp["deviation"] == 500000 - 230000


def test_optimistic_locking_and_audit(client):
    acc = client.post("/api/accounts", json={"name": "X", "start_balance": 0, "start_date": "2026-01-01"}).json()
    ok = client.put(f"/api/accounts/{acc['id']}", json={"name": "Y", "kind": "checking", "expected_updated_at": acc["updated_at"]})
    assert ok.status_code == 200
    stale = client.put(f"/api/accounts/{acc['id']}", json={"name": "Z", "kind": "checking", "expected_updated_at": acc["updated_at"]})
    assert stale.status_code == 409
    log = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()
    upd = [a for a in log if a["action"] == "update"][0]
    assert upd["before"]["name"] == "X" and upd["after"]["name"] == "Y"
    r = client.post(f"/api/audit/{upd['id']}/revert").json()
    assert r["name"] == "X"
    log = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()
    assert log[0]["action"] == "revert" and log[0]["reverts_id"] == upd["id"]


def test_state_contract(client):
    acc = client.post("/api/accounts", json={"name": "Contract", "start_balance": 0, "start_date": "2026-01-01"}).json()
    state = client.get("/api/state").json()
    row = next(a for a in state["accounts"] if a["id"] == acc["id"])
    assert set(row) == {"id", "name", "kind", "note", "archived", "updated_at"}
    assert row["archived"] is False  # not the raw stored 0/1
    assert "data_version" in state

    # A column added directly to the table (bypassing TABLES/the response model, e.g. a future
    # migration) must not leak onto the wire: the contract is decoupled from the table shape.
    conn = db.connect(S.db_path)
    conn.execute("ALTER TABLE accounts ADD COLUMN extra_col TEXT")
    conn.close()
    row2 = next(a for a in client.get("/api/state").json()["accounts"] if a["id"] == acc["id"])
    assert "extra_col" not in row2 and "created_at" not in row2


def test_audit_contract(client):
    acc = client.post("/api/accounts", json={"name": "AuditContract", "start_balance": 0, "start_date": "2026-01-01"}).json()
    entry = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()[0]
    assert set(entry) == {"id", "ts", "action", "entity", "entity_id", "before", "after", "comment", "reverts_id"}


def test_backup_status_contract(client):
    st = client.get("/api/backup/status").json()
    assert {"backup_dir", "backup_time", "current_version", "pending_changes", "files"} <= set(st)
    assert isinstance(st["pending_changes"], bool)


def test_nothing_can_be_deleted(client):
    conn = db.connect(S.db_path)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM accounts")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM audit_log")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE audit_log SET comment='x'")
    conn.close()


def test_percent_yearly():
    e = {"amount": -100000, "start_date": "2026-01-01"}
    adjs = [{"effective_date": "2026-01-01", "mode": "percent", "percent": 2.0, "repeat_yearly": 1, "note": ""}]
    from datetime import date
    assert forecast.amount_at(e, adjs, date(2026, 6, 1))[0] == -102000
    assert forecast.amount_at(e, adjs, date(2028, 1, 1))[0] == -106121  # 3x 2 %


def test_backup(client):
    os.makedirs(S.backup_dir, exist_ok=True)
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "error" and ".nas-marker" in r["last_error"]
    open(os.path.join(S.backup_dir, ".nas-marker"), "w").close()
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "ok"
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "unchanged"
    client.post("/api/accounts", json={"name": "New", "start_balance": 0, "start_date": "2026-01-01"})
    import time; time.sleep(1.1)
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "ok"
    files = backup.list_backups(S)
    assert len(files) == 2  # old backup is kept
    c = sqlite3.connect(os.path.join(S.backup_dir, files[0]["name"]))
    assert c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] >= 1


def test_migrations_upgrade_preserves_data(monkeypatch, tmp_path):
    # Own temp database so this stays independent of the shared module-scoped DB.
    path = str(tmp_path / "mig.sqlite")

    # A baseline (version 1) database holding one row, as an existing install would have.
    db.init(path)
    with db.tx(path) as conn:
        db.create(conn, "accounts", {"name": "Old", "kind": "checking", "note": ""})
    with db.read(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1

    # A new migration adds a column; init() must apply it and keep existing data.
    def _v2(conn):
        if not db._has_column(conn, "accounts", "color"):
            conn.execute("ALTER TABLE accounts ADD COLUMN color TEXT NOT NULL DEFAULT ''")
    monkeypatch.setattr(db, "MIGRATIONS", [(2, _v2)])

    db.init(path)
    with db.read(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db._has_column(conn, "accounts", "color")
        assert [r["name"] for r in conn.execute("SELECT name FROM accounts")] == ["Old"]

    # Running again is a no-op (idempotent), not an error.
    db.init(path)
    with db.read(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_settings_are_per_app(tmp_path):
    """Two apps with different settings coexist in one process: own DB, own auth."""
    def settings(name, password):
        return Settings(db_path=str(tmp_path / name / "finanzen.sqlite"), backup_dir=str(tmp_path / name / "nas"),
                        backup_scheduler=False, app_password=password)

    with TestClient(create_app(settings("open", ""))) as open_c, \
            TestClient(create_app(settings("locked", "secret"))) as locked_c:
        r = open_c.post("/api/accounts", json={"name": "A", "start_balance": 0, "start_date": "2026-01-01"})
        assert r.status_code == 200
        assert [a["name"] for a in open_c.get("/api/state").json()["accounts"]] == ["A"]

        assert locked_c.get("/healthz").status_code == 200
        assert locked_c.get("/api/state").status_code == 401
        assert locked_c.get("/api/state", auth=("admin", "wrong")).status_code == 401
        state = locked_c.get("/api/state", auth=("admin", "secret")).json()
        assert state["accounts"] == []  # separate database
        st = locked_c.get("/api/backup/status", auth=("admin", "secret")).json()
        assert st["backup_dir"] == str(tmp_path / "locked" / "nas")


def test_settings_from_env():
    s = Settings.from_env({"DB_PATH": "/x/db.sqlite", "BACKUP_REQUIRE_MARKER": "0", "BACKUP_SCHEDULER": "0",
                           "APP_PASSWORD": "pw", "BACKUP_TIME": "04:30"})
    assert s == Settings(db_path="/x/db.sqlite", backup_dir="/backup", backup_time="04:30",
                         backup_require_marker=False, backup_scheduler=False, app_user="admin", app_password="pw")
    assert Settings.from_env({}) == Settings()
