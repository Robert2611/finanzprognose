import json
import re
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import field, norm, put_value

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)      # 2026-01-20 12:00 Berlin


def open_once(app_page):
    app_page.page.clock.install(time=NOW)
    return app_page.open("einmalig")


def rows(page):
    return page.locator("#main table tbody tr")


def row_of(page, text):
    return rows(page).filter(has_text=text).first


def new_entry(page):
    page.get_by_role("button", name="+ Neue Buchung").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    return dlg


@pytest.fixture
def world(app_page):
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    return {"giro": giro, "tg": tg, "s": s}


# ---------------------------------------------------------------------------- list

@pytest.mark.contract("FE-ONCE-001", "FE-ONCE-003")
def test_empty_list_and_heading(world, app_page):
    """FE-ONCE-001/003: heading 'Einmalige Buchungen'; recurring bookings are not listed; empty list row."""
    world["s"].entry(world["giro"]["id"], "Miete", -120000)
    page = open_once(app_page)
    expect(page.locator(".toolbar h2")).to_have_text("Einmalige Buchungen")
    expect(rows(page)).to_have_count(1)
    expect(rows(page).first).to_contain_text("Noch keine einmaligen Buchungen.")


@pytest.mark.contract("FE-ONCE-001")
def test_archived_one_time_bookings_are_hidden_until_the_checkbox_is_ticked(world, app_page):
    """FE-ONCE-001: archived one-time bookings appear (class 'archived') only with 'Archivierte zeigen'."""
    s, g = world["s"], world["giro"]["id"]
    s.entry(g, "Aktiv", -100, "2026-02-01", kind="once")
    old = s.entry(g, "Alt", -100, "2026-01-01", kind="once")
    s.c.post(f"/api/entries/{old['id']}/archive", json={})
    page = open_once(app_page)
    expect(rows(page)).to_have_count(1)
    page.get_by_label("Archivierte zeigen").check()
    expect(rows(page)).to_have_count(2)
    expect(row_of(page, "Alt")).to_have_class(re.compile(r"\barchived\b"))
    expect(rows(page).last).to_contain_text("Alt")          # archived last, despite the earlier date


@pytest.mark.contract("FE-ONCE-002")
def test_row_content_and_date_order(world, app_page):
    """FE-ONCE-002: headers; date, name+category+note, type, account(→target), amount; sorted by date."""
    s, g, t = world["s"], world["giro"]["id"], world["tg"]["id"]
    s.entry(g, "Urlaub", -200000, "2026-07-10", kind="once", category="Reisen", note="Italien")
    s.entry(g, "Steuererstattung", 85000, "2026-05-02", kind="once")
    s.entry(g, "Rücklage", 100000, "2026-03-01", kind="once", to_account_id=t)
    page = open_once(app_page)
    heads = [norm(h) for h in page.locator("#main table thead th").all_inner_texts()]
    assert heads[:5] == ["Datum", "Bezeichnung", "Typ", "Konto", "Betrag"]
    texts = [norm(t) for t in rows(page).all_inner_texts()]
    assert [x.split(" ")[0] for x in texts] == ["1.3.2026", "2.5.2026", "10.7.2026"]
    assert all(x in texts[0] for x in ("Rücklage", "Umbuchung", "Giro", "→ Tagesgeld", "1.000,00 €"))
    assert all(x in texts[1] for x in ("Steuererstattung", "Einnahme", "+850,00 €"))
    assert all(x in texts[2] for x in ("Urlaub", "Reisen", "Italien", "Ausgabe", "-2.000,00 €"))
    for name in ("Bearbeiten", "Archivieren", "Verlauf"):
        expect(row_of(page, "Urlaub").get_by_role("button", name=name)).to_have_count(1)
    expect(row_of(page, "Urlaub").get_by_role("button", name=re.compile("Anpassung"))).to_have_count(0)


# ---------------------------------------------------------------------------- create / edit

@pytest.mark.contract("FE-ONCE-004")
def test_new_dialog_fields_and_defaults(world, app_page):
    """FE-ONCE-004: 'Neue einmalige Buchung' with a single 'Datum' and no frequency, rhythm or end date."""
    page = open_once(app_page)
    dlg = new_entry(page)
    expect(dlg.locator("h3")).to_have_text("Neue einmalige Buchung")
    labels = [norm(t).removesuffix(" *") for t in dlg.locator("label.field > span").all_inner_texts()]
    assert labels == ["Bezeichnung", "Typ", "Konto", "Betrag (positiv eingeben)", "Art", "Datum", "Kategorie (optional)", "Notiz (optional)"]
    sel = lambda label: field(dlg, label).locator("select").evaluate("s => s.options[s.selectedIndex].text")
    assert sel("Typ") == "Ausgabe" and sel("Konto") == "Giro"
    expect(field(dlg, "Datum").locator("input")).to_have_value("2026-01-20")
    put_value(dlg, "Typ", "Umbuchung zwischen Konten")
    expect(field(dlg, "Zielkonto")).to_have_count(1)


@pytest.mark.contract("FE-ONCE-005")
@pytest.mark.parametrize("typ,stored", [("Ausgabe", -65000), ("Einnahme", 65000)])
def test_saving_stores_a_one_time_booking(world, app_page, typ, stored):
    """FE-ONCE-005: kind 'once', the sign from the type, no end date; the row appears in this view."""
    page = open_once(app_page)
    dlg = new_entry(page)
    put_value(dlg, "Bezeichnung", "Waschmaschine")
    put_value(dlg, "Typ", typ)
    put_value(dlg, "Betrag (positiv eingeben)", "650")
    put_value(dlg, "Datum", "2026-04-12")
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Gespeichert")
    expect(row_of(page, "Waschmaschine")).to_contain_text("12.4.2026")
    e = world["s"].state()["entries"][0]
    assert (e["kind"], e["amount"], e["start_date"], e["end_date"], e["interval_months"]) == ("once", stored, "2026-04-12", None, 1)


@pytest.mark.contract("FE-ONCE-006")
def test_edit_prefills_and_sends_expected_updated_at(world, app_page):
    """FE-ONCE-006: edit pre-fills, PUT carries expected_updated_at, keeps kind 'once', no retroactive note."""
    e = world["s"].entry(world["giro"]["id"], "Urlaub", -200000, "2026-07-10", kind="once")
    page = open_once(app_page)
    row_of(page, "Urlaub").get_by_role("button", name="Bearbeiten").click()
    dlg = page.locator("dialog")
    expect(field(dlg, "Bezeichnung").locator("input")).to_have_value("Urlaub")
    expect(field(dlg, "Datum").locator("input")).to_have_value("2026-07-10")
    expect(dlg).not_to_contain_text("rückwirkend")
    put_value(dlg, "Betrag (positiv eingeben)", "2.500,00")
    with page.expect_request(lambda r: r.method == "PUT" and f"/api/entries/{e['id']}" in r.url) as req:
        dlg.locator("button.primary").click()
    body = json.loads(req.value.post_data)
    assert body["expected_updated_at"] == e["updated_at"] and body["kind"] == "once" and body["amount"] == -250000
    expect(row_of(page, "Urlaub")).to_contain_text("-2.500,00 €")


@pytest.mark.contract("FE-ONCE-007")
def test_archive_and_restore(world, app_page):
    """FE-ONCE-007: 'Archivieren' (confirmation) and 'Wiederherstellen' work from this list."""
    world["s"].entry(world["giro"]["id"], "Urlaub", -200000, "2026-07-10", kind="once")
    page = open_once(app_page)
    row_of(page, "Urlaub").get_by_role("button", name="Archivieren").click()
    page.locator("dialog button.primary").click()
    expect(rows(page).first).to_contain_text("Noch keine einmaligen Buchungen.")
    page.get_by_label("Archivierte zeigen").check()
    row_of(page, "Urlaub").get_by_role("button", name="Wiederherstellen").click()
    expect(row_of(page, "Urlaub")).not_to_have_class(re.compile(r"\barchived\b"))
    assert world["s"].state()["entries"][0]["archived"] is False


@pytest.mark.contract("FE-ONCE-007")
def test_adjustments_button_only_when_the_booking_has_adjustments(world, app_page):
    """FE-ONCE-007: an existing adjustment on a one-time booking stays reachable through 'N Anpassung(en)'."""
    s = world["s"]
    e = s.entry(world["giro"]["id"], "Urlaub", -200000, "2026-07-10", kind="once")
    s.adjustment(e["id"], "2026-06-01", amount=-250000)
    page = open_once(app_page)
    row_of(page, "Urlaub").get_by_role("button", name="1 Anpassung").click()
    expect(page.locator("dialog h3")).to_have_text("Anpassungen: Urlaub")


# ---------------------------------------------------------------------------- grouping

@pytest.fixture
def grouped(world):
    s, g, t = world["s"], world["giro"]["id"], world["tg"]["id"]
    s.entry(g, "Urlaub", -200000, "2026-07-10", kind="once", category="Reisen")
    s.entry(g, "Flug", -45000, "2026-06-01", kind="once", category="Reisen", estimated=True)
    s.entry(g, "Erstattung", 85000, "2026-05-02", kind="once")
    s.entry(g, "Rücklage", 100000, "2026-03-01", kind="once", to_account_id=t)
    s.entry(g, "Miete", -120000)                          # recurring: not in this view
    return world


@pytest.mark.contract("FE-ONCE-008")
def test_group_select_options_and_category_sums(grouped, app_page):
    """FE-ONCE-008: Keine/Kategorie/Typ/Konto/Art (no Rhythmus); heads show the plain sum and transfers separately."""
    page = open_once(app_page)
    sel = page.locator("select[name=group-by]")
    assert sel.evaluate("s => [...s.options].map(o => o.text)") == ["Keine", "Kategorie", "Typ", "Konto", "Art"]
    sel.select_option(label="Kategorie")
    heads = [norm(t) for t in page.locator("#main tr.group-head").all_inner_texts()]
    assert heads == [
        "▾ Reisen · 2 Buchungen · Summe ≈ -2.450,00 €",
        "▾ Ohne Kategorie · 2 Buchungen · Summe +850,00 € · Umbuchungen 1.000,00 €",
    ]


@pytest.mark.contract("FE-ONCE-008")
def test_group_choice_is_separate_from_the_recurring_view(grouped, app_page):
    """FE-ONCE-008: the choice is remembered across reloads, separately from the recurring view's choice."""
    page = app_page.open("buchungen")
    page.locator("select[name=group-by]").select_option(label="Rhythmus")
    page.goto("/#einmalig")
    expect(page.locator("select[name=group-by]")).to_have_value("none")
    expect(page.locator("#main tr.group-head")).to_have_count(0)
    page.locator("select[name=group-by]").select_option(label="Typ")
    page.reload()
    expect(page.locator("#main tr.group-head")).to_have_count(3)
    page.goto("/#buchungen")
    expect(page.locator("select[name=group-by]")).to_have_value("rhythm")
