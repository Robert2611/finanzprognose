"""Read-only check of one backup file on the NAS (B-022).

Restoring stays a manual procedure: nothing here writes to BACKUP_DIR or touches the live
database. The chosen file is copied to a private staging file next to the database (SQLite
must never open files on the NAS, see BKP-024), opened read-only and immutable, and checked:

  * PRAGMA integrity_check,
  * its data_version (MAX(audit_log.id)) against the _v<N> in its name,
  * its SHA-256 against the line backups.log recorded when it was written,
  * row counts per table and its schema version, for the user to compare.

Problems are returned as language-neutral {code, params}; the frontend shows German text.
"""
import os
import re
import shutil
import sqlite3
import uuid
from typing import Optional

from . import db
from .backup import _sha256
from .settings import Settings

NAME = re.compile(r"^finanzen_\d{4}-\d{2}-\d{2}_\d{6}_v(\d+)\.sqlite$")


class BackupNotFound(Exception):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


def _logged_sha256(s: Settings, name: str) -> Optional[str]:
    """The checksum backups.log recorded for `name` (the last matching line), or None."""
    found = None
    try:
        with open(os.path.join(s.backup_dir, "backups.log"), encoding="utf-8") as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if len(cols) >= 4 and cols[2] == name and cols[3].startswith("sha256="):
                    found = cols[3].removeprefix("sha256=")
    except FileNotFoundError:
        pass
    return found


def verify_backup(s: Settings, name: str) -> dict:
    m = NAME.match(name or "")
    path = os.path.join(s.backup_dir, name) if m else None
    if not m or not os.path.isfile(path):
        raise BackupNotFound(name)   # also rejects any path ("../x"), since the name must match exactly
    file_version = int(m.group(1))
    result = {"name": name, "ok": False, "problems": [], "size": os.path.getsize(path),
              "file_version": file_version, "data_version": None, "schema_version": None,
              "counts": {}, "sha256": None, "sha256_logged": None}

    staging = os.path.join(os.path.dirname(os.path.abspath(s.db_path)), f".verify-{uuid.uuid4().hex}.sqlite.tmp")
    try:
        shutil.copyfile(path, staging)
        result["sha256"] = _sha256(staging)
        result["sha256_logged"] = _logged_sha256(s, name)
        if result["sha256_logged"] and result["sha256_logged"] != result["sha256"]:
            result["problems"].append({"code": "checksum_mismatch", "params": {}})
        try:
            conn = sqlite3.connect(f"file:{staging}?mode=ro&immutable=1", uri=True)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    result["problems"].append({"code": "integrity_failed", "params": {"result": integrity}})
                result["schema_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for t in [*db.TABLES, "audit_log"]:
                    if t in tables:
                        result["counts"][t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                if "audit_log" in tables:
                    result["data_version"] = conn.execute("SELECT COALESCE(MAX(id), 0) FROM audit_log").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.DatabaseError as ex:
            result["problems"].append({"code": "not_a_database", "params": {"detail": str(ex)}})
        else:
            missing = [t for t in [*db.TABLES, "audit_log"] if t not in result["counts"]]
            if missing:
                result["problems"].append({"code": "tables_missing", "params": {"tables": ", ".join(missing)}})
            elif result["data_version"] != file_version:
                result["problems"].append({"code": "version_mismatch",
                                           "params": {"file_version": file_version, "data_version": result["data_version"]}})
    finally:
        try:
            os.remove(staging)
        except OSError:
            pass
    result["ok"] = not result["problems"]
    return result
