# Behavioral Contracts

This directory specifies **what the Finanzprognose application is supposed to do**, unit
by unit, precisely enough that a test suite can be written from these documents **without
reading the implementation**.

## Purpose

- Describe observable behavior only: inputs, outputs, side effects, errors, state changes.
- Capture intent, not implementation. The current code is evidence of intent, not proof
  of it — where behavior looks wrong it is flagged in `OPEN_QUESTIONS.md`, not presented
  as correct.
- Serve as the single checklist for the test-writing agent (see `TRACEABILITY.md`).

## How to read a contract

Each unit file follows one template: **Purpose → Interface → Dependencies & side effects
→ Behavior clauses → Examples → Out of scope → Open questions.** The **Behavior clauses**
section is the normative part: every clause is atomic, has a stable ID, and carries a
source tag.

## Layers & index

| Layer | Directory | Contracts |
|---|---|---|
| Backend (Python) | `backend/` | db-connection, db-schema, db-crud, db-audit, db-errors, forecast, schemas, auth, app-errors |
| HTTP API | `api/` | health-and-state, accounts, resources, audit, forecast, backup, export |
| Frontend (lit-html) | `frontend/` | core-helpers, form-dialog, navigation, forecast-view, entries-view, accounts-view, audit-view, backup-view |
| Data | `data/` | schema |
| Backup | `backup/` | backup, restore-manual |
| End-to-end | `e2e/` | onboarding-forecast, bookings-adjustments, checkpoints-deviation, archive-restore-undo, backup-and-export, auth-and-persistence |

Supporting documents:
- `INVENTORY.md` — the unit map and architecture overview.
- `ENVIRONMENT.md` — how to install, run, point at a temp DB, simulate NAS failures,
  control the clock, and the known testability gaps.
- `OPEN_QUESTIONS.md` — ambiguities and suspected bugs, numbered, referenced by clauses.
- `TRACEABILITY.md` — every clause ID × layer × source tag × existing test coverage.

## ID scheme

Each contract declares an **ID prefix**. Clauses are numbered `PREFIX-NNN`, e.g.
`API-RES-004`, `FC-012`, `E2E-ONBOARD-003`. IDs are stable: never renumber; append new
clauses at the end.

## Source tags

Every clause ends-tagged with exactly one origin:

- `[README]` — stated in the README or other project docs.
- `[TEST]` — asserted by an existing test in `tests/test_app.py`.
- `[INFERRED]` — inferred from names, structure, or obvious purpose.
- `[OBSERVED]` — only evident from what the code currently does, nothing else confirming
  intent. Where an `[OBSERVED]` behavior looks wrong or arbitrary, the clause points to an
  `OPEN_QUESTIONS.md` entry instead of asserting the behavior is intended.

E2E clauses additionally carry a verification tag:

- `[HTTP-checkable]` — verifiable at the API level with FastAPI `TestClient` (no browser).
- `[BROWSER-REQUIRED]` — needs a real browser/DOM (anything about what is rendered,
  clicked, or shown to the user). Written to be runnable by Playwright once added.

## Rules for the test-writing agent

**You may read:** everything in `contracts/`, the project `README.md`, and the public
entry points needed to *start and configure* the app — `docker-compose.yml`, `Dockerfile`,
`.env.example`, `.devcontainer/devcontainer.json`, `.vscode/launch.json`, `requirements*.txt`,
and the environment-variable names those expose. You may read `tests/test_app.py` to see
the existing harness (but you are writing a fresh, independent suite).

**You may NOT read:** the implementation under `app/` — not `app/main.py`, `app/db/*`,
`app/forecast.py`, `app/backup.py`, `app/schemas.py`, `app/auth.py`, `app/errors.py`,
`app/contracts.py`, nor the frontend JS under `app/static/`. The vendored
`app/static/vendor/lit-html.js` is third-party and also off-limits. If a contract is
missing information you need (a selector, a schema field, an error format), treat that as
a contract defect to report — do not reverse-engineer it from source.

**Precedence:** where a contract and the current code disagree, the contract plus its
`OPEN_QUESTIONS.md` entry win. Do not assert `[OBSERVED]`-only behavior that a linked
open question marks as suspected-wrong; write those as `xfail`/skipped pending resolution.
