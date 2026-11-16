"""HTTP-checkable e2e clauses: each test replays the scenario from contracts/e2e/*.md through the public API."""
import base64
import sqlite3

import pytest

from tests.contract.backup.conftest import NAME, sha256
from tests.contract.helpers.sqlite_view import integrity_check, scalar


def acct(month, account_id):
    return month["accounts"][str(account_id)]


# ------------------------------------------------------------------ onboarding

@pytest.mark.contract("E2E-ONBOARD-004")
def test_first_account_creates_account_and_start_checkpoint(client, seed):
    """E2E-ONBOARD-004: POST /api/accounts -> 200; /api/state shows one account and one checkpoint {2026-01-15, 100000}."""
    r = client.post("/api/accounts", json={"name": "Giro", "kind": "checking", "start_balance": 100000, "start_date": "2026-01-15"})
    assert r.status_code == 200
    s = seed.state()
    assert len(s["accounts"]) == 1 and s["accounts"][0]["name"] == "Giro"
    assert [(c["date"], c["balance"]) for c in s["checkpoints"]] == [("2026-01-15", 100000)]


@pytest.mark.contract("E2E-ONBOARD-005")
def test_forecast_of_the_new_account_opens_at_the_start_balance(client, seed):
    """E2E-ONBOARD-005: GET /api/forecast?start=2026-01&months=12 -> 12 months; the starting month opens at the start balance."""
    a = seed.account("Giro", 100000, "2026-01-15")
    fc = seed.forecast("2026-01", 12)
    assert len(fc["months"]) == 12
    first = acct(fc["months"][0], a["id"])
    assert first["opening"] == 100000
    assert fc["months"][0]["opening"] == 100000


# ------------------------------------------------------------------ bookings & adjustments

@pytest.mark.contract("E2E-BOOK-002")
def test_salary_entry_roundtrips_through_state(client, seed):
    """E2E-BOOK-002: POST /api/entries (Gehalt, recurring, 300000, 2026-01-31) -> 200; /api/state lists it with amount 300000."""
    a = seed.account("Giro")
    r = client.post("/api/entries", json={"account_id": a["id"], "name": "Gehalt", "kind": "recurring", "amount": 300000,
                                          "start_date": "2026-01-31", "interval_months": 1})
    assert r.status_code == 200
    assert [(e["name"], e["amount"]) for e in seed.state()["entries"]] == [("Gehalt", 300000)]


@pytest.mark.contract("E2E-BOOK-004")
def test_transfer_shows_on_both_accounts_and_not_in_income_or_expense(client, seed):
    """E2E-BOOK-004: a 500,00 transfer is -50000 on the source, +50000 on the target (same date), excluded from income/expense."""
    a, b = seed.account("A", 100000, "2026-01-15"), seed.account("B", 0, "2026-01-15")
    seed.entry(a["id"], "Sparen", 50000, "2026-02-05", kind="once", to_account_id=b["id"])
    m = seed.forecast("2026-02", 1)["months"][0]
    src = [i for i in acct(m, a["id"])["items"] if i["type"] == "transfer"]
    dst = [i for i in acct(m, b["id"])["items"] if i["type"] == "transfer"]
    assert [(i["amount"], i["date"]) for i in src] == [(-50000, "2026-02-05")]
    assert [(i["amount"], i["date"]) for i in dst] == [(50000, "2026-02-05")]
    assert m["income"] == 0 and m["expense"] == 0


@pytest.mark.contract("E2E-BOOK-006")
def test_set_adjustment_changes_march_salary_with_a_set_amount_step(client, seed):
    """E2E-BOOK-006: after a 'set' adjustment of 320000 from 2026-03-01 the March salary is 320000 with a set_amount step."""
    a = seed.account("Giro", 100000, "2026-01-15")
    sal = seed.entry(a["id"], "Gehalt", 300000, "2026-01-31")
    seed.adjustment(sal["id"], "2026-03-01", amount=320000)
    fc = seed.forecast("2026-01", 4)
    march = [i for i in acct(fc["months"][2], a["id"])["items"] if i["label"] == "Gehalt"][0]
    feb = [i for i in acct(fc["months"][1], a["id"])["items"] if i["label"] == "Gehalt"][0]
    assert march["amount"] == 320000 and "set_amount" in [s["code"] for s in march["explanation"]]
    assert feb["amount"] == 300000


@pytest.mark.contract("E2E-BOOK-008")
def test_yearly_percent_adjustment_compounds_three_times_by_2028(client, seed):
    """E2E-BOOK-008: +2%/yr yearly from 2026-01-01 on -1.000,00: -106121 on 2028-01-01 (3x compounding)."""
    a = seed.account("Giro", 1000000, "2025-12-31")
    e = seed.entry(a["id"], "Abo", -100000, "2026-01-01", interval_months=12)
    seed.adjustment(e["id"], "2026-01-01", mode="percent", percent=2.0, repeat_yearly=True)
    fc = seed.forecast("2026-01", 25)
    by_date = {i["date"]: i["amount"] for m in fc["months"] for i in acct(m, a["id"])["items"] if i["type"] == "booking"}
    assert by_date["2026-01-01"] == -102000 and by_date["2027-01-01"] == -104040 and by_date["2028-01-01"] == -106121


@pytest.mark.contract("E2E-BOOK-010")
def test_transfer_to_same_account_is_422_with_the_code(client, seed):
    """E2E-BOOK-010: POST /api/entries with to_account_id == account_id -> 422, errors include transfer_same_account."""
    a = seed.account("Giro")
    r = client.post("/api/entries", json={"account_id": a["id"], "to_account_id": a["id"], "name": "x", "kind": "once",
                                          "amount": 100, "start_date": "2026-01-01"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error" and "transfer_same_account" in [e["code"] for e in body["params"]["errors"]]


# ------------------------------------------------------------------ checkpoints & deviation

@pytest.mark.contract("E2E-CP-002")
def test_checkpoint_roundtrips_through_state(client, seed):
    """E2E-CP-002: POST /api/checkpoints -> 200; /api/state lists it."""
    a = seed.account("Giro", 100000, "2026-01-15")
    r = client.post("/api/checkpoints", json={"account_id": a["id"], "date": "2026-02-20", "balance": 500000})
    assert r.status_code == 200
    assert (a["id"], "2026-02-20", 500000) in [(c["account_id"], c["date"], c["balance"]) for c in seed.state()["checkpoints"]]


@pytest.mark.contract("E2E-CP-003")
def test_deviation_of_a_new_checkpoint(client, seed):
    """E2E-CP-003: expected == 400000-120000-50000 and deviation == 500000 - expected for the 2026-02-20 checkpoint."""
    giro = seed.account("Giro", 100000, "2026-01-15")
    tg = seed.account("Spar", 0, "2026-01-15", kind="savings")
    seed.entry(giro["id"], "Gehalt", 300000, "2026-01-31")
    seed.entry(giro["id"], "Miete", -120000, "2026-01-01")
    seed.entry(giro["id"], "Sparen", 50000, "2026-02-05", to_account_id=tg["id"])
    seed.checkpoint(giro["id"], "2026-02-20", 500000)
    m = seed.forecast("2026-02", 1)["months"][0]
    cp = [i for i in acct(m, giro["id"])["items"] if i["type"] == "checkpoint"][0]
    assert cp["expected"] == 400000 - 120000 - 50000
    assert cp["deviation"] == 500000 - cp["expected"]


@pytest.mark.contract("E2E-CP-005", "FC-011")
def test_account_without_checkpoint_gets_a_warning_and_null_balances(client, seed):
    """E2E-CP-005: no checkpoint -> warnings contain {code: no_checkpoint, account_id}; that account's opening/closing are null."""
    a = seed.account("Giro", 100000, "2026-01-15")
    cp = seed.state()["checkpoints"][0]
    client.post(f"/api/checkpoints/{cp['id']}/archive", json={})
    fc = seed.forecast("2026-01", 3)
    assert {"code": "no_checkpoint", "account_id": a["id"]} in fc["warnings"]
    for m in fc["months"]:
        assert acct(m, a["id"])["opening"] is None and acct(m, a["id"])["closing"] is None


@pytest.mark.contract("E2E-CP-007")
def test_same_day_booking_is_applied_before_the_checkpoint(client, seed):
    """E2E-CP-007: a booking on the checkpoint's day is applied first, so it is part of `expected`."""
    a = seed.account("Giro", 100000, "2026-01-15")
    seed.entry(a["id"], "Einkauf", -30000, "2026-02-20", kind="once")
    seed.checkpoint(a["id"], "2026-02-20", 80000)
    items = acct(seed.forecast("2026-02", 1)["months"][0], a["id"])["items"]
    assert [i["type"] for i in items] == ["booking", "checkpoint"]
    assert items[1]["expected"] == 70000 and items[1]["deviation"] == 10000


# ------------------------------------------------------------------ archive / restore / undo

@pytest.mark.contract("E2E-ARCH-004")
def test_archived_booking_leaves_the_forecast_and_returns_on_restore(client, seed):
    """E2E-ARCH-004: archive removes every item of the booking from the forecast; restore brings it back."""
    a = seed.account("Giro", 100000, "2026-01-15")
    e = seed.entry(a["id"], "Miete", -120000, "2026-02-01")
    count = lambda: len([i for m in seed.forecast("2026-01", 4)["months"] for i in acct(m, a["id"])["items"] if i["type"] == "booking"])
    assert count() == 3
    client.post(f"/api/entries/{e['id']}/archive", json={})
    assert count() == 0
    client.post(f"/api/entries/{e['id']}/restore", json={})
    assert count() == 3


@pytest.mark.contract("E2E-ARCH-005")
@pytest.mark.parametrize("table", ["accounts", "entries", "adjustments", "checkpoints"])
def test_archived_records_stay_in_state_flagged(client, seed, table):
    """E2E-ARCH-005: an archived record remains in /api/state with archived:true (archived is not deleted)."""
    w = seed.standard_world()
    adj = seed.adjustment(w["salary"]["id"], "2026-03-01", amount=1)
    ids = {"accounts": w["giro"]["id"], "entries": w["salary"]["id"], "adjustments": adj["id"],
           "checkpoints": seed.state()["checkpoints"][0]["id"]}
    client.post(f"/api/{table}/{ids[table]}/archive", json={})
    assert [r["archived"] for r in seed.state()[table] if r["id"] == ids[table]] == [True]


@pytest.mark.contract("E2E-ARCH-008")
def test_revert_returns_pre_update_values_and_logs_a_revert_row(client, seed):
    """E2E-ARCH-008: POST /api/audit/{id}/revert -> the record with its old values; GET /api/audit shows revert with reverts_id."""
    a = seed.account("X")
    client.put(f"/api/accounts/{a['id']}", json={"name": "Y", "kind": "checking"})
    upd = client.get(f"/api/audit?entity=accounts&entity_id={a['id']}").json()[0]
    r = client.post(f"/api/audit/{upd['id']}/revert")
    assert r.status_code == 200 and r.json()["name"] == "X"
    newest = client.get("/api/audit?limit=1").json()[0]
    assert newest["action"] == "revert" and newest["reverts_id"] == upd["id"]


@pytest.mark.contract("E2E-ARCH-009")
@pytest.mark.parametrize("table", ["accounts", "entries", "adjustments", "checkpoints", "audit_log"])
def test_raw_delete_is_rejected_and_the_row_remains(client, seed, db_path, table):
    """E2E-ARCH-009: a raw DELETE at DB level is rejected by a trigger; the row remains."""
    w = seed.standard_world()
    seed.adjustment(w["salary"]["id"], "2026-03-01", amount=1)
    conn = sqlite3.connect(db_path)
    before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(f"DELETE FROM {table}")
    assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == before > 0
    conn.close()


# ------------------------------------------------------------------ backup & export

@pytest.mark.contract("E2E-BKP-002")
def test_marker_missing_run_fails_and_writes_no_file(client, nas, seed):
    """E2E-BKP-002: marker missing -> last_result 'error', last_error contains '.nas-marker', no backup file."""
    seed.account("Giro")
    st = client.post("/api/backup/run").json()
    assert st["last_result"] == "error" and ".nas-marker" in st["last_error"] and nas.backups() == []


@pytest.mark.contract("E2E-BKP-004", "E2E-BKP-005", "E2E-BKP-006")
def test_backup_sequence_ok_unchanged_ok_keeps_the_first_file(client, nas, seed):
    """E2E-BKP-004/005/006: ok (+.json) -> unchanged (no new file) -> change -> ok with a second file; the first is untouched."""
    nas.put_marker()
    a = seed.account("Giro")
    st = client.post("/api/backup/run").json()
    assert st["last_result"] == "ok"
    (first,) = nas.backups()
    assert NAME.match(first) and nas.backups(".json") == [first[:-7] + ".json"]
    digest = sha256(nas.path / first)
    assert client.post("/api/backup/run").json()["last_result"] == "unchanged" and nas.backups() == [first]
    client.put(f"/api/accounts/{a['id']}", json={"name": "Giro 2", "kind": "checking"})
    assert client.post("/api/backup/run").json()["last_result"] == "ok"
    assert len(nas.backups()) == 2 and first in nas.backups() and sha256(nas.path / first) == digest


@pytest.mark.contract("E2E-BKP-009")
def test_export_has_all_sections_and_an_attachment_name(client, seed):
    """E2E-BKP-009: /api/export returns the four arrays, audit_log, exported_at, data_version and a dated attachment filename."""
    seed.standard_world()
    r = client.get("/api/export")
    assert {"accounts", "entries", "adjustments", "checkpoints", "audit_log", "exported_at", "data_version"} <= set(r.json())
    assert 'attachment' in r.headers["content-disposition"] and "finanzen_export_" in r.headers["content-disposition"]


# ------------------------------------------------------------------ authentication & persistence

def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


@pytest.mark.contract("E2E-AUTH-001")
@pytest.mark.app_settings(app_password="s3cret")
def test_no_credentials_is_401_with_basic_challenge(anon_client):
    """E2E-AUTH-001: password set, no credentials -> 401 with a WWW-Authenticate: Basic header."""
    r = anon_client.get("/api/state")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")


@pytest.mark.contract("E2E-AUTH-002")
@pytest.mark.app_settings(app_password="s3cret")
def test_correct_credentials_are_200(anon_client):
    """E2E-AUTH-002: correct APP_USER/APP_PASSWORD -> 200."""
    assert anon_client.get("/api/state", headers=basic("admin", "s3cret")).status_code == 200


@pytest.mark.contract("E2E-AUTH-003")
@pytest.mark.app_settings(app_password="s3cret")
def test_wrong_password_is_401(anon_client):
    """E2E-AUTH-003: wrong password -> 401."""
    assert anon_client.get("/api/state", headers=basic("admin", "nope")).status_code == 401


@pytest.mark.contract("E2E-AUTH-004")
@pytest.mark.app_settings(app_password="s3cret")
def test_healthz_is_open(anon_client):
    """E2E-AUTH-004: /healthz needs no credentials and returns {"ok": true}."""
    r = anon_client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


@pytest.mark.contract("E2E-AUTH-005")
def test_empty_password_disables_auth(anon_client):
    """E2E-AUTH-005: empty password -> /api/state is 200 without credentials."""
    assert anon_client.get("/api/state").status_code == 200


@pytest.mark.contract("E2E-AUTH-008")
def test_a_new_session_sees_the_same_data(client, seed, make_client, settings):
    """E2E-AUTH-008: data created over the API is returned by a brand-new client/app instance on the same database."""
    seed.standard_world()
    other = make_client(settings)
    assert other.get("/api/state").json() == client.get("/api/state").json()
    assert len(other.get("/api/state").json()["accounts"]) == 2
