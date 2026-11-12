# API — backup status & manual run
ID prefix: API-BKP
Layer: api

## Purpose
Lets the UI show whether backups are healthy and trigger one on demand. The heavy lifting
(consistency, atomicity, failure handling) is specified in `backup/backup.md`; this file is
the HTTP contract for the two endpoints.

## Interface
- `GET /api/backup/status` → `200 BackupStatusOut`:
  ```
  {
    "backup_dir": str, "backup_time": str, "current_version": int, "pending_changes": bool,
    "last_attempt": str|null, "last_reason": str|null, "last_success": str|null,
    "last_version": int|null, "last_file": str|null, "last_result": str|null,
    "last_error": str|null, "last_scheduled_run": str|null,
    "files": [ {"name": str, "size": int, "mtime": str}, ... ]
  }
  ```
  `files` lists up to the newest 30 `finanzen_*.sqlite` backups.
- `POST /api/backup/run` → `200 BackupStatusOut` — runs a manual backup (not forced; still
  skipped if unchanged) and returns the resulting status.

## Dependencies & side effects
`status` reads `backup_status.json` and lists `BACKUP_DIR`. `run` may write backup
artifacts to `BACKUP_DIR` and update `backup_status.json` (see `backup/backup.md`).

## Behavior clauses

- `API-BKP-001` [TEST] `GET /api/backup/status` includes at least
  `{backup_dir, backup_time, current_version, pending_changes, files}`, with
  `pending_changes` a boolean. [TEST: `test_backup_status_contract`]
- `API-BKP-002` [INFERRED] `current_version` equals the backend `data_version`;
  `pending_changes` is `true` iff `current_version != last_version` (something changed since
  the last successful backup).
- `API-BKP-003` [INFERRED] `backup_dir` echoes the configured `BACKUP_DIR`; `backup_time`
  echoes `BACKUP_TIME`.
- `API-BKP-004` [TEST] When the marker guard is on and `.nas-marker` is missing,
  `POST /api/backup/run` returns a status with `last_result == "error"` and a `last_error`
  mentioning `.nas-marker`. [TEST: `test_backup`]
- `API-BKP-005` [TEST] With the marker present and changes pending, `POST /api/backup/run`
  returns `last_result == "ok"`. [TEST: `test_backup`]
- `API-BKP-006` [TEST] A second `POST /api/backup/run` with nothing changed returns
  `last_result == "unchanged"`. [TEST: `test_backup`]
- `API-BKP-007` [TEST] After a data change, a further `POST /api/backup/run` returns
  `last_result == "ok"` and a new backup file (old ones are kept). [TEST: `test_backup`]
- `API-BKP-008` [INFERRED] `files` is sorted newest-first and capped at 30; each entry has
  `name`, `size` (bytes), `mtime` (ISO seconds).
- `API-BKP-009` [INFERRED] `POST /api/backup/run` is a manual (`reason`-tagged) run and is
  not forced — it still returns `unchanged` when `data_version` matches the last backup and
  that file still exists.

## Examples
- Marker missing → `run` → `{last_result:'error', last_error:'…​.nas-marker…'}`. [TEST]
- Marker present, pending change → `run` → `{last_result:'ok', last_file:'finanzen_…sqlite'}`.
  [TEST]

## Out of scope / not specified
- Artifact internals, naming, atomicity, retries — see `backup/backup.md`.
- Exact German-free vs. German content of `last_error` (today it is German text from the
  backend; see OPEN_QUESTIONS #11). Tests should match the substring `.nas-marker`, not the
  full sentence.

## Open questions
- OPEN_QUESTIONS #11 (`last_error`/`last_reason` still carry German text, unlike other API
  outputs).
