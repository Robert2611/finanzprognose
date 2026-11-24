# updater_link — the app's side of the automatic update
ID prefix: UPDATER
Layer: backend

## Purpose
Lets the app show what the host updater (`deploy/auto-update.md`) reports and ask it for an
update, without the app touching Docker or the host (B-026). The only link is a shared folder.

## Interface
`app/updater_link.py`: `status(s) -> dict` (the `UpdateStatusOut` data) and
`request_update(s, version=None)`, raising `NotConfigured`, `UpdateInProgress` or `OSError`.
Folder: `Settings.update_dir` (`UPDATE_DIR`, `/updater` in the production compose file; empty =
not configured). Files: `status.json` and `last-update.log` (host, read only), `request.json`
(written here).

## Behavior clauses

- `UPDATER-001` [README] With `update_dir` empty, `status` returns `enabled: false`, the
  `running_version` and no host data, and `request_update` raises `NotConfigured` without
  writing anything.
- `UPDATER-002` [README] `status.json` becomes `host` (unknown keys are ignored). A missing file
  gives `host_error {code: "updater_status_missing"}`; invalid JSON, an unknown `mode`, `state`
  or `result`, or a file over 256 KiB gives `host_error {code: "updater_status_unreadable"}`.
- `UPDATER-003` [README] `update_available` is true iff `host.latest` is set and differs from
  `running_version` (`Settings.app_version`, the image's `APP_VERSION`).
- `UPDATER-004` [README] `request_pending` is true iff `request.json` exists.
- `UPDATER-005` [INFERRED] `log_tail` holds the last 40 lines of `last-update.log`, each cut to
  500 characters; `[]` without the file.
- `UPDATER-006` [README] `request_update` writes `request.json` as
  `{"requested_at": <local ISO time>, "version": <version or null>}` via a temp file and a
  rename (no temp file is left), replacing an earlier pending request.
- `UPDATER-007` [README] While `host.state` is `updating`, `request_update` raises
  `UpdateInProgress` and writes nothing.
- `UPDATER-008` [README] The app never changes or removes `status.json`, `last-update.log` or
  any other host file; `status` only reads.
