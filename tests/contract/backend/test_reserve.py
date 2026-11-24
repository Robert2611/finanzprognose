"""B-028: reserve accounts - the input model and the forecast engine."""
import pytest

from app import forecast, schemas
from tests.contract.backend.forecast_helpers import account, checkpoint, entry, month, state
from tests.contract.backend.test_schemas import codes

ACC = dict(name="Notgroschen", kind="savings", note="")


@pytest.mark.contract("SCH-020")
def test_reserve_defaults_to_false():
    """SCH-020: an AccountIn without reserve is available money."""
    assert schemas.AccountIn(**ACC).reserve is False
    assert schemas.AccountCreate(**ACC, start_balance=0, start_date="2026-01-01").reserve is False


@pytest.mark.contract("SCH-020")
@pytest.mark.parametrize("value", [True, False])
def test_reserve_accepts_booleans(value):
    """SCH-020: reserve takes a boolean."""
    assert schemas.AccountIn(**ACC, reserve=value).reserve is value


@pytest.mark.contract("SCH-020")
def test_reserve_rejects_a_non_boolean():
    """SCH-020: a value that is not a boolean fails with bool_parsing."""
    assert "bool_parsing" in codes(schemas.AccountIn, **ACC, reserve="vielleicht")


def run(entries, reserve=1, months=2):
    """Giro (1, 5.000 €) and Notgroschen (2, 10.000 €, reserve unless reserve=0), anchored on 2026-01-01."""
    accs = [account(1, "Giro"), account(2, "Notgroschen", "savings", reserve=reserve)]
    cps = [checkpoint(1, 1, "2026-01-01", 500000), checkpoint(2, 2, "2026-01-01", 1000000)]
    return forecast.compute(state(accs, entries, (), cps), "2026-02", months)


@pytest.mark.contract("FC-034")
def test_available_money_leaves_out_reserve_accounts():
    """FC-034: available_opening/closing sum only the non-reserve accounts; opening/closing still sum all."""
    m = month(run([entry(1, 1, -100000, "2026-02-03"), entry(2, 2, 2000, "2026-02-28", name="Zinsen")]), "2026-02")
    assert (m["opening"], m["closing"]) == (1500000, 1402000)
    assert (m["available_opening"], m["available_closing"]) == (500000, 400000)


@pytest.mark.contract("FC-034")
def test_without_reserve_accounts_available_equals_the_total():
    """FC-034: with no reserve account the available money is the total and to_reserve is 0."""
    m = month(run([entry(1, 1, 30000, "2026-02-10", to_account_id=2)], reserve=0), "2026-02")
    assert (m["available_opening"], m["available_closing"]) == (m["opening"], m["closing"])
    assert m["to_reserve"] == 0


@pytest.mark.contract("FC-035")
def test_transfers_into_and_out_of_the_reserve_are_the_to_reserve_flow():
    """FC-035: putting money aside counts positive, taking it out negative; both net per month."""
    es = [entry(1, 1, 30000, "2026-02-10", to_account_id=2, name="Sparen"),
          entry(2, 2, 80000, "2026-03-05", to_account_id=1, kind="once", name="Reparatur")]
    r = run(es)
    feb, mar = month(r, "2026-02"), month(r, "2026-03")
    assert feb["to_reserve"] == 30000
    assert mar["to_reserve"] == 30000 - 80000
    assert feb["available_closing"] == 500000 - 30000
    assert mar["available_closing"] == 500000 - 60000 + 80000


@pytest.mark.contract("FC-035")
def test_transfers_between_available_accounts_and_bookings_are_not_reserve_flow():
    """FC-035: a transfer between two available accounts, and bookings on a reserve account, are not to_reserve."""
    accs = [account(1, "Giro"), account(2, "Tagesgeld", "savings"), account(3, "Notgroschen", "savings", reserve=1)]
    cps = [checkpoint(i, i, "2026-01-01", 0) for i in (1, 2, 3)]
    es = [entry(1, 1, 30000, "2026-02-10", to_account_id=2), entry(2, 3, 500, "2026-02-28", name="Zinsen")]
    m = month(forecast.compute(state(accs, es, (), cps), "2026-02", 1), "2026-02")
    assert m["to_reserve"] == 0
    assert m["income"] == 500          # income/expense still cover every account (FC-004)


@pytest.mark.contract("FC-035")
def test_transfer_to_an_archived_reserve_is_not_reserve_flow():
    """FC-035: when the reserve target is archived it is no longer a reserve account; the money just leaves (FC-028)."""
    accs = [account(1, "Giro"), account(2, "Notgroschen", "savings", archived=1, reserve=1)]
    es = [entry(1, 1, 30000, "2026-02-10", to_account_id=2)]
    m = month(forecast.compute(state(accs, es, (), [checkpoint(1, 1, "2026-01-01", 0)]), "2026-02", 1), "2026-02")
    assert m["to_reserve"] == 0 and m["available_closing"] == -30000
