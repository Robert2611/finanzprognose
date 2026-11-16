import re

import pytest

from app import db
from tests.contract.backend.conftest import make_account, make_entry
from tests.contract.helpers.timing import next_ms


def audit(path, **kw):
    with db.read(path) as r:
        return db.audit_list(r, **kw)


def version(path):
    with db.read(path) as r:
        return db.data_version(r)


@pytest.fixture
def history(path):
    """account A (create, rename), account B (create), entry on A (create)."""
    with db.tx(path) as c:
        a = make_account(c, "A")
        b = make_account(c, "B")
        e = make_entry(c, a["id"], "E")
    next_ms()
    with db.tx(path) as c:
        db.update(c, "accounts", a["id"], {"name": "A2"})
    return {"a": a, "b": b, "e": e}


@pytest.mark.contract("DB-AUDIT-001")
def test_audit_list_is_newest_first(path, history):
    """DB-AUDIT-001: audit_list returns rows by id descending."""
    ids = [r["id"] for r in audit(path)]
    assert ids == sorted(ids, reverse=True) and len(ids) == 4


@pytest.mark.contract("DB-AUDIT-002")
def test_before_after_are_parsed_objects_or_none(path, history):
    """DB-AUDIT-002: before/after come back as dicts or None, never JSON strings."""
    rows = audit(path)
    assert isinstance(rows[0]["before"], dict) and isinstance(rows[0]["after"], dict)
    assert rows[-1]["before"] is None and isinstance(rows[-1]["after"], dict)
    assert {"id", "ts", "action", "entity", "entity_id", "before", "after", "comment", "reverts_id"} <= set(rows[0])


@pytest.mark.contract("DB-AUDIT-003")
def test_entity_and_entity_id_filters_combine(path, history):
    """DB-AUDIT-003: entity filters to a table, entity_id to a record, both together (AND)."""
    assert {r["entity"] for r in audit(path, entity="accounts")} == {"accounts"}
    assert len(audit(path, entity="accounts")) == 3
    assert len(audit(path, entity="entries")) == 1
    a = history["a"]["id"]
    assert [r["action"] for r in audit(path, entity="accounts", entity_id=a)] == ["update", "create"]
    assert audit(path, entity="entries", entity_id=a) == [] or all(r["entity"] == "entries" for r in audit(path, entity="entries", entity_id=a))


@pytest.mark.contract("DB-AUDIT-003")
def test_entity_id_without_match_is_empty(path, history):
    """DB-AUDIT-003: a filter that matches nothing yields an empty list."""
    assert audit(path, entity="accounts", entity_id=999999) == []


@pytest.mark.contract("DB-AUDIT-004")
def test_before_id_returns_only_older_rows(path, history):
    """DB-AUDIT-004: before_id returns only rows with id < before_id (keyset pagination)."""
    ids = [r["id"] for r in audit(path)]
    older = audit(path, before_id=ids[1])
    assert [r["id"] for r in older] == ids[2:]
    assert audit(path, before_id=ids[-1]) == []


@pytest.mark.contract("DB-AUDIT-005")
def test_limit_caps_and_default_is_200(path):
    """DB-AUDIT-005: limit caps the result; the default cap is 200."""
    with db.tx(path) as c:
        for i in range(205):
            make_account(c, f"n{i}")
    assert len(audit(path, limit=5)) == 5
    assert len(audit(path)) == 200
    assert len(audit(path, limit=1000)) == 205


@pytest.mark.contract("DB-AUDIT-006", "DB-AUDIT-010", "DB-AUDIT-008")
def test_revert_update_restores_before_and_appends_a_revert_row(path, history):
    """DB-AUDIT-006/008/010: reverting an update restores the old name, appends a revert row, leaves the old row alone."""
    a = history["a"]["id"]
    upd = audit(path, entity="accounts", entity_id=a)[0]
    before_rows = audit(path)
    with db.tx(path) as c:
        res = db.revert(c, upd["id"])
    assert res["name"] == "A"
    newest = audit(path)[0]
    assert newest["action"] == "revert" and newest["reverts_id"] == upd["id"]
    assert newest["entity"] == "accounts" and newest["entity_id"] == a
    assert audit(path)[1:] == before_rows        # history untouched, only appended


@pytest.mark.contract("DB-AUDIT-006")
def test_revert_archive_restores_active_flag(path, history):
    """DB-AUDIT-006: reverting an archive row sets archived back to 0."""
    b = history["b"]["id"]
    with db.tx(path) as c:
        db.set_archived(c, "accounts", b, True)
    arch = audit(path)[0]
    with db.tx(path) as c:
        res = db.revert(c, arch["id"])
        assert res["archived"] == 0
        assert db.get(c, "accounts", b)["archived"] == 0


@pytest.mark.contract("DB-AUDIT-006")
def test_revert_restore_archives_again(path, history):
    """DB-AUDIT-006: reverting a restore row sets archived back to 1."""
    b = history["b"]["id"]
    with db.tx(path) as c:
        db.set_archived(c, "accounts", b, True)
        db.set_archived(c, "accounts", b, False)
    restore = audit(path)[0]
    assert restore["action"] == "restore"
    with db.tx(path) as c:
        assert db.revert(c, restore["id"])["archived"] == 1


@pytest.mark.contract("DB-AUDIT-007")
def test_revert_create_archives_the_record(path, history):
    """DB-AUDIT-007: reverting a create row archives the record and logs a revert row."""
    e = history["e"]["id"]
    create = audit(path, entity="entries", entity_id=e)[-1]
    assert create["action"] == "create"
    with db.tx(path) as c:
        res = db.revert(c, create["id"])
    assert res["archived"] == 1
    with db.read(path) as r:
        assert db.get(r, "entries", e) is not None
    newest = audit(path)[0]
    assert newest["action"] == "revert" and newest["reverts_id"] == create["id"]


@pytest.mark.contract("DB-AUDIT-009")
def test_revert_unknown_audit_id_raises_not_found(path):
    """DB-AUDIT-009: revert of a non-existent audit id raises NotFound(entity='audit_log', id=...)."""
    with pytest.raises(db.NotFound) as ei:
        with db.tx(path) as c:
            db.revert(c, 424242)
    assert ei.value.code == "not_found" and ei.value.params == {"entity": "audit_log", "id": 424242}


@pytest.mark.contract("DB-AUDIT-011")
def test_data_version_is_zero_when_empty_then_counts_changes(path):
    """DB-AUDIT-011: data_version is 0 on an empty DB and rises by one per logged change."""
    assert version(path) == 0
    with db.tx(path) as c:
        a = make_account(c, "x")
    assert version(path) == 1
    next_ms()
    with db.tx(path) as c:
        db.update(c, "accounts", a["id"], {"name": "y"})
    assert version(path) == 2
    with db.tx(path) as c:
        db.set_archived(c, "accounts", a["id"], True)
    assert version(path) == 3
    assert version(path) == max(r["id"] for r in audit(path))


@pytest.mark.contract("DB-AUDIT-012")
def test_noop_write_does_not_change_data_version(path):
    """DB-AUDIT-012: a no-op update/archive writes no audit row, so data_version is unchanged."""
    with db.tx(path) as c:
        a = make_account(c, "x")
    v = version(path)
    with db.tx(path) as c:
        db.update(c, "accounts", a["id"], {"name": "x"})
        db.set_archived(c, "accounts", a["id"], False)
    assert version(path) == v


@pytest.mark.contract("DB-AUDIT-013")
def test_export_all_shape(path, history):
    """DB-AUDIT-013: export_all has a key per data table, audit_log, exported_at and data_version."""
    with db.read(path) as r:
        out = db.export_all(r)
    assert {"accounts", "entries", "adjustments", "checkpoints", "audit_log", "exported_at", "data_version"} <= set(out)
    assert len(out["accounts"]) == 2 and len(out["entries"]) == 1
    assert out["data_version"] == version(path)
    assert re.match(r"\d{4}-\d{2}-\d{2}T", out["exported_at"])


@pytest.mark.contract("DB-AUDIT-013")
def test_export_all_on_empty_database(path):
    """DB-AUDIT-013: an empty database exports empty arrays and data_version 0."""
    with db.read(path) as r:
        out = db.export_all(r)
    assert [out[k] for k in ("accounts", "entries", "adjustments", "checkpoints", "audit_log")] == [[]] * 5
    assert out["data_version"] == 0


@pytest.mark.contract("DB-AUDIT-014")
def test_export_audit_log_is_oldest_first(path, history):
    """DB-AUDIT-014: export_all's audit_log is ascending by id, the reverse of audit_list."""
    with db.read(path) as r:
        ids = [x["id"] for x in db.export_all(r)["audit_log"]]
    assert ids == sorted(ids) and ids == [r["id"] for r in reversed(audit(path))]
