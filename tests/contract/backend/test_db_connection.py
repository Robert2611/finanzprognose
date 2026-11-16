import re
import sqlite3
import threading
from datetime import datetime, timedelta

import pytest

from app import db
from tests.contract.backend.conftest import make_account
from tests.contract.helpers.timing import next_ms


@pytest.mark.contract("DB-CONN-001")
def test_connect_returns_mapping_rows(path):
    """DB-CONN-001: connect(path) rows support row['col'] access."""
    c = db.connect(path)
    try:
        row = c.execute("SELECT 1 AS one, 'x' AS two").fetchone()
        assert row["one"] == 1 and row["two"] == "x"
    finally:
        c.close()


@pytest.mark.contract("DB-CONN-001")
def test_connect_pragmas_from_the_interface(path):
    """DB-CONN-001: foreign keys are on and the connection is in autocommit mode."""
    c = db.connect(path)
    try:
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.isolation_level is None
    finally:
        c.close()


@pytest.mark.contract("DB-CONN-002")
def test_two_paths_side_by_side(make_settings):
    """DB-CONN-002: connect(path) opens exactly that database; two paths coexist in one process."""
    a, b = make_settings().db_path, make_settings().db_path
    db.init(a)
    db.init(b)
    with db.tx(a) as c:
        make_account(c, "only in A")
    with db.read(a) as ca, db.read(b) as cb:
        assert ca.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1
        assert cb.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0


@pytest.mark.contract("DB-CONN-003")
def test_tx_commits_on_normal_exit(path):
    """DB-CONN-003: statements in a tx() block commit together on normal exit."""
    with db.tx(path) as c:
        make_account(c, "one")
        make_account(c, "two")
    with db.read(path) as r:
        assert r.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 2
        assert r.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 2


@pytest.mark.contract("DB-CONN-003")
def test_tx_rolls_back_everything_on_exception(path):
    """DB-CONN-003: if the block raises, no statement persists (data and audit rows alike)."""
    with pytest.raises(RuntimeError):
        with db.tx(path) as c:
            make_account(c, "one")
            make_account(c, "two")
            raise RuntimeError("boom")
    with db.read(path) as r:
        assert r.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
        assert r.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0


@pytest.mark.contract("DB-CONN-004")
def test_tx_blocks_serialize_writers(path):
    """DB-CONN-004: a second tx() body cannot start while another tx() is open."""
    a_inside, release_a, b_inside = threading.Event(), threading.Event(), threading.Event()

    def writer_a():
        with db.tx(path):
            a_inside.set()
            release_a.wait(10)

    def writer_b():
        with db.tx(path):
            b_inside.set()

    ta = threading.Thread(target=writer_a)
    ta.start()
    assert a_inside.wait(5)
    tb = threading.Thread(target=writer_b)
    tb.start()
    try:
        assert not b_inside.wait(0.3), "second writer entered while the first still held its transaction"
    finally:
        release_a.set()
    assert b_inside.wait(10), "second writer never got the lock after the first finished"
    ta.join(10)
    tb.join(10)


@pytest.mark.contract("DB-CONN-005", "DB-CONN-009")
def test_exception_propagates_and_connection_is_closed(path):
    """DB-CONN-005/009: the exception reaches the caller and the connection is closed afterwards."""
    holder = {}
    with pytest.raises(ValueError, match="bad"):
        with db.tx(path) as c:
            holder["c"] = c
            raise ValueError("bad")
    with pytest.raises(sqlite3.ProgrammingError):
        holder["c"].execute("SELECT 1")


@pytest.mark.contract("DB-CONN-009")
def test_tx_connection_closed_after_normal_exit(path):
    """DB-CONN-009: the tx() connection is closed after a successful block."""
    with db.tx(path) as c:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        c.execute("SELECT 1")


@pytest.mark.contract("DB-CONN-006", "DB-CONN-009")
def test_read_closes_connection_and_opens_no_transaction(path):
    """DB-CONN-006/009: read() yields a connection outside any transaction and closes it on exit."""
    with db.read(path) as r:
        assert r.in_transaction is False
        r.execute("SELECT 1").fetchone()
    with pytest.raises(sqlite3.ProgrammingError):
        r.execute("SELECT 1")


@pytest.mark.contract("DB-CONN-006")
def test_read_does_not_take_the_write_lock(path):
    """DB-CONN-006: read() works while a tx() is open (no write lock, no blocking)."""
    with db.tx(path) as c:
        make_account(c, "x")
        with db.read(path) as r:
            r.execute("SELECT COUNT(*) FROM accounts").fetchone()


@pytest.mark.contract("DB-CONN-006")
def test_concurrent_reads_are_allowed(path):
    """DB-CONN-006: several read() connections can be open at once."""
    with db.read(path) as r1, db.read(path) as r2:
        assert r1.execute("SELECT 1").fetchone()[0] == r2.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.contract("DB-CONN-007")
def test_now_is_utc_with_millisecond_precision():
    """DB-CONN-007: now() is timezone-aware UTC ending in +00:00 with three fractional digits."""
    s = db.now()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00", s), s
    parsed = datetime.fromisoformat(s)
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.contract("DB-CONN-008")
def test_writes_a_millisecond_apart_get_distinct_timestamps(path):
    """DB-CONN-008: two writes >= 1 ms apart get distinct updated_at values."""
    with db.tx(path) as c:
        acc = make_account(c, "n0")
    next_ms()
    with db.tx(path) as c:
        first = db.update(c, "accounts", acc["id"], {"name": "n1"})
    next_ms()
    with db.tx(path) as c:
        second = db.update(c, "accounts", acc["id"], {"name": "n2"})
    assert len({acc["updated_at"], first["updated_at"], second["updated_at"]}) == 3
    assert second["updated_at"] > first["updated_at"] > acc["updated_at"]
