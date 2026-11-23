import json
import re
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, field, norm, put_value

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)      # 2026-01-20 12:00 Berlin


def open_entries(app_page):
    app_page.page.clock.install(time=NOW)
    return app_page.open("buchungen")


def rows(page):
    return page.locator("#main table tbody tr")


def row_of(page, text):
    return rows(page).filter(has_text=text).first


@pytest.fixture
def world(app_page):
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    return {"giro": giro, "tg": tg, "s": s}


# ---------------------------------------------------------------------------- list

@pytest.mark.contract("FE-ENTRIES-004")
def test_empty_list_row(world, app_page):
    """FE-ENTRIES-004: an empty list renders a single 'Noch keine Buchungen.' row."""
    page = open_entries(app_page)
    expect(rows(page)).to_have_count(1)
    expect(rows(page).first).to_contain_text("Noch keine Buchungen.")


@pytest.mark.contract("FE-ENTRIES-001", "E2E-ARCH-002")
def test_archived_entries_are_hidden_until_the_checkbox_is_ticked(world, app_page):
    """FE-ENTRIES-001: archived bookings are listed (class 'archived') only after ticking 'Archivierte zeigen'."""
    s = world["s"]
    s.entry(world["giro"]["id"], "Aktiv", -100)
    old = s.entry(world["giro"]["id"], "Alt", -100)
    s.c.post(f"/api/entries/{old['id']}/archive", json={})
    page = open_entries(app_page)
    expect(rows(page)).to_have_count(1)
    expect(rows(page).first).to_contain_text("Aktiv")
    page.get_by_label("Archivierte zeigen").check()
    expect(rows(page)).to_have_count(2)
    expect(row_of(page, "Alt")).to_have_class(re.compile(r"\barchived\b"))
    expect(row_of(page, "Aktiv")).not_to_have_class(re.compile(r"\barchived\b"))
    expect(row_of(page, "Alt").get_by_role("button", name="Wiederherstellen")).to_have_count(1)


@pytest.mark.contract("FE-ENTRIES-002", "FE-ENTRIES-003")
def test_row_content_for_expense_income_transfer_and_once(world, app_page):
    """FE-ENTRIES-002/003: name+category+note, type, account(→target), base amount, cadence and period per row."""
    s, g, t = world["s"], world["giro"], world["tg"]
    s.entry(g["id"], "Miete", -120000, "2026-01-01", category="Wohnen", note="Kaltmiete", end_date="2026-12-01")
    s.entry(g["id"], "Gehalt", 300000, "2026-01-31")
    s.entry(g["id"], "Sparen", 50000, "2026-02-05", to_account_id=t["id"], interval_months=3)
    s.entry(g["id"], "Urlaub", -200000, "2026-03-10", kind="once")
    page = open_entries(app_page)
    miete, gehalt = norm(row_of(page, "Miete").inner_text()), norm(row_of(page, "Gehalt").inner_text())
    sparen, urlaub = norm(row_of(page, "Sparen").inner_text()), norm(row_of(page, "Urlaub").inner_text())
    assert all(x in miete for x in ("Wohnen", "Kaltmiete", "Ausgabe", "Giro", "-1.200,00 €", "monatlich", "ab 1.1.2026 bis 1.12.2026"))
    assert all(x in gehalt for x in ("Einnahme", "+3.000,00 €", "monatlich", "ab 31.1.2026")) and "bis" not in gehalt
    assert all(x in sparen for x in ("Umbuchung", "Giro", "→ Tagesgeld", "500,00 €", "quartalsweise", "ab 5.2.2026"))
    assert all(x in urlaub for x in ("Ausgabe", "-2.000,00 €", "einmalig", "10.3.2026")) and "ab 10.3.2026" not in urlaub


@pytest.mark.contract("FE-ENTRIES-005")
def test_adjustment_count_button_counts_only_active_adjustments(world, app_page):
    """FE-ENTRIES-005: the 'N Anpassung(en)' button shows the number of non-archived adjustments."""
    s, g = world["s"], world["giro"]
    e = s.entry(g["id"], "Gehalt", 300000)
    page = open_entries(app_page)
    assert re.search(r"\b0\b.*Anpassung", norm(row_of(page, "Gehalt").inner_text()))
    a1 = s.adjustment(e["id"], "2026-03-01", amount=320000)
    a2 = s.adjustment(e["id"], "2026-06-01", amount=330000)
    s.c.post(f"/api/adjustments/{a2['id']}/archive", json={})
    page.reload()
    btn = row_of(page, "Gehalt").get_by_role("button", name=re.compile(r"Anpassung"))
    assert norm(btn.inner_text()) == "1 Anpassung"
    s.adjustment(e["id"], "2026-07-01", amount=1)
    page.reload()
    assert norm(row_of(page, "Gehalt").get_by_role("button", name=re.compile(r"Anpassung")).inner_text()) == "2 Anpassungen"


@pytest.mark.contract("FE-ENTRIES-001")
def test_table_headers_and_row_actions(world, app_page):
    """FE-ENTRIES (interface): headers and per-row actions as documented."""
    world["s"].entry(world["giro"]["id"], "Miete", -100)
    page = open_entries(app_page)
    heads = [norm(h) for h in page.locator("#main table thead th").all_inner_texts()]
    assert heads[:7] == ["Bezeichnung", "Typ", "Konto", "Grundbetrag", "Rhythmus", "Zeitraum", "Anpassungen"]
    r = row_of(page, "Miete")
    for name in ("Bearbeiten", "Archivieren", "Verlauf"):
        expect(r.get_by_role("button", name=name)).to_have_count(1)
    expect(page.locator(".toolbar")).to_contain_text("Buchungen")
    expect(page.locator(".toolbar button.primary")).to_have_text("+ Neue Buchung")


# ---------------------------------------------------------------------------- create / edit

def new_entry(page):
    page.get_by_role("button", name="+ Neue Buchung").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    return dlg


@pytest.mark.contract("FE-ENTRIES-006")
def test_new_entry_dialog_defaults(world, app_page):
    """FE-ENTRIES-006: defaults are type Ausgabe, Wiederkehrend, monthly, today, first account."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    sel = lambda label: field(dlg, label).locator("select").evaluate("s => s.options[s.selectedIndex].text")
    assert sel("Typ") == "Ausgabe" and sel("Häufigkeit") == "Wiederkehrend" and sel("Rhythmus") == "monatlich"
    assert sel("Konto") == "Giro"
    expect(field(dlg, "Datum der (ersten) Fälligkeit").locator("input")).to_have_value("2026-01-20")
    assert field(dlg, "Typ").locator("option").all_inner_texts() == ["Einnahme", "Ausgabe", "Umbuchung zwischen Konten"]


@pytest.mark.contract("FE-ENTRIES-007", "E2E-BOOK-001")
@pytest.mark.parametrize("typ,typed,stored", [("Ausgabe", "1.200,00", -120000), ("Einnahme", "3.000,00", 300000)])
def test_amount_is_entered_positive_and_sign_follows_the_type(world, app_page, typ, typed, stored):
    """FE-ENTRIES-007: expense -> negative, income -> positive; saving toasts 'Gespeichert'."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    put_value(dlg, "Bezeichnung", "Test")
    put_value(dlg, "Typ", typ)
    put_value(dlg, "Betrag (positiv eingeben)", typed)
    put_value(dlg, "Datum der (ersten) Fälligkeit", "2026-01-31")
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Gespeichert")
    expect(page.locator("dialog")).to_have_count(0)
    assert world["s"].state()["entries"][0]["amount"] == stored
    expect(row_of(page, "Test")).to_contain_text(typ)


@pytest.mark.contract("FE-ENTRIES-007", "FE-ENTRIES-008", "E2E-BOOK-003")
def test_transfer_reveals_zielkonto_and_is_stored_positive(world, app_page):
    """FE-ENTRIES-007/008: 'Umbuchung zwischen Konten' reveals Zielkonto; stored positive; non-transfers send null."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    expect(field(dlg, "Zielkonto")).to_have_count(0)
    put_value(dlg, "Typ", "Umbuchung zwischen Konten")
    expect(field(dlg, "Zielkonto")).to_have_count(1)
    put_value(dlg, "Bezeichnung", "Sparen")
    put_value(dlg, "Zielkonto", "Tagesgeld")
    put_value(dlg, "Betrag (positiv eingeben)", "500,00")
    dlg.locator("button.primary").click()
    expect(page.locator("dialog")).to_have_count(0)
    e = world["s"].state()["entries"][0]
    assert e["amount"] == 50000 and e["to_account_id"] == world["tg"]["id"]


@pytest.mark.contract("FE-ENTRIES-008")
def test_switching_away_from_transfer_sends_null_target(world, app_page):
    """FE-ENTRIES-008: a hidden Zielkonto is sent as null, not its earlier value."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    put_value(dlg, "Typ", "Umbuchung zwischen Konten")
    put_value(dlg, "Zielkonto", "Tagesgeld")
    put_value(dlg, "Typ", "Ausgabe")
    expect(field(dlg, "Zielkonto")).to_have_count(0)
    put_value(dlg, "Bezeichnung", "Doch Ausgabe")
    put_value(dlg, "Betrag (positiv eingeben)", "10")
    dlg.locator("button.primary").click()
    expect(page.locator("dialog")).to_have_count(0)
    assert world["s"].state()["entries"][0]["to_account_id"] is None


@pytest.mark.contract("FE-ENTRIES-009")
def test_einmalig_hides_rhythm_and_end_date(world, app_page):
    """FE-ENTRIES-009: 'Einmalig' hides Rhythmus and 'Letzte Fälligkeit (optional)'."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    expect(field(dlg, "Rhythmus")).to_have_count(1)
    expect(field(dlg, "Letzte Fälligkeit (optional)")).to_have_count(1)
    put_value(dlg, "Häufigkeit", "Einmalig")
    expect(field(dlg, "Rhythmus")).to_have_count(0)
    expect(field(dlg, "Letzte Fälligkeit (optional)")).to_have_count(0)


@pytest.mark.contract("FE-ENTRIES-010", "FE-ENTRIES-011")
def test_edit_prefills_sends_expected_updated_at_and_shows_the_retroactive_note(world, app_page):
    """FE-ENTRIES-010/011: edit pre-fills, PUT carries expected_updated_at, toast 'Gespeichert', info note mentions Anpassungen."""
    e = world["s"].entry(world["giro"]["id"], "Miete", -120000, "2026-01-01", category="Wohnen")
    page = open_entries(app_page)
    row_of(page, "Miete").get_by_role("button", name="Bearbeiten").click()
    dlg = page.locator("dialog")
    expect(field(dlg, "Bezeichnung").locator("input")).to_have_value("Miete")
    expect(field(dlg, "Kategorie").locator("input")).to_have_value("Wohnen")
    assert "Anpassungen" in norm(dlg.inner_text())
    sent = []
    page.on("request", lambda r: sent.append(r) if r.method == "PUT" and "/api/entries/" in r.url else None)
    put_value(dlg, "Bezeichnung", "Miete neu")
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Gespeichert")
    expect(row_of(page, "Miete neu")).to_be_visible()
    assert len(sent) == 1 and json.loads(sent[0].post_data)["expected_updated_at"] == e["updated_at"]


@pytest.mark.contract("FE-ENTRIES-011")
def test_new_entry_dialog_has_no_retroactive_note(world, app_page):
    """FE-ENTRIES-011: the 'acts retroactively' note belongs to editing only."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    assert "Anpassungen" not in norm(dlg.inner_text())


@pytest.mark.contract("FE-ENTRIES-012", "E2E-BOOK-009")
def test_server_validation_error_is_shown_inline_and_dialog_stays_open(world, app_page):
    """FE-ENTRIES-012: a transfer to the same account shows 'Quell- und Zielkonto müssen verschieden sein.' in the open dialog."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    put_value(dlg, "Typ", "Umbuchung zwischen Konten")
    put_value(dlg, "Bezeichnung", "Kreis")
    put_value(dlg, "Zielkonto", "Giro")
    put_value(dlg, "Betrag (positiv eingeben)", "5")
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text("Quell- und Zielkonto müssen verschieden sein.")
    expect(page.locator("dialog")).to_have_count(1)
    assert world["s"].state()["entries"] == []


@pytest.mark.contract("E2E-BOOK-011")
def test_zero_amount_is_rejected_with_the_german_message(world, app_page):
    """E2E-BOOK-011: amount 0 -> 'Der Betrag darf nicht 0 sein.' and nothing is saved."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    put_value(dlg, "Bezeichnung", "Null")
    put_value(dlg, "Betrag (positiv eingeben)", "0")
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text("Der Betrag darf nicht 0 sein.")
    assert world["s"].state()["entries"] == []


@pytest.mark.contract("E2E-BOOK-012")
def test_empty_required_field_blocks_without_a_request(world, app_page):
    """E2E-BOOK-012: a required field left empty -> 'Bitte „<label>“ ausfüllen.' and no request is sent."""
    page = open_entries(app_page)
    dlg = new_entry(page)
    posts = []
    page.on("request", lambda r: posts.append(r) if r.method == "POST" else None)
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text(re.compile(r"Bitte „.+“ ausfüllen\."))
    assert posts == []


@pytest.mark.contract("E2E-BOOK-013")
def test_second_tab_saving_a_stale_booking_gets_the_conflict_message(world, app_page, context):
    """E2E-BOOK-013: when another tab already changed the booking, the stale save shows the conflict message."""
    world["s"].entry(world["giro"]["id"], "Miete", -120000, "2026-01-01")
    page1 = open_entries(app_page)
    page2 = context.new_page()
    page2.goto("/#buchungen")
    row_of(page1, "Miete").get_by_role("button", name="Bearbeiten").click()
    row_of(page2, "Miete").get_by_role("button", name="Bearbeiten").click()
    d1, d2 = page1.locator("dialog"), page2.locator("dialog")
    put_value(d1, "Bezeichnung", "Erste")
    d1.locator("button.primary").click()
    expect(page1.locator("#toast")).to_contain_text("Gespeichert")
    put_value(d2, "Bezeichnung", "Zweite")
    d2.locator("button.primary").click()
    expect(d2.locator(".err")).to_contain_text("Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen.")
    assert world["s"].state()["entries"][0]["name"] == "Erste"


# ---------------------------------------------------------------------------- archive / restore / history

@pytest.mark.contract("FE-ENTRIES-013", "E2E-ARCH-001", "E2E-ARCH-003")
def test_archive_and_restore_from_the_list(world, app_page):
    """FE-ENTRIES-013: Archivieren (with confirmation) hides the row; Wiederherstellen brings it back."""
    world["s"].entry(world["giro"]["id"], "Miete", -100)
    page = open_entries(app_page)
    row_of(page, "Miete").get_by_role("button", name="Archivieren").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Archiviert")
    expect(rows(page).filter(has_text="Miete")).to_have_count(0)
    page.get_by_label("Archivierte zeigen").check()
    row_of(page, "Miete").get_by_role("button", name="Wiederherstellen").click()
    expect(page.locator("#toast")).to_contain_text("Wiederhergestellt")
    page.get_by_label("Archivierte zeigen").uncheck()
    expect(row_of(page, "Miete")).to_be_visible()


@pytest.mark.contract("FE-ENTRIES-014", "E2E-ARCH-010")
def test_verlauf_opens_the_records_history_dialog(world, app_page):
    """FE-ENTRIES-014: 'Verlauf' opens that entry's history in a modal with a 'Schließen' button."""
    world["s"].entry(world["giro"]["id"], "Miete", -100)
    page = open_entries(app_page)
    row_of(page, "Miete").get_by_role("button", name="Verlauf").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    expect(dlg).to_contain_text("Angelegt")
    dlg.get_by_role("button", name="Schließen").click()
    expect(page.locator("dialog")).to_have_count(0)


# ---------------------------------------------------------------------------- adjustments

@pytest.fixture
def salary(world, app_page):
    return world["s"].entry(world["giro"]["id"], "Gehalt", 300000, "2026-01-31")


def open_adjustments(page, name="Gehalt"):
    row_of(page, name).get_by_role("button", name=re.compile("Anpassung")).click()
    dlg = page.locator("dialog").last
    expect(dlg).to_be_visible()
    return dlg


@pytest.mark.contract("FE-ENTRIES-015", "FE-ENTRIES-016")
def test_adjustments_dialog_lists_sorted_by_date_with_labels(world, app_page, salary):
    """FE-ENTRIES-015/016: sorted by effective date; set -> 'neuer Betrag <eur>', percent -> '<±p> %' + ' jährlich wiederkehrend'."""
    s = world["s"]
    s.adjustment(salary["id"], "2026-09-01", mode="percent", percent=2.5, repeat_yearly=True, note="Inflation")
    s.adjustment(salary["id"], "2026-03-01", amount=320000, note="Raise")
    s.adjustment(salary["id"], "2026-06-01", mode="percent", percent=-3.0)
    page = open_entries(app_page)
    dlg = open_adjustments(page)
    text = norm(dlg.inner_text())
    assert text.index("neuer Betrag 3.200,00 €") < text.index("-3 %") < text.index("2,5 %")
    assert "jährlich wiederkehrend" in text.split("2,5 %")[1] and "jährlich wiederkehrend" not in text.split("2,5 %")[0]
    assert "Raise" in text and "Inflation" in text
    assert text.index("1.3.2026") < text.index("1.6.2026") < text.index("1.9.2026") or text.index("01.03.2026") < text.index("01.09.2026")


@pytest.mark.contract("FE-ENTRIES-017", "E2E-BOOK-005")
def test_new_adjustment_form_fields_depend_on_the_kind(world, app_page, salary):
    """FE-ENTRIES-017: 'Gültig ab', 'Art der Änderung', and per kind 'Neuer Betrag' or 'Änderung in %' + yearly checkbox, 'Notiz'."""
    page = open_entries(app_page)
    open_adjustments(page).get_by_role("button", name="+ Anpassung").click()
    form = page.locator("dialog").last
    for label in ("Gültig ab", "Art der Änderung", "Notiz"):
        expect(field(form, label)).to_have_count(1)
    assert field(form, "Art der Änderung").locator("option").all_inner_texts() == ["Neuer fester Betrag", "Prozentuale Änderung"]
    put_value(form, "Art der Änderung", "Neuer fester Betrag")
    expect(field(form, "Neuer Betrag")).to_have_count(1)
    expect(field(form, "Änderung in %")).to_have_count(0)
    expect(field(form, "Jedes Jahr erneut anwenden")).to_have_count(0)
    put_value(form, "Art der Änderung", "Prozentuale Änderung")
    expect(field(form, "Neuer Betrag")).to_have_count(0)
    expect(field(form, "Änderung in %")).to_have_count(1)
    expect(field(form, "Jedes Jahr erneut anwenden").locator("input[type=checkbox]")).to_have_count(1)


@pytest.mark.contract("FE-ENTRIES-017", "FE-ENTRIES-019", "E2E-BOOK-005")
def test_saving_a_set_adjustment_updates_the_list_and_the_booking_row(world, app_page, salary):
    """FE-ENTRIES-017/019: saving 'Neuer fester Betrag 3.200,00' lists 'neuer Betrag 3.200,00 €'; after closing the row says '1 Anpassung'."""
    page = open_entries(app_page)
    dlg = open_adjustments(page)
    dlg.get_by_role("button", name="+ Anpassung").click()
    form = page.locator("dialog").last
    put_value(form, "Gültig ab", "2026-03-01")
    put_value(form, "Art der Änderung", "Neuer fester Betrag")
    put_value(form, "Neuer Betrag", "3.200,00")
    form.locator("button.primary").click()
    expect(page.locator("dialog").last).to_contain_text("neuer Betrag 3.200,00 €")
    page.locator("dialog").last.get_by_role("button", name=re.compile("Schließen|Fertig")).click()
    expect(page.locator("dialog")).to_have_count(0)
    expect(row_of(page, "Gehalt")).to_contain_text("1 Anpassung")
    assert [a["amount"] for a in world["s"].state()["adjustments"]] == [320000]


@pytest.mark.contract("FE-ENTRIES-018")
def test_set_adjustment_keeps_the_entrys_sign(world, app_page):
    """FE-ENTRIES-018: for an expense a typed positive 'Neuer Betrag' is stored negative; for a transfer it stays positive."""
    s, g, t = world["s"], world["giro"], world["tg"]
    s.entry(g["id"], "Miete", -120000, "2026-01-01")
    s.entry(g["id"], "Sparen", 50000, "2026-02-05", to_account_id=t["id"])
    page = open_entries(app_page)
    for name, typed in (("Miete", "1.300,00"), ("Sparen", "600,00")):
        open_adjustments(page, name).get_by_role("button", name="+ Anpassung").click()
        form = page.locator("dialog").last
        put_value(form, "Gültig ab", "2026-04-01")
        put_value(form, "Art der Änderung", "Neuer fester Betrag")
        put_value(form, "Neuer Betrag", typed)
        form.locator("button.primary").click()
        expect(page.locator("dialog").last).to_contain_text("neuer Betrag")
        page.locator("dialog").last.get_by_role("button", name=re.compile("Schließen|Fertig")).click()
        expect(page.locator("dialog")).to_have_count(0)
    by_entry = {a["entry_id"]: a["amount"] for a in s.state()["adjustments"]}
    ids = {e["name"]: e["id"] for e in s.state()["entries"]}
    assert by_entry[ids["Miete"]] == -130000 and by_entry[ids["Sparen"]] == 60000


@pytest.mark.contract("FE-ENTRIES-017")
def test_saving_a_yearly_percent_adjustment(world, app_page, salary):
    """FE-ENTRIES-017: 'Prozentuale Änderung' with 'Jedes Jahr erneut anwenden' stores percent + repeat_yearly."""
    page = open_entries(app_page)
    open_adjustments(page).get_by_role("button", name="+ Anpassung").click()
    form = page.locator("dialog").last
    put_value(form, "Gültig ab", "2026-01-01")
    put_value(form, "Art der Änderung", "Prozentuale Änderung")
    put_value(form, "Änderung in %", "2.5")      # a number input: plain decimal point
    put_value(form, "Jedes Jahr erneut anwenden", True)
    form.locator("button.primary").click()
    expect(page.locator("dialog").last).to_contain_text("jährlich wiederkehrend")
    a = world["s"].state()["adjustments"][0]
    assert a["mode"] == "percent" and a["percent"] == 2.5 and a["repeat_yearly"] is True and a["amount"] is None


@pytest.mark.contract("FE-ENTRIES-015")
def test_adjustment_can_be_archived_and_restored_from_its_list(world, app_page, salary):
    """FE-ENTRIES-015: each adjustment has archive (or restore) actions."""
    world["s"].adjustment(salary["id"], "2026-03-01", amount=320000)
    page = open_entries(app_page)
    dlg = open_adjustments(page)
    dlg.get_by_role("button", name="Archivieren").first.click()
    confirm = page.locator("dialog").filter(has_text="Grund (optional)")
    try:                                    # whether adjustments ask for confirmation is not specified (F-28)
        confirm.wait_for(timeout=1500)
        confirm.locator("button.primary").click()
    except Exception:                       # noqa: BLE001 - no confirmation dialog appeared
        pass
    expect(page.locator("dialog").last.get_by_role("button", name="Wiederherstellen")).to_have_count(1)
    assert world["s"].state()["adjustments"][0]["archived"] is True
    expect(page.locator("dialog").last.get_by_role("button", name="Wiederherstellen")).to_have_count(1)


# ---------------------------------------------------------------------------- category suggestions

@pytest.mark.contract("FE-ENTRIES-020")
def test_category_field_suggests_known_categories(world, app_page):
    """FE-ENTRIES-020: one suggestion per case-insensitive name, majority spelling, most used first, archived count."""
    s, giro = world["s"], world["giro"]["id"]
    for name, cat in [("A", "Lebensmittel"), ("B", "Lebensmittel"), ("C", "lebensmittel"),
                      ("D", "Wohnen"), ("E", "Auto"), ("F", "Auto"), ("G", "")]:
        s.entry(giro, name, -100, category=cat)
    old = s.entry(giro, "H", -100, category="Urlaub")
    s.c.post(f"/api/entries/{old['id']}/archive", json={})
    page = open_entries(app_page)
    dlg = new_entry(page)
    inp = field(dlg, "Kategorie").locator("input")
    list_id = inp.get_attribute("list")
    assert list_id
    options = dlg.locator(f"datalist[id='{list_id}'] option").evaluate_all("os => os.map(o => o.value)")
    assert options == ["Lebensmittel", "Auto", "Urlaub", "Wohnen"]


@pytest.mark.contract("FE-ENTRIES-020")
def test_category_field_accepts_a_new_category(world, app_page):
    """FE-ENTRIES-020: the field stays free text, so a category nobody used yet can be saved."""
    world["s"].entry(world["giro"]["id"], "Miete", -100, category="Wohnen")
    page = open_entries(app_page)
    dlg = new_entry(page)
    put_value(dlg, "Bezeichnung", "Kino")
    put_value(dlg, "Betrag", "12,50")
    put_value(dlg, "Kategorie", "Freizeit")
    dlg.get_by_role("button", name="Speichern").click()
    expect(page.locator("dialog")).to_have_count(0)
    saved = [e for e in world["s"].state()["entries"] if e["name"] == "Kino"]
    assert [e["category"] for e in saved] == ["Freizeit"]
