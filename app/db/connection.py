"""Connection and transaction plumbing: single DB path, single writer lock.

DB_PATH itself is defined in the package's __init__.py (the attribute tests
and callers patch as `db.DB_PATH`); the lookup here is deliberately lazy
(`from . import DB_PATH` inside the function, not at module scope) so a
patched value is picked up on the next call.
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

_write_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect() -> sqlite3.Connection:
    from . import DB_PATH
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


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
