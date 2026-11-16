"""Self-checks of the test infrastructure itself (not contract clauses)."""
import os
import sqlite3

import pytest


def test_apps_are_isolated(make_settings, make_client):
    a, b = make_settings(), make_settings()
    assert a.db_path != b.db_path and a.backup_dir != b.backup_dir
    ca, cb = make_client(a), make_client(b)
    ca.post("/api/accounts", json={"name": "A", "start_balance": 0, "start_date": "2026-01-01"})
    assert len(ca.get("/api/state").json()["accounts"]) == 1
    assert cb.get("/api/state").json()["accounts"] == []


def test_seed_standard_world(seed):
    w = seed.standard_world()
    assert {"giro", "tg", "salary", "rent", "saving", "trip"} <= set(w)
    assert len(seed.state()["entries"]) == 4


def test_nas_helpers(nas):
    assert nas.names() == []
    nas.put_marker()
    assert nas.names() == [".nas-marker"]
    nas.remove()
    assert not nas.path.exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_nas_read_only(nas):
    nas.make_read_only()
    with pytest.raises(PermissionError):
        (nas.path / "x").write_text("x")


@pytest.mark.app_settings(app_password="s3cret")
def test_password_setting_gates_anon_client(client, anon_client):
    assert anon_client.get("/api/state").status_code == 401
    assert client.get("/api/state").status_code == 200


def test_live_server_serves_the_app(live_server):
    import httpx
    assert httpx.get(live_server.url + "/healthz").json() == {"ok": True}
    assert "html" in httpx.get(live_server.url + "/").headers["content-type"]


def test_sqlite_view(client, db_path):
    from tests.contract.helpers.sqlite_view import integrity_check
    assert integrity_check(db_path) == "ok"
