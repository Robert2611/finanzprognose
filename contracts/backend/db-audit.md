# db — audit log, revert, export, version
ID prefix: DB-AUDIT
Layer: backend

## Purpose
The read and undo side of the append-only change log, plus the two values derived from it:
the change counter (`data_version`) that backups use to skip unchanged runs, and the full
JSON export. "Undo" is implemented as a new forward change that restores a prior snapshot —
history is never rewritten.

## Interface
Import: `from app import db`.

- `db.audit_list(conn, limit=200, before_id=None, entity=None, entity_id=None) -> list[dict]`
  — rows newest-first (`id` DESC), filtered and paginated; `before`/`after` parsed from
  JSON into dicts (or `None`).
- `db.revert(conn, audit_id) -> dict` — undo the change recorded by `audit_log` row
  `audit_id`, as a new logged change; returns the resulting row.
- `db.data_version(conn) -> int` — `MAX(audit_log.id)` (0 if empty).
- `db.export_all(conn) -> dict` — the full dataset for backup/export.

## Dependencies & side effects
`audit_list`/`data_version`/`export_all` are reads. `revert` writes (through `DB-CRUD`'s
write path) and therefore appends a new audit row in the same transaction. Raises
`db.NotFound` for an unknown `audit_id`.

## Behavior clauses

- `DB-AUDIT-001` [INFERRED] `audit_list` returns rows ordered by `id` **descending**
  (newest first).
- `DB-AUDIT-002` [INFERRED] `before` and `after` are returned as parsed objects (dict) or
  `None`, not JSON strings.
- `DB-AUDIT-003` [INFERRED] `entity` filters to rows of that table; `entity_id` filters to
  that record; both combine (AND). [TEST: `test_optimistic_locking_and_audit`]
- `DB-AUDIT-004` [INFERRED] `before_id` returns only rows with `id < before_id`
  (keyset pagination toward older rows).
- `DB-AUDIT-005` [INFERRED] `limit` caps the number of rows returned (default 200).
- `DB-AUDIT-006` [README] `revert` of an `update`/`archive`/`restore` row restores the
  `before` snapshot's writable columns **and** `archived`, writing a new audit row with
  `action='revert'` and `reverts_id=<audit_id>`. [TEST: `test_optimistic_locking_and_audit`]
- `DB-AUDIT-007` [INFERRED] `revert` of a `create` row archives the record (sets
  `archived=1`) — since the record cannot be deleted — writing a `revert` audit row with
  `reverts_id=<audit_id>`.
- `DB-AUDIT-008` [README] Revert never rewrites history: the original audit row is
  untouched and a new forward row is appended. [TEST: `test_optimistic_locking_and_audit`]
- `DB-AUDIT-009` [INFERRED] `revert` on a non-existent `audit_id` raises
  `db.NotFound('not_found', entity='audit_log', id=audit_id)`.
- `DB-AUDIT-010` [TEST] After reverting an update that changed `name` X→Y, the record's
  `name` is X again and the newest audit row has `action='revert'` and `reverts_id` equal
  to the reverted row's id. [TEST: `test_optimistic_locking_and_audit`]
- `DB-AUDIT-011` [README] `data_version` equals `MAX(audit_log.id)`, i.e. it increases by
  one on every logged change and is `0` on an empty database.
- `DB-AUDIT-012` [README] Because a no-op update/archive writes no audit row (see
  `DB-CRUD-010/014`), `data_version` does **not** change across a no-op write, so the next
  backup is skipped as unchanged. Intended (OPEN_QUESTIONS #2, B-019).
- `DB-AUDIT-013` [INFERRED] `export_all` returns a dict with a key per data table
  (`accounts`, `entries`, `adjustments`, `checkpoints`) holding all rows, plus
  `audit_log` (oldest-first), `exported_at` (a `now()` timestamp) and `data_version`.
- `DB-AUDIT-014` [INFERRED] The `audit_log` entries inside `export_all` are in ascending
  id order (chronological), i.e. the reverse of `audit_list`'s default order.
- `DB-AUDIT-015` [README] Reverting a `revert` row is a **redo** (OPEN_QUESTIONS #4, B-019):
  like any revert it restores that row's `before` snapshot, which is the state before the
  undo, so the undone change is back. It is a new forward change with `action='revert'`
  and `reverts_id` = the reverted revert row. Undoing the undo of a `create` (which
  archived the record) therefore makes the record active again. Chains work the same way
  at every step; nothing in history is rewritten.

## Examples
- Create account (audit id 10), update name (id 11) → `revert(c, 11)` writes audit id 12
  (`action='revert'`, `reverts_id=11`) and the account name is back to its pre-update value.
- Empty DB → `data_version()` == 0. After one create → 1.

## Out of scope / not specified
- Exact `exported_at` value (timestamp; assert presence/format, not the instant).

## Open questions
- None open. (#2 and #4 were settled, see `DB-AUDIT-012` and `DB-AUDIT-015`.)
