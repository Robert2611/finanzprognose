"""GET /api/update/status and POST /api/update/request (contracts/api/update.md)."""
import json
import os

import pytest

HOST = {"schema": 1, "mode": "notify", "state": "idle", "current": "v1.0.0", "latest": "v1.1.0",
        "checked_at": "2026-11-24T10:00:00+01:00", "check_error": None, "target": None, "failed_version": None,
        "last_update": {"from": "v0.9.0", "to": "v1.0.0", "result": "success", "at": "2026-11-20T10:00:00+01:00"}}


@pytest.fixture
def upd(tmp_path):
    d = tmp_path / "updater"
    d.mkdir()
    (d / "status.json").write_text(json.dumps(HOST))
    return d


@pytest.fixture
def uclient(make_settings, make_client, upd, request):
    over = {"update_dir": str(upd), "app_version": "v1.0.0"}
    for m in request.node.iter_markers("app_settings"):
        over.update(m.kwargs)
    s = make_settings(**over)
    c = make_client(s)
    if s.app_password:
        c.auth = ("admin", s.app_password)
    return c


@pytest.mark.contract("API-UPD-001")
def test_status_shape(uclient):
    r = uclient.get("/api/update/status")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"enabled", "running_version", "host", "host_error", "update_available", "request_pending", "log_tail"}
    assert body["enabled"] is True and body["running_version"] == "v1.0.0" and body["update_available"] is True
    assert body["host"]["last_update"] == HOST["last_update"]  # keeps the key "from"
    assert set(body["host"]) == {"mode", "state", "current", "latest", "checked_at", "check_error", "target",
                                 "failed_version", "last_update"}


@pytest.mark.contract("API-UPD-001")
def test_status_not_configured(client):
    body = client.get("/api/update/status").json()
    assert body["enabled"] is False and body["host"] is None and body["running_version"] == "dev"


@pytest.mark.contract("API-UPD-002")
def test_request(uclient, upd):
    r = uclient.post("/api/update/request", json={"version": "v1.1.0"})
    assert r.status_code == 202 and r.json()["request_pending"] is True
    assert json.loads((upd / "request.json").read_text())["version"] == "v1.1.0"
    assert uclient.post("/api/update/request").status_code == 202  # no body: latest
    assert json.loads((upd / "request.json").read_text())["version"] is None


@pytest.mark.contract("API-UPD-003")
@pytest.mark.parametrize("version", ["latest", "1.1.0", "v1.1", "v1.1.0; reboot", 5])
def test_invalid_version(uclient, upd, version):
    r = uclient.post("/api/update/request", json={"version": version})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert not (upd / "request.json").exists()


@pytest.mark.contract("API-UPD-004")
def test_not_configured(client):
    r = client.post("/api/update/request", json={})
    assert r.status_code == 409 and r.json() == {"code": "updater_not_configured", "params": {}}


@pytest.mark.contract("API-UPD-004")
def test_in_progress(uclient, upd):
    (upd / "status.json").write_text(json.dumps(HOST | {"state": "updating", "target": "v1.1.0"}))
    r = uclient.post("/api/update/request", json={})
    assert r.status_code == 409 and r.json() == {"code": "update_in_progress", "params": {}}


@pytest.mark.contract("API-UPD-004")
def test_folder_not_writable(uclient, upd):
    os.rename(upd, str(upd) + "-gone")
    r = uclient.post("/api/update/request", json={})
    assert r.status_code == 503 and r.json() == {"code": "updater_unavailable", "params": {}}


@pytest.mark.contract("API-UPD-005")
@pytest.mark.app_settings(app_password="pw")
def test_behind_auth(make_client, settings, upd):
    anon = make_client(settings)
    assert anon.get("/api/update/status").status_code == 401
    assert anon.post("/api/update/request", json={}).status_code == 401
