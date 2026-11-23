from datetime import date

import pytest


@pytest.fixture
def world(seed):
    return seed.standard_world()


def acct(month, account_id):
    return month["accounts"][str(account_id)]


@pytest.mark.contract("API-FC-001")
def test_four_month_forecast_shape(seed, world):
    """API-FC-001: start=2026-01&months=4 -> four labelled months with per-account closings."""
    fc = seed.forecast("2026-01", 4)
    assert [m["month"] for m in fc["months"]] == ["2026-01", "2026-02", "2026-03", "2026-04"]
    assert fc["start"] == "2026-01"
    g = world["giro"]["id"]
    assert all("closing" in acct(m, g) for m in fc["months"])


@pytest.mark.contract("API-FC-002")
def test_defaults_are_current_month_and_24_months(client, seed, world):
    """API-FC-002: no params -> start is the current month and 24 months are returned."""
    fc = client.get("/api/forecast").json()
    assert len(fc["months"]) == 24
    assert fc["months"][0]["month"] == date.today().strftime("%Y-%m")


@pytest.mark.contract("API-FC-002")
def test_months_default_applies_with_explicit_start(client):
    """API-FC-002: omitting months defaults to 24."""
    assert len(client.get("/api/forecast?start=2030-06").json()["months"]) == 24


@pytest.mark.contract("API-FC-003")
@pytest.mark.parametrize("start", ["2026-1", "2026-13x", "abc", "202601", "2026-01-01", "", "26-01", "2026_01"])
def test_malformed_start_is_422(client, start):
    """API-FC-003: a start not matching YYYY-MM -> 422."""
    assert client.get("/api/forecast", params={"start": start}).status_code == 422


@pytest.mark.contract("API-FC-004")
@pytest.mark.parametrize("months", [0, -1, 241, 1000, "abc", 1.5])
def test_months_out_of_range_is_422(client, months):
    """API-FC-004: months < 1 or > 240 (or not an integer) -> 422."""
    assert client.get("/api/forecast", params={"start": "2026-01", "months": months}).status_code == 422


@pytest.mark.contract("API-FC-004")
@pytest.mark.parametrize("months", [1, 240])
def test_months_boundaries_are_accepted(client, months):
    """API-FC-004: 1 and 240 are valid."""
    r = client.get("/api/forecast", params={"start": "2026-01", "months": months})
    assert r.status_code == 200 and len(r.json()["months"]) == months


@pytest.mark.contract("API-FC-005")
def test_forecast_numbers_follow_the_engine_contract(seed):
    """API-FC-005: checkpoints, adjustments, transfers and month-end clamping all show up in the HTTP result."""
    giro = seed.account("Checking", 100000, "2026-01-15")
    tg = seed.account("Savings", 0, "2026-01-15", kind="savings")
    sal = seed.entry(giro["id"], "Salary", 300000, "2026-01-31")
    seed.entry(giro["id"], "Rent", -120000, "2026-01-01")
    seed.entry(giro["id"], "Saving", 50000, "2026-02-05", to_account_id=tg["id"])
    seed.entry(giro["id"], "Vacation", -200000, "2026-03-10", kind="once")
    seed.adjustment(sal["id"], "2026-03-01", amount=320000, note="Raise")
    m = {x["month"]: x for x in seed.forecast("2026-01", 4)["months"]}
    g, s = giro["id"], tg["id"]
    assert acct(m["2026-01"], g)["closing"] == 400000
    assert acct(m["2026-02"], g)["closing"] == 400000 - 120000 + 300000 - 50000
    feb_close = 400000 - 120000 + 300000 - 50000
    # March: rent, raised salary (320000), the monthly saving transfer again, and the one-off vacation
    assert acct(m["2026-03"], g)["closing"] == feb_close - 120000 + 320000 - 50000 - 200000
    assert acct(m["2026-02"], s)["closing"] == 50000 and acct(m["2026-03"], s)["closing"] == 100000
    feb = [i for i in acct(m["2026-02"], g)["items"] if i["label"] == "Salary"]
    assert feb[0]["date"] == "2026-02-28"
    mar_salary = [i for i in acct(m["2026-03"], g)["items"] if i["label"] == "Salary"][0]
    assert mar_salary["amount"] == 320000 and mar_salary["explanation"][-1]["code"] == "set_amount"


@pytest.mark.contract("API-FC-006")
def test_warnings_are_present_and_language_neutral(seed):
    """API-FC-006: `warnings` is always a list; entries use codes with id params, no prose."""
    assert seed.forecast("2026-01", 2)["warnings"] == []
    a = seed.account("Giro")
    cps = seed.state()["checkpoints"]
    seed.c.post(f"/api/checkpoints/{cps[0]['id']}/archive", json={})
    w = seed.forecast("2026-01", 2)["warnings"]
    assert w == [{"code": "no_checkpoint", "account_id": a["id"]}]


@pytest.mark.contract("API-FC-007")
@pytest.mark.parametrize("start", ["2026-13", "2026-00", "2026-99"])
def test_out_of_range_month_in_start_is_rejected(client, start):
    """API-FC-007: an out-of-range month is a 422 validation error on 'start', not a wrapped month."""
    r = client.get(f"/api/forecast?start={start}&months=1")
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"
    assert [(e["field"], e["code"]) for e in body["params"]["errors"]] == [("start", "string_pattern_mismatch")]


@pytest.mark.contract("API-FC-007")
@pytest.mark.parametrize("start", ["2026-01", "2026-12"])
def test_boundary_months_are_accepted(client, start):
    """API-FC-007: January and December are valid."""
    assert client.get(f"/api/forecast?start={start}&months=1").json()["months"][0]["month"] == start


@pytest.mark.contract("API-FC-008")
def test_forecast_without_accounts(client):
    """API-FC-008: no accounts -> empty accounts/warnings and zero portfolio opening/closing."""
    fc = client.get("/api/forecast?start=2026-01&months=3").json()
    assert fc["accounts"] == [] and fc["warnings"] == []
    assert len(fc["months"]) == 3
    assert all(m["opening"] == 0 and m["closing"] == 0 for m in fc["months"])
