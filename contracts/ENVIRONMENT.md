# Test Environment

Everything a blind test writer needs to run the app, point it at throwaway storage,
simulate NAS failures, and control time. No implementation reading required.

## 1. Install & run

**Python:** 3.12. Install deps:

```bash
pip install -r requirements-dev.txt   # = requirements.txt + pytest + httpx
```

`requirements.txt` pins `fastapi==0.115.6`, `uvicorn==0.34.0`, `pydantic==2.10.4`.
`requirements-dev.txt` adds `pytest==9.2.0`, `httpx==0.28.1`.

**Start the backend (serves the API *and* the frontend):**

```bash
DB_PATH=./data/finanzen.sqlite BACKUP_DIR=./data/backup \
BACKUP_REQUIRE_MARKER=0 APP_PASSWORD= \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

- The app entry point is `app.main:app`. On startup it runs the DB init and starts the
  backup scheduler thread (FastAPI lifespan). Use the `TestClient` as a context manager
  (`with TestClient(app) as c:`) so the lifespan runs.
- **Always `--workers 1`.** The app assumes a single process (single-writer lock + the
  in-process scheduler). Do not add workers.
- The frontend is served by the same process: `GET /` returns `index.html`; static
  assets are under `/` (e.g. `/core.js`, `/vendor/lit-html.js`, `/style.css`). There is
  **no build step** — files are served as-is.

**Serve the frontend for browser tests:** point Playwright at `http://localhost:8000/`.
There is no separate dev server; the backend serves the SPA.

## 2. Fresh / temporary SQLite database

- The DB file path is the `DB_PATH` env var (parent directories are created automatically).
  Point it at a temp dir for a clean database:

  ```bash
  export DB_PATH=$(mktemp -d)/finanzen.sqlite
  ```

- For an in-process test harness, don't use env vars at all: build the app with
  `app.main.create_app(Settings(db_path=..., backup_dir=..., backup_scheduler=False, ...))`
  and wrap it in `TestClient`. `Settings` (`app/settings.py`, frozen dataclass) has these
  fields: `db_path`, `backup_dir`, `backup_time` (`HH:MM`, default `03:00`),
  `backup_require_marker` (default `True`), `backup_scheduler` (default `True`),
  `app_user` (default `admin`) and `app_password` (default empty = auth off). Each app has its own DB, backup dir, status file and auth, so
  differently configured apps can coexist in one process (see `tests/contract/harness/test_harness.py::test_apps_are_isolated`).
  The data layer takes the path explicitly: `db.init(path)`, `db.tx(path)`, `db.read(path)`.
- A brand-new DB starts empty (no accounts/entries/...). `user_version` is set to the
  baseline (1) plus any applied migrations.
- WAL mode means a DB on disk is three files: `finanzen.sqlite`, `-wal`, `-shm`. When
  copying/moving a database, move all three.

## 3. Pointing the backup at a local directory & simulating NAS failures

The "NAS" is just the directory named by `BACKUP_DIR`. Point it at a temp dir:

```bash
export BACKUP_DIR=$(mktemp -d)
```

The marker guard models "is the NAS mounted?": with `BACKUP_REQUIRE_MARKER=1` (the default
and the production/compose value), a backup refuses unless `BACKUP_DIR/.nas-marker` exists.

| Scenario to simulate | How |
|---|---|
| **NAS mounted, healthy** | `BACKUP_REQUIRE_MARKER=1`, create `BACKUP_DIR/.nas-marker` (empty file). |
| **Marker check disabled** (local dev) | `BACKUP_REQUIRE_MARKER=0` — no marker needed. |
| **NAS not mounted** (marker missing) | `BACKUP_REQUIRE_MARKER=1`, no `.nas-marker` → backup fails with a marker error. |
| **NAS target gone/unreachable** | Set `BACKUP_DIR` to a path that does not exist (and don't create it) → backup fails with a "target does not exist" error. |
| **Permission denied** | Make `BACKUP_DIR` read-only for the process (e.g. `chmod 000` the dir, or own it by another user) → the temp-file write/rename fails and the backup records an error. |
| **Disk full** | Hardest to do portably. Options: a small `tmpfs`/loopback mount sized to a few KB mounted at `BACKUP_DIR`, or a filesystem quota. See the testability gap below. |
| **Slow NAS** | No seam exists to inject latency into file writes without a slow/throttled filesystem under `BACKUP_DIR`. See the testability gap below. |

Note: the backup *status* file `backup_status.json` is written **next to the DB file**
(the directory of `DB_PATH`), **not** in `BACKUP_DIR`. A test that wants a clean backup
status must start from a fresh `DB_PATH` directory.

## 4. Seed & fixture data

- No seed data is required or shipped; a fresh DB is empty and the app works from zero
  (the frontend shows a welcome/empty state).
- To create fixtures, drive the public API (`POST /api/accounts`, `POST /api/entries`,
  etc.) rather than writing SQL — writes outside the data layer bypass the audit log and
  triggers and are explicitly forbidden by the data-safety invariants.
- Money everywhere on the wire and in the DB is **integer cents** (e.g. `100000` = 1000,00 €).
- Dates are ISO `YYYY-MM-DD`; forecast start month is `YYYY-MM`.

## 5. Clock & time dependencies

Time enters in several places; a black-box test must be able to pin it:

| Where | What depends on the clock |
|---|---|
| Audit timestamps (`ts`) | UTC ISO-8601 with millisecond precision, set on every write. |
| `created_at` / `updated_at` | Same UTC format; `updated_at` drives optimistic locking. |
| Backup filenames & `last_attempt`/`last_success` | **Local** time (`datetime.now()`), formatted `YYYY-MM-DD_HHMMSS` in filenames. |
| Backup scheduler | Compares **local** `datetime.now()` to `BACKUP_TIME` (`HH:MM`) once per 60s. |
| Forecast default `start` | `date.today()` when `?start=` is omitted. |
| Frontend `today()` / `thisMonth()` | Browser-local date for default form values and default forecast range. |

There is **no injectable clock**. To make time deterministic:
- For *forecast* and *backup-filename* determinism, always pass explicit inputs: use
  `?start=YYYY-MM` on `/api/forecast`, and assert on backup *results/versioning* rather
  than exact timestamps. Two backups in the same second are disambiguated by the
  `_vN` data-version suffix in the filename, not the timestamp.
- For *scheduler* determinism, prefer calling `POST /api/backup/run` (manual trigger)
  instead of waiting for the 60s loop. See the testability gap below.
- `TZ` affects all local-time values; set `TZ=Europe/Berlin` (the app default) for
  reproducibility.

## 6. Authentication for tests

- `APP_PASSWORD=` (empty) **disables auth** — every request is allowed. The existing
  suite runs this way.
- With a non-empty `APP_PASSWORD`, all paths except `/healthz` require HTTP Basic Auth
  with `APP_USER` (default `admin`) and `APP_PASSWORD`. Supply
  `auth=(user, password)` on the HTTP client, or an `Authorization: Basic …` header.

## 7. Testability gaps (seams a black-box test cannot reach)

Each gap below names a dependency a black-box test can't cleanly control, and suggests a
seam. **Do not implement the seam** — record only.

1. **Backup scheduler timing & 60s poll.** `start_scheduler(s)` spawns a daemon thread
   that loops every 60s comparing `datetime.now()` to `BACKUP_TIME`. A test cannot force
   "it is now 03:00" or fast-forward the loop. *Seam suggestion:* extract the "is a
   scheduled run due?" decision and the sleep interval into injectable parameters, or
   expose a `tick()`/`run_due(now)` function the test can call with a chosen `now`.
   *Workaround today:* test the backup *mechanics* through `POST /api/backup/run`
   (manual) and treat the scheduler's cadence as out of scope.
2. **Hourly retry-after-error.** The retry branch also keys off `datetime.now()` minus
   `last_attempt > 1h`. Same gap/seam as above.
3. **`datetime.now()` for filenames/timestamps.** No clock injection, so exact backup
   filenames and `last_*` timestamps are nondeterministic. *Seam:* a module-level
   `now()`/clock callable that tests can patch (the data layer already has `db.now()`
   for UTC; backup uses `datetime.now()` directly instead).
4. **"Disk full" and "slow NAS".** No seam to inject `ENOSPC` or latency into the file
   writes; only a constrained/throttled filesystem under `BACKUP_DIR` can reproduce them.
   *Seam:* route file writes through an injectable filesystem/open function.
5. ~~**Global/import-time config.**~~ *Closed:* all config lives in a per-app `Settings`
   object (`app/settings.py`). `Settings.from_env()` reads the env vars for production;
   tests pass `Settings(...)` to `create_app()`. No module reads config at import.
6. ~~**Scheduler always starts.**~~ *Closed:* `Settings.backup_scheduler` (env
   `BACKUP_SCHEDULER`, default `1`) controls whether the lifespan starts it, and the
   lifespan stops it on shutdown.
7. **Browser/DOM.** The repo ships no browser test harness; the frontend is only
   reachable via a real browser. E2E clauses tagged `[BROWSER-REQUIRED]` need Playwright
   (planned) pointed at the served SPA; `[HTTP-checkable]` ones can be verified with
   `TestClient`.
