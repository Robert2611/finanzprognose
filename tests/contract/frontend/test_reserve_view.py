"""B-028: reserve accounts in the forecast view and the Verlauf (browser tests)."""
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, norm, show_balance

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)      # 2026-01-20 12:00 Berlin


def open_view(app_page, hash_=""):
    app_page.page.clock.install(time=NOW)
    return app_page.open(hash_)


def row(page, ym):
    return page.locator("#ftable tr.clickable").filter(has_text=call(page, "fMonth", ym)).first


def select(page, ym):
    row(page, ym).click()
    expect(page.locator("#fdetail h2")).to_have_text(call(page, "fMonth", ym))


def heads(page):
    expect(page.locator("#ftable tr.clickable").first).to_be_visible()
    return [norm(t) for t in page.locator("#ftable thead th").all_inner_texts()]


@pytest.fixture
def world(app_page):
    """Giro 1.000 € and the reserve Notgroschen 10.000 €; salary, rent, a monthly saving into the
    reserve from February, and a repair paid out of the reserve in March."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    res = s.account("Notgroschen", 1000000, "2026-01-15", kind="savings", reserve=True)
    s.entry(giro["id"], "Gehalt", 300000, "2026-01-31")
    s.entry(giro["id"], "Miete", -120000, "2026-02-01")
    s.entry(giro["id"], "Sparen", 30000, "2026-02-05", to_account_id=res["id"])
    s.entry(res["id"], "Reparatur", 150000, "2026-03-10", kind="once", to_account_id=giro["id"])
    return s


@pytest.mark.contract("FE-FORECAST-023")
def test_without_reserve_accounts_the_page_shows_the_total(app_page):
    """FE-FORECAST-023: with no reserve account the table and chart are about 'Gesamt', no 'Verfügbar'."""
    s = app_page.seed
    s.account("Giro", 100000, "2026-01-15")
    s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    page = open_view(app_page)
    assert heads(page) == ["Monat (Monatsende)", "Giro", "Tagesgeld", "Gesamt", "Veränderung"]
    show_balance(page)
    assert page.locator("#chart .legend span").all_inner_texts()[0] == "Gesamt"
    select(page, "2026-01")
    expect(page.locator("#fdetail")).not_to_contain_text("Verfügbar")


@pytest.mark.contract("FE-FORECAST-023")
def test_with_a_reserve_the_table_and_chart_are_about_available_money(world, app_page):
    """FE-FORECAST-023: 'Verfügbar' is the bold column and the main series; 'Veränderung' follows it; 'Gesamt' last."""
    page = open_view(app_page)
    assert heads(page) == ["Monat (Monatsende)", "Giro", "Notgroschen Rücklage", "Verfügbar", "Veränderung", "Gesamt"]
    show_balance(page)
    assert page.locator("#chart .legend span").all_inner_texts() == ["Verfügbar", "Giro", "Notgroschen"]
    feb = [norm(t) for t in row(page, "2026-02").locator("td").all_inner_texts()]
    assert feb[1:] == ["5.500,00 €", "10.300,00 €", "5.500,00 €", "+1.500,00 €", "15.800,00 €"]
    expect(row(page, "2026-02").locator("td b")).to_have_text("5.500,00 €")


@pytest.mark.contract("FE-FORECAST-025")
def test_month_summary_shows_the_reserve_flow_and_available_money(world, app_page):
    """FE-FORECAST-025: 'In Rücklage gelegt' / 'Aus Rücklage entnommen', then Verfügbar and Gesamtstand Monatsende."""
    page = open_view(app_page)
    select(page, "2026-02")
    kv = norm(page.locator("#fdetail .kv").first.inner_text())
    assert "In Rücklage gelegt 300,00 €" in kv
    assert "Verfügbar Monatsende 5.500,00 €" in kv and "Gesamtstand Monatsende 15.800,00 €" in kv
    expect(page.locator("#fdetail .kv b").first).to_have_text("5.500,00 €")
    select(page, "2026-03")
    kv = norm(page.locator("#fdetail .kv").first.inner_text())
    assert "Aus Rücklage entnommen 1.200,00 €" in kv and "In Rücklage gelegt" not in kv
    select(page, "2026-01")
    assert "Rücklage" not in norm(page.locator("#fdetail .kv").first.inner_text())


@pytest.mark.contract("FE-FORECAST-025")
def test_reserve_account_card_is_tagged(world, app_page):
    """FE-FORECAST-025: the reserve account's card in the month detail carries a 'Rücklage' tag."""
    page = open_view(app_page)
    select(page, "2026-02")
    expect(page.locator("#fdetail .acc-card .head .tag.reserve")).to_have_count(1)
    expect(page.locator("#fdetail .acc-card").filter(has_text="Notgroschen").locator(".tag.reserve")).to_have_text("Rücklage")


@pytest.mark.contract("FE-FORECAST-024")
def test_negative_banner_uses_the_available_money(app_page):
    """FE-FORECAST-024: the available money going negative raises the banner even though the total stays positive."""
    s = app_page.seed
    giro = s.account("Giro", 10000, "2026-01-15")
    s.account("Notgroschen", 1000000, "2026-01-15", kind="savings", reserve=True)
    s.entry(giro["id"], "Waschmaschine", -50000, "2026-02-10", kind="once")
    page = open_view(app_page)
    banner = page.locator("#warn .banner.err")
    expect(banner).to_have_text(f"Achtung: Im {call(page, 'fMonth', '2026-02')} wird das verfügbare Geld (ohne Rücklagen) "
                                "voraussichtlich negativ (-400,00 €).")


@pytest.mark.contract("FE-FORECAST-024")
def test_a_negative_reserve_alone_raises_no_banner(app_page):
    """FE-FORECAST-024: only the available money is checked."""
    s = app_page.seed
    s.account("Giro", 100000, "2026-01-15")
    s.account("Kredit", -50000, "2026-01-15", kind="other", reserve=True)
    page = open_view(app_page)
    expect(page.locator("#ftable tr.clickable").first).to_be_visible()
    expect(page.locator("#warn .banner.err")).to_have_count(0)


@pytest.mark.contract("FE-AUDIT-013")
def test_audit_shows_the_reserve_mark_in_german(app_page):
    """FE-AUDIT-013: flipping the mark shows 'Rücklage: nein → ja' in the Änderungsverlauf."""
    s = app_page.seed
    a = s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    assert s.c.put(f"/api/accounts/{a['id']}", json={"name": "Tagesgeld", "kind": "savings", "reserve": True, "note": ""}).status_code == 200
    page = open_view(app_page, "verlauf")
    expect(page.locator("#main h2", has_text="Änderungsverlauf")).to_be_visible()
    assert "Rücklage: nein → ja" in norm(page.locator("#main table tbody tr").first.inner_text())
