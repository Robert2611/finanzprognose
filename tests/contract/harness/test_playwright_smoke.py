"""Self-check: Playwright can load the in-process served SPA."""
from playwright.sync_api import expect


def test_spa_loads(page, live_server):
    page.goto("/")
    expect(page.locator("header .brand")).to_have_text("Finanzprognose")
