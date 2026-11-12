# E2E — checkpoints & deviation
ID prefix: E2E-CP
Layer: e2e

## Purpose
The user periodically records the real account balance ("Ist-Stand"). The forecast then
continues from the real value and reports how far off it had been. This is the "keep the
forecast honest" journey.

## Preconditions
An account with a starting checkpoint and at least one booking between the start and the new
checkpoint date, so a deviation is meaningful.

## Scenarios

- `E2E-CP-001` [BROWSER-REQUIRED] **Given** the "Konten & Ist-Stände" view, **when** the user
  clicks `"+ Ist-Stand"` on an account, enters date `2026-02-20`, balance `5.000,00`, and
  saves, **then** a `"Gespeichert"` toast appears and the card's `"Letzter Ist-Stand"` shows
  `5.000,00 € am 20.2.2026`. [FE-ACCOUNTS]
- `E2E-CP-002` [HTTP-checkable] **Given** the same via API,
  `POST /api/checkpoints {account_id, date:'2026-02-20', balance:500000}` → `200`, and
  `GET /api/state` lists the checkpoint. [API-RES]
- `E2E-CP-003` [HTTP-checkable] **Given** a start checkpoint of `1.000,00` on 2026-01-15, a
  `-1.200,00` rent and a `-500,00` saving transfer before 2026-02-20, and a new checkpoint of
  `5.000,00`, **when** `GET /api/forecast?start=2026-02&months=1`, **then** the checkpoint item
  has `expected == 400000-120000-50000` and `deviation == 500000 - expected`. [FC-008/TEST
  test_full_flow]
- `E2E-CP-004` [BROWSER-REQUIRED] **Given** the forecast month containing the new checkpoint,
  **when** the user opens the month detail and expands the checkpoint item, **then** it shows
  `"Prognose war <eur>, tatsächlich <eur> → Abweichung <signed eur>"` and
  `"Ab hier rechnet die Prognose mit dem echten Kontostand weiter."`. [FE-FORECAST-012]
- `E2E-CP-005` [HTTP-checkable] **Given** an account with **no** checkpoint, **when**
  `GET /api/forecast`, **then** the response `warnings` contains
  `{code:'no_checkpoint', account_id:<id>}` and that account's months have null opening/closing.
  [FC-011]
- `E2E-CP-006` [BROWSER-REQUIRED] **Given** such an account, **when** the user views its card,
  **then** `"Letzter Ist-Stand"` shows `"keiner – Konto wird nicht berechnet"`, and the
  forecast view shows a `.banner.warn` with
  `"Konto „<name>“ hat keinen Ist-Stand und kann nicht berechnet werden."`. [FE-ACCOUNTS-003/
  FE-FORECAST-014]
- `E2E-CP-007` [HTTP-checkable] **Given** a booking dated on the same day as a checkpoint,
  **when** `GET /api/forecast`, **then** the booking is applied before the checkpoint resets
  the balance (same-day order). [FC-007]

## Out of scope
- The arithmetic of multiple interleaved checkpoints beyond the single-deviation case (covered
  by backend `FC` clauses).
