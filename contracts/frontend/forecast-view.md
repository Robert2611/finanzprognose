# Frontend — forecast view ("Prognose")
ID prefix: FE-FORECAST
Layer: frontend

## Purpose
The main screen: a time-range toolbar, a chart (by default the monthly surplus as bars, B-030;
or the projected balances as lines), a month table, and a detail panel breaking a selected month into every booking
with its derivation. It also surfaces warnings and a negative-balance alert. If there are no
accounts yet, it shows a welcome call-to-action.

## Interface
Rendered into `#main` when view = `prognose`. Fetches `GET /api/forecast?start=&months=`.
Stable DOM:
- `.toolbar` with: an `Ab` `<input type="month">` (start month), a `Zeitraum` `<select>`
  (options `12/24/36/60/120 Monate`), a `"Heute"` button, a `Gruppieren nach` `<select>`
  (FE-FORECAST-018), a `"+ Wiederkehrend"` primary button, a `"+ Einmalig"` button, and a
  `"+ Ist-Stand"` button.
- `#warn` — warning/negative banners.
- `#chart` — the chart: `.chart-mode` buttons (`button[data-mode=flow]` „Überschuss pro
  Monat“, `button[data-mode=balance]` „Kontostand“), the SVG (`svg.chart[data-mode]`) with
  clickable month `<rect>`s carrying a `<title>`, and a `.legend`. Drawn by `forecast_chart.js`.
- `#ftable` — the month table (`table` with header `"Monat (Monatsende)"`, per-account
  columns when >1 account, `"Gesamt"`, `"Veränderung"`); rows are `tr.clickable`, the
  selected row has class `selected`.
- `#fdetail` — the selected month's breakdown.

Empty state (no accounts): a `.panel` with heading `"Willkommen"` and a primary button
`"Erstes Konto anlegen"`.

## Dependencies & side effects
`GET /api/forecast`. Opens entry/checkpoint/account dialogs. Mutates in-memory selection
state `S.from`, `S.months`, `S.sel`.

## Behavior clauses

- `FE-FORECAST-001` [INFERRED] With no accounts, the view shows the `"Willkommen"` panel and
  an `"Erstes Konto anlegen"` button that opens the new-account dialog.
- `FE-FORECAST-002` [INFERRED] With accounts, the toolbar, chart (`#chart`), table
  (`#ftable`), and detail (`#fdetail`) are rendered from `GET /api/forecast`.
- `FE-FORECAST-003` [INFERRED] The `Zeitraum` select offers 12/24/36/60/120 months;
  changing it re-fetches the forecast for the new horizon.
- `FE-FORECAST-004` [INFERRED] Changing the `Ab` month input re-fetches from that start
  month and resets the selected month.
- `FE-FORECAST-005` [INFERRED] The `"Heute"` button resets the start month to the current
  month.
- `FE-FORECAST-006` [INFERRED] The month table has one row per forecast month, showing the
  German month label, the total `"Gesamt"` closing (bold), and the change vs. opening
  (`"Veränderung"`, signed/colored); with more than one account, a column per account.
- `FE-FORECAST-007` [INFERRED] Clicking a table row (or a chart month rect) selects that
  month: the row gains `selected` and the detail panel updates to that month.
- `FE-FORECAST-008` [INFERRED] In the „Kontostand“ view the chart draws a `"Gesamt"` series
  plus one series per account (when >1), a zero reference line, axis labels in `k €`/`€`, and
  a `.legend` listing each series name.
- `FE-FORECAST-009` [INFERRED] The detail panel (`#fdetail`) for the selected month shows
  `"Einnahmen"`, `"Ausgaben"`, and `"Gesamtstand Monatsende"`, then a card per account.
- `FE-FORECAST-010` [INFERRED] Each account card lists `"Anfangsstand"`, each item for the
  month, and `"Endstand"`. A month with no items shows `"Keine Buchungen in diesem Monat"`.
- `FE-FORECAST-011` [README] Each booking item row shows its date, label, signed amount, and
  an expandable derivation (`.expl`) listing each explanation step via `explLine` plus
  `"Kontostand danach: <eur>"`.
- `FE-FORECAST-012` [README] A checkpoint item shows the balance and, when it has a
  deviation, the text `"Prognose war <eur>, tatsächlich <eur> → Abweichung <signed eur>"`
  and `"Ab hier rechnet die Prognose mit dem echten Kontostand weiter."`; the first/start
  checkpoint instead shows `"Ausgangspunkt der Berechnung für dieses Konto"`.
- `FE-FORECAST-013` [INFERRED] The start checkpoint label reads `"Startstand (Ist-Stand)"`
  and a later one `"Ist-Stand eingetragen"`, distinguished by the presence of a deviation.
- `FE-FORECAST-014` [INFERRED] Each forecast `warning` renders as a `.banner.warn` in
  `#warn` with the German text from `warnMsg`.
- `FE-FORECAST-015` [INFERRED] If any month's total closing is negative, `#warn` shows a
  `.banner.err` naming the first such month and amount
  (`"Achtung: Im <Monat> wird der Gesamtstand voraussichtlich negativ (<eur>)."`). With
  reserve accounts the check uses the available money instead (FE-FORECAST-024).
- `FE-FORECAST-016` [INFERRED] Clicking a booking item's label opens that entry's edit
  dialog (pre-filled): the recurring dialog for a recurring booking, the one-time dialog for a
  one-time booking (B-027).
- `FE-FORECAST-017` [INFERRED] `"+ Wiederkehrend"` opens the new recurring booking dialog,
  `"+ Einmalig"` the new one-time booking dialog (B-027); `"+ Ist-Stand"` opens the
  new-checkpoint dialog; all refresh the forecast after a successful save.

### Grouping (B-012)
- `FE-FORECAST-018` [README] The toolbar has a `Gruppieren nach` select with the same
  options and group order as the Buchungen view (FE-ENTRIES-021/022). `Keine` (default) shows
  the per-account cards. Any other option replaces them, in the selected month's detail, with
  one card per group (class `group`): the group label and the sum of the group's booking
  amounts in that month as forecast (adjustments included), marked `"≈ "` when it includes
  an estimated booking (FE-FORECAST-021). Checkpoints are not listed.
- `FE-FORECAST-019` [README] Transfers are listed in their group but kept out of the sum and
  shown separately as `"Umbuchungen <eur>"`. A transfer counts once (its source side), except
  for `Konto`, where each side is listed under its own account.
- `FE-FORECAST-020` [README] Group cards are folded by default; clicking the header shows the
  group's bookings (date, name, amount, explanation lines), each with its account as a tag
  when there are several accounts (not for `Konto`). The choice is remembered separately
  from the Buchungen view, like FE-ENTRIES-025.
- `FE-FORECAST-021` [README] The amount of a booking or transfer item whose `estimated` is
  true has a leading `"≈ "`, and its explanation ends with the line `"Geschätzter Betrag –
  die Abweichung zur Wirklichkeit zeigt der nächste Ist-Stand."` Fixed items are unchanged.
  This applies to the per-account cards and the group cards alike (B-015).
- `FE-FORECAST-022` [README] When the selected month contains estimated bookings, the
  month summary shows `"davon geschätzt ≈ <eur>"` right after `Einnahmen` and/or `Ausgaben`
  (the estimated part of each, bookings only, transfers excluded like in the totals). Without
  estimated bookings in that direction the line is absent.

### Reserve accounts (B-028)
- `FE-FORECAST-023` [README] Without any reserve account (`accounts[].reserve` all false) the
  page is exactly as described above (`"Gesamt"`). With at least one, the page is about the
  available money (`available_closing`): the chart's main series and the table's bold column
  are named `"Verfügbar"`, `"Veränderung"` is the change of the available money in that
  month, and a muted `"Gesamt"` column (all accounts) follows it. A reserve account's column
  header carries the note `"Rücklage"`; its own line stays in the chart.
- `FE-FORECAST-024` [README] With reserve accounts the negative banner checks the available
  money and reads `"Achtung: Im <Monat> wird das verfügbare Geld (ohne Rücklagen)
  voraussichtlich negativ (<eur>)."`; a negative reserve or total alone raises no banner.
- `FE-FORECAST-025` [README] With reserve accounts the month summary in `#fdetail` shows,
  after `Einnahmen`/`Ausgaben`, the month's reserve flow as `"In Rücklage gelegt <eur>"`
  (`to_reserve` > 0) or `"Aus Rücklage entnommen <eur>"` (< 0, shown as a positive amount;
  absent when 0), then `"Verfügbar Monatsende"` (bold) and `"Gesamtstand Monatsende"`. The
  card of a reserve account has a `"Rücklage"` tag next to its name.

### Optional bookings (B-029)
- `FE-FORECAST-026` [README] When there are non-archived optional bookings, a panel
  `"Optionale Posten"` (`.optional-panel`) between the warnings and the chart lists them by
  date, each with a checkbox (`name="include-optional"`), its name, amount and due date
  (one-time) or rhythm and period (recurring). All are unticked at first; the forecast is
  requested with `include=<id>` for each ticked one, so only those count. Ticking or
  unticking re-runs the forecast. Without optional bookings the panel is absent.
- `FE-FORECAST-027` [README] Which optional bookings are ticked is remembered in the browser
  across reloads (localStorage), never stored on the server; ids that are no longer active
  optional bookings are ignored. Without browser storage the page works and the choice lasts
  until the next reload.
- `FE-FORECAST-028` [README] While some optional bookings are left out (`with_optional` set),
  the chart adds a dashed series `"mit optionalen Posten"` (the main amount — available money
  with reserve accounts, else the total — with every optional booking counted), shown dashed
  in the legend too, and the month summary ends with `"mit allen optionalen Posten <eur>"`.
  A ticked optional booking's items carry an `"optional"` tag in the month detail.

### Monthly surplus chart and events (B-030)
- `FE-FORECAST-029` [README] The chart has two views, switched by the `.chart-mode` buttons:
  „Überschuss pro Monat“ (`flow`, the default) and „Kontostand“ (`balance`, the line chart of
  FE-FORECAST-008/023/028). The active button has class `active` and `aria-pressed="true"`.
  The choice is remembered in the browser across reloads; without browser storage the page
  works and the choice lasts until the next reload.
- `FE-FORECAST-030` [README] In the flow view each month has one bar (`g.bar[data-month]`)
  made of the month's booking items on the counted accounts — the non-reserve accounts when
  there is a reserve account, otherwise all — summed into segments
  (`rect.seg[data-cls][data-est][data-opt][data-amount]`) by class: `monthly` (recurring
  every month), `irregular` (recurring less often, e.g. quarterly or yearly) and `once`;
  with reserve accounts the month's reserve flow is a `reserve` segment of `−to_reserve`.
  Other transfers are not shown (they cancel out within the counted money). Estimated and
  optional (switched-in) parts are separate segments, drawn lighter and dashed respectively.
  Positive segments stack upward from zero, negative ones downward, in the class order above.
- `FE-FORECAST-031` [README] Each bar has a surplus marker (`line.net[data-amount]`), the sum
  of its segments. A month's click target has the tooltip
  `"<Monat>: Überschuss <±eur>"`, `"Einnahmen <eur>, Ausgaben <eur>"` and one `"• <event>"`
  line per event (FE-FORECAST-032); clicking it selects the month. The legend lists the
  classes that occur, `"Überschuss des Monats"`, the event marker when there are events, and
  a note `"heller = geschätzt"` / `"gestrichelt = optional"` when such parts occur. The bars
  show planned cash flow only: corrections by later checkpoints are not part of them.
- `FE-FORECAST-032` [README] A month's events, from the bookings the forecast counts (active,
  on an active account, optional ones only when switched in): a one-time booking
  (`"<Name>: <±eur> (einmalig)"`, a transfer as `"Umbuchung <eur>"`), a recurring booking
  starting (`"Neu: <Name> <±eur> <Rhythmus>"`, except in the first shown month) or ending
  (`"Endet: <Name> (letzte Fälligkeit <Datum>)"`), and an active adjustment taking effect
  (`"<Name>: ab <Datum> <change>"`, the change labeled as in FE-ENTRIES-016), sorted by date.
  In the flow view a month with events has a marker (`circle.event-mark[data-month][data-count]`)
  above its bar.
- `FE-FORECAST-033` [README] In both views the month detail lists the selected month's events
  under `"Ereignisse in diesem Monat"` (`.events li.event[data-kind]`, kinds `once`, `start`,
  `end`, `adjustment`), after the month summary; without events the block is absent.

## Examples
- Account with a start checkpoint and a monthly salary → the first month's card shows
  `"Anfangsstand"`, a `"Gehalt"` item with `+<eur>` and an explanation, and `"Endstand"`.
- A forecast where month totals dip below 0 → a red banner names the first negative month.

## Out of scope / not specified
- Exact chart pixel geometry/scaling.
- Tooltip timing/hover behavior on chart rects (the `<title>` text is specified; hover UX is
  not).
- Precise color values.

## Open questions
None (chart internals deliberately out of scope).
