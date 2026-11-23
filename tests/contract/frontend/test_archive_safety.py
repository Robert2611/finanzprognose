"""B-017/B-018: archive/restore are optimistic-locked, and archiving a used account warns first (browser tests)."""
import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import norm

CONFLICT = "Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen."


def entry_body(e, **patch):
    keys = ("account_id", "to_account_id", "name", "category", "kind", "amount", "start_date", "end_date",
            "interval_months", "estimated", "note")
    return {**{k: e[k] for k in keys}, **patch}


@pytest.fixture
def world(app_page):
    s = app_page.seed
    giro, tg = s.account("Giro", 100000, "2026-01-15"), s.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    return {"s": s, "giro": giro, "tg": tg}


def card_of(page, name):
    return page.locator("#main .cards > .panel").filter(has_text=name).first


def entry_row(page, name):
    return page.locator("#main table tbody tr").filter(has_text=name).first


# ---------------------------------------------------------------------------- B-017: locking

@pytest.mark.contract("FE-FORM-016")
def test_archiving_a_booking_changed_elsewhere_shows_the_conflict(world, app_page):
    """FE-FORM-016: the archive dialog sends expected_updated_at; a stale row gets the conflict message, nothing is archived."""
    s = world["s"]
    e = s.entry(world["giro"]["id"], "Miete", -120000)
    page = app_page.open("buchungen")
    entry_row(page, "Miete").get_by_role("button", name="Archivieren").click()
    assert s.c.put(f"/api/entries/{e['id']}", json=entry_body(e, name="Miete neu")).status_code == 200
    dlg = page.locator("dialog")
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text(CONFLICT)
    assert s.state()["entries"][0]["archived"] is False


@pytest.mark.contract("FE-FORM-016")
def test_archive_sends_the_rows_updated_at(world, app_page):
    """FE-FORM-016: a normal archive posts expected_updated_at equal to the row's updated_at and succeeds."""
    e = world["s"].entry(world["giro"]["id"], "Miete", -120000)
    page = app_page.open("buchungen")
    with page.expect_request(lambda r: r.url.endswith("/archive")) as req:
        entry_row(page, "Miete").get_by_role("button", name="Archivieren").click()
        page.locator("dialog button.primary").click()
    assert req.value.post_data_json["expected_updated_at"] == e["updated_at"]
    expect(page.locator("#toast")).to_contain_text("Archiviert")


@pytest.mark.contract("FE-FORM-016")
def test_restoring_a_stale_row_toasts_the_conflict_and_reloads(world, app_page):
    """FE-FORM-016: restoreRow on a row changed elsewhere shows an error toast; the view reloads to the current state."""
    s = world["s"]
    e = s.entry(world["giro"]["id"], "Miete", -120000)
    e = s.c.post(f"/api/entries/{e['id']}/archive", json={}).json()
    page = app_page.open("buchungen")
    page.get_by_label("Archivierte zeigen").check()
    expect(entry_row(page, "Miete")).to_be_visible()
    assert s.c.put(f"/api/entries/{e['id']}", json=entry_body(e, name="Miete alt")).status_code == 200
    entry_row(page, "Miete").get_by_role("button", name="Wiederherstellen").click()
    expect(page.locator("#toast")).to_contain_text(CONFLICT)
    expect(entry_row(page, "Miete alt")).to_be_visible()
    assert s.state()["entries"][0]["archived"] is True


# ---------------------------------------------------------------------------- B-018: archiving a used account

@pytest.mark.contract("FE-ACCOUNTS-013")
def test_archive_dialog_lists_what_still_uses_the_account(world, app_page):
    """FE-ACCOUNTS-013: own bookings, transfers from and to the account and its Ist-Stände are listed; nothing else is archived."""
    s, giro, tg = world["s"], world["giro"]["id"], world["tg"]["id"]
    s.entry(tg, "Zinsen", 300, interval_months=3)
    s.entry(tg, "Entnahme", 20000, to_account_id=giro)
    s.entry(giro, "Sparen", 50000, to_account_id=tg)
    s.entry(giro, "Miete", -120000)
    old = s.entry(tg, "Altbuchung", -100)
    s.c.post(f"/api/entries/{old['id']}/archive", json={})
    page = app_page.open("konten")
    card_of(page, "Tagesgeld").get_by_role("button", name="Archivieren", exact=True).first.click()
    notice = page.locator("dialog .banner.warn.usage")
    expect(notice).to_contain_text("Dieses Konto wird noch verwendet.")
    items = [norm(t) for t in notice.locator("li").all_inner_texts()]
    assert items == [
        "1 Buchung: „Zinsen“ – fließen nicht mehr in die Prognose ein.",
        "1 Umbuchung von diesem Konto: „Entnahme“ – fließen nicht mehr in die Prognose ein, auch nicht beim Zielkonto.",
        "1 Umbuchung auf dieses Konto: „Sparen“ – werden weiter vom Quellkonto abgebucht.",
        "1 Ist-Stand",
    ]
    page.locator("dialog button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Archiviert")
    st = s.state()
    assert [a["archived"] for a in st["accounts"] if a["id"] == tg] == [True]
    assert all(not e["archived"] for e in st["entries"] if e["name"] != "Altbuchung")


@pytest.mark.contract("FE-ACCOUNTS-013")
def test_no_warning_for_an_unused_account(world, app_page):
    """FE-ACCOUNTS-013: an account with only its Ist-Stände has no usage warning."""
    page = app_page.open("konten")
    card_of(page, "Tagesgeld").get_by_role("button", name="Archivieren", exact=True).first.click()
    expect(page.locator("dialog")).to_have_count(1)
    expect(page.locator("dialog .banner.usage")).to_have_count(0)


@pytest.mark.contract("FC-028", "FE-CORE-024")
def test_forecast_keeps_the_outflow_to_an_archived_account(world, app_page):
    """FC-028/FE-CORE-024: after archiving the target, Giro still shows the transfer and the warning explains it."""
    s, giro, tg = world["s"], world["giro"]["id"], world["tg"]["id"]
    s.entry(giro, "Sparen", 50000, "2026-02-05", to_account_id=tg)
    s.c.post(f"/api/accounts/{tg}/archive", json={})
    page = app_page.open()
    expect(page.locator("#warn")).to_contain_text("Umbuchung „Sparen“: Zielkonto „Tagesgeld“ ist archiviert – berücksichtigt wird nur die Abbuchung vom Quellkonto.")
