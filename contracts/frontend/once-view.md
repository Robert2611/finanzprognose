# Frontend — one-time bookings view ("Einmalig")
ID prefix: FE-ONCE
Layer: frontend

## Purpose
Where the user manages single payments into or out of an account (and single transfers
between accounts): a tax refund, a holiday, a new washing machine. Recurring bookings have
their own view (`entries-view.md`, FE-ENTRIES); keeping the two apart (B-027) means each
dialog only asks for what its kind needs, and a new booking never has to be switched from
"recurring" to "once".

## Interface
Rendered into `#main` when view = `einmalig` (`once.js`). Reads bookings with
`kind = 'once'` from in-memory state `S.data`. The dialog is `onceDialog(entry?)` in
`entry_dialogs.js`.
Stable DOM:
- `.toolbar` with heading `"Einmalige Buchungen"`, an `"Archivierte zeigen"` checkbox, a
  `Gruppieren nach` select (FE-ONCE-008), and a `"+ Neue Buchung"` primary button.
- A `table` (`.table-wrap.page-scroll`, as FE-ENTRIES-028) with headers
  `Datum, Bezeichnung, Typ, Konto, Betrag`, plus an action column. Archived rows have class
  `archived`.

## Dependencies & side effects
`POST/PUT /api/entries` (+ archive/restore). `GET /api/audit` for the history dialog.
Refreshes state after saves. No API or schema change: a one-time booking is an entry with
`kind = 'once'`, `interval_months = 1` and `end_date = null`.

## Behavior clauses

- `FE-ONCE-001` [README] The view lists the non-archived one-time bookings; recurring
  bookings never appear here. Ticking `"Archivierte zeigen"` also lists archived ones (class
  `archived`, after the active ones). The checkbox is shared with the recurring view.
- `FE-ONCE-002` [README] Rows are sorted by date (oldest first; archived last, ties by name).
  Each row shows the date, the name (with optional category tag and note), the type label
  (`Einnahme`/`Ausgabe`/`Umbuchung`), the account (and `→ target` for transfers), and the
  amount (signed for income/expense, unsigned for transfers, `"≈ "` in front when estimated).
  Actions: `"Bearbeiten"`, `"Archivieren"` (or `"Wiederherstellen"`), `"Verlauf"`.
- `FE-ONCE-003` [README] An empty list renders a single `"Noch keine einmaligen Buchungen."`
  row.
- `FE-ONCE-004` [README] `"+ Neue Buchung"` opens the dialog `"Neue einmalige Buchung"` with
  the fields `Bezeichnung`, `Typ` (Einnahme/Ausgabe/Umbuchung zwischen Konten), `Konto`,
  `Zielkonto` (only for a transfer), `Betrag (positiv eingeben)`, `Art` (Fest/Geschätzt),
  `Datum`, `Planung` (FE-ENTRIES-029), `Kategorie (optional)` (with suggestions as
  FE-ENTRIES-020), `Notiz (optional)` —
  no frequency, rhythm or end date. Defaults: type Ausgabe, today, first active account, fest.
- `FE-ONCE-005` [README] Saving sends `kind: 'once'`, `interval_months: 1`, `end_date: null`
  and the sign from the type (expense negative, income and transfer positive); a
  `"Gespeichert"` toast appears and the list refreshes.
- `FE-ONCE-006` [README] `"Bearbeiten"` opens the same dialog pre-filled (title
  `Buchung „<name>“ bearbeiten`), sends `expected_updated_at`, and keeps `kind: 'once'`. It
  has no note about retroactive base-amount changes (that note belongs to recurring bookings).
- `FE-ONCE-007` [README] `"Archivieren"` opens the archive confirmation, `"Wiederherstellen"`
  restores, `"Verlauf"` opens the record's history. A one-time booking has no adjustments
  column; only when it already has adjustments (from before B-027) does the row show the
  `"N Anpassung(en)"` button that opens the adjustments dialog (FE-ENTRIES-015).
- `FE-ONCE-008` [README] The `Gruppieren nach` select offers `Keine`, `Kategorie`, `Typ`,
  `Konto`, `Art` (no `Rhythmus`), grouped as in FE-ENTRIES-022 and folding as in
  FE-ENTRIES-024. A group header shows `"<label> · N Buchung(en)"` followed by
  `"· Summe <±eur>"` — the plain total of its non-archived, non-optional non-transfer
  bookings — and
  `"· Umbuchungen <eur>"` for its transfers; a part with nothing to sum is omitted, and a sum
  that includes an estimated booking is marked `"≈ "`. The choice is remembered across
  reloads, separately from the recurring and forecast views.

## Examples
- Create `"Waschmaschine"`, Ausgabe, `650`, Datum `2026-04-12` → stored as
  `{kind:'once', amount:-65000, start_date:'2026-04-12', end_date:null}`, listed as
  `12.4.2026 · Waschmaschine · Ausgabe · Giro · -650,00 €`.

## Out of scope / not specified
- Converting a booking between recurring and one-time in the UI (archive it and create a new
  one instead).

## Open questions
None.
