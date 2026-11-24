# Frontend — Version view and update pill
ID prefix: FE-UPDATE
Layer: frontend

## Purpose
Shows the running version and what the update service on the server reports, and starts an
update with one click (B-026). Module `update.js`; German texts for the codes in `core.js`.

## Interface
- Nav button `data-view="version"` ("Version"), view heading "Version".
- `button#updatePill.pill` (`data-view="version"`) in the header; `updatePillState(status)`
  (export of `update.js`) gives `{cls, text}` or `null`.

## Behavior clauses

- `FE-UPDATE-001` [README] The update pill is hidden unless: an update is running or requested
  ("Update läuft …", `warn`); the newest release failed to install
  ("Update auf vX fehlgeschlagen", `err`); or an update is available
  ("Update verfügbar: vX", `warn`). Clicking it opens the Version view.
- `FE-UPDATE-002` [README] The view shows "Laufende Version", and with host data "Neueste
  Version" (with the time of the check), "Aktualisierung" (the mode in German) and "Letztes
  Update" (`from → to`, the result in German, the time).
- `FE-UPDATE-003` [README] Not configured → a `.banner.warn` saying so; a `host_error` or
  `check_error` → a `.banner.warn` with its German text.
- `FE-UPDATE-004` [README] With an update available and nothing running, the button
  "Jetzt auf vX aktualisieren" asks in a dialog first; "Aktualisieren" sends
  `POST /api/update/request {version: latest}`, "Abbrechen" sends nothing.
- `FE-UPDATE-005` [README] After a request (or while one is pending or running) the view shows
  "Update läuft …" and polls the status, ignoring the moments the server is down; it reloads the
  page once the running version changed or the host finished the run.
- `FE-UPDATE-006` [README] If the last update did not succeed, a `.banner.err` names the version
  and the German result; when it was the newest release, the button reads
  "Erneut versuchen: vX".
- `FE-UPDATE-007` [INFERRED] The log tail is shown in a collapsed
  "Ausgabe des letzten Updates" section.
