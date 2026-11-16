import pytest
from playwright.sync_api import expect

OPEN = """async (spec) => {
  const m = await import('/core.js');
  window.__calls = []; window.__result = undefined; window.__done = false;
  const fields = spec.fields.map(f => f.showIf ? {...f, showIf: new Function('v', 'return ' + f.showIf)} : f);
  m.formDialog({title: spec.title || 'Testformular', fields, values: spec.values || {}, submitLabel: spec.submitLabel,
    onSubmit: async (v) => {
      window.__calls.push(v);
      if (spec.mode === 'throw') throw new Error('kaputt gegangen');
      if (spec.mode === 'hang') await new Promise(r => { window.__release = r; });
      return 'ergebnis';
    }}).then(r => { window.__result = (r === null ? '__null__' : r); window.__done = true; });
}"""

TEXT = {"name": "name", "label": "Name", "required": True}


@pytest.fixture
def form(app_page):
    page = app_page.open()
    expect(page.locator("#main")).to_be_visible()

    def open_(fields, **kw):
        page.evaluate(OPEN, {"fields": fields, **kw})
        expect(page.locator("dialog")).to_have_count(1)
        return page.locator("dialog")

    page.open_form = open_
    return page


def calls(page):
    return page.evaluate("window.__calls")


@pytest.mark.contract("FE-FORM-001", "FE-FORM-013")
def test_dialog_is_appended_opened_modally_and_removed_on_cancel(form):
    """FE-FORM-001/013: formDialog appends a <dialog>, opens it modally; Abbrechen closes+removes it, result null, no onSubmit."""
    dlg = form.open_form([TEXT])
    assert dlg.evaluate("d => d.open && d.matches(':modal') && d.parentElement === document.body")
    dlg.get_by_role("button", name="Abbrechen").click()
    expect(form.locator("dialog")).to_have_count(0)
    assert form.evaluate("window.__result") == "__null__" and calls(form) == []


@pytest.mark.contract("FE-FORM-001", "FE-FORM-013")
def test_escape_closes_with_null(form):
    """FE-FORM-001/013: Esc closes the dialog, resolves null and makes no call."""
    form.open_form([TEXT])
    form.keyboard.press("Escape")
    expect(form.locator("dialog")).to_have_count(0)
    assert form.evaluate("window.__result") == "__null__" and calls(form) == []


@pytest.mark.contract("FE-FORM-002")
def test_field_markup_label_control_name_and_required_star(form):
    """FE-FORM-002: label.field[data-name] wraps a control with that name; label text has ' *' when required."""
    dlg = form.open_form([TEXT, {"name": "note", "label": "Notiz"}])
    for n in ("name", "note"):
        assert dlg.locator(f'label.field[data-name="{n}"] [name="{n}"]').count() == 1
    assert "Name *" in dlg.locator('label.field[data-name="name"]').inner_text().replace(" ", " ")
    assert "*" not in dlg.locator('label.field[data-name="note"]').inner_text()
    assert dlg.get_by_text("Testformular").count() >= 1


@pytest.mark.contract("FE-FORM-003")
def test_select_renders_options_and_preselects_current_value(form):
    """FE-FORM-003: select options come from field.options; the option matching the value is selected."""
    dlg = form.open_form([{"name": "typ", "label": "Typ", "type": "select",
                           "options": [{"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta"}]}], values={"typ": "b"})
    sel = dlg.locator('select[name="typ"]')
    assert sel.locator("option").all_inner_texts() == ["Alpha", "Beta"]
    assert sel.input_value() == "b"


@pytest.mark.contract("FE-FORM-004")
def test_checkbox_textarea_and_text_controls(form):
    """FE-FORM-004: checkbox reflects the boolean value; textarea and (default/money) text inputs render."""
    dlg = form.open_form([{"name": "flag", "label": "Flag", "type": "checkbox"}, {"name": "long", "label": "Lang", "type": "textarea"},
                          {"name": "plain", "label": "Plain"}, {"name": "geld", "label": "Geld", "type": "money"}],
                         values={"flag": True, "long": "zeile\nzwei"})
    assert dlg.locator('input[type="checkbox"][name="flag"]').is_checked()
    assert dlg.locator('textarea[name="long"]').input_value() == "zeile\nzwei"
    assert dlg.locator('input[name="plain"]').count() == 1 and dlg.locator('input[name="geld"]').count() == 1


@pytest.mark.contract("FE-FORM-005", "FE-FORM-006")
def test_show_if_is_re_evaluated_live_and_values_survive_re_render(form):
    """FE-FORM-005/006: a showIf field appears/disappears live; entered values are kept across re-renders."""
    dlg = form.open_form([{"name": "typ", "label": "Typ", "type": "select", "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
                          {"name": "extra", "label": "Extra", "showIf": "v.typ === 'b'"},
                          {"name": "frei", "label": "Frei"}], values={"typ": "a"})
    expect(dlg.locator('label.field[data-name="extra"]')).to_have_count(0)
    dlg.locator('input[name="frei"]').fill("bleibt")
    dlg.locator('select[name="typ"]').select_option("b")
    expect(dlg.locator('label.field[data-name="extra"]')).to_have_count(1)
    expect(dlg.locator('input[name="frei"]')).to_have_value("bleibt")
    dlg.locator('input[name="extra"]').fill("sichtbar")
    dlg.locator('select[name="typ"]').select_option("a")
    expect(dlg.locator('label.field[data-name="extra"]')).to_have_count(0)


@pytest.mark.contract("FE-FORM-007")
def test_required_field_blocks_submit_with_message(form):
    """FE-FORM-007: an empty required field shows 'Bitte „<label>“ ausfüllen.' in .err and makes no onSubmit call."""
    dlg = form.open_form([TEXT])
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text("Bitte „Name“ ausfüllen.")
    assert calls(form) == []
    expect(form.locator("dialog")).to_have_count(1)


@pytest.mark.contract("FE-FORM-008")
def test_unparseable_money_blocks_submit(form):
    """FE-FORM-008: an invalid money value shows '„<label>“ ist kein gültiger Betrag.' and does not submit."""
    dlg = form.open_form([{"name": "betrag", "label": "Betrag", "type": "money", "required": True}])
    dlg.locator('input[name="betrag"]').fill("abc")
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text("„Betrag“ ist kein gültiger Betrag.")
    assert calls(form) == []


@pytest.mark.contract("FE-FORM-008")
@pytest.mark.parametrize("typed,cents", [("1.234,56", 123456), ("-250", -25000), ("0,05", 5)])
def test_valid_money_is_submitted_as_integer_cents(form, typed, cents):
    """FE-FORM-008: a valid money field reaches onSubmit as integer cents."""
    dlg = form.open_form([{"name": "betrag", "label": "Betrag", "type": "money", "required": True}])
    dlg.locator('input[name="betrag"]').fill(typed)
    dlg.locator("button.primary").click()
    expect(form.locator("dialog")).to_have_count(0)
    assert calls(form) == [{"betrag": cents}]


@pytest.mark.contract("FE-FORM-009")
def test_hidden_field_is_submitted_as_null(form):
    """FE-FORM-009: a showIf-false field is sent as null even if it had been filled before."""
    dlg = form.open_form([{"name": "typ", "label": "Typ", "type": "select", "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
                          {"name": "extra", "label": "Extra", "showIf": "v.typ === 'b'"}], values={"typ": "b"})
    dlg.locator('input[name="extra"]').fill("alt")
    dlg.locator('select[name="typ"]').select_option("a")
    dlg.locator("button.primary").click()
    expect(form.locator("dialog")).to_have_count(0)
    (sent,) = calls(form)
    assert sent["typ"] == "a" and sent["extra"] is None


@pytest.mark.contract("FE-FORM-010")
def test_submit_button_is_disabled_while_saving(form):
    """FE-FORM-010: while onSubmit is in flight the primary button is disabled (one onSubmit call so far)."""
    dlg = form.open_form([TEXT], mode="hang", values={"name": "x"})
    btn = dlg.locator("button.primary")
    btn.click()
    expect(btn).to_be_disabled()
    assert len(calls(form)) == 1
    form.evaluate("window.__release()")
    expect(form.locator("dialog")).to_have_count(0)


@pytest.mark.contract("FE-FORM-011")
def test_submit_error_keeps_dialog_open_and_shows_message(form):
    """FE-FORM-011: if onSubmit throws, the dialog stays open, submit is re-enabled and the message is shown in .err."""
    dlg = form.open_form([TEXT], mode="throw", values={"name": "x"})
    dlg.locator("button.primary").click()
    expect(dlg.locator(".err")).to_contain_text("kaputt gegangen")
    expect(dlg.locator("button.primary")).to_be_enabled()
    assert form.evaluate("window.__done") is False


@pytest.mark.contract("FE-FORM-012")
def test_successful_submit_resolves_with_the_return_value_and_closes(form):
    """FE-FORM-012: on success the promise resolves with onSubmit's return value and the dialog closes."""
    dlg = form.open_form([TEXT], values={"name": "Giro"})
    dlg.locator("button.primary").click()
    expect(form.locator("dialog")).to_have_count(0)
    form.wait_for_function("window.__done === true")
    assert form.evaluate("window.__result") == "ergebnis" and calls(form) == [{"name": "Giro"}]


@pytest.mark.contract("FE-FORM-002")
def test_custom_submit_label(form):
    """FE-FORM-002 (interface): the primary button shows submitLabel, default 'Speichern'."""
    dlg = form.open_form([TEXT], submitLabel="Anlegen")
    assert dlg.locator("button.primary").inner_text() == "Anlegen"
    dlg.get_by_role("button", name="Abbrechen").click()
    dlg = form.open_form([TEXT])
    assert dlg.locator("button.primary").inner_text() == "Speichern"


@pytest.mark.contract("FE-FORM-014")
def test_archive_dialog_asks_for_an_optional_reason_and_archives(app_page):
    """FE-FORM-014: archiveDialog shows an intro and 'Grund (optional)', POSTs archive, toasts 'Archiviert', refreshes."""
    a = app_page.seed.account("Giro")
    e = app_page.seed.entry(a["id"], "Miete", -100)
    page = app_page.open("buchungen")
    expect(page.locator("#main")).to_contain_text("Miete")
    page.evaluate("""async (id) => { const m = await import('/core.js');
        const rows = await m.api('GET', '/api/state'); const row = rows.entries.find(x => x.id === id);
        m.archiveDialog('entries', row, 'Miete'); }""", e["id"])
    dlg = page.locator("dialog")
    expect(dlg.locator('label.field[data-name] >> text=Grund (optional)')).to_have_count(1)
    dlg.locator("textarea, input[type=text], input:not([type])").first.fill("nicht mehr aktuell")
    dlg.locator("button.primary").click()
    expect(page.locator("#toast")).to_contain_text("Archiviert")
    expect(page.locator("dialog")).to_have_count(0)
    st = app_page.seed.state()["entries"][0]
    assert st["archived"] is True
    reason = [r for r in app_page.seed.c.get("/api/audit?entity=entries").json() if r["action"] == "archive"][0]["comment"]
    assert reason == "nicht mehr aktuell"


@pytest.mark.contract("FE-FORM-015")
def test_restore_row_posts_without_a_dialog(app_page):
    """FE-FORM-015: restoreRow POSTs restore with no dialog, toasts 'Wiederhergestellt' and refreshes."""
    a = app_page.seed.account("Giro")
    e = app_page.seed.entry(a["id"], "Miete", -100)
    app_page.seed.c.post(f"/api/entries/{e['id']}/archive", json={})
    page = app_page.open("buchungen")
    page.evaluate("""async (id) => { const m = await import('/core.js');
        const s = await m.api('GET', '/api/state'); m.restoreRow('entries', s.entries.find(x => x.id === id)); }""", e["id"])
    expect(page.locator("#toast")).to_contain_text("Wiederhergestellt")
    assert page.locator("dialog").count() == 0
    assert app_page.seed.state()["entries"][0]["archived"] is False
