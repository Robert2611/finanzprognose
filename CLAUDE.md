# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

- Never push to the remote on your own.
- Never revert any commits.
- Open work items are tracked in `BACKLOG.md`. When you finish one, update its status there.

## Project

Self-hosted personal finance forecast app (replaces an Excel sheet). FastAPI + SQLite backend, vanilla-JS single-page frontend, no build step. Runs as one Docker container on a Proxmox LXC, with daily backups to a NAS. Code, docstrings, comments, identifiers, log messages and tests are in **English**. The UI and the README are in **German** (only the frontend is meant to be localized). Known exception: some backend-generated runtime strings are still German because the frontend displays them verbatim (API error messages, forecast `warnings`/`explanation`/item labels, backup errors, the "Startstand bei Anlage" note and the "Rückgängig gemacht" audit comment); see B-005 in `BACKLOG.md`. Until that is done, keep new strings of that kind German so the UI stays consistent.

## Commands

```bash
# Dependencies (pytest + httpx are needed for tests but are NOT in requirements.txt)
pip install -r requirements.txt pytest httpx

# Run all tests
python -m pytest -q

# Run a single test
python -m pytest -q tests/test_app.py::test_full_flow

# Run locally (defaults point to /data and /backup, so override them; an empty APP_PASSWORD disables auth)
DB_PATH=./data/finanzen.sqlite BACKUP_DIR=./data/backup APP_PASSWORD= uvicorn app.main:app --reload

# Production (needs APP_PASSWORD and BACKUP_HOST_DIR in .env, see .env.example)
docker compose up -d --build
```

API docs are served at `/api/docs`. There is no linter or formatter configured.

## Architecture

- `app/db.py` is the data layer, and every write goes through it. `TABLES` is the single whitelist of tables and of the columns that are writable through the API. It drives the generic CRUD, the DELETE-blocking triggers and the export. To add a column, update `SCHEMA`, `TABLES` and the Pydantic model in `main.py`. There is no migration system: the schema uses `CREATE TABLE IF NOT EXISTS`, and `user_version` is hard-coded to 1, so changes to existing tables need hand-written `ALTER TABLE` handling in `db.init()`.
- `app/main.py` exposes generic REST routes (`/api/{table}`, `/api/{table}/{id}`, `/archive`, `/restore`), and `MODELS` maps table names to Pydantic validators. `POST /api/accounts` is special: it also creates the account's first checkpoint (the starting balance) in the same transaction. Static files are mounted at `/` last, so API routes must be registered before that mount.
- `app/forecast.py` is a pure function, `compute(state, start, months)`. It takes the raw table rows and returns the per-month, per-account item lists that the frontend renders directly. Every amount carries an `explanation` list, a human-readable derivation (base amount, then each adjustment applied). Keep these explanations accurate whenever the calculation logic changes, because showing them is a core feature.
- `app/backup.py` runs a daemon scheduler thread, started from the FastAPI lifespan, that checks every 60s. Backup state is kept in `backup_status.json` next to the database.
- `app/static/app.js` is the whole UI: hash-based views, with the full state loaded from `/api/state`. It sends `expected_updated_at` on every PUT.

### Data-safety invariants (do not break)

- **Nothing is ever deleted.** SQLite triggers abort any `DELETE` on the data tables. Records are archived instead (`archived=1`), and archived rows are ignored by the forecast.
- **`audit_log` is append-only** (triggers block UPDATE/DELETE). Every create/update/archive/restore/revert writes an audit row with before/after JSON **in the same transaction**, via `db._write`/`db.create`. Never write to the data tables outside these helpers.
- **"Undo" (`db.revert`) is a new forward change** that restores the `before` snapshot. It never rewrites history.
- **Optimistic locking:** if `expected_updated_at` does not match, `db.Conflict` is raised and turned into HTTP 409.
- **Money is integer cents**, in the API and in the DB. Percentage adjustments use `Decimal` with `ROUND_HALF_UP`.
- **`data_version` = `MAX(audit_log.id)`.** Backups use it to skip runs when nothing has changed, and it appears in backup filenames.
- **Single writer:** writes are serialized with a process-level `threading.Lock` plus `BEGIN IMMEDIATE`, and the backup scheduler runs in-process. This is why the Dockerfile runs uvicorn with `--workers 1`. Do not add workers.
- **Backups are never deleted or overwritten.** They are written to temp files, fsynced, then renamed, and refused if `.nas-marker` is missing from `BACKUP_DIR` (this guards against an unmounted NAS).

### Forecast semantics

- Checkpoints (`checkpoints`, actual balances "at the end of that day") are the anchors. An account's first checkpoint is its start. Entries dated on or before it are treated as already included. Each later checkpoint resets the running balance and reports `expected`/`deviation`.
- On the same day, entries are applied before checkpoints.
- Recurring dates clamp to the last day of the month (an entry starting on the 31st falls on Feb 28).
- A transfer (`to_account_id` set) is stored as a positive amount and produces a −amount item on the source account and a +amount item on the target account. Transfers are not counted in the monthly `income`/`expense` totals.
- An adjustment with `mode='set'` replaces the amount. One with `mode='percent'` and `repeat_yearly` is applied `full_years(effective_date, date) + 1` times. Adjustments are applied in `(effective_date, id)` order.

### Tests

There is a single file, `tests/test_app.py`. It sets `DB_PATH`/`BACKUP_DIR` env vars to a temp dir **before** importing `app`, because those paths are read at import time. All tests share one module-scoped DB, so later tests see data created by earlier ones.
