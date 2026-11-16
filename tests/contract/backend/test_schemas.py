import pytest
from pydantic import ValidationError

from app import errors, schemas

ENTRY = dict(account_id=1, to_account_id=None, name="x", category="", kind="recurring", amount=-500,
             start_date="2026-01-01", end_date=None, interval_months=1, note="")
ADJ = dict(entry_id=1, effective_date="2026-01-01", mode="set", amount=100, percent=None, repeat_yearly=False, note="")
CP = dict(account_id=1, date="2026-01-01", balance=0, note="")
ACC = dict(name="Giro", kind="checking", note="")
ACC_CREATE = dict(ACC, start_balance=0, start_date="2026-01-01")


def errs(model, **kw):
    """[(field, code)] of the validation errors, or [] if the body is valid (via errors.validation_detail)."""
    try:
        model(**kw)
    except ValidationError as ex:
        return [(e["field"], e["code"]) for e in errors.validation_detail(ex)["params"]["errors"]]
    return []


def codes(model, **kw):
    return {c for _, c in errs(model, **kw)}


def fields(model, **kw):
    return {f for f, _ in errs(model, **kw)}


# --------------------------------------------------------------------------- field level

@pytest.mark.contract("SCH-001")
@pytest.mark.parametrize("model,base", [(schemas.AccountIn, ACC), (schemas.EntryIn, ENTRY)])
@pytest.mark.parametrize("name,expected", [("", "string_too_short"), ("x" * 101, "string_too_long"),
                                           ("a", None), ("x" * 100, None), ("Größe 日本語 😀", None)])
def test_name_length(model, base, name, expected):
    """SCH-001: names are 1-100 characters (counted in characters, unicode allowed)."""
    c = codes(model, **{**base, "name": name})
    assert (expected in c) if expected else not c


@pytest.mark.contract("SCH-002")
@pytest.mark.parametrize("kind", ["checking", "savings", "custody", "credit_card", "cash", "other"])
def test_account_kind_accepts_the_six_values(kind):
    """SCH-002: all six account kinds validate."""
    assert not errs(schemas.AccountIn, **{**ACC, "kind": kind})


@pytest.mark.contract("SCH-002")
@pytest.mark.parametrize("kind", ["", "Checking", "loan", None, 5])
def test_account_kind_rejects_others(kind):
    """SCH-002: any other kind is a validation error on `kind`."""
    assert "kind" in fields(schemas.AccountIn, **{**ACC, "kind": kind})


@pytest.mark.contract("SCH-002")
def test_account_kind_defaults_to_checking():
    """SCH-002: omitting kind defaults to 'checking'."""
    assert schemas.AccountIn(name="x").kind == "checking"


@pytest.mark.contract("SCH-003")
@pytest.mark.parametrize("kind", ["recurring", "once"])
def test_entry_kind_accepts_allowed(kind):
    """SCH-003: recurring and once validate."""
    assert not errs(schemas.EntryIn, **{**ENTRY, "kind": kind})


@pytest.mark.contract("SCH-003")
@pytest.mark.parametrize("kind", ["weekly", "", "ONCE"])
def test_entry_kind_rejects_others(kind):
    """SCH-003: other entry kinds are rejected."""
    assert "kind" in fields(schemas.EntryIn, **{**ENTRY, "kind": kind})


@pytest.mark.contract("SCH-003")
def test_entry_kind_is_required():
    """SCH-003: entry kind has no default."""
    body = {k: v for k, v in ENTRY.items() if k != "kind"}
    assert ("kind", "missing") in errs(schemas.EntryIn, **body)


@pytest.mark.contract("SCH-004")
@pytest.mark.parametrize("mode", ["set", "percent"])
def test_adjustment_mode_accepts_allowed(mode):
    """SCH-004: set and percent validate (with the matching value)."""
    body = {**ADJ, "mode": mode, "amount": 5 if mode == "set" else None, "percent": 1.5 if mode == "percent" else None}
    assert not errs(schemas.AdjustmentIn, **body)


@pytest.mark.contract("SCH-004")
@pytest.mark.parametrize("mode", ["multiply", "", "SET"])
def test_adjustment_mode_rejects_others(mode):
    """SCH-004: other modes are rejected on `mode`."""
    assert "mode" in fields(schemas.AdjustmentIn, **{**ADJ, "mode": mode})


@pytest.mark.contract("SCH-004")
def test_adjustment_mode_is_required():
    """SCH-004: mode has no default."""
    body = {k: v for k, v in ADJ.items() if k != "mode"}
    assert ("mode", "missing") in errs(schemas.AdjustmentIn, **body)


@pytest.mark.contract("SCH-005")
@pytest.mark.parametrize("n,expected", [(0, "greater_than_equal"), (-1, "greater_than_equal"), (121, "less_than_equal"),
                                        (1000, "less_than_equal"), (1, None), (12, None), (120, None)])
def test_interval_months_range(n, expected):
    """SCH-005: interval_months must be 1-120."""
    c = codes(schemas.EntryIn, **{**ENTRY, "interval_months": n})
    assert (expected in c) if expected else not c


@pytest.mark.contract("SCH-005")
def test_interval_months_defaults_to_one():
    """SCH-005: omitted interval_months is 1."""
    body = {k: v for k, v in ENTRY.items() if k != "interval_months"}
    assert schemas.EntryIn(**body).interval_months == 1


@pytest.mark.contract("SCH-006")
@pytest.mark.parametrize("p,expected", [(-100, "greater_than"), (-150.0, "greater_than"), (1000, "less_than"),
                                        (5000.5, "less_than"), (-99.99, None), (0, None), (999.99, None)])
def test_percent_bounds(p, expected):
    """SCH-006: percent must be > -100 and < 1000."""
    c = codes(schemas.AdjustmentIn, **{**ADJ, "mode": "percent", "amount": None, "percent": p})
    assert (expected in c) if expected else not c


@pytest.mark.contract("SCH-007")
@pytest.mark.parametrize("model,base,limit", [(schemas.AccountIn, ACC, 2000), (schemas.EntryIn, ENTRY, 2000),
                                              (schemas.AdjustmentIn, ADJ, 500), (schemas.CheckpointIn, CP, 500)])
def test_note_length_limits(model, base, limit):
    """SCH-007: note limit is 2000 for accounts/entries and 500 for adjustments/checkpoints."""
    assert not errs(model, **{**base, "note": "n" * limit})
    assert ("note", "string_too_long") in errs(model, **{**base, "note": "n" * (limit + 1)})


@pytest.mark.contract("SCH-007")
@pytest.mark.parametrize("model,base", [(schemas.AccountIn, ACC), (schemas.EntryIn, ENTRY),
                                        (schemas.AdjustmentIn, ADJ), (schemas.CheckpointIn, CP)])
def test_comment_limit_500(model, base):
    """SCH-007: comment is limited to 500 characters on every write model."""
    assert not errs(model, **{**base, "comment": "c" * 500})
    assert ("comment", "string_too_long") in errs(model, **{**base, "comment": "c" * 501})


@pytest.mark.contract("SCH-008")
@pytest.mark.parametrize("model,base,field", [(schemas.EntryIn, ENTRY, "amount"), (schemas.CheckpointIn, CP, "balance"),
                                              (schemas.AccountCreate, ACC_CREATE, "start_balance"),
                                              (schemas.AdjustmentIn, ADJ, "amount")])
@pytest.mark.parametrize("bad", ["abc", "12,50", 1.5, [1], {"a": 1}])
def test_money_must_be_integer_cents(model, base, field, bad):
    """SCH-008: non-integer money values are validation errors on that field."""
    assert field in fields(model, **{**base, field: bad})


@pytest.mark.contract("SCH-008")
@pytest.mark.parametrize("model,base,field", [(schemas.EntryIn, ENTRY, "amount"), (schemas.CheckpointIn, CP, "balance"),
                                              (schemas.AccountCreate, ACC_CREATE, "start_balance")])
@pytest.mark.parametrize("value", [-100000, 1, 10**12])
def test_money_accepts_integers(model, base, field, value):
    """SCH-008: integer cents (negative and large) are accepted."""
    assert not errs(model, **{**base, field: value})


@pytest.mark.contract("SCH-009")
@pytest.mark.parametrize("model,base,field", [(schemas.EntryIn, ENTRY, "start_date"), (schemas.EntryIn, ENTRY, "end_date"),
                                              (schemas.AdjustmentIn, ADJ, "effective_date"), (schemas.CheckpointIn, CP, "date"),
                                              (schemas.AccountCreate, ACC_CREATE, "start_date")])
@pytest.mark.parametrize("bad", ["not-a-date", "2026-02-30", "2026-13-01", "01.02.2026", "2026/01/01"])
def test_dates_must_be_iso(model, base, field, bad):
    """SCH-009: non-ISO or impossible dates are validation errors on that field."""
    assert field in fields(model, **{**base, field: bad})


@pytest.mark.contract("SCH-009")
@pytest.mark.parametrize("model,base,field", [(schemas.EntryIn, ENTRY, "start_date"), (schemas.CheckpointIn, CP, "date")])
@pytest.mark.parametrize("ok", ["2026-01-01", "2028-02-29", "1999-12-31"])
def test_dates_accept_iso(model, base, field, ok):
    """SCH-009: valid ISO dates (incl. a leap day) validate."""
    assert not errs(model, **{**base, field: ok})


# --------------------------------------------------------------------------- cross-field

@pytest.mark.contract("SCH-010")
def test_end_before_start_is_rejected():
    """SCH-010: end_date earlier than start_date -> end_before_start."""
    assert "end_before_start" in codes(schemas.EntryIn, **{**ENTRY, "start_date": "2026-02-01", "end_date": "2026-01-31"})


@pytest.mark.contract("SCH-010")
@pytest.mark.parametrize("end", ["2026-02-01", "2026-03-01", None])
def test_end_on_or_after_start_is_fine(end):
    """SCH-010: end_date equal to or after start_date (or absent) is valid."""
    assert not errs(schemas.EntryIn, **{**ENTRY, "start_date": "2026-02-01", "end_date": end})


@pytest.mark.contract("SCH-011")
def test_once_entry_is_normalised():
    """SCH-011: kind=once forces end_date None and interval_months 1 (no error)."""
    m = schemas.EntryIn(**{**ENTRY, "kind": "once", "end_date": "2026-02-01", "interval_months": 6})
    assert m.end_date is None and m.interval_months == 1


@pytest.mark.contract("SCH-012")
def test_transfer_to_same_account_is_rejected():
    """SCH-012: to_account_id == account_id -> transfer_same_account."""
    assert "transfer_same_account" in codes(schemas.EntryIn, **{**ENTRY, "to_account_id": 1, "amount": 100})


@pytest.mark.contract("SCH-012")
def test_transfer_to_other_account_is_fine():
    """SCH-012: a transfer to a different account validates."""
    assert not errs(schemas.EntryIn, **{**ENTRY, "to_account_id": 2, "amount": 100})


@pytest.mark.contract("SCH-013")
@pytest.mark.parametrize("amount", [-500, -1])
def test_transfer_amount_must_be_positive(amount):
    """SCH-013: a transfer with amount <= 0 -> transfer_amount_not_positive."""
    assert "transfer_amount_not_positive" in codes(schemas.EntryIn, **{**ENTRY, "to_account_id": 2, "amount": amount})


@pytest.mark.contract("SCH-014")
@pytest.mark.parametrize("extra", [{}, {"kind": "once"}])
def test_zero_amount_is_rejected(extra):
    """SCH-014: amount 0 -> amount_zero (recurring and once)."""
    assert "amount_zero" in codes(schemas.EntryIn, **{**ENTRY, "amount": 0, **extra})


@pytest.mark.contract("SCH-013", "SCH-014")
def test_zero_amount_transfer_is_rejected_with_one_of_the_two_codes():
    """SCH-013/014: a transfer of 0 violates both rules; the contract does not say which code wins (F-21)."""
    assert codes(schemas.EntryIn, **{**ENTRY, "amount": 0, "to_account_id": 2}) & {"amount_zero", "transfer_amount_not_positive"}


@pytest.mark.contract("SCH-014")
def test_amount_zero_example_has_no_field_params():
    """SCH-014/ERRENV-005: the cross-field error carries the short code and empty params."""
    try:
        schemas.EntryIn(**{**ENTRY, "amount": 0})
    except ValidationError as ex:
        found = [e for e in errors.validation_detail(ex)["params"]["errors"] if e["code"] == "amount_zero"]
        assert found and found[0]["params"] == {}


@pytest.mark.contract("SCH-015")
def test_set_adjustment_requires_amount():
    """SCH-015: mode=set without amount -> amount_required."""
    assert "amount_required" in codes(schemas.AdjustmentIn, **{**ADJ, "amount": None})


@pytest.mark.contract("SCH-015")
def test_set_adjustment_clears_percent_fields():
    """SCH-015: for mode=set, percent and repeat_yearly are forced to None/False."""
    m = schemas.AdjustmentIn(**{**ADJ, "mode": "set", "amount": 77, "percent": 5.0, "repeat_yearly": True})
    assert m.amount == 77 and m.percent is None and not m.repeat_yearly


@pytest.mark.contract("SCH-016")
def test_percent_adjustment_requires_percent():
    """SCH-016: mode=percent without percent -> percent_required."""
    assert "percent_required" in codes(schemas.AdjustmentIn, **{**ADJ, "mode": "percent", "amount": None, "percent": None})


@pytest.mark.contract("SCH-016")
def test_percent_adjustment_clears_amount():
    """SCH-016: for mode=percent, amount is forced to None and repeat_yearly is kept."""
    m = schemas.AdjustmentIn(**{**ADJ, "mode": "percent", "amount": 999, "percent": 3.5, "repeat_yearly": True})
    assert m.amount is None and m.percent == 3.5 and m.repeat_yearly is True


@pytest.mark.contract("SCH-017")
def test_expected_updated_at_is_optional_free_form():
    """SCH-017: expected_updated_at is an optional arbitrary string."""
    assert schemas.CheckpointIn(**CP).expected_updated_at is None
    assert schemas.CheckpointIn(**CP, expected_updated_at="whatever 123").expected_updated_at == "whatever 123"


@pytest.mark.contract("SCH-018")
def test_comment_is_optional_and_defaults_to_empty():
    """SCH-018: comment defaults to '' and may be supplied."""
    assert schemas.CheckpointIn(**CP).comment == ""
    assert schemas.CheckpointIn(**CP, comment="why").comment == "why"


@pytest.mark.contract("SCH-001", "SCH-008", "SCH-009")
def test_account_create_requires_start_fields():
    """SCH-008/009 (AccountCreate): start_balance and start_date are required."""
    c = errs(schemas.AccountCreate, **ACC)
    assert ("start_balance", "missing") in c and ("start_date", "missing") in c
