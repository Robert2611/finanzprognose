"""B-014: the Buchungen and Verlauf tables grow with the page instead of scrolling inside it (browser tests)."""
import pytest
from playwright.sync_api import expect

ROWS = 60  # far more than fit into one viewport


def assert_page_scrolls(page):
    wrap = page.locator("#main .table-wrap")
    # the table is not cut off: the wrapper is as tall as its content, and the document is taller than the viewport
    assert wrap.evaluate("w => w.scrollHeight <= w.clientHeight + 1")
    assert page.evaluate("() => document.documentElement.scrollHeight > window.innerHeight")
    # after scrolling the page, the column headers sit right below the app header
    page.mouse.wheel(0, 3000)
    page.wait_for_function("() => window.scrollY > 0")
    header_bottom = page.evaluate("() => document.querySelector('header').getBoundingClientRect().bottom")
    th_top = page.locator("#main table thead th").first.evaluate("th => th.getBoundingClientRect().top")
    assert abs(th_top - header_bottom) <= 1


@pytest.mark.contract("FE-ENTRIES-028")
def test_bookings_table_scrolls_with_the_page(app_page):
    """FE-ENTRIES-028: a long bookings list has no inner scroll area; the page scrolls and the headers stick."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    for i in range(ROWS):
        s.entry(giro["id"], f"Buchung {i:02d}", -1000)
    page = app_page.open("buchungen")
    expect(page.locator("#main table tbody tr")).to_have_count(ROWS)
    assert_page_scrolls(page)


@pytest.mark.contract("FE-AUDIT-012")
def test_history_table_scrolls_with_the_page(app_page):
    """FE-AUDIT-012: a long history has no inner scroll area; the page scrolls and the headers stick."""
    s = app_page.seed
    giro = s.account("Giro", 100000, "2026-01-15")
    for i in range(ROWS):
        s.entry(giro["id"], f"Buchung {i:02d}", -1000)
    page = app_page.open("verlauf")
    expect(page.locator("#main h2", has_text="Änderungsverlauf")).to_be_visible()
    assert page.locator("#main table tbody tr").count() >= ROWS
    assert_page_scrolls(page)
