import pytest

from app import db


@pytest.mark.contract("DB-ERR-001")
def test_api_error_carries_code_and_params():
    """DB-ERR-001: ApiError('x', a=1, b=2) has .code 'x' and .params {'a': 1, 'b': 2}."""
    e = db.ApiError("x", a=1, b=2)
    assert e.code == "x" and e.params == {"a": 1, "b": 2}


@pytest.mark.contract("DB-ERR-001")
def test_api_error_without_params_has_empty_params():
    """DB-ERR-001: no keyword arguments means empty params."""
    assert db.ApiError("x").params == {}


@pytest.mark.contract("DB-ERR-002")
@pytest.mark.parametrize("cls", ["NotFound", "Conflict"])
def test_specific_errors_are_api_errors(cls):
    """DB-ERR-002: NotFound and Conflict subclass ApiError (and Exception)."""
    klass = getattr(db, cls)
    assert issubclass(klass, db.ApiError) and issubclass(klass, Exception)
    with pytest.raises(db.ApiError):
        raise klass("code")


@pytest.mark.contract("DB-ERR-003")
def test_not_found_params_example():
    """DB-ERR-003: NotFound('not_found', entity='accounts', id=99) exposes code and params."""
    e = db.NotFound("not_found", entity="accounts", id=99)
    assert e.code == "not_found" and e.params == {"entity": "accounts", "id": 99}


@pytest.mark.contract("DB-ERR-004")
def test_conflict_has_code_conflict_and_no_params(path):
    """DB-ERR-004: the optimistic-lock Conflict has code 'conflict' and no params."""
    from tests.contract.backend.conftest import make_account
    with db.tx(path) as c:
        a = make_account(c, "x")
    with pytest.raises(db.Conflict) as ei:
        with db.tx(path) as c:
            db.update(c, "accounts", a["id"], {"name": "y"}, expected_updated_at="stale")
    assert ei.value.code == "conflict" and ei.value.params == {}


@pytest.mark.contract("DB-ERR-005")
@pytest.mark.parametrize("make", [lambda: db.ApiError("some_code", a=1), lambda: db.NotFound("not_found", entity="x", id=1),
                                  lambda: db.Conflict("conflict")])
def test_exception_message_is_the_code(make):
    """DB-ERR-005: str(exception) equals the code (no human text)."""
    e = make()
    assert str(e) == e.code
