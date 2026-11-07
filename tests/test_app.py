import os
import sqlite3
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "data", "finanzen.sqlite")
os.environ["BACKUP_DIR"] = os.path.join(_tmp, "backup")
os.environ["APP_PASSWORD"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import backup, db, forecast  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_full_flow(client):
    giro = client.post("/api/accounts", json={"name": "Checking", "kind": "giro", "start_balance": 100000, "start_date": "2026-01-15"}).json()
    tg = client.post("/api/accounts", json={"name": "Savings", "kind": "tagesgeld", "start_balance": 0, "start_date": "2026-01-15"}).json()
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
    assert any("neuer Betrag" in e for e in sal_mar["explanation"])

    # Checkpoint with deviation
    client.post("/api/checkpoints", json={"account_id": giro["id"], "date": "2026-02-20", "balance": 500000})
    fc = client.get("/api/forecast?start=2026-02&months=1").json()
    cp = [i for i in fc["months"][0]["accounts"][g]["items"] if i["type"] == "checkpoint"][0]
    assert cp["expected"] == 400000 - 120000 - 50000 and cp["deviation"] == 500000 - 230000


def test_optimistic_locking_and_audit(client):
    acc = client.post("/api/accounts", json={"name": "X", "start_balance": 0, "start_date": "2026-01-01"}).json()
    ok = client.put(f"/api/accounts/{acc['id']}", json={"name": "Y", "kind": "giro", "expected_updated_at": acc["updated_at"]})
    assert ok.status_code == 200
    stale = client.put(f"/api/accounts/{acc['id']}", json={"name": "Z", "kind": "giro", "expected_updated_at": acc["updated_at"]})
    assert stale.status_code == 409
    log = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()
    upd = [a for a in log if a["action"] == "update"][0]
    assert upd["before"]["name"] == "X" and upd["after"]["name"] == "Y"
    r = client.post(f"/api/audit/{upd['id']}/revert").json()
    assert r["name"] == "X"


def test_nothing_can_be_deleted():
    conn = db.connect()
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
    os.makedirs(backup.BACKUP_DIR, exist_ok=True)
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "error" and ".nas-marker" in r["last_error"]
    open(os.path.join(backup.BACKUP_DIR, ".nas-marker"), "w").close()
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "ok"
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "unchanged"
    client.post("/api/accounts", json={"name": "New", "start_balance": 0, "start_date": "2026-01-01"})
    import time; time.sleep(1.1)
    r = client.post("/api/backup/run").json()
    assert r["last_result"] == "ok"
    files = backup.list_backups()
    assert len(files) == 2  # old backup is kept
    c = sqlite3.connect(os.path.join(backup.BACKUP_DIR, files[0]["name"]))
    assert c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] >= 1
