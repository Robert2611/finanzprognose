# Deploy — automatic update on the Docker host
ID prefix: DEPLOY-UPD
Layer: deploy

## Purpose
Installs new releases without a shell on the server (B-026). `deploy/auto-update.sh` runs on
the Docker host, started by systemd every 15 minutes (`finanzprognose-update.timer`) and as soon
as the app asks for an update (`finanzprognose-update.path`, which watches
`updater/request.json`). It reuses `update.sh` for the update itself. The host is not reachable
from outside, so nothing is pushed to it: it only pulls from ghcr.io.

## Interface
- `auto-update.sh` (no arguments), run as root from the install directory (`/opt/finanzprognose`).
- `.env`: `APP_VERSION` (the installed release), `AUTO_UPDATE` = `auto` (default, also for a
  missing or unknown value) or `notify`.
- Folder `updater/` next to `.env`, mounted into the container at `/updater` (see
  `backend/updater.md`):
  - `status.json` (written here):
    ```
    { "schema": 1, "mode": "auto"|"notify", "state": "idle"|"updating",
      "current": str|null, "latest": str|null, "checked_at": str|null,
      "check_error": "pull_failed"|"bad_version_label"|null, "target": str|null,
      "failed_version": str|null,
      "last_update": {"from": str|null, "to": str|null,
                      "result": "success"|"rolled_back"|"rollback_failed"|"failed",
                      "at": str|null} | null }
    ```
  - `request.json` (written by the app, consumed here): `{"requested_at": str, "version": str|null}`.
  - `last-update.log`: the output of the last `update.sh` run.
  - `state`, `.lock`: this script's own files.
- `update.sh [--auto-rollback] [vX.Y.Z]`, exit codes: `0` updated or already up to date, `1`
  failed before or while switching, `2` unhealthy and rolled back, `3` rollback failed too.

## Behavior clauses

- `DEPLOY-UPD-001` [README] Every run pulls `:latest`, reads its version label and writes
  `status.json` with `schema: 1`, the mode, `state: "idle"`, `current` (`APP_VERSION`),
  `latest` and `checked_at`. Without a new release it changes nothing else.
- `DEPLOY-UPD-002` [README] In `auto` mode a `latest` that differs from `APP_VERSION` is
  installed with `update.sh --auto-rollback <latest>`; the result is recorded in `last_update`
  (`from`, `to`, `result: "success"`, `at`) and the output in `last-update.log`.
- `DEPLOY-UPD-003` [README] In `notify` mode nothing is installed without a request. A missing
  or unknown `AUTO_UPDATE` means `auto`.
- `DEPLOY-UPD-004` [README] A pending `request.json` is removed and causes an update in either
  mode: to its `version` if that is a valid release tag, otherwise to `latest`. Nothing in the
  file is ever executed.
- `DEPLOY-UPD-005` [README] `update.sh` exit code `2`/`3`/other becomes `result`
  `rolled_back`/`rollback_failed`/`failed`, and `failed_version` is set to the target. The timer
  does not retry `failed_version`; a request does, and a newer release is installed as usual. A
  successful update clears `failed_version`.
- `DEPLOY-UPD-006` [README] If the check fails, `check_error` is set (`pull_failed`,
  `bad_version_label`), the last known `latest` is kept and no automatic update starts (it would
  fail to pull as well and mark the release as failed).
- `DEPLOY-UPD-007` [README] While `update.sh` runs, `status.json` has `state: "updating"` and
  `target` set to the version being installed.
- `DEPLOY-UPD-008` [README] Runs never overlap: a run that can't take `updater/.lock` exits 0
  at once without touching anything (the path unit starts it again if a request is still there).
- `DEPLOY-UPD-009` [INFERRED] `status.json` is always valid JSON: only versions, codes and
  timestamps are written; any other value (e.g. a broken `APP_VERSION`) becomes `null`.
- `DEPLOY-UPD-010` [INFERRED] An `update.sh` without `--auto-rollback` (after a rollback to a
  release from before B-026) is called without the flag.
- `DEPLOY-UPD-011` [README] `update.sh --auto-rollback`: if the new version does not become
  healthy, the database of the failed version is moved to `data/failed-update_<timestamp>/`, the
  copy from `data/pre-update/` is restored, the previous version is started again, and the exit
  code is `2`. Nothing is deleted.
- `DEPLOY-UPD-012` [README] If that rollback fails too, `update.sh` prints the manual steps and
  exits `3`. Without `--auto-rollback` a failed update keeps the old behavior: manual steps,
  exit `1`.
- `DEPLOY-UPD-013` [README] `install.sh` and `update.sh` copy `auto-update.sh` and the three
  systemd units out of the image (the units with the install directory filled in) and enable the
  timer and the path unit. A release without these files leaves the installed ones alone.

## Out of scope / not specified
- Notifications outside the app (e-mail, push).
- Avoiding the daily backup time: a backup cut off by the restart leaves only a temp file and
  is caught up after the start (`BKP-001`).
