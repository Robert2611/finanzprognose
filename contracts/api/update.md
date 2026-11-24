# API — automatic update
ID prefix: API-UPD
Layer: api

## Purpose
The HTTP side of `backend/updater.md` (B-026): the "Version" page reads the status and asks the
host for an update.

## Interface
- `GET /api/update/status` → `200 UpdateStatusOut`:
  ```
  { "enabled": bool, "running_version": str,
    "host": { "mode", "state", "current", "latest", "checked_at", "check_error", "target",
              "failed_version", "last_update": {"from", "to", "result", "at"}|null } | null,
    "host_error": {"code", "params"}|null, "update_available": bool,
    "request_pending": bool, "log_tail": [str] }
  ```
- `POST /api/update/request` with `{"version": "vX.Y.Z"}` (optional) → `202 UpdateStatusOut`.

## Behavior clauses

- `API-UPD-001` [README] `GET /api/update/status` returns the `UPDATER-001..005` data in the
  shape above; `last_update` keeps the key `from`.
- `API-UPD-002` [README] `POST /api/update/request` writes the request (`UPDATER-006`) and
  returns `202` with the new status (`request_pending: true`).
- `API-UPD-003` [README] A `version` that isn't a release tag (`vX.Y.Z[-suffix]`) gets
  `422 validation_error` and nothing is written.
- `API-UPD-004` [README] Not configured → `409 {code: "updater_not_configured"}`; an update
  running → `409 {code: "update_in_progress"}`; the folder can't be written →
  `503 {code: "updater_unavailable"}`.
- `API-UPD-005` [README] Both endpoints are behind the Basic auth like every `/api` route.
