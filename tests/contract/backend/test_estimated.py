"""B-015: entries marked as estimated - the input model and the forecast engine."""
import pytest

from app import forecast, schemas
from tests.contract.backend.forecast_helpers import account, checkpoint, entry, items, month, state
from tests.contract.backend.test_schemas import ENTRY, codes


@pytest.mark.contract("SCH-019")
def test_estimated_defaults_to_false():
    """SCH-019: an EntryIn without estimated is a fixed amount."""
    assert schemas.EntryIn(**ENTRY).estimated is False


@pytest.mark.contract("SCH-019")
@pytest.mark.parametrize("value", [True, False])
def test_estimated_accepts_booleans(value):
    """SCH-019: estimated takes a boolean."""
    assert schemas.EntryIn(**ENTRY, estimated=value).estimated is value


@pytest.mark.contract("SCH-019")
def test_estimated_rejects_a_non_boolean():
    """SCH-019: a value that is not a boolean fails with bool_parsing."""
    assert "bool_parsing" in codes(schemas.EntryIn, **ENTRY, estimated="vielleicht")


def run(entries):
    accs = [account(1), account(2)]
    cps = [checkpoint(1, 1, "2026-01-01", 0), checkpoint(2, 2, "2026-01-01", 0)]
    return forecast.compute(state(accs, entries, (), cps), "2026-02", 1)


@pytest.mark.contract("FC-033")
@pytest.mark.parametrize("stored, expected", [(1, True), (True, True), (0, False), (None, False)])
def test_items_carry_the_entry_estimated_flag(stored, expected):
    """FC-033: booking and transfer items (both sides) copy estimated from their entry; missing -> false."""
    es = [entry(1, 1, -45000, "2026-02-03", estimated=stored),
          entry(2, 1, 10000, "2026-02-04", to_account_id=2, estimated=stored)]
    r = run(es)
    its = items(r, "2026-02", 1) + items(r, "2026-02", 2)
    assert {it["type"] for it in its if it["type"] != "checkpoint"} == {"booking", "transfer"}
    assert all(it["estimated"] is expected for it in its if it["type"] != "checkpoint")


@pytest.mark.contract("FC-033")
def test_estimated_mark_does_not_change_the_numbers():
    """FC-033: an estimated entry yields the same amounts, balances, explanations and totals as a fixed one."""
    def strip(result):
        for m in result["months"]:
            for a in m["accounts"].values():
                for it in a["items"]:
                    it.pop("estimated", None)
        return result
    fixed = [entry(1, 1, -45000, "2026-02-03"), entry(2, 1, 250000, "2026-02-01", estimated=0)]
    est = [entry(1, 1, -45000, "2026-02-03", estimated=1), entry(2, 1, 250000, "2026-02-01", estimated=1)]
    assert strip(run(est)) == strip(run(fixed))
    m = month(run(est), "2026-02")
    assert m["income"] == 250000 and m["expense"] == -45000
