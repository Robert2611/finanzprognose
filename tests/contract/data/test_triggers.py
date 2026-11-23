import sqlite3

import pytest

from tests.contract.helpers.sqlite_view import open_db

DATA_TABLES = {"accounts": "account", "entries": "entry", "adjustments": "adjustment", "checkpoints": "checkpoint"}


@pytest.mark.contract("DATA-001")
@pytest.mark.parametrize("table", list(DATA_TABLES))
def test_raw_delete_on_data_table_is_aborted(world, table):
    """DATA-001: a raw DELETE on a data table is aborted and the row remains."""
    row_id = world[DATA_TABLES[table]]["id"]
    with open_db(world["db"]) as c:
        with pytest.raises(sqlite3.DatabaseError):
            c.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
        assert c.execute(f"SELECT COUNT(*) FROM {table} WHERE id=?", (row_id,)).fetchone()[0] == 1


@pytest.mark.contract("DATA-001")
@pytest.mark.parametrize("table", list(DATA_TABLES))
def test_raw_delete_of_all_rows_is_aborted(world, table):
    """DATA-001: even an unfiltered DELETE removes nothing."""
    with open_db(world["db"]) as c:
        before = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        with pytest.raises(sqlite3.DatabaseError):
            c.execute(f"DELETE FROM {table}")
        assert c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == before


@pytest.mark.contract("DATA-002")
def test_raw_update_on_audit_log_is_aborted(world):
    """DATA-002: a raw UPDATE on audit_log is aborted and the row is unchanged."""
    with open_db(world["db"]) as c:
        first = c.execute("SELECT id, comment, action FROM audit_log ORDER BY id LIMIT 1").fetchone()
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("UPDATE audit_log SET comment='tampered' WHERE id=?", (first["id"],))
        again = c.execute("SELECT id, comment, action FROM audit_log WHERE id=?", (first["id"],)).fetchone()
        assert tuple(again) == tuple(first)


@pytest.mark.contract("DATA-003")
def test_raw_delete_on_audit_log_is_aborted(world):
    """DATA-003: a raw DELETE on audit_log is aborted and the rows remain."""
    with open_db(world["db"]) as c:
        before = c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        assert before > 0
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("DELETE FROM audit_log WHERE id=(SELECT MIN(id) FROM audit_log)")
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("DELETE FROM audit_log")
        assert c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before
