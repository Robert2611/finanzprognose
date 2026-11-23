# Frontend — entries view ("Buchungen") & adjustments
ID prefix: FE-ENTRIES
Layer: frontend

## Purpose
Where the user manages bookings — income, expenses, and transfers between accounts — and
the per-booking adjustments (a new fixed amount or a percentage change from a date). It
lists bookings, supports create/edit/archive/restore, and opens an adjustments sub-dialog.

## Interface
Rendered into `#main` when view = `buchungen`. Reads bookings from in-memory state `S.data`.
Stable DOM:
- `.toolbar` with heading `"Buchungen"`, an `"Archivierte zeigen"` checkbox, a
  `Gruppieren nach` select (FE-ENTRIES-021), and a
  `"+ Neue Buchung"` primary button.
- A `table` with headers `Bezeichnung, Typ, Konto, Grundbetrag, Rhythmus, Zeitraum,
  Anpassungen`, plus an action column. Archived rows have class `archived`. Empty list shows
  `"Noch keine Buchungen."`.
- Per row action buttons: `"Bearbeiten"`, `"Archivieren"` (or `"Wiederherstellen"` when
  archived), `"Verlauf"`, and an `"N Anpassung(en)"` button.

Dialogs (via `formDialog`):
- `entryDialog(entry?)` — fields: `Bezeichnung`, `Typ` (Einnahme/Ausgabe/Umbuchung zwischen
  Konten), `Konto`, `Zielkonto` (only for transfer), `Betrag (positiv eingeben)`, `Art`
  (Fest/Geschätzt),
  `Häufigkeit` (Wiederkehrend/Einmalig), `Rhythmus` (only recurring), `Datum der (ersten)
  Fälligkeit`, `Letzte Fälligkeit (optional)` (only recurring), `Kategorie`, `Notiz`.
- `adjustmentsDialog(entry)` — a sub-dialog listing adjustments with `+ Anpassung`.

## Dependencies & side effects
`POST/PUT /api/entries`, `/api/adjustments` (+ archive/restore). `GET /api/audit` for the
history dialog. Refreshes forecast/state after saves.

## Behavior clauses

### List
- `FE-ENTRIES-001` [INFERRED] The view lists all non-archived bookings by default; ticking
  `"Archivierte zeigen"` also lists archived ones (shown with the `archived` class).
- `FE-ENTRIES-002` [INFERRED] Each row shows the name (with optional category tag and note),
  the type label (`Einnahme`/`Ausgabe`/`Umbuchung`), the account (and `→ target` for
  transfers), the base amount, the cadence (`einmalig` or the German rhythm), and the period
  (`ab <date>` / `ab <date> bis <date>` / a single date for once).
- `FE-ENTRIES-003` [INFERRED] The type is derived from the data: a transfer has
  `to_account_id`; otherwise negative amount = expense, positive = income.
- `FE-ENTRIES-004` [INFERRED] An empty list renders a single `"Noch keine Buchungen."` row.
- `FE-ENTRIES-005` [INFERRED] The `"N Anpassung(en)"` button shows the count of non-archived
  adjustments for that entry and opens the adjustments dialog.

### Create / edit
- `FE-ENTRIES-006` [INFERRED] `"+ Neue Buchung"` opens the entry dialog with defaults
  (type Ausgabe, Wiederkehrend, monthly, today, first account).
- `FE-ENTRIES-007` [INFERRED] Amount is entered as a positive number; the type determines the
  stored sign (expense → negative, income/transfer → positive).
- `FE-ENTRIES-008` [INFERRED] Selecting type `"Umbuchung zwischen Konten"` reveals the
  `Zielkonto` field; it is hidden and sent as null for non-transfers.
- `FE-ENTRIES-009` [INFERRED] Selecting `"Einmalig"` hides the Rhythmus and end-date fields.
- `FE-ENTRIES-010` [INFERRED] Editing an existing booking pre-fills the form and sends
  `expected_updated_at`; a successful save toasts `"Gespeichert"` and refreshes.
- `FE-ENTRIES-011` [INFERRED] When editing, an informational note explains that changing the
  base amount acts retroactively and that date-based changes belong in "Anpassungen".
- `FE-ENTRIES-012` [INFERRED] A server validation error (e.g. transfer to the same account)
  is shown inline in the dialog via the localized message and the dialog stays open.

### Archive / restore / history
- `FE-ENTRIES-013` [INFERRED] `"Archivieren"` opens the archive confirmation; `"Wiederherstellen"`
  restores an archived booking; both refresh the list.
- `FE-ENTRIES-014` [INFERRED] `"Verlauf"` opens the per-record history dialog for that entry.

### Adjustments sub-dialog
- `FE-ENTRIES-015` [INFERRED] The adjustments dialog lists the entry's adjustments sorted by
  effective date, each showing the date, a change label, the note, and edit/archive (or
  restore) actions.
- `FE-ENTRIES-016` [README] A `set` adjustment is labeled `"neuer Betrag <eur>"`; a `percent`
  one `"<±p> %"` with `" jährlich wiederkehrend"` appended when repeat-yearly.
- `FE-ENTRIES-017` [INFERRED] `"+ Anpassung"` opens a form with `Gültig ab`, `Art der
  Änderung` (Neuer fester Betrag / Prozentuale Änderung), a `Neuer Betrag` field (only for
  set), a `Änderung in %` field + `Jedes Jahr erneut anwenden` checkbox (only for percent),
  and a note.
- `FE-ENTRIES-018` [INFERRED] For a `set` adjustment on a non-transfer, the stored amount
  keeps the entry's sign (an expense stays negative); for a transfer it is positive.
- `FE-ENTRIES-019` [INFERRED] Saving an adjustment refreshes the entry's adjustment list and
  (on dialog close) the forecast.
- `FE-ENTRIES-020` [README] The `Kategorie` field stays free text and offers the categories
  already used by any entry (archived ones included) as suggestions (a `datalist`). Names
  that differ only in case appear once, spelled the way they are used most often; the list
  is ordered by how often a category is used (most first, ties alphabetically). Empty
  categories are not offered.

### Grouping (B-012)
- `FE-ENTRIES-021` [README] The toolbar has a `Gruppieren nach` select with the options
  `Keine`, `Kategorie`, `Typ`, `Konto`, `Rhythmus`, `Art`. `Keine` is the default and renders the
  flat list exactly as without grouping.
- `FE-ENTRIES-022` [README] With any other option the table shows one header row
  (class `group-head`) per group, `"<label> · N Buchung(en)"`, followed by the group's rows
  in the usual order. Groups: `Kategorie` — case-insensitive, labeled with the most-used
  spelling (as in FE-ENTRIES-020), alphabetical, `Ohne Kategorie` last; `Typ` — `Einnahmen`,
  `Ausgaben`, `Umbuchungen`; `Konto` — the booking's (source) account, in account order;
  `Rhythmus` — by interval (`monatlich` first), `einmalig` last; `Art` — `fest`, then
  `geschätzt` (B-015).
- `FE-ENTRIES-023` [README] A group header shows the monthly equivalent of the group's
  non-archived recurring bookings as `"<±eur>/Monat"` (amount ÷ interval in months, from the
  base amount, rounded to the cent). One-time bookings are listed but not summed. Transfers
  are summed separately as `"Umbuchungen <eur>/Monat"`. A part with nothing to sum is omitted.
- `FE-ENTRIES-024` [README] Groups are open by default; clicking a group header folds or
  unfolds its rows.
- `FE-ENTRIES-025` [README] The chosen option is remembered in the browser across reloads,
  separately from the forecast view's choice. Without browser storage the view still works
  (the choice then lasts until the next reload).

### Estimated bookings (B-015)
- `FE-ENTRIES-026` [README] The entry form has an `Art` select with `Fest (…)` (default for a
  new booking) and `Geschätzt (…)`; it is pre-filled from the booking when editing and
  saved as `estimated: false/true`.
- `FE-ENTRIES-027` [README] The base amount of an estimated booking is shown with a leading
  `"≈ "` (fixed ones without). A group's monthly sum (FE-ENTRIES-023) that includes an
  estimated booking is marked `"≈ "` as well; the transfer sum is marked the same way.
- `FE-ENTRIES-028` [README] The bookings table has no inner vertical scroll area (no height
  cap): it grows to its full length and the page itself scrolls (B-014). Its column headers
  stay visible right below the sticky app header while scrolling.

## Examples
- Create `"Miete"`, type Ausgabe, 1200, monthly, from 2026-01-01 → appears as an expense of
  `−1.200,00 €`, cadence `monatlich`, period `ab 1.1.2026`.
- Add a `set` adjustment `3200` effective 2026-03 to a salary → the entry shows
  `"1 Anpassung"` and the forecast salary jumps in March.

## Out of scope / not specified
- Exact sort order of the booking list beyond "archived last, then by kind/name".
- Field tab order within dialogs.

## Open questions
None.
