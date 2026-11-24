"""B-029: optional entries - the input model and the forecast engine."""
import pytest

from app import forecast, schemas
from tests.contract.backend.forecast_helpers import account, checkpoint, entry, items, month, state
from tests.contract.backend.test_schemas import ENTRY, codes


@pytest.mark.contract("SCH-021")
def test_optional_defaults_to_false():
    """SCH-021: an EntryIn without optional is planned."""
    assert schemas.EntryIn(**ENTRY).optional is False


@pytest.mark.contract("SCH-021")
@pytest.mark.parametrize("value", [True, False])
def test_optional_accepts_booleans(value):
    """SCH-021: optional takes a boolean."""
    assert schemas.EntryIn(**ENTRY, optional=value).optional is value


@pytest.mark.contract("SCH-021")
def test_optional_rejects_a_non_boolean():
    """SCH-021: a value that is not a boolean fails with bool_parsing."""
    assert "bool_parsing" in codes(schemas.EntryIn, **ENTRY, optional="vielleicht")


def run(entries, include=(), accs=None, months=2):
    """Giro (1, 5.000 €) and Notgroschen (2, 10.000 €, reserve), anchored on 2026-01-01; from 2026-02."""
    accs = accs or [account(1, "Giro"), account(2, "Notgroschen", "savings", reserve=1)]
    cps = [checkpoint(a["id"], a["id"], "2026-01-01", 500000 if a["id"] == 1 else 1000000) for a in accs]
    return forecast.compute(state(accs, entries, (), cps), "2026-02", months, include)


PLANNED = entry(1, 1, -100000, "2026-02-01", name="Miete")
TRIP = entry(2, 1, -250000, "2026-02-15", kind="once", name="Zweiter Urlaub", optional=1)


@pytest.mark.contract("FC-036")
def test_optional_entries_are_left_out_by_default():
    """FC-036: without include an optional entry yields no items and changes no number."""
    r = run([PLANNED, TRIP])
    assert [it["entry_id"] for it in items(r, "2026-02", 1) if it["type"] != "checkpoint"] == [1]
    strip = lambda res: [{k: v for k, v in m.items() if k != "with_optional"} for m in res["months"]]
    assert strip(r) == strip(run([PLANNED]))
    assert (month(r, "2026-02")["expense"], month(r, "2026-02")["closing"]) == (-100000, 1400000)


@pytest.mark.contract("FC-036")
def test_included_optional_entries_count_like_planned_ones():
    """FC-036: an optional entry whose id is in include is computed like any other; its items carry optional=true."""
    r = run([PLANNED, TRIP], include=[2])
    its = [it for it in items(r, "2026-02", 1) if it["type"] != "checkpoint"]
    assert [(it["entry_id"], it["optional"]) for it in its] == [(1, False), (2, True)]
    assert month(r, "2026-02")["expense"] == -350000 and month(r, "2026-02")["available_closing"] == 150000


@pytest.mark.contract("FC-036")
def test_include_ignores_ids_of_planned_or_unknown_entries():
    """FC-036: listing a planned or a non-existent id in include changes nothing."""
    base = run([PLANNED, TRIP])
    assert run([PLANNED, TRIP], include=[1, 99]) == base


@pytest.mark.contract("FC-037")
def test_with_optional_holds_the_totals_with_every_optional_entry():
    """FC-037: with an optional entry left out, each month carries with_optional = totals as if all were counted."""
    r = run([PLANNED, TRIP, entry(3, 1, -50000, "2026-03-05", kind="once", optional=1)])
    feb, mar = month(r, "2026-02"), month(r, "2026-03")
    assert feb["with_optional"] == {"closing": 1400000 - 250000, "available_closing": 400000 - 250000}
    assert mar["with_optional"] == {"closing": 1300000 - 300000, "available_closing": 300000 - 300000}
    assert feb["closing"] == 1400000


@pytest.mark.contract("FC-037")
def test_with_optional_is_null_when_nothing_is_left_out():
    """FC-037: with no optional entries, or all of them included, with_optional is null."""
    assert all(m["with_optional"] is None for m in run([PLANNED])["months"])
    assert all(m["with_optional"] is None for m in run([PLANNED, TRIP], include=[2])["months"])


@pytest.mark.contract("FC-037")
def test_with_optional_ignores_archived_optional_entries():
    """FC-037: an archived optional entry is not part of the comparison either."""
    gone = {**TRIP, "archived": 1}
    assert all(m["with_optional"] is None for m in run([PLANNED, gone])["months"])
