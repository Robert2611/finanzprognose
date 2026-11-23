"""B-019: reverting a revert row is a redo (DB-AUDIT-015)."""
import pytest

from app import db
from tests.contract.backend.conftest import make_account
from tests.contract.helpers.timing import next_ms


def audit(path, **kw):
    with db.read(path) as r:
        return db.audit_list(r, **kw)


def revert(path, audit_id):
    next_ms()
    with db.tx(path) as c:
        return db.revert(c, audit_id)


@pytest.fixture
def renamed(path):
    """Account 'A' renamed to 'B'; returns (account id, id of the update row)."""
    with db.tx(path) as c:
        a = make_account(c, "A")
    next_ms()
    with db.tx(path) as c:
        db.update(c, "accounts", a["id"], {"name": "B"})
    return a["id"], audit(path)[0]["id"]


@pytest.mark.contract("DB-AUDIT-015")
def test_reverting_an_undo_restores_the_undone_change(path, renamed):
    """DB-AUDIT-015: undo (B -> A), then revert the undo row -> B again, as a new revert row."""
    acc, upd = renamed
    assert revert(path, upd)["name"] == "A"
    undo = audit(path)[0]
    assert revert(path, undo["id"])["name"] == "B"
    redo = audit(path)[0]
    assert redo["action"] == "revert" and redo["reverts_id"] == undo["id"]
    assert redo["before"]["name"] == "A" and redo["after"]["name"] == "B"
    assert [r["action"] for r in audit(path, entity="accounts", entity_id=acc)] == ["revert", "revert", "update", "create"]


@pytest.mark.contract("DB-AUDIT-015")
def test_a_chain_alternates_and_never_rewrites_history(path, renamed):
    """DB-AUDIT-015: undo, redo, undo the redo -> A; every step is appended, earlier rows stay untouched."""
    acc, upd = renamed
    revert(path, upd)
    snapshot = audit(path)
    revert(path, audit(path)[0]["id"])               # redo  -> B
    assert revert(path, audit(path)[0]["id"])["name"] == "A"   # undo the redo -> A
    assert audit(path)[2:] == snapshot


@pytest.mark.contract("DB-AUDIT-015")
def test_redo_of_an_undone_create_makes_the_record_active_again(path):
    """DB-AUDIT-015: undoing a create archives the record; reverting that undo restores it."""
    with db.tx(path) as c:
        a = make_account(c, "A")
    create = audit(path)[0]
    assert revert(path, create["id"])["archived"] == 1
    assert revert(path, audit(path)[0]["id"])["archived"] == 0
