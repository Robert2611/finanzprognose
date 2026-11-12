# API — JSON export
ID prefix: API-EXPORT
Layer: api

## Purpose
Lets the user download the complete dataset as a human-readable JSON file, independent of
the app — the same export that is written alongside each backup. It is a plain,
app-independent snapshot.

## Interface
- `GET /api/export` → `200` JSON body with a `Content-Disposition: attachment;
  filename="finanzen_export_<YYYY-MM-DD>.json"` header.
  Body shape (from `db.export_all`):
  ```
  {
    "accounts": [...], "entries": [...], "adjustments": [...], "checkpoints": [...],
    "audit_log": [...],            // oldest-first
    "exported_at": "<timestamp>",
    "data_version": <int>
  }
  ```

## Dependencies & side effects
Read-only. Serializes all four data tables plus the full audit log.

## Behavior clauses

- `API-EXPORT-001` [INFERRED] `GET /api/export` returns `200` with a JSON body containing
  the four data-table arrays, the full `audit_log`, `exported_at`, and `data_version`.
- `API-EXPORT-002` [INFERRED] The response sets a `Content-Disposition: attachment`
  header whose filename is `finanzen_export_<today ISO date>.json`.
- `API-EXPORT-003` [INFERRED] Table arrays include all rows (archived included), matching
  the stored data; money stays integer cents.
- `API-EXPORT-004` [INFERRED] `audit_log` in the export is ordered oldest-first
  (chronological), the reverse of `GET /api/audit`'s default order.
- `API-EXPORT-005` [INFERRED] `data_version` in the export equals the current change
  counter.

## Examples
- Fresh DB → `{accounts:[],entries:[],adjustments:[],checkpoints:[],audit_log:[],
  exported_at:'…',data_version:0}` with the attachment header.

## Out of scope / not specified
- Exact `exported_at` instant.
- Whether export rows use the raw stored shape (they do — full columns incl. `created_at`)
  vs. the `/api/state` projection (they are **not** projected; export is the raw dump).

## Open questions
None.
