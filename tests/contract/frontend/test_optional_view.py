"""B-029: optional bookings in the booking dialogs and lists, the forecast and the Verlauf (browser tests)."""
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, field, norm, put_value, show_balance

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)      # 2026-01-20 12:00 Berlin


def open_view(app_page, hash_=""):
    app_page.page.clock.install(time=NOW)
    return app_page.open(hash_)


def row(page, ym):
    return page.locator("#ftable tr.clickable").filter(has_text=call(page, "fMonth", ym)).first


def select(page, ym):
    row(page, ym).click()
    expect(page.locator("#fdetail h2")).to_have_text(call(page, "fMonth", ym))


def total(page, ym):
    return norm(row(page, ym).locator("td b").inner_text())


def panel(page):
    return page.locator("#main .optional-panel")


def box(page, name):
    return panel(page).locator("label.opt-item").filter(has_text=name).locator("input[type=checkbox]")


@pytest.fixture
def world(app_page):
    """Giro 1.000 € with a salary; optional: a second holiday in March and a gym membership from February."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    s.entry(giro["id"], "Gehalt", 300000, "2026-01-31")
    trip = s.entry(giro["id"], "Zweiter Urlaub", -250000, "2026-03-10", kind="once", optional=True)
    gym = s.entry(giro["id"], "Fitnessstudio", -4000, "2026-02-01", optional=True)
    return {"s": s, "giro": giro, "trip": trip, "gym": gym}


# ---------------------------------------------------------------------------- dialogs and lists

@pytest.mark.contract("FE-ENTRIES-029")
@pytest.mark.parametrize("view,date_label", [("buchungen", "Datum der ersten Fälligkeit"), ("einmalig", "Datum")])
def test_dialog_saves_a_booking_as_optional_and_the_list_tags_it(app_page, view, date_label):
    """FE-ENTRIES-029: 'Planung' defaults to 'Eingeplant'; 'Optional – …' is saved as optional=true and tagged in the list."""
    s = app_page.seed
    s.account("Giro", 100000, "2026-01-15")
    page = open_view(app_page, view)
    page.get_by_role("button", name="+ Neue Buchung").click()
    dlg = page.locator("dialog")
    planung = field(dlg, "Planung").locator("select")
    assert planung.evaluate("s => [...s.options].map(o => o.text)") == ["Eingeplant", "Optional – noch nicht entschieden"]
    assert planung.evaluate("s => s.options[s.selectedIndex].text") == "Eingeplant"
    put_value(dlg, "Bezeichnung", "Sofa")
    put_value(dlg, "Betrag (positiv eingeben)", "800")
    put_value(dlg, date_label, "2026-04-01")
    put_value(dlg, "Planung", "Optional – noch nicht entschieden")
    dlg.locator("button.primary").click()
    expect(page.locator("dialog")).to_have_count(0)
    assert s.state()["entries"][0]["optional"] is True
    expect(page.locator("#main tbody tr").filter(has_text="Sofa").locator(".tag.optional")).to_have_text("optional")


@pytest.mark.contract("FE-ENTRIES-029")
def test_editing_prefills_planung_and_group_sums_leave_optional_out(world, app_page):
    """FE-ENTRIES-029: the edit dialog shows the stored choice; group sums count planned bookings only."""
    page = open_view(app_page, "buchungen")
    page.locator("#main tbody tr").filter(has_text="Fitnessstudio").get_by_role("button", name="Bearbeiten").click()
    sel = field(page.locator("dialog"), "Planung").locator("select")
    assert sel.evaluate("s => s.options[s.selectedIndex].text") == "Optional – noch nicht entschieden"
    page.locator("dialog").get_by_role("button", name="Abbrechen").click()
    page.locator("select[name=group-by]").select_option(label="Konto")
    expect(page.locator("#main tr.group-head")).to_have_text(
        "▾ Giro · 2 Buchungen · +3.000,00 €/Monat", use_inner_text=True)


# ---------------------------------------------------------------------------- forecast

@pytest.mark.contract("FE-FORECAST-026")
def test_without_optional_bookings_there_is_no_panel(app_page):
    """FE-FORECAST-026: no optional bookings -> no 'Optionale Posten' panel and no dashed series."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    s.entry(giro["id"], "Gehalt", 300000, "2026-01-31")
    page = open_view(app_page)
    expect(page.locator("#ftable tr.clickable").first).to_be_visible()
    expect(panel(page)).to_have_count(0)
    show_balance(page)
    assert "mit optionalen Posten" not in page.locator("#chart .legend").inner_text()


@pytest.mark.contract("FE-FORECAST-026")
def test_panel_lists_optional_bookings_unticked_and_they_do_not_count(world, app_page):
    """FE-FORECAST-026: the panel lists them by date, unticked; the forecast leaves them out."""
    page = open_view(app_page)
    expect(panel(page)).to_contain_text("Optionale Posten")
    items = [norm(t) for t in panel(page).locator("label.opt-item").all_inner_texts()]
    assert items == ["Fitnessstudio -40,00 € monatlich ab 1.2.2026", "Zweiter Urlaub -2.500,00 € 10.3.2026"]
    expect(panel(page).locator("input[name=include-optional]:checked")).to_have_count(0)
    assert total(page, "2026-03") == "10.000,00 €"
    select(page, "2026-03")
    expect(page.locator("#fdetail")).not_to_contain_text("Zweiter Urlaub")


@pytest.mark.contract("FE-FORECAST-026", "FE-FORECAST-028")
def test_ticking_switches_a_booking_in(world, app_page):
    """FE-FORECAST-026/028: ticking re-runs the forecast with include=<id>; the item appears tagged 'optional'."""
    page = open_view(app_page)
    expect(row(page, "2026-03")).to_be_visible()
    with page.expect_request(lambda r: "/api/forecast" in r.url and f"include={world['trip']['id']}" in r.url):
        box(page, "Zweiter Urlaub").check()
    expect(row(page, "2026-03").locator("td b")).to_have_text("7.500,00 €")
    select(page, "2026-03")
    item = page.locator("#fdetail .row").filter(has_text="Zweiter Urlaub")
    expect(item.locator(".tag.optional")).to_have_text("optional")
    box(page, "Zweiter Urlaub").uncheck()
    expect(row(page, "2026-03").locator("td b")).to_have_text("10.000,00 €")


@pytest.mark.contract("FE-FORECAST-027")
def test_ticked_bookings_are_remembered_across_reloads(world, app_page):
    """FE-FORECAST-027: the choice survives a reload, and it is not stored on the server."""
    page = open_view(app_page)
    box(page, "Fitnessstudio").check()
    expect(row(page, "2026-02").locator("td b")).to_have_text("6.960,00 €")
    page.reload()
    expect(box(page, "Fitnessstudio")).to_be_checked()
    expect(box(page, "Zweiter Urlaub")).not_to_be_checked()
    expect(row(page, "2026-02").locator("td b")).to_have_text("6.960,00 €")
    assert all(e["optional"] is True for e in world["s"].state()["entries"] if e["name"] != "Gehalt")


@pytest.mark.contract("FE-FORECAST-027")
def test_stale_ids_are_ignored(world, app_page):
    """FE-FORECAST-027: a remembered id that is no longer an optional booking is not sent."""
    page = app_page.page
    page.add_init_script("localStorage.setItem('finanzprognose.includeOptional', '[999]')")
    with page.expect_request(lambda r: "/api/forecast" in r.url) as req:
        open_view(app_page)
    assert "include=" not in req.value.url


@pytest.mark.contract("FE-FORECAST-027")
def test_works_without_browser_storage(world, app_page):
    """FE-FORECAST-027: when localStorage throws, the panel still works until the next reload."""
    page = app_page.page
    page.add_init_script("""Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });""")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page = open_view(app_page)
    box(page, "Zweiter Urlaub").check()
    expect(row(page, "2026-03").locator("td b")).to_have_text("7.500,00 €")
    assert errors == []


@pytest.mark.contract("FE-FORECAST-028")
def test_dashed_comparison_and_summary_line(world, app_page):
    """FE-FORECAST-028: a dashed 'mit optionalen Posten' series and a summary line while some are left out."""
    page = open_view(app_page)
    show_balance(page)
    expect(page.locator("#chart .legend span.dashed")).to_have_text("mit optionalen Posten")
    expect(page.locator("#chart path[stroke-dasharray]")).to_have_count(1)
    select(page, "2026-03")
    kv = norm(page.locator("#fdetail .kv").first.inner_text())
    assert "mit allen optionalen Posten 7.420,00 €" in kv
    box(page, "Zweiter Urlaub").check()
    box(page, "Fitnessstudio").check()
    expect(row(page, "2026-03").locator("td b")).to_have_text("7.420,00 €")
    expect(page.locator("#chart .legend span.dashed")).to_have_count(0)
    expect(page.locator("#fdetail")).not_to_contain_text("mit allen optionalen Posten")


# ---------------------------------------------------------------------------- Verlauf

@pytest.mark.contract("FE-AUDIT-014")
def test_audit_shows_the_planning_mark_in_german(app_page):
    """FE-AUDIT-014: flipping the mark shows 'Planung: eingeplant → optional' in the Änderungsverlauf."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    e = s.entry(giro["id"], "Sofa", -80000, "2026-04-01", kind="once")
    body = {k: e[k] for k in ("account_id", "to_account_id", "name", "category", "kind", "amount", "start_date",
                              "end_date", "interval_months", "note")}
    assert s.c.put(f"/api/entries/{e['id']}", json={**body, "optional": True}).status_code == 200
    page = open_view(app_page, "verlauf")
    expect(page.locator("#main h2", has_text="Änderungsverlauf")).to_be_visible()
    assert "Planung: eingeplant → optional" in norm(page.locator("#main table tbody tr").first.inner_text())
