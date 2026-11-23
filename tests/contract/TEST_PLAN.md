# Contract test plan (Phase 1: awaiting confirmation)

> **Revised after commit 1d92908 (B-010, `create_app(Settings)`).** That commit closes TG-5
> (import-time config) and TG-6 (scheduler always starts), so the subprocess-per-test design
> from the first draft is dropped. Everything except Playwright now runs in-process.
> Later merges added `contracts/data/schema.md` (DATA-001..015 are now all specified) and named
> `Settings.app_user` / `app_password`; gap G-1 and finding F-1/F-11 are closed.

Black-box suite written only from `contracts/**`, `README.md`, and the config/entry-point
files. No implementation code under `app/` has been read.

## How to run

```bash
pip install -r requirements-dev.txt             # includes pytest-playwright
python -m playwright install chromium            # one-time; Chromium is already cached here
python -m pytest -q                              # default: legacy tests + contract suite, browser tests skipped
python -m pytest -q -m ""                        # EVERYTHING, incl. Playwright tests (what the release pipeline runs)
python -m pytest -q -m "" tests/contract         # only the contract suite, incl. browser tests
python -m pytest -q -m "" tests/contract --contract BKP-004   # a single clause
```

Decisions taken (from your answers): in-process `create_app(Settings)` + `TestClient`;
tests that use a browser are auto-marked `browser` and excluded by default via the root
`pytest.ini` (`addopts = -m "not browser"`); `.github/workflows/release.yml` runs
`python -m pytest -q -m ""` so browser tests gate every release; the open-question clauses
(`DB-CRUD-013`, `API-RES-018`, `FC-028`, `API-FC-007`) are skipped with a reason.

## 1. Directory layout

```
tests/contract/
  pytest.ini               # registers the `contract` marker, strict markers, default opts
  conftest.py              # fixtures, clause-ID validation hook, result-recording plugin
  helpers/
    server.py              # in-process uvicorn thread serving create_app(settings), for Playwright only
    seed.py                # API-driven builders: account(), entry(), adjustment(), checkpoint()
    nas.py                 # temp NAS dir, marker, read-only/unreachable simulations
    sqlite_view.py         # read-only sqlite3 access to a DB or a backup file
    report.py              # junit/JSON results -> COVERAGE.md and TEST_REPORT.md
  data/                    # raw SQLite: DELETE blocking, audit append-only
  backend/                 # in-process: app.db, app.forecast, app.schemas, app.errors
                           # + live-server: auth, error envelope
  api/                     # HTTP endpoints against a live server
  backup/                  # run_backup/status/list_backups in-process, plus HTTP + files on the temp NAS
  frontend/                # Playwright: core.js helpers, dialog, views
  e2e/                     # contracts/e2e flows: HTTP-checkable (httpx) and BROWSER-REQUIRED (Playwright)
  TEST_PLAN.md  CONTRACT_FEEDBACK.md  TEST_REPORT.md  COVERAGE.md
```

## 2. Shared fixtures

| Fixture | Scope | What it does |
|---|---|---|
| `workdir` | function | A fresh `tmp_path` tree: `data/finanzen.sqlite`, `nas/`. Nothing is shared between tests. |
| `nas` | function | The temp NAS dir (`BACKUP_DIR`). Options: `marker=True/False`, `exists=True/False`, `read_only=True`. Helper methods: `put_marker()`, `files()`. |
| `settings` (factory) | function | Builds `Settings(db_path=<tmp>/data/finanzen.sqlite, backup_dir=<tmp>/nas, backup_require_marker=True, backup_scheduler=False, app_password="")`, with per-test overrides (`app_password`, `app_user`, `backup_require_marker`, `backup_time`). Field names are taken from the contract (`db_path`, `backup_dir`, `backup_time`, `backup_require_marker`, `backup_scheduler`) and from the existing harness (`app_password`). |
| `app_client` (factory) | function | `with TestClient(create_app(settings)) as c`: runs the lifespan, so the DB is initialised. Several differently configured apps can coexist in one process. Used for all API, backend-HTTP, backup-HTTP and e2e HTTP tests. |
| `live_server` (factory) | function | Only for Playwright: serves `create_app(settings)` with `uvicorn.Server` in a background thread of the test process on a free port. No env vars, no subprocess. Waits for `/healthz` by polling, shuts the server down at teardown. |
| `api` (`seed`) | function | Builders that go through the public API only: `seed.account(...)`, `seed.entry(...)`, `seed.adjustment(...)`, `seed.checkpoint(...)`, `seed.standard_world()` (the account/entry set from the e2e preconditions). They take any client (`TestClient` or `httpx`). |
| `workdir` / `nas` | function | `tmp_path` tree and the temp NAS dir. Helpers: `put_marker()`, `files()`, `make_read_only()`, `remove()` (unreachable target). |
| `db_path` | function | `str(tmp_path/"x"/"finanzen.sqlite")` for in-process data-layer tests: `db.init(path)`, `db.tx(path)`, `db.read(path)` (the path is an explicit argument now). |
| `browser` / `page` | session / function | `pytest-playwright` Chromium, a fresh context per test, `base_url=live_server.url`. `http_credentials` for the auth tests. `page.clock` pins the browser date and fast-forwards the pill poll (no sleeps). `page.route` simulates an unreachable backend and delays responses. |
| Clause validator | session hook | Fails collection if a `@pytest.mark.contract("ID")` names an ID that is not in `contracts/TRACEABILITY.md`. |
| Result recorder | session plugin | Writes `results.json` (clause ID -> outcomes) so `COVERAGE.md` and `TEST_REPORT.md` are generated, not hand-written. |

**Isolation:** every test builds its own `Settings` pointing at its own temp DB, status file and
NAS directory, so no state is shared and run order does not matter. The scheduler is switched
off with `backup_scheduler=False`, so there is no background thread and no catch-up backup
(OPEN_QUESTIONS #12) to disturb a test. Only the browser tests need a real socket; they use an
in-process uvicorn thread instead of a subprocess.

**What the commit does not change:** the clock (TG-1/2/3: no `tick()`/`run_due(now)`), disk full
/ slow NAS (TG-4), and the integrity-check injection (new TG-7). `Settings` is not specified in
the contracts beyond five fields (see F-11).

## 3. Clause -> level map

IDs are from `contracts/TRACEABILITY.md`. "FS" = file-based, "IP" = in-process import,
"LS" = live server (Playwright only), "PW" = Playwright.

| Group | Clauses | Level / location | Notes |
|---|---|---|---|
| Data layer | DATA-001..015 | `data/` (plain `sqlite3` on a DB made by `db.init(path)`; raw INSERT/UPDATE/DELETE, `PRAGMA table_info`, `sqlite_master`) | FK clauses (012) use `db.connect(path)` so `foreign_keys=ON`. 010 is checked as "audit row written in the same transaction as the change" via the API. 015: not asserted at DB level, as the contract instructs. Trigger error text is not asserted. |
| db-connection | DB-CONN-001..009 | `backend/` IP | `db.connect(path)`/`tx(path)`/`read(path)`. 002 now means two paths side by side in one process. 004 uses two threads and an event; 005/006 check the closed connection. |
| db-schema | DB-SCHEMA-001..011 | `backend/` IP | `db.init(path)`; patches `db.MIGRATIONS` (documented). |
| db-crud | DB-CRUD-001..016 | `backend/` IP | 010/014 per OQ #2: tested as specified (defensible, not flagged suspicious). 013 is skipped (OQ #3 suspected bug). |
| db-audit | DB-AUDIT-001..014 | `backend/` IP | 012 follows 010. Revert-of-revert not tested (OQ #4). |
| db-errors | DB-ERR-001..005 | `backend/` IP | |
| forecast | FC-001..032 | `backend/` IP (pure) | Table-driven. 011 as OBSERVED + OQ #6 (not flagged suspicious): tested. 028 is skipped (OQ #7 "review"). |
| schemas | SCH-001..018 | `backend/` IP | Parametrized valid/invalid cases per field. |
| auth | AUTH-001..007 | `backend/` `app_client` with `app_password` set | 006 is not observable. |
| errors envelope | ERRENV-001..009 | `backend/` `app_client` | 009 is sampled over the error responses seen in the suite. |
| API | API-STATE-*, API-ACC-*, API-RES-*, API-AUDIT-*, API-FC-*, API-BKP-*, API-EXPORT-* | `api/` `app_client` | API-RES-018 skipped (OQ #3). API-RES-020 tested only as "archive is accepted" (OQ #10). API-FC-007 skipped (OQ #8). API-RES-015: status only (OQ #9). |
| Backup | BKP-002..015, 017 (partly), 018, 020..023; API-BKP | `backup/` | Artifact validity, version/filename, `backups.log`, never-delete, concurrent writes, every failure mode, permission denied, unreachable NAS. |
| Restore | RESTORE-001..007 | `backup/` | The manual procedure is automated in the test into a second `Settings.db_path` plus a second app built with `create_app`. 007 is a UI path (PW, via e2e/archive). |
| Frontend helpers | FE-CORE-001..027 | `frontend/` PW (`page.evaluate(() => import('/core.js'))`) | No private state access; `warnMsg` is tested through the UI banner or after a real `load()`. |
| Frontend views | FE-FORM, FE-NAV, FE-FORECAST, FE-ENTRIES, FE-ACCOUNTS, FE-AUDIT, FE-BACKUP | `frontend/` PW | Selectors only from the contract (ids, `data-view`, `data-name`, roles, German text). |
| E2E | E2E-*-`[BROWSER-REQUIRED]` | `e2e/` PW | |
| E2E | E2E-*-`[HTTP-checkable]` | `e2e/` `app_client` | Flow-shaped, exactly the contract examples. |

## 4. Clauses I cannot test as specified

These are kept as `@pytest.mark.skip(reason="Testability gap TG-n: …")` stubs where a seam is
suggested, or logged in `CONTRACT_FEEDBACK.md` when the clause is ambiguous/unobservable.

| Clause(s) | Reason | Class |
|---|---|---|
| BKP-001, BKP-019 (and the hourly retry) | Scheduler timing: TG-1/TG-2. `start_scheduler(s)` now returns a stop `Event`, but there is still no `tick()`/`run_due(now)` seam, so the 60 s wall-clock loop cannot be driven. | TG-1/2 (skip stub) |
| BKP-013 exact timestamp value; `last_*` timestamps | No clock injection (TG-3). I assert only the `finanzen_YYYY-MM-DD_HHMMSS_v<N>.sqlite` pattern and that `<N>` equals `data_version`. | Partial |
| Disk full, slow NAS (ENVIRONMENT table) | TG-4: no ENOSPC/latency seam; no root/mount rights for a loopback or tmpfs in this container. | TG-4 (skip stub) |
| BKP-010 "failing integrity check aborts, no final artifact" | No seam to inject a failing `integrity_check`. The success half (valid artifact) is tested. | **TG-7 (new)**: skip stub |
| BKP-016, BKP-017 (mid-write failure) | Temp-name/fsync/atomic-rename internals are not observable. I test the observable parts: after a successful run no `.tmp` files remain, and after read-only NAS/missing dir failures no final `.sqlite`/`.json` appears and the server keeps serving. The true "fail halfway through a write" case needs an fs-injection seam (TG-4). | Partial + TG-4 stub |
| BKP-022 "does not take the data-layer write lock" | Internal. I test the observable part: reads and writes succeed while a backup runs (BKP-021). | Partial |
| DB-CONN-009 (no connection leak) | Not observable through the documented interface beyond "closed after exit" (tested under DB-CONN-005/006). | Partial |
| DB-SCHEMA-010 `synchronous=FULL` | Per-connection pragma, not readable from a new connection. Only `journal_mode=wal` is observable. | Ambiguous, logged |
| AUTH-006 constant-time compare | A timing property; not black-box testable. Only "both username and password must match" is tested. | Unobservable |
| BKP-005 `force=True` | Reachable only via `backup.run_backup(s, force=True)`, so tested in-process with a `Settings` (no patching needed now). | IP |
| DB-CRUD-013, API-RES-018 | Archive/restore not locked: OQ #3 "possible bug". Not asserted; skipped pending resolution. | OQ #3 |
| FC-028 | OQ #7: transfer to an archived target dropped silently. Not asserted; skipped. | OQ #7 |
| API-FC-007 | OQ #8: invalid month `2026-13`/`2026-00` unspecified. Not asserted; skipped. | OQ #8 |
| FE-FORECAST-007/008/011/012, E2E-BOOK-007, E2E-CP-004 | The contract names no selector for chart month `<rect>`s, the zero line, individual item rows, or how an item's `.expl` is "expanded" (click, `<details>`, always visible?). I will use visible German text and roles where the contract gives text, and log the rest. | Ambiguous, logged |
| API-ACC-003 vs OQ #11 | `last_reason` ("manuell"/"zeitplan") is German in the backend. I assert only the `last_result` enum and the `.nas-marker` substring. | By design |
| ERRENV-009 "no German in any error" | Not provable generally; sampled over the error bodies the suite produces. | Partial |

## 5. Conventions

- Marker: `@pytest.mark.contract("BKP-004", "API-BKP-006")` (several IDs allowed); the
  docstring is one line starting with the clause ID.
- No sleeps: server readiness via `/healthz` polling; browser waits via `expect`/auto-wait;
  clock via `page.clock`; concurrency via threads with explicit barriers.
- Money is integer cents everywhere; dates ISO.
- Frontend spacing: assert significant characters (normalize NBSP/narrow NBSP), per
  `core-helpers.md` "Out of scope".
- Order of work: data -> backend -> api -> backup -> frontend -> e2e. Each layer is run before
  starting the next. No source or contract file is modified; a failing test stays failing.

## 6. New dependencies

- `pytest-playwright` (brings `pytest-base-url`; `playwright` 1.64.1 and Chromium 1248 are
  already installed in this container). Originally added as a separate `requirements-contract.txt`;
  now part of `requirements-dev.txt`, pinned to a version compatible with `pytest==9.2.0`.
  The Docker image is not affected.
- No Node toolchain. No `faketime`, no root-only mounts.
- Config files added: `tests/contract/pytest.ini` (marker registration). A root `pytest.ini` only
  if you choose to keep the browser tests out of the default run (Decision 2).

## 7. Decisions

All resolved (see the top of this file). Phase 2 infrastructure is in place; Phase 3 is next.
