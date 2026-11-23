import json
import sqlite3

import pytest

from app import db
from tests.contract.backend.conftest import make_account, make_entry
from tests.contract.helpers.timing import next_ms


def audit(path, **kw):
    with db.read(path) as r:
        return db.audit_list(r, **kw)


@pytest.mark.contract("DB-CRUD-001")
def test_get_returns_full_row_with_system_columns(path):
    """DB-CRUD-001: get returns a dict incl. id, archived, created_at, updated_at."""
    with db.tx(path) as c:
        a = make_account(c, "x")
        row = db.get(c, "accounts", a["id"])
    assert isinstance(row, dict)
    assert {"id", "name", "kind", "note", "archived", "created_at", "updated_at"} <= set(row)
    assert row["name"] == "x"


@pytest.mark.contract("DB-CRUD-001")
def test_get_unknown_id_is_none(path):
    """DB-CRUD-001: get returns None for an unknown id."""
    with db.tx(path) as c:
        assert db.get(c, "accounts", 4242) is None


@pytest.mark.contract("DB-CRUD-002")
def test_all_rows_includes_archived_and_is_ordered_by_id(path):
    """DB-CRUD-002: all_rows returns every row, archived included, ascending by id."""
    with db.tx(path) as c:
        ids = [make_account(c, n)["id"] for n in ("c", "a", "b")]
        db.set_archived(c, "accounts", ids[1], True)
        rows = db.all_rows(c, "accounts")
    assert [r["id"] for r in rows] == sorted(ids)
    assert [r["archived"] for r in rows] == [0, 1, 0]


@pytest.mark.contract("DB-CRUD-002")
def test_all_rows_on_empty_table(path):
    """DB-CRUD-002: an empty table yields an empty list."""
    with db.read(path) as r:
        assert db.all_rows(r, "entries") == []


@pytest.mark.contract("DB-CRUD-003")
def test_create_sets_timestamps_archived_and_id(path):
    """DB-CRUD-003: create sets created_at == updated_at, archived 0, and returns the new id."""
    with db.tx(path) as c:
        a = make_account(c, "x")
        b = make_account(c, "y")
    assert a["created_at"] == a["updated_at"] and a["archived"] == 0
    assert isinstance(a["id"], int) and b["id"] != a["id"]


@pytest.mark.contract("DB-CRUD-004")
def test_create_ignores_non_whitelisted_keys(path):
    """DB-CRUD-004: keys outside TABLES[table] (id, archived, junk) are not written."""
    with db.tx(path) as c:
        a = db.create(c, "accounts", {"name": "x", "kind": "checking", "note": "", "id": 999, "archived": 1,
                                      "created_at": "1999-01-01", "bogus": "zzz"})
    assert a["id"] != 999 and a["archived"] == 0 and a["created_at"] != "1999-01-01"
    assert "bogus" not in a


@pytest.mark.contract("DB-CRUD-004")
def test_create_with_missing_whitelisted_keys_uses_defaults(path):
    """DB-CRUD-004: missing whitelisted keys are inserted as NULL/column default."""
    with db.tx(path) as c:
        a = db.create(c, "accounts", {"name": "only name"})
    assert a["name"] == "only name" and a["kind"] == "checking" and a["note"] == ""


@pytest.mark.contract("DB-CRUD-005")
def test_create_writes_audit_row(path):
    """DB-CRUD-005: create writes action=create, entity, entity_id, before=NULL, after=new row."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    (row,) = audit(path)
    assert (row["action"], row["entity"], row["entity_id"], row["before"]) == ("create", "accounts", a["id"], None)
    assert row["after"]["name"] == "x" and row["after"]["id"] == a["id"]


@pytest.mark.contract("DB-CRUD-006")
def test_update_changes_only_given_columns_and_bumps_updated_at(path):
    """DB-CRUD-006: update changes the listed whitelisted columns, sets updated_at, returns the row."""
    with db.tx(path) as c:
        a = make_account(c, "x", note="keep")
    next_ms()
    with db.tx(path) as c:
        u = db.update(c, "accounts", a["id"], {"name": "y"})
    assert u["name"] == "y" and u["note"] == "keep" and u["kind"] == "checking"
    assert u["updated_at"] > a["updated_at"] and u["created_at"] == a["created_at"]


@pytest.mark.contract("DB-CRUD-006")
def test_update_ignores_non_whitelisted_columns(path):
    """DB-CRUD-006: id/archived/created_at in the data are not written by update."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    next_ms()
    with db.tx(path) as c:
        u = db.update(c, "accounts", a["id"], {"name": "y", "archived": 1, "id": 77, "created_at": "x"})
    assert u["id"] == a["id"] and u["archived"] == 0 and u["created_at"] == a["created_at"]


@pytest.mark.contract("DB-CRUD-007")
def test_stale_expected_updated_at_raises_conflict_and_changes_nothing(path):
    """DB-CRUD-007: a mismatching expected_updated_at raises Conflict('conflict') and writes nothing."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    with pytest.raises(db.Conflict) as ei:
        with db.tx(path) as c:
            db.update(c, "accounts", a["id"], {"name": "y"}, expected_updated_at="2000-01-01T00:00:00.000+00:00")
    assert ei.value.code == "conflict"
    with db.read(path) as r:
        assert db.get(r, "accounts", a["id"])["name"] == "x"
    assert len(audit(path)) == 1


@pytest.mark.contract("DB-CRUD-008")
def test_matching_expected_updated_at_proceeds(path):
    """DB-CRUD-008: a matching expected_updated_at lets the update proceed."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    next_ms()
    with db.tx(path) as c:
        u = db.update(c, "accounts", a["id"], {"name": "y"}, expected_updated_at=a["updated_at"])
    assert u["name"] == "y"


@pytest.mark.contract("DB-CRUD-008")
@pytest.mark.parametrize("expected", [None, ""])
def test_missing_expected_updated_at_skips_the_lock(path, expected):
    """DB-CRUD-008: None/falsy expected_updated_at skips the optimistic-lock check."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    next_ms()
    with db.tx(path) as c:
        db.update(c, "accounts", a["id"], {"name": "y"})
    next_ms()
    with db.tx(path) as c:
        u = db.update(c, "accounts", a["id"], {"name": "z"}, expected_updated_at=expected)
    assert u["name"] == "z"


@pytest.mark.contract("DB-CRUD-009", "DB-ERR-003")
@pytest.mark.parametrize("op", ["update", "archive", "restore"])
def test_missing_id_raises_not_found(path, op):
    """DB-CRUD-009: update/set_archived on a missing id raise NotFound('not_found', entity, id)."""
    with pytest.raises(db.NotFound) as ei:
        with db.tx(path) as c:
            if op == "update":
                db.update(c, "accounts", 31337, {"name": "y"})
            else:
                db.set_archived(c, "accounts", 31337, op == "archive")
    assert ei.value.code == "not_found"
    assert ei.value.params == {"entity": "accounts", "id": 31337}


@pytest.mark.contract("DB-CRUD-010")
def test_noop_update_returns_row_without_bump_or_audit(path):
    """DB-CRUD-010: an update that changes nothing returns the row, keeps updated_at, writes no audit row."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    next_ms()
    with db.tx(path) as c:
        u = db.update(c, "accounts", a["id"], {"name": "x", "kind": "checking"})
    assert u == a
    assert len(audit(path)) == 1


@pytest.mark.contract("DB-CRUD-011")
def test_update_writes_audit_row_with_before_and_after(path):
    """DB-CRUD-011: update writes action=update with before/after snapshots."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    next_ms()
    with db.tx(path) as c:
        db.update(c, "accounts", a["id"], {"name": "y"})
    newest = audit(path)[0]
    assert newest["action"] == "update" and newest["entity"] == "accounts" and newest["entity_id"] == a["id"]
    assert newest["before"]["name"] == "x" and newest["after"]["name"] == "y"


@pytest.mark.contract("DB-CRUD-012")
def test_archive_and_restore_flip_flag_and_log_actions(path):
    """DB-CRUD-012: set_archived True -> archived=1 + 'archive' row; False -> archived=0 + 'restore' row."""
    with db.tx(path) as c:
        a = make_account(c, "x")
        arch = db.set_archived(c, "accounts", a["id"], True)
        rest = db.set_archived(c, "accounts", a["id"], False)
    assert arch["archived"] == 1 and rest["archived"] == 0
    assert [r["action"] for r in audit(path)] == ["restore", "archive", "create"]


@pytest.mark.contract("DB-CRUD-013")
@pytest.mark.parametrize("archived", [True, False])
def test_set_archived_with_stale_expected_updated_at_conflicts(path, archived):
    """DB-CRUD-013: a stale expected_updated_at raises Conflict and changes nothing, for archive and restore."""
    with db.tx(path) as c:
        a = make_account(c, "x")
        if not archived:
            a = db.set_archived(c, "accounts", a["id"], True)
        n = len(db.audit_list(c))
    with pytest.raises(db.Conflict):
        with db.tx(path) as c:
            db.set_archived(c, "accounts", a["id"], archived, expected_updated_at="1999-01-01T00:00:00.000+00:00")
    with db.read(path) as r:
        assert db.get(r, "accounts", a["id"])["archived"] == (0 if archived else 1)
        assert len(db.audit_list(r)) == n


@pytest.mark.contract("DB-CRUD-013")
def test_set_archived_with_matching_or_missing_expected_updated_at(path):
    """DB-CRUD-013: a matching expected_updated_at archives; None skips the check."""
    with db.tx(path) as c:
        a = make_account(c, "x")
        arch = db.set_archived(c, "accounts", a["id"], True, expected_updated_at=a["updated_at"])
        rest = db.set_archived(c, "accounts", a["id"], False, expected_updated_at=None)
    assert arch["archived"] == 1 and rest["archived"] == 0


@pytest.mark.contract("DB-CRUD-013", "DB-CRUD-014")
def test_stale_lock_is_checked_before_the_noop_path(path):
    """DB-CRUD-013: archiving an already-archived row with a stale expected_updated_at still conflicts."""
    with db.tx(path) as c:
        a = db.set_archived(c, "accounts", make_account(c, "x")["id"], True)
    with pytest.raises(db.Conflict):
        with db.tx(path) as c:
            db.set_archived(c, "accounts", a["id"], True, expected_updated_at="stale")


@pytest.mark.contract("DB-CRUD-014")
def test_archiving_twice_and_restoring_active_are_noops(path):
    """DB-CRUD-014: archiving an archived row / restoring an active row writes no audit row."""
    with db.tx(path) as c:
        a = make_account(c, "x")
        db.set_archived(c, "accounts", a["id"], False)       # already active
        n1 = len(db.audit_list(c))
        db.set_archived(c, "accounts", a["id"], True)
        n2 = len(db.audit_list(c))
        db.set_archived(c, "accounts", a["id"], True)        # already archived
        n3 = len(db.audit_list(c))
    assert (n1, n2, n3) == (1, 2, 2)


@pytest.mark.contract("DB-CRUD-015")
def test_comment_is_stored_verbatim_default_empty(path):
    """DB-CRUD-015: the comment lands verbatim on the audit row; the default is ''."""
    text = "Grund: Größe ≠ klein \"quoted\" 日本語"
    with db.tx(path) as c:
        a = make_account(c, "x")
        db.update(c, "accounts", a["id"], {"name": "y"}, comment=text)
        db.set_archived(c, "accounts", a["id"], True, comment="weg")
    rows = audit(path)
    assert [r["comment"] for r in rows] == ["weg", text, ""]


@pytest.mark.contract("DB-CRUD-016", "DB-CRUD-005")
def test_data_write_and_audit_row_roll_back_together(path):
    """DB-CRUD-016: create/update/archive participate in the caller's transaction (all-or-nothing)."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    with pytest.raises(RuntimeError):
        with db.tx(path) as c:
            db.update(c, "accounts", a["id"], {"name": "y"})
            db.set_archived(c, "accounts", a["id"], True)
            make_account(c, "second")
            raise RuntimeError("abort")
    with db.read(path) as r:
        row = db.get(r, "accounts", a["id"])
        assert row["name"] == "x" and row["archived"] == 0
        assert len(db.all_rows(r, "accounts")) == 1
        assert len(db.audit_list(r)) == 1
