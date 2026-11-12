# db — schema & migrations
ID prefix: DB-SCHEMA
Layer: backend

## Purpose
Creates the database on startup and keeps it up to date: it applies an idempotent schema
baseline (tables, triggers, index), then runs an ordered list of numbered migrations on
top, advancing `user_version` as it goes. It also exposes the `TABLES` whitelist that
drives the generic CRUD and export.

## Interface
Import: `from app import db`.

- `db.init() -> None` — create/upgrade the database at `db.DB_PATH`. Safe to call
  repeatedly. Sets WAL + `synchronous=FULL`, applies `SCHEMA`, ensures `user_version >= 1`,
  then applies each pending migration in `MIGRATIONS` in its own transaction.
- `db.TABLES: dict[str, list[str]]` — the writable-column whitelist, keys
  `accounts`, `entries`, `adjustments`, `checkpoints` (see `data/schema.md` for the lists).
- `db.SCHEMA: str` — the idempotent baseline DDL (`CREATE TABLE/TRIGGER/INDEX IF NOT EXISTS`).
- `db.MIGRATIONS: list[tuple[int, callable]]` — ordered `(target_version, fn)`; empty by
  default. Patchable by tests.
- `db._has_column(conn, table, col) -> bool` — helper used to guard idempotent `ALTER`s.

## Dependencies & side effects
Creates the parent directory of `db.DB_PATH`. Creates/alters the SQLite schema. Reads
`db.DB_PATH` and `db.MIGRATIONS` lazily on each call (so patched values take effect).

## Behavior clauses

- `DB-SCHEMA-001` [INFERRED] `init()` on a non-existent `DB_PATH` creates the parent
  directory and an empty, fully-structured database (all tables, triggers, index present).
- `DB-SCHEMA-002` [INFERRED] `init()` is idempotent: calling it again on an existing
  database makes no destructive change and does not error.
- `DB-SCHEMA-003` [TEST] After `init()` with no pending migrations, `PRAGMA user_version`
  is `1`. [TEST: `test_migrations_upgrade_preserves_data`]
- `DB-SCHEMA-004` [TEST] Given a version-1 database with existing rows and a migration
  `(2, fn)` registered in `MIGRATIONS`, `init()` applies `fn`, advances `user_version` to
  `2`, and preserves all existing rows. [TEST: `test_migrations_upgrade_preserves_data`]
- `DB-SCHEMA-005` [TEST] Re-running `init()` after a migration is a no-op: `user_version`
  stays at the latest target and the migration is not re-applied (migrations are expected
  to be idempotent, e.g. guarding `ALTER` with `_has_column`).
  [TEST: `test_migrations_upgrade_preserves_data`]
- `DB-SCHEMA-006` [INFERRED] Each migration runs in its own transaction; if a migration
  raises, that migration's changes roll back and `init()` propagates the error (earlier
  migrations that already committed stay applied).
- `DB-SCHEMA-007` [INFERRED] Migrations are applied in ascending `target_version` order,
  and only those with `target_version` greater than the current `user_version`.
- `DB-SCHEMA-008` [INFERRED] `TABLES` contains exactly the four data tables as keys; it
  does not include `audit_log` (the audit log is not written through generic CRUD).
- `DB-SCHEMA-009` [INFERRED] `_has_column(conn, table, col)` returns `True` iff `col` is a
  column of `table` per `PRAGMA table_info`.
- `DB-SCHEMA-010` [README] `init()` enables WAL (`journal_mode=WAL`) and
  `synchronous=FULL` so every committed change is durable on disk.
- `DB-SCHEMA-011` [INFERRED] The baseline is applied before migrations, so a fresh
  database gets a new column from `SCHEMA` while an existing one gets it from the matching
  migration — both converge to the same shape (the migration must therefore guard against
  the column already existing).

## Examples
- Fresh dir, `init()` → empty DB, `user_version=1`, `SELECT COUNT(*) FROM accounts` = 0.
- `MIGRATIONS=[(2, add_color)]`, `init()` twice → `user_version=2`, column added once.

## Out of scope / not specified
- The concrete contents of `SCHEMA` beyond what `data/schema.md` specifies.
- Downgrade/rollback of an applied migration (not supported).
- Behavior when `MIGRATIONS` is non-monotonic or has duplicate targets (not specified;
  the project convention is ascending unique targets).

## Open questions
None.
