"""B-015: estimated bookings in the Buchungen list and the forecast (browser tests)."""
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, field, norm, put_value

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)      # 2026-01-20 12:00 Berlin
NOTE = "Geschätzter Betrag – die Abweichung zur Wirklichkeit zeigt der nächste Ist-Stand."


def open_view(app_page, hash_=""):
    app_page.page.clock.install(time=NOW)
    return app_page.open(hash_)


@pytest.fixture
def world(app_page):
    """Giro with a fixed rent, an estimated food budget and an estimated side income, plus a fixed transfer."""
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    s.entry(giro["id"], "Miete", -120000, "2026-01-01", category="Wohnen")
    s.entry(giro["id"], "Lebensmittel", -45000, "2026-01-02", category="Wohnen", estimated=True)
    s.entry(giro["id"], "Nebenjob", 20000, "2026-01-03", estimated=True)
    s.entry(giro["id"], "Sparen", 50000, "2026-01-05", to_account_id=tg["id"])
    return {"s": s, "giro": giro, "tg": tg}


def row_of(page, text):
    return page.locator("#main table tbody tr").filter(has_text=text).first


def amount_cell(page, name):
    return norm(row_of(page, name).locator("td.num").inner_text())


# ---------------------------------------------------------------------------- Buchungen

@pytest.mark.contract("FE-ENTRIES-026")
def test_new_booking_can_be_marked_estimated(world, app_page):
    """FE-ENTRIES-026: the form's Art select defaults to Fest; choosing Geschätzt saves estimated=true."""
    page = open_view(app_page, "buchungen")
    page.get_by_role("button", name="+ Neue Buchung").click()
    dlg = page.locator("dialog")
    art = field(dlg, "Art").locator("select")
    assert art.evaluate("s => s.options[s.selectedIndex].text").startswith("Fest")
    put_value(dlg, "Bezeichnung", "Tanken")
    put_value(dlg, "Betrag", "120,00")
    art.select_option(label="Geschätzt (z. B. Lebensmittel)")
    dlg.get_by_role("button", name="Speichern").click()
    expect(page.locator("dialog")).to_have_count(0)
    saved = next(e for e in world["s"].state()["entries"] if e["name"] == "Tanken")
    assert saved["estimated"] is True


@pytest.mark.contract("FE-ENTRIES-026")
def test_editing_prefills_and_can_unmark(world, app_page):
    """FE-ENTRIES-026: editing an estimated booking pre-selects Geschätzt; switching to Fest saves false."""
    page = open_view(app_page, "buchungen")
    row_of(page, "Lebensmittel").get_by_role("button", name="Bearbeiten").click()
    art = field(page.locator("dialog"), "Art").locator("select")
    assert art.evaluate("s => s.options[s.selectedIndex].text").startswith("Geschätzt")
    art.select_option(label="Fest (z. B. Miete, Abo)")
    page.locator("dialog").get_by_role("button", name="Speichern").click()
    expect(page.locator("dialog")).to_have_count(0)
    saved = next(e for e in world["s"].state()["entries"] if e["name"] == "Lebensmittel")
    assert saved["estimated"] is False


@pytest.mark.contract("FE-ENTRIES-027")
def test_estimated_amounts_carry_the_approx_mark(world, app_page):
    """FE-ENTRIES-027: estimated base amounts start with '≈ ', fixed ones don't."""
    page = open_view(app_page, "buchungen")
    assert amount_cell(page, "Lebensmittel") == "≈ -450,00 €"
    assert amount_cell(page, "Nebenjob") == "≈ +200,00 €"
    assert amount_cell(page, "Miete") == "-1.200,00 €"
    assert amount_cell(page, "Sparen") == "500,00 €"


@pytest.mark.contract("FE-ENTRIES-022", "FE-ENTRIES-027")
def test_group_by_art(world, app_page):
    """FE-ENTRIES-022/027: 'Art' groups into fest, then geschätzt; a sum with an estimate is marked '≈'."""
    page = open_view(app_page, "buchungen")
    page.locator("select[name=group-by]").select_option(label="Art")
    assert [norm(t) for t in page.locator("#main tr.group-head").all_inner_texts()] == [
        "▾ fest · 2 Buchungen · -1.200,00 €/Monat · Umbuchungen 500,00 €/Monat",
        "▾ geschätzt · 2 Buchungen · ≈ -250,00 €/Monat",
    ]


@pytest.mark.contract("FE-ENTRIES-027")
def test_mixed_group_sum_is_marked(world, app_page):
    """FE-ENTRIES-027: a category group mixing fixed and estimated bookings shows an '≈' sum."""
    page = open_view(app_page, "buchungen")
    page.locator("select[name=group-by]").select_option(label="Kategorie")
    heads = [norm(t) for t in page.locator("#main tr.group-head").all_inner_texts()]
    assert "▾ Wohnen · 2 Buchungen · ≈ -1.650,00 €/Monat" in heads


# ---------------------------------------------------------------------------- Prognose

def show_february(app_page):
    page = open_view(app_page)
    page.locator("#ftable tr").filter(has_text=call(page, "fMonth", "2026-02")).click()
    return page


def item(page, name):
    return page.locator("#fdetail .acc-card .row").filter(has=page.locator("button.link", has_text=name)).first


@pytest.mark.contract("FE-FORECAST-021")
def test_estimated_items_are_marked_and_explained(world, app_page):
    """FE-FORECAST-021: estimated items show '≈ ' and the estimate note; fixed items show neither."""
    page = show_february(app_page)
    food = item(page, "Lebensmittel")
    assert norm(food.locator(".num").inner_text()) == "≈ -450,00 €"
    expect(food.locator(".expl")).to_contain_text(NOTE)
    rent = item(page, "Miete")
    assert norm(rent.locator(".num").inner_text()) == "-1.200,00 €"
    expect(rent.locator(".expl")).not_to_contain_text("Geschätzter Betrag")


@pytest.mark.contract("FE-FORECAST-022")
def test_month_summary_shows_the_estimated_part(world, app_page):
    """FE-FORECAST-022: 'davon geschätzt' follows Einnahmen and Ausgaben with the estimated part of each."""
    page = show_february(app_page)
    kv = norm(page.locator("#fdetail .kv").inner_text())
    assert "Einnahmen 200,00 € davon geschätzt ≈ 200,00 € Ausgaben -1.650,00 € davon geschätzt ≈ -450,00 €" in kv


@pytest.mark.contract("FE-FORECAST-022")
def test_no_estimated_line_without_estimates(app_page):
    """FE-FORECAST-022: a month without estimated bookings has no 'davon geschätzt' line."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    s.entry(giro["id"], "Miete", -120000, "2026-01-01")
    page = show_february(app_page)
    expect(page.locator("#fdetail .kv")).to_contain_text("Ausgaben")
    expect(page.locator("#fdetail .kv")).not_to_contain_text("davon geschätzt")


@pytest.mark.contract("FE-FORECAST-018", "FE-FORECAST-021")
def test_forecast_group_by_art(world, app_page):
    """FE-FORECAST-018/021: grouped by Art the estimated group's sum and items carry '≈'."""
    page = show_february(app_page)
    page.locator("select[name=group-by]").select_option(label="Art")
    cards = [norm(t) for t in page.locator("#fdetail .acc-card.group > .head").all_inner_texts()]
    assert cards == ["▸ fest -1.200,00 € Umbuchungen 500,00 €", "▸ geschätzt ≈ -250,00 €"]
    card = page.locator("#fdetail .acc-card.group").filter(has_text="geschätzt")
    card.get_by_role("button", name="▸ geschätzt").click()
    expect(card.locator(".row")).to_have_count(2)
    assert norm(card.locator(".row").first.inner_text()).count("≈") == 1
    expect(card.locator(".row").first.locator(".expl")).to_contain_text(NOTE)


# ---------------------------------------------------------------------------- Verlauf

@pytest.mark.contract("FE-AUDIT-010")
def test_audit_shows_the_mark_in_german(app_page):
    """FE-AUDIT-010: flipping the mark shows 'Fest/geschätzt: fest → geschätzt' in the Änderungsverlauf."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    e = s.entry(giro["id"], "Lebensmittel", -45000, "2026-01-02")
    body = {k: e[k] for k in ("account_id", "to_account_id", "name", "category", "kind", "amount", "start_date",
                              "end_date", "interval_months", "note")}
    assert s.c.put(f"/api/entries/{e['id']}", json={**body, "estimated": True}).status_code == 200
    page = open_view(app_page, "verlauf")
    expect(page.locator("#main h2", has_text="Änderungsverlauf")).to_be_visible()
    top = norm(page.locator("#main table tbody tr").first.inner_text())
    assert "Fest/geschätzt: fest → geschätzt" in top
