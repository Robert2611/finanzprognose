# Frontend — form dialog & archive/restore helpers
ID prefix: FE-FORM
Layer: frontend

## Purpose
The one modal form component every create/edit action reuses. It renders a `<dialog>` with
typed fields, shows/hides fields by condition, validates required fields and money inputs
client-side, disables submit while saving, surfaces server errors inline, and resolves when
the user saves or cancels. `archiveDialog`/`restoreRow` are the shared archive/restore
actions built on it.

## Interface
Exported from `core.js`:
- `formDialog({title, fields, values?, submitLabel?, onSubmit, intro?}) -> Promise<result|null>`
  — opens a modal `<dialog>` (native `showModal`). Resolves to `onSubmit`'s return value on
  success, or `null` on cancel/close.
- `archiveDialog(table, row, label, notice?) -> Promise` — confirmation form (optional reason)
  that POSTs `/api/{table}/{id}/archive`; `notice` is an optional extra template below the intro.
- `restoreRow(table, row) -> Promise` — POSTs `/api/{table}/{id}/restore` (no dialog) and
  refreshes.
- `setArchived(table, row, archived) -> Promise<bool>` — POSTs archive/restore without a
  dialog; on an error it toasts the German message and resolves `false`.

**Field descriptor:** `{name, label, type?, options?, required?, showIf?, hint?, step?}`.
`type` ∈ (default text) `select`, `textarea`, `checkbox`, `money`, `number`, `date`, `text`.

**Stable DOM:** the dialog is a `<dialog>` appended to `<body>` and opened modally. Each
field is a `<label class="field" data-name="<name>">` containing a control with
`name="<name>"`; a `select` renders `<option>`s; the submit button has class `primary` and
text `submitLabel` (default `"Speichern"`); there is a `"Abbrechen"` button; validation/
server errors render in a `.err` container.

## Dependencies & side effects
Mutates the DOM (appends/removes a `<dialog>`). `onSubmit` typically calls `api()`
(network). `archiveDialog`/`restoreRow` call `api()` then `toast()` + `refresh()`.

## Behavior clauses

- `FE-FORM-001` [INFERRED] Calling `formDialog(...)` appends a `<dialog>` to the document
  and opens it modally; closing it (save/cancel/Esc) removes it from the DOM.
- `FE-FORM-002` [INFERRED] Each field renders a `label.field[data-name=<name>]` wrapping a
  control whose `name` attribute equals the field name; the label text is `field.label`,
  with a trailing ` *` when `required`.
- `FE-FORM-003` [INFERRED] `type:'select'` renders `<option>`s from `field.options`
  (`{value,label}`), preselecting the option matching the current value.
- `FE-FORM-004` [INFERRED] `type:'checkbox'` renders a checkbox reflecting the boolean value;
  `type:'textarea'` a textarea; `type:'money'`/default a text input.
- `FE-FORM-005` [INFERRED] A field with `showIf(values)` returning false is **not rendered**;
  changing another field re-evaluates `showIf` live and shows/hides it (e.g. "Zielkonto"
  appears only when type is "Umbuchung"; "Rhythmus" only when "Wiederkehrend").
- `FE-FORM-006` [INFERRED] Editing any field re-renders the form in place, preserving entered
  values (state is tracked, not read back from stale DOM).
- `FE-FORM-007` [INFERRED] On submit, a required field left empty blocks submission and shows
  `"Bitte „<label>“ ausfüllen."` in the `.err` area; no `onSubmit` call is made.
- `FE-FORM-008` [INFERRED] A `money` field with an unparseable value blocks submission with
  `"„<label>“ ist kein gültiger Betrag."`; a valid money field is converted to integer cents
  before `onSubmit`.
- `FE-FORM-009` [INFERRED] A hidden (`showIf` false) field is sent as `null` in the submitted
  values, not its stale entered value.
- `FE-FORM-010` [INFERRED] While `onSubmit` is in flight, the submit button is disabled
  (`busy`), preventing double submit.
- `FE-FORM-011` [INFERRED] If `onSubmit` throws (e.g. `api()` rejects with a server error),
  the dialog stays open, re-enables submit, and shows the thrown message in `.err`.
- `FE-FORM-012` [INFERRED] On successful `onSubmit`, the promise resolves with the return
  value and the dialog closes; a caller typically then shows a `"Gespeichert"` toast and
  refreshes.
- `FE-FORM-013` [INFERRED] Clicking `"Abbrechen"`, pressing Esc, or otherwise closing the
  dialog resolves the promise with `null` and makes no network call.
- `FE-FORM-014` [INFERRED] `archiveDialog(table,row,label)` shows an explanatory intro
  (archiving excludes the record from the forecast, nothing is deleted, restorable), an
  optional `"Grund (optional)"` reason field, and on confirm POSTs the archive endpoint,
  then toasts `"Archiviert"` and refreshes.
- `FE-FORM-015` [INFERRED] `restoreRow(table,row)` POSTs the restore endpoint without a
  dialog, toasts `"Wiederhergestellt"`, and refreshes.
- `FE-FORM-016` [README] Every archive/restore request from the frontend (`archiveDialog`,
  `restoreRow`, `setArchived`, including adjustments) sends the row's `updated_at` as
  `expected_updated_at` (B-017). A `409` shows the conflict message (`ERROR_CODES.conflict`):
  inside the archive dialog as its error, otherwise as an error toast, and the view reloads.

## Examples
- `formDialog({title:'Neues Konto', fields:[{name:'name',label:'Name',required:true}],
  onSubmit})` → modal with a `label.field[data-name="name"] > input[name="name"]`, a
  `"Speichern"` primary button, and a `"Abbrechen"` button. Submitting empty shows
  `"Bitte „Name“ ausfüllen."`.

## Out of scope / not specified
- Exact modal styling/animation.
- Keyboard focus order within the dialog.

## Open questions
- OPEN_QUESTIONS #14 (no `data-testid`; selectors rely on `data-name`, `name`, button text).
