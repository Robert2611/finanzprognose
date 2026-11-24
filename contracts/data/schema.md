# schema — SQLite schema
ID prefix: DATA
Layer: data

## Purpose
Specifies the persistent shape of the database: tables, columns, types, constraints,
foreign keys, triggers (DELETE block, append-only audit log), the index and `user_version`.
Source of truth in code: `SCHEMA` and `TABLES` in `app/db/schema.py`. The data-safety
promises in the README ("nothing is ever deleted", "append-only audit log", "whole cents",
"WAL + `synchronous=FULL`") live here at the database level, independent of the API.

## Interface
A SQLite file at `Settings.db_path`, created/upgraded by `db.init(path)` (see
`backend/db-schema.md`). Tests inspect it with plain `sqlite3` (`PRAGMA table_info`,
`sqlite_master`, raw `DELETE`/`UPDATE` statements).

### Tables
Common to the four data tables: `id INTEGER PRIMARY KEY`, `archived INTEGER NOT NULL
DEFAULT 0`, `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`, `note TEXT NOT NULL
DEFAULT ''`. Columns the API may write are listed in `db.TABLES`; everything else
(`id`, `archived`, `created_at`, `updated_at`) is set by the data layer.

| Table | Columns (type, constraint) |
|---|---|
| `accounts` | `name TEXT NOT NULL`, `kind TEXT NOT NULL DEFAULT 'checking'`, `reserve INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)` (1 = a reserve, not money to plan with; B-028), `note` |
| `entries` | `account_id INTEGER NOT NULL → accounts(id)`, `to_account_id INTEGER NULL → accounts(id)`, `name TEXT NOT NULL`, `category TEXT NOT NULL DEFAULT ''`, `kind TEXT NOT NULL CHECK IN ('recurring','once')`, `amount INTEGER NOT NULL` (cents, signed; transfers positive), `start_date TEXT NOT NULL`, `end_date TEXT NULL`, `interval_months INTEGER NOT NULL DEFAULT 1 CHECK >= 1`, `estimated INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)` (1 = an estimate, not a fixed debit; B-015), `optional INTEGER NOT NULL DEFAULT 0 CHECK IN (0,1)` (1 = not yet decided, left out of the plan; B-029), `note` |
| `adjustments` | `entry_id INTEGER NOT NULL → entries(id)`, `effective_date TEXT NOT NULL`, `mode TEXT NOT NULL CHECK IN ('set','percent')`, `amount INTEGER NULL` (cents; used when `mode='set'`), `percent REAL NULL` (used when `mode='percent'`), `repeat_yearly INTEGER NOT NULL DEFAULT 0`, `note` |
| `checkpoints` | `account_id INTEGER NOT NULL → accounts(id)`, `date TEXT NOT NULL`, `balance INTEGER NOT NULL` (cents, actual balance at the end of that day), `note` |
| `audit_log` | `id INTEGER PRIMARY KEY`, `ts TEXT NOT NULL`, `action TEXT NOT NULL`, `entity TEXT NOT NULL`, `entity_id INTEGER NOT NULL`, `before TEXT NULL` (JSON), `after TEXT NULL` (JSON), `comment TEXT NOT NULL DEFAULT ''`, `reverts_id INTEGER NULL → audit_log(id)` |

Foreign keys are enforced (`PRAGMA foreign_keys=ON` on every connection).

### Triggers and index
- `{accounts,entries,adjustments,checkpoints}_no_delete` — `BEFORE DELETE`, aborts.
- `audit_log_no_update`, `audit_log_no_delete` — abort on `UPDATE` / `DELETE`.
- `idx_audit_entity` on `audit_log(entity, entity_id)`.

## Dependencies & side effects
None of its own; the schema is applied by `db.init` (idempotent, `IF NOT EXISTS`).

## Behavior clauses

- `DATA-001` [README] A raw `DELETE` on any of `accounts`, `entries`, `adjustments`,
  `checkpoints` is aborted by a trigger and the row remains. [TEST: `test_nothing_can_be_deleted`]
- `DATA-002` [README] A raw `UPDATE` on `audit_log` is aborted by a trigger; the row is
  unchanged. [TEST: `test_nothing_can_be_deleted`]
- `DATA-003` [README] A raw `DELETE` on `audit_log` is aborted by a trigger; the row
  remains. [TEST: `test_nothing_can_be_deleted`]
- `DATA-004` [INFERRED] After `init()` the database contains exactly the tables
  `accounts`, `entries`, `adjustments`, `checkpoints`, `audit_log`, with the columns,
  types and `NOT NULL` flags listed above (checkable via `PRAGMA table_info`).
- `DATA-005` [README] Money columns (`entries.amount`, `adjustments.amount`,
  `checkpoints.balance`) are `INTEGER` (whole cents); a non-integer value is never
  produced by the data layer. `adjustments.percent` is the only fractional column.
- `DATA-006` [README] Every data table has `archived INTEGER NOT NULL DEFAULT 0`;
  archiving is the only removal mechanism, and a newly inserted row without an explicit
  value has `archived = 0`.
- `DATA-007` [INFERRED] `created_at` and `updated_at` are `NOT NULL` on every data table
  (no default: the data layer must supply them on insert).
- `DATA-008` [INFERRED] `entries.kind` accepts only `'recurring'` or `'once'`; any other
  value is rejected by a CHECK constraint (`sqlite3.IntegrityError`).
- `DATA-009` [INFERRED] `entries.interval_months` must be `>= 1`; `0` or negative values
  are rejected by a CHECK constraint. Default is `1`.
- `DATA-010` [README] `audit_log` stores `before` and `after` as nullable TEXT (JSON
  snapshots), in the same database and written in the same transaction as the change.
- `DATA-011` [INFERRED] Index `idx_audit_entity` exists on `audit_log(entity, entity_id)`.
- `DATA-012` [INFERRED] Foreign keys are enforced: inserting an `entries`/`checkpoints`
  row with a non-existent `account_id`, an `adjustments` row with a non-existent
  `entry_id`, or an `entries.to_account_id` that doesn't exist, fails with
  `IntegrityError` (on a connection opened by the data layer).
- `DATA-013` [TEST] `PRAGMA user_version` equals the target of the latest migration in
  `MIGRATIONS` after `init()` (currently `4`; `1` if there were none), for a fresh database
  and for an upgraded one. [TEST: `test_migrations_upgrade_preserves_data`]
- `DATA-014` [INFERRED] Column defaults: `accounts.kind='checking'`, `accounts.reserve=0`, `note=''` (all data
  tables), `entries.category=''`, `entries.estimated=0`, `entries.optional=0`, `adjustments.repeat_yearly=0`, `audit_log.comment=''`.
- `DATA-015` [README] `adjustments.mode` is CHECKed to `'set'`/`'percent'`, but the
  schema does **not** enforce that `amount` is set only for `'set'` and `percent` only
  for `'percent'`; that coupling is enforced by the API models only (`SCH-015/016`). This is
  intended: nothing writes outside the API, and a CHECK would need a table rebuild in a
  migration (OPEN_QUESTIONS #5, B-019). Tests must not assert a DB-level rejection of e.g.
  `mode='set'` with a `percent`.
- `DATA-016` [README] `entries.estimated` accepts only `0` or `1` (CHECK constraint,
  `IntegrityError` otherwise) and defaults to `0` (fixed) when not given (B-015).
- `DATA-017` [README] `accounts.reserve` accepts only `0` or `1` (CHECK constraint,
  `IntegrityError` otherwise) and defaults to `0` (available money) when not given (B-028).
- `DATA-018` [README] `entries.optional` accepts only `0` or `1` (CHECK constraint,
  `IntegrityError` otherwise) and defaults to `0` (planned) when not given (B-029).

## Examples
- `INSERT INTO entries(..., kind) VALUES (..., 'weekly')` → `IntegrityError`.
- `DELETE FROM accounts WHERE id=1` → `IntegrityError: Löschen ist nicht erlaubt – bitte archivieren`.
- `UPDATE audit_log SET comment='x'` → `IntegrityError: Das Änderungsprotokoll ist unveränderlich`.

## Out of scope / not specified
- Date formats inside `TEXT` date columns (validated by the API models, not the DB).
- Exact trigger error message text (German, see CLAUDE.md B-005); assert only that the
  statement is rejected.
- Journal mode / `synchronous` (specified in `DB-SCHEMA-010`).
- Migration mechanics (see `DB-SCHEMA-004..007`); the concrete migrations are `DB-SCHEMA-012..014`.

## Open questions
- None open. (`DATA-015` was settled in OPEN_QUESTIONS #5.)
