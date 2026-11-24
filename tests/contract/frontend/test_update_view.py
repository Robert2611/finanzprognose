"""The Version view and the update pill (contracts/frontend/update-view.md)."""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import norm

HOST = {"schema": 1, "mode": "notify", "state": "idle", "current": "v1.0.0", "latest": "v1.1.0",
        "checked_at": "2026-11-24T10:00:00+01:00", "check_error": None, "target": None, "failed_version": None,
        "last_update": {"from": "v0.9.0", "to": "v1.0.0", "result": "success", "at": "2026-11-20T10:00:00+01:00"}}


@pytest.fixture
def upd(tmp_path):
    d = tmp_path / "updater"
    d.mkdir()
    return d


@pytest.fixture
def settings(make_settings, upd, request):
    """The primary app with an update folder and version v1.0.0 (overridable with @pytest.mark.app_settings)."""
    over = {"update_dir": str(upd), "app_version": "v1.0.0"}
    for m in request.node.iter_markers("app_settings"):
        over.update(m.kwargs)
    return make_settings(**over)


def host(upd, **changes):
    (upd / "status.json").write_text(json.dumps(HOST | changes))


def pill(page):
    return page.locator("button#updatePill")


@pytest.mark.contract("FE-UPDATE-001")
def test_pill_hidden_when_up_to_date(app_page, upd):
    host(upd, latest="v1.0.0")
    page = app_page.open()
    expect(page.locator("button#backupPill")).not_to_have_text("Sicherung …")
    expect(pill(page)).to_be_hidden()


@pytest.mark.contract("FE-UPDATE-001")
def test_pill_shows_an_available_update_and_opens_the_view(app_page, upd):
    host(upd)
    page = app_page.open()
    expect(pill(page)).to_have_text("Update verfügbar: v1.1.0")
    expect(pill(page)).to_have_class(re.compile(r"\bwarn\b"))
    pill(page).click()
    assert page.evaluate("location.hash") == "#version"
    expect(page.locator("#main h2")).to_have_text("Version")


@pytest.mark.contract("FE-UPDATE-001")
@pytest.mark.parametrize("changes, text, cls", [
    ({"failed_version": "v1.1.0", "last_update": HOST["last_update"] | {"to": "v1.1.0", "from": "v1.0.0", "result": "rolled_back"}},
     "Update auf v1.1.0 fehlgeschlagen", "err"),
    ({"state": "updating", "target": "v1.1.0"}, "Update läuft …", "warn"),
])
def test_pill_states(app_page, upd, changes, text, cls):
    host(upd, **changes)
    page = app_page.open()
    expect(pill(page)).to_have_text(text)
    expect(pill(page)).to_have_class(re.compile(rf"\b{cls}\b"))


@pytest.mark.contract("FE-UPDATE-002")
def test_view_shows_versions_mode_and_last_update(app_page, upd):
    host(upd)
    page = app_page.open("version")
    main = page.locator("#main")
    expect(main.locator(".running-version")).to_have_text("v1.0.0")
    text = norm(main.inner_text())
    assert "Neueste Version" in text and "v1.1.0" in text and "geprüft" in text
    assert "nur anzeigen" in text
    assert "v0.9.0 → v1.0.0, erfolgreich" in text


@pytest.mark.contract("FE-UPDATE-003")
@pytest.mark.app_settings(update_dir="")
def test_not_configured_banner(app_page):
    page = app_page.open("version")
    expect(page.locator("#main .banner.warn")).to_contain_text("nicht eingerichtet")
    expect(page.locator("#main .running-version")).to_have_text("v1.0.0")
    expect(pill(page)).to_be_hidden()


@pytest.mark.contract("FE-UPDATE-003")
def test_host_and_check_errors_are_shown_in_german(app_page, upd):
    page = app_page.open("version")
    expect(page.locator("#main .banner.warn")).to_contain_text("noch kein Status")
    host(upd, check_error="pull_failed")
    page.reload()
    expect(page.locator("#main .banner.warn")).to_contain_text("ghcr.io nicht erreichbar")


@pytest.mark.contract("FE-UPDATE-004")
def test_cancel_sends_nothing(app_page, upd):
    host(upd)
    page = app_page.open("version")
    page.get_by_role("button", name="Jetzt auf v1.1.0 aktualisieren").click()
    dlg = page.locator("dialog[open]")
    expect(dlg).to_contain_text("v1.1.0")
    dlg.get_by_role("button", name="Abbrechen").click()
    expect(dlg).to_have_count(0)
    assert not (upd / "request.json").exists()


@pytest.mark.contract("FE-UPDATE-004", "FE-UPDATE-005")
def test_confirm_requests_the_update_and_reloads_when_the_host_is_done(app_page, upd):
    host(upd)
    page = app_page.open("version")
    page.get_by_role("button", name="Jetzt auf v1.1.0 aktualisieren").click()
    with page.expect_request(lambda r: r.url.endswith("/api/update/request") and r.method == "POST") as req:
        page.locator("dialog[open]").get_by_role("button", name="Aktualisieren").click()
    assert req.value.post_data_json == {"version": "v1.1.0"}
    expect(page.locator("#main .update-busy")).to_contain_text("Update läuft")
    assert json.loads((upd / "request.json").read_text())["version"] == "v1.1.0"
    # the host takes the request and finishes the run (here without a version change)
    (upd / "request.json").unlink()
    with page.expect_event("load", timeout=20000):
        host(upd, checked_at="2026-11-24T10:15:00+01:00",
             last_update=HOST["last_update"] | {"from": "v1.0.0", "to": "v1.1.0", "result": "rolled_back"},
             failed_version="v1.1.0")
    expect(page.locator("#main .banner.err")).to_contain_text("Update auf v1.1.0 fehlgeschlagen")


@pytest.mark.contract("FE-UPDATE-005")
def test_polling_survives_the_server_being_down(app_page, upd):
    host(upd, state="updating", target="v1.1.0")
    page = app_page.open("version")
    expect(page.locator("#main .update-busy")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("aktualisieren|versuchen"))).to_have_count(0)
    page.route("**/api/update/status", lambda r: r.abort())  # the app restarts
    page.wait_for_timeout(4000)
    page.unroute("**/api/update/status")
    with page.expect_event("load", timeout=20000):
        host(upd, checked_at="2026-11-24T10:15:00+01:00")


@pytest.mark.contract("FE-UPDATE-006")
def test_failed_update_banner_and_retry_button(app_page, upd):
    host(upd, failed_version="v1.1.0",
         last_update={"from": "v1.0.0", "to": "v1.1.0", "result": "rollback_failed", "at": "2026-11-24T09:00:00+01:00"})
    page = app_page.open("version")
    expect(page.locator("#main .banner.err")).to_contain_text("auch das Zurückrollen ist fehlgeschlagen")
    expect(page.get_by_role("button", name="Erneut versuchen: v1.1.0")).to_be_visible()


@pytest.mark.contract("FE-UPDATE-007")
def test_log_tail_in_a_collapsed_section(app_page, upd):
    host(upd)
    (upd / "last-update.log").write_text("==> Pulling\n==> Done. Running v1.0.0\n")
    page = app_page.open("version")
    details = page.locator("#main details")
    expect(details.locator("summary")).to_have_text("Ausgabe des letzten Updates")
    assert details.get_attribute("open") is None
    details.locator("summary").click()
    expect(details.locator("pre")).to_contain_text("Done. Running v1.0.0")
