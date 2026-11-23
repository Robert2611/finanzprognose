"""The concrete schema migrations in db.MIGRATIONS (the runner itself is tested in test_db_schema.py)."""
import sqlite3

import pytest

from app import db
from tests.contract.helpers.sqlite_view import open_db, scalar

T = "2026-01-01T00:00:00"


def make_v1_database(path):
    """A database as version 1 created it: the baseline without entries.estimated, with some rows."""
    lines = db.SCHEMA.splitlines()
    v1 = "\n".join(line for line in lines if not line.strip().startswith("estimated "))
    assert len(v1.splitlines()) == len(lines) - 1, "SCHEMA no longer has the estimated column line"
    with open_db(path) as c:
        c.executescript(v1)
        c.execute("PRAGMA user_version=1")
        c.execute("INSERT INTO accounts(name, created_at, updated_at) VALUES ('Giro', ?, ?)", (T, T))
        for name, amount in (("Miete", -120000), ("Lebensmittel", -45000)):
            c.execute("INSERT INTO entries(account_id, name, kind, amount, start_date, created_at, updated_at)"
                      " VALUES (1, ?, 'recurring', ?, '2026-01-01', ?, ?)", (name, amount, T, T))
        c.execute("INSERT INTO checkpoints(account_id, date, balance, created_at, updated_at) VALUES (1, '2026-01-01', 500000, ?, ?)", (T, T))
        c.execute("INSERT INTO audit_log(ts, action, entity, entity_id, after) VALUES (?, 'create', 'entries', 1, '{}')", (T,))
        c.commit()


def dump(path, table):
    with open_db(path) as c:
        return [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY id")]


def columns(path, table):
    with open_db(path) as c:
        return [(r["name"], r["type"], r["notnull"], r["dflt_value"]) for r in c.execute(f"PRAGMA table_info({table})")]


@pytest.mark.contract("DB-SCHEMA-012")
def test_v2_adds_estimated_and_keeps_every_row(tmp_path):
    """DB-SCHEMA-012: upgrading a version-1 database adds entries.estimated=0 and keeps all rows unchanged."""
    path = str(tmp_path / "old.sqlite")
    make_v1_database(path)
    before = {t: dump(path, t) for t in ("accounts", "entries", "checkpoints", "audit_log")}
    db.init(path)
    assert scalar(path, "PRAGMA user_version") == 2
    after = {t: dump(path, t) for t in before}
    assert [{k: v for k, v in r.items() if k != "estimated"} for r in after["entries"]] == before["entries"]
    assert [r["estimated"] for r in after["entries"]] == [0, 0]
    assert {t: after[t] for t in ("accounts", "checkpoints", "audit_log")} == \
           {t: before[t] for t in ("accounts", "checkpoints", "audit_log")}


@pytest.mark.contract("DB-SCHEMA-012")
def test_upgraded_database_matches_a_fresh_one(tmp_path):
    """DB-SCHEMA-012: the upgraded entries table has the same columns as a fresh database's."""
    old, fresh = str(tmp_path / "old.sqlite"), str(tmp_path / "fresh.sqlite")
    make_v1_database(old)
    db.init(old)
    db.init(fresh)
    assert columns(old, "entries")[:-1] == [c for c in columns(fresh, "entries") if c[0] != "estimated"]
    assert ("estimated", "INTEGER", 1, "0") in columns(old, "entries")
    assert ("estimated", "INTEGER", 1, "0") in columns(fresh, "entries")


@pytest.mark.contract("DB-SCHEMA-012")
def test_v2_is_a_no_op_when_the_column_exists(fresh_db):
    """DB-SCHEMA-012: the migration is guarded, so running it on a database that has the column changes nothing."""
    migrate = dict(db.MIGRATIONS)[2]
    with open_db(fresh_db) as c:
        migrate(c)
        assert [r["name"] for r in c.execute("PRAGMA table_info(entries)")].count("estimated") == 1


@pytest.mark.contract("DB-SCHEMA-012")
def test_upgraded_entries_can_be_marked_estimated(tmp_path):
    """DB-SCHEMA-012: after the upgrade an existing entry can be marked as estimated through the data layer."""
    path = str(tmp_path / "old.sqlite")
    make_v1_database(path)
    db.init(path)
    with db.tx(path) as c:
        row = db.update(c, "entries", 2, {"estimated": True})
    assert row["estimated"] == 1


@pytest.mark.contract("DATA-016")
def test_estimated_defaults_to_zero(fresh_db):
    """DATA-016: an entry inserted without estimated is fixed (0)."""
    with open_db(fresh_db) as c:
        c.execute("INSERT INTO accounts(name, created_at, updated_at) VALUES ('A', ?, ?)", (T, T))
        c.execute("INSERT INTO entries(account_id, name, kind, amount, start_date, created_at, updated_at)"
                  " VALUES (1, 'E', 'once', -1, '2026-01-01', ?, ?)", (T, T))
        assert c.execute("SELECT estimated FROM entries").fetchone()[0] == 0


@pytest.mark.contract("DATA-016")
@pytest.mark.parametrize("value", [2, -1, "ja"])
def test_estimated_rejects_values_other_than_zero_and_one(fresh_db, value):
    """DATA-016: the CHECK constraint rejects anything but 0/1."""
    with open_db(fresh_db) as c:
        c.execute("INSERT INTO accounts(name, created_at, updated_at) VALUES ('A', ?, ?)", (T, T))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO entries(account_id, name, kind, amount, start_date, estimated, created_at, updated_at)"
                      " VALUES (1, 'E', 'once', -1, '2026-01-01', ?, ?, ?)", (value, T, T))
