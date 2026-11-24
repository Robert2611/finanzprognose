import json
import re
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import field, norm, put_value

NOW = datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc)


def open_accounts(app_page):
    app_page.page.clock.install(time=NOW)
    return app_page.open("konten")


def cards(page):
    return page.locator("#main .cards > .panel")


def card_of(page, name):
    return cards(page).filter(has_text=name).first


@pytest.fixture
def s(app_page):
    return app_page.seed


@pytest.mark.contract("FE-ACCOUNTS-001")
def test_empty_state(app_page):
    """FE-ACCOUNTS (interface): no accounts -> 'Noch keine Konten.'."""
    page = open_accounts(app_page)
    expect(page.locator("#main")).to_contain_text("Noch keine Konten.")
    expect(page.locator(".toolbar")).to_contain_text("Konten & Ist-Stände")
    expect(page.locator(".toolbar button.primary")).to_have_text("+ Neues Konto")


@pytest.mark.contract("FE-ACCOUNTS-001", "FE-ACCOUNTS-012")
def test_archived_accounts_only_with_the_checkbox_and_only_restore_offered(s, app_page):
    """FE-ACCOUNTS-001/012: archived accounts show with 'Archivierte zeigen' (class archived), offering only Wiederherstellen."""
    s.account("Aktiv")
    old = s.account("Alt")
    s.c.post(f"/api/accounts/{old['id']}/archive", json={})
    page = open_accounts(app_page)
    expect(cards(page)).to_have_count(1)
    page.get_by_label("Archivierte zeigen").check()
    expect(cards(page)).to_have_count(2)
    alt = card_of(page, "Alt")
    expect(alt).to_have_class(re.compile(r"\barchived\b"))
    expect(alt.get_by_role("button", name="Wiederherstellen")).to_have_count(1)
    # account-level actions only (buttons outside the checkpoint table; row actions on archived accounts are unspecified, F-27)
    head_buttons = alt.locator("xpath=.//button[not(ancestor::table)]")
    assert [b.inner_text().strip() for b in head_buttons.all()] == ["Wiederherstellen"]
    active = card_of(page, "Aktiv").locator("xpath=.//button[not(ancestor::table)]")
    assert [b.inner_text().strip() for b in active.all()] == ["Bearbeiten", "Archivieren", "+ Ist-Stand"]


@pytest.mark.contract("FE-ACCOUNTS-001")
def test_archived_checkpoints_show_with_the_checkbox(s, app_page):
    """FE-ACCOUNTS-001: archived checkpoints are listed (dimmed) only with 'Archivierte zeigen'."""
    a = s.account("Giro", 100000, "2026-01-15")
    cp = s.checkpoint(a["id"], "2026-02-20", 500000)
    s.c.post(f"/api/checkpoints/{cp['id']}/archive", json={})
    page = open_accounts(app_page)
    card = card_of(page, "Giro")
    expect(card.locator("table tbody tr")).to_have_count(1)
    page.get_by_label("Archivierte zeigen").check()
    expect(card.locator("table tbody tr")).to_have_count(2)
    expect(card.locator("table tbody tr.archived")).to_have_count(1)


@pytest.mark.contract("FE-ACCOUNTS-002")
@pytest.mark.parametrize("kind,label", [("checking", "Girokonto"), ("savings", "Tagesgeld"), ("custody", "Depot"),
                                        ("credit_card", "Kreditkarte"), ("cash", "Bargeld"), ("other", "Sonstiges")])
def test_card_shows_name_and_german_kind_tag(s, app_page, kind, label):
    """FE-ACCOUNTS-002: the card shows the account name and the German kind label."""
    s.account("Mein Konto", kind=kind)
    page = open_accounts(app_page)
    card = card_of(page, "Mein Konto")
    expect(card).to_contain_text(label)


@pytest.mark.contract("FE-ACCOUNTS-003", "E2E-CP-001")
def test_letzter_ist_stand_shows_latest_balance_and_date(s, app_page):
    """FE-ACCOUNTS-003: 'Letzter Ist-Stand' shows the most recent active checkpoint's balance and date."""
    a = s.account("Giro", 100000, "2026-01-15")
    page = open_accounts(app_page)
    assert "Letzter Ist-Stand" in norm(card_of(page, "Giro").inner_text())
    assert "1.000,00 € am 15.1.2026" in norm(card_of(page, "Giro").inner_text())
    s.checkpoint(a["id"], "2026-02-20", 500000)
    page.reload()
    assert "5.000,00 € am 20.2.2026" in norm(card_of(page, "Giro").inner_text())


@pytest.mark.contract("FE-ACCOUNTS-003", "E2E-CP-006")
def test_letzter_ist_stand_when_there_is_none(s, app_page):
    """FE-ACCOUNTS-003: with no active checkpoint it reads 'keiner – Konto wird nicht berechnet'."""
    a = s.account("Giro", 100000, "2026-01-15")
    cp = s.state()["checkpoints"][0]
    s.c.post(f"/api/checkpoints/{cp['id']}/archive", json={})
    page = open_accounts(app_page)
    assert "keiner – Konto wird nicht berechnet" in norm(card_of(page, "Giro").inner_text())


@pytest.mark.contract("FE-ACCOUNTS-004", "FE-ACCOUNTS-005")
def test_earliest_checkpoint_is_tagged_startstand_and_list_is_newest_first(s, app_page):
    """FE-ACCOUNTS-004/005: the earliest active checkpoint is tagged 'Startstand'; checkpoints are listed newest-first."""
    a = s.account("Giro", 100000, "2026-01-15")
    s.checkpoint(a["id"], "2026-03-20", 700000)
    s.checkpoint(a["id"], "2026-02-20", 500000)
    page = open_accounts(app_page)
    trs = card_of(page, "Giro").locator("table tbody tr")
    texts = [norm(t) for t in trs.all_inner_texts()]
    assert len(texts) == 3
    assert "20.3.2026" in texts[0] and "20.2.2026" in texts[1] and "15.1.2026" in texts[2]
    assert "Startstand" in texts[2] and "Startstand" not in texts[0] + texts[1]
    assert s.state()["checkpoints"][0]["note"] == ""


@pytest.mark.contract("FE-ACCOUNTS-006", "E2E-ONBOARD-002")
def test_new_account_dialog_fields(app_page):
    """FE-ACCOUNTS-006: 'Name', 'Kontoart', 'Aktueller Kontostand', 'Stand vom (abends)' and 'Notiz'."""
    page = open_accounts(app_page)
    page.get_by_role("button", name="+ Neues Konto").click()
    dlg = page.locator("dialog")
    for label in ("Name", "Kontoart", "Aktueller Kontostand", "Stand vom (abends)", "Notiz"):
        expect(field(dlg, label)).to_have_count(1)
    assert field(dlg, "Kontoart").locator("option").all_inner_texts() == ["Girokonto", "Tagesgeld", "Depot", "Kreditkarte", "Bargeld", "Sonstiges"]


@pytest.mark.contract("FE-ACCOUNTS-007", "E2E-ONBOARD-003")
def test_creating_an_account_posts_start_balance_and_shows_card_with_startstand(s, app_page):
    """FE-ACCOUNTS-007: creating 'Giro' 1.000,00 on 2026-01-15 posts to /api/accounts; the card shows a 'Startstand' row."""
    page = open_accounts(app_page)
    page.get_by_role("button", name="+ Neues Konto").click()
    dlg = page.locator("dialog")
    put_value(dlg, "Name", "Giro")
    put_value(dlg, "Kontoart", "Girokonto")
    put_value(dlg, "Aktueller Kontostand", "1.000,00")
    put_value(dlg, "Stand vom (abends)", "2026-01-15")
    with page.expect_request(lambda r: r.method == "POST" and r.url.endswith("/api/accounts")) as req:
        dlg.locator("button.primary").click()
    body = json.loads(req.value.post_data)
    assert body["start_balance"] == 100000 and body["start_date"] == "2026-01-15" and body["name"] == "Giro"
    expect(page.locator("#toast")).to_contain_text("Gespeichert")
    card = card_of(page, "Giro")
    expect(card).to_contain_text("Startstand")
    assert "1.000,00 €" in norm(card.inner_text()) and "15.1.2026" in norm(card.inner_text())


@pytest.mark.contract("FE-ACCOUNTS-008")
def test_editing_an_account_has_only_name_kind_reserve_note_and_sends_expected_updated_at(s, app_page):
    """FE-ACCOUNTS-008: edit shows Name/Kontoart/Rücklage/Notiz only, and the PUT carries expected_updated_at."""
    a = s.account("Giro", note="alt")
    page = open_accounts(app_page)
    card_of(page, "Giro").get_by_role("button", name="Bearbeiten", exact=True).first.click()
    dlg = page.locator("dialog")
    assert dlg.locator("label.field").count() == 4
    expect(field(dlg, "Rücklage – nicht zum Verplanen")).to_have_count(1)
    expect(field(dlg, "Aktueller Kontostand")).to_have_count(0)
    expect(field(dlg, "Name").locator("input")).to_have_value("Giro")
    put_value(dlg, "Name", "Giro neu")
    with page.expect_request(lambda r: r.method == "PUT" and "/api/accounts/" in r.url) as req:
        dlg.locator("button.primary").click()
    assert json.loads(req.value.post_data)["expected_updated_at"] == a["updated_at"]
    expect(card_of(page, "Giro neu")).to_be_visible()


@pytest.mark.contract("FE-ACCOUNTS-009")
def test_checkpoint_dialog_fields_and_intro(s, app_page):
    """FE-ACCOUNTS-009: '+ Ist-Stand' opens Konto/Datum (Stand am Abend)/Kontostand/Notiz with an end-of-day intro."""
    s.account("Giro")
    page = open_accounts(app_page)
    card_of(page, "Giro").get_by_role("button", name="+ Ist-Stand").click()
    dlg = page.locator("dialog")
    for label in ("Konto", "Datum (Stand am Abend)", "Kontostand", "Notiz"):
        expect(field(dlg, label)).to_have_count(1)
    assert re.search(r"Abend|Tagesende", norm(dlg.inner_text()))


@pytest.mark.contract("FE-ACCOUNTS-010", "E2E-CP-001")
def test_saving_a_checkpoint_refreshes_the_card(s, app_page):
    """FE-ACCOUNTS-010: saving an Ist-Stand toasts 'Gespeichert' and the card's 'Letzter Ist-Stand' shows it."""
    s.account("Giro", 100000, "2026-01-15")
    page = open_accounts(app_page)
    card_of(page, "Giro").get_by_role("button", name="+ Ist-Stand").click()
    dlg = page.locator("dialog")
    put_value(dlg, "Datum (Stand am Abend)", "2026-02-20")
    put_value(dlg, "Kontostand", "5.000,00")
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Gespeichert")
    # the toast shows before the cards reload, so wait for the new value (\s also matches the NBSPs)
    expect(card_of(page, "Giro")).to_contain_text(re.compile(r"5\.000,00\s€\sam\s20\.2\.2026"))


@pytest.mark.contract("FE-ACCOUNTS-011")
def test_archive_and_restore_an_account(s, app_page):
    """FE-ACCOUNTS-011: accounts use the shared archive dialog and restore action, then refresh."""
    s.account("Giro")
    page = open_accounts(app_page)
    card_of(page, "Giro").get_by_role("button", name="Archivieren", exact=True).first.click()
    page.locator("dialog").locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Archiviert")
    expect(page.locator("#main")).to_contain_text("Noch keine Konten.")
    page.get_by_label("Archivierte zeigen").check()
    card_of(page, "Giro").get_by_role("button", name="Wiederherstellen").click()
    expect(page.locator("#toast")).to_contain_text("Wiederhergestellt")
    page.get_by_label("Archivierte zeigen").uncheck()
    expect(card_of(page, "Giro")).to_be_visible()
    expect(page.locator("#main")).not_to_contain_text("Noch keine Konten.")


@pytest.mark.contract("FE-ACCOUNTS-011")
def test_archive_and_restore_a_checkpoint(s, app_page):
    """FE-ACCOUNTS-011: checkpoint rows can be archived and restored too."""
    a = s.account("Giro", 100000, "2026-01-15")
    s.checkpoint(a["id"], "2026-02-20", 500000)
    page = open_accounts(app_page)
    card_of(page, "Giro").locator("table tbody tr").first.get_by_role("button", name="Archivieren").click()
    page.locator("dialog").locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Archiviert")
    assert [c["archived"] for c in s.state()["checkpoints"]] == [False, True]
    page.get_by_label("Archivierte zeigen").check()
    card_of(page, "Giro").locator("table tbody tr.archived").get_by_role("button", name="Wiederherstellen").click()
    expect(page.locator("#toast")).to_contain_text("Wiederhergestellt")
    assert [c["archived"] for c in s.state()["checkpoints"]] == [False, False]


# ---------------------------------------------------------------------------- reserve accounts (B-028)

RESERVE = "Rücklage – nicht zum Verplanen"


@pytest.mark.contract("FE-ACCOUNTS-014")
def test_new_account_can_be_created_as_a_reserve(s, app_page):
    """FE-ACCOUNTS-014: the checkbox starts unchecked, is sent as reserve=true, and the card gets a 'Rücklage' tag."""
    page = open_accounts(app_page)
    page.get_by_role("button", name="+ Neues Konto").click()
    dlg = page.locator("dialog")
    box = field(dlg, RESERVE).locator("input[type=checkbox]")
    expect(box).not_to_be_checked()
    put_value(dlg, "Name", "Notgroschen")
    put_value(dlg, "Kontoart", "Tagesgeld")
    put_value(dlg, "Aktueller Kontostand", "10.000,00")
    put_value(dlg, RESERVE, True)
    with page.expect_request(lambda r: r.method == "POST" and r.url.endswith("/api/accounts")) as req:
        dlg.locator("button.primary").click()
    assert json.loads(req.value.post_data)["reserve"] is True
    expect(card_of(page, "Notgroschen").locator(".tag.reserve")).to_have_text("Rücklage")
    assert s.state()["accounts"][0]["reserve"] is True


@pytest.mark.contract("FE-ACCOUNTS-014")
def test_editing_prefills_and_clears_the_reserve_mark(s, app_page):
    """FE-ACCOUNTS-014: editing a reserve account shows the box checked; unticking sends reserve=false."""
    s.account("Notgroschen", kind="savings", reserve=True)
    s.account("Giro")
    page = open_accounts(app_page)
    expect(card_of(page, "Giro").locator(".tag.reserve")).to_have_count(0)
    card_of(page, "Notgroschen").get_by_role("button", name="Bearbeiten", exact=True).first.click()
    dlg = page.locator("dialog")
    box = field(dlg, RESERVE).locator("input[type=checkbox]")
    expect(box).to_be_checked()
    put_value(dlg, RESERVE, False)
    with page.expect_request(lambda r: r.method == "PUT" and "/api/accounts/" in r.url) as req:
        dlg.locator("button.primary").click()
    assert json.loads(req.value.post_data)["reserve"] is False
    expect(card_of(page, "Notgroschen").locator(".tag.reserve")).to_have_count(0)
