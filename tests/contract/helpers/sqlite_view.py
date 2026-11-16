"""Plain sqlite3 access to a database or a backup file (read-mostly helper)."""
import sqlite3
from contextlib import contextmanager


@contextmanager
def open_db(path, foreign_keys: bool = True):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def scalar(path, sql, params=()):
    with open_db(path) as c:
        row = c.execute(sql, params).fetchone()
        return None if row is None else row[0]


def integrity_check(path) -> str:
    return scalar(path, "PRAGMA integrity_check")
