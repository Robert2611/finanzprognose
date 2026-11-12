# API — audit log & revert
ID prefix: API-AUDIT
Layer: api

## Purpose
Exposes the immutable change log so the UI can show a complete history and let the user undo
any single change. Undo is a new forward change, never a rewrite of history.

## Interface
- `GET /api/audit?limit=&before_id=&entity=&entity_id=` → `200` list of `AuditEntryOut`,
  newest first:
  `{id, ts, action, entity, entity_id, before|null, after|null, comment, reverts_id|null}`.
  - `limit` default 200, max 1000.
  - `before_id` returns rows with `id < before_id` (older-page pagination).
  - `entity` / `entity_id` filter to one table / one record.
- `POST /api/audit/{audit_id}/revert` → `200` with the resulting data row.

## Dependencies & side effects
`GET` is read-only. `revert` writes a new audited change (see `DB-AUDIT`), advancing
`data_version`.

## Behavior clauses

- `API-AUDIT-001` [TEST] `GET /api/audit?entity=accounts&entity_id={id}` returns that
  account's audit rows, newest first. [TEST: `test_optimistic_locking_and_audit`]
- `API-AUDIT-002` [TEST] Each audit object has exactly the keys
  `{id, ts, action, entity, entity_id, before, after, comment, reverts_id}`. [TEST:
  `test_audit_contract`]
- `API-AUDIT-003` [TEST] A `create` row has `before=null` and `after=<row>`; an `update`
  row has both `before` and `after` with the changed fields reflected. [TEST:
  `test_optimistic_locking_and_audit`]
- `API-AUDIT-004` [INFERRED] `limit` caps the result size (default 200); values above 1000
  are rejected with a `422` (query constraint `le=1000`).
- `API-AUDIT-005` [INFERRED] `before_id` enables paging: successive calls with the last
  returned `id` walk toward older entries; a short page (fewer than `limit`) signals the end.
- `API-AUDIT-006` [INFERRED] `entity` and `entity_id` combine (AND) to scope to a single
  record's history.
- `API-AUDIT-007` [TEST] `POST /api/audit/{id}/revert` of an update returns the record
  restored to its pre-update state, and a subsequent audit query shows a new newest row with
  `action='revert'` and `reverts_id` equal to the reverted audit id. [TEST:
  `test_optimistic_locking_and_audit`]
- `API-AUDIT-008` [INFERRED] `revert` of a `create` row archives the record (it cannot be
  deleted) and writes a `revert` row referencing the create.
- `API-AUDIT-009` [INFERRED] `revert` of a non-existent `audit_id` returns `404`
  `{"code":"not_found","params":{"entity":"audit_log","id":audit_id}}`.
- `API-AUDIT-010` [INFERRED] The audit log is append-only over the API too: there is no
  endpoint to edit or delete audit rows.

## Examples
- Create+update an account, then `POST /api/audit/{update_id}/revert` → `200`, account name
  back to original; `GET /api/audit?entity=accounts&entity_id={id}` newest row is
  `{action:'revert', reverts_id: update_id}`. [TEST]

## Out of scope / not specified
- Exact `ts` values (timestamps).
- Reverting a `revert` (structurally allowed; semantics unspecified — OPEN_QUESTIONS #4).

## Open questions
- OPEN_QUESTIONS #4 (revert-of-revert).
