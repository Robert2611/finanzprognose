# API — forecast
ID prefix: API-FC
Layer: api

## Purpose
Runs the forecast engine over the current data for a chosen start month and horizon, and
returns the per-month, per-account projection the UI renders. This is the HTTP wrapper
around `forecast.compute` (see `FC` for the full computation contract).

## Interface
- `GET /api/forecast?start=YYYY-MM&months=N` → `200` with the `compute` result
  (see `backend/forecast.md` for the full shape: `{start, months[], accounts[], warnings[]}`).
  - `start` optional, must match `^\d{4}-\d{2}$`; defaults to the current month
    (`date.today()` in `YYYY-MM`).
  - `months` optional int, `1 ≤ months ≤ 240`, default `24`.
  - `include` optional, repeatable int (`&include=3&include=7`): the optional entries to count
    in the main numbers (B-029, `FC-036`).

## Dependencies & side effects
Read-only. Loads all four tables and runs `forecast.compute`. No clock dependency when
`start` is supplied.

## Behavior clauses

- `API-FC-001` [TEST] `GET /api/forecast?start=2026-01&months=4` returns a `months` array of
  length 4, keyed month labels `2026-01`..`2026-04`, with per-account `closing` values.
  [TEST: `test_full_flow`]
- `API-FC-002` [INFERRED] Omitting `start` defaults to the current calendar month;
  omitting `months` defaults to 24.
- `API-FC-003` [INFERRED] `start` not matching `^\d{4}-(0[1-9]|1[0-2])$` (e.g. `2026-1`,
  `2026-13x`, `abc`) returns `422` (query pattern violation, envelope per `ERRENV-010`).
- `API-FC-004` [INFERRED] `months < 1` or `months > 240` returns `422` (query range
  violation).
- `API-FC-005` [TEST] The result's forecast numbers match the engine contract `FC-*`
  (checkpoints, adjustments, transfers, clamping). [TEST: `test_full_flow`]
- `API-FC-006` [INFERRED] `warnings` is present (possibly empty) and uses language-neutral
  codes (`no_checkpoint`, `transfer_target_archived`) with id params — no German text.
- `API-FC-007` [README] An out-of-range month in `start` (e.g. `2026-00`, `2026-13`) is
  rejected with `422 {code:'validation_error'}` whose error has `field:'start'` and
  `code:'string_pattern_mismatch'`; it is never wrapped into another month (B-017,
  OPEN_QUESTIONS #8).
- `API-FC-008` [INFERRED] With no accounts, the result has an empty `accounts` list, empty
  `warnings`, and `months` whose portfolio `opening`/`closing` are 0.
- `API-FC-009` [README] Optional entries are left out of the result unless their id is given
  as an `include` parameter (repeatable); `with_optional` then compares (`FC-036/037`). A
  non-integer `include` is a `422 validation_error`.

## Examples
- `GET /api/forecast?start=2026-02&months=1` after adding a checkpoint on 2026-02-20 →
  the single month's checkpoint item has `expected` and `deviation`. [TEST: `test_full_flow`]

## Out of scope / not specified
- The German rendering of warnings/explanations (frontend, `FE-CORE`/`FE-FORECAST`).
- Performance characteristics for very large horizons.

## Open questions
- None open. (#8 was settled, see `API-FC-007`.)
