import base64

import pytest


def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


SECRET = "s3cret"
gated = pytest.mark.app_settings(app_password=SECRET)


@pytest.mark.contract("AUTH-001")
@gated
@pytest.mark.parametrize("method,url", [("get", "/api/state"), ("get", "/api/forecast"), ("get", "/api/audit"),
                                        ("get", "/api/backup/status"), ("get", "/api/export"), ("post", "/api/backup/run")])
def test_requests_without_credentials_get_401_with_challenge(anon_client, method, url):
    """AUTH-001: with a password set, an unauthenticated request returns 401 + WWW-Authenticate Basic realm."""
    r = getattr(anon_client, method)(url)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == 'Basic realm="Finanzprognose"'


@pytest.mark.contract("AUTH-001")
@gated
def test_rejected_request_does_not_run_the_route(anon_client):
    """AUTH-001: the route does not run for a rejected request (nothing gets created)."""
    r = anon_client.post("/api/accounts", json={"name": "x", "start_balance": 0, "start_date": "2026-01-01"})
    assert r.status_code == 401
    assert anon_client.get("/api/state", headers=basic("admin", SECRET)).json()["accounts"] == []


@pytest.mark.contract("AUTH-002")
def test_without_password_everything_is_open(anon_client):
    """AUTH-002: with an empty password, requests succeed without credentials."""
    assert anon_client.get("/api/state").status_code == 200
    assert anon_client.get("/").status_code == 200
    assert anon_client.post("/api/accounts", json={"name": "x", "start_balance": 0, "start_date": "2026-01-01"}).status_code == 200


@pytest.mark.contract("AUTH-002")
def test_without_password_credentials_are_not_required_nor_harmful(anon_client):
    """AUTH-002: sending credentials to an open instance does not break the request."""
    assert anon_client.get("/api/state", headers=basic("anyone", "anything")).status_code == 200


@pytest.mark.contract("AUTH-003")
@gated
def test_healthz_is_always_open(anon_client):
    """AUTH-003: /healthz answers 200 {"ok": true} without credentials even when a password is set."""
    r = anon_client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


@pytest.mark.contract("AUTH-004")
@gated
def test_correct_credentials_reach_the_route(anon_client):
    """AUTH-004: the default user 'admin' with the right password is let through."""
    r = anon_client.get("/api/state", headers=basic("admin", SECRET))
    assert r.status_code == 200 and "accounts" in r.json()


@pytest.mark.contract("AUTH-004")
@pytest.mark.app_settings(app_password=SECRET, app_user="robert")
def test_configured_username_is_honoured(anon_client):
    """AUTH-004: APP_USER is configurable; the configured user works and the default one does not."""
    assert anon_client.get("/api/state", headers=basic("robert", SECRET)).status_code == 200
    assert anon_client.get("/api/state", headers=basic("admin", SECRET)).status_code == 401


@pytest.mark.contract("AUTH-004")
@pytest.mark.app_settings(app_password="pässwörd:ü 日本", app_user="üser")
def test_unicode_credentials_and_colon_in_password(anon_client):
    """AUTH-004: non-ASCII user/password and a colon inside the password authenticate correctly."""
    assert anon_client.get("/api/state", headers=basic("üser", "pässwörd:ü 日本")).status_code == 200


@pytest.mark.contract("AUTH-005", "AUTH-006")
@gated
@pytest.mark.parametrize("user,password", [("admin", "wrong"), ("root", SECRET), ("ADMIN", SECRET), ("admin", SECRET + "x"),
                                           ("admin", SECRET[:-1]), ("admin", ""), ("", SECRET), ("", "")])
def test_wrong_credentials_are_rejected(anon_client, user, password):
    """AUTH-005/006: wrong username or password -> 401 (both must match; comparison is case-sensitive)."""
    assert anon_client.get("/api/state", headers=basic(user, password)).status_code == 401


@pytest.mark.contract("AUTH-005")
@gated
@pytest.mark.parametrize("header", [
    "Basic", "Basic ", "Basic !!!not-base64!!!", "Basic " + base64.b64encode(b"adminonly").decode(),
    "Bearer " + SECRET, "Digest username=admin", SECRET, "basic", "Token abc",
])
def test_malformed_or_non_basic_authorization_is_rejected(anon_client, header):
    """AUTH-005: malformed Authorization headers and other schemes return 401."""
    assert anon_client.get("/api/state", headers={"Authorization": header}).status_code == 401


@pytest.mark.contract("AUTH-007")
@gated
@pytest.mark.parametrize("url", ["/", "/index.html", "/core.js", "/style.css"])
def test_static_assets_are_gated_too(anon_client, url):
    """AUTH-007: the SPA's static files require credentials when a password is set."""
    assert anon_client.get(url).status_code == 401
    assert anon_client.get(url, headers=basic("admin", SECRET)).status_code in (200, 304)
