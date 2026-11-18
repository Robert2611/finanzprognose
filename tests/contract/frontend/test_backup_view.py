import re

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import norm


@pytest.fixture
def s(app_page):
    return app_page.seed


def open_backup(app_page):
    return app_page.open("sicherung")


def pill(page):
    return page.locator("button#backupPill")


@pytest.mark.contract("FE-BACKUP-001", "E2E-BKP-001")
def test_status_block_shows_target_schedule_version(s, app_page, settings, nas):
    """FE-BACKUP-001: Ziel (dir), Zeitplan text, last success/file/attempt and the Datenstand with its secured/unsecured note."""
    nas.put_marker()
    s.account("Giro")
    page = open_backup(app_page)
    main = page.locator("#main")
    expect(main).to_contain_text("Sicherung")
    expect(main.locator("code").first).to_have_text(settings.backup_dir)
    text = norm(main.inner_text())
    assert f"täglich um {settings.backup_time} Uhr, nur bei Änderungen" in text
    for label in ("Ziel", "Zeitplan", "Letzte erfolgreiche", "Letzte Datei", "Letzter Versuch", "Datenstand"):
        assert label in text, label
    assert re.search(r"Version \d+", text) and "ungesicherte Änderungen" in text
    expect(main.get_by_role("button", name="Jetzt sichern")).to_have_count(1)
    expect(main.get_by_role("link", name="Export als JSON herunterladen")).to_have_count(1)


@pytest.mark.contract("FE-BACKUP-002", "FE-BACKUP-004", "E2E-BKP-007")
def test_run_backup_ok_then_unchanged_with_toasts_list_and_pill(s, app_page, nas):
    """FE-BACKUP-002/004/005: 'Jetzt sichern' -> 'Sicherung erstellt'; again -> 'Keine Änderungen seit der letzten Sicherung'; list + pill update."""
    nas.put_marker()
    s.account("Giro")
    page = open_backup(app_page)
    page.get_by_role("button", name="Jetzt sichern").click()
    expect(page.locator("#toast")).to_contain_text("Sicherung erstellt")
    main = page.locator("#main")
    expect(main).to_contain_text("erfolgreich")
    expect(main).to_contain_text("gesichert")
    assert "ungesicherte Änderungen" not in norm(main.inner_text())
    name = nas.backups()[0]
    expect(main.locator("table")).to_contain_text(name)
    assert re.search(re.escape(name) + r".*KB", norm(main.locator("table").inner_text()))
    expect(pill(page)).to_have_class(re.compile(r"\bok\b"))
    expect(pill(page)).to_contain_text("Gesichert")
    page.get_by_role("button", name="Jetzt sichern").click()
    expect(page.locator("#toast")).to_contain_text("Keine Änderungen seit der letzten Sicherung")
    expect(main).to_contain_text("keine Änderungen – nichts zu sichern")
    assert len(nas.backups()) == 1


@pytest.mark.contract("FE-BACKUP-003", "FE-BACKUP-004", "FE-BACKUP-007", "E2E-BKP-003")
def test_failed_backup_shows_error_toast_banner_and_pill(s, app_page, nas):
    """FE-BACKUP-003/004/007: with the marker missing: toast 'Sicherung fehlgeschlagen: …', red banner and pill 'Sicherung fehlgeschlagen!'."""
    s.account("Giro")
    page = open_backup(app_page)
    page.get_by_role("button", name="Jetzt sichern").click()
    expect(page.locator("#toast")).to_contain_text("Sicherung fehlgeschlagen:")
    banner = page.locator("#main .banner.err")
    expect(banner).to_have_count(1)
    expect(banner).to_contain_text("Letzte Sicherung fehlgeschlagen:")
    expect(banner).to_contain_text(".nas-marker")
    expect(page.locator("#main")).to_contain_text("FEHLER")
    expect(pill(page)).to_have_class(re.compile(r"\berr\b"))
    expect(pill(page)).to_have_text("Sicherung fehlgeschlagen!")


@pytest.mark.contract("FE-BACKUP-005")
def test_empty_backup_list(s, app_page):
    """FE-BACKUP-005: no backups -> 'Keine Sicherungen gefunden.'."""
    s.account("Giro")
    page = open_backup(app_page)
    expect(page.locator("#main")).to_contain_text("Vorhandene Sicherungen (neueste 30)")
    expect(page.locator("#main")).to_contain_text("Keine Sicherungen gefunden.")


@pytest.mark.contract("FE-BACKUP-005")
def test_backup_list_is_capped_at_thirty(s, app_page, nas):
    """FE-BACKUP-005: at most the newest 30 backups are listed."""
    nas.put_marker()
    a = s.account("Giro")
    for i in range(32):
        s.c.put(f"/api/accounts/{a['id']}", json={"name": f"G{i}", "kind": "checking"})
        assert s.c.post("/api/backup/run").json()["last_result"] == "ok"
    page = open_backup(app_page)
    expect(page.locator("#main table tbody tr")).to_have_count(30)


@pytest.mark.contract("FE-BACKUP-006", "E2E-BKP-001")
def test_export_link_points_to_the_json_export(s, app_page):
    """FE-BACKUP-006: 'Export als JSON herunterladen' is a link to /api/export."""
    page = open_backup(app_page)
    link = page.get_by_role("link", name="Export als JSON herunterladen")
    assert link.get_attribute("href").endswith("/api/export")
    with page.expect_download() as dl:
        link.click()
    assert re.fullmatch(r"finanzen_export_\d{4}-\d{2}-\d{2}\.json", dl.value.suggested_filename)


@pytest.mark.contract("FE-BACKUP-007")
def test_pill_without_any_backup_is_a_warning(s, app_page):
    """FE-BACKUP-007: before the first backup the pill is 'warn' with 'Noch keine Sicherung'."""
    s.account("Giro")
    page = open_backup(app_page)
    expect(pill(page)).to_have_class(re.compile(r"\bwarn\b"))
    expect(pill(page)).to_have_text("Noch keine Sicherung")


@pytest.mark.contract("FE-BACKUP-007")
def test_pill_shows_pending_changes_after_a_backup(s, app_page, nas):
    """FE-BACKUP-007: after a backup, new changes add ' · neue Änderungen' to the 'Gesichert <time>' pill."""
    nas.put_marker()
    a = s.account("Giro")
    s.c.post("/api/backup/run")
    page = open_backup(app_page)
    expect(pill(page)).to_contain_text("Gesichert")
    assert "neue Änderungen" not in norm(pill(page).inner_text())
    s.c.put(f"/api/accounts/{a['id']}", json={"name": "Neu", "kind": "checking"})
    page.reload()
    expect(pill(page)).to_contain_text("· neue Änderungen")
    expect(pill(page)).to_have_class(re.compile(r"\bok\b"))


@pytest.mark.contract("FE-BACKUP-008", "E2E-AUTH-010")
def test_pill_says_server_unreachable_when_status_fails(s, app_page):
    """FE-BACKUP-008: if GET /api/backup/status fails, the pill is 'err' with 'Server nicht erreichbar'."""
    s.account("Giro")
    page = app_page.page
    page.route("**/api/backup/status", lambda r: r.abort())
    page.goto("/")
    expect(pill(page)).to_have_class(re.compile(r"\berr\b"))
    expect(pill(page)).to_have_text("Server nicht erreichbar")


@pytest.mark.contract("FE-BACKUP-009")
def test_pill_refreshes_periodically(s, app_page, nas):
    """FE-BACKUP-009: the pill polls the status; a backup made elsewhere shows up after the clock advances."""
    nas.put_marker()
    s.account("Giro")
    page = app_page.page
    page.clock.install()
    page.goto("/")
    expect(pill(page)).to_have_text("Noch keine Sicherung")
    assert s.c.post("/api/backup/run").json()["last_result"] == "ok"
    page.clock.run_for("01:00:00")
    expect(pill(page)).to_contain_text("Gesichert")


@pytest.mark.contract("FE-BACKUP-010")
@pytest.mark.parametrize("fail", ["http", "network"])
def test_failed_run_request_shows_error_toast(s, app_page, nas, fail):
    """FE-BACKUP-010: a failing POST /api/backup/run (500 or aborted) shows an error toast instead of doing nothing."""
    nas.put_marker()
    s.account("Giro")
    page = open_backup(app_page)
    if fail == "http":
        page.route("**/api/backup/run", lambda r: r.fulfill(status=500, content_type="application/json", body='{"detail":"kaputt"}'))
    else:
        page.route("**/api/backup/run", lambda r: r.abort())
    page.get_by_role("button", name="Jetzt sichern").click()
    expect(page.locator("#toast .e")).to_contain_text("Sicherung fehlgeschlagen:")
