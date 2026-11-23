"""B-020/B-022: German text for backup codes and the „Prüfen“ dialog (browser tests)."""
import json

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import norm


@pytest.fixture
def s(app_page):
    return app_page.seed


def open_backup(app_page):
    page = app_page.open("sicherung")
    expect(page.locator("#main h2", has_text="Sicherung")).to_be_visible()
    return page


@pytest.mark.contract("FE-BACKUP-011", "FE-BACKUP-003")
def test_marker_error_is_shown_in_german(s, app_page, nas):
    """FE-BACKUP-011: marker_missing -> the German sentence, in the toast and in the banner."""
    s.account("Giro")
    page = open_backup(app_page)
    page.get_by_role("button", name="Jetzt sichern").click()
    text = "Datei .nas-marker fehlt im Backup-Ziel – ist das NAS eingebunden? Es wurde nichts gesichert."
    expect(page.locator("#toast")).to_contain_text("Sicherung fehlgeschlagen: " + text)
    expect(page.locator("#main .banner.err")).to_contain_text("Letzte Sicherung fehlgeschlagen: " + text)


@pytest.mark.contract("FE-BACKUP-011", "FE-BACKUP-012")
def test_old_german_status_is_shown_as_is(app_page, settings, nas):
    """FE-BACKUP-011/012: a status file from before B-020 (German strings) still renders unchanged."""
    with open(settings.status_file, "w", encoding="utf-8") as f:
        json.dump({"last_result": "error", "last_reason": "zeitplan", "last_attempt": "2026-01-01T03:00:00",
                   "last_error": "Backup-Ziel /backup existiert nicht."}, f)
    page = open_backup(app_page)
    expect(page.locator("#main .banner.err")).to_contain_text("Backup-Ziel /backup existiert nicht.")
    expect(page.locator("#main .kv")).to_contain_text("(zeitplan)")


@pytest.mark.contract("FE-BACKUP-012")
def test_last_attempt_shows_the_reason(s, app_page, nas):
    """FE-BACKUP-012: after 'Jetzt sichern' the last attempt says '(manuell)'."""
    nas.put_marker()
    s.account("Giro")
    page = open_backup(app_page)
    page.get_by_role("button", name="Jetzt sichern").click()
    expect(page.locator("#toast")).to_contain_text("Sicherung erstellt")
    expect(page.locator("#main .kv")).to_contain_text("(manuell) · erfolgreich")


def make_backup(s, nas):
    nas.put_marker()
    s.account("Giro")
    return s.c.post("/api/backup/run").json()["last_file"]


def open_verify(app_page, name):
    page = open_backup(app_page)
    page.locator("#main tr").filter(has_text=name).get_by_role("button", name="Prüfen").click()
    dlg = page.locator("dialog")
    expect(dlg.locator("h3")).to_have_text("Sicherung prüfen")
    return dlg


@pytest.mark.contract("FE-BACKUP-013")
def test_checking_a_good_backup(s, app_page, nas):
    """FE-BACKUP-013: 'Prüfen' shows the ok banner, versions, checksum state and row counts."""
    name = make_backup(s, nas)
    dlg = open_verify(app_page, name)
    expect(dlg.locator(".banner.ok")).to_have_text("In Ordnung – diese Sicherung ist vollständig lesbar und lässt sich wiederherstellen.")
    expect(dlg).to_contain_text(name)
    kv = norm(dlg.locator(".kv").inner_text())
    v = name.rsplit("_v", 1)[1].removesuffix(".sqlite")
    assert f"Datenstand Version {v} (laut Dateiname v{v})" in kv
    assert "Prüfsumme stimmt mit backups.log überein" in kv
    assert "Konten 1" in kv and "Ist-Stände 1" in kv and "Buchungen 0" in kv
    expect(dlg).to_contain_text("Geprüft wird eine Kopie")
    dlg.get_by_role("button", name="Schließen").click()
    expect(app_page.page.locator("dialog")).to_have_count(0)


@pytest.mark.contract("FE-BACKUP-013")
def test_checking_a_damaged_backup_lists_the_problems(s, app_page, nas):
    """FE-BACKUP-013: a renamed, unlogged copy shows 'Probleme gefunden' with the German problem lines."""
    name = make_backup(s, nas)
    other = name.rsplit("_v", 1)[0] + "_v999.sqlite"
    (nas.path / other).write_bytes((nas.path / name).read_bytes())
    dlg = open_verify(app_page, other)
    err = dlg.locator(".banner.err")
    expect(err).to_contain_text("Probleme gefunden:")
    expect(err.locator("li")).to_have_count(1)
    expect(err).to_contain_text("passt nicht zum Dateinamen (v999)")
    expect(dlg.locator(".kv")).to_contain_text("nicht in backups.log eingetragen")
