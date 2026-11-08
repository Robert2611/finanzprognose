# Backlog

Open work items for this project. Each item has a stable ID; update the status instead of deleting entries.

Status values: `open`, `in progress`, `done`.

## B-001 Add test dependencies to the project

- **Status:** done
- **Problem:** The tests need `pytest` and `httpx` (used by FastAPI's `TestClient`), but neither is listed in `requirements.txt`. A fresh environment cannot run the tests without guessing what to install.
- **Proposal:** Add a `requirements-dev.txt` that includes `-r requirements.txt` plus pinned `pytest` and `httpx`. Keep `requirements.txt` production-only so the Docker image stays lean.
- **Done when:** `pip install -r requirements-dev.txt && python -m pytest` works in a fresh venv, and the commands in `CLAUDE.md` reference the new file.

## B-002 Introduce schema migrations

- **Status:** done (runner implemented; the `db.py` split is split out to B-009)
- **Problem:** `db.init()` only ran `CREATE TABLE IF NOT EXISTS` and always set `PRAGMA user_version=1`. Changing an existing table (e.g. adding a column) had no upgrade path for production databases that already exist.
- **Proposal:** Add an ordered list of numbered migration steps in `db.py`. On startup, read `user_version` and apply every step with a higher number, each in its own transaction, bumping `user_version` as it goes. Keep the existing data-safety rules: migrations must never delete data, and the audit log triggers stay in place.
- **Resolution:** `db.init()` now keeps `SCHEMA` as an always-applied idempotent baseline (version 1) and runs an ordered `MIGRATIONS` list of `(target_version, fn)` on top; each migration runs in its own transaction and must be idempotent (guard `ALTER`s with `_has_column`, since a fresh database gets the change from `SCHEMA` while an existing one gets it from the migration). `MIGRATIONS` is currently empty — there is no pending schema change — with a commented example showing where the first real one slots in. `test_migrations_upgrade_preserves_data` builds a version-1 DB with a row, applies a migration, and asserts the version advanced and the row survived (on its own temp DB, independent of the shared suite DB).
- **Note:** The `db.py` split proposed originally is moved to **B-009** so the runner could land as a small, contained change.
- **Done when:** ~~A test creates a version-1 database, starts the app, and verifies it is upgraded to the latest version with all existing data intact.~~ Done.

## B-003 Make local development work out of the box

- **Status:** done
- **Problem:** `DB_PATH` and `BACKUP_DIR` default to `/data/finanzen.sqlite` and `/backup` (the container paths), so running `uvicorn` locally fails or writes to system paths unless both are overridden.
- **Proposal:** Add a short "Local development" section to the README (or a `.env.dev` file) with the override values, e.g. `DB_PATH=./data/finanzen.sqlite BACKUP_DIR=./data/backup APP_PASSWORD=`. Leave the production defaults unchanged.
- **Done when:** A documented one-line command starts the app locally without touching `/data` or `/backup`.

## B-004 Make tests independent of each other

- **Status:** open
- **Problem:** All tests in `tests/test_app.py` share one module-scoped temp database. Later tests see data created by earlier ones (e.g. `test_backup` expects exactly 2 backup files), so tests can break when run alone, reordered, or extended.
- **Proposal:** Give each test its own temp database and backup directory through a fixture. Because `db.DB_PATH` and `backup.BACKUP_DIR` are read at import time, the fixture has to patch the module attributes (e.g. with `monkeypatch.setattr`) rather than environment variables.
- **Done when:** Every test passes when run on its own and when the suite runs in random order (e.g. with `pytest-randomly`).

## B-005 Move all user-facing text to the frontend (localization)

- **Status:** open
- **Problem:** The backend still produces German text that the frontend displays verbatim: API error messages (`detail`, including Pydantic validator messages in `main.py` and `NotFound`/`Conflict` in `db.py`), forecast `warnings`, `explanation` lines and item labels in `forecast.py` ("Startstand (Ist-Stand)", "Grundbetrag …"), backup errors and run reasons ("manuell", "zeitplan") in `backup.py`, and the DB trigger messages. Two German strings are also stored in the database: the checkpoint note "Startstand bei Anlage" and the audit comment "Rückgängig gemacht: Protokolleintrag #n". The account `kind` values (`giro`, `tagesgeld`, `depot`, `kreditkarte`, `bar`, `sonstiges`) are German identifiers stored in existing databases.
- **Proposal:** Make the backend language-neutral: return stable error/message codes plus parameters (e.g. `{"code": "conflict"}`, `{"code": "base_amount", "amount": -60000}`) and let `app.js` map them to German text. Store neutral values for the two stored strings and keep rendering the old German values for existing rows. Treat renaming the `kind` values as a data migration (depends on B-002), or keep them as opaque keys and only localize their labels.
- **Done when:** No German text remains in `app/*.py` except in tests that assert on legacy stored data, the UI still shows the same German text, and an upgraded production database still renders correctly.

## B-006 Make Claude Code available in the dev container

- **Status:** done (implemented; the rebuild check below still has to be done by hand in VS Code)
- **Problem:** The dev container (`.devcontainer/`) does not include Claude Code, so it cannot be used from inside the container where the app and tests run.
- **Proposal:** Install the Claude Code CLI in the dev container (e.g. via the official Dev Container Feature or an npm install in the Dockerfile/`postCreateCommand`). Persist its config (`~/.claude`) across rebuilds with a named volume or bind mount, and document how to authenticate.
- **Done when:** After rebuilding the dev container, `claude` starts in the integrated terminal, stays logged in across rebuilds, and the setup is described in the README or `CLAUDE.md`.

## B-007 Split app/main.py into smaller modules

- **Status:** open
- **Problem:** `main.py` combines several unrelated responsibilities in one 260+ line file: auth middleware, exception handlers, all Pydantic request models, and every route (generic CRUD, accounts, audit/revert, forecast, backup, export). This violates the file-size preference in `CLAUDE.md`.
- **Proposal:** Split by responsibility, e.g. `app/schemas.py` (the Pydantic models and `MODELS` mapping), `app/auth.py` (the auth middleware), and keep `main.py` for route wiring only (or split routes further by area if that still ends up large). Keep the route paths and behavior unchanged.
- **Done when:** `main.py` only wires routes/middleware together, the split-out modules each have a single clear responsibility, and the existing test suite passes unchanged.

## B-008 Split app/static/app.js into smaller modules

- **Status:** open
- **Problem:** `app.js` is a single 500+ line file covering everything: generic helpers, state, the generic form-dialog component, routing, and every view (forecast, entries, accounts, audit/history, backup). It already has clear comment-delimited sections, but they all live in one file. This violates the file-size preference in `CLAUDE.md`.
- **Proposal:** Split along the existing section boundaries into separate files (e.g. `core.js` for helpers/state/formDialog/routing, and one file per view: `forecast.js`, `entries.js`, `accounts.js`, `audit.js`, `backup.js`). Since the project has no build step, load them as native ES modules (`<script type="module">` with explicit imports/exports) rather than introducing a bundler.
- **Done when:** `app.js` no longer exists as one monolith, each new file has a single view/responsibility, and the app works unchanged in the browser without any build step.

## B-009 Split db.py into focused modules

- **Status:** open
- **Problem:** `db.py` combines several responsibilities in one file: the schema and migration runner (B-002), the generic CRUD helpers, the audit log, and the transaction/connection plumbing. This violates the file-size preference in `CLAUDE.md`. It was carved out of B-002 so the migration runner could land as a small, contained change.
- **Proposal:** Split `db.py` into smaller, well-scoped modules (e.g. schema + migrations, generic CRUD, audit log, connection/transaction helpers), keeping the public functions importable as they are today so callers (`main.py`, `backup.py`, tests) don't change. Preserve every data-safety invariant: DELETE-blocking triggers, append-only `audit_log`, optimistic locking, and the single-writer lock.
- **Done when:** `db.py`'s responsibilities live in focused modules, the import surface used elsewhere is unchanged, and the existing test suite passes unchanged.
