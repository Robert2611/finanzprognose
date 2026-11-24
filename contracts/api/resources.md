# API — generic resource CRUD (entries, adjustments, checkpoints, account updates)
ID prefix: API-RES
Layer: api

## Purpose
One generic set of routes drives create/update/archive/restore for all data tables, so
every resource behaves consistently: validate the body, check referenced ids exist, write
through the audited data layer, and enforce optimistic locking on updates. Nothing is ever
deleted — archive/restore flips a flag.

## Interface
`{table}` ∈ `accounts` | `entries` | `adjustments` | `checkpoints`.

- `POST /api/{table}` — create. Body = the table's write model (see `SCH`). Returns `200`
  with the created row. (`table == accounts` is delegated to `POST /api/accounts`,
  `API-ACC`.)
- `PUT /api/{table}/{id}` — update. Body = the write model plus optional
  `expected_updated_at` and `comment`. Returns `200` with the updated row.
- `POST /api/{table}/{id}/archive` — body `{comment?: str}` (≤500). Returns `200` with the
  archived row.
- `POST /api/{table}/{id}/restore` — body `{comment?: str}`. Returns `200` with the
  restored row.

**Error envelope** (from `ERRENV`): `{"code","params"}`. Statuses:
- `404 unknown_table` — `{table}` not a known table (POST/PUT path).
- `422 validation_error` — body fails `SCH` validation.
- `422 ref_not_found` — a referenced id (`account_id`, `to_account_id`, `entry_id`) does
  not exist.
- `404 not_found` — updating/archiving a missing `{id}`.
- `409 conflict` — `expected_updated_at` mismatch on update.

## Dependencies & side effects
Validates via `SCH`; checks references via `db.get`; writes via `DB-CRUD` (data row +
audit row in one transaction). `comment`/`expected_updated_at` are not written to the data
row.

## Behavior clauses

### Create
- `API-RES-001` [TEST] `POST /api/entries` with a valid body returns `200` and the created
  entry (with `id`, `updated_at`). [TEST: `test_full_flow`]
- `API-RES-002` [INFERRED] `POST /api/{table}` for a table not in the whitelist returns
  `404` with `{"code":"unknown_table","params":{"table": <name>}}`.
- `API-RES-003` [INFERRED] A body failing validation returns `422`
  `{"code":"validation_error",...}` and creates nothing (e.g. entry `amount=0`,
  transfer with `to_account_id==account_id`, adjustment `set` without `amount`).
- `API-RES-004` [INFERRED] When `account_id`, `to_account_id`, or `entry_id` references a
  non-existent row, the response is `422`
  `{"code":"ref_not_found","params":{"field":...,"id":...}}` and nothing is created.
- `API-RES-005` [INFERRED] A successful create writes exactly one `create` audit row and
  advances `data_version` by 1.
- `API-RES-006` [INFERRED] Transfer entries are stored with the positive `amount` as given;
  the sign handling for the two sides happens only in the forecast (see `FC-026`).

### Update
- `API-RES-007` [TEST] `PUT /api/{table}/{id}` with a matching `expected_updated_at` applies
  the change and returns `200` with the updated row. [TEST:
  `test_optimistic_locking_and_audit`]
- `API-RES-008` [TEST] `PUT` with a stale `expected_updated_at` returns `409`
  `{"code":"conflict"}` and changes nothing. [TEST: `test_optimistic_locking_and_audit`]
- `API-RES-009` [INFERRED] `PUT` on a non-existent `{id}` returns `404`
  `{"code":"not_found","params":{"entity":table,"id":id}}`.
- `API-RES-010` [INFERRED] `PUT` validates the body with the same rules as create
  (`422 validation_error` on failure) and checks references (`422 ref_not_found`).
- `API-RES-011` [INFERRED] A successful update writes one `update` audit row capturing
  `before`/`after`; a no-op update (nothing changed) returns the row but writes no audit
  row (see `DB-CRUD-010`).
- `API-RES-012` [INFERRED] `PUT` without `expected_updated_at` skips the optimistic-lock
  check and applies the change (last-writer-wins).

### Archive / restore
- `API-RES-013` [INFERRED] `POST /api/{table}/{id}/archive` sets `archived=true`, returns
  the row, and writes an `archive` audit row.
- `API-RES-014` [INFERRED] `POST /api/{table}/{id}/restore` sets `archived=false` and writes
  a `restore` audit row.
- `API-RES-015` [INFERRED] archive/restore for a table not in the whitelist returns `404`
  `{code:'unknown_table', params:{table}}`, the same envelope as create/update (B-017,
  OPEN_QUESTIONS #9).
- `API-RES-016` [OBSERVED] archive/restore on a non-existent `{id}` surfaces a `not_found`
  from the data layer (`404` with `{code:'not_found'}`).
- `API-RES-017` [INFERRED] The optional `comment` on archive/restore (≤500 chars; truncated
  if longer) is stored on the audit row.
- `API-RES-018` [README] archive/restore accept an optional `expected_updated_at` in the body
  (B-017, OPEN_QUESTIONS #3). If it doesn't match the row's `updated_at` the response is
  `409 {code:'conflict'}` and nothing changes (no audit row); if it is omitted the call is not
  locked. The frontend always sends it.
- `API-RES-019` [README] Nothing is deleted anywhere in this API; archive is the only
  removal, and it is always reversible via restore. [TEST: `test_nothing_can_be_deleted`
  at the DB level]
- `API-RES-020` [README] Archiving an account that is still referenced by active
  entries/checkpoints is permitted, with no cascade and no referential check (B-018,
  OPEN_QUESTIONS #10): the referencing rows stay active, and the forecast handles them per
  `FC-028`/`FC-029`. The frontend warns before archiving (`FE-ACCOUNTS-013`).
- `API-RES-021` [README] `POST`/`PUT /api/entries` accept `estimated` (boolean, B-015). When
  it is omitted the entry is fixed (`estimated = 0`); a `PUT` that flips it is a normal
  update with one audit row whose `before`/`after` differ in `estimated`.
- `API-RES-022` [README] `POST`/`PUT /api/entries` accept `optional` (boolean, B-029). When
  it is omitted the entry is planned (`optional = 0`); a non-boolean is a `422
  validation_error` on the `optional` field; a `PUT` that flips it is a normal update with
  one audit row whose `before`/`after` differ in `optional`.

## Examples
- `POST /api/entries {account_id:<giro>, name:'Rent', kind:'recurring', amount:-120000,
  start_date:'2026-01-01', interval_months:1}` → `200` entry row. [TEST]
- `PUT /api/accounts/5 {name:'Z', kind:'checking', expected_updated_at:'<stale>'}` → `409`.
  [TEST]
- `POST /api/entries {account_id: 999999, ...}` → `422 ref_not_found` (field `account_id`).

## Out of scope / not specified
- The exact body returned by create/update (raw data-layer row incl. `created_at`), beyond
  the fields tests rely on (`id`, writable columns, `archived`, `updated_at`).
- Behavior of archive on `audit_log` (not a data table; not archivable).

## Open questions
- None open. (#3, #9 and #10 were settled, see `API-RES-018`, `API-RES-015` and `API-RES-020`.)
