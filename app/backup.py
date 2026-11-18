"""Daily backup to the NAS.

  * Runs once a day at Settings.backup_time (default 03:00).
  * Only backs up if something has changed since the last backup.
  * Old backups are NEVER deleted; every backup is a new file with a timestamp.
  * Each backup consists of a consistent SQLite copy (online backup API, checked with
    integrity_check) and a human-readable JSON export. Checksums go to backups.log.
  * Protection against "NAS not mounted": the target folder must contain the file .nas-marker,
    otherwise NOTHING is backed up and the app shows a red error.
  * If a backup fails, it is retried every hour.

All configuration comes from the `Settings` passed in by the caller (the app's settings),
never from module globals, so tests can use several configurations in one process.
"""
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import threading
from datetime import datetime, timedelta

from . import db
from .settings import Settings

log = logging.getLogger("backup")

MARKER = ".nas-marker"

_lock = threading.Lock()


def _data_version(s: Settings) -> int:
    with db.read(s.db_path) as conn:
        return db.data_version(conn)


def status(s: Settings) -> dict:
    try:
        with open(s.status_file, encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}
    st["backup_dir"] = s.backup_dir
    st["backup_time"] = s.backup_time
    st["current_version"] = _data_version(s)
    st["pending_changes"] = st["current_version"] != st.get("last_version")
    return st


def _save_status(s: Settings, st: dict) -> None:
    st = {k: v for k, v in st.items() if k not in ("backup_dir", "backup_time", "current_version", "pending_changes")}
    tmp = s.status_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, s.status_file)


def _fsync_file(path: str) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_backup(s: Settings, force: bool = False, reason: str = "zeitplan") -> dict:
    backup_dir = s.backup_dir
    with _lock:
        st = status(s)
        st["last_attempt"] = datetime.now().isoformat(timespec="seconds")
        st["last_reason"] = reason
        try:
            if not os.path.isdir(backup_dir):
                raise RuntimeError(f"Backup-Ziel {backup_dir} existiert nicht.")
            if s.backup_require_marker and not os.path.exists(os.path.join(backup_dir, MARKER)):
                raise RuntimeError(
                    f"Datei {MARKER} fehlt im Backup-Ziel – ist das NAS eingebunden? "
                    "Es wurde nichts gesichert.")
            version = _data_version(s)
            last_file = st.get("last_file")
            if (not force and version == st.get("last_version") and last_file
                    and os.path.exists(os.path.join(backup_dir, last_file))):
                st["last_result"] = "unchanged"
                st["last_error"] = None
                return st

            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            base = f"finanzen_{stamp}_v{version}"
            final_db = os.path.join(backup_dir, base + ".sqlite")
            final_json = os.path.join(backup_dir, base + ".json")
            # SQLite must not write to the NAS directly (file locking on SMB/NFS is unreliable
            # and can hang), so build and verify both files next to the database first.
            work_dir = os.path.dirname(os.path.abspath(s.db_path))
            loc_db = os.path.join(work_dir, f".{base}.sqlite.tmp")
            loc_json = os.path.join(work_dir, f".{base}.json.tmp")
            tmp_db = os.path.join(backup_dir, f".{base}.sqlite.tmp")
            tmp_json = os.path.join(backup_dir, f".{base}.json.tmp")

            src = db.connect(s.db_path)
            try:
                dst = sqlite3.connect(loc_db)
                src.backup(dst)
                dst.close()
                export = db.export_all(src)
            finally:
                src.close()

            chk = sqlite3.connect(loc_db)
            try:
                res = chk.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                chk.close()
            if res != "ok":
                raise RuntimeError(f"Integritätsprüfung der Sicherung fehlgeschlagen: {res}")

            with open(loc_json, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=1)
            for src_path, dst_path in ((loc_db, tmp_db), (loc_json, tmp_json)):
                shutil.copyfile(src_path, dst_path)
                _fsync_file(dst_path)
            os.replace(tmp_db, final_db)
            os.replace(tmp_json, final_json)

            line = f"{stamp}\tv{version}\t{os.path.basename(final_db)}\tsha256={_sha256(final_db)}\t{reason}\n"
            with open(os.path.join(backup_dir, "backups.log"), "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            st.update(last_success=st["last_attempt"], last_version=version,
                      last_file=os.path.basename(final_db), last_result="ok", last_error=None)
            log.info("Backup created: %s", final_db)
        except Exception as ex:  # noqa: BLE001
            st["last_result"] = "error"
            st["last_error"] = str(ex)
            log.error("Backup failed: %s", ex)
            for p in ("tmp_db", "tmp_json", "loc_db", "loc_json"):
                path = locals().get(p)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        finally:
            for p in ("loc_db", "loc_json"):
                path = locals().get(p)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            _save_status(s, st)
        return status(s)


def list_backups(s: Settings, limit: int = 100) -> list[dict]:
    backup_dir = s.backup_dir
    if not os.path.isdir(backup_dir):
        return []
    files = []
    for name in os.listdir(backup_dir):
        if name.startswith("finanzen_") and name.endswith(".sqlite"):
            p = os.path.join(backup_dir, name)
            files.append({"name": name, "size": os.path.getsize(p),
                          "mtime": datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds")})
    files.sort(key=lambda f: f["name"], reverse=True)
    return files[:limit]


def _scheduler(s: Settings, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            now = datetime.now()
            hh, mm = map(int, s.backup_time.split(":"))
            due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            st = status(s)
            last_sched = st.get("last_scheduled_run")
            last_sched = datetime.fromisoformat(last_sched) if last_sched else None
            last_attempt = datetime.fromisoformat(st["last_attempt"]) if st.get("last_attempt") else None
            if now >= due and (last_sched is None or last_sched < due):
                st = run_backup(s, reason="zeitplan")
                st["last_scheduled_run"] = now.isoformat(timespec="seconds")
                _save_status(s, st)
            elif (st.get("last_result") == "error" and last_attempt
                  and now - last_attempt > timedelta(hours=1)):
                run_backup(s, reason="wiederholung nach fehler")
        except Exception as ex:  # noqa: BLE001
            log.exception("Error in backup scheduler: %s", ex)
        stop.wait(60)


def start_scheduler(s: Settings) -> threading.Event:
    """Start the daily backup thread. Setting the returned event stops it."""
    stop = threading.Event()
    threading.Thread(target=_scheduler, args=(s, stop), name="backup-scheduler", daemon=True).start()
    return stop
