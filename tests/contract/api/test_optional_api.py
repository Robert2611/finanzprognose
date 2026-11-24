"""B-029: optional entries through the REST API."""
import pytest

from tests.contract.api.test_resources import audit, entry_body


@pytest.fixture
def acc(seed):
    return seed.account("Giro", 500000, "2026-01-15")


def state_entry(client, id_):
    return next(e for e in client.get("/api/state").json()["entries"] if e["id"] == id_)


@pytest.mark.contract("API-RES-022", "API-STATE-012")
def test_create_without_optional_is_planned(client, acc):
    """API-RES-022/API-STATE-012: an entry created without optional is planned and reads back false."""
    row = client.post("/api/entries", json=entry_body(acc["id"])).json()
    assert row["optional"] == 0
    assert state_entry(client, row["id"])["optional"] is False


@pytest.mark.contract("API-RES-022", "API-STATE-012")
def test_create_as_optional(client, acc):
    """API-RES-022/API-STATE-012: optional=true is stored and /api/state shows a real boolean true."""
    row = client.post("/api/entries", json=entry_body(acc["id"], kind="once", optional=True)).json()
    assert state_entry(client, row["id"])["optional"] is True


@pytest.mark.contract("API-RES-022")
def test_put_flips_optional_with_one_audit_row(client, acc):
    """API-RES-022: a PUT that flips optional writes one update audit row whose before/after differ in it."""
    row = client.post("/api/entries", json=entry_body(acc["id"])).json()
    r = client.put(f"/api/entries/{row['id']}", json=entry_body(acc["id"], optional=True, expected_updated_at=row["updated_at"]))
    assert r.status_code == 200 and r.json()["optional"] == 1
    upd = [a for a in audit(client, entity="entries", entity_id=row["id"]) if a["action"] == "update"]
    assert len(upd) == 1 and upd[0]["before"]["optional"] == 0 and upd[0]["after"]["optional"] == 1


@pytest.mark.contract("API-RES-022")
def test_optional_must_be_boolean(client, acc):
    """API-RES-022: a non-boolean optional is a 422 validation error on the optional field."""
    r = client.post("/api/entries", json=entry_body(acc["id"], optional="vielleicht"))
    assert r.status_code == 422
    assert "optional" in {e["field"] for e in r.json()["params"]["errors"]}


@pytest.mark.contract("API-FC-009")
def test_include_switches_optional_entries_into_the_forecast(client, seed, acc):
    """API-FC-009: optional entries are left out unless listed in the repeatable include parameter."""
    a = seed.entry(acc["id"], "Urlaub", -250000, "2026-02-15", kind="once", optional=True)
    b = seed.entry(acc["id"], "Sofa", -80000, "2026-02-20", kind="once", optional=True)
    base = client.get("/api/forecast?start=2026-02&months=1").json()["months"][0]
    assert base["closing"] == 500000
    assert base["with_optional"] == {"closing": 170000, "available_closing": 170000}
    one = client.get(f"/api/forecast?start=2026-02&months=1&include={a['id']}").json()["months"][0]
    assert one["closing"] == 250000 and one["with_optional"]["closing"] == 170000
    both = client.get(f"/api/forecast?start=2026-02&months=1&include={a['id']}&include={b['id']}").json()["months"][0]
    assert both["closing"] == 170000 and both["with_optional"] is None


@pytest.mark.contract("API-FC-009")
def test_include_must_be_integers(client):
    """API-FC-009: a non-integer include value is a 422 validation error."""
    r = client.get("/api/forecast?start=2026-02&months=1&include=abc")
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
