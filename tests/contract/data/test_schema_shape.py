import sqlite3

import pytest

from app import db
from tests.contract.helpers.sqlite_view import open_db, scalar

COMMON = {"id": ("INTEGER", None), "archived": ("INTEGER", 1), "created_at": ("TEXT", 1), "updated_at": ("TEXT", 1),
          "note": ("TEXT", 1)}
# name -> (declared type, NOT NULL flag or None when not asserted)
EXPECTED = {
    "accounts": {**COMMON, "name": ("TEXT", 1), "kind": ("TEXT", 1)},
    "entries": {**COMMON, "account_id": ("INTEGER", 1), "to_account_id": ("INTEGER", 0), "name": ("TEXT", 1),
                "category": ("TEXT", 1), "kind": ("TEXT", 1), "amount": ("INTEGER", 1), "start_date": ("TEXT", 1),
                "end_date": ("TEXT", 0), "interval_months": ("INTEGER", 1),
                "estimated": ("INTEGER", 1)},
    "adjustments": {**COMMON, "entry_id": ("INTEGER", 1), "effective_date": ("TEXT", 1), "mode": ("TEXT", 1),
                    "amount": ("INTEGER", 0), "percent": ("REAL", 0), "repeat_yearly": ("INTEGER", 1)},
    "checkpoints": {**COMMON, "account_id": ("INTEGER", 1), "date": ("TEXT", 1), "balance": ("INTEGER", 1)},
    "audit_log": {"id": ("INTEGER", None), "ts": ("TEXT", 1), "action": ("TEXT", 1), "entity": ("TEXT", 1),
                  "entity_id": ("INTEGER", 1), "before": ("TEXT", 0), "after": ("TEXT", 0),
                  "comment": ("TEXT", 1), "reverts_id": ("INTEGER", 0)},
}
# audit_log has no archived/created_at/updated_at/note
EXPECTED["audit_log"] = {k: v for k, v in EXPECTED["audit_log"].items()}

# minimal valid raw rows (no defaults relied on except where a test says so)
T = "2026-01-01T00:00:00.000+00:00"


def insert_account(c, **kw):
    cols = {"name": "A", "created_at": T, "updated_at": T, **kw}
    cur = c.execute(f"INSERT INTO accounts({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", list(cols.values()))
    return cur.lastrowid


@pytest.mark.contract("DATA-004")
def test_init_creates_exactly_the_five_tables(fresh_db):
    """DATA-004: init() creates exactly accounts, entries, adjustments, checkpoints, audit_log."""
    with open_db(fresh_db) as c:
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert names == set(EXPECTED)


@pytest.mark.contract("DATA-004")
@pytest.mark.parametrize("table", list(EXPECTED))
def test_table_columns_types_and_not_null(fresh_db, table):
    """DATA-004: each table has the listed columns with the listed types and NOT NULL flags."""
    with open_db(fresh_db) as c:
        info = {r["name"]: (r["type"].upper(), r["notnull"]) for r in c.execute(f"PRAGMA table_info({table})")}
    assert set(info) == set(EXPECTED[table])
    for col, (typ, notnull) in EXPECTED[table].items():
        assert info[col][0] == typ, f"{table}.{col} type"
        if notnull is not None:
            assert info[col][1] == notnull, f"{table}.{col} notnull"


@pytest.mark.contract("DATA-005")
def test_money_columns_are_declared_integer(fresh_db):
    """DATA-005: entries.amount, adjustments.amount and checkpoints.balance are INTEGER; percent is REAL."""
    with open_db(fresh_db) as c:
        def typ(t, col):
            return {r["name"]: r["type"].upper() for r in c.execute(f"PRAGMA table_info({t})")}[col]
        assert typ("entries", "amount") == "INTEGER"
        assert typ("adjustments", "amount") == "INTEGER"
        assert typ("checkpoints", "balance") == "INTEGER"
        assert typ("adjustments", "percent") == "REAL"


@pytest.mark.contract("DATA-005")
def test_data_layer_stores_whole_cents(world):
    """DATA-005: values written through the app are stored as integers (percent as real)."""
    assert scalar(world["db"], "SELECT typeof(amount) FROM entries") == "integer"
    assert scalar(world["db"], "SELECT typeof(amount) FROM adjustments") == "integer"
    assert scalar(world["db"], "SELECT DISTINCT typeof(balance) FROM checkpoints") == "integer"


@pytest.mark.contract("DATA-005")
def test_percent_adjustment_amount_is_null_and_percent_fractional(client, seed, db_path):
    """DATA-005: adjustments.percent is the only fractional column."""
    a = seed.account()
    e = seed.entry(a["id"], amount=-100000)
    seed.adjustment(e["id"], "2026-01-01", mode="percent", percent=2.5, repeat_yearly=True)
    assert scalar(db_path, "SELECT percent FROM adjustments") == 2.5
    assert scalar(db_path, "SELECT amount FROM adjustments") is None


@pytest.mark.contract("DATA-006")
@pytest.mark.parametrize("table", ["accounts", "entries", "adjustments", "checkpoints"])
def test_archived_column_defaults_to_zero(fresh_db, table):
    """DATA-006: archived is INTEGER NOT NULL DEFAULT 0 on every data table."""
    with open_db(fresh_db) as c:
        row = {r["name"]: r for r in c.execute(f"PRAGMA table_info({table})")}["archived"]
        assert row["type"].upper() == "INTEGER" and row["notnull"] == 1 and str(row["dflt_value"]) == "0"


@pytest.mark.contract("DATA-006")
def test_row_inserted_without_archived_has_zero(fresh_db):
    """DATA-006: a newly inserted row without an explicit archived value has archived = 0."""
    with open_db(fresh_db) as c:
        aid = insert_account(c)
        assert c.execute("SELECT archived FROM accounts WHERE id=?", (aid,)).fetchone()[0] == 0


@pytest.mark.contract("DATA-006")
def test_archive_does_not_remove_the_row(world, client):
    """DATA-006: archiving is the removal mechanism: the row stays with archived=1."""
    eid = world["entry"]["id"]
    assert client.post(f"/api/entries/{eid}/archive", json={}).status_code == 200
    assert scalar(world["db"], "SELECT archived FROM entries WHERE id=?", (eid,)) == 1


def _insert_sql(table, omit):
    acct = 1
    base = {
        "accounts": {"name": "A"},
        "entries": {"account_id": acct, "name": "E", "kind": "once", "amount": 1, "start_date": "2026-01-01"},
        "adjustments": {"entry_id": 1, "effective_date": "2026-01-01", "mode": "set"},
        "checkpoints": {"account_id": acct, "date": "2026-01-01", "balance": 0},
    }[table]
    cols = {**base, "created_at": T, "updated_at": T}
    cols.pop(omit)
    return f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", list(cols.values())


@pytest.mark.contract("DATA-007")
@pytest.mark.parametrize("omit", ["created_at", "updated_at"])
@pytest.mark.parametrize("table", ["accounts", "entries", "adjustments", "checkpoints"])
def test_timestamps_are_required_on_insert(fresh_db, table, omit):
    """DATA-007: created_at/updated_at are NOT NULL with no default."""
    with open_db(fresh_db) as c:
        insert_account(c)                                            # account id 1
        c.execute("INSERT INTO entries(account_id,name,kind,amount,start_date,created_at,updated_at) "
                  "VALUES (1,'E','once',1,'2026-01-01',?,?)", (T, T))  # entry id 1
        sql, params = _insert_sql(table, omit)
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(sql, params)


@pytest.mark.contract("DATA-011")
def test_audit_entity_index_exists(fresh_db):
    """DATA-011: idx_audit_entity exists on audit_log(entity, entity_id)."""
    with open_db(fresh_db) as c:
        idx = c.execute("SELECT tbl_name FROM sqlite_master WHERE type='index' AND name='idx_audit_entity'").fetchone()
        assert idx is not None and idx["tbl_name"] == "audit_log"
        cols = [r["name"] for r in c.execute("PRAGMA index_info(idx_audit_entity)")]
    assert cols == ["entity", "entity_id"]


@pytest.mark.contract("DATA-013")
def test_fresh_database_user_version_is_latest_migration_target(fresh_db):
    """DATA-013: PRAGMA user_version of a fresh database equals the target of the latest migration."""
    assert scalar(fresh_db, "PRAGMA user_version") == max(v for v, _ in db.MIGRATIONS)


@pytest.mark.contract("DATA-013")
def test_user_version_equals_latest_migration_target(fresh_db, monkeypatch):
    """DATA-013: after init() with a migration (2, fn), user_version equals 2."""
    def add_col(conn):
        if not db._has_column(conn, "accounts", "color"):
            conn.execute("ALTER TABLE accounts ADD COLUMN color TEXT")
    monkeypatch.setattr(db, "MIGRATIONS", [(2, add_col)])
    db.init(fresh_db)
    assert scalar(fresh_db, "PRAGMA user_version") == 2


@pytest.mark.contract("DATA-014")
def test_column_defaults(fresh_db):
    """DATA-014: documented column defaults apply when a column is omitted."""
    with open_db(fresh_db) as c:
        aid = insert_account(c)
        c.execute("INSERT INTO entries(account_id,name,kind,amount,start_date,created_at,updated_at) "
                  "VALUES (?,?,?,?,?,?,?)", (aid, "E", "once", 5, "2026-01-01", T, T))
        eid = c.execute("SELECT id FROM entries").fetchone()[0]
        c.execute("INSERT INTO adjustments(entry_id,effective_date,mode,created_at,updated_at) VALUES (?,?,?,?,?)",
                  (eid, "2026-01-01", "set", T, T))
        c.execute("INSERT INTO checkpoints(account_id,date,balance,created_at,updated_at) VALUES (?,?,?,?,?)",
                  (aid, "2026-01-01", 0, T, T))
        c.execute("INSERT INTO audit_log(ts,action,entity,entity_id) VALUES (?,?,?,?)", (T, "create", "accounts", aid))
        q = lambda sql: c.execute(sql).fetchone()[0]
        assert q("SELECT kind FROM accounts") == "checking"
        assert q("SELECT note FROM accounts") == "" and q("SELECT note FROM entries") == ""
        assert q("SELECT note FROM adjustments") == "" and q("SELECT note FROM checkpoints") == ""
        assert q("SELECT category FROM entries") == ""
        assert q("SELECT interval_months FROM entries") == 1
        assert q("SELECT repeat_yearly FROM adjustments") == 0
        assert q("SELECT comment FROM audit_log") == ""
