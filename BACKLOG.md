# Backlog

Open work items for this project. Each item has a stable ID; update the status instead of deleting entries.

Status values: `open`, `in progress`, `done`.

## B-001 Add test dependencies to the project

- **Status:** open
- **Problem:** The tests need `pytest` and `httpx` (used by FastAPI's `TestClient`), but neither is listed in `requirements.txt`. A fresh environment cannot run the tests without guessing what to install.
- **Proposal:** Add a `requirements-dev.txt` that includes `-r requirements.txt` plus pinned `pytest` and `httpx`. Keep `requirements.txt` production-only so the Docker image stays lean.
- **Done when:** `pip install -r requirements-dev.txt && python -m pytest` works in a fresh venv, and the commands in `CLAUDE.md` reference the new file.

## B-002 Introduce schema migrations

- **Status:** open
- **Problem:** `db.init()` only runs `CREATE TABLE IF NOT EXISTS` and always sets `PRAGMA user_version=1`. Changing an existing table (e.g. adding a column) has no upgrade path for production databases that already exist.
- **Proposal:** Add an ordered list of numbered migration steps in `db.py`. On startup, read `user_version`, apply every step with a higher number inside one transaction, then set `user_version` to the latest number. Keep the existing data-safety rules: migrations must never delete data, and the audit log triggers stay in place.
- **Done when:** A test creates a version-1 database, starts the app, and verifies it is upgraded to the latest version with all existing data intact.

## B-003 Make local development work out of the box

- **Status:** open
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
