# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules

- `main` is protected: never commit to it or push to it directly. Do all work on a feature branch, push that branch, and open a pull request into `main`.
- Never revert any commits.
- Open work items are tracked in `BACKLOG.md`. When you finish one, add its resolution and move it to the end of `docs/backlog-done.md` (IDs are stable and never reused; take new ones from the "Next free ID" line). References like "B-020" point to an item in one of the two files.
- Prefer several smaller files with a well-defined scope over one big file that combines everything. When a file grows unrelated responsibilities, split it rather than adding to the pile.
- Run `python -m pytest -q` before committing, and don't commit if it fails.
- Every PR is reviewed by a fresh Claude session in CI (`.github/workflows/claude-review.yml`, B-025, see `docs/claude-review.md`) and auto-merged into `main` when the review passes and CI is green. Keep PRs small and self-explanatory; changes to `.github/` always fail that review and need a human merge.

## Project

Self-hosted personal finance forecast app (replaces an Excel sheet). FastAPI + SQLite backend, vanilla-JS single-page frontend, no build step. Runs as one Docker container in a Debian VM on Proxmox, with daily backups to a NAS. Releases are delivered as a Docker image on ghcr.io and installed/updated with `deploy/install.sh` / `deploy/update.sh`. Code, docstrings, comments, identifiers, log messages and tests are in **English**. The UI and the README are in **German** (only the frontend is meant to be localized). The API is language-neutral (B-005): errors, forecast explanations and warnings are `{code, params}`, and the frontend turns them into German. This includes the backup status (B-020): `last_error` is `{code, params}` and `last_reason` is `scheduled`/`manual`/`retry`; only a status file written before B-020 can still hold German strings, which the frontend shows as-is. Don't add German strings to the backend; add a code and map it in the frontend instead.

## Commands

```bash
# Dependencies (requirements-dev.txt = requirements.txt + pytest + httpx + pytest-playwright)
pip install -r requirements-dev.txt
python -m playwright install chromium   # one-time, only needed for the browser tests
# Or use a Chromium that is already installed (e.g. the one preinstalled in a cloud container);
# point it at the *headless shell* binary, since the full Chrome handles HTTP auth differently:
# export PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chrome-headless-shell

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

- `app/db/` is the data layer, and every write goes through it. It is a package (B-009) that re-exports everything as `db.<name>`: `connection.py` (`connect`/`tx`/`read`, the single-writer lock), `schema.py` (`TABLES`, `SCHEMA`, `MIGRATIONS`, `init`), `crud.py` (generic create/update/archive/restore, writing `audit_log`), `audit.py` (audit list, `revert`, export, `data_version`) and `errors.py` (`NotFound`/`Conflict`). `TABLES` is the single whitelist of tables and of the columns writable through the API; it drives the generic CRUD, the DELETE-blocking triggers and the export. Every function takes the DB path explicitly.
- **Schema changes:** `SCHEMA` is the always-applied, idempotent picture of the current schema (version 1 baseline), and `MIGRATIONS` is an ordered list of `(target_version, fn)` run on top by `db.init()`, each in its own transaction, bumping `user_version` (B-002). To add a column: add it to `SCHEMA` (for fresh databases) **and** add a migration that `ALTER`s existing ones (guard it with `_has_column`, since a fresh DB already has the column), then update `TABLES`, the input model in `app/schemas.py` and, if it should be visible, the output model in `app/contracts.py`. Migrations must never delete data. Migration 2 (`entries.estimated`, B-015) is the first real one and the example to follow; its tests are in `tests/contract/backend/test_db_migrations.py`, and the runner tests in `test_db_schema.py` number their patched migrations after the real ones, so they don't need touching when a migration is added.
- `app/settings.py` holds all runtime config in a frozen `Settings` dataclass. `Settings.from_env()` reads the env vars (production); nothing else reads them, and no module captures config at import. To add a setting, add a field and its env var in `from_env()`.
- `app/main.py` only wires the app (B-007): `create_app(settings)` builds an independent app (own DB, backup dir, auth, scheduler), stores the settings on `app.state.settings`, adds the Basic-auth middleware (`app/auth.py`), the exception handlers (`app/errors.py`), the router and the static files; `app = create_app()` is what uvicorn serves. Static files are mounted at `/` last, so API routes must be registered before that mount.
- `app/routes.py` exposes the REST routes (generic `/api/{table}`, `/api/{table}/{id}`, `/archive`, `/restore`, plus state, forecast, audit/revert, backup and export) on an `APIRouter`; each route gets the settings through `Depends(get_settings)` and passes `s.db_path` to `db.tx()`/`db.read()`. Input is validated by the Pydantic models in `app/schemas.py` (`MODELS` maps table names to them). `POST /api/accounts` is special: it also creates the account's first checkpoint (the starting balance) in the same transaction.
- **API contract (B-005):** read endpoints (`/api/state`, `/api/audit`, `/api/backup/status`) return the response models in `app/contracts.py`, so new table columns don't leak onto the wire until added there; `archived` is a boolean. Errors are `{"code", "params"}` envelopes (`app/errors.py`, `db.NotFound`/`db.Conflict`), never German text; invalid query/path parameters get the same `validation_error` envelope as invalid bodies.
- `app/forecast.py` is a pure function, `compute(state, start, months)`. It takes the raw table rows and returns the per-month, per-account item lists that the frontend renders directly. Every amount carries an `explanation` list of `{code, params}` steps (base amount, then each adjustment applied), and `warnings` are codes too; the frontend renders them as German text. Keep these explanations accurate whenever the calculation logic changes, because showing them is a core feature.
- The backup is three modules, all taking the app's `Settings`: `app/backup.py` (`run_backup`, `status`, `list_backups`; state kept in `backup_status.json` next to the database), `app/backup_schedule.py` (B-021: the pure decision `due_run(now, status, backup_time)`, `tick(s, now)` and the daemon thread, started from the FastAPI lifespan unless `backup_scheduler` is off, calling `tick` every 60s and stopping on shutdown) and `app/backup_verify.py` (B-022: the read-only „Backup prüfen“ check behind `GET /api/backup/verify`, which copies the file next to the database first, because SQLite must never open files on the NAS).
- **Automatic update (B-026):** `deploy/auto-update.sh` runs on the host (systemd `finanzprognose-update.timer` every 15 min, and `finanzprognose-update.path` when `updater/request.json` appears), checks `:latest` on ghcr.io and installs it with `update.sh --auto-rollback` (unless `AUTO_UPDATE=notify`). App and host only share the folder `updater/` (`/updater`, `Settings.update_dir`): the host writes `status.json` and `last-update.log`, the app reads them and only writes `request.json` (`app/updater_link.py`, routes in `app/update_routes.py`, view `update.js`). The app never runs Docker or host commands; keep it that way. The file formats are in `contracts/deploy/auto-update.md`; the host scripts are tested with a fake `docker` in `tests/contract/deploy/`.
- `deploy/` holds the production delivery: `docker-compose.yml` (the only compose file; uses the released image, version pinned by `APP_VERSION` in `.env`), `install.sh` (sets up a fresh Debian VM: Docker, ghcr.io login, NAS mount, `.env`) and `update.sh` (copies the DB to `data/pre-update/`, switches the version, waits for the health check). The Dockerfile copies `deploy/` into the image at `/deploy` and sets the label `finanzprognose.version`; both scripts copy the deploy files out of the image, so they update themselves and only need a `read:packages` token. `install.sh` is standalone (it is also a release asset), so a few helpers are duplicated in both scripts; keep them in sync.
- **Frontend** (`app/static/`, B-008): native ES modules, no build step, rendered with the vendored `vendor/lit-html.js` (tagged `html`/`svg` templates with inline `@event` bindings; use `svg` for nested templates that produce bare SVG elements). `app.js` is only the bootstrap. `core.js` holds the helpers, the code → German maps (`ERROR_CODES`, `EXPLANATION_CODES`, `WARNING_CODES`, `KINDS`, `FIELD`, …), the state `S`, `formDialog`/`archiveDialog` and the hash router. One module per view: `forecast.js`, `entries.js`, `accounts.js`, `audit.js`, `backup.js`, `update.js` (the „Version“ page); `grouping.js` holds the "Gruppieren nach" logic shared by the Buchungen list and the forecast (B-012). The full state is loaded from `/api/state`, and every PUT sends `expected_updated_at`. All user-visible text lives here, in German.

### Data-safety invariants (do not break)

- **Nothing is ever deleted.** SQLite triggers abort any `DELETE` on the data tables. Records are archived instead (`archived=1`), and archived rows are ignored by the forecast.
- **`audit_log` is append-only** (triggers block UPDATE/DELETE). Every create/update/archive/restore/revert writes an audit row with before/after JSON **in the same transaction**, via `db._write`/`db.create`. Never write to the data tables outside these helpers.
- **"Undo" (`db.revert`) is a new forward change** that restores the `before` snapshot. It never rewrites history.
- **Optimistic locking:** if `expected_updated_at` does not match, `db.Conflict` is raised and turned into HTTP 409. This applies to PUT and to archive/restore (B-017); the frontend always sends it.
- **Money is integer cents**, in the API and in the DB. Percentage adjustments use `Decimal` with `ROUND_HALF_UP`.
- **`data_version` = `MAX(audit_log.id)`.** Backups use it to skip runs when nothing has changed, and it appears in backup filenames.
- **Single writer:** writes are serialized with a process-level `threading.Lock` plus `BEGIN IMMEDIATE`, and the backup scheduler runs in-process. This is why the Dockerfile runs uvicorn with `--workers 1`. Do not add workers.
- **Backups are never deleted or overwritten.** They are written to temp files, fsynced, then renamed, and refused if `.nas-marker` is missing from `BACKUP_DIR` (this guards against an unmounted NAS).

### Forecast semantics

- Checkpoints (`checkpoints`, actual balances "at the end of that day") are the anchors. An account's first checkpoint is its start. Entries dated on or before it are treated as already included. Each later checkpoint resets the running balance and reports `expected`/`deviation`.
- On the same day, entries are applied before checkpoints.
- `entries.estimated` (B-015) only marks an amount as an estimate; items carry it as `estimated`, and it never changes a number. Checkpoints absorb the difference to reality.
- Recurring dates clamp to the last day of the month (an entry starting on the 31st falls on Feb 28).
- A transfer (`to_account_id` set) is stored as a positive amount and produces a −amount item on the source account and a +amount item on the target account. Transfers are not counted in the monthly `income`/`expense` totals. If the target account is archived, the source side is kept (the money still leaves) and a `transfer_target_archived` warning is emitted; if the source is archived, the whole entry is ignored (B-018).
- An adjustment with `mode='set'` replaces the amount. One with `mode='percent'` and `repeat_yearly` is applied `full_years(effective_date, date) + 1` times. Adjustments are applied in `(effective_date, id)` order.

### Tests

All tests live in `tests/contract/`, a black-box suite written against the specs in `contracts/` (`tests/contract/TEST_PLAN.md` describes it). Every test carries `@pytest.mark.contract("<ID>")` with a clause ID from `contracts/TRACEABILITY.md`; collection fails for a missing or unknown ID (only `tests/contract/harness/` is exempt). When you change behavior, update the clause in `contracts/` and its row in `TRACEABILITY.md` along with the test. Each test builds its own app via `create_app(Settings(...))` with a temp DB and backup dir and wraps it in `TestClient` (fixtures in `tests/contract/conftest.py`; per-test overrides with `@pytest.mark.app_settings(...)`); no env vars are involved. Tests that use a browser fixture are marked `browser` automatically and skipped by default. The run writes `tests/contract/results.json` (gitignored); `python -m tests.contract.helpers.report` turns it into `COVERAGE.md` and `TEST_REPORT.md`.
