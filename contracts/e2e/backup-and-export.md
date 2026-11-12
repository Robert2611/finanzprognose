# E2E — backup & export
ID prefix: E2E-BKP
Layer: e2e

## Purpose
The user checks backup status, runs a manual backup, and downloads a JSON export. Covers the
NAS-marker guard (missing marker → visible failure → success after fixing it → "unchanged"
when nothing changed).

## Preconditions
`BACKUP_DIR` points at a test directory. `BACKUP_REQUIRE_MARKER=1`. A database with at least
one account. For the "unchanged" step, no data change between runs (and the previous backup
file still present).

## Scenarios

- `E2E-BKP-001` [BROWSER-REQUIRED] **Given** the "Sicherung" view, **when** it loads, **then**
  it shows `Ziel` (the backup dir), the schedule text `"täglich um <time> Uhr, nur bei
  Änderungen"`, the data version, a `"Jetzt sichern"` button, and an
  `"Export als JSON herunterladen"` link. [FE-BACKUP-001/006]
- `E2E-BKP-002` [HTTP-checkable] **Given** `.nas-marker` missing, **when**
  `POST /api/backup/run`, **then** `last_result == "error"` and `last_error` contains
  `".nas-marker"`, and no backup file is written. [API-BKP-004/BKP-006/TEST test_backup]
- `E2E-BKP-003` [BROWSER-REQUIRED] **Given** the marker missing, **when** the user clicks
  `"Jetzt sichern"`, **then** an error toast `"Sicherung fehlgeschlagen: …"` appears, a red
  `.banner.err` is shown, and the header pill reads `"Sicherung fehlgeschlagen!"`. [FE-BACKUP-003/
  004/007]
- `E2E-BKP-004` [HTTP-checkable] **Given** the `.nas-marker` now present and pending changes,
  **when** `POST /api/backup/run`, **then** `last_result == "ok"` and a
  `finanzen_<stamp>_v<version>.sqlite` (plus `.json`) exists in `BACKUP_DIR`. [API-BKP-005/
  BKP-009/TEST test_backup]
- `E2E-BKP-005` [HTTP-checkable] **Given** the just-written backup, **when**
  `POST /api/backup/run` again with no data change, **then** `last_result == "unchanged"` and no
  new file is written. [API-BKP-006/TEST test_backup]
- `E2E-BKP-006` [HTTP-checkable] **Given** a data change after a backup, **when**
  `POST /api/backup/run`, **then** `last_result == "ok"`, a second backup file exists, and the
  first is still present (nothing deleted). [API-BKP-007/BKP-015/TEST test_backup]
- `E2E-BKP-007` [BROWSER-REQUIRED] **Given** a successful backup, **when** the user reopens the
  "Sicherung" view, **then** the backup appears in the `"Vorhandene Sicherungen (neueste 30)"`
  list and the pill reads `"Gesichert <time>"` (class `ok`). [FE-BACKUP-005/007]
- `E2E-BKP-008` [HTTP-checkable] **Given** the written backup `.sqlite`, **when** it is opened
  as SQLite, **then** `PRAGMA integrity_check` returns `ok` and it contains the source data
  (e.g. the accounts). [BKP-010/BKP-012/TEST test_backup]
- `E2E-BKP-009` [HTTP-checkable] **Given** the app, **when** `GET /api/export`, **then** it
  returns a JSON body with the four data arrays, `audit_log`, `exported_at`, and `data_version`,
  plus a `Content-Disposition` attachment filename `finanzen_export_<date>.json`. [API-EXPORT]
- `E2E-BKP-010` [HTTP-checkable] **Given** a backup `.sqlite` and the manual restore steps,
  **when** it is copied to a fresh `DB_PATH` and the app started, **then** `GET /api/state`
  matches the backed-up data and `data_version` equals the `_v<v>` in the filename. [RESTORE-003/
  005]

## Out of scope
- The daily scheduled run and hourly retry (uncontrollable timing; ENVIRONMENT gaps #1–#3).
- Disk-full / slow-NAS (no reliable seam; ENVIRONMENT gap #4).
