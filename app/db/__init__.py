"""Data layer. Every write goes through this package.

Split into focused modules (see BACKLOG.md B-009):
  * connection.py -- connect/tx/read, the single-writer lock
  * schema.py     -- table/trigger DDL and the migration runner
  * errors.py     -- ApiError/NotFound/Conflict
  * crud.py       -- generic get/create/update/archive, writing audit_log
  * audit.py      -- audit log read/revert, export, data_version

Everything below is re-exported so callers keep using `db.<name>` exactly as
before the split.

There is no module-level database path: connect()/tx()/read()/init() take the
path explicitly (callers pass `Settings.db_path`), so several databases can be
used in one process. MIGRATIONS is the one piece tests patch as `db.MIGRATIONS`;
schema.init() re-reads it via `from . import MIGRATIONS` on every call.
"""

from .audit import audit_list, data_version, export_all, revert
from .connection import connect, now, read, tx
from .crud import all_rows, create, get, set_archived, update
from .errors import ApiError, Conflict, NotFound
from .schema import MIGRATIONS, SCHEMA, TABLES, _has_column, init

__all__ = [
    "TABLES", "SCHEMA", "MIGRATIONS",
    "ApiError", "NotFound", "Conflict",
    "now", "connect", "tx", "read", "init", "_has_column",
    "get", "all_rows", "create", "update", "set_archived",
    "revert", "audit_list", "data_version", "export_all",
]
