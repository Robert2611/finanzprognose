# E2E — archive, restore & undo (data safety)
ID prefix: E2E-ARCH
Layer: e2e

## Purpose
The data-safety promises in action: records can be archived (excluded from the forecast) and
restored, every change is logged, and any single change can be undone from the history —
nothing is ever truly deleted.

## Preconditions
A database with at least one account, one booking, and some edit history.

## Scenarios

### Archive / restore
- `E2E-ARCH-001` [BROWSER-REQUIRED] **Given** the "Buchungen" view, **when** the user clicks
  `"Archivieren"` on a booking and confirms, **then** a `"Archiviert"` toast appears and the
  booking disappears from the default list. [FE-ENTRIES/FE-FORM]
- `E2E-ARCH-002` [BROWSER-REQUIRED] **Given** archived bookings exist, **when** the user ticks
  `"Archivierte zeigen"`, **then** the archived booking reappears with the `archived` styling
  and a `"Wiederherstellen"` button. [FE-ENTRIES-001]
- `E2E-ARCH-003` [BROWSER-REQUIRED] **Given** an archived booking shown, **when** the user
  clicks `"Wiederherstellen"`, **then** a `"Wiederhergestellt"` toast appears and it returns to
  the active list. [FE-FORM-015]
- `E2E-ARCH-004` [HTTP-checkable] **Given** a booking, **when** `POST /api/entries/{id}/archive`
  then `GET /api/forecast`, **then** the booking no longer contributes any item; after
  `POST /api/entries/{id}/restore` it contributes again. [API-RES-013/FC-029]
- `E2E-ARCH-005` [HTTP-checkable] **Given** any record, **when** archived, **then** it is still
  present in `GET /api/state` with `archived:true` (archived ≠ deleted). [API-RES-019]

### Undo from history
- `E2E-ARCH-006` [BROWSER-REQUIRED] **Given** an account renamed from `"X"` to `"Y"`, **when**
  the user opens "Verlauf", **then** the newest row shows action `"Geändert"` and a diff
  `Name: X → Y`. [FE-AUDIT-003]
- `E2E-ARCH-007` [BROWSER-REQUIRED] **Given** that history row, **when** the user clicks
  `"Rückgängig"` and confirms, **then** a `"Rückgängig gemacht"` toast appears, a new
  `"Rückgängig"` row appears at the top showing
  `"Rückgängig gemacht: Protokolleintrag #<id>"`, and the account name is `"X"` again.
  [FE-AUDIT-005/FE-AUDIT-007]
- `E2E-ARCH-008` [HTTP-checkable] **Given** an update audit row id, **when**
  `POST /api/audit/{id}/revert`, **then** it returns the record with the pre-update values and
  `GET /api/audit` shows a new `revert` row with `reverts_id == id`. [API-AUDIT-007/TEST
  test_optimistic_locking_and_audit]
- `E2E-ARCH-009` [HTTP-checkable] **Given** any data table, **when** a raw `DELETE` is
  attempted at the DB level, **then** it is rejected and the row remains (DB trigger). [DATA-001/
  TEST test_nothing_can_be_deleted] *(DB-level check, not via the UI.)*
- `E2E-ARCH-010` [BROWSER-REQUIRED] **Given** a booking row, **when** the user clicks
  `"Verlauf"`, **then** a modal shows that record's change history and a `"Schließen"` button.
  [FE-AUDIT-009]

## Out of scope
- Revert-of-revert chains beyond one redo (specified in `DB-AUDIT-015`, tested there).
- Cascading effects of archiving an account referenced by entries: there are none by design
  (`API-RES-020`, `FE-ACCOUNTS-013`).
