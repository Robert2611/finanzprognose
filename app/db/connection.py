"""Connection and transaction plumbing: explicit DB path, single writer lock.

The database path is passed in by the caller (it comes from the app's `Settings`), so
there is no module-level path to patch and several databases can be used in one process.
The writer lock stays process-wide: it only needs to serialize writers, and sharing it
between databases is harmless.
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

_write_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def tx(path: str):
    """Write transaction: all or nothing."""
    with _write_lock:
        conn = connect(path)
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
def read(path: str):
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()
