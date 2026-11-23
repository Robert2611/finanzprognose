# db — generic CRUD
ID prefix: DB-CRUD
Layer: backend

## Purpose
The single write path for the four data tables. Every create/update/archive/restore goes
through here, and each one writes a matching `audit_log` row **in the same transaction**,
so the change log can never drift from the data. Enforces optimistic locking on updates.

## Interface
Import: `from app import db`. All functions take an open connection `conn` (normally from
`db.tx()`), and `table` must be a key of `db.TABLES`.

- `db.get(conn, table, id_) -> dict | None` — one row as a dict, or `None` if absent.
- `db.all_rows(conn, table) -> list[dict]` — all rows ordered by `id` ascending.
- `db.create(conn, table, data: dict, comment: str = '') -> dict` — insert a row
  (only whitelisted columns from `data` are used; `created_at`/`updated_at` set to `now()`),
  write a `create` audit row, return the new row.
- `db.update(conn, table, id_, data: dict, expected_updated_at=None, comment='') -> dict`
  — update whitelisted columns, optimistic-lock on `expected_updated_at`, write an
  `update` audit row, return the updated row.
- `db.set_archived(conn, table, id_, archived: bool, comment='', expected_updated_at=None) -> dict`
  — set `archived` to 1/0, optimistic-lock on `expected_updated_at` like `update`, write an
  `archive`/`restore` audit row, return the row.

## Dependencies & side effects
Reads/writes the data tables and `audit_log` (via `DB-AUDIT`'s write path) in one
transaction. Uses `db.now()` for timestamps. Raises `db.NotFound`/`db.Conflict`
(`DB-ERR`).

## Behavior clauses

- `DB-CRUD-001` [INFERRED] `get` returns the full row as a dict including system columns
  (`id`, `archived`, `created_at`, `updated_at`); returns `None` for an unknown id.
- `DB-CRUD-002` [INFERRED] `all_rows` returns every row (archived included) ordered by
  ascending `id`.
- `DB-CRUD-003` [INFERRED] `create` sets `created_at == updated_at == now()` and
  `archived = 0` (schema default) for the new row, and returns the row with its new `id`.
- `DB-CRUD-004` [INFERRED] `create` ignores keys in `data` that are not whitelisted for
  the table (only `TABLES[table]` columns are written); missing whitelisted keys are
  inserted as `NULL`/column default.
- `DB-CRUD-005` [README] `create` writes an `audit_log` row with `action='create'`,
  `entity=table`, `entity_id=<new id>`, `before=NULL`, `after=<new row JSON>`, in the same
  transaction. [TEST: `test_optimistic_locking_and_audit`, `test_full_flow`]
- `DB-CRUD-006` [INFERRED] `update` changes only whitelisted columns present in `data`,
  sets `updated_at=now()`, and returns the updated row.
- `DB-CRUD-007` [README] When `expected_updated_at` is provided and does **not** equal the
  row's current `updated_at`, `update` raises `db.Conflict('conflict')` and makes no change.
  [TEST: `test_optimistic_locking_and_audit`]
- `DB-CRUD-008` [INFERRED] When `expected_updated_at` is provided and **matches**, the
  update proceeds. When `expected_updated_at` is `None`/falsy, the optimistic-lock check is
  skipped and the update always proceeds.
- `DB-CRUD-009` [INFERRED] `update`/`set_archived` on a non-existent `id_` raises
  `db.NotFound('not_found', entity=table, id=id_)`.
- `DB-CRUD-010` [OBSERVED] A no-op update (all submitted values already equal the stored
  values) returns the existing row unchanged, does **not** bump `updated_at`, and writes
  **no** audit row. See OPEN_QUESTIONS #2.
- `DB-CRUD-011` [README] `update` writes an `audit_log` row with `action='update'`,
  `before=<prior row JSON>`, `after=<new row JSON>` when any column actually changed.
  [TEST: `test_optimistic_locking_and_audit`]
- `DB-CRUD-012` [INFERRED] `set_archived(conn, table, id_, True, …)` sets `archived=1` and
  writes an audit row with `action='archive'`; `set_archived(…, False, …)` sets
  `archived=0` with `action='restore'`.
- `DB-CRUD-013` [README] `set_archived` is optimistic-locked like `update` (B-017, OPEN_QUESTIONS
  #3): when `expected_updated_at` is given and differs from the row's `updated_at`, it raises
  `db.Conflict('conflict')` and changes nothing (checked before the no-op path of
  `DB-CRUD-014`); `None` or empty skips the check.
- `DB-CRUD-014` [INFERRED] Archiving an already-archived row (or restoring an already-active
  row) is a no-op that writes no audit row (same no-change path as `DB-CRUD-010`).
- `DB-CRUD-015` [INFERRED] The optional `comment` is stored verbatim on the audit row;
  default is the empty string.
- `DB-CRUD-016` [INFERRED] All of `create`/`update`/`set_archived` operate on the passed
  connection and therefore participate in the caller's transaction — the data write and
  its audit row commit or roll back together.

## Examples
- `create(c, 'accounts', {'name':'Giro','kind':'checking','note':''})` → `{id, name:'Giro',
  kind:'checking', note:'', archived:0, created_at, updated_at}` + one audit row.
- `update(c, 'accounts', 5, {'name':'Z'}, expected_updated_at='<stale>')` → raises
  `Conflict`.

## Out of scope / not specified
- Whether `data` values are type-coerced here (callers pass already-validated data from
  `app.schemas`; see `SCH`).
- JSON serialization details of audit snapshots beyond "the row's columns" (see `DB-AUDIT`).

## Open questions
- OPEN_QUESTIONS #2 (no-op update: no audit row, `data_version` unchanged).
- OPEN_QUESTIONS #3 (archive/restore not optimistic-locked).
