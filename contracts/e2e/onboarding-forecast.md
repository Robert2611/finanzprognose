# E2E — onboarding to first forecast
ID prefix: E2E-ONBOARD
Layer: e2e

## Purpose
A brand-new user opens the app, is guided to create their first account with a starting
balance, and immediately sees a forecast. This is the "empty database → something useful"
journey.

## Preconditions
Fresh empty database. `APP_PASSWORD` empty (or valid credentials supplied). App served at
the base URL.

## Scenarios (Given/When/Then)

- `E2E-ONBOARD-001` [BROWSER-REQUIRED] **Given** an empty database, **when** the user opens
  `/`, **then** the "Prognose" view shows a `"Willkommen"` panel with an
  `"Erstes Konto anlegen"` button. [README/FE-FORECAST]
- `E2E-ONBOARD-002` [BROWSER-REQUIRED] **Given** the welcome screen, **when** the user clicks
  `"Erstes Konto anlegen"`, **then** a modal account form opens with fields `Name`,
  `Kontoart`, `Aktueller Kontostand`, `Stand vom (abends)`, `Notiz`. [FE-ACCOUNTS/FE-FORM]
- `E2E-ONBOARD-003` [BROWSER-REQUIRED] **Given** the account form, **when** the user enters
  name `"Giro"`, balance `1.000,00`, date `2026-01-15` and submits, **then** a
  `"Gespeichert"` toast appears and the welcome screen is replaced by the forecast
  (toolbar + chart `#chart` + month table `#ftable`). [FE-ACCOUNTS/FE-FORECAST]
- `E2E-ONBOARD-004` [HTTP-checkable] **Given** the same action via API, **when**
  `POST /api/accounts {name:'Giro', kind:'checking', start_balance:100000,
  start_date:'2026-01-15'}`, **then** it returns `200`, and `GET /api/state` shows one
  account and one checkpoint `{date:'2026-01-15', balance:100000}`. [API-ACC]
- `E2E-ONBOARD-005` [HTTP-checkable] **Given** the created account, **when**
  `GET /api/forecast?start=2026-01&months=12`, **then** the account's starting month opens
  at the start balance and the months array has length 12. [API-FC/FC]
- `E2E-ONBOARD-006` [BROWSER-REQUIRED] **Given** the forecast is shown, **when** the user
  clicks a month row in `#ftable`, **then** that row gains the `selected` class and the
  `#fdetail` panel shows that month's `"Anfangsstand"`/`"Endstand"` for the account.
  [FE-FORECAST]
- `E2E-ONBOARD-007` [BROWSER-REQUIRED] **Given** no accounts and the backend reachable,
  **when** the page loads, **then** the header shows the seven nav buttons (`Prognose`,
  `Wiederkehrend`, `Einmalig`, `Konten & Ist-Stände`, `Verlauf`, `Sicherung`, `Version`) and
  the backup pill.
  [FE-NAV]

## Out of scope
- Chart pixel rendering.
- Validation specifics (covered in `bookings-adjustments` and backend contracts).
