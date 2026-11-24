# schemas — request validation models
ID prefix: SCH
Layer: backend

## Purpose
Validates and normalizes every API write body before it reaches the data layer. Besides
per-field type/length limits, it encodes the cross-field business rules (transfers need a
distinct positive target; a `once` entry has no end date or interval; a `set` adjustment
needs an amount, a `percent` one needs a percent). Validation failures are raised as short
machine-readable codes, never German sentences.

## Interface
Import: `from app import schemas`. Pydantic v2 models; `MODELS` maps table → model.

- `schemas.MODELS = {'accounts': AccountIn, 'entries': EntryIn, 'adjustments': AdjustmentIn,
  'checkpoints': CheckpointIn}`.
- `schemas.Base` — common fields on every write: `expected_updated_at: str|None`,
  `comment: str` (max 500).
- `AccountIn(Base)`: `name` (1–100), `kind` ∈ {checking, savings, custody, credit_card,
  cash, other} default `checking`, `reserve: bool` default `False` (B-028), `note` (≤2000).
- `AccountCreate(AccountIn)`: adds `start_balance: int` (cents), `start_date: date`.
- `EntryIn(Base)`: `account_id:int`, `to_account_id:int|None`, `name` (1–100),
  `category` (≤100), `kind` ∈ {recurring, once}, `amount:int`, `start_date:date`,
  `end_date:date|None`, `interval_months:int` (1–120, default 1), `estimated:bool`
  (default false), `note` (≤2000).
- `AdjustmentIn(Base)`: `entry_id:int`, `effective_date:date`, `mode` ∈ {set, percent},
  `amount:int|None`, `percent:float|None` (> −100 and < 1000), `repeat_yearly:bool`
  default false, `note` (≤500).
- `CheckpointIn(Base)`: `account_id:int`, `date:date`, `balance:int`, `note` (≤500).

A validation failure raises `pydantic.ValidationError`; each error exposes a machine code
(either Pydantic's built-in `type` like `string_too_short`, or the custom codes below).

## Dependencies & side effects
None (pure validation). Consumed by the API routes (`API-ACC`, `API-RES`) and translated
to the HTTP envelope by `ERRENV`.

## Behavior clauses

### Field-level
- `SCH-001` [INFERRED] `name` on accounts and entries must be 1–100 chars; empty → code
  `string_too_short`; >100 → `string_too_long`.
- `SCH-002` [INFERRED] `account.kind` must be one of the six allowed values; anything else
  → a literal/enum validation error. Omitting it defaults to `checking`.
- `SCH-003` [INFERRED] `entry.kind` must be `recurring` or `once`; required (no default).
- `SCH-004` [INFERRED] `adjustment.mode` must be `set` or `percent`; required.
- `SCH-005` [INFERRED] `interval_months` must be an int in 1–120; `<1` → `greater_than_equal`,
  `>120` → `less_than_equal`.
- `SCH-006` [INFERRED] `percent` (when supplied) must satisfy `> -100` and `< 1000`;
  `-100` or below → `greater_than`, `1000` or above → `less_than`.
- `SCH-007` [INFERRED] `note` length limits: 2000 for accounts/entries, 500 for
  adjustments/checkpoints; `comment` ≤ 500. Over-length → `string_too_long`.
- `SCH-008` [INFERRED] `amount`/`balance`/`start_balance` are integers (cents); a
  non-integer/garbage value → an int parsing/type error.
- `SCH-009` [INFERRED] Date fields parse ISO `YYYY-MM-DD`; a non-date → a date parsing error.

### Cross-field (custom codes)
- `SCH-010` [INFERRED] `EntryIn`: `end_date < start_date` → `ValueError('end_before_start')`.
- `SCH-011` [INFERRED] `EntryIn`: when `kind == 'once'`, `end_date` is forced to `None` and
  `interval_months` to `1` (normalization, not an error).
- `SCH-012` [INFERRED] `EntryIn`: when `to_account_id == account_id` →
  `ValueError('transfer_same_account')`.
- `SCH-013` [INFERRED] `EntryIn`: when `to_account_id` is set and `amount <= 0` →
  `ValueError('transfer_amount_not_positive')`.
- `SCH-014` [INFERRED] `EntryIn`: `amount == 0` → `ValueError('amount_zero')` (applies to
  non-transfers too).
- `SCH-015` [INFERRED] `AdjustmentIn`: `mode == 'set'` with `amount is None` →
  `ValueError('amount_required')`; otherwise `percent`/`repeat_yearly` are forced to
  `None`/`False`.
- `SCH-016` [INFERRED] `AdjustmentIn`: `mode == 'percent'` with `percent is None` →
  `ValueError('percent_required')`; otherwise `amount` is forced to `None`.
- `SCH-017` [INFERRED] `Base.expected_updated_at` is optional and free-form string; it is
  not written to the record (it drives optimistic locking only).
- `SCH-018` [INFERRED] `comment` is optional (default empty) and is not written to the
  data row (it goes onto the audit entry).
- `SCH-019` [README] `EntryIn.estimated` is a boolean, default `False` (a fixed amount);
  `True` marks the amount as an estimate (B-015). A value that is not a boolean (e.g.
  `"vielleicht"`) fails with `bool_parsing`.
- `SCH-020` [README] `AccountIn.reserve` (and so `AccountCreate.reserve`) is a boolean,
  default `False` (available money); `True` marks the account as a reserve that is not money
  to plan with (B-028). A value that is not a boolean fails with `bool_parsing`.

## Examples
- `EntryIn(account_id=1, name='x', kind='once', amount=-500, start_date='2026-01-01',
  end_date='2026-02-01', interval_months=6)` → validates; `end_date` normalized to `None`,
  `interval_months` to `1`.
- `EntryIn(... amount=0 ...)` → `ValidationError` carrying code `amount_zero`.
- `AdjustmentIn(entry_id=1, effective_date='2026-01-01', mode='set')` → code
  `amount_required`.

## Out of scope / not specified
- The HTTP status and German text for each code (see `ERRENV` and `FE-CORE`).
- Whether a referenced `account_id`/`entry_id` exists — that is checked later in the API
  route (`API-RES`), not by these models.

## Open questions
None.
