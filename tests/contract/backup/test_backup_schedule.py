"""B-021: when the scheduled backup and the retry run (BKP-001, BKP-019, BKP-026)."""
from datetime import datetime, timedelta

import pytest

from app import backup, backup_schedule
from app.backup_schedule import due_run

DAY = datetime(2026, 11, 23)


def at(hh, mm=0, day=DAY):
    return day.replace(hour=hh, minute=mm)


# ------------------------------------------------------------------ the pure decision

@pytest.mark.contract("BKP-026")
@pytest.mark.parametrize("now, st, expected", [
    (at(2, 59), {}, None),                                                             # before BACKUP_TIME
    (at(3, 0), {}, "scheduled"),                                                       # at BACKUP_TIME
    (at(3, 1), {"last_scheduled_run": at(3, 0).isoformat()}, None),                    # already ran today
    (at(15), {"last_scheduled_run": at(3, 0, DAY - timedelta(days=1)).isoformat()}, "scheduled"),  # catch-up after a restart
    (at(2), {"last_scheduled_run": at(3, 0, DAY - timedelta(days=1)).isoformat()}, None),         # next run not due yet
    (at(3, 0, DAY + timedelta(days=1)), {"last_scheduled_run": at(3, 0).isoformat()}, "scheduled"),  # the next day
])
def test_scheduled_run_is_due_once_a_day_from_backup_time(now, st, expected):
    """BKP-026: the scheduled run is due from BACKUP_TIME on, once per day, including a catch-up after a restart."""
    assert due_run(now, st, "03:00") == expected


@pytest.mark.contract("BKP-026")
@pytest.mark.parametrize("since, result, expected", [
    (timedelta(minutes=61), "error", "retry"),
    (timedelta(minutes=59), "error", None),
    (timedelta(hours=5), "ok", None),
    (timedelta(hours=5), "unchanged", None),
])
def test_retry_is_due_an_hour_after_a_failed_attempt(since, result, expected):
    """BKP-026: a retry is due once more than an hour has passed since a failed attempt, never after ok/unchanged."""
    now = at(12)
    st = {"last_scheduled_run": at(3).isoformat(), "last_result": result, "last_attempt": (now - since).isoformat()}
    assert due_run(now, st, "03:00") == expected


@pytest.mark.contract("BKP-026")
def test_scheduled_run_takes_precedence_over_a_retry():
    """BKP-026: when both are due, one scheduled run happens (not two runs)."""
    st = {"last_scheduled_run": at(3, 0, DAY - timedelta(days=1)).isoformat(), "last_result": "error",
          "last_attempt": at(1).isoformat()}
    assert due_run(at(3, 5), st, "03:00") == "scheduled"


@pytest.mark.contract("BKP-026")
def test_backup_time_is_honored():
    """BKP-026: the due time comes from BACKUP_TIME."""
    assert due_run(at(21, 29), {}, "21:30") is None
    assert due_run(at(21, 30), {}, "21:30") == "scheduled"


# ------------------------------------------------------------------ tick() against a real app

def files(nas):
    return sorted(n for n in nas.names() if n.endswith(".sqlite"))


@pytest.mark.contract("BKP-001")
def test_tick_runs_the_daily_backup_once(settings, healthy, bump):
    """BKP-001: a tick at BACKUP_TIME backs up and records the run; another tick that day does nothing."""
    today = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0)
    assert backup_schedule.tick(settings, today) == "scheduled"
    st = backup.status(settings)
    assert st["last_result"] == "ok" and st["last_reason"] == "scheduled"
    assert st["last_scheduled_run"] == today.isoformat(timespec="seconds")
    bump()
    assert backup_schedule.tick(settings, today + timedelta(minutes=1)) is None
    assert len(files(healthy)) == 1


@pytest.mark.contract("BKP-001")
def test_tick_on_the_next_day_backs_up_the_new_changes(settings, healthy, bump):
    """BKP-001: the next day's tick runs again and writes a new file for the new data version."""
    today = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0)
    backup_schedule.tick(settings, today)
    bump()
    assert backup_schedule.tick(settings, today + timedelta(days=1)) == "scheduled"
    assert len(files(healthy)) == 2


@pytest.mark.contract("BKP-019")
def test_failed_backup_is_retried_after_an_hour(settings, client, nas, seed):
    """BKP-019: a failed run is not retried within the hour, then retried; the retry is tagged 'retry'."""
    seed.account()
    backup.run_backup(settings)                          # marker missing -> error, last_attempt = now
    assert backup.status(settings)["last_result"] == "error"
    # today's scheduled run counts as done (recorded later than any due time the ticks below can see),
    # so these ticks can only ever decide on the retry, whatever the time of day the suite runs at
    backup.mark_scheduled_run(settings, datetime.now() + timedelta(hours=2))
    assert backup_schedule.tick(settings, datetime.now() + timedelta(minutes=30)) is None
    nas.put_marker()
    assert backup_schedule.tick(settings, datetime.now() + timedelta(minutes=61)) == "retry"
    st = backup.status(settings)
    assert st["last_result"] == "ok" and st["last_reason"] == "retry" and len(files(nas)) == 1
