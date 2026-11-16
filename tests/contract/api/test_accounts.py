import pytest

BODY = {"name": "Checking", "kind": "checking", "start_balance": 100000, "start_date": "2026-01-15"}


def post(client, **patch):
    body = {**BODY, **patch}
    body = {k: v for k, v in body.items() if v is not ...}
    return client.post("/api/accounts", json=body)


@pytest.mark.contract("API-ACC-001")
def test_create_account_returns_row(client):
    """API-ACC-001: valid POST -> 200 with id, name, kind, note, archived, updated_at."""
    r = post(client)
    assert r.status_code == 200
    row = r.json()
    assert {"id", "name", "kind", "note", "archived", "updated_at"} <= set(row)
    assert row["name"] == "Checking" and row["kind"] == "checking" and row["note"] == ""
    assert not row["archived"] and isinstance(row["id"], int)


@pytest.mark.contract("API-ACC-002")
def test_starting_checkpoint_is_created(client, seed):
    """API-ACC-002: exactly one checkpoint is created with date == start_date and balance == start_balance."""
    a = post(client).json()
    cps = [c for c in seed.state()["checkpoints"] if c["account_id"] == a["id"]]
    assert len(cps) == 1 and cps[0]["date"] == "2026-01-15" and cps[0]["balance"] == 100000


@pytest.mark.contract("API-ACC-003")
def test_starting_checkpoint_note_is_empty(client, seed):
    """API-ACC-003: the starting checkpoint has an empty note (no stored 'Startstand' text)."""
    a = post(client).json()
    assert [c["note"] for c in seed.state()["checkpoints"] if c["account_id"] == a["id"]] == [""]


@pytest.mark.contract("API-ACC-004")
@pytest.mark.parametrize("patch", [{"name": ""}, {"kind": "bogus"}, {"start_date": "nope"}, {"start_balance": "x"}])
def test_invalid_create_persists_nothing(client, seed, patch):
    """API-ACC-004: when validation fails neither the account nor the checkpoint is stored."""
    assert post(client, **patch).status_code == 422
    s = seed.state()
    assert s["accounts"] == [] and s["checkpoints"] == [] and s["data_version"] == 0


@pytest.mark.contract("API-ACC-005")
def test_kind_defaults_to_checking(client):
    """API-ACC-005: omitting kind -> 'checking'."""
    assert post(client, kind=...).json()["kind"] == "checking"


@pytest.mark.contract("API-ACC-005")
@pytest.mark.parametrize("kind", ["checking", "savings", "custody", "credit_card", "cash", "other"])
def test_all_kinds_are_accepted(client, kind):
    """API-ACC-005: the six allowed kinds work."""
    assert post(client, kind=kind).json()["kind"] == kind


@pytest.mark.contract("API-ACC-005")
@pytest.mark.parametrize("kind", ["loan", "", "Checking"])
def test_invalid_kind_is_422_and_creates_nothing(client, seed, kind):
    """API-ACC-005: an invalid kind -> 422 validation_error on `kind`, nothing created."""
    r = post(client, kind=kind)
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert "kind" in {e["field"] for e in r.json()["params"]["errors"]}
    assert seed.state()["accounts"] == []


@pytest.mark.contract("API-ACC-006")
@pytest.mark.parametrize("missing", ["name", "start_balance", "start_date"])
def test_missing_required_field_is_422(client, missing):
    """API-ACC-006: a missing name/start_balance/start_date -> 422 validation_error."""
    r = post(client, **{missing: ...})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert missing in {e["field"] for e in r.json()["params"]["errors"]}


@pytest.mark.contract("API-ACC-006")
def test_empty_name_is_string_too_short(client):
    """API-ACC-006: an empty name reports string_too_short."""
    errs = post(client, name="").json()["params"]["errors"]
    assert ("name", "string_too_short") in {(e["field"], e["code"]) for e in errs}


@pytest.mark.contract("API-ACC-007")
@pytest.mark.parametrize("balance", [0, -250000, 1, 99999999999])
def test_start_balance_may_be_zero_or_negative(client, seed, balance):
    """API-ACC-007: any integer start_balance is accepted (zero, negative for credit cards)."""
    a = post(client, start_balance=balance).json()
    assert [c["balance"] for c in seed.state()["checkpoints"] if c["account_id"] == a["id"]] == [balance]


@pytest.mark.contract("API-ACC-008")
def test_state_shows_account_and_data_version_rises_by_two(client, seed):
    """API-ACC-008: the account and its checkpoint show up in /api/state; data_version grows by 2."""
    before = seed.state()["data_version"]
    a = post(client).json()
    s = seed.state()
    assert [x["id"] for x in s["accounts"]] == [a["id"]] and len(s["checkpoints"]) == 1
    assert s["data_version"] == before + 2


@pytest.mark.contract("API-ACC-009")
def test_comment_lands_on_the_account_create_audit_row_only(client):
    """API-ACC-009: the comment is stored on the account's create audit row, not on the checkpoint's."""
    a = post(client, comment="Erstes Konto").json()
    rows = client.get("/api/audit").json()
    acc_row = [r for r in rows if r["entity"] == "accounts" and r["entity_id"] == a["id"]][0]
    cp_row = [r for r in rows if r["entity"] == "checkpoints"][0]
    assert acc_row["action"] == "create" and acc_row["comment"] == "Erstes Konto"
    assert cp_row["comment"] == ""


@pytest.mark.contract("API-ACC-009")
def test_comment_is_not_stored_on_the_data_row(client, seed):
    """API-ACC-009: comment is not a column of the account."""
    post(client, comment="x")
    assert "comment" not in seed.state()["accounts"][0]


@pytest.mark.contract("API-ACC-001", "API-ACC-002")
def test_unicode_account_name_roundtrips(client, seed):
    """API-ACC-001: unicode names are stored and returned unchanged."""
    post(client, name="Spar-Konto äöü ß 日本語 😀")
    assert seed.state()["accounts"][0]["name"] == "Spar-Konto äöü ß 日本語 😀"
