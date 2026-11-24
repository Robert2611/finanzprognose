# Traceability

Every clause ID × layer × source tag × existing test coverage. This is the checklist for
the test-writing agent: a row with `—` in **Covered by** has no existing test and needs a
new one. **Covered by** is a historical snapshot of the former `tests/test_app.py`, which has
since been removed; today every clause is tested in `tests/contract/` (see
`tests/contract/COVERAGE.md`).

Source tags: `R`=README, `T`=TEST, `I`=INFERRED, `O`=OBSERVED. (A clause tagged `R`/`I` can
still be *covered* by an existing test — the two columns are independent.)

Existing test keys: `flow`=test_full_flow, `lock`=test_optimistic_locking_and_audit,
`state`=test_state_contract, `audit`=test_audit_contract, `bstat`=test_backup_status_contract,
`nodel`=test_nothing_can_be_deleted, `pct`=test_percent_yearly, `bkp`=test_backup,
`mig`=test_migrations_upgrade_preserves_data, `env`=test_settings_from_env.

## Data layer
| Clause | Tag | Covered by |
|---|---|---|
| DATA-001 | R | nodel |
| DATA-002 | R | nodel |
| DATA-003 | R | nodel |
| DATA-004 | I | — |
| DATA-005 | R | — |
| DATA-006 | R | — |
| DATA-007 | I | — |
| DATA-008 | I | — |
| DATA-009 | I | — |
| DATA-010 | R | — |
| DATA-011 | I | — |
| DATA-012 | I | bkp (indirect) |
| DATA-013 | T | mig |
| DATA-014 | I | — |
| DATA-015 | R | — |
| DATA-016 | R | — |
| DATA-017 | R | — |
| DATA-018 | R | — |

## Backend
| Clause | Tag | Covered by |
|---|---|---|
| DB-CONN-001 | I | — |
| DB-CONN-002 | I | mig |
| DB-CONN-003 | R | — |
| DB-CONN-004 | R | — |
| DB-CONN-005 | I | — |
| DB-CONN-006 | I | — |
| DB-CONN-007 | I | — |
| DB-CONN-008 | I | lock (indirect) |
| DB-CONN-009 | I | — |
| DB-SCHEMA-001 | I | — |
| DB-SCHEMA-002 | I | mig |
| DB-SCHEMA-003 | T | mig |
| DB-SCHEMA-004 | T | mig |
| DB-SCHEMA-005 | T | mig |
| DB-SCHEMA-006 | I | — |
| DB-SCHEMA-007 | I | — |
| DB-SCHEMA-008 | I | — |
| DB-SCHEMA-009 | I | mig |
| DB-SCHEMA-010 | R | — |
| DB-SCHEMA-011 | I | — |
| DB-SCHEMA-012 | R | — |
| DB-SCHEMA-013 | R | — |
| DB-SCHEMA-014 | R | — |
| DB-CRUD-001 | I | — |
| DB-CRUD-002 | I | — |
| DB-CRUD-003 | I | flow |
| DB-CRUD-004 | I | — |
| DB-CRUD-005 | R | flow, lock |
| DB-CRUD-006 | I | lock |
| DB-CRUD-007 | R | lock |
| DB-CRUD-008 | I | lock |
| DB-CRUD-009 | I | — |
| DB-CRUD-010 | R | — |
| DB-CRUD-011 | R | lock |
| DB-CRUD-012 | I | — |
| DB-CRUD-013 | R | — |
| DB-CRUD-014 | I | — |
| DB-CRUD-015 | I | — |
| DB-CRUD-016 | I | — |
| DB-AUDIT-001 | I | — |
| DB-AUDIT-002 | I | lock |
| DB-AUDIT-003 | I | lock |
| DB-AUDIT-004 | I | — |
| DB-AUDIT-005 | I | — |
| DB-AUDIT-006 | R | lock |
| DB-AUDIT-007 | I | — |
| DB-AUDIT-008 | R | lock |
| DB-AUDIT-009 | I | — |
| DB-AUDIT-010 | T | lock |
| DB-AUDIT-011 | R | — |
| DB-AUDIT-012 | R | — |
| DB-AUDIT-013 | I | bkp (indirect) |
| DB-AUDIT-014 | I | — |
| DB-AUDIT-015 | R | — |
| DB-ERR-001 | I | — |
| DB-ERR-002 | I | — |
| DB-ERR-003 | I | — |
| DB-ERR-004 | I | lock (indirect) |
| DB-ERR-005 | I | — |
| FC-001 | I | flow |
| FC-002 | I | — |
| FC-003 | T | flow |
| FC-004 | I | — |
| FC-005 | R | — |
| FC-006 | R | flow |
| FC-007 | R | — |
| FC-008 | R | flow |
| FC-009 | I | flow |
| FC-010 | I | — |
| FC-011 | R | — |
| FC-012 | I | — |
| FC-013 | I | flow |
| FC-014 | I | — |
| FC-015 | I | flow |
| FC-016 | I | — |
| FC-017 | I | — |
| FC-018 | R | — |
| FC-019 | R | flow |
| FC-020 | R | — |
| FC-021 | R/T | pct |
| FC-022 | I | — |
| FC-023 | I | pct |
| FC-024 | I | — |
| FC-025 | I | — |
| FC-026 | R/T | flow |
| FC-027 | I | — |
| FC-028 | R | — |
| FC-029 | I | — |
| FC-030 | I | flow |
| FC-031 | I | flow |
| FC-032 | I | flow |
| FC-033 | R | — |
| FC-034 | R | — |
| FC-035 | R | — |
| FC-036 | R | — |
| FC-037 | R | — |
| SCH-001 | I | — |
| SCH-002 | I | — |
| SCH-003 | I | — |
| SCH-004 | I | — |
| SCH-005 | I | — |
| SCH-006 | I | — |
| SCH-007 | I | — |
| SCH-008 | I | — |
| SCH-009 | I | — |
| SCH-010 | I | — |
| SCH-011 | I | — |
| SCH-012 | I | — |
| SCH-013 | I | — |
| SCH-014 | I | — |
| SCH-015 | I | — |
| SCH-016 | I | — |
| SCH-017 | I | lock (indirect) |
| SCH-018 | I | — |
| SCH-019 | R | — |
| SCH-020 | R | — |
| SCH-021 | R | — |
| AUTH-001 | R | — |
| AUTH-002 | R | (all tests run with auth off) |
| AUTH-003 | I | — |
| AUTH-004 | I | — |
| AUTH-005 | I | — |
| AUTH-006 | I | — |
| AUTH-007 | I | — |
| ERRENV-001 | I | — |
| ERRENV-002 | I | lock |
| ERRENV-003 | I | — |
| ERRENV-004 | I | — |
| ERRENV-005 | I | — |
| ERRENV-006 | I | — |
| ERRENV-007 | I | — |
| ERRENV-008 | I | — |
| ERRENV-009 | I | — |
| ERRENV-010 | R | — |
| SETTINGS-001 | T | env |
| SETTINGS-002 | T | env |
| SETTINGS-003 | T | env |
| SETTINGS-004 | R | — |
| UPDATER-001 | R | — |
| UPDATER-002 | R | — |
| UPDATER-003 | R | — |
| UPDATER-004 | R | — |
| UPDATER-005 | I | — |
| UPDATER-006 | R | — |
| UPDATER-007 | R | — |
| UPDATER-008 | R | — |

## HTTP API
| Clause | Tag | Covered by |
|---|---|---|
| API-STATE-001 | I | — |
| API-STATE-002 | T | state |
| API-STATE-003 | T | state |
| API-STATE-004 | T | state |
| API-STATE-005 | T | state |
| API-STATE-006 | I | — |
| API-STATE-007 | I | — |
| API-STATE-008 | I | — |
| API-STATE-009 | I | — |
| API-STATE-010 | R | — |
| API-STATE-011 | R | — |
| API-STATE-012 | R | — |
| API-ACC-001 | T | flow, state |
| API-ACC-002 | I | — |
| API-ACC-003 | R | — |
| API-ACC-004 | I | — |
| API-ACC-005 | I | — |
| API-ACC-006 | I | — |
| API-ACC-007 | I | flow |
| API-ACC-008 | I | — |
| API-ACC-009 | I | — |
| API-ACC-010 | R | — |
| API-RES-001 | T | flow |
| API-RES-002 | I | — |
| API-RES-003 | I | — |
| API-RES-004 | I | — |
| API-RES-005 | I | — |
| API-RES-006 | I | flow |
| API-RES-007 | T | lock |
| API-RES-008 | T | lock |
| API-RES-009 | I | — |
| API-RES-010 | I | — |
| API-RES-011 | I | lock |
| API-RES-012 | I | — |
| API-RES-013 | I | — |
| API-RES-014 | I | — |
| API-RES-015 | I | — |
| API-RES-016 | O | — |
| API-RES-017 | I | — |
| API-RES-018 | R | — |
| API-RES-019 | R | nodel (DB-level) |
| API-RES-020 | R | — |
| API-RES-021 | R | — |
| API-RES-022 | R | — |
| API-AUDIT-001 | T | lock |
| API-AUDIT-002 | T | audit |
| API-AUDIT-003 | T | lock |
| API-AUDIT-004 | I | — |
| API-AUDIT-005 | I | — |
| API-AUDIT-006 | I | lock |
| API-AUDIT-007 | T | lock |
| API-AUDIT-008 | I | — |
| API-AUDIT-009 | I | — |
| API-AUDIT-010 | I | — |
| API-AUDIT-011 | R | — |
| API-FC-001 | T | flow |
| API-FC-002 | I | — |
| API-FC-003 | I | — |
| API-FC-004 | I | — |
| API-FC-005 | T | flow |
| API-FC-006 | I | — |
| API-FC-007 | R | — |
| API-FC-008 | I | — |
| API-FC-009 | R | — |
| API-BKP-001 | T | bstat |
| API-BKP-002 | I | — |
| API-BKP-003 | I | — |
| API-BKP-004 | T | bkp |
| API-BKP-005 | T | bkp |
| API-BKP-006 | T | bkp |
| API-BKP-007 | T | bkp |
| API-BKP-008 | I | — |
| API-BKP-009 | I | bkp |
| API-BKP-010 | R | — |
| API-BKP-011 | R | — |
| API-UPD-001 | R | — |
| API-UPD-002 | R | — |
| API-UPD-003 | R | — |
| API-UPD-004 | R | — |
| API-UPD-005 | R | — |
| API-EXPORT-001 | I | — |
| API-EXPORT-002 | I | — |
| API-EXPORT-003 | I | — |
| API-EXPORT-004 | I | — |
| API-EXPORT-005 | I | — |

## Backup
| Clause | Tag | Covered by |
|---|---|---|
| BKP-001 | R | — |
| BKP-002 | R | bkp |
| BKP-003 | R/T | bkp |
| BKP-004 | O | — |
| BKP-005 | I | — |
| BKP-006 | R/T | bkp |
| BKP-007 | I | — |
| BKP-008 | I | — |
| BKP-009 | R | bkp |
| BKP-010 | R/T | bkp |
| BKP-011 | R | — |
| BKP-012 | T | bkp |
| BKP-013 | R | — |
| BKP-014 | R | — |
| BKP-015 | R/T | bkp |
| BKP-016 | R | — |
| BKP-017 | I | — |
| BKP-018 | I | bkp (indirect) |
| BKP-019 | R | — |
| BKP-020 | I | bstat |
| BKP-021 | R/I | — |
| BKP-022 | I | — |
| BKP-023 | R | — |
| BKP-024 | R | — |
| BKP-025 | I | — |
| BKP-026 | R | — |
| BKP-027 | R | — |
| BKP-028 | R | — |
| BKP-029 | R | — |
| BKP-030 | R | — |
| BKP-031 | R | — |
| RESTORE-001 | R | — |
| RESTORE-002 | R | — |
| RESTORE-003 | I | — |
| RESTORE-004 | I | — |
| RESTORE-005 | I | — |
| RESTORE-006 | I | — |
| RESTORE-007 | R | — |

## Frontend
| Clause | Tag | Covered by |
|---|---|---|
| FE-CORE-001..018 | I | — |
| FE-CORE-019 | R | — |
| FE-CORE-020 | R | — |
| FE-CORE-021 | R | — |
| FE-CORE-022..027 | I | — |
| FE-FORM-001..015 | I | — |
| FE-FORM-016 | R | — |
| FE-NAV-001..010 | I | — |
| FE-NAV-011 | I | — |
| FE-FORECAST-001..010 | I | — |
| FE-FORECAST-011 | R | — |
| FE-FORECAST-012 | R | — |
| FE-FORECAST-013..017 | I | — |
| FE-FORECAST-018..020 | R | — |
| FE-FORECAST-021..022 | R | — |
| FE-FORECAST-023..025 | R | — |
| FE-FORECAST-026..028 | R | — |
| FE-ENTRIES-001..015 | I | — |
| FE-ENTRIES-016 | R | — |
| FE-ENTRIES-017..019 | I | — |
| FE-ENTRIES-020 | R | — |
| FE-ENTRIES-021..025 | R | — |
| FE-ENTRIES-026..027 | R | — |
| FE-ENTRIES-028 | R | — |
| FE-ENTRIES-029 | R | — |
| FE-ONCE-001..008 | R | — |
| FE-ACCOUNTS-001..003 | I | — |
| FE-ACCOUNTS-004 | R/I | — |
| FE-ACCOUNTS-005..012 | I | — |
| FE-ACCOUNTS-013 | R | — |
| FE-ACCOUNTS-014 | R | — |
| FE-AUDIT-001..009 | I | — |
| FE-AUDIT-010 | R | — |
| FE-AUDIT-011 | R | — |
| FE-AUDIT-012 | R | — |
| FE-AUDIT-013 | R | — |
| FE-AUDIT-014 | R | — |
| FE-BACKUP-001..002 | I | — |
| FE-BACKUP-003 | R | — |
| FE-BACKUP-004..006 | I | — |
| FE-BACKUP-007 | R | — |
| FE-BACKUP-008..009 | I | — |
| FE-BACKUP-010 | I | — |
| FE-BACKUP-011..013 | R | — |
| FE-UPDATE-001 | R | — |
| FE-UPDATE-002 | R | — |
| FE-UPDATE-003 | R | — |
| FE-UPDATE-004 | R | — |
| FE-UPDATE-005 | R | — |
| FE-UPDATE-006 | R | — |
| FE-UPDATE-007 | I | — |

(No existing test covers any frontend clause — there is no browser/DOM harness today.)

## Deploy
| Clause | Tag | Covered by |
|---|---|---|
| DEPLOY-UPD-001 | R | — |
| DEPLOY-UPD-002 | R | — |
| DEPLOY-UPD-003 | R | — |
| DEPLOY-UPD-004 | R | — |
| DEPLOY-UPD-005 | R | — |
| DEPLOY-UPD-006 | R | — |
| DEPLOY-UPD-007 | R | — |
| DEPLOY-UPD-008 | R | — |
| DEPLOY-UPD-009 | I | — |
| DEPLOY-UPD-010 | I | — |
| DEPLOY-UPD-011 | R | — |
| DEPLOY-UPD-012 | R | — |
| DEPLOY-UPD-013 | R | — |

## End-to-end
`HTTP`=HTTP-checkable, `BR`=BROWSER-REQUIRED.
| Clause | Verif | Covered by |
|---|---|---|
| E2E-ONBOARD-001 | BR | — |
| E2E-ONBOARD-002 | BR | — |
| E2E-ONBOARD-003 | BR | — |
| E2E-ONBOARD-004 | HTTP | flow/state (partial) |
| E2E-ONBOARD-005 | HTTP | flow |
| E2E-ONBOARD-006 | BR | — |
| E2E-ONBOARD-007 | BR | — |
| E2E-BOOK-001 | BR | — |
| E2E-BOOK-002 | HTTP | flow |
| E2E-BOOK-003 | BR | — |
| E2E-BOOK-004 | HTTP | flow |
| E2E-BOOK-005 | BR | — |
| E2E-BOOK-006 | HTTP | flow |
| E2E-BOOK-007 | BR | — |
| E2E-BOOK-008 | HTTP | pct |
| E2E-BOOK-009 | BR | — |
| E2E-BOOK-010 | HTTP | — |
| E2E-BOOK-011 | BR | — |
| E2E-BOOK-012 | BR | — |
| E2E-BOOK-013 | BR | — |
| E2E-CP-001 | BR | — |
| E2E-CP-002 | HTTP | flow (partial) |
| E2E-CP-003 | HTTP | flow |
| E2E-CP-004 | BR | — |
| E2E-CP-005 | HTTP | — |
| E2E-CP-006 | BR | — |
| E2E-CP-007 | HTTP | — |
| E2E-ARCH-001 | BR | — |
| E2E-ARCH-002 | BR | — |
| E2E-ARCH-003 | BR | — |
| E2E-ARCH-004 | HTTP | — |
| E2E-ARCH-005 | HTTP | — |
| E2E-ARCH-006 | BR | — |
| E2E-ARCH-007 | BR | — |
| E2E-ARCH-008 | HTTP | lock |
| E2E-ARCH-009 | HTTP | nodel |
| E2E-ARCH-010 | BR | — |
| E2E-BKP-001 | BR | — |
| E2E-BKP-002 | HTTP | bkp |
| E2E-BKP-003 | BR | — |
| E2E-BKP-004 | HTTP | bkp |
| E2E-BKP-005 | HTTP | bkp |
| E2E-BKP-006 | HTTP | bkp |
| E2E-BKP-007 | BR | — |
| E2E-BKP-008 | HTTP | bkp |
| E2E-BKP-009 | HTTP | — |
| E2E-BKP-010 | HTTP | — |
| E2E-AUTH-001 | HTTP | — |
| E2E-AUTH-002 | HTTP | — |
| E2E-AUTH-003 | HTTP | — |
| E2E-AUTH-004 | HTTP | — |
| E2E-AUTH-005 | HTTP | (harness runs auth-off) |
| E2E-AUTH-006 | BR | — |
| E2E-AUTH-007 | BR | — |
| E2E-AUTH-008 | HTTP | state |
| E2E-AUTH-009 | BR | — |
| E2E-AUTH-010 | BR | — |

## Summary
- **Units:** 38 (backend 11, api 8, frontend 9, data 1, backup 2, deploy 1, e2e 6).
- **Clauses:** 491 total (B-026 added the updater, API-UPD, FE-UPDATE and DEPLOY-UPD clauses).
- **Already covered by an existing test (directly or indirectly):** ~45 clauses; the rest
  need new tests.
- **`[OBSERVED]`-only clauses (treat with care):** 2 — API-RES-016, BKP-004. The others
  were settled with the user (OPEN_QUESTIONS, 2026-11-23) and are now `R`.
