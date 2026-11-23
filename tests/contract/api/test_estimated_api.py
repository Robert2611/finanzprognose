"""B-015: the estimated mark on entries through the REST API."""
import pytest

from tests.contract.api.test_resources import audit, entry_body


@pytest.fixture
def acc(seed):
    return seed.account("Giro")


def state_entry(client, id_):
    return next(e for e in client.get("/api/state").json()["entries"] if e["id"] == id_)


@pytest.mark.contract("API-RES-021", "API-STATE-010")
def test_create_without_estimated_is_fixed(client, acc):
    """API-RES-021/API-STATE-010: an entry created without estimated is fixed and reads back as false."""
    row = client.post("/api/entries", json=entry_body(acc["id"])).json()
    assert row["estimated"] == 0
    assert state_entry(client, row["id"])["estimated"] is False


@pytest.mark.contract("API-RES-021", "API-STATE-010")
def test_create_as_estimated(client, acc):
    """API-RES-021/API-STATE-010: estimated=true is stored and /api/state shows a real boolean true."""
    row = client.post("/api/entries", json=entry_body(acc["id"], name="Lebensmittel", amount=-45000, estimated=True)).json()
    assert state_entry(client, row["id"])["estimated"] is True


@pytest.mark.contract("API-RES-021")
def test_put_flips_estimated_with_one_audit_row(client, acc):
    """API-RES-021: a PUT that flips estimated writes one update audit row whose before/after differ in it."""
    row = client.post("/api/entries", json=entry_body(acc["id"])).json()
    r = client.put(f"/api/entries/{row['id']}", json=entry_body(acc["id"], estimated=True, expected_updated_at=row["updated_at"]))
    assert r.status_code == 200 and r.json()["estimated"] == 1
    upd = [a for a in audit(client, entity="entries", entity_id=row["id"]) if a["action"] == "update"]
    assert len(upd) == 1
    assert upd[0]["before"]["estimated"] == 0 and upd[0]["after"]["estimated"] == 1


@pytest.mark.contract("API-RES-021")
def test_estimated_must_be_boolean(client, acc):
    """API-RES-021: a non-boolean estimated is a 422 validation error on the estimated field."""
    r = client.post("/api/entries", json=entry_body(acc["id"], estimated="vielleicht"))
    assert r.status_code == 422
    assert "estimated" in {e["field"] for e in r.json()["params"]["errors"]}


@pytest.mark.contract("FC-033")
def test_forecast_items_show_the_mark(client, acc):
    """FC-033: through /api/forecast the items of an estimated entry carry estimated=true."""
    e = client.post("/api/entries", json=entry_body(acc["id"], name="Lebensmittel", amount=-45000, estimated=True)).json()
    fc = client.get("/api/forecast?start=2026-02&months=1").json()
    its = [it for it in fc["months"][0]["accounts"][str(acc["id"])]["items"] if it.get("entry_id") == e["id"]]
    assert its and all(it["estimated"] is True for it in its)
