# API — health & state
ID prefix: API-STATE
Layer: api

## Purpose
`/healthz` is the always-open liveness probe used by the Docker healthcheck. `/api/state`
is the single read the SPA uses to hydrate itself: the full current dataset in a stable,
presentation-neutral shape that does **not** track internal schema churn.

## Interface
- `GET /healthz` → `200 {"ok": true}`. No auth required.
- `GET /api/state` → `200` with:
  ```
  {
    "accounts":    [AccountOut],
    "entries":     [EntryOut],
    "adjustments": [AdjustmentOut],
    "checkpoints": [CheckpointOut],
    "data_version": <int>
  }
  ```
  **AccountOut:** `{id, name, kind, note, archived: bool, updated_at}`
  **EntryOut:** `{id, account_id, to_account_id|null, name, category, kind, amount,
  start_date, end_date|null, interval_months, estimated: bool, note, archived: bool, updated_at}`
  **AdjustmentOut:** `{id, entry_id, effective_date, mode, amount|null, percent|null,
  repeat_yearly: bool, note, archived: bool, updated_at}`
  **CheckpointOut:** `{id, account_id, date, balance, note, archived: bool, updated_at}`

## Dependencies & side effects
Read-only. Reads all four data tables and the audit max-id (`data_version`).

## Behavior clauses

- `API-STATE-001` [INFERRED] `GET /healthz` returns `200 {"ok": true}` and never requires
  authentication.
- `API-STATE-002` [TEST] `GET /api/state` returns the four table arrays plus a
  `data_version` integer. [TEST: `test_state_contract`]
- `API-STATE-003` [TEST] Each account object has **exactly** the keys
  `{id, name, kind, note, archived, updated_at}` — no `created_at`, no other internal
  columns. [TEST: `test_state_contract`]
- `API-STATE-004` [TEST] `archived` is a JSON boolean (`true`/`false`), not the stored
  `0`/`1`. [TEST: `test_state_contract`]
- `API-STATE-005` [TEST] A column added directly to a table (bypassing the response model,
  e.g. a future migration or an `ALTER TABLE`) does **not** appear in `/api/state` — the
  wire shape is decoupled from the table shape. [TEST: `test_state_contract`]
- `API-STATE-006` [INFERRED] `amount`/`balance` are integer cents; `percent` is a number or
  `null`; money is never divided or formatted server-side.
- `API-STATE-007` [INFERRED] Rows are returned ordered by ascending `id` within each array
  (archived rows included).
- `API-STATE-008` [INFERRED] `data_version` equals the backend change counter
  (`MAX(audit_log.id)`), increasing as data changes.
- `API-STATE-009` [INFERRED] On an empty database, all four arrays are empty and
  `data_version` is `0`.
- `API-STATE-010` [README] `EntryOut.estimated` is a real boolean (not the stored `0/1`):
  `false` for a fixed amount, `true` for an estimate (B-015).

## Examples
- Fresh DB → `{"accounts":[],"entries":[],"adjustments":[],"checkpoints":[],"data_version":0}`.
- After creating one account → `accounts` has one `AccountOut`, `data_version` ≥ 1.

## Out of scope / not specified
- The relative ordering guarantee beyond ascending id.
- Any pagination of `/api/state` (there is none; it returns everything).

## Open questions
None.
