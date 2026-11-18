# Backup subsystem
ID prefix: BKP
Layer: backup

## Purpose
Keeps an off-box copy of the data on the NAS so a lost container or disk doesn't lose the
finances. It runs daily (and on demand), only when something changed, never overwrites or
deletes older backups, verifies each snapshot's integrity, and guards against silently
writing to an unmounted NAS.

## Interface
Import: `from app import backup`. Every function takes the app's `Settings` `s`
(`app/settings.py`): `s.backup_dir` (env `BACKUP_DIR`, default `/backup`), `s.backup_time`
(env `BACKUP_TIME`, default `03:00`), `s.backup_require_marker` (env `BACKUP_REQUIRE_MARKER`,
default `1`; `MARKER = ".nas-marker"`), `s.db_path`. Nothing is captured at import.

- `backup.run_backup(s, force=False, reason="zeitplan") -> dict` — attempt a backup; returns
  the resulting status dict.
- `backup.status(s) -> dict` — current status (persisted fields + live `backup_dir`,
  `backup_time`, `current_version`, `pending_changes`).
- `backup.list_backups(s, limit=100) -> list[dict]` — `{name, size, mtime}` for
  `finanzen_*.sqlite` files, newest-first.
- `backup.start_scheduler(s) -> threading.Event` — start the daemon scheduler thread;
  setting the returned event stops it. The app lifespan starts it only when
  `s.backup_scheduler` is true (env `BACKUP_SCHEDULER`, default `1`) and stops it on shutdown.

**Artifacts in `BACKUP_DIR`** for a run at data-version `v`, local timestamp
`YYYY-MM-DD_HHMMSS`:
- `finanzen_<stamp>_v<v>.sqlite` — a consistent SQLite copy.
- `finanzen_<stamp>_v<v>.json` — the same data as readable JSON (the export).
- `backups.log` — append-only log line per successful backup with a SHA-256 of the
  `.sqlite`.

**Status file:** `backup_status.json`, stored **next to the DB file** (dir of `DB_PATH`).

## Dependencies & side effects
Reads the live DB (online backup API) and `data_version`. Writes artifacts to `BACKUP_DIR`,
appends `backups.log`, writes `backup_status.json`. Uses local `datetime.now()` for stamps
and scheduling. Serializes runs with an internal lock.

## Behavior clauses

### Triggers & change detection
- `BKP-001` [README] A scheduled backup runs once per day at `BACKUP_TIME` (local time),
  driven by a daemon thread that checks roughly every 60 seconds.
- `BKP-002` [README] A backup can be triggered manually via `POST /api/backup/run`
  (`reason="manuell"`). [TEST: `test_backup`]
- `BKP-003` [README][TEST] A backup only produces a new artifact if `data_version` differs
  from the last successful backup's version; otherwise the run result is `"unchanged"` and
  no file is written. [TEST: `test_backup`]
- `BKP-004` [OBSERVED] The `"unchanged"` short-circuit also requires the last backup file to
  still exist in `BACKUP_DIR`; if it was removed, a new backup is written even though
  `data_version` is unchanged. [INFERRED intent: self-heal a missing artifact]
- `BKP-005` [INFERRED] `force=True` bypasses the change check and always writes a new
  artifact (the manual API path uses `force=False`).

### NAS-marker guard & target checks
- `BKP-006` [README][TEST] With `BACKUP_REQUIRE_MARKER=1`, if `BACKUP_DIR/.nas-marker` is
  missing, the run fails: `last_result="error"`, `last_error` mentions `.nas-marker`, and
  **no** artifact is written. [TEST: `test_backup`]
- `BKP-007` [INFERRED] With `BACKUP_REQUIRE_MARKER=0`, no marker file is required (local dev
  mode).
- `BKP-008` [INFERRED] If `BACKUP_DIR` does not exist, the run fails with an error naming
  the missing target and writes nothing.

### Artifact contract
- `BKP-009` [README] On success, exactly two artifacts are written for the run: the
  `.sqlite` copy and the equally-named `.json` export.
- `BKP-010` [README] The `.sqlite` artifact opens as a valid SQLite database and passes
  `PRAGMA integrity_check` (the run verifies this before finalizing; a failing check aborts
  the run with an error and leaves no final artifact). [TEST: `test_backup` opens the file
  and queries it]
- `BKP-011` [README] The `.sqlite` artifact is a **consistent** snapshot of the source
  database taken via SQLite's online backup API, so it is valid even if writes happen during
  the backup.
- `BKP-012` [TEST] The `.sqlite` artifact contains the same data as the source at snapshot
  time (e.g. the accounts present at backup time are queryable in the copy). [TEST:
  `test_backup` asserts `COUNT(*) FROM accounts >= 1`]
- `BKP-013` [README] Backup filenames encode the local timestamp and the data-version:
  `finanzen_YYYY-MM-DD_HHMMSS_v<version>.sqlite` (and `.json`).
- `BKP-014` [README] `backups.log` gains one appended line per successful backup containing
  the stamp, `v<version>`, the `.sqlite` filename, its `sha256=` checksum, and the reason.

### Never destroy
- `BKP-015` [README][TEST] Older backups are never deleted or overwritten; each successful
  backup is a new file, so the directory accumulates. [TEST: `test_backup` asserts 2 files
  after two distinct-version backups]
- `BKP-016` [README] Artifacts are written to temp names (prefixed `.`, suffix `.tmp`),
  fsynced, then atomically renamed into place — an interrupted run never leaves a
  half-written final artifact.
- `BKP-017` [INFERRED] On any failure mid-run, the temporary files are removed (best effort)
  and no final `.sqlite`/`.json` appears.
- `BKP-024` [README] SQLite never reads or writes a file inside `BACKUP_DIR` (file locking on
  SMB/NFS is unreliable and can hang). The snapshot, the integrity check and the JSON export
  are built in a staging area in the directory of `DB_PATH` (dot-prefixed `.tmp` names) and
  only the finished files are copied to `BACKUP_DIR` (then fsynced and renamed per BKP-016).
- `BKP-025` [INFERRED] The staging files are removed after every run, successful or not, so
  the DB directory holds no `.tmp` leftovers.

### Status & retry
- `BKP-018` [INFERRED] After a run, `status()` reflects `last_attempt`, `last_reason`,
  `last_result` (`ok`/`unchanged`/`error`), and on success `last_success`, `last_version`,
  `last_file`; on error `last_error` is set and `last_success`/`last_version` are unchanged.
- `BKP-019` [README] After a failed backup, the scheduler retries about once an hour
  (in addition to the daily run). [OBSERVED: retry keys off `last_result=='error'` and
  `now - last_attempt > 1h`; see OPEN_QUESTIONS #12.]
- `BKP-020` [INFERRED] `pending_changes` in `status()` is `true` when `current_version`
  differs from the last backed-up version.

### Effect on the running app
- `BKP-021` [README][INFERRED] Backups do not require stopping the app: the online backup
  API copies the live DB while it keeps serving requests. Runs are serialized by an internal
  lock so two backups don't overlap.
- `BKP-022` [INFERRED] A single process performs both serving and backups (`--workers 1`);
  the backup holds its own lock but does not take the data-layer write lock, so reads
  continue during a backup.

### Retention
- `BKP-023` [README] There is **no** retention/rotation/pruning: nothing is ever removed
  automatically. External NAS snapshots are recommended but out of this subsystem's scope.

## Examples
- Marker missing → `run_backup()` → `{last_result:'error', last_error:'…​.nas-marker…'}`,
  dir unchanged. [TEST]
- Marker present, v5 pending → `run_backup()` → writes `finanzen_<stamp>_v5.sqlite` + `.json`,
  appends `backups.log`, `{last_result:'ok', last_version:5}`. [TEST]
- No change since v5 → `run_backup()` → `{last_result:'unchanged'}`, no new file. [TEST]

## Out of scope / not specified
- Scheduler wall-clock behavior in tests (uncontrollable; see ENVIRONMENT gaps #1–#3).
  Verify backup mechanics via the manual run, not the schedule.
- Exact German text of `last_error`/`reason` (see OPEN_QUESTIONS #11).
- Disk-full / slow-NAS behavior details (no seam to reproduce reliably; ENVIRONMENT gap #4).

## Open questions
- OPEN_QUESTIONS #11 (German text in backup status fields).
- OPEN_QUESTIONS #12 (hourly-retry trigger conditions and whether it can double-run).
