# forecast — the forecast engine
ID prefix: FC
Layer: backend

## Purpose
A pure function that turns the raw table rows into the per-month, per-account numbers the
UI shows: opening balance → every individual booking (each with a human-traceable
derivation of its amount) → closing balance, anchored to the actual-balance checkpoints.
Showing *how* each amount is derived is a core feature, so the explanation steps are part
of the contract.

## Interface
Import: `from app import forecast`. Pure functions, no I/O.

- `forecast.compute(state: dict, start: str, months: int) -> dict` — the engine.
  - `state`: `{'accounts': [...], 'entries': [...], 'adjustments': [...],
    'checkpoints': [...]}` — raw rows (dicts) as stored, including `archived` (0/1 or bool).
  - `start`: `'YYYY-MM'` (first forecast month).
  - `months`: number of months (≥1).
  - Returns `{start, months: [...], accounts: [...], warnings: [...]}` (shape below).
- `forecast.amount_at(entry: dict, adjs: list[dict], d: date) -> (int, list[dict])` —
  the amount of one entry on date `d`, plus its ordered explanation steps.
- `forecast.occurrences(entry: dict, until: date)` — generator of the dates an entry falls
  due up to `until`.
- `forecast.add_months(y, m, n) -> (year, month)` — calendar month arithmetic.
- `forecast.full_years(a: date, b: date) -> int` — whole years from `a` to `b`.

**`compute` return shape:**
```
{
  "start": "YYYY-MM",
  "months": [ {
      "month": "YYYY-MM",
      "opening": <int cents, sum over accounts>,
      "closing": <int cents, sum over accounts>,
      "income":  <int cents, sum of positive bookings this month>,
      "expense": <int cents, sum of negative bookings this month>,
      "accounts": { "<account_id>": {
          "opening": <int|null>, "closing": <int|null>,
          "items": [ <item>, ... ]
      } }
  }, ... ],
  "accounts": [ {"id", "name", "kind"}, ... ],   // non-archived only
  "warnings": [ {"code", ...params}, ... ]
}
```
**Item shapes (inside `accounts.<id>.items`):**
- booking: `{type:'booking', entry_id, date, category, estimated, label, amount, balance, explanation}`
- transfer: `{type:'transfer', entry_id, date, category, estimated, label, amount, balance, explanation}`
- checkpoint: `{type:'checkpoint', checkpoint_id, date, balance, note[, expected, deviation]}`

**Explanation step shapes (list on each booking/transfer item):**
- `{code:'base_amount', amount}`
- `{code:'set_amount', date, amount, note}`
- `{code:'percent_change', date, percent, repeat_yearly, years, amount, note}`

**Warning shapes:**
- `{code:'transfer_target_archived', entry_id, account_id}`
- `{code:'no_checkpoint', account_id}`

## Dependencies & side effects
None. Pure computation over the passed `state`. Does not read the DB or the clock
(the caller supplies `start`).

## Behavior clauses

### Month grid & totals
- `FC-001` [INFERRED] `months` output has exactly `months` entries, consecutive calendar
  months starting at `start`, each labeled `"YYYY-MM"`.
- `FC-002` [INFERRED] Each month's `closing` for the whole portfolio equals the sum of its
  accounts' `closing` values (null account closings count as 0).
- `FC-003` [TEST] A booking dated on a month's last day is included in that month; a
  recurring entry whose day exceeds the month length clamps to the last day (e.g. a
  monthly entry started on the 31st falls on Feb 28 in a non-leap February).
  [TEST: `test_full_flow` asserts the Feb salary item is dated `2026-02-28`]
- `FC-004` [INFERRED] `income` sums the amounts of this month's **booking** items with
  `amount > 0`; `expense` sums those with `amount < 0`. Transfers are excluded from both.
- `FC-005` [README] Transfers are not counted in monthly income/expense totals.

### Checkpoints as anchors
- `FC-006` [README] An account's **first** checkpoint is its starting point; bookings
  dated on or before that day are treated as already included and do not move the balance.
  [TEST: `test_full_flow` — Jan rent on Jan 1 is ignored because start is Jan 15]
- `FC-007` [README] On the same calendar day, bookings are applied **before** checkpoints.
- `FC-008` [README] A later checkpoint resets the running balance to its `balance` and
  reports `expected` (the forecast value just before it) and `deviation`
  (`balance - expected`). [TEST: `test_full_flow`]
- `FC-009` [INFERRED] The **first** checkpoint item for an account has no `expected`/
  `deviation` keys (nothing precedes it); later checkpoints have both.
- `FC-010` [INFERRED] After a checkpoint, subsequent bookings continue from the
  checkpoint's `balance`.
- `FC-011` [README] An account with **no** (non-archived) checkpoint produces a
  `no_checkpoint` warning and its per-account `opening`/`closing` stay `null` with no
  booking items applied (bookings before the first checkpoint are skipped, and there is no
  checkpoint to start from). Intended: without an anchor there is no honest starting
  balance, so there is no zero-based fallback (OPEN_QUESTIONS #6, B-019).
- `FC-012` [INFERRED] Checkpoints dated after the forecast horizon are ignored; checkpoints
  at or before the horizon are considered.

### Entry occurrences
- `FC-013` [INFERRED] A `recurring` entry recurs every `interval_months` from `start_date`;
  a `once` entry occurs exactly once on `start_date`.
- `FC-014` [INFERRED] An entry with an `end_date` produces no occurrence after `end_date`.
- `FC-015` [INFERRED] `occurrences` yields dates in ascending order up to and including the
  `until` bound, clamping each to the last valid day of its month (see `FC-003`).
- `FC-016` [INFERRED] An entry whose first occurrence is after the horizon contributes no
  items.

### Amounts, adjustments & explanations
- `FC-017` [INFERRED] With no adjustments, an entry's amount on any date equals its stored
  `amount`, and its explanation is exactly `[{code:'base_amount', amount}]`.
- `FC-018` [README] Adjustments apply from their `effective_date`, in `(effective_date, id)`
  order; an adjustment with `effective_date` after the occurrence date is not applied.
- `FC-019` [README] A `set` adjustment replaces the amount outright (and supersedes earlier
  adjustments); its explanation step is `{code:'set_amount', date, amount, note}`.
- `FC-020` [README] A `percent` adjustment multiplies the current amount by
  `(1 + percent/100)`, rounded half-up to whole cents. Its step is
  `{code:'percent_change', date, percent, repeat_yearly, years, amount, note}`.
- `FC-021` [README][TEST] A `percent` adjustment with `repeat_yearly` true is applied
  `full_years(effective_date, date) + 1` times (compounding each year). [TEST:
  `test_percent_yearly`: base −100000, +2%/yr yearly → −102000 on 2026-06-01 (1×),
  −106121 on 2028-01-01 (3×)]
- `FC-022` [INFERRED] A `percent` adjustment without `repeat_yearly` is applied once
  (`years = 1`).
- `FC-023` [INFERRED] Rounding is half-up at each application step for `percent`
  (not once at the end), matching `test_percent_yearly`'s `-106121`.
- `FC-024` [INFERRED] The explanation list order reflects application order: `base_amount`
  first, then each applied adjustment step in `(effective_date, id)` order.
- `FC-025` [INFERRED] `full_years(a, b)` counts whole elapsed years from `a` to `b`
  (decremented when `b`'s month/day is before `a`'s); `full_years` of same-day is 0.

### Transfers
- `FC-026` [README][TEST] A transfer (`to_account_id` set) stored as a positive amount
  produces a `-amount` item on the source account and a `+amount` item on the target
  account on the same date. [TEST: `test_full_flow` — savings transfer lands +50000 on the
  target]
- `FC-027` [INFERRED] The source transfer item's `label` names the target
  (`"<entry name> → <target name>"`); the target item's `label` names the source
  (`"<entry name> ← <source name>"`).
- `FC-028` [README] If a transfer's `to_account_id` points to an archived account, the
  (active) source account still gets its −amount transfer item every time it falls due
  (label `'<name> → <target>'`, with the usual explanation), because the money still leaves;
  only the target side is dropped. A `{code:'transfer_target_archived', entry_id,
  account_id}` warning is emitted once per entry (B-018, OPEN_QUESTIONS #7). If the source
  account itself is archived, the whole entry is ignored (`FC-029`).

### Archiving & scope
- `FC-029` [INFERRED] Archived accounts, entries, adjustments and checkpoints are excluded
  from the forecast.
- `FC-030` [INFERRED] The top-level `accounts` list in the result contains only
  non-archived accounts, each as `{id, name, kind}`.

### Item invariants
- `FC-031` [INFERRED] Every booking/transfer item carries its `entry_id`, ISO `date`,
  `category`, `estimated`, a `label`, the signed `amount`, the running `balance` after it, and a
  non-empty `explanation` list.
- `FC-032` [INFERRED] Within an account, items are ordered by `(date, kind-order, id)` with
  bookings before checkpoints on the same day (per `FC-007`), and each item's `balance`
  reflects all prior items plus any checkpoint resets.
- `FC-033` [README] Every booking/transfer item carries `estimated: bool`, copied from its
  entry (missing or `0` → `false`). The mark is informational only (B-015): amounts,
  balances, explanations and the monthly `income`/`expense` are the same as for a fixed
  entry.

## Examples
- `amount_at({'amount':-100000,'start_date':'2026-01-01'}, [{'effective_date':'2026-01-01',
  'mode':'percent','percent':2.0,'repeat_yearly':1,'note':''}], date(2028,1,1))` →
  `(-106121, [...])`. [TEST]
- `test_full_flow`: Jan closing for the checking account = 400000 (start 100000 on Jan 15,
  Jan-1 rent ignored, salary +300000 on Jan 31).

## Out of scope / not specified
- The German rendering of any `code` (that lives in the frontend, see `FE-CORE`).
- Behavior for a malformed `start` such as month `00`/`13`: the API rejects it
  (`API-FC-007`), so the engine assumes a valid month.
- Ordering of `warnings` relative to each other.

## Open questions
- None open. (#6 was settled, see `FC-011`; #7 see `FC-028`.)

