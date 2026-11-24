import re
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, norm

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)        # 2026-01-20 12:00 in Berlin


def open_forecast(app_page, hash_=""):
    app_page.page.clock.install(time=NOW)
    return app_page.open(hash_)


@pytest.fixture
def world(app_page):
    """Giro (1.000 on 15.1.) + Tagesgeld, salary (raise from March), rent, a monthly transfer, a later Ist-Stand."""
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    sal = s.entry(giro["id"], "Gehalt", 300000, "2026-01-31")
    s.entry(giro["id"], "Miete", -120000, "2026-01-01")
    s.entry(giro["id"], "Sparen", 50000, "2026-02-05", to_account_id=tg["id"])
    s.adjustment(sal["id"], "2026-03-01", amount=320000, note="Raise")
    s.checkpoint(giro["id"], "2026-02-20", 500000)
    return {"giro": giro, "tg": tg, "salary": sal}


@pytest.fixture
def single(app_page):
    a = app_page.seed.account("Giro", 100000, "2026-01-15")
    app_page.seed.entry(a["id"], "Gehalt", 300000, "2026-01-31")
    return a


def row(page, ym):
    label = call(page, "fMonth", ym)
    return page.locator("#ftable tr.clickable").filter(has_text=label).first


def select(page, ym):
    row(page, ym).click()
    expect(row(page, ym)).to_have_class(re.compile(r"\bselected\b"))


@pytest.mark.contract("FE-FORECAST-001", "E2E-ONBOARD-001")
def test_empty_state_welcome_panel_opens_the_account_dialog(app_page):
    """FE-FORECAST-001: with no accounts: 'Willkommen' panel + 'Erstes Konto anlegen' opening the new-account dialog."""
    page = open_forecast(app_page)
    panel = page.locator("#main .panel").filter(has_text="Willkommen")
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Erstes Konto anlegen").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    expect(dlg.locator('label.field[data-name="name"]')).to_have_count(1)
    assert page.locator("#ftable").count() == 0


@pytest.mark.contract("FE-FORECAST-002")
def test_toolbar_chart_table_and_detail_are_rendered(app_page, single):
    """FE-FORECAST-002: with accounts, the toolbar, #chart, #ftable and #fdetail come from GET /api/forecast."""
    page = app_page.page
    page.clock.install(time=NOW)
    with page.expect_request(lambda r: "/api/forecast" in r.url):
        page.goto("/")
    for sel in (".toolbar", "#chart", "#ftable", "#fdetail"):
        expect(page.locator(sel)).to_be_visible()
    expect(page.locator("#chart svg.chart")).to_be_visible()
    tb = page.locator(".toolbar")
    expect(tb.locator('input[type="month"]')).to_have_count(1)
    expect(tb.locator("select:not([name=group-by])")).to_have_count(1)   # Zeitraum
    expect(tb.locator("select[name=group-by]")).to_have_count(1)          # Gruppieren nach (FE-FORECAST-018)
    for name in ("Heute", "+ Wiederkehrend", "+ Einmalig", "+ Ist-Stand"):
        expect(tb.get_by_role("button", name=name, exact=True)).to_have_count(1)
    expect(tb.locator("button.primary")).to_have_text("+ Wiederkehrend")


@pytest.mark.contract("FE-FORECAST-003")
def test_zeitraum_offers_the_five_horizons_and_refetches(app_page, single):
    """FE-FORECAST-003: Zeitraum has 12/24/36/60/120 Monate; changing it re-fetches with the new horizon."""
    page = open_forecast(app_page)
    sel = page.locator(".toolbar select:not([name=group-by])")
    assert [o.strip() for o in sel.locator("option").all_inner_texts()] == ["12 Monate", "24 Monate", "36 Monate", "60 Monate", "120 Monate"]
    with page.expect_request(lambda r: "/api/forecast" in r.url and "months=36" in r.url):
        sel.select_option(label="36 Monate")
    expect(page.locator("#ftable tr.clickable")).to_have_count(36)


@pytest.mark.contract("FE-FORECAST-004")
def test_changing_ab_refetches_from_that_month_and_resets_selection(app_page, single):
    """FE-FORECAST-004: changing 'Ab' re-fetches from the new start month and resets the selected month."""
    page = open_forecast(app_page)
    select(page, "2026-06")
    with page.expect_request(lambda r: "/api/forecast" in r.url and "start=2026-05" in r.url):
        page.locator('.toolbar input[type="month"]').fill("2026-05")
    first = page.locator("#ftable tr.clickable").first
    expect(first).to_contain_text(call(page, "fMonth", "2026-05"))
    expect(row(page, "2026-06")).not_to_have_class(re.compile(r"\bselected\b"))


@pytest.mark.contract("FE-FORECAST-005")
def test_heute_resets_start_month_to_the_current_month(app_page, single):
    """FE-FORECAST-005: 'Heute' sets the start month to the current month (browser clock)."""
    page = open_forecast(app_page)
    ab = page.locator('.toolbar input[type="month"]')
    expect(ab).to_have_value("2026-01")
    ab.fill("2025-03")
    expect(ab).to_have_value("2025-03")
    page.locator(".toolbar").get_by_role("button", name="Heute").click()
    expect(ab).to_have_value("2026-01")
    expect(page.locator("#ftable tr.clickable").first).to_contain_text(call(page, "fMonth", "2026-01"))


@pytest.mark.contract("FE-FORECAST-006")
def test_month_table_has_one_row_per_month_with_total_and_change(app_page, single):
    """FE-FORECAST-006: columns Monat (Monatsende)/Gesamt/Veränderung (single account); one row per month; closing + change."""
    page = open_forecast(app_page)
    expect(page.locator("#ftable tr.clickable").first).to_be_visible()      # wait for the table before reading it
    heads = [norm(t) for t in page.locator("#ftable thead th").all_inner_texts()]
    assert heads == ["Monat (Monatsende)", "Gesamt", "Veränderung"]
    rows = page.locator("#ftable tr.clickable")
    expect(rows).to_have_count(24)
    jan = norm(rows.first.inner_text())
    assert call(page, "fMonth", "2026-01") in jan and "4.000,00 €" in jan
    assert "3.000,00 €" in jan          # change vs opening: salary of the month (opening = start balance 1.000 -> 4.000)


@pytest.mark.contract("FE-FORECAST-006")
def test_month_table_has_a_column_per_account_when_there_are_several(app_page, world):
    """FE-FORECAST-006: with more than one account the table gets a column per account."""
    page = open_forecast(app_page)
    expect(page.locator("#ftable tr.clickable").first).to_be_visible()      # wait for the table before reading it
    heads = [norm(t) for t in page.locator("#ftable thead th").all_inner_texts()]
    assert "Giro" in heads and "Tagesgeld" in heads and "Gesamt" in heads and "Veränderung" in heads and heads[0] == "Monat (Monatsende)"


@pytest.mark.contract("FE-FORECAST-007", "E2E-ONBOARD-006")
def test_clicking_a_row_selects_the_month_and_updates_the_detail(app_page, world):
    """FE-FORECAST-007: clicking a table row selects it (class 'selected') and updates #fdetail."""
    page = open_forecast(app_page)
    select(page, "2026-03")
    assert page.locator("#ftable tr.selected").count() == 1
    expect(page.locator("#fdetail")).to_contain_text("Anfangsstand")
    first_detail = page.locator("#fdetail").inner_text()
    select(page, "2026-02")
    assert page.locator("#ftable tr.selected").count() == 1
    assert page.locator("#fdetail").inner_text() != first_detail


@pytest.mark.contract("FE-FORECAST-007")
def test_clicking_a_chart_month_selects_it_too(app_page, world):
    """FE-FORECAST-007: clicking a chart month <rect> selects that month (selector per F-5: a rect carrying a <title>)."""
    page = open_forecast(app_page)
    rects = page.locator("#chart rect:has(title)")
    try:
        rects.first.wait_for(state="attached", timeout=5000)
    except Exception:                      # noqa: BLE001 - reported by the assertion below
        pass
    assert rects.count() >= 3, "no clickable month rects with a <title> found in #chart"
    rects.nth(2).click()
    expect(page.locator("#ftable tr.selected")).to_have_count(1)
    expect(page.locator("#ftable tr.clickable").nth(2)).to_have_class(re.compile(r"\bselected\b"))


@pytest.mark.contract("FE-FORECAST-008")
def test_chart_has_total_and_account_series_and_a_legend(app_page, world):
    """FE-FORECAST-008: legend lists 'Gesamt' and each account (more than one account); axis labels use € / k €."""
    page = open_forecast(app_page)
    legend = norm(page.locator("#chart .legend").inner_text())
    assert "Gesamt" in legend and "Giro" in legend and "Tagesgeld" in legend
    labels = " ".join((el.text_content() or "") for el in page.locator("#chart svg text").all())
    assert "€" in labels


@pytest.mark.contract("FE-FORECAST-008")
def test_chart_legend_with_a_single_account_lists_only_the_total(app_page, single):
    """FE-FORECAST-008: with one account only the 'Gesamt' series is drawn (per-account series appear for >1 account)."""
    page = open_forecast(app_page)
    legend = norm(page.locator("#chart .legend").inner_text())
    assert "Gesamt" in legend and "Giro" not in legend


@pytest.mark.contract("FE-FORECAST-009")
def test_detail_panel_summary_and_account_cards(app_page, world):
    """FE-FORECAST-009: #fdetail shows Einnahmen, Ausgaben, Gesamtstand Monatsende, then a card per account."""
    page = open_forecast(app_page)
    select(page, "2026-03")
    d = page.locator("#fdetail")
    for t in ("Einnahmen", "Ausgaben", "Gesamtstand Monatsende"):
        expect(d).to_contain_text(t)
    for name in ("Giro", "Tagesgeld"):          # the contract names no selector for the per-account card (F-26)
        expect(d).to_contain_text(name)
    assert norm(d.inner_text()).count("Anfangsstand") == 2


@pytest.mark.contract("FE-FORECAST-010")
def test_account_card_lists_start_items_and_end(app_page, world):
    """FE-FORECAST-010: each account card lists Anfangsstand, the month's items and Endstand."""
    page = open_forecast(app_page)
    select(page, "2026-03")
    text = norm(page.locator("#fdetail").inner_text())
    assert text.count("Anfangsstand") >= 2 and text.count("Endstand") >= 2
    assert "Gehalt" in text and "Miete" in text and "Sparen" in text
    assert text.index("Anfangsstand") < text.index("Gehalt") < text.index("Endstand")


@pytest.mark.contract("FE-FORECAST-010")
def test_month_without_items_says_so(app_page, single):
    """FE-FORECAST-010: a month with no items shows 'Keine Buchungen in diesem Monat'."""
    app_page.seed.c.post(f"/api/entries/{app_page.seed.state()['entries'][0]['id']}/archive", json={})
    page = open_forecast(app_page)
    select(page, "2026-03")
    expect(page.locator("#fdetail")).to_contain_text("Keine Buchungen in diesem Monat")


@pytest.mark.contract("FE-FORECAST-011", "E2E-BOOK-007")
def test_booking_item_shows_date_label_amount_and_derivation(app_page, world):
    """FE-FORECAST-011: a booking row has date, label, signed amount and a .expl derivation ending in 'Kontostand danach'."""
    page = open_forecast(app_page)
    select(page, "2026-03")
    item = page.locator("#fdetail").locator("tr, li, div").filter(has_text="Gehalt").last
    text = norm(item.text_content())
    assert "31.3.2026" in text or "31.03.2026" in text or "31.03." in text
    assert "3.200,00 €" in text
    expl = norm(page.locator("#fdetail .expl").filter(has_text="Raise").first.text_content())
    assert "Grundbetrag 3.000,00 €" in expl
    assert "ab 01.03.2026: neuer Betrag 3.200,00 € (Raise)" in expl
    assert "Kontostand danach:" in expl
    assert expl.index("Grundbetrag") < expl.index("neuer Betrag") < expl.index("Kontostand danach")


@pytest.mark.contract("FE-FORECAST-012", "FE-FORECAST-013", "E2E-CP-004")
def test_checkpoint_item_shows_forecast_vs_actual_and_deviation(app_page, world):
    """FE-FORECAST-012/013: a later checkpoint shows 'Prognose war …, tatsächlich … → Abweichung …' and the continue-note."""
    page = open_forecast(app_page)
    select(page, "2026-02")
    text = norm(page.locator("#fdetail").text_content())
    assert re.search(r"Prognose war 2\.300,00 €, tatsächlich 5\.000,00 € → Abweichung \+?2\.700,00 €", text), text
    assert "Ab hier rechnet die Prognose mit dem echten Kontostand weiter." in text
    assert "Ist-Stand eingetragen" in text


@pytest.mark.contract("FE-FORECAST-012", "FE-FORECAST-013")
def test_start_checkpoint_item_shows_starting_point_wording(app_page, world):
    """FE-FORECAST-012/013: the first checkpoint reads 'Startstand (Ist-Stand)' / 'Ausgangspunkt der Berechnung für dieses Konto'."""
    page = open_forecast(app_page)
    select(page, "2026-01")
    text = norm(page.locator("#fdetail").text_content())
    assert "Startstand (Ist-Stand)" in text and "Ausgangspunkt der Berechnung für dieses Konto" in text
    assert "Abweichung" not in text


@pytest.mark.contract("FE-FORECAST-014", "E2E-CP-006")
def test_forecast_warning_renders_as_a_warn_banner(app_page):
    """FE-FORECAST-014: each forecast warning is a .banner.warn in #warn with the German text."""
    s = app_page.seed
    s.account("Giro", 100000, "2026-01-15")
    solo = s.account("Ohne Stand", 0, "2026-01-15")
    cp = [c for c in s.state()["checkpoints"] if c["account_id"] == solo["id"]][0]
    s.c.post(f"/api/checkpoints/{cp['id']}/archive", json={})
    page = open_forecast(app_page)
    banner = page.locator("#warn .banner.warn")
    expect(banner).to_have_count(1)
    expect(banner).to_contain_text("Konto „Ohne Stand“ hat keinen Ist-Stand und kann nicht berechnet werden.")


@pytest.mark.contract("FE-FORECAST-015")
def test_negative_total_shows_an_error_banner_naming_the_first_month(app_page):
    """FE-FORECAST-015: a negative total closing -> .banner.err 'Achtung: Im <Monat> wird der Gesamtstand voraussichtlich negativ (<eur>).'."""
    s = app_page.seed
    a = s.account("Giro", 10000, "2026-01-15")
    s.entry(a["id"], "Miete", -50000, "2026-02-01")
    page = open_forecast(app_page)
    month = call(page, "fMonth", "2026-02")
    expected = f"Achtung: Im {month} wird der Gesamtstand voraussichtlich negativ ({norm(call(page, 'eur', -40000))})."
    banner = page.locator("#warn .banner.err")
    expect(banner).to_have_count(1)
    assert norm(banner.inner_text()) == expected


@pytest.mark.contract("FE-FORECAST-015")
def test_no_error_banner_when_the_total_never_goes_negative(app_page, single):
    """FE-FORECAST-015: no negative-balance banner for a healthy forecast."""
    page = open_forecast(app_page)
    expect(page.locator("#ftable")).to_be_visible()
    assert page.locator("#warn .banner.err").count() == 0


@pytest.mark.contract("FE-FORECAST-016")
def test_clicking_a_booking_label_opens_the_prefilled_edit_dialog(app_page, world):
    """FE-FORECAST-016: clicking a booking item's label opens that entry's edit dialog, pre-filled."""
    page = open_forecast(app_page)
    select(page, "2026-03")
    page.locator("#fdetail").get_by_text("Miete", exact=True).first.click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    expect(dlg.locator("input").first).to_have_value("Miete")


@pytest.mark.contract("FE-FORECAST-017")
def test_wiederkehrend_button_opens_new_recurring_dialog_and_refreshes_the_forecast(app_page, single):
    """FE-FORECAST-017: '+ Wiederkehrend' opens the new recurring booking dialog; saving refreshes the forecast."""
    page = open_forecast(app_page)
    page.locator(".toolbar").get_by_role("button", name="+ Wiederkehrend").click()
    dlg = page.locator("dialog")
    expect(dlg.locator("h3")).to_have_text("Neue wiederkehrende Buchung")
    expect(dlg.locator("label.field").filter(has_text="Bezeichnung")).to_have_count(1)
    dlg.locator("label.field").filter(has_text="Bezeichnung").locator("input").fill("Streaming")
    dlg.locator("label.field").filter(has_text="Betrag").locator("input").first.fill("12,99")
    dlg.locator("label.field").filter(has_text="Datum der ersten Fälligkeit").locator("input").fill("2026-02-10")
    dlg.locator("button.primary").click()
    expect(page.locator("dialog")).to_have_count(0)
    select(page, "2026-02")
    expect(page.locator("#fdetail")).to_contain_text("Streaming")


@pytest.mark.contract("FE-FORECAST-017")
def test_einmalig_button_opens_new_one_time_dialog_and_refreshes_the_forecast(app_page, single):
    """FE-FORECAST-017: '+ Einmalig' opens the new one-time booking dialog; saving refreshes the forecast."""
    page = open_forecast(app_page)
    page.locator(".toolbar").get_by_role("button", name="+ Einmalig").click()
    dlg = page.locator("dialog")
    expect(dlg.locator("h3")).to_have_text("Neue einmalige Buchung")
    dlg.locator("label.field").filter(has_text="Bezeichnung").locator("input").fill("Waschmaschine")
    dlg.locator("label.field").filter(has_text="Betrag").locator("input").first.fill("650")
    dlg.locator("label.field").filter(has_text="Datum").locator("input").fill("2026-02-10")
    dlg.locator("button.primary").click()
    expect(page.locator("dialog")).to_have_count(0)
    select(page, "2026-02")
    expect(page.locator("#fdetail")).to_contain_text("Waschmaschine")
    select(page, "2026-03")
    expect(page.locator("#fdetail")).not_to_contain_text("Waschmaschine")


@pytest.mark.contract("FE-FORECAST-016")
def test_clicking_a_one_time_booking_opens_the_one_time_dialog(app_page, single):
    """FE-FORECAST-016: a one-time booking opens in the one-time dialog (no Rhythmus field)."""
    app_page.seed.entry(single["id"], "Urlaub", -150000, "2026-02-10", kind="once")
    page = open_forecast(app_page)
    select(page, "2026-02")
    page.locator("#fdetail").get_by_text("Urlaub", exact=True).first.click()
    dlg = page.locator("dialog")
    expect(dlg.locator("h3")).to_have_text("Buchung „Urlaub“ bearbeiten")
    expect(dlg.locator("label.field").filter(has_text="Rhythmus")).to_have_count(0)
    expect(dlg.locator("label.field").filter(has_text="Datum").locator("input")).to_have_value("2026-02-10")


@pytest.mark.contract("FE-FORECAST-017")
def test_ist_stand_button_opens_checkpoint_dialog_and_refreshes_the_forecast(app_page, single):
    """FE-FORECAST-017: '+ Ist-Stand' opens the checkpoint dialog; saving refreshes the forecast."""
    page = open_forecast(app_page)
    page.locator(".toolbar").get_by_role("button", name="+ Ist-Stand").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    dlg.locator("label.field").filter(has_text="Datum (Stand am Abend)").locator("input").fill("2026-02-20")
    dlg.locator("label.field").filter(has_text="Kontostand").locator("input").fill("5.000,00")
    dlg.locator("button.primary").click()
    expect(page.locator("dialog")).to_have_count(0)
    select(page, "2026-02")
    expect(page.locator("#fdetail")).to_contain_text("Ist-Stand eingetragen")


# ---------------------------------------------------------------------------- grouping (B-012)

@pytest.fixture
def grouped(app_page):
    """Giro + Tagesgeld with categorised bookings; in March 2026 the salary is raised and the yearly
    Hausrat and the quarterly interest fall due."""
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    sal = s.entry(giro["id"], "Gehalt", 300000, "2026-01-31", category="Einkommen")
    s.adjustment(sal["id"], "2026-03-01", amount=320000)
    s.entry(giro["id"], "Miete", -120000, "2026-01-01", category="Wohnen")
    s.entry(giro["id"], "Strom", -9000, "2026-01-10", category="wohnen")
    s.entry(giro["id"], "Hausrat", -12000, "2026-03-15", category="Wohnen", interval_months=12)
    s.entry(giro["id"], "Sparen", 50000, "2026-02-05", category="Sparen", to_account_id=tg["id"])
    s.entry(tg["id"], "Zinsen", 3000, "2026-03-31", interval_months=3)
    return s


def show_march_grouped(app_page, option):
    page = open_forecast(app_page)
    page.locator("#ftable tr").filter(has_text="März 2026").click()
    page.locator("select[name=group-by]").select_option(label=option)
    return page


def group_cards(page):
    return [norm(t) for t in page.locator("#fdetail .acc-card.group > .head").all_inner_texts()]


@pytest.mark.contract("FE-FORECAST-018")
def test_forecast_grouping_defaults_to_account_cards(grouped, app_page):
    """FE-FORECAST-018: 'Keine' is the default and keeps the per-account cards."""
    page = open_forecast(app_page)
    sel = page.locator("select[name=group-by]")
    assert sel.evaluate("s => [...s.options].map(o => o.text)") == ["Keine", "Kategorie", "Typ", "Konto", "Rhythmus", "Art"]
    expect(sel).to_have_value("none")
    expect(page.locator("#fdetail .acc-card")).to_have_count(2)
    expect(page.locator("#fdetail .acc-card.group")).to_have_count(0)


@pytest.mark.contract("FE-FORECAST-018", "FE-FORECAST-019")
def test_forecast_groups_by_category_with_month_sums(grouped, app_page):
    """FE-FORECAST-018/019: month sums per category incl. the March raise; the transfer counts once and only as 'Umbuchungen'."""
    page = show_march_grouped(app_page, "Kategorie")
    assert group_cards(page) == [
        "▸ Einkommen +3.200,00 €",
        "▸ Sparen Umbuchungen 500,00 €",
        "▸ Wohnen -1.410,00 €",
        "▸ Ohne Kategorie +30,00 €",
    ]


@pytest.mark.contract("FE-FORECAST-019")
def test_forecast_group_by_account_lists_both_transfer_sides(grouped, app_page):
    """FE-FORECAST-019: under 'Konto' each side of the transfer belongs to its own account."""
    page = show_march_grouped(app_page, "Konto")
    assert group_cards(page) == ["▸ Giro +1.790,00 € Umbuchungen 500,00 €", "▸ Tagesgeld +30,00 € Umbuchungen 500,00 €"]


@pytest.mark.contract("FE-FORECAST-020")
def test_forecast_group_unfolds_to_its_bookings(grouped, app_page):
    """FE-FORECAST-020: folded by default; opening shows date, name, account tag, amount and explanation."""
    page = show_march_grouped(app_page, "Kategorie")
    card = page.locator("#fdetail .acc-card.group").filter(has_text="Wohnen")
    expect(card.locator(".row")).to_have_count(0)
    card.get_by_role("button", name="▸ Wohnen").click()
    expect(card.locator(".row")).to_have_count(3)
    assert card.locator(".row button.link").all_inner_texts() == ["Miete", "Strom", "Hausrat"]
    assert card.locator(".row .tag").all_inner_texts() == ["Giro", "Giro", "Giro"]
    first = norm(card.locator(".row").first.inner_text())
    assert first.startswith("01.03.") and "-1.200,00 €" in first and "Grundbetrag" in first


@pytest.mark.contract("FE-FORECAST-020")
def test_forecast_group_choice_is_remembered_separately(grouped, app_page):
    """FE-FORECAST-020: the forecast's choice survives a reload and leaves the Buchungen view at 'Keine'."""
    page = show_march_grouped(app_page, "Typ")
    page.reload()
    expect(page.locator("select[name=group-by]")).to_have_value("type")
    page.goto("/#buchungen")
    expect(page.locator("select[name=group-by]")).to_have_value("none")
