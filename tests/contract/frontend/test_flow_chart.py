"""B-030: the monthly surplus chart, its events and the chart mode (browser tests)."""
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, norm, show_balance

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)      # 2026-01-20 12:00 Berlin


def open_view(app_page, hash_=""):
    app_page.page.clock.install(time=NOW)
    page = app_page.open(hash_)
    expect(page.locator("#ftable tr.clickable").first).to_be_visible()
    return page


def segs(page, ym):
    """(class, estimated, optional, amount) of a month's bar segments, in drawing order."""
    return page.locator(f"#chart g.bar[data-month='{ym}'] rect.seg").evaluate_all(
        "rs => rs.map(r => [r.dataset.cls, r.dataset.est === '1', r.dataset.opt === '1', +r.dataset.amount])")


def net(page, ym):
    return int(page.locator(f"#chart g.bar[data-month='{ym}'] line.net").get_attribute("data-amount"))


def select(page, ym):
    page.locator("#ftable tr.clickable").filter(has_text=call(page, "fMonth", ym)).first.click()
    expect(page.locator("#fdetail h2")).to_have_text(call(page, "fMonth", ym))


@pytest.fixture
def world(app_page):
    """Giro (1.000 € on 15.1.) and the reserve Notgroschen. Salary until June (raised from April), rent,
    estimated groceries and a saving into the reserve from February, a yearly insurance and an estimated
    holiday in March, and an optional sofa in April."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    res = s.account("Notgroschen", 1000000, "2026-01-15", kind="savings", reserve=True)
    g = giro["id"]
    sal = s.entry(g, "Gehalt", 300000, "2026-01-31", end_date="2026-06-30")
    s.entry(g, "Miete", -120000, "2026-01-01")
    s.entry(g, "Lebensmittel", -40000, "2026-02-03", estimated=True)
    s.entry(g, "Sparen", 30000, "2026-02-05", to_account_id=res["id"])
    s.entry(g, "Versicherung", -60000, "2026-03-02", interval_months=12)
    s.entry(g, "Urlaub", -200000, "2026-03-10", kind="once", estimated=True)
    s.entry(res["id"], "Zinsen", 1000, "2026-03-31", kind="once")
    s.adjustment(sal["id"], "2026-04-01", amount=320000)
    sofa = s.entry(g, "Sofa", -80000, "2026-04-20", kind="once", optional=True)
    return {"s": s, "sofa": sofa}


# ---------------------------------------------------------------------------- mode

@pytest.mark.contract("FE-FORECAST-029")
def test_flow_is_the_default_and_the_choice_is_remembered(world, app_page):
    """FE-FORECAST-029: 'Überschuss pro Monat' is active by default; 'Kontostand' sticks across a reload."""
    page = open_view(app_page)
    flow, bal = page.locator("#chart button[data-mode=flow]"), page.locator("#chart button[data-mode=balance]")
    expect(flow).to_have_text("Überschuss pro Monat")
    expect(bal).to_have_text("Kontostand")
    expect(flow).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#chart svg.chart[data-mode=flow]")).to_have_count(1)
    show_balance(page)
    expect(bal).to_have_class("small active")
    page.reload()
    expect(page.locator("#chart svg.chart[data-mode=balance]")).to_have_count(1)
    page.locator("#chart button[data-mode=flow]").click()
    expect(page.locator("#chart svg.chart[data-mode=flow]")).to_have_count(1)


@pytest.mark.contract("FE-FORECAST-029")
def test_mode_works_without_browser_storage(world, app_page):
    """FE-FORECAST-029: when localStorage throws, switching still works."""
    page = app_page.page
    page.add_init_script("""Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });""")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page = open_view(app_page)
    show_balance(page)
    assert errors == []


# ---------------------------------------------------------------------------- bars

@pytest.mark.contract("FE-FORECAST-030", "FE-FORECAST-031")
def test_bar_segments_by_class_and_the_surplus(world, app_page):
    """FE-FORECAST-030/031: segments per class (estimates apart), the reserve flow, no other transfers; net = sum."""
    page = open_view(app_page)
    assert segs(page, "2026-01") == [["monthly", False, False, 300000]]
    assert segs(page, "2026-02") == [["monthly", False, False, 300000], ["monthly", False, False, -120000],
                                     ["monthly", True, False, -40000], ["reserve", False, False, -30000]]
    assert net(page, "2026-02") == 110000
    assert segs(page, "2026-03") == [["monthly", False, False, 300000], ["monthly", False, False, -120000],
                                     ["monthly", True, False, -40000], ["irregular", False, False, -60000],
                                     ["once", True, False, -200000], ["reserve", False, False, -30000]]
    assert net(page, "2026-03") == -150000          # the interest on the reserve account is not counted


@pytest.mark.contract("FE-FORECAST-030")
def test_switched_in_optional_bookings_are_dashed_segments(world, app_page):
    """FE-FORECAST-030: an optional booking appears only when switched in, as its own (optional) segment."""
    page = open_view(app_page)
    assert not any(s[2] for s in segs(page, "2026-04"))
    page.locator(".optional-panel label.opt-item").filter(has_text="Sofa").locator("input").check()
    expect(page.locator("#chart g.bar[data-month='2026-04'] rect.seg[data-opt='1']")).to_have_count(1)
    assert ["once", False, True, -80000] in segs(page, "2026-04")


@pytest.mark.contract("FE-FORECAST-030")
def test_without_reserve_accounts_transfers_are_not_shown(app_page):
    """FE-FORECAST-030: with only available accounts a transfer between them is no segment; bookings on every account count."""
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    s.entry(giro["id"], "Sparen", 30000, "2026-02-05", to_account_id=tg["id"])
    s.entry(tg["id"], "Zinsen", 500, "2026-02-28", interval_months=3)
    page = open_view(app_page)
    assert segs(page, "2026-02") == [["irregular", False, False, 500]]
    assert net(page, "2026-02") == 500


@pytest.mark.contract("FE-FORECAST-031")
def test_tooltip_legend_and_click(world, app_page):
    """FE-FORECAST-031: the month tooltip, the legend entries and selecting a month by clicking its bar."""
    page = open_view(app_page)
    target = page.locator("#chart rect:has(title)").nth(2)
    title = target.locator("title").text_content()
    assert [norm(t) for t in title.splitlines()[:2]] == [f"{call(page, 'fMonth', '2026-03')}: Überschuss -1.500,00 €",
                                      "Einnahmen 3.000,00 €, Ausgaben -4.500,00 €"]
    assert "• Urlaub: -2.000,00 € (einmalig)" in norm(title)
    legend = [norm(t) for t in page.locator("#chart .legend span").all_inner_texts()]
    assert legend[:5] == ["Monatlich wiederkehrend", "Seltener wiederkehrend (z. B. jährlich)", "Einmalig", "Rücklage", "Überschuss des Monats"]
    assert legend[-1] == "heller = geschätzt"
    target.click()
    expect(page.locator("#fdetail h2")).to_have_text(call(page, "fMonth", "2026-03"))


# ---------------------------------------------------------------------------- events

@pytest.mark.contract("FE-FORECAST-032", "FE-FORECAST-033")
def test_events_per_month(world, app_page):
    """FE-FORECAST-032/033: markers and the detail list: starts (not in the first month), one-time, adjustment, end."""
    page = open_view(app_page)
    marks = page.locator("#chart circle.event-mark").evaluate_all("cs => cs.map(c => [c.dataset.month, +c.dataset.count])")
    assert marks == [["2026-02", 2], ["2026-03", 3], ["2026-04", 1], ["2026-06", 1]]
    expected = {
        "2026-02": [("start", "Neu: Lebensmittel -400,00 € monatlich"), ("start", "Neu: Sparen Umbuchung 300,00 € monatlich")],
        "2026-03": [("start", "Neu: Versicherung -600,00 € jährlich"), ("once", "Urlaub: -2.000,00 € (einmalig)"),
                    ("once", "Zinsen: +10,00 € (einmalig)")],
        "2026-04": [("adjustment", "Gehalt: ab 1.4.2026 neuer Betrag 3.200,00 €")],
        "2026-06": [("end", "Endet: Gehalt (letzte Fälligkeit 30.6.2026)")],
    }
    for ym, items in expected.items():
        select(page, ym)
        expect(page.locator("#fdetail .events")).to_contain_text("Ereignisse in diesem Monat")
        got = page.locator("#fdetail .events li.event").evaluate_all("ls => ls.map(l => [l.dataset.kind, l.textContent])")
        assert [(k, norm(t)) for k, t in got] == items
    select(page, "2026-01")
    expect(page.locator("#fdetail .events")).to_have_count(0)


@pytest.mark.contract("FE-FORECAST-032")
def test_optional_events_only_when_switched_in(world, app_page):
    """FE-FORECAST-032: an optional booking is an event only once it is switched in; the list shows in both views."""
    page = open_view(app_page)
    select(page, "2026-04")
    expect(page.locator("#fdetail .events li.event")).to_have_count(1)
    page.locator(".optional-panel label.opt-item").filter(has_text="Sofa").locator("input").check()
    expect(page.locator("#fdetail .events li.event")).to_have_count(2)
    expect(page.locator("#chart circle.event-mark[data-month='2026-04']")).to_have_attribute("data-count", "2")
    show_balance(page)
    expect(page.locator("#fdetail .events li.event").filter(has_text="Sofa")).to_have_count(1)
