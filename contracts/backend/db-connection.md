# db — connection & transactions
ID prefix: DB-CONN
Layer: backend

## Purpose
Owns how the rest of the backend talks to SQLite: it opens connections with the right
pragmas, serializes all writes through a single process-wide lock inside all-or-nothing
transactions, and supplies the canonical UTC timestamp used on every write. This is the
plumbing every other data-layer function builds on.

## Interface
Import: `from app import db` (re-exported from the `app.db` package).

- `db.connect() -> sqlite3.Connection` — a new connection; `row_factory=sqlite3.Row`,
  `foreign_keys=ON`, `busy_timeout=30000`, autocommit (`isolation_level=None`).
- `db.tx()` — context manager yielding a connection inside a write transaction
  (`BEGIN IMMEDIATE` … `COMMIT`, `ROLLBACK` on any exception). Acquires the process-wide
  write lock for its whole body.
- `db.read()` — context manager yielding a connection for reads; no transaction, no lock.
- `db.now() -> str` — current time as UTC ISO-8601 with millisecond precision
  (e.g. `'2026-11-12T09:30:00.123+00:00'`).
- `db.DB_PATH: str` — the database file path (module attribute; patchable by tests;
  re-read lazily on each `connect()`).

## Dependencies & side effects
Reads `db.DB_PATH`. Opens/holds SQLite connections. `tx()` holds an in-process
`threading.Lock` for the duration of the `with` block. No network, no files beyond the DB.

## Behavior clauses

- `DB-CONN-001` [INFERRED] `connect()` returns a usable connection whose rows are
  mapping-style (`row['col']` works) because `row_factory` is `sqlite3.Row`.
- `DB-CONN-002` [INFERRED] `connect()` honors the current value of `db.DB_PATH` at call
  time, not the value captured at import (patching `db.DB_PATH` then calling `connect()`
  opens the new path). [TEST: `test_migrations_upgrade_preserves_data` relies on this]
- `DB-CONN-003` [README] Within a `tx()` block, all statements commit together on normal
  exit and roll back entirely if the block raises — partial writes never persist.
- `DB-CONN-004` [README] `tx()` serializes writers: two `tx()` blocks cannot run their
  bodies concurrently (process-level lock + `BEGIN IMMEDIATE`). This is why the app runs a
  single worker.
- `DB-CONN-005` [INFERRED] An exception raised inside a `tx()` block propagates to the
  caller after the transaction is rolled back and the connection closed.
- `DB-CONN-006` [INFERRED] `read()` yields a connection and closes it on exit without
  beginning a transaction or taking the write lock; concurrent reads are allowed.
- `DB-CONN-007` [INFERRED] `now()` returns a string that is timezone-aware UTC (ends in
  `+00:00`) and has millisecond precision (three fractional-second digits).
- `DB-CONN-008` [INFERRED] `now()` is monotonic enough across separate writes that two
  writes performed ≥1 ms apart get distinct timestamps; callers rely on `updated_at`
  changing between successive updates to the same row (see `DB-CRUD` optimistic locking).
- `DB-CONN-009` [INFERRED] Connections are closed when the `tx()`/`read()` block exits
  (no connection leak on success or on exception).

## Examples
- `with db.tx() as c: db.create(c, 'accounts', {...})` → committed; a later `read()` sees
  the row.
- `with db.tx() as c: db.create(...); raise RuntimeError()` → nothing persisted.

## Out of scope / not specified
- The exact `busy_timeout`/`timeout` numeric values as externally asserted behavior
  (documented for context; don't build tests around the 30 000 ms figure).
- Behavior under multiple OS processes (the app forbids `--workers > 1`).

## Open questions
None.
