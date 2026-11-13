# auth — HTTP Basic Auth middleware
ID prefix: AUTH
Layer: backend

## Purpose
Protects the whole app behind a password when one is configured, so a self-hosted instance
isn't open to anyone who can reach the port. Auth is all-or-nothing: either a password is
set and every request must authenticate (except the health probe), or no password is set
and the app is open.

## Interface
HTTP middleware applied to every request (`app.middleware("http")`). Configured by the app's `Settings`: `app_user` (default `admin`) and `app_password`
(default empty). In production these come from the env vars `APP_USER` / `APP_PASSWORD`
via `Settings.from_env()`; tests pass them directly to `Settings(...)`.

Clients authenticate with standard HTTP Basic Auth (`Authorization: Basic base64(user:pass)`).

## Dependencies & side effects
Reads `app_user`/`app_password` from the serving app's `Settings` on each request (no import-time capture). No DB, no files. On failure returns
`401` without calling the route.

## Behavior clauses

- `AUTH-001` [README] When `APP_PASSWORD` is non-empty, any request without valid Basic
  Auth credentials to a non-`/healthz` path returns `401` with a
  `WWW-Authenticate: Basic realm="Finanzprognose"` header, and the route does not run.
- `AUTH-002` [README] When `APP_PASSWORD` is empty, authentication is disabled: all
  requests are allowed through without credentials. [TEST harness runs this way]
- `AUTH-003` [INFERRED] `GET /healthz` is always reachable without credentials, even when a
  password is set (so the Docker healthcheck works).
- `AUTH-004` [INFERRED] A request with correct `APP_USER` + `APP_PASSWORD` is allowed and
  reaches the route.
- `AUTH-005` [INFERRED] A request with the wrong username, wrong password, malformed
  `Authorization` header, or a non-Basic scheme returns `401`.
- `AUTH-006` [INFERRED] Credential comparison is constant-time and covers both username and
  password (both must match).
- `AUTH-007` [INFERRED] The `401` applies uniformly to API routes **and** static assets
  (the middleware runs before the static mount), so the SPA itself is gated when a password
  is set.

## Examples
- `APP_PASSWORD='s3cret'`, `GET /api/state` with no header → `401` + `WWW-Authenticate`.
- Same, with `auth=('admin','s3cret')` → `200`.
- `APP_PASSWORD='s3cret'`, `GET /healthz` → `200` without credentials.

## Out of scope / not specified
- Session/cookie handling (there is none; Basic Auth only).
- Rate limiting or lockout on repeated failures (none).
- Changing the password at runtime (requires restart; see ENVIRONMENT testability gap #5).

## Open questions
None.
