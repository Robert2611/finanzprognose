"""Datenbank-Schicht.

Core principles for data safety:
  * NOTHING is ever deleted. Records are only archived (archived=1).
    SQLite triggers prevent DELETE on all tables.
  * Every change is stored in the immutable change log (audit_log)
    with its before/after state, in the same transaction.
    Triggers prevent UPDATE and DELETE on the log.
  * Optimistic locking: anyone trying to save a stale version
    (e.g. from a second browser tab) gets a conflict instead of data loss.
  * Amounts are stored as whole cents (INTEGER), so there are no rounding errors.
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "/data/finanzen.sqlite")

# Fields that may be written through the API
TABLES = {
    "accounts": ["name", "kind", "note"],
    "entries": [
        "account_id", "to_account_id", "name", "category", "kind", "amount",
        "start_date", "end_date", "interval_months", "note",
    ],
    "adjustments": ["entry_id", "effective_date", "mode", "amount", "percent", "repeat_yearly", "note"],
    "checkpoints": ["account_id", "date", "balance", "note"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'giro',
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
  comment TEXT NOT NULL DEFAULT ''
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

_write_lock = threading.Lock()


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")  # every transaction is safely on disk
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA user_version=1")
    finally:
        conn.close()


@contextmanager
def tx():
    """Write transaction: all or nothing."""
    with _write_lock:
        conn = connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


@contextmanager
def read():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get(conn, table: str, id_: int) -> dict | None:
    assert table in TABLES
    r = conn.execute(f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone()
    return dict(r) if r else None


def all_rows(conn, table: str) -> list[dict]:
    assert table in TABLES
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def _audit(conn, action, entity, entity_id, before, after, comment=""):
    conn.execute(
        "INSERT INTO audit_log(ts, action, entity, entity_id, before, after, comment) VALUES(?,?,?,?,?,?,?)",
        (now(), action, entity, entity_id,
         json.dumps(before, ensure_ascii=False) if before is not None else None,
         json.dumps(after, ensure_ascii=False) if after is not None else None,
         comment or ""),
    )


def create(conn, table: str, data: dict, comment: str = "") -> dict:
    fields = TABLES[table]
    ts = now()
    cols = fields + ["created_at", "updated_at"]
    vals = [data.get(f) for f in fields] + [ts, ts]
    cur = conn.execute(
        f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals
    )
    new = get(conn, table, cur.lastrowid)
    _audit(conn, "create", table, new["id"], None, new, comment)
    return new


def _write(conn, table, id_, changes: dict, action: str, comment="", expected_updated_at=None) -> dict:
    before = get(conn, table, id_)
    if before is None:
        raise NotFound(f"{table} #{id_} nicht gefunden")
    if expected_updated_at and before["updated_at"] != expected_updated_at:
        raise Conflict("Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen.")
    changes = {k: v for k, v in changes.items() if before.get(k) != v}
    if not changes:
        return before
    changes["updated_at"] = now()
    sets = ",".join(f"{k}=?" for k in changes)
    conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*changes.values(), id_])
    after = get(conn, table, id_)
    _audit(conn, action, table, id_, before, after, comment)
    return after


def update(conn, table, id_, data: dict, expected_updated_at=None, comment="") -> dict:
    changes = {f: data[f] for f in TABLES[table] if f in data}
    return _write(conn, table, id_, changes, "update", comment, expected_updated_at)


def set_archived(conn, table, id_, archived: bool, comment="") -> dict:
    return _write(conn, table, id_, {"archived": 1 if archived else 0},
                  "archive" if archived else "restore", comment)


def revert(conn, audit_id: int) -> dict:
    """Undoes a single logged change (as a new, logged change)."""
    a = conn.execute("SELECT * FROM audit_log WHERE id=?", (audit_id,)).fetchone()
    if a is None:
        raise NotFound(f"Protokolleintrag #{audit_id} nicht gefunden")
    table, eid = a["entity"], a["entity_id"]
    comment = f"Rückgängig gemacht: Protokolleintrag #{audit_id}"
    if a["action"] == "create":
        return _write(conn, table, eid, {"archived": 1}, "revert", comment)
    before = json.loads(a["before"])
    changes = {f: before[f] for f in TABLES[table] + ["archived"] if f in before}
    return _write(conn, table, eid, changes, "revert", comment)


def audit_list(conn, limit=200, before_id=None, entity=None, entity_id=None) -> list[dict]:
    q, p = "SELECT * FROM audit_log WHERE 1=1", []
    if before_id:
        q += " AND id<?"
        p.append(before_id)
    if entity:
        q += " AND entity=?"
        p.append(entity)
    if entity_id:
        q += " AND entity_id=?"
        p.append(entity_id)
    q += " ORDER BY id DESC LIMIT ?"
    p.append(limit)
    out = []
    for r in conn.execute(q, p):
        d = dict(r)
        d["before"] = json.loads(d["before"]) if d["before"] else None
        d["after"] = json.loads(d["after"]) if d["after"] else None
        out.append(d)
    return out


def data_version(conn=None) -> int:
    """Increases with every change; basis for 'only back up if something changed'."""
    own = conn is None
    conn = conn or connect()
    try:
        return conn.execute("SELECT COALESCE(MAX(id),0) FROM audit_log").fetchone()[0]
    finally:
        if own:
            conn.close()


def export_all(conn) -> dict:
    data = {t: all_rows(conn, t) for t in TABLES}
    data["audit_log"] = list(reversed(audit_list(conn, limit=10**9)))
    data["exported_at"] = now()
    data["data_version"] = data_version(conn)
    return data
