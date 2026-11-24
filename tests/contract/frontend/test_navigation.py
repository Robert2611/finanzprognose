import pytest
from playwright.sync_api import expect

NAV = [("prognose", "Prognose"), ("buchungen", "Buchungen"), ("konten", "Konten & Ist-Stände"),
       ("verlauf", "Verlauf"), ("sicherung", "Sicherung"), ("version", "Version")]
HEADINGS = {"buchungen": "Buchungen", "konten": "Konten & Ist-Stände", "verlauf": "Änderungsverlauf", "sicherung": "Sicherung",
            "version": "Laufende Version"}


@pytest.fixture
def one_account(app_page):
    app_page.seed.account("Giro", 100000, "2026-01-15")
    return app_page


@pytest.mark.contract("FE-NAV-001")
def test_initial_load_fetches_state_and_renders_forecast(one_account):
    """FE-NAV-001: on load the app fetches /api/state and renders the initial view (prognose by default)."""
    page = one_account.page
    with page.expect_response(lambda r: r.url.endswith("/api/state") and r.status == 200):
        page.goto("/")
    expect(page.locator("#ftable")).to_be_visible()
    expect(page.locator("#nav button[data-view=prognose]")).to_have_class("active")


@pytest.mark.contract("FE-NAV-001")
def test_initial_view_comes_from_the_hash(one_account):
    """FE-NAV-001: the initial view is taken from location.hash."""
    page = one_account.open("konten")
    expect(page.locator("#main")).to_contain_text("Konten & Ist-Stände")
    expect(page.locator("#nav button[data-view=konten]")).to_have_class("active")


@pytest.mark.contract("FE-NAV-002", "E2E-ONBOARD-007")
def test_header_shows_brand_six_nav_buttons_and_pill(app_page):
    """FE-NAV-002: header has the brand, the six nav buttons with exact labels, and the backup pill."""
    page = app_page.open()
    expect(page.locator("header .brand")).to_have_text("Finanzprognose")
    buttons = page.locator("#nav button")
    expect(buttons).to_have_count(6)
    assert [(b.get_attribute("data-view"), b.inner_text().strip()) for b in buttons.all()] == NAV
    expect(page.locator("button#backupPill.pill")).to_be_visible()
    assert page.locator("main#main").count() == 1 and page.locator("div#toast").count() == 1


@pytest.mark.contract("FE-NAV-003")
@pytest.mark.parametrize("view", list(HEADINGS))
def test_clicking_a_nav_button_sets_hash_and_renders_the_view(one_account, view):
    """FE-NAV-003: a nav click sets location.hash and renders that view into #main."""
    page = one_account.open()
    page.locator(f'#nav button[data-view="{view}"]').click()
    expect(page.locator("#main")).to_contain_text(HEADINGS[view])
    assert page.evaluate("location.hash") == f"#{view}"


@pytest.mark.contract("FE-NAV-004")
def test_only_the_current_nav_button_is_active(one_account):
    """FE-NAV-004: the button whose data-view is the current view has class 'active'; no other does."""
    page = one_account.open()
    for view, _ in NAV[1:]:
        page.locator(f'#nav button[data-view="{view}"]').click()
        expect(page.locator(f'#nav button[data-view="{view}"]')).to_have_class("active")
        assert page.locator("#nav button.active").count() == 1


@pytest.mark.contract("FE-NAV-005")
def test_hash_change_and_history_switch_the_view(one_account):
    """FE-NAV-005: changing location.hash (manually or via back/forward) switches the view."""
    page = one_account.open()
    page.evaluate("location.hash = '#verlauf'")
    expect(page.locator("#main")).to_contain_text("Änderungsverlauf")
    page.locator('#nav button[data-view="konten"]').click()
    expect(page.locator("#main")).to_contain_text("Konten & Ist-Stände")
    page.go_back()
    expect(page.locator("#main")).to_contain_text("Änderungsverlauf")
    expect(page.locator("#nav button[data-view=verlauf]")).to_have_class("active")
    page.go_forward()
    expect(page.locator("#main")).to_contain_text("Konten & Ist-Stände")


@pytest.mark.contract("FE-NAV-006")
@pytest.mark.parametrize("hash_", ["", "nonsense", "PROGNOSE-X", "forecast"])
def test_unknown_or_empty_hash_shows_the_forecast(one_account, hash_):
    """FE-NAV-006: an unknown/empty hash renders the forecast view."""
    page = one_account.open(hash_)
    expect(page.locator("#ftable")).to_be_visible()


@pytest.mark.contract("FE-NAV-007")
def test_view_render_failure_shows_an_error_banner_not_a_blank_shell(one_account):
    """FE-NAV-007: if a view fails while rendering, #main shows a .banner.err and the shell (nav) stays usable."""
    page = one_account.page
    page.route("**/api/forecast*", lambda r: r.fulfill(status=500, content_type="application/json", body='{"detail":"render kaputt"}'))
    page.goto("/")
    expect(page.locator("#main .banner.err")).to_be_visible()
    expect(page.locator("#nav button")).to_have_count(6)
    page.locator('#nav button[data-view="konten"]').click()
    expect(page.locator("#main")).to_contain_text("Konten & Ist-Stände")


@pytest.mark.contract("FE-NAV-008", "E2E-AUTH-009")
def test_failed_initial_state_load_shows_an_error_banner(app_page):
    """FE-NAV-008: if /api/state fails at start-up, #main shows a .banner.err with the error message."""
    page = app_page.page
    page.route("**/api/state", lambda r: r.fulfill(status=500, content_type="application/json", body='{"detail":"Datenbank kaputt"}'))
    page.goto("/")
    banner = page.locator("#main .banner.err")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("Datenbank kaputt")


@pytest.mark.contract("FE-NAV-008", "E2E-AUTH-009")
def test_unreachable_backend_shows_an_error_banner(app_page):
    """FE-NAV-008: with the backend unreachable (/api aborted) #main shows an error banner instead of a blank page."""
    page = app_page.page
    page.route("**/api/**", lambda r: r.abort())
    page.goto("/")
    expect(page.locator("#main .banner.err")).to_be_visible()


@pytest.mark.contract("FE-NAV-009")
def test_refresh_reloads_state_and_rerenders_the_current_view(app_page):
    """FE-NAV-009: refresh() reloads state and re-renders the current view (new data appears without a page reload)."""
    page = app_page.open("konten")
    expect(page.locator("#main")).to_contain_text("Noch keine Konten.")
    app_page.seed.account("Neu per API")
    page.evaluate("async () => (await import('/core.js')).refresh()")
    expect(page.locator("#main")).to_contain_text("Neu per API")
    assert page.evaluate("location.hash") == "#konten"


@pytest.mark.contract("FE-NAV-009")
def test_saving_in_a_dialog_refreshes_the_view(app_page):
    """FE-NAV-009: after a create via the UI the list reflects it without a manual reload."""
    page = app_page.open("konten")
    page.get_by_role("button", name="+ Neues Konto").click()
    dlg = page.locator("dialog")
    dlg.locator('[name="name"]').fill("Frisch")
    dlg.locator('[name="start_balance"], [name="balance"]').first.fill("10,00")
    dlg.locator("button.primary").click()
    expect(page.locator(".cards")).to_contain_text("Frisch")


@pytest.mark.contract("FE-NAV-010")
def test_backup_pill_opens_the_backup_view(one_account):
    """FE-NAV-010: the backup pill is a nav control (data-view=sicherung) that opens the backup view."""
    page = one_account.open()
    pill = page.locator("button#backupPill")
    assert pill.get_attribute("data-view") == "sicherung"
    pill.click()
    expect(page.locator("#main")).to_contain_text("Sicherung")
    assert page.evaluate("location.hash") == "#sicherung"


@pytest.mark.contract("FE-NAV-011")
def test_slow_forecast_does_not_clobber_the_view_navigated_to(one_account):
    """FE-NAV-011: leaving the forecast while its data loads: the late response neither errors nor overwrites the new view."""
    page = one_account.open("verlauf")
    expect(page.locator("#main")).to_contain_text("Änderungsverlauf")
    held = []
    page.route("**/api/forecast*", lambda r: held.append(r))
    page.locator('#nav button[data-view="prognose"]').click()
    expect(page.locator("#main #chart")).to_have_count(1)      # skeleton is up, data request is held
    page.locator('#nav button[data-view="verlauf"]').click()
    expect(page.locator("#main")).to_contain_text("Änderungsverlauf")
    assert len(held) == 1
    with page.expect_response("**/api/forecast*"):
        held[0].continue_()
    page.wait_for_timeout(300)                                   # let the stale render run
    expect(page.locator("#main")).to_contain_text("Änderungsverlauf")
    expect(page.locator("#main .banner.err")).to_have_count(0)
