"""Schema definition and the migration runner (see docs/backlog-done.md B-002).

Core data-safety principles enforced here:
  * NOTHING is ever deleted. Records are only archived (archived=1).
    SQLite triggers prevent DELETE on all tables.
  * audit_log is append-only. Triggers prevent UPDATE and DELETE on it.
  * Amounts are stored as whole cents (INTEGER), so there are no rounding errors.
"""
import os

from .connection import connect

# Fields that may be written through the API
TABLES = {
    "accounts": ["name", "kind", "reserve", "note"],
    "entries": [
        "account_id", "to_account_id", "name", "category", "kind", "amount",
        "start_date", "end_date", "interval_months", "estimated", "note",
    ],
    "adjustments": ["entry_id", "effective_date", "mode", "amount", "percent", "repeat_yearly", "note"],
    "checkpoints": ["account_id", "date", "balance", "note"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'checking',
  reserve INTEGER NOT NULL DEFAULT 0 CHECK(reserve IN (0,1)),  -- 1 = a reserve, not money to plan with (B-028)
  note TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries(
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  to_account_id INTEGER REFERENCES accounts(id),
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL CHECK(kind IN ('recurring','once')),
  amount INTEGER NOT NULL,              -- cents, signed (transfer: positive)
  start_date TEXT NOT NULL,
  end_date TEXT,
  interval_months INTEGER NOT NULL DEFAULT 1 CHECK(interval_months >= 1),
  estimated INTEGER NOT NULL DEFAULT 0 CHECK(estimated IN (0,1)),  -- 1 = an estimate, not a fixed debit (B-015)
  note TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adjustments(
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entries(id),
  effective_date TEXT NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('set','percent')),
  amount INTEGER,                        -- if mode='set': new amount in cents
  percent REAL,                          -- if mode='percent'
  repeat_yearly INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoints(
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  date TEXT NOT NULL,
  balance INTEGER NOT NULL,              -- actual account balance at the end of this day, in cents
  note TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  before TEXT,
  after TEXT,
  comment TEXT NOT NULL DEFAULT '',
  reverts_id INTEGER REFERENCES audit_log(id)
);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity, entity_id);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Das Änderungsprotokoll ist unveränderlich'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Das Änderungsprotokoll ist unveränderlich'); END;
"""

for _t in TABLES:
    SCHEMA += f"""
CREATE TRIGGER IF NOT EXISTS {_t}_no_delete BEFORE DELETE ON {_t}
BEGIN SELECT RAISE(ABORT, 'Löschen ist nicht erlaubt – bitte archivieren'); END;
"""


def _has_column(conn, table: str, col: str) -> bool:
    return any(r["name"] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def _v2_entries_estimated(conn) -> None:
    """B-015: mark entries as estimated (variable spending) instead of fixed; existing rows stay fixed."""
    if not _has_column(conn, "entries", "estimated"):
        conn.execute("ALTER TABLE entries ADD COLUMN estimated INTEGER NOT NULL DEFAULT 0 CHECK(estimated IN (0,1))")


def _v3_accounts_reserve(conn) -> None:
    """B-028: mark accounts as a reserve that is not money to plan with; existing accounts stay available."""
    if not _has_column(conn, "accounts", "reserve"):
        conn.execute("ALTER TABLE accounts ADD COLUMN reserve INTEGER NOT NULL DEFAULT 0 CHECK(reserve IN (0,1))")


# Ordered schema migrations, each `(target_version, migrate_fn)`. Version 1 is the
# baseline created by SCHEMA above, so real migrations start at 2. A migration must be
# idempotent (e.g. guard ALTERs with _has_column): a fresh database already gets the
# change from SCHEMA, while an existing one gets it here. SCHEMA stays the living picture
# of the current schema; every change to an existing table also needs a migration here.
MIGRATIONS: list[tuple[int, "callable"]] = [
    (2, _v2_entries_estimated),
    (3, _v3_accounts_reserve),
]


def init(path: str) -> None:
    """Create or upgrade the database at `path`."""
    # Lazy package-level lookup (not a module-scope import): MIGRATIONS is patched
    # as `db.MIGRATIONS` by tests, so each run of init() must re-read the current value.
    from . import MIGRATIONS

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")   # must run outside a transaction
        conn.execute("PRAGMA synchronous=FULL")   # every transaction is safely on disk
        conn.executescript(SCHEMA)                # idempotent baseline (version 1)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            version = 1
            conn.execute("PRAGMA user_version=1")
        for target, migrate in MIGRATIONS:
            if version < target:
                conn.execute("BEGIN")
                try:
                    migrate(conn)
                    conn.execute(f"PRAGMA user_version={target}")
                    conn.execute("COMMIT")
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
                version = target
    finally:
        conn.close()
