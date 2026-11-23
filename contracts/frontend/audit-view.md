# Frontend — audit view ("Verlauf") & history dialog
ID prefix: FE-AUDIT
Layer: frontend

## Purpose
Shows the complete, immutable change history with before/after diffs and lets the user undo
any single change. A compact per-record variant ("Verlauf" dialog) is reachable from the
entries/accounts views.

## Interface
Rendered into `#main` when view = `verlauf`. Fetches `GET /api/audit?limit=200` (and pages
with `before_id`). Stable DOM:
- `.toolbar` with heading `"Änderungsverlauf"` and an explanatory subtitle.
- A `table` with headers `Zeitpunkt, Aktion, Objekt, Änderung` + an action column; each row
  has a `"Rückgängig"` button.
- An `"Ältere laden"` button when more rows may exist (a full page of 200 was returned).

`historyDialog(entity, id)` opens a `<dialog>` listing that record's audit rows (same row
template) with a `"Schließen"` button.

## Dependencies & side effects
`GET /api/audit`, `POST /api/audit/{id}/revert`. Reloads state and re-renders after a revert.

## Behavior clauses

- `FE-AUDIT-001` [INFERRED] The view lists audit rows newest-first, each showing the
  timestamp and `#id`, the action label (German `ACTION` map), the object (entity label +
  a human object label), and a diff of what changed.
- `FE-AUDIT-002` [INFERRED] The action is shown in German: `Angelegt/Geändert/Archiviert/
  Wiederhergestellt/Rückgängig` for `create/update/archive/restore/revert`.
- `FE-AUDIT-003` [INFERRED] For a `create` row (no `before`), the diff lists the created
  field values; for an update, it lists only changed fields as `old → new`.
- `FE-AUDIT-004` [INFERRED] Field names and values are rendered via the German `FIELD` map
  and value formatters (amounts as EUR, account/entry ids as names, dates formatted, booleans
  as `ja/nein`, rhythm/mode/kind as German words).
- `FE-AUDIT-010` [README] The entry field `estimated` is labeled `Fest/geschätzt` and its
  values are shown as `fest` / `geschätzt` (B-015), e.g. `"Fest/geschätzt: fest → geschätzt"`.
- `FE-AUDIT-005` [INFERRED] A row with a `comment` shows it as `„<comment>“`; a `revert` row
  shows `"Rückgängig gemacht: Protokolleintrag #<reverts_id>"` derived from `reverts_id`.
- `FE-AUDIT-006` [INFERRED] Clicking `"Rückgängig"` opens a confirmation dialog explaining the
  record will be reset and the reset itself logged; confirming POSTs the revert.
- `FE-AUDIT-007` [INFERRED] After a successful revert, a `"Rückgängig gemacht"` toast is
  shown and the list re-renders with the new `revert` entry at the top.
- `FE-AUDIT-008` [INFERRED] `"Ältere laden"` appears only when the last fetch returned a full
  page (200 rows) and loads the next older page, appending to the list.
- `FE-AUDIT-009` [INFERRED] `historyDialog(entity, id)` fetches that record's history
  (`entity`/`entity_id` filter, limit 500) and renders the same rows in a modal with a
  `"Schließen"` button; closing it refreshes the underlying view.

## Examples
- Rename an account from `X` to `Y` → the top audit row shows action `"Geändert"`, object
  `"Konto"` with the object label, and the diff `Name: X → Y`. Clicking `"Rückgängig"` and
  confirming restores `X` and adds a `"Rückgängig"` row referencing the update.

## Out of scope / not specified
- Exact timestamp formatting locale nuances.
- Pagination page-size beyond "200 per page, 500 in the per-record dialog".

## Open questions
None.
