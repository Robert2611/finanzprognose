# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

- `main` is protected: never commit to it or push to it directly. Do all work on a feature branch, push that branch, and open a pull request into `main`.
- Never revert any commits.
- Open work items are tracked in `BACKLOG.md`. When you finish one, update its status there.
- Prefer several smaller files with a well-defined scope over one big file that combines everything. When a file grows unrelated responsibilities, split it rather than adding to the pile.
- Run `python -m pytest -q` before committing, and don't commit if it fails.

## Project

Self-hosted personal finance forecast app (replaces an Excel sheet). FastAPI + SQLite backend, vanilla-JS single-page frontend, no build step. Runs as one Docker container in a Debian VM on Proxmox, with daily backups to a NAS. Releases are delivered as a Docker image on ghcr.io and installed/updated with `deploy/install.sh` / `deploy/update.sh`. Code, docstrings, comments, identifiers, log messages and tests are in **English**. The UI and the README are in **German** (only the frontend is meant to be localized). Known exception: some backend-generated runtime strings are still German because the frontend displays them verbatim (API error messages, forecast `warnings`/`explanation`/item labels, backup errors, the "Startstand bei Anlage" note and the "Rückgängig gemacht" audit comment); see B-005 in `BACKLOG.md`. Until that is done, keep new strings of that kind German so the UI stays consistent.

## Commands

```bash
# Dependencies (requirements-dev.txt = requirements.txt + pytest + httpx + pytest-playwright)
pip install -r requirements-dev.txt
python -m playwright install chromium   # one-time, only needed for the browser tests

# Run all tests (browser tests are deselected by default via pytest.ini)
python -m pytest -q

# Including the Playwright browser tests (what the release pipeline runs)
python -m pytest -q -m ""

# Run a single test
python -m pytest -q tests/contract/api/test_accounts.py::test_create_account_returns_row

# All tests for one contract clause
python -m pytest -q --contract BKP-004

# Run locally (defaults point to /data and /backup, so override them; an empty APP_PASSWORD disables auth;
# BACKUP_DIR must exist). Easiest: use the dev container (.devcontainer/) and press F5 (.vscode/launch.json).
mkdir -p data/backup
DB_PATH=./data/finanzen.sqlite BACKUP_DIR=./data/backup BACKUP_REQUIRE_MARKER=0 APP_PASSWORD= uvicorn app.main:app --reload

# Build the image locally and run it with the production compose file (needs a .env, see .env.example;
# --project-directory keeps ./data and .env relative to the repo root instead of deploy/)
docker build -t ghcr.io/robert2611/finanzprognose:dev . && APP_VERSION=dev docker compose --project-directory . -f deploy/docker-compose.yml up -d

# Release: publish a GitHub release with a tag vX.Y.Z -> .github/workflows/release.yml runs the tests,
# pushes ghcr.io/robert2611/finanzprognose:vX.Y.Z (+ :latest unless prerelease) and attaches install.sh.
# On the server (Debian VM, /opt/finanzprognose):
sudo bash install.sh             # first setup or reconfiguration
sudo /opt/finanzprognose/update.sh [vX.Y.Z]
```

The dev container also installs the Claude Code CLI and VS Code extension (Dev Container Feature). Its login and config persist in the named volume `finanzprognose-claude-config` (mounted at `~/.claude`, with `CLAUDE_CONFIG_DIR` pointing there); see the README for authentication.

API docs are served at `/api/docs`. There is no linter or formatter configured.

## Architecture

- `app/db.py` is the data layer, and every write goes through it. `TABLES` is the single whitelist of tables and of the columns that are writable through the API. It drives the generic CRUD, the DELETE-blocking triggers and the export. To add a column, update `SCHEMA`, `TABLES` and the Pydantic model in `main.py`. There is no migration system: the schema uses `CREATE TABLE IF NOT EXISTS`, and `user_version` is hard-coded to 1, so changes to existing tables need hand-written `ALTER TABLE` handling in `db.init()`.
- `app/settings.py` holds all runtime config in a frozen `Settings` dataclass. `Settings.from_env()` reads the env vars (production); nothing else reads them, and no module captures config at import. To add a setting, add a field and its env var in `from_env()`.
- `app/main.py` is the app factory: `create_app(settings)` builds an independent app (own DB, backup dir, auth, scheduler) and stores the settings on `app.state.settings`; `app = create_app()` is what uvicorn serves. Static files are mounted at `/` last, so API routes must be registered before that mount.
- `app/routes.py` exposes generic REST routes (`/api/{table}`, `/api/{table}/{id}`, `/archive`, `/restore`) on an `APIRouter`; each route gets the settings through `Depends(get_settings)` and passes `s.db_path` to `db.tx()`/`db.read()`. `MODELS` (in `schemas.py`) maps table names to Pydantic validators. `POST /api/accounts` is special: it also creates the account's first checkpoint (the starting balance) in the same transaction.
- `app/forecast.py` is a pure function, `compute(state, start, months)`. It takes the raw table rows and returns the per-month, per-account item lists that the frontend renders directly. Every amount carries an `explanation` list, a human-readable derivation (base amount, then each adjustment applied). Keep these explanations accurate whenever the calculation logic changes, because showing them is a core feature.
- `app/backup.py` functions all take the app's `Settings`. The daemon scheduler thread is started from the FastAPI lifespan (unless `backup_scheduler` is off), checks every 60s and stops on shutdown. Backup state is kept in `backup_status.json` next to the database.
- `deploy/` holds the production delivery: `docker-compose.yml` (the only compose file; uses the released image, version pinned by `APP_VERSION` in `.env`), `install.sh` (sets up a fresh Debian VM: Docker, ghcr.io login, NAS mount, `.env`) and `update.sh` (copies the DB to `data/pre-update/`, switches the version, waits for the health check). The Dockerfile copies `deploy/` into the image at `/deploy` and sets the label `finanzprognose.version`; both scripts copy the deploy files out of the image, so they update themselves and only need a `read:packages` token. `install.sh` is standalone (it is also a release asset), so a few helpers are duplicated in both scripts; keep them in sync.
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

All tests live in `tests/contract/`, a black-box suite written against the specs in `contracts/` (`tests/contract/TEST_PLAN.md` describes it). Every test carries `@pytest.mark.contract("<ID>")` with a clause ID from `contracts/TRACEABILITY.md`; collection fails for a missing or unknown ID (only `tests/contract/harness/` is exempt). When you change behavior, update the clause in `contracts/` and its row in `TRACEABILITY.md` along with the test. Each test builds its own app via `create_app(Settings(...))` with a temp DB and backup dir and wraps it in `TestClient` (fixtures in `tests/contract/conftest.py`; per-test overrides with `@pytest.mark.app_settings(...)`); no env vars are involved. Tests that use a browser fixture are marked `browser` automatically and skipped by default. The run writes `tests/contract/results.json` (gitignored); `python -m tests.contract.helpers.report` turns it into `COVERAGE.md` and `TEST_REPORT.md`.
