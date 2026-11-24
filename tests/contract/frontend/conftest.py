import re

import pytest
from playwright.sync_api import expect


def norm(s):
    """Normalise formatting noise the contract says not to assert: NBSP/narrow NBSP and the typographic minus."""
    if not isinstance(s, str):
        return s
    return re.sub(r"\s+", " ", s.replace(" ", " ").replace(" ", " ").replace("−", "-")).strip()


def call(page, fn, *args):
    """Call an export of /core.js in the page and return its (JSON-serialisable) result."""
    return page.evaluate(
        "async ([fn, args]) => { const m = await import('/core.js'); const v = await m[fn](...args);"
        " return (typeof v === 'number' && Number.isNaN(v)) ? '__NaN__' : v; }", [fn, list(args)])


def prop(page, name):
    return page.evaluate("async (n) => { const m = await import('/core.js'); return m[n]; }", name)


@pytest.fixture
def app_page(page, seed_live):
    """A page already pointed at the app. `seed_live` can create data before `open()` is called."""
    class P:
        def __init__(self):
            self.page, self.seed = page, seed_live

        def open(self, hash_=""):
            page.goto("/" + (f"#{hash_}" if hash_ else ""))
            return page

    return P()


def field(dlg, label):
    """The `label.field` of a form dialog whose own visible label text is `label` (optionally followed by ' *' or ' (optional)').

    The contract gives labels, not data-names. XPath on the label's first non-blank text node, so it
    re-evaluates on every use (dialogs re-render) and 'Konto' does not match 'Kontostand' or 'Zielkonto'.
    """
    # the label text lives in the first <span> (or directly in the label for checkbox-style fields)
    exprs = ["normalize-space(descendant::span[1])", "normalize-space(text()[normalize-space()][1])"]
    cond = " or ".join(f"{e}='{label}' or {e}='{label} *' or starts-with({e}, '{label} (')" for e in exprs)
    return dlg.locator(f"xpath=.//label[contains(concat(' ', normalize-space(@class), ' '), ' field ')][{cond}]")


def put_value(dlg, label, value):
    f = field(dlg, label)
    control = f.locator("select, textarea, input").first
    tag = control.evaluate("e => e.tagName.toLowerCase()")
    if tag == "select":
        control.select_option(label=value)
    elif control.get_attribute("type") == "checkbox":
        control.set_checked(bool(value))
    else:
        control.fill(str(value))


def show_balance(page):
    """Switch the forecast chart to the 'Kontostand' (balance lines) view (B-030: the default is the bar chart)."""
    page.locator("#chart .chart-mode button[data-mode=balance]").click()
    expect(page.locator("#chart svg.chart[data-mode=balance]")).to_have_count(1)
