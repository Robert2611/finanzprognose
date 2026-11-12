# db — error types
ID prefix: DB-ERR
Layer: backend

## Purpose
The data layer signals failure with exceptions that carry a machine-readable
`{code, params}` payload instead of human text, so the API layer can translate them into a
consistent error envelope and the frontend can localize. This keeps language out of the
backend.

## Interface
Import: `from app import db`.

- `db.ApiError(code: str, **params)` — base class; `.code: str`, `.params: dict`.
- `db.NotFound(ApiError)` — raised when a referenced record is missing.
- `db.Conflict(ApiError)` — raised on an optimistic-lock mismatch.

## Dependencies & side effects
None (pure exception types). Raised by `DB-CRUD`/`DB-AUDIT`; caught and translated by the
API error handlers (`ERRENV`).

## Behavior clauses

- `DB-ERR-001` [INFERRED] `ApiError('x', a=1, b=2)` has `.code == 'x'` and
  `.params == {'a': 1, 'b': 2}`.
- `DB-ERR-002` [INFERRED] `NotFound` and `Conflict` are subclasses of `ApiError` (and of
  `Exception`), so a handler for `ApiError` would catch both.
- `DB-ERR-003` [INFERRED] `NotFound` is raised with `code='not_found'` and params
  `entity=<table>`, `id=<id>` (e.g. by `update`/`revert` on a missing record).
- `DB-ERR-004` [INFERRED] `Conflict` is raised with `code='conflict'` and no params (by
  the optimistic-lock check in `update`).
- `DB-ERR-005` [INFERRED] The exception message (`str(ex)`) is the code (no German text).

## Examples
- `NotFound('not_found', entity='accounts', id=99)` → `.code='not_found'`,
  `.params={'entity':'accounts','id':99}`.

## Out of scope / not specified
- HTTP status mapping (that is the API layer's job; see `ERRENV` / `API-RES`).

## Open questions
None.
