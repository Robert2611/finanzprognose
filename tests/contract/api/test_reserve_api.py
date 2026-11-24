"""B-028: reserve accounts through the REST API."""
import pytest

from tests.contract.api.test_resources import audit


def state_account(client, id_):
    return next(a for a in client.get("/api/state").json()["accounts"] if a["id"] == id_)


@pytest.mark.contract("API-ACC-010", "API-STATE-011")
def test_create_without_reserve_is_available(client, seed):
    """API-ACC-010/API-STATE-011: an account created without reserve is available money and reads back false."""
    acc = seed.account("Giro")
    assert acc["reserve"] == 0
    assert state_account(client, acc["id"])["reserve"] is False


@pytest.mark.contract("API-ACC-010", "API-STATE-011")
def test_create_as_reserve(client, seed):
    """API-ACC-010/API-STATE-011: reserve=true is stored and /api/state shows a real boolean true."""
    acc = seed.account("Notgroschen", kind="savings", reserve=True)
    assert state_account(client, acc["id"])["reserve"] is True


@pytest.mark.contract("API-ACC-010")
def test_put_flips_reserve_with_one_audit_row(client, seed):
    """API-ACC-010: a PUT that flips reserve writes one update audit row whose before/after differ in it."""
    acc = seed.account("Tagesgeld", kind="savings")
    r = client.put(f"/api/accounts/{acc['id']}", json={"name": "Tagesgeld", "kind": "savings", "reserve": True,
                                                       "note": "", "expected_updated_at": acc["updated_at"]})
    assert r.status_code == 200 and r.json()["reserve"] == 1
    upd = [a for a in audit(client, entity="accounts", entity_id=acc["id"]) if a["action"] == "update"]
    assert len(upd) == 1 and upd[0]["before"]["reserve"] == 0 and upd[0]["after"]["reserve"] == 1


@pytest.mark.contract("API-ACC-010")
def test_reserve_must_be_boolean(client):
    """API-ACC-010: a non-boolean reserve is a 422 validation error on the reserve field."""
    r = client.post("/api/accounts", json={"name": "X", "start_balance": 0, "start_date": "2026-01-01", "reserve": "vielleicht"})
    assert r.status_code == 422
    assert "reserve" in {e["field"] for e in r.json()["params"]["errors"]}


@pytest.mark.contract("FC-034", "FC-035")
def test_forecast_reports_available_money_and_reserve_flow(client, seed):
    """FC-034/035: /api/forecast marks reserve accounts and reports available money and the to_reserve flow."""
    giro = seed.account("Giro", 500000, "2026-01-15")
    res = seed.account("Notgroschen", 1000000, "2026-01-15", kind="savings", reserve=True)
    seed.entry(giro["id"], "Sparen", 30000, "2026-02-10", to_account_id=res["id"])
    fc = client.get("/api/forecast?start=2026-02&months=1").json()
    assert {a["name"]: a["reserve"] for a in fc["accounts"]} == {"Giro": False, "Notgroschen": True}
    m = fc["months"][0]
    assert (m["available_closing"], m["closing"], m["to_reserve"]) == (470000, 1500000, 30000)
