# Manual restore procedure
ID prefix: RESTORE
Layer: backup

## Purpose
There is no automated restore. Recovery is a documented manual procedure: stop the app,
set aside the current database, copy a chosen backup `.sqlite` into place, and start again.
This contract rewrites that procedure as acceptance steps so a test can later verify a
backup artifact is actually restorable.

## Interface
Inputs: a backup artifact `finanzen_<stamp>_v<v>.sqlite` from `BACKUP_DIR` (the NAS), and a
stopped app instance whose database lives at `DB_PATH` (compose: `./data/finanzen.sqlite`).
Output: a running app serving the data as of that backup.

**Documented procedure (README "Wiederherstellen aus einer Sicherung"):**
1. Stop the app (`docker compose stop`).
2. Move the current DB aside — **including the `-wal` and `-shm` files**:
   `mkdir -p data/alt && mv data/finanzen.sqlite* data/alt/`.
3. Copy the chosen backup over the DB path:
   `cp <BACKUP_DIR>/finanzen_<stamp>_v<v>.sqlite data/finanzen.sqlite`.
4. Start the app (`docker compose start`).

## Dependencies & side effects
Replaces the live database file. The app re-opens it on start (and `db.init()` runs,
which is idempotent and must not destroy restored data).

## Behavior clauses

- `RESTORE-001` [README] A backup `.sqlite` opens directly as the app's database when
  copied to `DB_PATH`; no transformation or import step is required.
- `RESTORE-002` [README] The current DB must be moved aside **with its `-wal`/`-shm`
  siblings** before copying the backup in; leaving a stale `-wal`/`-shm` next to the
  restored file risks corruption/incorrect data.
- `RESTORE-003` [INFERRED] After restore and start, `GET /api/state` reflects exactly the
  data contained in the restored backup (same accounts/entries/adjustments/checkpoints).
- `RESTORE-004` [INFERRED] Running `db.init()` against a restored backup is safe: it applies
  only idempotent baseline DDL plus any pending migrations and preserves all restored rows.
- `RESTORE-005` [INFERRED] The restored database's `data_version` equals the `_v<v>` encoded
  in the backup filename (the max audit id at snapshot time).
- `RESTORE-006` [INFERRED] `PRAGMA integrity_check` on the restored database returns `ok`.
- `RESTORE-007` [README] For single mistaken changes, the in-app "Verlauf → Rückgängig"
  (revert) is the preferred recovery; a full file restore is for whole-database recovery.

**Acceptance test sketch (for the future suite):** create known data via the API → run a
backup (marker present) → capture the `.sqlite` filename and `data_version` → simulate loss
(point `DB_PATH` at a fresh empty dir) → copy the backup to `DB_PATH` → start a fresh app →
assert `GET /api/state` matches the known data and `data_version` matches the `_v<v>` suffix.

## Examples
- Backup `finanzen_2026-11-08_030000_v57.sqlite` restored to `data/finanzen.sqlite` →
  app serves the v57 snapshot; `/api/state.data_version == 57`.

## Out of scope / not specified
- Restoring the `.json` export (it is a readable copy, not the restore path).
- Any partial/row-level restore from a backup (not supported; use revert in-app).
- Merging a backup with newer live changes (not supported; restore is whole-file).

## Open questions
None (but see OPEN_QUESTIONS #13: no automated restore / no built-in post-restore
verification beyond this manual procedure).
