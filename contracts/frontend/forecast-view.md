# Frontend — forecast view ("Prognose")
ID prefix: FE-FORECAST
Layer: frontend

## Purpose
The main screen: a time-range toolbar, a line chart of the projected total (and per
account), a month table, and a detail panel breaking a selected month into every booking
with its derivation. It also surfaces warnings and a negative-balance alert. If there are no
accounts yet, it shows a welcome call-to-action.

## Interface
Rendered into `#main` when view = `prognose`. Fetches `GET /api/forecast?start=&months=`.
Stable DOM:
- `.toolbar` with: an `Ab` `<input type="month">` (start month), a `Zeitraum` `<select>`
  (options `12/24/36/60/120 Monate`), a `"Heute"` button, a `Gruppieren nach` `<select>`
  (FE-FORECAST-018), a `"+ Buchung"` primary button, and a `"+ Ist-Stand"` button.
- `#warn` — warning/negative banners.
- `#chart` — the SVG chart (`svg.chart`), with clickable month `<rect>`s and a `.legend`.
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
- `FE-FORECAST-008` [INFERRED] The chart draws a `"Gesamt"` series plus one series per
  account (when >1), a zero reference line, axis labels in `k €`/`€`, and a `.legend`
  listing each series name.
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
  (`"Achtung: Im <Monat> wird der Gesamtstand voraussichtlich negativ (<eur>)."`).
- `FE-FORECAST-016` [INFERRED] Clicking a booking item's label opens that entry's edit
  dialog (pre-filled).
- `FE-FORECAST-017` [INFERRED] `"+ Buchung"` opens the new-entry dialog; `"+ Ist-Stand"`
  opens the new-checkpoint dialog; both refresh the forecast after a successful save.

### Grouping (B-012)
- `FE-FORECAST-018` [README] The toolbar has a `Gruppieren nach` select with the same
  options and group order as the Buchungen view (FE-ENTRIES-021/022). `Keine` (default) shows
  the per-account cards. Any other option replaces them, in the selected month's detail, with
  one card per group (class `group`): the group label and the sum of the group's booking
  amounts in that month as forecast (adjustments included). Checkpoints are not listed.
- `FE-FORECAST-019` [README] Transfers are listed in their group but kept out of the sum and
  shown separately as `"Umbuchungen <eur>"`. A transfer counts once (its source side), except
  for `Konto`, where each side is listed under its own account.
- `FE-FORECAST-020` [README] Group cards are folded by default; clicking the header shows the
  group's bookings (date, name, amount, explanation lines), each with its account as a tag
  when there are several accounts (not for `Konto`). The choice is remembered separately
  from the Buchungen view, like FE-ENTRIES-025.

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
