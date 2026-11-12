# E2E — bookings & adjustments
ID prefix: E2E-BOOK
Layer: e2e

## Purpose
The user records income, expenses, and transfers, then refines a booking with a date-based
adjustment (a raise, inflation), and sees the forecast and its explanations update. Also
covers the main validation errors shown to the user.

## Preconditions
A database with at least two accounts, each with a starting checkpoint (so the forecast
computes). `APP_PASSWORD` empty or credentials supplied.

## Scenarios

### Create bookings
- `E2E-BOOK-001` [BROWSER-REQUIRED] **Given** the "Buchungen" view, **when** the user clicks
  `"+ Neue Buchung"`, enters name `"Gehalt"`, type `Einnahme`, amount `3.000,00`, Wiederkehrend
  monthly, start `2026-01-31`, and submits, **then** a `"Gespeichert"` toast appears and the
  booking row shows `"Gehalt"`, type `Einnahme`, `+3.000,00 €`, cadence `monatlich`. [FE-ENTRIES]
- `E2E-BOOK-002` [HTTP-checkable] **Given** the same via API,
  `POST /api/entries {account_id, name:'Gehalt', kind:'recurring', amount:300000,
  start_date:'2026-01-31', interval_months:1}` → `200`, and `GET /api/state` lists the entry
  with `amount:300000`. [API-RES]
- `E2E-BOOK-003` [BROWSER-REQUIRED] **Given** the entry form, **when** the user picks type
  `"Umbuchung zwischen Konten"`, **then** a `Zielkonto` select appears; submitting a transfer
  of `500,00` from account A to B saves successfully. [FE-ENTRIES]
- `E2E-BOOK-004` [HTTP-checkable] **Given** a transfer entry, **when**
  `GET /api/forecast`, **then** the source account shows a `-50000` item and the target a
  `+50000` item on the same date, and the transfer is excluded from month income/expense.
  [FC-026/FC-005]

### Adjustments
- `E2E-BOOK-005` [BROWSER-REQUIRED] **Given** the salary booking, **when** the user opens its
  `"N Anpassung(en)"` dialog, clicks `"+ Anpassung"`, chooses `"Neuer fester Betrag"`
  `3.200,00` effective `2026-03-01`, and saves, **then** the adjustment list shows
  `"neuer Betrag 3.200,00 €"` from that date. [FE-ENTRIES]
- `E2E-BOOK-006` [HTTP-checkable] **Given** that adjustment via API, **when**
  `GET /api/forecast` for a range including March, **then** the salary item in March has
  `amount == 320000` and an explanation step `{code:'set_amount'}`. [FC-019]
- `E2E-BOOK-007` [BROWSER-REQUIRED] **Given** the forecast month detail for March, **when**
  the user expands the salary item, **then** the derivation lists a base-amount line and a
  `"ab 01.03.2026: neuer Betrag 3.200,00 €"` line, then `"Kontostand danach: …"`. [FE-FORECAST]
- `E2E-BOOK-008` [HTTP-checkable] **Given** a `percent` yearly adjustment of `+2%` from
  `2026-01-01` on a `-1.000,00` entry, **when** `GET /api/forecast`, **then** the amount on
  2028-01-01 is `-106121` (3× compounding). [FC-021/TEST test_percent_yearly]

### Validation errors shown to the user
- `E2E-BOOK-009` [BROWSER-REQUIRED] **Given** the entry form, **when** the user sets a
  transfer with the same source and target account and submits, **then** the dialog stays open
  and shows `"Quell- und Zielkonto müssen verschieden sein."`. [FE-FORM/ERRENV/FE-CORE]
- `E2E-BOOK-010` [HTTP-checkable] **Given** the same via API,
  `POST /api/entries {... to_account_id == account_id, amount:100 ...}` → `422` with
  `{"code":"validation_error", params.errors[*].code includes "transfer_same_account"}`.
  [SCH-012/ERRENV]
- `E2E-BOOK-011` [BROWSER-REQUIRED] **Given** the entry form, **when** the user submits with an
  amount of `0`, **then** it is rejected with `"Der Betrag darf nicht 0 sein."`. [SCH-014/FE-CORE]
- `E2E-BOOK-012` [BROWSER-REQUIRED] **Given** the entry form with a required field left empty,
  **when** the user submits, **then** the form blocks with `"Bitte „<label>“ ausfüllen."`
  and makes no request. [FE-FORM-007]
- `E2E-BOOK-013` [BROWSER-REQUIRED] **Given** two browser tabs editing the same booking,
  **when** the second tab saves after the first already saved, **then** it shows the conflict
  message `"Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut
  versuchen."`. [API-RES-008/FE-CORE-013]

## Out of scope
- Exact forecast chart appearance.
- Ordering of booking rows.
