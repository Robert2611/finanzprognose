# Frontend — backup view ("Sicherung") & status pill
ID prefix: FE-BACKUP
Layer: frontend

## Purpose
Shows backup health, lets the user trigger a backup and download a JSON export, and lists
existing backups. A small status pill in the header reflects backup state on every screen
and refreshes periodically.

## Interface
Rendered into `#main` when view = `sicherung`. Fetches `GET /api/backup/status`. Stable DOM:
- Heading `"Sicherung"`; a `.banner.err` when the last result was an error.
- A status `.kv` block: `Ziel` (a `<code>` of the backup dir), `Zeitplan`
  (`"täglich um <time> Uhr, nur bei Änderungen"`), `"Letzte erfolgreiche"`,
  `"Letzte Datei"`, `"Letzter Versuch"` (+ a result word), `"Datenstand"`
  (`Version <n>` with `"ungesicherte Änderungen"` / `"gesichert"`).
- A `"Jetzt sichern"` primary button and an `"Export als JSON herunterladen"` link to
  `/api/export`.
- A `"Vorhandene Sicherungen (neueste 30)"` panel: a table of `name` + size in KB, or
  `"Keine Sicherungen gefunden."`.

Header pill: `button#backupPill.pill` with class `ok`/`warn`/`err` and status text.

## Dependencies & side effects
`GET /api/backup/status`, `POST /api/backup/run`, link to `GET /api/export`. The pill polls
status on an interval and after actions.

## Behavior clauses

- `FE-BACKUP-001` [INFERRED] The view shows `Ziel` (backup dir), the schedule text, last
  success/attempt, last file, and the data version with a secured/unsecured indicator, all
  from `GET /api/backup/status`.
- `FE-BACKUP-002` [INFERRED] The `"Letzter Versuch"` result is rendered in German:
  `erfolgreich` (ok), `"keine Änderungen – nichts zu sichern"` (unchanged), or `FEHLER`
  (error).
- `FE-BACKUP-003` [README] When the last result was an error, a red `.banner.err` shows
  `"Letzte Sicherung fehlgeschlagen:"` followed by the server `last_error`.
- `FE-BACKUP-004` [INFERRED] `"Jetzt sichern"` POSTs `/api/backup/run`, then toasts the
  outcome: `"Sicherung erstellt"` (ok), `"Keine Änderungen seit der letzten Sicherung"`
  (unchanged), or an error toast `"Sicherung fehlgeschlagen: <error>"`; the panel and pill
  refresh.
- `FE-BACKUP-005` [INFERRED] The existing-backups panel lists up to 30 files (name + size in
  KB) newest-first, or `"Keine Sicherungen gefunden."` when empty.
- `FE-BACKUP-006` [INFERRED] `"Export als JSON herunterladen"` is a link to `/api/export`
  (downloads the JSON attachment).
- `FE-BACKUP-007` [README] The header pill reflects status: class/text `ok`
  (`"Gesichert <time>"`, with `" · neue Änderungen"` when pending), `warn`
  (`"Noch keine Sicherung"`), or `err` (`"Sicherung fehlgeschlagen!"`).
- `FE-BACKUP-008` [INFERRED] If `GET /api/backup/status` itself fails (server unreachable),
  the pill shows `err` with `"Server nicht erreichbar"`.
- `FE-BACKUP-009` [INFERRED] The pill refreshes on a periodic interval and after a manual
  backup run.

## Examples
- Marker missing, run backup → error toast + red banner with the `.nas-marker` message +
  pill `"Sicherung fehlgeschlagen!"`.
- Marker present, pending change, run backup → `"Sicherung erstellt"` toast, the new file
  appears in the list, pill turns `ok`.

## Out of scope / not specified
- The exact pill refresh interval value.
- Whether the export download is intercepted or navigates (it is a plain link).

## Open questions
None.
