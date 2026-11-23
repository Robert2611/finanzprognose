# Contract Inventory

Phase 1 deliverable: the map of what will get a behavioral contract. **No contracts
are written yet** — this is the proposal to confirm before Phase 2.

Source of truth for intent, per the task:
`[README]` README/docs · `[TEST]` an existing test asserts it · `[INFERRED]` inferred
from names/structure · `[OBSERVED]` only evident from current code (suspicious ones go
to `OPEN_QUESTIONS.md`, not presented as intended).

---

## 1. Architecture overview

```
 Browser (static files, no build step)
   app/static/index.html
   app/static/app.js  ──imports──►  core.js  ──imports──►  per-view ES modules
        (bootstrap)                 (helpers, state,        forecast.js
                                     code→German maps,      entries.js
                                     formDialog, router)    accounts.js
                                                            audit.js
                                                            backup.js
   vendor/lit-html.js (vendored, rendering engine)
             │
             │  fetch() JSON over HTTP, HTTP Basic Auth
             ▼
 HTTP API  (FastAPI, app/main.py — routes + static mount at "/")
   middleware:  app/auth.py        (HTTP Basic Auth)
   handlers:    app/errors.py      ({code,params} error envelope)
   validation:  app/schemas.py     (Pydantic request models, MODELS)
   wire shapes: app/contracts.py   (Pydantic response models)
             │
             ▼
 Python services
   app/db/        data layer — EVERY write goes through here
      connection.py  connect/tx/read, single-writer lock
      schema.py      DDL, triggers, migration runner, TABLES whitelist
      crud.py        generic get/create/update/archive + audit write
      audit.py       audit read, revert (undo), export, data_version
      errors.py      ApiError/NotFound/Conflict
   app/forecast.py   pure compute(state, start, months) → per-month items
   app/backup.py     daemon scheduler thread + run_backup()
             │                               │
             ▼                               ▼
 SQLite  (DB_PATH, WAL,                NAS target  (BACKUP_DIR, local dir
          synchronous=FULL)            standing in for the mounted NAS share;
                                       guarded by a .nas-marker file)
```

- The frontend is a thin presentation layer: it owns **all** human-readable German
  text and all formatting. The backend emits language-neutral `{code, params}` for
  errors, forecast explanations/warnings, and stores integer cents.
- Single process only (`uvicorn --workers 1`): writes are serialized by a process-level
  lock + `BEGIN IMMEDIATE`, and the backup scheduler runs in-process.

---

## 2. Proposed units (grouped by layer)

### Backend — Python modules (`contracts/backend/`)
| File | Unit | One-line purpose |
|---|---|---|
| `db-connection.md` | `app.db` connection/tx (`connect`, `tx`, `read`, `now`) | Open connections, serialize writes in all-or-nothing transactions, supply UTC timestamps. |
| `db-schema.md` | `app.db` schema & migrations (`init`, `TABLES`, `SCHEMA`, `MIGRATIONS`, `_has_column`) | Create/upgrade the schema idempotently, install delete-blocking + audit triggers, run ordered migrations. |
| `db-crud.md` | `app.db` generic CRUD (`get`, `all_rows`, `create`, `update`, `set_archived`) | Read/write the whitelisted tables, writing an audit row in the same transaction; enforce optimistic locking. |
| `db-audit.md` | `app.db` audit & derived helpers (`audit_list`, `revert`, `data_version`, `export_all`) | Read the append-only log, undo a logged change as a new forward change, expose the change counter and full export. |
| `db-errors.md` | `app.db` exceptions (`ApiError`, `NotFound`, `Conflict`) | Carry a machine-readable `{code, params}` payload from the data layer to the API. |
| `forecast.md` | `app.forecast` (`compute`, `amount_at`, `occurrences`, `add_months`, `full_years`) | Pure forecast engine: turn raw table rows into per-month, per-account item lists with explanations. |
| `schemas.md` | `app.schemas` request models (`MODELS`, `AccountIn/Create`, `EntryIn`, `AdjustmentIn`, `CheckpointIn`) | Validate and normalize API request bodies; define cross-field rules (transfers, once-vs-recurring, set-vs-percent). |
| `auth.md` | `app.auth.basic_auth` | HTTP Basic Auth middleware; gate every path except `/healthz` when a password is set. |
| `app-errors.md` | `app.errors` (`validation_detail`, `register`) | Translate Pydantic/data-layer errors into the `{code, params}` HTTP envelope with the right status codes. |

`app/contracts.py` (response models) is **not** a standalone unit: its observable effect
is the exact wire shape of `/api/state`, `/api/audit`, `/api/backup/status`, which is
specified inside those API contracts and `data/schema.md`.

### HTTP API — endpoint groups (`contracts/api/`)
| File | Unit | One-line purpose |
|---|---|---|
| `health-and-state.md` | `GET /healthz`, `GET /api/state` | Liveness probe and the full presentation-neutral snapshot used to hydrate the UI. |
| `accounts.md` | `POST /api/accounts` | Create an account **and** its first checkpoint (starting balance) in one transaction. |
| `resources.md` | `POST/PUT /api/{table}`, `POST /api/{table}/{id}/archive`, `.../restore` | Generic create/update/archive/restore for `entries`, `adjustments`, `checkpoints` (and account updates). |
| `audit.md` | `GET /api/audit`, `POST /api/audit/{id}/revert` | Query the change log (filter/paginate) and undo a single logged change. |
| `forecast.md` | `GET /api/forecast` | Run the forecast engine over current data for a start month + horizon. |
| `backup.md` | `GET /api/backup/status`, `POST /api/backup/run` | Report backup status/file list and trigger a manual backup. |
| `export.md` | `GET /api/export` | Download the full dataset as a JSON attachment. |

### Frontend — views & components (`contracts/frontend/`)
| File | Unit | One-line purpose |
|---|---|---|
| `core-helpers.md` | `core.js` pure helpers & code maps (`eur`, `parseEUR`, `fDate`/`fFull`/…, `errMsg`, `explLine`, `warnMsg`, `api`) | Formatting, EUR parsing, and the `{code,params}`→German maps for errors/explanations/warnings. |
| `form-dialog.md` | `core.js` `formDialog`, `archiveDialog`, `restoreRow` | Generic modal form component: field types, show-if logic, validation, busy/error state, submit. |
| `navigation.md` | `core.js` routing (`setView`, `render`, hash handling, `load`/`refresh`) | Hash-based view switching, nav highlighting, top-level error banner. |
| `forecast-view.md` | `forecast.js` `renderForecast` | Toolbar, chart (SVG), month table, month detail with per-item explanations; warnings/negative banner. |
| `entries-view.md` | `entries.js` `renderEntries`, `entryDialog`, adjustments dialog | List/create/edit bookings and transfers; manage per-entry adjustments. |
| `accounts-view.md` | `accounts.js` `renderAccounts`, `accountDialog`, `checkpointDialog` | Account cards with checkpoints; create/edit accounts and actual balances. |
| `audit-view.md` | `audit.js` `renderAudit`, `historyDialog` | Change-log table with diffs, paging, per-row revert; per-record history dialog. |
| `backup-view.md` | `backup.js` `renderBackup`, `refreshBackupPill` | Backup status panel, run button, file list, export link, and the header status pill. |

`app.js` (8-line bootstrap) is listed **out of scope** in its own contract note (covered
by `navigation.md` + `backup-view.md`); it only wires `load()`+`render()`+pill polling.

### Data (`contracts/data/`)
| File | Unit | One-line purpose |
|---|---|---|
| `schema.md` | SQLite schema | Tables, columns, types, constraints, FKs, triggers (DELETE block, append-only audit), indexes, `user_version`. |

### Backup (`contracts/backup/`)
| File | Unit | One-line purpose |
|---|---|---|
| `backup.md` | Backup subsystem (`app.backup`) | Schedule, change-detection, artifact production, atomicity, failure handling, NAS-marker guard. |
| `restore-manual.md` | Manual restore procedure | The documented restore steps rewritten as an acceptance contract with verification. |

### End-to-end flows (`contracts/e2e/`)
| File | Flow | One-line purpose |
|---|---|---|
| `onboarding-forecast.md` | First account → forecast appears | Welcome screen, create first account, see chart/table. |
| `bookings-adjustments.md` | Add income/expense/transfer + adjustments | Create bookings, attach adjustments, see effect on forecast with explanations. |
| `checkpoints-deviation.md` | Enter actual balances | Add checkpoints, see expected/deviation, forecast continues from the real value. |
| `archive-restore-undo.md` | Data-safety journeys | Archive/restore a record, undo a change from the history, nothing is deleted. |
| `backup-and-export.md` | Backup & export | Run a manual backup (marker missing → error → success → unchanged), download JSON export. |
| `auth-and-persistence.md` | Login + reload persistence | Basic-auth gate when a password is set; data survives reload. |

---

## 3. How the app is started, configured and run

**Entry point:** `app.main:app` (FastAPI), built by `create_app(Settings.from_env())`. Run with
`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`. The FastAPI *lifespan*
runs `db.init(path)` then (unless `BACKUP_SCHEDULER=0`) `backup.start_scheduler(s)` on
startup, and stops the scheduler on shutdown. `create_app(settings)` builds further
independent instances (used by tests).

**Ports:** container listens on **8000**; Docker maps host `${PORT:-8080}→8000`. Dev
container forwards 8000.

**Static UI:** served by the app itself — `StaticFiles` mounted at `/` with `html=True`
(so `/` serves `index.html`). API routes are registered before the mount.

**Environment variables:**
| Var | Default | Meaning |
|---|---|---|
| `DB_PATH` | `/data/finanzen.sqlite` | SQLite file location (parent dir auto-created). `Settings.db_path`. |
| `BACKUP_DIR` | `/backup` | Backup output directory (the NAS mount). |
| `BACKUP_TIME` | `03:00` | Daily backup time, `HH:MM`, 24h. |
| `BACKUP_REQUIRE_MARKER` | `1` | If `1`, refuse backup unless `BACKUP_DIR/.nas-marker` exists. |
| `BACKUP_SCHEDULER` | `1` | If `0`, the daily backup thread is not started (tests). |
| `APP_USER` | `admin` | Basic-auth username. |
| `APP_PASSWORD` | `` (empty) | Basic-auth password; **empty disables auth entirely**. |
| `BACKUP_HOST_DIR` | — | Compose-only: host path bind-mounted to `/backup`. |
| `PORT` | `8080` | Compose-only: host port. |
| `TZ` | `Europe/Berlin` | Timezone (affects `BACKUP_TIME` wall-clock and local timestamps). |

**Config files:** `.env` (from `.env.example`) for compose; `deploy/docker-compose.yml`
(1 worker, volumes `./data:/data` and `BACKUP_HOST_DIR:/backup`); `Dockerfile`
(`python:3.12-slim`, `--workers 1`, healthcheck on `/healthz`); `.devcontainer/devcontainer.json`
(sets `DB_PATH`/`BACKUP_DIR` under `./data`, `BACKUP_REQUIRE_MARKER=0`, `APP_PASSWORD=`);
`.vscode/launch.json` (F5 dev run, optional `dev` password).

**Backup state:** `backup_status.json` is written next to the DB file (same dir as
`DB_PATH`), not in `BACKUP_DIR`.

**DB internals:** WAL mode, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=30000`,
`user_version` baseline 1 + ordered `MIGRATIONS`.

---

## 4. Existing test infrastructure

- **Framework:** `pytest` (9.2.0) + FastAPI `TestClient` (needs `httpx` 0.28.1).
  Install via `pip install -r requirements-dev.txt`. Run with `python -m pytest -q`.
- **Test suite:** `tests/contract/` (the black-box contract suite). The former
  `tests/test_app.py` (11 tests) has been removed; the notes below describe it as it was.
- **Setup:** the module builds a `Settings` pointing at a fresh `tempfile.mkdtemp()`
  (`backup_require_marker=True`, `backup_scheduler=False`, no password); no env vars.
- **Fixtures:** one module-scoped `client` fixture wrapping `TestClient(create_app(S))` (which runs
  the lifespan). Tests share one DB and are **order-dependent** (e.g. `test_backup`
  expects exactly 2 backup files) — this is a known gap tracked as **B-004**.
- **Existing tests:** `test_full_flow`, `test_optimistic_locking_and_audit`,
  `test_state_contract`, `test_audit_contract`, `test_backup_status_contract`,
  `test_nothing_can_be_deleted`, `test_percent_yearly`, `test_backup`,
  `test_migrations_upgrade_preserves_data` (uses its own temp DB via monkeypatch).

---

## 5. Notes / early flags (to expand in Phase 2 OPEN_QUESTIONS)

These stood out while mapping; I will investigate and file them properly in Phase 2:
- `POST /api/{table}/{id}/archive` and `/restore` accept **any** table in `TABLES`
  including `accounts`, but there is no referential cleanup — archiving an account
  referenced by entries/checkpoints just drops it from the forecast (and may raise a
  `no_checkpoint`/`transfer_target_archived` warning).
- `data_version` = `MAX(audit_log.id)`; backups key change-detection off it. Reverts and
  no-op updates both affect the log in specific ways worth pinning down.
- Scheduler uses local `datetime.now()` and a 60s poll loop — hard to control in a
  black-box test (testability gap for `ENVIRONMENT.md`).
- Forecast `once` entries, last-day-of-month clamping, and the "entries before first
  checkpoint are already included" rule have subtle boundaries to cover.

---

**STOP — awaiting your confirmation or adjustments before writing Phase 2 contracts.**

Open questions for you before I continue:
1. **Unit granularity for the `db` package:** I split it into 5 files mirroring the
   module files (connection/schema/crud/audit/errors). Prefer that, or one combined
   `backend/db.md`?
2. **Frontend pure helpers vs. views:** I made `core-helpers.md` its own unit (parsing,
   formatting, code→German maps) since those are the most unit-testable. Keep it split
   from the view/router contracts?
3. **E2E depth:** 6 flows listed. Is HTTP-level E2E (TestClient) acceptable where a real
   browser/DOM harness isn't set up, or do you want these written strictly against a
   browser driver (the existing tests have no browser harness)?
