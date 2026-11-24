# API — create account
ID prefix: API-ACC
Layer: api

## Purpose
Creating an account is special: an account is only meaningful once it has a starting
balance, so this endpoint creates the account **and** its first checkpoint (the starting
balance at a date) in one atomic transaction. The starting checkpoint is what the forecast
anchors to.

## Interface
- `POST /api/accounts` — body (JSON):
  ```
  {
    "name": str (1–100, required),
    "kind": "checking"|"savings"|"custody"|"credit_card"|"cash"|"other" (default "checking"),
    "note": str (≤2000, default ""),
    "start_balance": int cents (required),
    "start_date": "YYYY-MM-DD" (required),
    "comment": str (≤500, optional)
  }
  ```
  → `200` with the created **account** row:
  `{id, name, kind, note, archived, created_at, updated_at}` (raw create-path row, not the
  `AccountOut` projection).

(Note: `POST /api/{table}` with `table == "accounts"` is routed to this same handler; see
`API-RES`.)

## Dependencies & side effects
Writes an `accounts` row and a `checkpoints` row (the starting balance), each with its own
`create` audit entry, all in one transaction. Advances `data_version` by 2.

## Behavior clauses

- `API-ACC-001` [TEST] A valid `POST /api/accounts` returns `200` and the new account row
  including its `id` and `updated_at`. [TEST: `test_full_flow`, `test_state_contract`]
- `API-ACC-002` [INFERRED] The same call also creates exactly one checkpoint for the new
  account with `date == start_date` and `balance == start_balance`.
- `API-ACC-003` [README][OBSERVED] The starting checkpoint is created with an **empty**
  `note` (no stored German "Startstand" text); the "Startstand" label is derived by the
  frontend, not stored. [B-005 phase 4]
- `API-ACC-004` [INFERRED] Account and starting checkpoint are created atomically: if either
  insert fails, neither persists.
- `API-ACC-005` [INFERRED] `kind` defaults to `checking` when omitted; an invalid `kind`
  yields `422 validation_error` (code for the kind field) and nothing is created.
- `API-ACC-006` [INFERRED] Missing `name`, `start_balance`, or `start_date` yields
  `422 validation_error`; an empty `name` yields `string_too_short`.
- `API-ACC-007` [INFERRED] `start_balance` may be any integer, including `0` and negatives
  (e.g. a credit card). [TEST: `test_full_flow` creates a savings account with
  `start_balance: 0`]
- `API-ACC-008` [INFERRED] After creation, `GET /api/state` shows the account (as
  `AccountOut`) and its starting checkpoint; `data_version` increased by 2 relative to
  before the call.
- `API-ACC-009` [INFERRED] An optional `comment` is recorded on the account's `create`
  audit entry (not on the checkpoint, and not on the data row).
- `API-ACC-010` [README] `POST /api/accounts` and `PUT /api/accounts/{id}` accept `reserve`
  (boolean, B-028). When it is omitted the account is available money (`reserve = 0`); a
  non-boolean is a `422 validation_error` on the `reserve` field; a `PUT` that flips it is a
  normal update with one audit row whose `before`/`after` differ in `reserve`.

## Examples
- `POST /api/accounts {"name":"Checking","kind":"checking","start_balance":100000,
  "start_date":"2026-01-15"}` → `200`, account row; one checkpoint
  `{date:"2026-01-15", balance:100000, note:""}`.

## Out of scope / not specified
- Whether the account-create response is the `AccountOut` projection or the raw row — it is
  the **raw create row** (it includes `created_at`), unlike `/api/state`. Tests should rely
  only on `id`, `name`, `kind`, `note`, `archived`, `updated_at` being present.

## Open questions
None.
