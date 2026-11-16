import json
import re
from datetime import date

import pytest


@pytest.mark.contract("API-EXPORT-001")
def test_export_has_all_sections(client, seed):
    """API-EXPORT-001: 200 JSON with the four tables, audit_log, exported_at and data_version."""
    seed.standard_world()
    r = client.get("/api/export")
    assert r.status_code == 200
    body = r.json()
    assert {"accounts", "entries", "adjustments", "checkpoints", "audit_log", "exported_at", "data_version"} <= set(body)
    assert len(body["accounts"]) == 2 and len(body["entries"]) == 4


@pytest.mark.contract("API-EXPORT-001")
def test_export_of_empty_database(client):
    """API-EXPORT-001: a fresh DB exports empty arrays and data_version 0."""
    body = client.get("/api/export").json()
    assert [body[k] for k in ("accounts", "entries", "adjustments", "checkpoints", "audit_log")] == [[]] * 5
    assert body["data_version"] == 0 and body["exported_at"]


@pytest.mark.contract("API-EXPORT-002")
def test_export_is_an_attachment_named_after_today(client):
    """API-EXPORT-002: Content-Disposition attachment; filename=finanzen_export_<today>.json."""
    cd = client.get("/api/export").headers["content-disposition"]
    assert cd.startswith("attachment")
    assert f'finanzen_export_{date.today().isoformat()}.json' in cd


@pytest.mark.contract("API-EXPORT-003")
def test_export_includes_archived_rows_with_integer_cents(client, seed):
    """API-EXPORT-003: all rows (archived included), money as integer cents."""
    w = seed.standard_world()
    client.post(f"/api/entries/{w['trip']['id']}/archive", json={})
    body = client.get("/api/export").json()
    assert len(body["entries"]) == 4
    assert [e["archived"] for e in body["entries"] if e["id"] == w["trip"]["id"]] in ([1], [True])
    assert all(type(e["amount"]) is int for e in body["entries"])
    assert sorted(a["id"] for a in body["accounts"]) == sorted(a["id"] for a in seed.state()["accounts"])


@pytest.mark.contract("API-EXPORT-004")
def test_export_audit_log_is_oldest_first(client, seed):
    """API-EXPORT-004: audit_log is chronological, the reverse of GET /api/audit."""
    seed.standard_world()
    exported = [r["id"] for r in client.get("/api/export").json()["audit_log"]]
    listed = [r["id"] for r in client.get("/api/audit?limit=1000").json()]
    assert exported == sorted(exported) and exported == list(reversed(listed))


@pytest.mark.contract("API-EXPORT-005")
def test_export_data_version_equals_current_counter(client, seed):
    """API-EXPORT-005: data_version in the export equals the current change counter."""
    seed.standard_world()
    assert client.get("/api/export").json()["data_version"] == seed.state()["data_version"]


@pytest.mark.contract("API-EXPORT-001", "API-EXPORT-003")
def test_export_is_valid_json_with_unicode(client, seed):
    """API-EXPORT-001/003: the body is valid JSON and keeps unicode names intact."""
    seed.account("Größe 日本語 😀")
    parsed = json.loads(client.get("/api/export").content.decode("utf-8"))
    assert parsed["accounts"][0]["name"] == "Größe 日本語 😀"
