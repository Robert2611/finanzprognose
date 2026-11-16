import pytest

from app import db


@pytest.fixture
def path(fresh_db):
    """Path of an initialised, empty database."""
    return fresh_db


def make_account(c, name="A", **kw):
    return db.create(c, "accounts", {"name": name, "kind": "checking", "note": "", **kw})


def make_entry(c, account_id, name="E", amount=-100, **kw):
    data = {"account_id": account_id, "to_account_id": None, "name": name, "category": "", "kind": "once",
            "amount": amount, "start_date": "2026-01-01", "end_date": None, "interval_months": 1, "note": ""}
    data.update(kw)
    return db.create(c, "entries", data)
