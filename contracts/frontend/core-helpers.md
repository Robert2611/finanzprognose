# Frontend — core helpers & code→German maps
ID prefix: FE-CORE
Layer: frontend

## Purpose
The frontend owns all human text and formatting. This unit is the pure, unit-testable core
of that: EUR formatting/parsing, date/month formatting, the `api()` fetch wrapper, and the
maps that turn the backend's language-neutral `{code, params}` (errors, forecast
explanations, warnings) into the exact German strings the UI shows. Getting these right is
how "no German in the backend" stays invisible to the user.

## Interface
ES module `core.js`, served at `/core.js`. A browser-context test (e.g. Playwright
`page.evaluate` with a dynamic `import('/core.js')`) can import and call the exports. Key
exported functions:

- `eur(cents) -> string` — German EUR, e.g. `eur(123456) === "1.234,56 €"`; `eur(null) === "–"`.
- `parseEUR(str) -> number` — parse a German/plain money string to integer cents, or `NaN`.
- `toInput(cents) -> string` — cents → plain decimal string for a form field (no grouping).
- `fDate(iso)`, `fShort(iso)`, `fFull(iso)`, `fMonth(ym)`, `fTs(ts)` — date/time formatters
  (German locale). `fDate('2026-01-05') === "5.1.2026"`; `fFull('2026-01-05') === "05.01.2026"`.
- `today() -> "YYYY-MM-DD"`, `thisMonth() -> "YYYY-MM"` (browser-local).
- `api(method, url, body?) -> Promise` — fetch wrapper: JSON in/out; throws `Error` with a
  localized message built from the error envelope on non-2xx.
- `errMsg(data) -> string|null` — map an error `{code, params}` body to German text.
- `explLine(step) -> string` — map a forecast explanation `{code, params}` to German.
- `warnMsg(warning) -> string` — map a forecast warning `{code, params}` to German.
- Label maps: `KINDS`, `RHYTHM`/`rhythm(n)`, `ENTITY`, `ACTION`, `FIELD`.

## Dependencies & side effects
`api()` performs `fetch`. The formatters/maps are pure. `errMsg`/`explLine`/`warnMsg` read
only their argument. `accName`/`entryName` (used by `warnMsg`) read the in-memory state `S`.

## Behavior clauses

### Money
- `FE-CORE-001` [INFERRED] `eur(cents)` renders integer cents as German currency with a
  thousands separator `.`, decimal `,`, and ` €` suffix (`eur(123456) === "1.234,56 €"`).
- `FE-CORE-002` [INFERRED] `eur(null)`/`eur(undefined)` renders the placeholder `"–"`.
- `FE-CORE-003` [INFERRED] `parseEUR` accepts German format (`"1.234,56"` → `123456`),
  plain decimals (`"1234.56"` → `123456`), bare integers (`"-250"` → `-25000`), optional
  `€`/whitespace, and returns `NaN` for empty or non-numeric input.
- `FE-CORE-004` [INFERRED] `parseEUR` rounds to whole cents and handles negatives
  (`"-250,00"` → `-25000`).
- `FE-CORE-005` [INFERRED] `toInput(cents)` is the inverse used for form prefill: integer
  cents → plain decimal string with a comma, no grouping (`toInput(-25000) === "-250,00"`).

### Dates
- `FE-CORE-006` [INFERRED] `fFull('2026-01-05')` is zero-padded day/month/year
  (`"05.01.2026"`); `fDate('2026-01-05')` is non-padded German (`"5.1.2026"`).
- `FE-CORE-007` [INFERRED] `fMonth('2026-03')` renders a short month + year in German
  (e.g. `"März 2026"`).
- `FE-CORE-008` [INFERRED] `today()`/`thisMonth()` return the browser-local date/month in
  ISO form (`sv-SE` locale yields `YYYY-MM-DD`).

### api()
- `FE-CORE-009` [INFERRED] `api('GET', url)` resolves to the parsed JSON body on a 2xx
  response.
- `FE-CORE-010` [INFERRED] On a non-2xx response, `api()` throws an `Error` whose `message`
  is the localized text from `errMsg(body)`, falling back to `body.detail`, then to
  `"Fehler <status>"`.
- `FE-CORE-011` [INFERRED] `api()` sends `Content-Type: application/json` and a JSON body
  only when a body is provided.

### Error code → German (`errMsg`)
- `FE-CORE-012` [INFERRED] `errMsg({code:'not_found', params:{entity:'accounts', id:5}})`
  → `"Konto #5 nicht gefunden"` (uses the `ENTITY` map; unknown entity falls back to its
  raw key).
- `FE-CORE-013` [INFERRED] `errMsg({code:'conflict'})` →
  `"Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen."`
- `FE-CORE-014` [INFERRED] `errMsg({code:'unknown_table'})` → `"Unbekannter Datentyp"`.
- `FE-CORE-015` [INFERRED] `errMsg({code:'ref_not_found', params:{field:'account_id',id:9}})`
  → `"Verweis account_id=9 existiert nicht."`.
- `FE-CORE-016` [INFERRED] `errMsg({code:'validation_error', params:{errors:[...]}})` joins
  per-field messages with `"; "`, each prefixed by the German `FIELD` label; a field error
  with an empty `field` shows just the message.
- `FE-CORE-017` [INFERRED] Validation sub-codes map to fixed German phrases, e.g.
  `missing`→`"ist erforderlich"`, `string_too_short`→`"muss mindestens N Zeichen haben"`,
  `amount_zero`→`"Der Betrag darf nicht 0 sein."`,
  `transfer_same_account`→`"Quell- und Zielkonto müssen verschieden sein."`,
  `end_before_start`→`"Das Enddatum liegt vor dem Startdatum."`.
- `FE-CORE-018` [INFERRED] `errMsg` returns `null` for a body without a recognized `code`.

### Forecast explanation code → German (`explLine`)
- `FE-CORE-019` [README] `explLine({code:'base_amount', amount})` → `"Grundbetrag <eur>"`.
- `FE-CORE-020` [README] `explLine({code:'set_amount', date, amount, note})` →
  `"ab <fFull(date)>: neuer Betrag <eur>"` plus ` (<note>)` when a note is present.
- `FE-CORE-021` [README] `explLine({code:'percent_change', date, percent, repeat_yearly,
  years, amount, note})` renders the percent with a German decimal comma and sign, the
  `", jährlich – hier <years>× angewendet"` clause when `repeat_yearly`, then `→ <eur>` and
  an optional note — matching the README's example line.
- `FE-CORE-022` [INFERRED] `explLine` for an unknown code returns the code string itself.

### Warning code → German (`warnMsg`)
- `FE-CORE-023` [INFERRED] `warnMsg({code:'no_checkpoint', account_id})` →
  `"Konto „<account name>“ hat keinen Ist-Stand und kann nicht berechnet werden."` (name
  resolved from state via `accName`; unknown id shows `#<id>`).
- `FE-CORE-024` [INFERRED] `warnMsg({code:'transfer_target_archived', entry_id, account_id})`
  → `"Umbuchung „<entry name>“ ignoriert: Zielkonto „<account name>“ ist archiviert."`.

### Label maps
- `FE-CORE-025` [INFERRED] `KINDS` maps account kinds to German:
  `checking→Girokonto, savings→Tagesgeld, custody→Depot, credit_card→Kreditkarte,
  cash→Bargeld, other→Sonstiges`.
- `FE-CORE-026` [INFERRED] `rhythm(n)` maps interval months to German cadence
  (`1→monatlich, 2→"alle 2 Monate", 3→quartalsweise, 6→halbjährlich, 12→jährlich`),
  defaulting to `"alle N Monate"`.
- `FE-CORE-027` [INFERRED] `ENTITY`/`ACTION`/`FIELD` provide the German labels for audit
  entities, actions, and field names used across views.

## Examples
- `eur(100000)` → `"1.000,00 €"`; `parseEUR("1.000,00 €")` → `100000`.
- `errMsg({code:'not_found', params:{entity:'checkpoints', id:3}})` → `"Ist-Stand #3 nicht
  gefunden"`.

## Out of scope / not specified
- Exact `Intl`/locale micro-formatting (e.g. narrow vs. non-breaking spaces) — assert the
  significant characters, not byte-exact spacing.
- Internal rendering helpers (`signed`, `eurCls`) beyond their visible effect in the views.

## Open questions
- OPEN_QUESTIONS #14 (frontend has no `data-testid` hooks; browser tests must rely on
  visible text/roles and the handful of ids listed in `FE-NAV`).
