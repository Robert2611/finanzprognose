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
  `"Letzte Sicherung fehlgeschlagen:"` followed by the German text of `last_error`
  (`FE-BACKUP-011`).
- `FE-BACKUP-004` [INFERRED] `"Jetzt sichern"` POSTs `/api/backup/run`, then toasts the
  outcome: `"Sicherung erstellt"` (ok), `"Keine Änderungen seit der letzten Sicherung"`
  (unchanged), or an error toast `"Sicherung fehlgeschlagen: <error>"`; the panel and pill
  refresh.
- `FE-BACKUP-010` [INFERRED] If the `POST /api/backup/run` request itself fails (HTTP error
  or network failure), the click is not silently swallowed: an error toast
  `"Sicherung fehlgeschlagen: <message>"` is shown and the panel and pill refresh.
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
- `FE-BACKUP-011` [README] Backup codes are shown in German (B-020): `marker_missing` →
  `"Datei <marker> fehlt im Backup-Ziel – ist das NAS eingebunden? Es wurde nichts
  gesichert."`, `backup_dir_missing` → `"Backup-Ziel <dir> existiert nicht."`,
  `integrity_failed` → `"Integritätsprüfung der Sicherung fehlgeschlagen: <result>"`,
  `backup_failed` → `"Unerwarteter Fehler: <detail>"`; an unknown code shows the code; a
  plain string (status from before B-020) shows as-is. The same text is used in the error
  toast of `"Jetzt sichern"`.
- `FE-BACKUP-012` [README] `"Letzter Versuch"` shows the reason after the time in brackets:
  `scheduled` → `Zeitplan`, `manual` → `manuell`, `retry` → `Wiederholung nach Fehler`
  (other values as-is).
- `FE-BACKUP-013` [README] Each row of the backups list has a `"Prüfen"` button. It opens a
  dialog `"Sicherung prüfen"` with the file name that loads `GET /api/backup/verify`. On
  `ok` it shows a `.banner.ok` `"In Ordnung – diese Sicherung ist vollständig lesbar und
  lässt sich wiederherstellen."`; otherwise a `.banner.err` `"Probleme gefunden:"` with one
  German line per problem code. Below: `Datenstand` (`Version <data_version> (laut
  Dateiname v<file_version>)`), `Schema-Version`, `Größe`, `Prüfsumme` (`stimmt mit
  backups.log überein` / `weicht von backups.log ab` / `nicht in backups.log eingetragen`)
  and the row counts (`Konten`, `Buchungen`, `Anpassungen`, `Ist-Stände`,
  `Protokolleinträge`). A note says only a copy is checked and points to the README for
  restoring. `"Schließen"` closes it.

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
