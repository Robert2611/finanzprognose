"""Data layer. Every write goes through this package.

Split into focused modules (see BACKLOG.md B-009):
  * connection.py -- DB path, connect/tx/read, the single-writer lock
  * schema.py     -- table/trigger DDL and the migration runner
  * errors.py     -- ApiError/NotFound/Conflict
  * crud.py       -- generic get/create/update/archive, writing audit_log
  * audit.py      -- audit log read/revert, export, data_version

Everything below is re-exported so callers keep using `db.<name>` exactly as
before the split.

DB_PATH is defined here, not in connection.py: it's the one piece of mutable
config callers/tests patch directly as `db.DB_PATH`, and connection.connect()
/ schema.init() look it up lazily (`from . import DB_PATH`) so a patched
value takes effect on the next call instead of being frozen at import time.
Same story for MIGRATIONS, which schema.init() re-reads via `from . import
MIGRATIONS` rather than its own module global.
"""
import os

DB_PATH = os.environ.get("DB_PATH", "/data/finanzen.sqlite")

from .audit import audit_list, data_version, export_all, revert
from .connection import connect, now, read, tx
from .crud import all_rows, create, get, set_archived, update
from .errors import ApiError, Conflict, NotFound
from .schema import MIGRATIONS, SCHEMA, TABLES, _has_column, init

__all__ = [
    "DB_PATH", "TABLES", "SCHEMA", "MIGRATIONS",
    "ApiError", "NotFound", "Conflict",
    "now", "connect", "tx", "read", "init", "_has_column",
    "get", "all_rows", "create", "update", "set_archived",
    "revert", "audit_list", "data_version", "export_all",
]
