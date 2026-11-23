# app.errors — HTTP error envelope
ID prefix: ERRENV
Layer: backend

## Purpose
Turns backend failures into one consistent, language-neutral HTTP shape so the frontend can
localize them. Pydantic validation errors and the data layer's `NotFound`/`Conflict`
become a `{code, params}` JSON body with the right status code; the frontend maps codes to
German.

## Interface
Import: `from app import errors`.
- `errors.validation_detail(ex: pydantic.ValidationError) -> dict` — builds the validation
  envelope.
- `errors.register(app)` — installs exception handlers on the FastAPI app.

**Error envelope on the wire:** `{"code": "<code>", "params": {...}}` with an appropriate
HTTP status. (Framework-internal errors outside the app's own routes may instead use the
plain `{"detail": ...}` shape.)

## Dependencies & side effects
Registers handlers for `db.NotFound`, `db.Conflict`, and `HTTPException`. No DB/IO.

## Behavior clauses

- `ERRENV-001` [INFERRED] A `db.NotFound` raised in a route produces HTTP `404` with body
  `{"code": "not_found", "params": {"entity": ..., "id": ...}}`.
- `ERRENV-002` [INFERRED] A `db.Conflict` produces HTTP `409` with body
  `{"code": "conflict", "params": {}}`. [TEST: `test_optimistic_locking_and_audit` asserts
  the 409 status]
- `ERRENV-003` [INFERRED] `validation_detail` returns
  `{"code": "validation_error", "params": {"errors": [{field, code, params}, ...]}}`, one
  entry per field error.
- `ERRENV-004` [INFERRED] For a built-in constraint violation, each error's `code` is
  Pydantic's machine `type` (e.g. `string_too_short`, `less_than_equal`) and `params`
  carries the relevant context (e.g. `{min_length: 1}`, `{le: 120}`), filtered to
  scalar values.
- `ERRENV-005` [INFERRED] For a custom `model_validator` failure, each error's `code` is the
  short string raised (e.g. `amount_zero`, `end_before_start`, `transfer_same_account`)
  with empty `params`.
- `ERRENV-006` [INFERRED] `field` is the dotted path of the offending field
  (e.g. `name`, `interval_months`); model-level (cross-field) errors may have an empty or
  non-field location.
- `ERRENV-007` [INFERRED] An `HTTPException(detail={"code":...,"params":...})` raised by a
  route is passed through unchanged as the JSON body with its status code (used for
  `unknown_table` 404, `ref_not_found` 422, `validation_error` 422).
- `ERRENV-008` [INFERRED] An `HTTPException` whose `detail` is a plain value (no `code` key)
  is returned as `{"detail": <value>}` — the fallback for framework-internal errors
  (e.g. the generic 404/405).
- `ERRENV-009` [INFERRED] No handled error response contains German text; all human text is
  the frontend's responsibility.
- `ERRENV-010` [README] An invalid query or path parameter (e.g. `?start=2026-13`,
  `?months=0`, a non-numeric `{id}`) returns `422` with the same `validation_error` envelope
  as an invalid body; `field` is the parameter name without the `query`/`path` prefix
  (B-017).

## Examples
- POST an entry with `amount=0` → `422`,
  `{"code":"validation_error","params":{"errors":[{"field":"","code":"amount_zero","params":{}}]}}`
  (field location is the model, not a single field).
- PUT with a stale `expected_updated_at` → `409`, `{"code":"conflict","params":{}}`.

## Out of scope / not specified
- Exact `field` string for model-level validators (empty vs. body root — assert the `code`,
  not the field, for cross-field rules).
- The German text (frontend; `FE-CORE`).

## Open questions
None.
