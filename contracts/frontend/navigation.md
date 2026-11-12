# Frontend — navigation, routing & shell
ID prefix: FE-NAV
Layer: frontend

## Purpose
The app shell: a fixed header with five nav buttons and a backup status pill, a `#main`
content area, and hash-based routing that swaps views without a page reload. It also loads
the app state once at startup and re-renders on navigation, and shows a top-level error
banner if a view fails.

## Interface
Static page `index.html` (served at `/`). Stable DOM anchors (the main selectors a browser
test can rely on):
- `header` with `.brand` text `"Finanzprognose"`.
- `nav#nav` containing five `<button data-view=…>`: `prognose` ("Prognose"),
  `buchungen` ("Buchungen"), `konten` ("Konten & Ist-Stände"), `verlauf` ("Verlauf"),
  `sicherung` ("Sicherung").
- `button#backupPill.pill` (also `data-view="sicherung"`).
- `main#main` — the view container.
- `div#toast` — transient toast messages.

Routing exports (from `core.js`): `setView(v)`, `render()`, `load()`, `refresh()`.
`load()` fetches `/api/state` into the in-memory state `S`.

## Dependencies & side effects
`load()` calls `GET /api/state`. Clicking a `[data-view]` element sets `location.hash` and
re-renders. The active view maps: `prognose→forecast`, `buchungen→entries`,
`konten→accounts`, `verlauf→audit`, `sicherung→backup` (unknown → forecast).

## Behavior clauses

- `FE-NAV-001` [INFERRED] On load, the app fetches `/api/state`, renders the initial view
  (from `location.hash`, default `prognose`), and starts the backup-pill refresh.
- `FE-NAV-002` [INFERRED] The header always shows the five nav buttons with the exact German
  labels listed above, plus the backup pill.
- `FE-NAV-003` [INFERRED] Clicking a nav button sets `location.hash` to its `data-view` and
  renders the corresponding view into `#main`.
- `FE-NAV-004` [INFERRED] The nav button whose `data-view` equals the current view has the
  `active` class; others do not.
- `FE-NAV-005` [INFERRED] Changing `location.hash` (back/forward or manual) switches the
  view to match the hash.
- `FE-NAV-006` [INFERRED] An unknown/empty hash renders the forecast ("Prognose") view.
- `FE-NAV-007` [INFERRED] If a view's render throws, `#main` shows a `.banner.err` with the
  error message instead of crashing the shell.
- `FE-NAV-008` [INFERRED] If the initial `/api/state` load fails (backend down), `#main`
  shows a `.banner.err` with the error message.
- `FE-NAV-009` [INFERRED] `refresh()` reloads state, re-renders the current view, and updates
  the backup pill — used after any create/edit/archive/restore so the UI reflects the change
  without a manual reload.
- `FE-NAV-010` [INFERRED] The backup pill is itself a nav control (`data-view="sicherung"`):
  clicking it opens the backup view.

## Examples
- Load `/#konten` → the "Konten & Ist-Stände" view renders and its nav button is `active`.
- Backend stopped, open `/` → `#main` contains a `.banner.err`.

## Out of scope / not specified
- Scroll position retention across view switches.
- Deep-linking into a specific record (there are no per-record routes).

## Open questions
None.
