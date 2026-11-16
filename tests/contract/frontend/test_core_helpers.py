import json
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect

from tests.contract.frontend.conftest import call, norm, prop

NAN = "__NaN__"


@pytest.fixture
def core(app_page):
    page = app_page.open()
    return page


# ---------------------------------------------------------------------------- money

@pytest.mark.contract("FE-CORE-001")
@pytest.mark.parametrize("cents,text", [(123456, "1.234,56 €"), (100000, "1.000,00 €"), (0, "0,00 €"), (5, "0,05 €"),
                                        (-25000, "-250,00 €"), (123456789, "1.234.567,89 €"), (99, "0,99 €")])
def test_eur_formats_german_currency(core, cents, text):
    """FE-CORE-001: eur(cents) -> German thousands '.', decimal ',', ' €' suffix."""
    assert norm(call(core, "eur", cents)) == text


@pytest.mark.contract("FE-CORE-002")
def test_eur_of_null_is_a_dash(core):
    """FE-CORE-002: eur(null) and eur(undefined) render the placeholder '–'."""
    assert call(core, "eur", None) == "–"
    assert core.evaluate("async () => (await import('/core.js')).eur(undefined)") == "–"


@pytest.mark.contract("FE-CORE-003")
@pytest.mark.parametrize("text,cents", [("1.234,56", 123456), ("1234.56", 123456), ("-250", -25000), ("1.000,00 €", 100000),
                                        ("  12,5  ", 1250), ("0,01", 1), ("1234", 123400), ("€ 5,00", 500), ("-0,50", -50)])
def test_parse_eur_accepts_german_and_plain_formats(core, text, cents):
    """FE-CORE-003: parseEUR understands German, plain-decimal, integer, € and whitespace forms."""
    assert call(core, "parseEUR", text) == cents


@pytest.mark.contract("FE-CORE-003")
@pytest.mark.parametrize("text", ["", "   ", "abc", "12,3,4x", "€", "--5"])
def test_parse_eur_returns_nan_for_unparseable_input(core, text):
    """FE-CORE-003: empty or non-numeric input -> NaN."""
    assert call(core, "parseEUR", text) == NAN


@pytest.mark.contract("FE-CORE-004")
@pytest.mark.parametrize("text,cents", [("-250,00", -25000), ("10,999", 1100), ("0,004", 0), ("19,99", 1999), ("-1,005", -101)])
def test_parse_eur_rounds_to_whole_cents_and_handles_negatives(core, text, cents):
    """FE-CORE-004: parseEUR rounds to whole cents and keeps the sign."""
    got = call(core, "parseEUR", text)
    assert got == cents or (text == "-1,005" and got in (-100, -101)), got      # negative tie: F-18


@pytest.mark.contract("FE-CORE-005")
@pytest.mark.parametrize("cents,text", [(-25000, "-250,00"), (123456, "1234,56"), (0, "0,00"), (5, "0,05"), (100000, "1000,00")])
def test_to_input_is_plain_decimal_without_grouping(core, cents, text):
    """FE-CORE-005: toInput(cents) -> decimal string with a comma and no thousands separator."""
    assert call(core, "toInput", cents) == text


@pytest.mark.contract("FE-CORE-005", "FE-CORE-003")
@pytest.mark.parametrize("cents", [0, 1, 99, 100, -25000, 123456, -987654321])
def test_to_input_and_parse_eur_roundtrip(core, cents):
    """FE-CORE-005/003: toInput is the inverse of parseEUR."""
    assert call(core, "parseEUR", call(core, "toInput", cents)) == cents


# ---------------------------------------------------------------------------- dates

@pytest.mark.contract("FE-CORE-006")
@pytest.mark.parametrize("fn,iso,text", [("fFull", "2026-01-05", "05.01.2026"), ("fDate", "2026-01-05", "5.1.2026"),
                                         ("fFull", "2026-12-31", "31.12.2026"), ("fDate", "2026-12-31", "31.12.2026")])
def test_date_formatters(core, fn, iso, text):
    """FE-CORE-006: fFull is zero-padded d.m.y, fDate is not."""
    assert call(core, fn, iso) == text


@pytest.mark.contract("FE-CORE-006")
def test_short_date_and_timestamp_formatters_return_text(core):
    """FE-CORE-006: fShort and fTs produce non-empty German text containing the date parts."""
    assert "5" in call(core, "fShort", "2026-01-05")
    ts = call(core, "fTs", "2026-01-05T08:30:00.000+00:00")
    assert isinstance(ts, str) and "2026" in ts


@pytest.mark.contract("FE-CORE-007")
@pytest.mark.parametrize("ym,month", [("2026-03", "Mär"), ("2026-12", "Dez"), ("2026-05", "Mai"), ("2026-10", "Okt")])
def test_month_formatter_is_german_short_month_and_year(core, ym, month):
    """FE-CORE-007: fMonth('2026-03') -> German month name + year (e.g. 'März 2026')."""
    out = call(core, "fMonth", ym)
    assert out.startswith(month) and out.endswith(ym[:4])


@pytest.mark.contract("FE-CORE-008")
def test_today_and_this_month_follow_the_browser_clock(context, seed_live):
    """FE-CORE-008: today()/thisMonth() are the browser-local date/month in ISO form."""
    page = context.new_page()
    page.clock.install(time=datetime(2026, 3, 9, 12, 0, 0))
    page.goto("/")
    assert call(page, "today") == "2026-03-09" and call(page, "thisMonth") == "2026-03"


@pytest.mark.contract("FE-CORE-008")
def test_today_uses_local_not_utc_date(browser, live_server):
    """FE-CORE-008: just after local midnight (UTC still on the previous day) today() is the local date."""
    ctx = browser.new_context(base_url=live_server.url, timezone_id="Europe/Berlin")
    page = ctx.new_page()
    # 22:30 UTC on Jun 30 is 00:30 CEST on Jul 1 in Europe/Berlin
    page.clock.install(time=datetime(2026, 6, 30, 22, 30, 0, tzinfo=timezone.utc))
    page.goto("/")
    assert call(page, "today") == "2026-07-01" and call(page, "thisMonth") == "2026-07"
    ctx.close()


# ---------------------------------------------------------------------------- api()

@pytest.mark.contract("FE-CORE-009")
def test_api_get_resolves_to_parsed_json(core):
    """FE-CORE-009: api('GET', url) resolves to the parsed body on 2xx."""
    out = call(core, "api", "GET", "/api/state")
    assert out["accounts"] == [] and out["data_version"] == 0


ERR_JS = """async ([method, url, body]) => {
  const m = await import('/core.js');
  try { await m.api(method, url, body); return {ok: true}; } catch (e) { return {ok: false, name: e.name, message: e.message}; }
}"""


def fulfill(page, status, body, content_type="application/json"):
    page.route("**/api/probe", lambda r: r.fulfill(status=status, body=body, content_type=content_type))


@pytest.mark.contract("FE-CORE-010")
@pytest.mark.parametrize("status,body,ctype,expected", [
    (409, json.dumps({"code": "conflict", "params": {}}), "application/json",
     "Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen."),
    (500, json.dumps({"detail": "kaputt gegangen"}), "application/json", "kaputt gegangen"),
    (503, "", "text/plain", "Fehler 503"),
    (404, json.dumps({"code": "not_found", "params": {"entity": "accounts", "id": 5}}), "application/json", "Konto #5 nicht gefunden"),
])
def test_api_throws_localised_errors_on_non_2xx(core, status, body, ctype, expected):
    """FE-CORE-010: non-2xx -> Error whose message is errMsg(body), else body.detail, else 'Fehler <status>'."""
    fulfill(core, status, body, ctype)
    res = core.evaluate(ERR_JS, ["GET", "/api/probe", None])
    assert res["ok"] is False and res["name"] == "Error" and res["message"] == expected


@pytest.mark.contract("FE-CORE-011")
def test_api_sends_json_only_when_a_body_is_given(core):
    """FE-CORE-011: Content-Type: application/json and a JSON body only when a body is provided."""
    seen = []
    core.route("**/api/probe", lambda r: (seen.append((r.request.method, r.request.headers, r.request.post_data)),
                                          r.fulfill(status=200, body="{}", content_type="application/json")))
    core.evaluate(ERR_JS, ["POST", "/api/probe", {"a": 1, "b": "ü"}])
    core.evaluate(ERR_JS, ["GET", "/api/probe", None])
    (m1, h1, b1), (m2, h2, b2) = seen
    assert m1 == "POST" and h1["content-type"].startswith("application/json") and json.loads(b1) == {"a": 1, "b": "ü"}
    assert m2 == "GET" and not b2


# ---------------------------------------------------------------------------- errMsg

@pytest.mark.contract("FE-CORE-012")
@pytest.mark.parametrize("entity,id_,text", [("accounts", 5, "Konto #5 nicht gefunden"), ("checkpoints", 3, "Ist-Stand #3 nicht gefunden")])
def test_err_msg_not_found(core, entity, id_, text):
    """FE-CORE-012: not_found uses the ENTITY label."""
    assert call(core, "errMsg", {"code": "not_found", "params": {"entity": entity, "id": id_}}) == text


@pytest.mark.contract("FE-CORE-012")
def test_err_msg_not_found_unknown_entity_falls_back_to_raw_key(core):
    """FE-CORE-012: an unknown entity shows its raw key."""
    out = call(core, "errMsg", {"code": "not_found", "params": {"entity": "widgets", "id": 7}})
    assert "widgets" in out and "7" in out and "nicht gefunden" in out


@pytest.mark.contract("FE-CORE-013")
def test_err_msg_conflict(core):
    """FE-CORE-013: conflict -> the documented German sentence."""
    assert call(core, "errMsg", {"code": "conflict"}) == "Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen."


@pytest.mark.contract("FE-CORE-014")
def test_err_msg_unknown_table(core):
    """FE-CORE-014: unknown_table -> 'Unbekannter Datentyp'."""
    assert call(core, "errMsg", {"code": "unknown_table", "params": {"table": "x"}}) == "Unbekannter Datentyp"


@pytest.mark.contract("FE-CORE-015")
def test_err_msg_ref_not_found(core):
    """FE-CORE-015: ref_not_found -> 'Verweis account_id=9 existiert nicht.'."""
    assert call(core, "errMsg", {"code": "ref_not_found", "params": {"field": "account_id", "id": 9}}) == "Verweis account_id=9 existiert nicht."


def verr(*errors):
    return {"code": "validation_error", "params": {"errors": [{"field": f, "code": c, "params": p} for f, c, p in errors]}}


@pytest.mark.contract("FE-CORE-016")
def test_err_msg_validation_joins_messages_with_semicolon(core):
    """FE-CORE-016: several field errors are joined with '; '."""
    out = call(core, "errMsg", verr(("", "amount_zero", {}), ("", "end_before_start", {})))
    assert out == "Der Betrag darf nicht 0 sein.; Das Enddatum liegt vor dem Startdatum."


@pytest.mark.contract("FE-CORE-016")
def test_err_msg_validation_prefixes_the_field_label(core):
    """FE-CORE-016: a field error is prefixed by the German FIELD label; an empty field shows just the message."""
    with_field = call(core, "errMsg", verr(("name", "string_too_short", {"min_length": 1})))
    bare = call(core, "errMsg", verr(("", "string_too_short", {"min_length": 1})))
    assert with_field.endswith(bare) and len(with_field) > len(bare)


@pytest.mark.contract("FE-CORE-017")
@pytest.mark.parametrize("code,params,text", [
    ("amount_zero", {}, "Der Betrag darf nicht 0 sein."),
    ("transfer_same_account", {}, "Quell- und Zielkonto müssen verschieden sein."),
    ("end_before_start", {}, "Das Enddatum liegt vor dem Startdatum."),
])
def test_err_msg_fixed_validation_phrases(core, code, params, text):
    """FE-CORE-017: validation sub-codes map to fixed German phrases."""
    assert call(core, "errMsg", verr(("", code, params))) == text


@pytest.mark.contract("FE-CORE-017")
@pytest.mark.parametrize("code,params,tail", [("missing", {}, "ist erforderlich"),
                                              ("string_too_short", {"min_length": 3}, "muss mindestens 3 Zeichen haben")])
def test_err_msg_field_phrases(core, code, params, tail):
    """FE-CORE-017: missing -> 'ist erforderlich'; string_too_short -> 'muss mindestens N Zeichen haben'."""
    assert call(core, "errMsg", verr(("name", code, params))).endswith(tail)


@pytest.mark.contract("FE-CORE-018")
@pytest.mark.parametrize("body", [{}, {"detail": "x"}, {"code": "totally_unknown", "params": {}}, {"foo": 1}])
def test_err_msg_returns_null_without_a_recognised_code(core, body):
    """FE-CORE-018: errMsg returns null for bodies without a recognised code."""
    assert call(core, "errMsg", body) is None


# ---------------------------------------------------------------------------- explLine

@pytest.mark.contract("FE-CORE-019")
def test_expl_line_base_amount(core):
    """FE-CORE-019: base_amount -> 'Grundbetrag <eur>'."""
    assert norm(call(core, "explLine", {"code": "base_amount", "amount": -60000})) == "Grundbetrag -600,00 €"


@pytest.mark.contract("FE-CORE-020")
def test_expl_line_set_amount(core):
    """FE-CORE-020: set_amount -> 'ab <dd.mm.yyyy>: neuer Betrag <eur>' (+ ' (<note>)' when a note is present)."""
    step = {"code": "set_amount", "date": "2026-03-01", "amount": 320000, "note": ""}
    assert norm(call(core, "explLine", step)) == "ab 01.03.2026: neuer Betrag 3.200,00 €"
    assert norm(call(core, "explLine", {**step, "note": "Raise"})) == "ab 01.03.2026: neuer Betrag 3.200,00 € (Raise)"


@pytest.mark.contract("FE-CORE-021")
def test_expl_line_percent_change_matches_readme_example(core):
    """FE-CORE-021: percent_change renders like the README line: 'ab 01.01.2027: +2,5 %, jährlich – hier 1× angewendet → -615,00 € (Inflation)'."""
    step = {"code": "percent_change", "date": "2027-01-01", "percent": 2.5, "repeat_yearly": True, "years": 1, "amount": -61500, "note": "Inflation"}
    assert norm(call(core, "explLine", step)) == "ab 01.01.2027: +2,5 %, jährlich – hier 1× angewendet → -615,00 € (Inflation)"


@pytest.mark.contract("FE-CORE-021")
def test_expl_line_percent_change_variants(core):
    """FE-CORE-021: one-off change has no 'jährlich' clause or note; a negative percent keeps its minus; years is shown."""
    once = norm(call(core, "explLine", {"code": "percent_change", "date": "2026-06-01", "percent": -3, "repeat_yearly": False,
                                        "years": 1, "amount": -97000, "note": ""}))
    assert "jährlich" not in once and "-3" in once and "-970,00 €" in once and not once.endswith(")")
    yearly = norm(call(core, "explLine", {"code": "percent_change", "date": "2026-01-01", "percent": 2, "repeat_yearly": True,
                                          "years": 3, "amount": -106121, "note": ""}))
    assert "hier 3× angewendet" in yearly and "+2 %" in yearly and yearly.endswith("-1.061,21 €")


@pytest.mark.contract("FE-CORE-022")
def test_expl_line_unknown_code_returns_the_code(core):
    """FE-CORE-022: an unknown explanation code returns the code string itself."""
    assert call(core, "explLine", {"code": "mystery_step"}) == "mystery_step"


# ---------------------------------------------------------------------------- warnMsg & maps

@pytest.mark.contract("FE-CORE-023")
def test_warn_msg_no_checkpoint_resolves_account_name(app_page):
    """FE-CORE-023: no_checkpoint -> 'Konto „<name>“ hat keinen Ist-Stand und kann nicht berechnet werden.'; unknown id -> #<id>."""
    a = app_page.seed.account("Giro")
    page = app_page.open()
    expect(page.locator("#main")).to_be_visible()
    assert call(page, "warnMsg", {"code": "no_checkpoint", "account_id": a["id"]}) == \
        "Konto „Giro“ hat keinen Ist-Stand und kann nicht berechnet werden."
    assert "#99999" in call(page, "warnMsg", {"code": "no_checkpoint", "account_id": 99999})


@pytest.mark.contract("FE-CORE-024")
def test_warn_msg_transfer_target_archived(app_page):
    """FE-CORE-024: transfer_target_archived -> 'Umbuchung „<entry>“ ignoriert: Zielkonto „<account>“ ist archiviert.'."""
    s = app_page.seed
    a, b = s.account("Giro"), s.account("Spar")
    e = s.entry(a["id"], "Sparen", 100, "2026-02-01", to_account_id=b["id"])
    page = app_page.open()
    expect(page.locator("#main")).to_be_visible()
    assert call(page, "warnMsg", {"code": "transfer_target_archived", "entry_id": e["id"], "account_id": b["id"]}) == \
        "Umbuchung „Sparen“ ignoriert: Zielkonto „Spar“ ist archiviert."


@pytest.mark.contract("FE-CORE-025")
def test_kinds_map(core):
    """FE-CORE-025: KINDS maps account kinds to German."""
    assert prop(core, "KINDS") == {"checking": "Girokonto", "savings": "Tagesgeld", "custody": "Depot",
                                   "credit_card": "Kreditkarte", "cash": "Bargeld", "other": "Sonstiges"}


@pytest.mark.contract("FE-CORE-026")
@pytest.mark.parametrize("n,text", [(1, "monatlich"), (2, "alle 2 Monate"), (3, "quartalsweise"), (6, "halbjährlich"),
                                    (12, "jährlich"), (5, "alle 5 Monate"), (24, "alle 24 Monate")])
def test_rhythm(core, n, text):
    """FE-CORE-026: rhythm(n) -> German cadence, default 'alle N Monate'."""
    assert call(core, "rhythm", n) == text


@pytest.mark.contract("FE-CORE-027")
def test_action_map_labels(core):
    """FE-CORE-027/FE-AUDIT-002: ACTION labels for the five audit actions."""
    assert prop(core, "ACTION") == {"create": "Angelegt", "update": "Geändert", "archive": "Archiviert",
                                    "restore": "Wiederhergestellt", "revert": "Rückgängig"}


@pytest.mark.contract("FE-CORE-027")
def test_entity_and_field_maps_exist(core):
    """FE-CORE-027: ENTITY labels the audited tables; FIELD labels field names (contents beyond the documented ones are unspecified, F-24)."""
    ent = prop(core, "ENTITY")
    assert ent["accounts"] == "Konto" and ent["checkpoints"] == "Ist-Stand"
    assert {"accounts", "entries", "adjustments", "checkpoints"} <= set(ent)
    assert isinstance(prop(core, "FIELD"), dict) and prop(core, "FIELD")
