import re

import pytest

BAD_ENTRY = {"name": "x", "kind": "once", "amount": 100, "start_date": "2026-01-01"}


def validation_errors(r):
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "validation_error"
    return body["params"]["errors"]


@pytest.fixture
def acc(seed):
    return seed.account("Giro")


@pytest.mark.contract("ERRENV-001")
def test_not_found_envelope_exact_for_account_update(client, seed):
    """ERRENV-001: exact body for a missing account."""
    r = client.put("/api/accounts/987654", json={"name": "x", "kind": "checking"})
    assert r.status_code == 404
    assert r.json() == {"code": "not_found", "params": {"entity": "accounts", "id": 987654}}


@pytest.mark.contract("ERRENV-001")
def test_not_found_envelope_for_revert(client):
    """ERRENV-001: reverting an unknown audit row -> 404 not_found with entity audit_log."""
    r = client.post("/api/audit/987654/revert")
    assert r.status_code == 404
    assert r.json() == {"code": "not_found", "params": {"entity": "audit_log", "id": 987654}}


@pytest.mark.contract("ERRENV-002")
def test_conflict_envelope(client, acc):
    """ERRENV-002: an optimistic-lock mismatch -> 409 {code: conflict, params: {}}."""
    r = client.put(f"/api/accounts/{acc['id']}", json={"name": "y", "kind": "checking", "expected_updated_at": "stale"})
    assert r.status_code == 409 and r.json() == {"code": "conflict", "params": {}}


@pytest.mark.contract("ERRENV-003")
def test_validation_envelope_lists_one_entry_per_field_error(client, acc):
    """ERRENV-003: {code: validation_error, params: {errors: [{field, code, params}, ...]}}."""
    r = client.post("/api/entries", json={**BAD_ENTRY, "account_id": acc["id"], "name": "", "interval_months": 0, "kind": "recurring"})
    errs = validation_errors(r)
    assert {e["field"] for e in errs} >= {"name", "interval_months"}
    for e in errs:
        assert set(e) == {"field", "code", "params"} and isinstance(e["params"], dict)


@pytest.mark.contract("ERRENV-004")
@pytest.mark.parametrize("body_patch,field,code,params", [
    ({"name": ""}, "name", "string_too_short", {"min_length": 1}),
    ({"name": "x" * 101}, "name", "string_too_long", {"max_length": 100}),
    ({"interval_months": 121, "kind": "recurring"}, "interval_months", "less_than_equal", {"le": 120}),
    ({"interval_months": 0, "kind": "recurring"}, "interval_months", "greater_than_equal", {"ge": 1}),
])
def test_builtin_constraint_codes_and_params(client, acc, body_patch, field, code, params):
    """ERRENV-004: built-in violations use Pydantic's machine type as code and scalar context as params."""
    errs = validation_errors(client.post("/api/entries", json={**BAD_ENTRY, "account_id": acc["id"], **body_patch}))
    match = [e for e in errs if e["field"] == field and e["code"] == code]
    assert match, errs
    assert match[0]["params"] == params or params.items() <= match[0]["params"].items()
    assert all(isinstance(v, (str, int, float, bool, type(None))) for v in match[0]["params"].values())


@pytest.mark.contract("ERRENV-005")
@pytest.mark.parametrize("patch,code", [
    ({"amount": 0}, "amount_zero"),
    ({"kind": "recurring", "start_date": "2026-03-01", "end_date": "2026-01-01"}, "end_before_start"),
])
def test_custom_validator_codes_have_empty_params(client, acc, patch, code):
    """ERRENV-005: model-level failures report the short code with empty params."""
    errs = validation_errors(client.post("/api/entries", json={**BAD_ENTRY, "account_id": acc["id"], **patch}))
    match = [e for e in errs if e["code"] == code]
    assert match and match[0]["params"] == {}


@pytest.mark.contract("ERRENV-005")
def test_transfer_same_account_code(client, acc):
    """ERRENV-005: transfer_same_account is reported by code."""
    errs = validation_errors(client.post("/api/entries", json={**BAD_ENTRY, "account_id": acc["id"], "to_account_id": acc["id"]}))
    assert "transfer_same_account" in {e["code"] for e in errs}


@pytest.mark.contract("ERRENV-006")
def test_field_is_the_plain_field_name(client, acc):
    """ERRENV-006: `field` is the offending field's name (e.g. name, interval_months)."""
    errs = validation_errors(client.post("/api/entries", json={**BAD_ENTRY, "account_id": acc["id"], "name": "", "kind": "recurring", "interval_months": 500}))
    assert {"name", "interval_months"} <= {e["field"] for e in errs}


@pytest.mark.contract("ERRENV-007")
def test_unknown_table_envelope_passes_through(client):
    """ERRENV-007: unknown_table -> 404 with the route's own {code, params} body unchanged."""
    r = client.post("/api/widgets", json={})
    assert r.status_code == 404 and r.json() == {"code": "unknown_table", "params": {"table": "widgets"}}


@pytest.mark.contract("ERRENV-007")
def test_ref_not_found_envelope_passes_through(client):
    """ERRENV-007: ref_not_found -> 422 with {code, params: {field, id}}."""
    r = client.post("/api/entries", json={**BAD_ENTRY, "account_id": 424242})
    assert r.status_code == 422
    assert r.json() == {"code": "ref_not_found", "params": {"field": "account_id", "id": 424242}}


@pytest.mark.contract("ERRENV-008")
@pytest.mark.parametrize("method,url", [("get", "/api/does-not-exist"), ("post", "/healthz"), ("delete", "/api/state")])
def test_plain_http_errors_use_detail_shape(client, method, url):
    """ERRENV-008: framework errors (404/405) come back as {"detail": ...} without a code."""
    r = getattr(client, method)(url)
    assert r.status_code in (404, 405)
    body = r.json()
    assert "detail" in body and "code" not in body


@pytest.mark.contract("ERRENV-009")
def test_sampled_error_responses_contain_no_german_text(client, acc):
    """ERRENV-009: sampled handled error bodies contain no German words or umlauts."""
    bodies = [
        client.put("/api/accounts/987654", json={"name": "x", "kind": "checking"}).text,
        client.put(f"/api/accounts/{acc['id']}", json={"name": "y", "kind": "checking", "expected_updated_at": "stale"}).text,
        client.post("/api/entries", json={**BAD_ENTRY, "account_id": acc["id"], "amount": 0}).text,
        client.post("/api/entries", json={**BAD_ENTRY, "account_id": 424242}).text,
        client.post("/api/widgets", json={}).text,
        client.post("/api/audit/987654/revert").text,
    ]
    for text in bodies:
        assert not re.search(r"[äöüÄÖÜß]", text), text
        assert not re.search(r"\b(nicht|Betrag|Konto|Fehler|ungültig|gefunden|Datensatz|bitte)\b", text, re.I), text
