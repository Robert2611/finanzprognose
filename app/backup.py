"""Tägliche Sicherung auf das NAS.

  * Läuft einmal täglich zur Uhrzeit BACKUP_TIME (Standard 03:00).
  * Sichert nur, wenn sich seit der letzten Sicherung etwas geändert hat.
  * Alte Stände werden NIE gelöscht – jede Sicherung ist eine neue Datei mit Zeitstempel.
  * Pro Sicherung: konsistente SQLite-Kopie (online backup API, integrity_check geprüft)
    und ein menschenlesbarer JSON-Export. Prüfsummen landen in backups.log.
  * Schutz gegen "NAS nicht eingebunden": Im Zielordner muss die Datei .nas-marker liegen,
    sonst wird NICHT gesichert und die App zeigt einen roten Fehler an.
  * Schlägt eine Sicherung fehl, wird stündlich erneut versucht.
"""
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from . import db

log = logging.getLogger("backup")

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backup")
BACKUP_TIME = os.environ.get("BACKUP_TIME", "03:00")
REQUIRE_MARKER = os.environ.get("BACKUP_REQUIRE_MARKER", "1") == "1"
MARKER = ".nas-marker"

_lock = threading.Lock()


def _status_file() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(db.DB_PATH)), "backup_status.json")


def status() -> dict:
    try:
        with open(_status_file(), encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}
    st["backup_dir"] = BACKUP_DIR
    st["backup_time"] = BACKUP_TIME
    st["current_version"] = db.data_version()
    st["pending_changes"] = st["current_version"] != st.get("last_version")
    return st


def _save_status(st: dict) -> None:
    st = {k: v for k, v in st.items() if k not in ("backup_dir", "backup_time", "current_version", "pending_changes")}
    tmp = _status_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _status_file())


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


def run_backup(force: bool = False, reason: str = "zeitplan") -> dict:
    with _lock:
        st = status()
        st["last_attempt"] = datetime.now().isoformat(timespec="seconds")
        st["last_reason"] = reason
        try:
            if not os.path.isdir(BACKUP_DIR):
                raise RuntimeError(f"Backup-Ziel {BACKUP_DIR} existiert nicht.")
            if REQUIRE_MARKER and not os.path.exists(os.path.join(BACKUP_DIR, MARKER)):
                raise RuntimeError(
                    f"Datei {MARKER} fehlt im Backup-Ziel – ist das NAS eingebunden? "
                    "Es wurde nichts gesichert.")
            version = db.data_version()
            last_file = st.get("last_file")
            if (not force and version == st.get("last_version") and last_file
                    and os.path.exists(os.path.join(BACKUP_DIR, last_file))):
                st["last_result"] = "unchanged"
                st["last_error"] = None
                return st

            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            base = f"finanzen_{stamp}_v{version}"
            final_db = os.path.join(BACKUP_DIR, base + ".sqlite")
            final_json = os.path.join(BACKUP_DIR, base + ".json")
            tmp_db = os.path.join(BACKUP_DIR, f".{base}.sqlite.tmp")
            tmp_json = os.path.join(BACKUP_DIR, f".{base}.json.tmp")

            src = db.connect()
            try:
                dst = sqlite3.connect(tmp_db)
                src.backup(dst)
                dst.close()
                export = db.export_all(src)
            finally:
                src.close()

            chk = sqlite3.connect(tmp_db)
            try:
                res = chk.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                chk.close()
            if res != "ok":
                raise RuntimeError(f"Integritätsprüfung der Sicherung fehlgeschlagen: {res}")

            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=1)
            for p in (tmp_db, tmp_json):
                _fsync_file(p)
            os.replace(tmp_db, final_db)
            os.replace(tmp_json, final_json)

            line = f"{stamp}\tv{version}\t{os.path.basename(final_db)}\tsha256={_sha256(final_db)}\t{reason}\n"
            with open(os.path.join(BACKUP_DIR, "backups.log"), "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            st.update(last_success=st["last_attempt"], last_version=version,
                      last_file=os.path.basename(final_db), last_result="ok", last_error=None)
            log.info("Sicherung erstellt: %s", final_db)
        except Exception as ex:  # noqa: BLE001
            st["last_result"] = "error"
            st["last_error"] = str(ex)
            log.error("Sicherung fehlgeschlagen: %s", ex)
            for p in ("tmp_db", "tmp_json"):
                path = locals().get(p)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        finally:
            _save_status(st)
        return status()


def list_backups(limit: int = 100) -> list[dict]:
    if not os.path.isdir(BACKUP_DIR):
        return []
    files = []
    for name in os.listdir(BACKUP_DIR):
        if name.startswith("finanzen_") and name.endswith(".sqlite"):
            p = os.path.join(BACKUP_DIR, name)
            files.append({"name": name, "size": os.path.getsize(p),
                          "mtime": datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds")})
    files.sort(key=lambda f: f["name"], reverse=True)
    return files[:limit]


def _scheduler() -> None:
    while True:
        try:
            now = datetime.now()
            hh, mm = map(int, BACKUP_TIME.split(":"))
            due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            st = status()
            last_sched = st.get("last_scheduled_run")
            last_sched = datetime.fromisoformat(last_sched) if last_sched else None
            last_attempt = datetime.fromisoformat(st["last_attempt"]) if st.get("last_attempt") else None
            if now >= due and (last_sched is None or last_sched < due):
                st = run_backup(reason="zeitplan")
                st["last_scheduled_run"] = now.isoformat(timespec="seconds")
                _save_status(st)
            elif (st.get("last_result") == "error" and last_attempt
                  and now - last_attempt > timedelta(hours=1)):
                run_backup(reason="wiederholung nach fehler")
        except Exception as ex:  # noqa: BLE001
            log.exception("Fehler im Backup-Planer: %s", ex)
        time.sleep(60)


def start_scheduler() -> None:
    threading.Thread(target=_scheduler, name="backup-scheduler", daemon=True).start()
