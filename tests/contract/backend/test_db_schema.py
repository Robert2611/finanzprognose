import pytest

from app import db
from tests.contract.helpers.sqlite_view import open_db, scalar
from tests.contract.backend.conftest import make_account

SYSTEM_COLS = {"id", "archived", "created_at", "updated_at"}


REAL_MIGRATIONS = list(db.MIGRATIONS)  # captured before any test patches db.MIGRATIONS


def latest():
    """Target version of the last real migration (1 = baseline only)."""
    return max((t for t, _ in REAL_MIGRATIONS), default=1)


def with_extra(*fns):
    """The real migrations plus test migrations numbered after them (latest()+1, +2, ...)."""
    base = latest()
    return [*REAL_MIGRATIONS, *((base + i, fn) for i, fn in enumerate(fns, 1))]


def _add_column(table, col):
    def migrate(conn):
        if not db._has_column(conn, table, col):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
    return migrate


@pytest.mark.contract("DB-SCHEMA-001")
def test_init_creates_parent_directory_and_structure(tmp_path):
    """DB-SCHEMA-001: init(path) creates missing parent dirs and a fully structured empty database."""
    path = str(tmp_path / "a" / "b" / "finanzen.sqlite")
    db.init(path)
    with open_db(path) as c:
        kinds = {(r["type"], r["name"]) for r in c.execute("SELECT type, name FROM sqlite_master")}
        assert c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
    tables = {n for t, n in kinds if t == "table"}
    assert {"accounts", "entries", "adjustments", "checkpoints", "audit_log"} <= tables
    assert ("index", "idx_audit_entity") in kinds
    assert len([1 for t, _ in kinds if t == "trigger"]) >= 6


@pytest.mark.contract("DB-SCHEMA-002")
def test_init_is_idempotent_and_preserves_data(path):
    """DB-SCHEMA-002: calling init() again does not error and destroys nothing."""
    with db.tx(path) as c:
        make_account(c, "keep me")
    db.init(path)
    db.init(path)
    with db.read(path) as r:
        assert [x["name"] for x in db.all_rows(r, "accounts")] == ["keep me"]
        assert r.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1


@pytest.mark.contract("DB-SCHEMA-003")
def test_user_version_is_latest_migration_without_pending_migrations(path):
    """DB-SCHEMA-003: with no pending migrations user_version is the latest migration's target (1 if none)."""
    assert scalar(path, "PRAGMA user_version") == latest()


@pytest.mark.contract("DB-SCHEMA-003")
def test_user_version_is_one_with_an_empty_migration_list(tmp_path, monkeypatch):
    """DB-SCHEMA-003: with an empty MIGRATIONS list a fresh database is at version 1."""
    monkeypatch.setattr(db, "MIGRATIONS", [])
    path = str(tmp_path / "x.sqlite")
    db.init(path)
    assert scalar(path, "PRAGMA user_version") == 1


@pytest.mark.contract("DB-SCHEMA-004")
def test_migration_runs_and_preserves_rows(path, monkeypatch):
    """DB-SCHEMA-004: a newly registered migration is applied, user_version advances to its target, rows survive."""
    with db.tx(path) as c:
        make_account(c, "old row")
    monkeypatch.setattr(db, "MIGRATIONS", with_extra(_add_column("accounts", "color")))
    db.init(path)
    assert scalar(path, "PRAGMA user_version") == latest() + 1
    with open_db(path) as c:
        assert db._has_column(c, "accounts", "color")
        assert [r["name"] for r in c.execute("SELECT name FROM accounts")] == ["old row"]


@pytest.mark.contract("DB-SCHEMA-005")
def test_rerunning_init_does_not_reapply_a_migration(path, monkeypatch):
    """DB-SCHEMA-005: init() after a migration is a no-op; the migration is not applied again."""
    calls = []

    def migrate(conn):
        calls.append(1)
        _add_column("accounts", "color")(conn)

    monkeypatch.setattr(db, "MIGRATIONS", with_extra(migrate))
    db.init(path)
    db.init(path)
    assert calls == [1]
    assert scalar(path, "PRAGMA user_version") == latest() + 1


@pytest.mark.contract("DB-SCHEMA-006")
def test_failing_migration_rolls_back_and_propagates(path, monkeypatch):
    """DB-SCHEMA-006: a raising migration is rolled back and init() raises; earlier migrations stay applied."""
    def bad(conn):
        conn.execute("ALTER TABLE accounts ADD COLUMN broken TEXT")
        raise RuntimeError("migration failed")

    good_version = latest() + 1
    monkeypatch.setattr(db, "MIGRATIONS", with_extra(_add_column("accounts", "color"), bad))
    with pytest.raises(RuntimeError, match="migration failed"):
        db.init(path)
    assert scalar(path, "PRAGMA user_version") == good_version
    with open_db(path) as c:
        assert db._has_column(c, "accounts", "color")
        assert not db._has_column(c, "accounts", "broken")


@pytest.mark.contract("DB-SCHEMA-007")
def test_only_pending_migrations_run_in_ascending_order(path, monkeypatch):
    """DB-SCHEMA-007: migrations with target > user_version run in ascending order; applied ones are skipped."""
    order = []
    n = latest()
    monkeypatch.setattr(db, "MIGRATIONS", with_extra(lambda c: order.append(1)))
    db.init(path)
    order.clear()
    monkeypatch.setattr(db, "MIGRATIONS", with_extra(lambda c: order.append(1), lambda c: order.append(2),
                                                     lambda c: order.append(3)))
    db.init(path)
    assert order == [2, 3]
    assert scalar(path, "PRAGMA user_version") == n + 3


@pytest.mark.contract("DB-SCHEMA-008")
def test_tables_whitelist_has_exactly_the_four_data_tables():
    """DB-SCHEMA-008: TABLES has exactly the four data tables as keys, not audit_log."""
    assert set(db.TABLES) == {"accounts", "entries", "adjustments", "checkpoints"}
    assert "audit_log" not in db.TABLES


@pytest.mark.contract("DB-SCHEMA-008")
def test_tables_whitelist_excludes_system_columns():
    """DB-SCHEMA-008: system columns (id, archived, created_at, updated_at) are never writable."""
    for table, cols in db.TABLES.items():
        assert SYSTEM_COLS.isdisjoint(cols), table
        assert "name" in cols or table in ("adjustments", "checkpoints")


@pytest.mark.contract("DB-SCHEMA-009")
def test_has_column(path):
    """DB-SCHEMA-009: _has_column is True iff the column exists per PRAGMA table_info."""
    with open_db(path) as c:
        assert db._has_column(c, "accounts", "name") is True
        assert db._has_column(c, "accounts", "nope") is False
        assert db._has_column(c, "entries", "amount") is True
        assert db._has_column(c, "checkpoints", "name") is False


@pytest.mark.contract("DB-SCHEMA-010")
def test_init_enables_wal(path):
    """DB-SCHEMA-010: init() puts the database in WAL mode (synchronous=FULL is per-connection, see F-2)."""
    assert scalar(path, "PRAGMA journal_mode").lower() == "wal"


@pytest.mark.contract("DB-SCHEMA-011")
def test_baseline_exists_before_migrations_run(tmp_path, monkeypatch):
    """DB-SCHEMA-011: on a fresh database the baseline tables already exist when a migration runs."""
    seen = {}

    def migrate(conn):
        seen["tables"] = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        _add_column("accounts", "color")(conn)

    monkeypatch.setattr(db, "MIGRATIONS", with_extra(migrate))
    path = str(tmp_path / "f" / "x.sqlite")
    db.init(path)
    assert {"accounts", "entries", "adjustments", "checkpoints", "audit_log"} <= seen["tables"]


@pytest.mark.contract("DB-SCHEMA-011")
def test_guarded_migration_converges_when_column_already_exists(path, monkeypatch):
    """DB-SCHEMA-011: a column-adding migration guarded by _has_column tolerates the column already existing."""
    with open_db(path) as c:
        c.execute("ALTER TABLE accounts ADD COLUMN color TEXT")
    monkeypatch.setattr(db, "MIGRATIONS", with_extra(_add_column("accounts", "color")))
    db.init(path)
    assert scalar(path, "PRAGMA user_version") == latest() + 1
