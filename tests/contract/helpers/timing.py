"""Deterministic time helpers (no sleeps)."""
from app import db


def next_ms() -> None:
    """Busy-wait until db.now() has advanced to a later millisecond."""
    t = db.now()
    while db.now() == t:
        pass


def next_second() -> None:
    """Busy-wait until the local wall clock is in a later second (backup file stamps have 1 s resolution)."""
    from datetime import datetime
    t = datetime.now().replace(microsecond=0)
    while datetime.now().replace(microsecond=0) == t:
        pass
