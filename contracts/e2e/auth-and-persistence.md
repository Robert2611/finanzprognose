# E2E — authentication & persistence
ID prefix: E2E-AUTH
Layer: e2e

## Purpose
When a password is configured the whole app is gated behind HTTP Basic Auth; when it isn't,
the app is open. Separately, all data persists across reloads (it lives in SQLite, not the
browser).

## Preconditions
Two app configurations are relevant: `APP_PASSWORD` set (gated) and empty (open). For
persistence, any running instance with a database.

## Scenarios

### Auth
- `E2E-AUTH-001` [HTTP-checkable] **Given** `APP_PASSWORD` set, **when** `GET /api/state`
  without credentials, **then** the response is `401` with a `WWW-Authenticate: Basic` header.
  [AUTH-001]
- `E2E-AUTH-002` [HTTP-checkable] **Given** `APP_PASSWORD` set, **when** `GET /api/state` with
  the correct `APP_USER`/`APP_PASSWORD`, **then** the response is `200`. [AUTH-004]
- `E2E-AUTH-003` [HTTP-checkable] **Given** `APP_PASSWORD` set, **when** `GET /api/state` with
  a wrong password, **then** the response is `401`. [AUTH-005]
- `E2E-AUTH-004` [HTTP-checkable] **Given** `APP_PASSWORD` set, **when** `GET /healthz` without
  credentials, **then** the response is `200 {"ok":true}` (health is always open). [AUTH-003]
- `E2E-AUTH-005` [HTTP-checkable] **Given** `APP_PASSWORD` empty, **when** `GET /api/state`
  without credentials, **then** the response is `200` (auth disabled). [AUTH-002]
- `E2E-AUTH-006` [BROWSER-REQUIRED] **Given** `APP_PASSWORD` set, **when** the user opens `/`
  and provides valid credentials to the browser's Basic-Auth prompt, **then** the SPA loads and
  the "Prognose" view renders. [AUTH-007/FE-NAV]

### Persistence across reloads
- `E2E-AUTH-007` [BROWSER-REQUIRED] **Given** the user created an account and some bookings,
  **when** the browser is reloaded, **then** the same accounts/bookings are still shown (state
  is re-fetched from `/api/state`, not browser storage). [FE-NAV-001]
- `E2E-AUTH-008` [HTTP-checkable] **Given** data created via the API, **when** a new client
  session calls `GET /api/state`, **then** it returns the same data (server-side persistence).
  [API-STATE]
- `E2E-AUTH-009` [BROWSER-REQUIRED] **Given** the backend is stopped, **when** the user opens or
  reloads the app, **then** `#main` shows a `.banner.err` error banner rather than a blank page.
  [FE-NAV-008]
- `E2E-AUTH-010` [BROWSER-REQUIRED] **Given** the backend is stopped, **when** the status pill
  refreshes, **then** it shows `"Server nicht erreichbar"` (class `err`). [FE-BACKUP-008]

## Out of scope
- Password rotation at runtime (requires restart; ENVIRONMENT gap #5).
- Browser credential caching behavior (handled by the browser, not the app).
