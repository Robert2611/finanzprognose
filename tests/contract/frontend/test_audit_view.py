import re

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import norm


def open_audit(app_page):
    return app_page.open("verlauf")


def rows(page):
    return page.locator("#main table tbody tr")


@pytest.fixture
def s(app_page):
    return app_page.seed


def rename(s, account, name, **extra):
    r = s.c.put(f"/api/accounts/{account['id']}", json={"name": name, "kind": "checking", **extra})
    assert r.status_code == 200, r.text


@pytest.mark.contract("FE-AUDIT-001")
def test_view_structure_and_newest_first_rows(s, app_page):
    """FE-AUDIT-001: heading 'Änderungsverlauf', headers Zeitpunkt/Aktion/Objekt/Änderung, newest first with #id."""
    a = s.account("X")
    rename(s, a, "Y")
    page = open_audit(app_page)
    expect(page.locator(".toolbar")).to_contain_text("Änderungsverlauf")
    heads = [norm(h) for h in page.locator("#main table thead th").all_inner_texts()]
    assert heads[:4] == ["Zeitpunkt", "Aktion", "Objekt", "Änderung"]
    ids = [int(re.search(r"#(\d+)", norm(t)).group(1)) for t in rows(page).all_inner_texts()]
    assert len(ids) == 3 and ids == sorted(ids, reverse=True)
    expect(rows(page).first.get_by_role("button", name="Rückgängig")).to_have_count(1)


@pytest.mark.contract("FE-AUDIT-002")
def test_actions_are_shown_in_german(s, app_page):
    """FE-AUDIT-002: create/update/archive/restore/revert -> Angelegt/Geändert/Archiviert/Wiederhergestellt/Rückgängig."""
    a = s.account("X")
    rename(s, a, "Y")
    s.c.post(f"/api/accounts/{a['id']}/archive", json={})
    s.c.post(f"/api/accounts/{a['id']}/restore", json={})
    upd = [r for r in s.c.get("/api/audit").json() if r["action"] == "update"][0]
    s.c.post(f"/api/audit/{upd['id']}/revert")
    page = open_audit(app_page)
    first_cells = [norm(r.locator("td").nth(1).inner_text()) for r in rows(page).all()]
    assert first_cells[:5] == ["Rückgängig", "Wiederhergestellt", "Archiviert", "Geändert", "Angelegt"] or \
        all(any(w in c for c in first_cells) for w in ("Rückgängig", "Wiederhergestellt", "Archiviert", "Geändert", "Angelegt"))


@pytest.mark.contract("FE-AUDIT-003", "E2E-ARCH-006")
def test_update_row_shows_only_changed_fields_old_to_new(s, app_page):
    """FE-AUDIT-003: an update lists only the changed fields as 'Name: X → Y'."""
    a = s.account("X", note="gleich")
    rename(s, a, "Y", note="gleich")
    page = open_audit(app_page)
    top = norm(rows(page).first.inner_text())
    assert "Geändert" in top and "Konto" in top and "Name: X → Y" in top
    assert "gleich" not in top and "Kontoart" not in top


@pytest.mark.contract("FE-AUDIT-003")
def test_create_row_lists_the_created_values(s, app_page):
    """FE-AUDIT-003: a create row (no before) lists the created field values."""
    s.account("Giro", kind="savings", note="Notizfeld")
    page = open_audit(app_page)
    acc_row = [norm(t) for t in rows(page).all_inner_texts() if "Angelegt" in t and "Konto" in t and "Ist-Stand" not in t][0]
    assert "Giro" in acc_row and "Tagesgeld" in acc_row and "Notizfeld" in acc_row


@pytest.mark.contract("FE-AUDIT-004")
def test_values_are_rendered_with_german_formatters(s, app_page):
    """FE-AUDIT-004: amounts as EUR, account ids as names, dates formatted, booleans ja/nein, kind/mode as German words."""
    a = s.account("Giro", 100000, "2026-01-15")
    b = s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    e = s.entry(a["id"], "Sparen", 50000, "2026-02-05", to_account_id=b["id"], interval_months=3)
    s.adjustment(e["id"], "2026-03-01", mode="percent", percent=2.0, repeat_yearly=True)
    page = open_audit(app_page)
    text = norm(" | ".join(rows(page).all_inner_texts()))
    assert "500,00 €" in text and "1.000,00 €" in text
    assert "Giro" in text and "Tagesgeld" in text
    assert re.search(r"5\.2\.2026|05\.02\.2026", text)
    assert "ja" in text and "quartalsweise" in text
    assert not re.search(r"\b(recurring|percent|true|false)\b", text)


@pytest.mark.contract("FE-AUDIT-005")
def test_comment_is_shown_in_quotes(s, app_page):
    """FE-AUDIT-005: a row with a comment shows it as „<comment>“."""
    a = s.account("X")
    s.c.post(f"/api/accounts/{a['id']}/archive", json={"comment": "nicht mehr genutzt"})
    page = open_audit(app_page)
    assert "„nicht mehr genutzt“" in norm(rows(page).first.inner_text())


@pytest.mark.contract("FE-AUDIT-006", "FE-AUDIT-007", "E2E-ARCH-007")
def test_revert_confirmation_toast_and_new_revert_row(s, app_page):
    """FE-AUDIT-006/007: 'Rückgängig' asks for confirmation; confirming reverts, toasts 'Rückgängig gemacht' and adds a revert row on top."""
    a = s.account("X")
    rename(s, a, "Y")
    page = open_audit(app_page)
    upd_id = int(re.search(r"#(\d+)", rows(page).first.inner_text()).group(1))
    rows(page).first.get_by_role("button", name="Rückgängig").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    assert s.state()["accounts"][0]["name"] == "Y"        # nothing happens before confirming
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Rückgängig gemacht")
    # the toast shows before the list reloads, so wait for the new revert row on top
    expect(rows(page).first).to_contain_text(f"Rückgängig gemacht: Protokolleintrag #{upd_id}")
    top = norm(rows(page).first.inner_text())
    assert "Rückgängig" in top and f"Rückgängig gemacht: Protokolleintrag #{upd_id}" in top
    assert s.state()["accounts"][0]["name"] == "X"


@pytest.mark.contract("FE-AUDIT-006")
def test_cancelling_the_revert_dialog_changes_nothing(s, app_page):
    """FE-AUDIT-006: cancelling the confirmation leaves data and history untouched."""
    a = s.account("X")
    rename(s, a, "Y")
    page = open_audit(app_page)
    n = rows(page).count()
    rows(page).first.get_by_role("button", name="Rückgängig").click()
    page.locator("dialog").get_by_role("button", name="Abbrechen").click()
    expect(page.locator("dialog")).to_have_count(0)
    assert rows(page).count() == n and s.state()["accounts"][0]["name"] == "Y"


@pytest.mark.contract("FE-AUDIT-008")
def test_older_page_button_appears_only_after_a_full_page(s, app_page):
    """FE-AUDIT-008: 'Ältere laden' shows when 200 rows came back and appends the next older page."""
    a = s.account("X")
    for i in range(205):
        rename(s, a, f"n{i}")
    page = open_audit(app_page)
    expect(rows(page)).to_have_count(200)
    older = page.get_by_role("button", name="Ältere laden")
    expect(older).to_have_count(1)
    older.click()
    expect(rows(page)).to_have_count(207)
    expect(page.get_by_role("button", name="Ältere laden")).to_have_count(0)


@pytest.mark.contract("FE-AUDIT-008")
def test_no_older_page_button_for_a_short_history(s, app_page):
    """FE-AUDIT-008: with fewer than 200 rows there is no 'Ältere laden' button."""
    s.account("X")
    page = open_audit(app_page)
    expect(rows(page)).to_have_count(2)
    expect(page.get_by_role("button", name="Ältere laden")).to_have_count(0)


@pytest.mark.contract("FE-AUDIT-009", "E2E-ARCH-010")
def test_history_dialog_for_a_record_closes_and_refreshes(s, app_page):
    """FE-AUDIT-009: the per-record history dialog lists only that record's rows and has 'Schließen'."""
    a = s.account("Giro", 100000, "2026-01-15")
    e = s.entry(a["id"], "Miete", -100)
    other = s.account("Andere")
    rename(s, other, "Andere2")
    s.c.put(f"/api/entries/{e['id']}", json={"account_id": a["id"], "to_account_id": None, "name": "Miete", "category": "",
                                              "kind": "recurring", "amount": -200, "start_date": "2026-01-01", "end_date": None,
                                              "interval_months": 1, "note": ""})
    page = app_page.open("buchungen")
    page.locator("#main table tbody tr").filter(has_text="Miete").get_by_role("button", name="Verlauf").click()
    dlg = page.locator("dialog")
    expect(dlg).to_have_count(1)
    body = norm(dlg.inner_text())
    assert "Angelegt" in body and "Geändert" in body and "Miete" in body
    assert "Andere2" not in body and body.count("Angelegt") == 1 and "Konto" in body
    dlg.get_by_role("button", name="Schließen").click()
    expect(page.locator("dialog")).to_have_count(0)
