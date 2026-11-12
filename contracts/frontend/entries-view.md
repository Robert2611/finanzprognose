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
- `.toolbar` with heading `"Buchungen"`, an `"Archivierte zeigen"` checkbox, and a
  `"+ Neue Buchung"` primary button.
- A `table` with headers `Bezeichnung, Typ, Konto, Grundbetrag, Rhythmus, Zeitraum,
  Anpassungen`, plus an action column. Archived rows have class `archived`. Empty list shows
  `"Noch keine Buchungen."`.
- Per row action buttons: `"Bearbeiten"`, `"Archivieren"` (or `"Wiederherstellen"` when
  archived), `"Verlauf"`, and an `"N Anpassung(en)"` button.

Dialogs (via `formDialog`):
- `entryDialog(entry?)` — fields: `Bezeichnung`, `Typ` (Einnahme/Ausgabe/Umbuchung zwischen
  Konten), `Konto`, `Zielkonto` (only for transfer), `Betrag (positiv eingeben)`,
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
