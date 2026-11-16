import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import field, put_value


@pytest.mark.contract("E2E-AUTH-006")
@pytest.mark.app_settings(app_password="s3cret", app_user="admin")
@pytest.mark.browser_context(http_credentials={"username": "admin", "password": "s3cret"})
def test_spa_loads_after_basic_auth_credentials(page, seed_live):
    """E2E-AUTH-006: with valid Basic credentials the SPA loads and the Prognose view renders."""
    seed_live.account("Giro", 100000, "2026-01-15")
    page.goto("/")
    expect(page.locator("header .brand")).to_have_text("Finanzprognose")
    expect(page.locator("#ftable")).to_be_visible()


@pytest.mark.contract("E2E-AUTH-006")
@pytest.mark.app_settings(app_password="s3cret")
def test_spa_is_not_served_without_credentials(browser, live_server):
    """E2E-AUTH-006/AUTH-007: without credentials the browser gets 401 and the SPA does not render."""
    ctx = browser.new_context(base_url=live_server.url)
    page = ctx.new_page()
    resp = page.goto("/")
    assert resp.status == 401
    assert page.locator("header .brand").count() == 0
    ctx.close()


@pytest.mark.contract("E2E-AUTH-007", "FE-NAV-001")
def test_data_created_in_the_ui_survives_a_reload(app_page):
    """E2E-AUTH-007: accounts and bookings created in the UI are still there after a reload (state comes from the server)."""
    page = app_page.open("konten")
    page.get_by_role("button", name="+ Neues Konto").click()
    dlg = page.locator("dialog")
    put_value(dlg, "Name", "Giro")
    put_value(dlg, "Aktueller Kontostand", "1.000,00")
    put_value(dlg, "Stand vom (abends)", "2026-01-15")
    dlg.locator("button.primary").click()
    expect(page.locator(".cards")).to_contain_text("Giro")
    page.locator('#nav button[data-view="buchungen"]').click()
    page.get_by_role("button", name="+ Neue Buchung").click()
    dlg = page.locator("dialog")
    put_value(dlg, "Bezeichnung", "Miete")
    put_value(dlg, "Betrag (positiv eingeben)", "1.200,00")
    dlg.locator("button.primary").click()
    expect(page.locator("#main table")).to_contain_text("Miete")
    page.reload()
    expect(page.locator("#main table")).to_contain_text("Miete")
    page.locator('#nav button[data-view="konten"]').click()
    expect(page.locator(".cards")).to_contain_text("Giro")
    assert page.evaluate("() => [localStorage.length, sessionStorage.length]") == [0, 0]
