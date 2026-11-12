# Frontend — accounts view ("Konten & Ist-Stände")
ID prefix: FE-ACCOUNTS
Layer: frontend

## Purpose
Where the user manages accounts and their actual-balance checkpoints ("Ist-Stände"). Each
account is a card showing its last actual balance and the list of checkpoints, with
create/edit/archive/restore for both the account and its checkpoints.

## Interface
Rendered into `#main` when view = `konten`. Reads accounts/checkpoints from `S.data`.
Stable DOM:
- `.toolbar` with heading `"Konten & Ist-Stände"`, an `"Archivierte zeigen"` checkbox, and a
  `"+ Neues Konto"` primary button.
- `.cards` containing one `.panel` per account (archived panels have class `archived` and are
  dimmed). Empty state: `"Noch keine Konten."`.
- Per card: the account name, a kind tag (German `KINDS` label), `"Bearbeiten"`/`"Archivieren"`
  (or `"Wiederherstellen"`), optional note, a `"Letzter Ist-Stand"` line, an `"Ist-Stände"`
  sub-section with `"+ Ist-Stand"`, and a table of checkpoints.
- Each checkpoint row: date (the earliest active one tagged `"Startstand"`), balance, note,
  and `"Bearbeiten"`/`"Archivieren"` (or `"Wiederherstellen"`).

Dialogs: `accountDialog(acc?)`, `checkpointDialog(accountId?, cp?)` (both via `formDialog`).

## Dependencies & side effects
`POST/PUT /api/accounts`, `/api/checkpoints` (+ archive/restore). Refreshes after saves.

## Behavior clauses

- `FE-ACCOUNTS-001` [INFERRED] The view shows one card per non-archived account by default;
  `"Archivierte zeigen"` includes archived accounts (and archived checkpoints), dimmed.
- `FE-ACCOUNTS-002` [INFERRED] Each card shows the account name and a kind tag using the
  German `KINDS` label (e.g. `Girokonto`, `Tagesgeld`).
- `FE-ACCOUNTS-003` [INFERRED] `"Letzter Ist-Stand"` shows the most recent active
  checkpoint's balance and date, or `"keiner – Konto wird nicht berechnet"` when the account
  has no active checkpoint.
- `FE-ACCOUNTS-004` [README][INFERRED] The earliest active checkpoint of an account is tagged
  `"Startstand"` in the list — this label is derived in the frontend, not stored (the stored
  note is empty). [B-005 phase 4]
- `FE-ACCOUNTS-005` [INFERRED] Checkpoints are listed newest-date-first within a card.
- `FE-ACCOUNTS-006` [INFERRED] `"+ Neues Konto"` opens the account dialog with a `Name`,
  `Kontoart` select, and (for new accounts only) `Aktueller Kontostand` + `Stand vom (abends)`
  plus a `Notiz` field.
- `FE-ACCOUNTS-007` [INFERRED] Creating an account posts to `/api/accounts` with the start
  balance and date; the resulting account and its starting checkpoint appear after refresh.
- `FE-ACCOUNTS-008` [INFERRED] Editing an account shows only `Name`, `Kontoart`, `Notiz`
  (no start balance/date) and sends `expected_updated_at`.
- `FE-ACCOUNTS-009` [INFERRED] `"+ Ist-Stand"` (card-level or editing one) opens the
  checkpoint dialog with `Konto`, `Datum (Stand am Abend)`, `Kontostand`, `Notiz`, and an
  intro explaining the balance is the end-of-day actual value and same-day bookings count as
  included.
- `FE-ACCOUNTS-010` [INFERRED] Saving a checkpoint refreshes the card (and the forecast);
  a `"Gespeichert"` toast is shown.
- `FE-ACCOUNTS-011` [INFERRED] Archiving/restoring an account or a checkpoint uses the shared
  archive dialog / restore action and refreshes.
- `FE-ACCOUNTS-012` [INFERRED] An archived account's card hides its edit/add actions and
  offers only `"Wiederherstellen"`.

## Examples
- New account `"Giro"`, kind Girokonto, 1.000,00 € on 2026-01-15 → a card for Giro with a
  checkpoint row dated 15.1.2026 tagged `"Startstand"`, balance `1.000,00 €`, and
  `"Letzter Ist-Stand"` showing the same.
- Add a later checkpoint 2026-02-20 / 5.000,00 € → it becomes the `"Letzter Ist-Stand"`.

## Out of scope / not specified
- Exact card ordering between accounts.
- The dimming opacity value for archived cards.

## Open questions
None.
