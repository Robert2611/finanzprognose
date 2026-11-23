"""When the daily backup runs (B-021).

The decision is a pure function of the current time and the backup status, so it can be
tested at any wall-clock time; the daemon thread only calls tick() every 60 seconds.

  * Scheduled run: once per day at Settings.backup_time. If the app starts after that time
    and today's run hasn't happened yet (e.g. after a reboot or an update), it is made up
    right away. A run with no changes is cheap: run_backup() reports "unchanged".
  * Retry: if the last attempt failed, try again once more than an hour has passed since it.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from . import backup
from .settings import Settings

log = logging.getLogger("backup")

RETRY_AFTER = timedelta(hours=1)


def _parse(ts: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(ts) if ts else None


def due_run(now: datetime, st: dict, backup_time: str) -> Optional[str]:
    """The reason of the run that is due at `now` (backup.REASON_SCHEDULED/REASON_RETRY), or None."""
    hh, mm = map(int, backup_time.split(":"))
    due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    last_sched = _parse(st.get("last_scheduled_run"))
    if now >= due and (last_sched is None or last_sched < due):
        return backup.REASON_SCHEDULED
    last_attempt = _parse(st.get("last_attempt"))
    if st.get("last_result") == "error" and last_attempt and now - last_attempt > RETRY_AFTER:
        return backup.REASON_RETRY
    return None


def tick(s: Settings, now: Optional[datetime] = None) -> Optional[str]:
    """Run the backup that is due at `now` (default: the current local time); returns its reason or None."""
    now = now or datetime.now()
    reason = due_run(now, backup.status(s), s.backup_time)
    if reason is not None:
        backup.run_backup(s, reason=reason)
        if reason == backup.REASON_SCHEDULED:
            backup.mark_scheduled_run(s, now)
    return reason


def _loop(s: Settings, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            tick(s)
        except Exception as ex:  # noqa: BLE001
            log.exception("Error in backup scheduler: %s", ex)
        stop.wait(60)


def start_scheduler(s: Settings) -> threading.Event:
    """Start the daily backup thread. Setting the returned event stops it."""
    stop = threading.Event()
    threading.Thread(target=_loop, args=(s, stop), name="backup-scheduler", daemon=True).start()
    return stop
