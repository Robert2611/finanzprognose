# Contract feedback

Ambiguities, gaps, and unobservable clauses found while planning. Appended to as tests are
written. Each item names the clause, the problem, and what I did instead.

| # | Clause(s) | Problem | What I did |
|---|---|---|---|
| F-1 | DATA-001..015 | `contracts/data/schema.md` is missing. `contracts/README.md` and `INVENTORY.md` list it, and `TRACEABILITY.md` has 15 DATA clauses, but there is no `contracts/data/` directory. | **Resolved** by `contracts/data/schema.md` (merge 0f6f4c2). All DATA clauses are now testable. |
| F-2 | DB-SCHEMA-010 | `synchronous=FULL` is a per-connection pragma and cannot be observed from a new connection. | Only `journal_mode=wal` is asserted. |
| F-3 | `forecast.occurrences`, `forecast.add_months` | The element type yielded by `occurrences` (`date` or ISO string?) and the month base for `add_months(y, m, n)` (1-based?) are not stated. | Will test only through `compute` and `amount_at`, which have stated shapes. |
| F-4 | `forecast.compute` | "Raw rows as stored" does not list the required keys per row (e.g. whether `created_at` is needed, whether `archived` may be omitted). | Will build rows from the `/api/export` shape (full columns) once seen through the API. |
| F-5 | FE-FORECAST-007/008/011/012, E2E-BOOK-007, E2E-CP-004 | No selector for chart month rects, the zero line, individual item rows, or how a derivation (`.expl`) is "expanded". | See TEST_PLAN §4. |
| F-6 | API-BKP-009, BKP-002 | The reason string ("manuell", "zeitplan") is German and the contract tells tests not to assert German text, while BKP-002 specifies `reason="manuell"`. | Assert `last_result` and the `.nas-marker` substring only. |
| F-7 | BKP-010 | "A failing integrity check aborts the run" has no injection seam. | Skip stub, marked TG-7. |
| F-8 | BKP-019, BKP-001 | Scheduler cadence still needs a clock seam (TG-1/2/3). The catch-up risk (OQ #12) is gone for tests because `backup_scheduler=False`. | Skip stubs. |
| F-9 | API-RES-015 | Archive/restore unknown-table 404 has no defined body (OQ #9). | Assert the status code only. |
| F-10 | API-AUDIT-004 | Only `limit>1000` is specified. `limit=0`, negative, and non-integer are not. | Test `1001` only. |
| F-11 | `Settings` | The contracts name only `db_path`, `backup_dir`, `backup_time`, `backup_require_marker`, `backup_scheduler`. The auth fields (`app_password`, and a user field) are not named anywhere in `contracts/`; I know `app_password` only from the existing harness. The `create_app` signature and the `app.settings` import path are also only in `ENVIRONMENT.md` prose. | **Resolved**: `ENVIRONMENT.md` and `auth.md` now name `app_user` and `app_password`. |
| F-12 | `contracts/ENVIRONMENT.md`, `INVENTORY.md` | Closed gaps TG-5/TG-6 are struck through but still numbered, so my TG-7 for the integrity-check seam is a new number, not a renumbering. `INVENTORY.md` §3 says `db.data_version(conn)` now requires a connection. | Noted. |
| F-13 | DATA-004 | "Exactly the columns, types and NOT NULL flags listed" for the audit/data tables, but the common `id`, `archived`, `created_at`, `updated_at` columns have no stated declared type for `archived`/`created_at` beyond the prose. | Assert the table set, column names, and NOT NULL flags; assert types only where the table gives them (INTEGER, TEXT, REAL). |
| F-14 | DB-SCHEMA-004..007, DATA-013 | The migration callable's signature is not stated. The contract only says `(target_version, fn)` and that migrations guard `ALTER` with `_has_column(conn, ...)`. | Tests assume `fn(conn)`. |
| F-15 | DB-CRUD-004 | "Missing whitelisted keys are inserted as NULL/column default" conflicts with `accounts.kind NOT NULL DEFAULT 'checking'`: a NULL insert violates NOT NULL, a default insert does not. The clause does not say which applies. | Test asserts the default (`kind == 'checking'`); see TEST_REPORT. |
| F-16 | `forecast.compute` result | The shape lists per-month account blocks keyed `"<account_id>"` (string) but a direct in-process call may return int keys; the contract does not say which. | Test helper accepts either key type. |
| F-17 | `forecast.amount_at` | The contract does not say whether `amount_at` sorts its `adjs` by `(effective_date, id)` itself or expects a pre-sorted list. FC-018 states the ordering for the engine. | Order is tested through `compute`, not through `amount_at` with an unsorted list. |
| F-18 | FC-020/FC-023 | "Rounded half-up" is not defined for negative ties (-151.5 -> -151 or -152?). | Ties are tested only for positive amounts; negative tests avoid exact .5 intermediates. |
| F-19 | FC-006 / E2E-ONBOARD-005 | FC-006 does not say what the per-account `opening` of the start month is, but E2E-ONBOARD-005 says the starting month "opens at the start balance". | Asserted under E2E-ONBOARD-005 only. |
| F-20 | SCH-010 / SCH-011 | For `kind=once` with `end_date < start_date`, it is not stated whether `end_before_start` fires or the normalisation drops `end_date` first. | Not tested. |
| F-21 | SCH-013 / SCH-014 | A transfer with `amount == 0` matches both rules; the contract says SCH-014 "applies to non-transfers too" but does not say which code a zero transfer reports. | Either code is accepted for that case. |
| F-22 | API-RES-017 | "<=500 chars; truncated if longer" for archive/restore `comment`: truncation vs. 422 rejection is unclear (the body model limits `comment` to 500). | Test accepts 200 (truncated to <=500) or 422. |
| F-23 | API-BKP-008 | "Newest-first" is not defined for backups with the same second in their stamp (the `_v<N>` suffix is not zero-padded, so name order is not version order). | Order is asserted only across different timestamps. |
| F-24 | FE-CORE-027 | `ENTITY`/`ACTION`/`FIELD` "provide the German labels" but only ACTION (FE-AUDIT-002) and a few ENTITY labels (via errMsg examples) are spelled out. | Only the documented entries are asserted. |
| F-25 | FE-FORM-007 | "Left empty" is not defined for whitespace-only input. | Not tested. |
| F-26 | FE-FORECAST-009/010 | The per-account card in `#fdetail` has no documented selector or class. | Assertions use the visible text of `#fdetail`. |
| F-27 | FE-ACCOUNTS-012 | "An archived account's card hides its edit/add actions": it is unclear whether this includes the Bearbeiten/Archivieren buttons on the account's checkpoint rows (observed: they stay). | Only account-level buttons (outside the checkpoint table) are asserted. |
| F-28 | FE-ENTRIES-015 | Whether archiving an adjustment asks for confirmation (like `archiveDialog`) is not stated (observed: it archives immediately). | The test tolerates both. |
| F-29 | FE-ACCOUNTS (interface) | The empty state "Noch keine Konten." has no stated markup (observed: a `.panel` inside `.cards`), so `.cards > .panel` count is not reliable for "no accounts". | Tests assert the empty-state text. |
