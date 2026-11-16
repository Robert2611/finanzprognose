from datetime import date

import pytest

from app import forecast
from tests.contract.backend.forecast_helpers import (account, acct, adjustment, checkpoint, entry, iso, items, month,
                                                     state)

A = 1


def run(accounts=None, entries=(), adjustments=(), checkpoints=None, start="2026-01", months=12):
    accounts = [account(A)] if accounts is None else accounts
    checkpoints = [checkpoint(1, A, "2026-01-15", 100000)] if checkpoints is None else checkpoints
    return forecast.compute(state(accounts, entries, adjustments, checkpoints), start, months)


# ------------------------------------------------------------------ month grid & totals

@pytest.mark.contract("FC-001")
@pytest.mark.parametrize("start,n,expected", [
    ("2026-01", 3, ["2026-01", "2026-02", "2026-03"]),
    ("2026-11", 4, ["2026-11", "2026-12", "2027-01", "2027-02"]),
    ("2026-05", 1, ["2026-05"]),
])
def test_month_grid(start, n, expected):
    """FC-001: exactly `months` consecutive calendar months labelled YYYY-MM from start."""
    r = run(start=start, months=n)
    assert [m["month"] for m in r["months"]] == expected and r["start"] == start


@pytest.mark.contract("FC-001")
def test_month_grid_length_for_long_horizon():
    """FC-001: a 120-month horizon yields 120 months ending in the right month."""
    r = run(start="2026-01", months=120)
    assert len(r["months"]) == 120 and r["months"][-1]["month"] == "2035-12"


@pytest.mark.contract("FC-002")
def test_portfolio_closing_is_sum_of_account_closings_null_as_zero():
    """FC-002: month closing/opening equal the sum over accounts; an account without checkpoint counts 0."""
    accs = [account(1), account(2)]
    r = run(accs, [entry(1, 1, 500, "2026-02-10")], checkpoints=[checkpoint(1, 1, "2026-01-15", 10000)])
    m = month(r, "2026-02")
    assert acct(m, 2)["closing"] is None
    assert m["closing"] == acct(m, 1)["closing"] == 10500
    assert m["opening"] == acct(m, 1)["opening"] == 10000


@pytest.mark.contract("FC-002")
def test_portfolio_totals_with_two_anchored_accounts():
    """FC-002: closing of the portfolio is the plain sum of two anchored accounts."""
    accs = [account(1), account(2)]
    cps = [checkpoint(1, 1, "2026-01-15", 10000), checkpoint(2, 2, "2026-01-15", 2500)]
    r = run(accs, [entry(1, 1, 700, "2026-02-10"), entry(2, 2, -300, "2026-02-12")], checkpoints=cps)
    m = month(r, "2026-02")
    assert m["closing"] == acct(m, 1)["closing"] + acct(m, 2)["closing"] == 10700 + 2200


@pytest.mark.contract("FC-003")
@pytest.mark.parametrize("year,feb_day", [(2026, "28"), (2027, "28"), (2028, "29")])
def test_monthly_entry_started_on_31st_clamps_to_month_end(year, feb_day):
    """FC-003: a monthly entry started on the 31st falls on the last day of shorter months (leap-aware)."""
    r = run(entries=[entry(1, A, 100, f"{year}-01-31")], checkpoints=[checkpoint(1, A, f"{year}-01-01", 0)],
            start=f"{year}-01", months=4)
    dates = [i["date"] for ym in (f"{year}-01", f"{year}-02", f"{year}-03", f"{year}-04")
             for i in items(r, ym, A) if i["type"] == "booking"]
    assert dates == [f"{year}-01-31", f"{year}-02-{feb_day}", f"{year}-03-31", f"{year}-04-30"]


@pytest.mark.contract("FC-003")
def test_booking_on_last_day_of_month_belongs_to_that_month():
    """FC-003: a booking dated on a month's last day is included in that month."""
    r = run(entries=[entry(1, A, 4200, "2026-02-28", kind="once")], start="2026-02", months=2)
    assert [i["date"] for i in items(r, "2026-02", A)] == ["2026-02-28"]
    assert items(r, "2026-03", A) == []


@pytest.mark.contract("FC-004", "FC-005")
def test_income_expense_sum_bookings_and_exclude_transfers():
    """FC-004/005: income sums positive bookings, expense negative ones; transfers are in neither."""
    accs = [account(1), account(2)]
    cps = [checkpoint(1, 1, "2026-01-01", 0), checkpoint(2, 2, "2026-01-01", 0)]
    es = [entry(1, 1, 300000, "2026-02-01", kind="once"), entry(2, 1, 50000, "2026-02-02", kind="once"),
          entry(3, 1, -120000, "2026-02-03", kind="once"), entry(4, 2, -7000, "2026-02-04", kind="once"),
          entry(5, 1, 99999, "2026-02-05", kind="once", to_account_id=2)]
    m = month(run(accs, es, checkpoints=cps, start="2026-02", months=1), "2026-02")
    assert m["income"] == 350000 and m["expense"] == -127000


# ------------------------------------------------------------------ checkpoints as anchors

@pytest.mark.contract("FC-006")
def test_entries_on_or_before_first_checkpoint_are_already_included():
    """FC-006: bookings dated on/before the start checkpoint don't move the balance."""
    es = [entry(1, A, -120000, "2026-01-01"), entry(2, A, -5000, "2026-01-15", kind="once"),
          entry(3, A, 300000, "2026-01-31", kind="once")]
    r = run(entries=es, start="2026-01", months=1)
    assert [i["type"] for i in items(r, "2026-01", A)].count("booking") == 1   # only the Jan 31 salary
    assert acct(month(r, "2026-01"), A)["closing"] == 400000


@pytest.mark.contract("E2E-ONBOARD-005")
def test_opening_balance_is_the_start_checkpoint():
    """E2E-ONBOARD-005: the account's starting month opens at the start balance."""
    r = run(start="2026-01", months=1)
    assert acct(month(r, "2026-01"), A)["opening"] == 100000


@pytest.mark.contract("FC-007")
def test_same_day_booking_is_applied_before_checkpoint():
    """FC-007: on the checkpoint's day the booking is applied first, so it is part of `expected`."""
    cps = [checkpoint(1, A, "2026-01-01", 1000), checkpoint(2, A, "2026-02-10", 5000)]
    r = run(entries=[entry(1, A, -300, "2026-02-10", kind="once")], checkpoints=cps, start="2026-02", months=1)
    its = items(r, "2026-02", A)
    assert [i["type"] for i in its] == ["booking", "checkpoint"]
    assert its[1]["expected"] == 700 and its[1]["deviation"] == 4300 and its[1]["balance"] == 5000


@pytest.mark.contract("FC-008", "FC-009")
def test_later_checkpoint_resets_balance_and_reports_deviation():
    """FC-008/009: a later checkpoint has expected and deviation = balance - expected; the first has neither."""
    cps = [checkpoint(1, A, "2026-01-15", 100000), checkpoint(2, A, "2026-02-20", 500000)]
    es = [entry(1, A, -120000, "2026-02-01", kind="once"), entry(2, A, -50000, "2026-02-05", kind="once")]
    r = run(entries=es, checkpoints=cps, start="2026-01", months=2)
    first = [i for i in items(r, "2026-01", A) if i["type"] == "checkpoint"]
    assert len(first) == 1 and "expected" not in first[0] and "deviation" not in first[0]
    later = [i for i in items(r, "2026-02", A) if i["type"] == "checkpoint"][0]
    assert later["expected"] == 100000 - 120000 - 50000
    assert later["deviation"] == 500000 - later["expected"] and later["balance"] == 500000
    assert acct(month(r, "2026-02"), A)["closing"] == 500000


@pytest.mark.contract("FC-010")
def test_bookings_after_a_checkpoint_continue_from_its_balance():
    """FC-010: following bookings start from the checkpoint balance."""
    cps = [checkpoint(1, A, "2026-01-15", 100000), checkpoint(2, A, "2026-02-20", 500000)]
    es = [entry(1, A, -1000, "2026-02-25", kind="once")]
    r = run(entries=es, checkpoints=cps, start="2026-02", months=1)
    assert [i["balance"] for i in items(r, "2026-02", A)] == [500000, 499000]
    assert acct(month(r, "2026-02"), A)["closing"] == 499000


@pytest.mark.contract("FC-011")
def test_account_without_checkpoint_warns_and_has_null_balances():
    """FC-011: no checkpoint -> no_checkpoint warning, null opening/closing, no booking items."""
    r = run(entries=[entry(1, A, -500, "2026-01-10")], checkpoints=[], start="2026-01", months=2)
    assert {"code": "no_checkpoint", "account_id": A} in r["warnings"]
    for ym in ("2026-01", "2026-02"):
        blk = acct(month(r, ym), A)
        assert blk["opening"] is None and blk["closing"] is None and blk["items"] == []


@pytest.mark.contract("FC-011", "FC-029")
def test_archived_checkpoint_does_not_anchor_an_account():
    """FC-011/029: an account whose only checkpoint is archived counts as having none."""
    r = run(checkpoints=[checkpoint(1, A, "2026-01-15", 100000, archived=1)], start="2026-01", months=1)
    assert {"code": "no_checkpoint", "account_id": A} in r["warnings"]


@pytest.mark.contract("FC-011")
def test_anchored_account_has_no_warning():
    """FC-011: an account with a checkpoint produces no no_checkpoint warning."""
    assert run()["warnings"] == []


@pytest.mark.contract("FC-012")
def test_checkpoint_after_the_horizon_is_ignored():
    """FC-012: a checkpoint dated after the forecast horizon neither resets nor appears."""
    cps = [checkpoint(1, A, "2026-01-15", 100000), checkpoint(2, A, "2026-06-10", 999999)]
    r = run(entries=[entry(1, A, -1000, "2026-02-01", kind="once")], checkpoints=cps, start="2026-01", months=3)
    assert acct(month(r, "2026-03"), A)["closing"] == 99000
    assert all(i["type"] != "checkpoint" or i["date"] <= "2026-03-31" for ym in ("2026-01", "2026-02", "2026-03")
               for i in items(r, ym, A))


@pytest.mark.contract("FC-012")
def test_checkpoint_on_last_day_of_horizon_is_considered():
    """FC-012: a checkpoint within the horizon (last day) is considered."""
    cps = [checkpoint(1, A, "2026-01-15", 100000), checkpoint(2, A, "2026-03-31", 7)]
    r = run(checkpoints=cps, start="2026-01", months=3)
    assert acct(month(r, "2026-03"), A)["closing"] == 7


# ------------------------------------------------------------------ occurrences

@pytest.mark.contract("FC-013")
def test_recurring_every_interval_months():
    """FC-013: a recurring entry recurs every interval_months from start_date."""
    r = run(entries=[entry(1, A, -10, "2026-02-10", interval_months=3)], start="2026-01", months=12)
    dates = [i["date"] for m in r["months"] for i in acct(m, A)["items"] if i["type"] == "booking"]
    assert dates == ["2026-02-10", "2026-05-10", "2026-08-10", "2026-11-10"]


@pytest.mark.contract("FC-013")
def test_once_entry_occurs_exactly_once():
    """FC-013: a once entry yields a single item."""
    r = run(entries=[entry(1, A, -10, "2026-04-10", kind="once")], start="2026-01", months=12)
    dates = [i["date"] for m in r["months"] for i in acct(m, A)["items"] if i["type"] == "booking"]
    assert dates == ["2026-04-10"]


@pytest.mark.contract("FC-014")
def test_end_date_stops_occurrences_inclusive():
    """FC-014: no occurrence after end_date; an occurrence on end_date itself is kept."""
    r = run(entries=[entry(1, A, -10, "2026-02-10", end_date="2026-04-10")], start="2026-01", months=8)
    dates = [i["date"] for m in r["months"] for i in acct(m, A)["items"] if i["type"] == "booking"]
    assert dates == ["2026-02-10", "2026-03-10", "2026-04-10"]


@pytest.mark.contract("FC-014")
def test_end_date_before_next_occurrence_drops_it():
    """FC-014: an end_date between two occurrences excludes the later one."""
    r = run(entries=[entry(1, A, -10, "2026-02-10", end_date="2026-04-09")], start="2026-01", months=8)
    dates = [i["date"] for m in r["months"] for i in acct(m, A)["items"] if i["type"] == "booking"]
    assert dates == ["2026-02-10", "2026-03-10"]


@pytest.mark.contract("FC-015")
def test_occurrences_ascending_inclusive_and_clamped():
    """FC-015: occurrences yields ascending dates up to and including `until`, clamped to month end."""
    got = [iso(d) for d in forecast.occurrences(entry(1, A, 1, "2026-01-31"), date(2026, 4, 30))]
    assert got == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]
    assert got == sorted(got)


@pytest.mark.contract("FC-015")
def test_occurrences_stop_before_until_when_next_is_later():
    """FC-015: nothing after the `until` bound is yielded."""
    got = [iso(d) for d in forecast.occurrences(entry(1, A, 1, "2026-01-10"), date(2026, 3, 9))]
    assert got == ["2026-01-10", "2026-02-10"]


@pytest.mark.contract("FC-015")
def test_once_occurrence_is_start_date_only():
    """FC-015: a once entry yields exactly its start date (when within until)."""
    assert [iso(d) for d in forecast.occurrences(entry(1, A, 1, "2026-05-05", kind="once"), date(2030, 1, 1))] == ["2026-05-05"]


@pytest.mark.contract("FC-016")
def test_entry_starting_after_horizon_contributes_nothing():
    """FC-016: an entry whose first occurrence is after the horizon yields no items."""
    r = run(entries=[entry(1, A, -10, "2027-06-01")], start="2026-01", months=6)
    assert all(acct(m, A)["items"] == [] or [i["type"] for i in acct(m, A)["items"]] == ["checkpoint"] for m in r["months"])
    assert acct(month(r, "2026-06"), A)["closing"] == 100000


# ------------------------------------------------------------------ amounts, adjustments, explanations

def amount_at(e, adjs, d):
    return forecast.amount_at(e, adjs, d)


@pytest.mark.contract("FC-017")
def test_no_adjustments_amount_is_base_and_explanation_is_exactly_base_step():
    """FC-017: without adjustments the amount is the stored one and the explanation is [base_amount]."""
    amt, expl = amount_at(entry(1, A, -4711, "2026-01-01"), [], date(2027, 5, 1))
    assert amt == -4711 and expl == [{"code": "base_amount", "amount": -4711}]


@pytest.mark.contract("FC-018")
def test_adjustment_after_the_date_is_not_applied():
    """FC-018: an adjustment whose effective_date is after the occurrence is ignored."""
    adj = adjustment(1, 1, "2026-03-01", amount=-9999)
    amt, expl = amount_at(entry(1, A, -100, "2026-01-01"), [adj], date(2026, 2, 28))
    assert amt == -100 and [s["code"] for s in expl] == ["base_amount"]


@pytest.mark.contract("FC-018")
def test_adjustment_applies_from_its_effective_date_inclusive():
    """FC-018: an adjustment applies on its effective_date and later."""
    adj = adjustment(1, 1, "2026-03-01", amount=-9999)
    assert amount_at(entry(1, A, -100, "2026-01-01"), [adj], date(2026, 3, 1))[0] == -9999


def booking_through_compute(adjs, base=-100, on="2026-12-01"):
    """One once-entry on `on`, run through compute() so ordering is the engine's job (see F-17)."""
    r = run(entries=[entry(1, A, base, on, kind="once")], adjustments=adjs, start=on[:7], months=1)
    return [i for i in items(r, on[:7], A) if i["type"] == "booking"][0]


@pytest.mark.contract("FC-018", "FC-024")
def test_adjustments_apply_in_effective_date_then_id_order():
    """FC-018/024: order is (effective_date, id), not list order; explanation follows application order."""
    later_low_id = adjustment(1, 1, "2026-06-01", amount=-300)
    earlier_high_id = adjustment(5, 1, "2026-03-01", amount=-200)
    same_day_b = adjustment(8, 1, "2026-09-01", amount=-500)
    same_day_a = adjustment(7, 1, "2026-09-01", amount=-400)
    it = booking_through_compute([later_low_id, same_day_b, earlier_high_id, same_day_a])
    assert it["amount"] == -500                          # last applied: effective 2026-09-01, id 8
    assert [s["code"] for s in it["explanation"]] == ["base_amount"] + ["set_amount"] * 4
    assert [s["amount"] for s in it["explanation"][1:]] == [-200, -300, -400, -500]


@pytest.mark.contract("FC-019")
def test_set_adjustment_replaces_amount_and_supersedes_earlier_ones():
    """FC-019: a set adjustment replaces the amount outright, discarding earlier percent changes."""
    pct = adjustment(1, 1, "2026-01-01", mode="percent", percent=50.0)
    st = adjustment(2, 1, "2026-02-01", amount=-777, note="Neu")
    amt, expl = amount_at(entry(1, A, -1000, "2026-01-01"), [pct, st], date(2026, 3, 1))
    assert amt == -777
    step = expl[-1]
    assert step["code"] == "set_amount" and step["amount"] == -777 and step["note"] == "Neu"
    assert str(step["date"]) == "2026-02-01"
    assert set(step) == {"code", "date", "amount", "note"}


@pytest.mark.contract("FC-020")
def test_percent_adjustment_multiplies_and_has_documented_step_shape():
    """FC-020: percent multiplies by (1 + p/100); the step carries the documented keys."""
    adj = adjustment(1, 1, "2026-01-01", mode="percent", percent=2.5, note="Inflation")
    amt, expl = amount_at(entry(1, A, -100000, "2026-01-01"), [adj], date(2026, 6, 1))
    assert amt == -102500
    step = expl[-1]
    assert set(step) == {"code", "date", "percent", "repeat_yearly", "years", "amount", "note"}
    assert step["code"] == "percent_change" and step["percent"] == 2.5 and step["amount"] == -102500
    assert step["note"] == "Inflation" and str(step["date"]) == "2026-01-01"


@pytest.mark.contract("FC-020")
@pytest.mark.parametrize("base,pct,expected", [(101, 50.0, 152), (1000, -10.0, 900), (999, 0.1, 1000), (100, 0.4, 100)])
def test_percent_rounds_half_up_to_whole_cents(base, pct, expected):
    """FC-020: the result is rounded half-up to whole cents (positive ties round up)."""
    adj = adjustment(1, 1, "2026-01-01", mode="percent", percent=pct)
    assert amount_at(entry(1, A, base, "2026-01-01"), [adj], date(2026, 1, 1))[0] == expected


@pytest.mark.contract("FC-021")
@pytest.mark.parametrize("d,expected", [("2026-06-01", -102000), ("2027-01-01", -104040), ("2028-01-01", -106121)])
def test_yearly_percent_is_applied_full_years_plus_one_times(d, expected):
    """FC-021: base -100000, +2%/yr from 2026-01-01: 1x, 2x, 3x compounding (-106121 on 2028-01-01)."""
    adj = adjustment(1, 1, "2026-01-01", mode="percent", percent=2.0, repeat_yearly=1)
    amt, expl = amount_at(entry(1, A, -100000, "2026-01-01"), [adj], date.fromisoformat(d))
    assert amt == expected


@pytest.mark.contract("FC-021")
@pytest.mark.parametrize("d,years", [("2027-06-14", 1), ("2027-06-15", 2), ("2028-06-14", 2), ("2028-06-15", 3)])
def test_yearly_percent_boundary_uses_whole_elapsed_years(d, years):
    """FC-021: the application count flips exactly on the anniversary of effective_date."""
    adj = adjustment(1, 1, "2026-06-15", mode="percent", percent=10.0, repeat_yearly=1)
    amt, expl = amount_at(entry(1, A, 1000, "2026-01-01"), [adj], date.fromisoformat(d))
    assert amt == round(1000 * 1.1 ** years) and expl[-1]["years"] == years and expl[-1]["repeat_yearly"] in (True, 1)


@pytest.mark.contract("FC-022")
def test_percent_without_repeat_is_applied_once():
    """FC-022: without repeat_yearly the change applies once (years = 1) however far in the future."""
    adj = adjustment(1, 1, "2026-01-01", mode="percent", percent=2.0, repeat_yearly=0)
    amt, expl = amount_at(entry(1, A, -100000, "2026-01-01"), [adj], date(2030, 1, 1))
    assert amt == -102000 and expl[-1]["years"] == 1 and not expl[-1]["repeat_yearly"]


@pytest.mark.contract("FC-023")
def test_rounding_happens_at_every_application_step():
    """FC-023: -9000 with +3%/yr over 3 applications is -9834 (rounding per step), not -9835 (rounded once)."""
    adj = adjustment(1, 1, "2026-01-01", mode="percent", percent=3.0, repeat_yearly=1)
    assert amount_at(entry(1, A, -9000, "2026-01-01"), [adj], date(2028, 1, 1))[0] == -9834


@pytest.mark.contract("FC-024")
def test_explanation_lists_base_then_each_applied_adjustment():
    """FC-024: explanation order is base_amount, then each applied adjustment step in application order."""
    a1 = adjustment(1, 1, "2026-02-01", mode="percent", percent=10.0)
    a2 = adjustment(2, 1, "2026-04-01", amount=-50)
    it = booking_through_compute([a2, a1], on="2026-05-01")
    assert [s["code"] for s in it["explanation"]] == ["base_amount", "percent_change", "set_amount"]
    assert it["amount"] == -50 and it["explanation"][0] == {"code": "base_amount", "amount": -100}


@pytest.mark.contract("FC-025")
@pytest.mark.parametrize("a,b,n", [
    (date(2026, 1, 1), date(2026, 1, 1), 0),
    (date(2026, 1, 15), date(2027, 1, 14), 0),
    (date(2026, 1, 15), date(2027, 1, 15), 1),
    (date(2026, 1, 15), date(2029, 3, 1), 3),
    (date(2026, 6, 30), date(2026, 12, 31), 0),
    (date(2028, 2, 29), date(2029, 2, 28), 0),
])
def test_full_years(a, b, n):
    """FC-025: full_years counts whole elapsed years, decremented when b's month/day is before a's."""
    assert forecast.full_years(a, b) == n


@pytest.mark.contract("FC-025")
def test_add_months_wraps_across_years():
    """FC-025/F-3: add_months is calendar month arithmetic (1-based months assumed, see CONTRACT_FEEDBACK)."""
    assert tuple(forecast.add_months(2026, 11, 3)) == (2027, 2)
    assert tuple(forecast.add_months(2026, 1, 0)) == (2026, 1)
    assert tuple(forecast.add_months(2026, 12, 12)) == (2027, 12)


# ------------------------------------------------------------------ transfers

def transfer_world():
    accs = [account(1, "Giro"), account(2, "Tagesgeld")]
    cps = [checkpoint(1, 1, "2026-01-01", 100000), checkpoint(2, 2, "2026-01-01", 0)]
    es = [entry(1, 1, 50000, "2026-02-05", name="Sparen", kind="once", to_account_id=2, category="Sparen")]
    return run(accs, es, checkpoints=cps, start="2026-02", months=1)


@pytest.mark.contract("FC-026")
def test_transfer_creates_minus_item_on_source_and_plus_on_target():
    """FC-026: a transfer stored positive gives -amount on the source and +amount on the target, same date."""
    r = transfer_world()
    src = [i for i in items(r, "2026-02", 1) if i["type"] == "transfer"]
    dst = [i for i in items(r, "2026-02", 2) if i["type"] == "transfer"]
    assert [(i["amount"], i["date"]) for i in src] == [(-50000, "2026-02-05")]
    assert [(i["amount"], i["date"]) for i in dst] == [(50000, "2026-02-05")]
    assert src[0]["entry_id"] == dst[0]["entry_id"] == 1
    m = month(r, "2026-02")
    assert acct(m, 1)["closing"] == 50000 and acct(m, 2)["closing"] == 50000


@pytest.mark.contract("FC-027")
def test_transfer_labels_name_the_other_account():
    """FC-027: source label '<name> → <target>', target label '<name> ← <source>'."""
    r = transfer_world()
    assert [i["label"] for i in items(r, "2026-02", 1) if i["type"] == "transfer"] == ["Sparen → Tagesgeld"]
    assert [i["label"] for i in items(r, "2026-02", 2) if i["type"] == "transfer"] == ["Sparen ← Giro"]


@pytest.mark.skip(reason="Open question #7 (transfer to archived target dropped on both sides): behavior not asserted pending resolution")
@pytest.mark.contract("FC-028")
def test_transfer_to_archived_target_is_skipped_with_warning():
    """FC-028: skipped, see OPEN_QUESTIONS #7."""


# ------------------------------------------------------------------ archiving & scope

@pytest.mark.contract("FC-029")
def test_archived_account_is_excluded_entirely():
    """FC-029/030: an archived account is absent from `accounts` and from every month's account blocks."""
    accs = [account(1), account(2, archived=1)]
    cps = [checkpoint(1, 1, "2026-01-01", 0), checkpoint(2, 2, "2026-01-01", 5)]
    r = run(accs, checkpoints=cps, start="2026-01", months=2)
    assert [a["id"] for a in r["accounts"]] == [1]
    assert all(str(2) not in {str(k) for k in m["accounts"]} for m in r["months"])


@pytest.mark.contract("FC-029")
def test_archived_entry_is_excluded():
    """FC-029: an archived entry contributes no items."""
    r = run(entries=[entry(1, A, -500, "2026-02-01", archived=1)], start="2026-02", months=1)
    assert items(r, "2026-02", A) == [] and acct(month(r, "2026-02"), A)["closing"] == 100000


@pytest.mark.contract("FC-029")
def test_archived_adjustment_is_excluded():
    """FC-029: an archived adjustment has no effect and no explanation step."""
    adj = adjustment(1, 1, "2026-01-01", amount=-9999, archived=1)
    r = run(entries=[entry(1, A, -500, "2026-02-01", kind="once")], adjustments=[adj], start="2026-02", months=1)
    it = items(r, "2026-02", A)[0]
    assert it["amount"] == -500 and [s["code"] for s in it["explanation"]] == ["base_amount"]


@pytest.mark.contract("FC-029")
def test_archived_later_checkpoint_is_excluded():
    """FC-029: an archived (non-first) checkpoint neither resets the balance nor appears."""
    cps = [checkpoint(1, A, "2026-01-15", 100000), checkpoint(2, A, "2026-02-20", 1, archived=1)]
    r = run(checkpoints=cps, start="2026-02", months=1)
    assert acct(month(r, "2026-02"), A)["closing"] == 100000
    assert all(i["type"] != "checkpoint" for i in items(r, "2026-02", A))


@pytest.mark.contract("FC-030")
def test_top_level_accounts_are_id_name_kind_only():
    """FC-030: result['accounts'] lists non-archived accounts as {id, name, kind}."""
    accs = [account(1, "Giro", "checking"), account(2, "Depot", "custody"), account(3, "Alt", archived=1)]
    r = run(accs, checkpoints=[checkpoint(1, 1, "2026-01-01", 0), checkpoint(2, 2, "2026-01-01", 0)])
    assert r["accounts"] == [{"id": 1, "name": "Giro", "kind": "checking"}, {"id": 2, "name": "Depot", "kind": "custody"}]


# ------------------------------------------------------------------ item invariants

@pytest.mark.contract("FC-031")
def test_booking_item_carries_all_documented_fields():
    """FC-031: booking items have entry_id, ISO date, category, label, signed amount, balance, explanation."""
    r = run(entries=[entry(7, A, -2500, "2026-02-03", name="Miete", category="Wohnen", kind="once")], start="2026-02", months=1)
    it = items(r, "2026-02", A)[0]
    assert set(it) == {"type", "entry_id", "date", "category", "label", "amount", "balance", "explanation"}
    assert (it["type"], it["entry_id"], it["date"], it["category"], it["label"], it["amount"], it["balance"]) == \
           ("booking", 7, "2026-02-03", "Wohnen", "Miete", -2500, 97500)
    assert it["explanation"]


@pytest.mark.contract("FC-031")
def test_checkpoint_item_fields():
    """FC-031: checkpoint items have checkpoint_id, date, balance, note (+ expected/deviation when later)."""
    cps = [checkpoint(1, A, "2026-01-15", 100000, note="Start"), checkpoint(2, A, "2026-02-20", 500000, note="Ist")]
    r = run(checkpoints=cps, start="2026-01", months=2)
    first = [i for i in items(r, "2026-01", A) if i["type"] == "checkpoint"][0]
    later = [i for i in items(r, "2026-02", A) if i["type"] == "checkpoint"][0]
    assert set(first) == {"type", "checkpoint_id", "date", "balance", "note"}
    assert set(later) == {"type", "checkpoint_id", "date", "balance", "note", "expected", "deviation"}
    assert (first["checkpoint_id"], first["note"], later["checkpoint_id"], later["note"]) == (1, "Start", 2, "Ist")


@pytest.mark.contract("FC-032")
def test_items_ordered_by_date_then_bookings_before_checkpoints_with_running_balance():
    """FC-032: items are date-ordered, bookings precede checkpoints on a day, and balance is the running total."""
    cps = [checkpoint(1, A, "2026-01-15", 1000), checkpoint(2, A, "2026-02-10", 9000)]
    es = [entry(1, A, -100, "2026-02-20", kind="once"), entry(2, A, -200, "2026-02-03", kind="once"),
          entry(3, A, 50, "2026-02-10", kind="once")]
    its = items(run(entries=es, checkpoints=cps, start="2026-02", months=1), "2026-02", A)
    assert [(i["date"], i["type"]) for i in its] == [("2026-02-03", "booking"), ("2026-02-10", "booking"),
                                                      ("2026-02-10", "checkpoint"), ("2026-02-20", "booking")]
    assert [i["balance"] for i in its] == [800, 850, 9000, 8900]


@pytest.mark.contract("FC-032")
def test_same_day_bookings_are_ordered_by_entry_id():
    """FC-032: same-day bookings are ordered by id."""
    es = [entry(9, A, -1, "2026-02-03", kind="once"), entry(4, A, -2, "2026-02-03", kind="once")]
    its = items(run(entries=es, start="2026-02", months=1), "2026-02", A)
    assert [i["entry_id"] for i in its] == [4, 9]
