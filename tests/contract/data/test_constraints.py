import sqlite3

import pytest

from tests.contract.helpers.sqlite_view import open_db

T = "2026-01-01T00:00:00.000+00:00"


@pytest.fixture
def conn(fresh_db):
    with open_db(fresh_db) as c:   # foreign_keys=ON, like a data-layer connection
        c.execute("INSERT INTO accounts(name,created_at,updated_at) VALUES ('A',?,?)", (T, T))
        yield c


def add_entry(c, kind="once", interval=None, account=1, to_account=None):
    cols = ["account_id", "to_account_id", "name", "kind", "amount", "start_date", "created_at", "updated_at"]
    vals = [account, to_account, "E", kind, 5, "2026-01-01", T, T]
    if interval is not None:
        cols.append("interval_months")
        vals.append(interval)
    c.execute(f"INSERT INTO entries({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)


@pytest.mark.contract("DATA-008")
@pytest.mark.parametrize("kind", ["recurring", "once"])
def test_entry_kind_accepts_allowed_values(conn, kind):
    """DATA-008: entries.kind accepts 'recurring' and 'once'."""
    add_entry(conn, kind=kind)


@pytest.mark.contract("DATA-008")
@pytest.mark.parametrize("kind", ["weekly", "", "RECURRING", "Once"])
def test_entry_kind_rejects_other_values(conn, kind):
    """DATA-008: any other entries.kind is rejected by a CHECK constraint."""
    with pytest.raises(sqlite3.IntegrityError):
        add_entry(conn, kind=kind)


@pytest.mark.contract("DATA-009")
@pytest.mark.parametrize("interval", [0, -1, -12])
def test_interval_months_below_one_is_rejected(conn, interval):
    """DATA-009: interval_months of 0 or a negative value is rejected."""
    with pytest.raises(sqlite3.IntegrityError):
        add_entry(conn, interval=interval)


@pytest.mark.contract("DATA-009")
@pytest.mark.parametrize("interval", [1, 2, 120])
def test_interval_months_one_or_more_is_accepted(conn, interval):
    """DATA-009: interval_months >= 1 is accepted."""
    add_entry(conn, interval=interval)


@pytest.mark.contract("DATA-009")
def test_interval_months_defaults_to_one(conn):
    """DATA-009: the default for interval_months is 1."""
    add_entry(conn)
    assert conn.execute("SELECT interval_months FROM entries").fetchone()[0] == 1


@pytest.mark.contract("DATA-012")
def test_entry_with_missing_account_is_rejected(conn):
    """DATA-012: an entries row with a non-existent account_id fails with IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        add_entry(conn, account=999)


@pytest.mark.contract("DATA-012")
def test_entry_with_missing_to_account_is_rejected(conn):
    """DATA-012: an entries row with a non-existent to_account_id fails with IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        add_entry(conn, to_account=999)


@pytest.mark.contract("DATA-012")
def test_checkpoint_with_missing_account_is_rejected(conn):
    """DATA-012: a checkpoints row with a non-existent account_id fails with IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO checkpoints(account_id,date,balance,created_at,updated_at) VALUES (999,'2026-01-01',0,?,?)", (T, T))


@pytest.mark.contract("DATA-012")
def test_adjustment_with_missing_entry_is_rejected(conn):
    """DATA-012: an adjustments row with a non-existent entry_id fails with IntegrityError."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO adjustments(entry_id,effective_date,mode,created_at,updated_at) VALUES (999,'2026-01-01','set',?,?)", (T, T))


@pytest.mark.contract("DATA-012")
def test_valid_references_are_accepted(conn):
    """DATA-012: rows referencing existing parents are accepted."""
    conn.execute("INSERT INTO accounts(name,created_at,updated_at) VALUES ('B',?,?)", (T, T))
    add_entry(conn, account=1, to_account=2)
    conn.execute("INSERT INTO adjustments(entry_id,effective_date,mode,created_at,updated_at) VALUES (1,'2026-01-01','set',?,?)", (T, T))
    conn.execute("INSERT INTO checkpoints(account_id,date,balance,created_at,updated_at) VALUES (1,'2026-01-01',0,?,?)", (T, T))


@pytest.mark.contract("DATA-015")
@pytest.mark.parametrize("mode", ["set", "percent"])
def test_adjustment_mode_accepts_set_and_percent(conn, mode):
    """DATA-015: adjustments.mode accepts 'set' and 'percent'."""
    add_entry(conn)
    conn.execute("INSERT INTO adjustments(entry_id,effective_date,mode,created_at,updated_at) VALUES (1,'2026-01-01',?,?,?)", (mode, T, T))


@pytest.mark.contract("DATA-015")
@pytest.mark.parametrize("mode", ["multiply", "", "SET"])
def test_adjustment_mode_rejects_other_values(conn, mode):
    """DATA-015: adjustments.mode is CHECKed to 'set'/'percent'."""
    add_entry(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO adjustments(entry_id,effective_date,mode,created_at,updated_at) VALUES (1,'2026-01-01',?,?,?)", (mode, T, T))
