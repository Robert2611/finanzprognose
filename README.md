# Finanzprognose

Eine selbst gehostete Web-App, die dir zeigt, wie viel Geld du in den kommenden Monaten haben wirst. Sie ersetzt das Excel-Sheet.

## Was die App kann

| Bereich | Funktion |
|---|---|
| **Konten** | Beliebig viele Konten (Giro, Tagesgeld, Depot …). Ein Konto lässt sich als **Rücklage** markieren: Geld für Unvorhergesehenes, das nicht verplant wird. |
| **Wiederkehrende Buchungen** | Einnahmen, Ausgaben und Umbuchungen zwischen Konten, die regelmäßig wiederkommen (monatlich, quartalsweise, jährlich …), mit Start- und optionalem Enddatum. Eigene Seite „Wiederkehrend“. |
| **Einmalige Buchungen** | Einzelne Zahlungen auf ein Konto oder von einem Konto weg (z. B. Steuererstattung, Urlaub, neue Waschmaschine) und einzelne Umbuchungen, mit einem Datum. Eigene Seite „Einmalig“ mit eigenem, kürzerem Formular. |
| **Anpassungen** | Änderungen ab einem Stichtag: neuer fester Betrag (z. B. Gehaltserhöhung) oder ein Prozentsatz, einmalig oder jedes Jahr erneut (z. B. Inflation) |
| **Ist-Stände** | Du trägst ab und zu den echten Kontostand ein. Die Prognose rechnet ab dort mit dem echten Wert weiter und zeigt dir, wie weit sie danebenlag. |
| **Prognose** | Diagramm und Monatstabelle. Ein Klick auf einen Monat zeigt jede einzelne Buchung, und zu jedem Betrag steht, wie er zustande kommt. |

### Nachvollziehbarkeit: Warum ist ein Wert so, wie er ist?

In der Monatsansicht steht zu jeder Buchung, wie ihr Betrag entsteht:

```
15.07.  Lebensmittel                                −615,00 €
        ↳ Grundbetrag −600,00 €
        ↳ ab 01.01.2027: +2,5 %, jährlich – hier 1× angewendet → −615,00 € (Inflation)
        ↳ Kontostand danach: 10.873,00 €
```

Bei Ist-Ständen siehst du den prognostizierten Wert, den tatsächlichen Wert und die Abweichung. Ein Klick auf eine Buchung öffnet sie zum Bearbeiten.

### Feste und geschätzte Beträge

Nicht jede Ausgabe ist eine feste Abbuchung. Für Lebensmittel, Tanken oder Freizeit trägst du einfach einen Schätzwert als wiederkehrende Buchung ein (z. B. „ca. 450 € im Monat“) und stellst bei **Art** auf **Geschätzt**. Solche Beträge werden mit „≈“ angezeigt, und die Monatsansicht zeigt, wie viel der Einnahmen und Ausgaben geschätzt ist. Einzelne Einkäufe musst du nicht erfassen: Der nächste Ist-Stand gleicht die Schätzung mit der Wirklichkeit ab und zeigt die Abweichung. Unter „Gruppieren nach → Art“ siehst du feste und geschätzte Buchungen getrennt.

### Rücklagen: Geld, das nicht verplant wird

Ein Notgroschen oder eine Reserve für Unvorhergesehenes soll nicht in die Planung einfließen. Setze beim Konto den Haken **Rücklage – nicht zum Verplanen**. Sobald es mindestens ein solches Konto gibt, zeigt die Prognose als Hauptwert das **verfügbare Geld** (alle anderen Konten): Diagramm-Hauptlinie und fette Tabellenspalte heißen „Verfügbar“, der Gesamtstand steht daneben. In der Monatsansicht steht, wie viel in die Rücklage gelegt („In Rücklage gelegt“) oder daraus entnommen wurde („Aus Rücklage entnommen“), und die Warnung vor einem negativen Stand bezieht sich auf das verfügbare Geld. Ohne Rücklage-Konten bleibt alles wie gewohnt.

### Datensicherheit

1. **Nichts wird gelöscht.** Datensätze lassen sich nur archivieren und jederzeit wiederherstellen. Die Datenbank selbst verbietet `DELETE` per Trigger.
2. **Lückenloses Änderungsprotokoll.** Jede Änderung wird mit Vorher- und Nachher-Zustand gespeichert, in derselben Transaktion wie die Änderung. Das Protokoll ist per Trigger unveränderlich. Jede einzelne Änderung lässt sich unter „Verlauf“ rückgängig machen. Auch das Rückgängigmachen wird protokolliert.
3. **Kein stilles Überschreiben.** Wurde ein Datensatz inzwischen woanders geändert (z. B. in einem zweiten Browser-Tab), lehnt die App das Speichern ab, statt die andere Änderung zu überschreiben.
4. **Beträge in ganzen Cent.** Dadurch entstehen keine Rundungsfehler durch Gleitkommazahlen.
5. **SQLite mit WAL und `synchronous=FULL`.** Jede gespeicherte Änderung steht sofort auf der Platte.
6. **Tägliche Sicherung aufs NAS** (Details siehe unten).
7. **Passwortschutz** per HTTP Basic Auth.

## Sicherung aufs NAS

- Läuft täglich um `BACKUP_TIME` (Standard 03:00). Unter „Sicherung“ kannst du sie auch per Knopf auslösen.
- Es wird **nur gesichert, wenn sich seit der letzten Sicherung etwas geändert hat.**
- **Alte Stände werden nie gelöscht.** Jede Sicherung ist eine neue Datei:
  - `finanzen_2026-11-08_030000_v57.sqlite`: vollständige Datenbank, auf Integrität geprüft
  - `finanzen_2026-11-08_030000_v57.json`: dieselben Daten als lesbares JSON, unabhängig von der App
  - `backups.log`: Liste aller Sicherungen mit SHA-256-Prüfsumme
- Dateien werden erst unter einem temporären Namen geschrieben und dann umbenannt. Ein Abbruch hinterlässt also nie eine halbe Sicherung.
- **Schutz gegen ein nicht eingebundenes NAS:** Im Zielordner muss die Datei `.nas-marker` liegen. Fehlt sie, wird nichts gesichert und die App zeigt oben rechts rot „Sicherung fehlgeschlagen!“ an. Sonst würden die Sicherungen unbemerkt auf der lokalen Platte landen, wenn das NAS einmal nicht eingebunden ist.
- Nach einem Fehler versucht die App es stündlich erneut. Startet die App nach `BACKUP_TIME` (z. B. nach einem Neustart oder Update), holt sie die Sicherung des Tages sofort nach.
- **Backup prüfen:** Unter „Sicherung“ hat jede Datei einen Knopf **Prüfen**. Er prüft eine Kopie der Sicherung (Integrität, Datenstand, Prüfsumme aus `backups.log`) und zeigt, wie viele Konten, Buchungen usw. darin stecken. Die Sicherung selbst und die laufende Datenbank werden dabei nicht verändert.

---

## Installation auf Proxmox

Empfohlener Aufbau: **Debian-VM mit Docker.** Ein einziges Skript (`install.sh`) richtet alles in der VM ein: Docker, die NAS-Freigabe für die Sicherungen, die Einstellungen und die App selbst. Updates spielt danach `update.sh` ein.

Die App kommt als fertiges Docker-Image aus GitHub (`ghcr.io/robert2611/finanzprognose`). Es wird bei jedem GitHub-Release automatisch gebaut. Auf dem Server wird nichts kompiliert, und es liegt dort kein Quellcode.

### 1. NAS-Freigabe vorbereiten

Lege auf dem NAS eine Freigabe an, z. B. `finanzbackup`, und einen Benutzer mit Schreibrecht darauf.

- **SMB:** Benutzername und Passwort fragt `install.sh` ab.
- **NFS:** Gib die Freigabe für die IP der VM frei. Stelle die Benutzerzuordnung (squash) so ein, dass alle Zugriffe auf einen NAS-Benutzer mit Schreibrecht abgebildet werden („Map all users to admin“ bzw. `all_squash`).

### 2. VM anlegen

Lege in der Proxmox-Oberfläche eine VM an:

- ISO: **Debian 13** (netinst), Debian 12 geht auch
- 1 CPU, 1 GB RAM, 10 GB Platte
- unter *Optionen* den **QEMU Guest Agent** einschalten
- bei der Debian-Installation nur „SSH-Server“ und „Standard-Systemwerkzeuge“ auswählen

Gib der VM eine feste IP-Adresse (oder eine feste DHCP-Zuweisung im Router), damit die App immer unter derselben Adresse erreichbar ist.

### 3. GitHub-Token anlegen

Das Image ist privat. Die VM braucht deshalb ein Token zum Herunterladen:

1. GitHub → *Settings → Developer settings → Personal access tokens → Tokens (classic)* → *Generate new token (classic)*
2. Nur den Haken bei **`read:packages`** setzen. Mehr Rechte braucht die VM nicht.
3. Ein Ablaufdatum wählen und das Token sicher aufheben.

Ist das Token abgelaufen, schlägt `update.sh` mit einem Hinweis fehl. Dann ein neues Token anlegen und in der VM `sudo docker login ghcr.io -u DEIN_GITHUB_NAME` ausführen (das Token als Passwort eingeben).

### 4. `install.sh` ausführen

Lade `install.sh` von der [Release-Seite](https://github.com/Robert2611/finanzprognose/releases/latest) herunter (unter *Assets*) und kopiere es in die VM:

```bash
scp install.sh BENUTZER@IP-DER-VM:
ssh BENUTZER@IP-DER-VM
sudo bash install.sh            # neueste Version
# oder: sudo bash install.sh v1.4.0
```

Das Skript fragt nacheinander ab:

- GitHub-Benutzername und das Token aus Schritt 3
- wie das NAS erreicht wird (`smb`, `nfs` oder `manual`, falls du es selbst eingebunden hast), dazu Adresse, Freigabe und ggf. Zugangsdaten
- Port (Standard 8080), Benutzername und Passwort für die App (leer lassen = Passwort erzeugen), Uhrzeit der täglichen Sicherung
- ob neue Versionen automatisch installiert (`auto`) oder nur in der App angezeigt werden (`notify`), siehe [Updates](#updates)

Danach liegt alles in `/opt/finanzprognose`:

| Pfad | Inhalt |
|---|---|
| `.env` | deine Einstellungen (nur für root lesbar) |
| `data/` | die Datenbank |
| `data/pre-update/` | Kopien der Datenbank vor jedem Update |
| `data/failed-update_DATUM/` | die Datenbank eines fehlgeschlagenen automatischen Updates (nach dem Zurückrollen) |
| `updater/` | Austausch mit der App: Status des Update-Dienstes, Update-Anfragen, Ausgabe des letzten Updates |
| `docker-compose.yml`, `update.sh`, `install.sh`, `auto-update.sh` | kommen aus dem Image und werden bei jedem Update ersetzt, nicht von Hand ändern |

Die NAS-Freigabe ist unter `/mnt/nas-finanzen` eingebunden (Eintrag in `/etc/fstab`), die Sicherungen landen in `/mnt/nas-finanzen/finanzprognose`. Dort legt das Skript auch die Datei `.nas-marker` an.

Außerdem schaltet das Skript die automatischen Sicherheitsupdates von Debian (`unattended-upgrades`) und die Begrenzung der Docker-Logs ein.

### 5. Ausprobieren

Öffne `http://IP-DER-VM:8080` im Browser. Geh einmal auf **Sicherung → Jetzt sichern** und prüfe, ob auf dem NAS eine Datei ankommt.

Du kannst `install.sh` jederzeit erneut ausführen, z. B. um Passwort oder NAS zu ändern. Es fragt, ob die bisherigen Einstellungen bleiben sollen, und lässt die Daten unangetastet.

### Updates

Neue Versionen kommen von selbst auf den Server: Der systemd-Timer `finanzprognose-update.timer` schaut alle 15 Minuten auf ghcr.io nach, ob es ein neues Release gibt. Der Server muss dafür nur nach außen ins Internet kommen, von außen erreichbar sein muss er nicht. Was passiert, steuert `AUTO_UPDATE` in `.env`:

- `AUTO_UPDATE=auto` (Standard): Ein neues Release wird automatisch installiert, spätestens etwa 15 Minuten nach dem Veröffentlichen.
- `AUTO_UPDATE=notify`: Das neue Release wird nur angezeigt. Installiert wird es erst, wenn du in der App auf **Version → Jetzt aktualisieren** klickst.

In der App zeigt die Seite **Version** die laufende und die neueste Version, ob gerade ein Update läuft, wie das letzte ausgegangen ist und dessen Ausgabe. Gibt es ein Update oder ist eins fehlgeschlagen, erscheint oben rechts ein Hinweis. Mit **Jetzt aktualisieren** startet das Update sofort; die Seite lädt neu, sobald die neue Version läuft.

Die App installiert dabei nichts selbst. Sie legt nur eine Anfrage in `updater/` ab, und den Rest erledigt `auto-update.sh` auf dem Server (gestartet von `finanzprognose-update.path`). Startet eine neue Version nicht, rollt das Skript selbst zurück: Es legt die Datenbank der neuen Version nach `data/failed-update_DATUM/`, holt die Kopie von vor dem Update zurück und startet wieder die alte Version. Dieses Release wird danach nicht mehr automatisch versucht; das nächste Release schon, und mit **Erneut versuchen** auch dieses.

Von Hand geht es weiterhin so:

```bash
sudo /opt/finanzprognose/update.sh            # neueste Version
sudo /opt/finanzprognose/update.sh v1.4.0     # eine bestimmte Version
sudo systemctl start finanzprognose-update    # jetzt nach Updates suchen (wie der Timer)
journalctl -u finanzprognose-update           # was der Update-Dienst gemacht hat
```

`update.sh`

1. lädt das neue Image herunter (ist schon die neueste Version installiert, hört es hier auf),
2. hält die App an und kopiert die Datenbank nach `data/pre-update/DATUM_ALTEVERSION/`,
3. übernimmt die neuen `docker-compose.yml`, `update.sh`, `install.sh` und `auto-update.sh` aus dem Image und richtet die Timer ein,
4. trägt die neue Version in `.env` ein, startet die App und wartet, bis sie läuft.

Die Kopien in `data/pre-update/` werden nie gelöscht. Wenn der Platz knapp wird, kannst du alte Kopien von Hand entfernen.

Vor großen Updates lohnt sich zusätzlich ein **Snapshot der VM** in Proxmox. Damit dir das automatische Update nicht zuvorkommt, setze vorher `AUTO_UPDATE=notify` in `.env`; der Timer liest die Datei bei jedem Lauf neu, ein Neustart ist nicht nötig.

### Zurückrollen

Neue Versionen können die Datenbank umbauen (Migration). Eine ältere Version kann eine umgebaute Datenbank nicht immer lesen. Zum Zurückrollen gehören deshalb **beide Schritte**: die Datenbank-Kopie von vor dem Update zurückholen und die alte Version starten. Startet die neue Version nicht, macht das automatische Update das selbst (siehe oben). Schlägt ein Update von Hand fehl, zeigt `update.sh` die passenden Befehle mit den richtigen Pfaden an. Allgemein:

```bash
cd /opt/finanzprognose
sudo docker compose stop
sudo mkdir -p data/verworfen && sudo mv data/finanzen.sqlite* data/verworfen/   # aktuellen Stand aufheben (inkl. -wal/-shm!)
sudo cp -p data/pre-update/2026-11-13_201500_v1.3.0/finanzen.sqlite* data/
sudo ./update.sh v1.3.0
```

Alles, was du nach dem Update eingetragen hast, fehlt danach. Es steht aber noch in `data/verworfen/`.

### Umzug von einer bisherigen LXC-Installation

1. Im alten Container: `cd /opt/finanzprognose && docker compose stop`
2. In der neuen VM `install.sh` ausführen (Schritte 1–5). Dabei kannst du dieselbe NAS-Freigabe verwenden.
3. Datenbank übernehmen:

   ```bash
   # in der VM
   cd /opt/finanzprognose
   sudo docker compose stop
   sudo mkdir -p data/leer && sudo mv data/finanzen.sqlite* data/leer/
   # alte Datenbank (inkl. finanzen.sqlite-wal/-shm, falls vorhanden) aus dem LXC nach data/ kopieren, z. B. per scp
   sudo docker compose start
   ```

4. Im Browser prüfen, ob alle Konten da sind. Danach den alten Container abschalten.

---

## Wiederherstellen aus einer Sicherung

Prüfe die gewünschte Sicherung vorher unter „Sicherung → Prüfen“. Das Zurückspielen selbst ist bewusst ein Handgriff auf dem Server, damit nichts in der App versehentlich die Daten ersetzen kann.

```bash
cd /opt/finanzprognose
sudo docker compose stop
sudo mkdir -p data/alt && sudo mv data/finanzen.sqlite* data/alt/       # aktuellen Stand aufheben (inkl. -wal/-shm!)
sudo cp /mnt/nas-finanzen/finanzprognose/finanzen_2026-11-08_030000_v57.sqlite data/finanzen.sqlite
sudo docker compose start
```

Du musst nicht immer den ganzen Stand zurückholen. Für einzelne Fehler reicht meist **Verlauf → Rückgängig**.

## Zusätzlicher Schutz (empfohlen)

- **Snapshots auf dem NAS** für die Backup-Freigabe aktivieren, z. B. Synology Snapshot Replication oder ZFS-Snapshots. Die App hat Schreibzugriff auf den Backup-Ordner. Schreibgeschützte Snapshots schützen die Sicherungen auch dann, wenn der Server kompromittiert wird.
- **Proxmox-Backup (vzdump)** der VM einplanen.
- Die App **nicht ins Internet freigeben.** Für den Zugriff von unterwegs besser ein VPN wie WireGuard oder Tailscale nutzen.

## Bedienung in Kürze

1. **Konto anlegen** mit aktuellem Kontostand und Datum. Dieser Stand ist der Startpunkt der Prognose.
2. **Buchungen eintragen:** unter „Wiederkehrend“ Gehalt, Miete, Versicherungen, Abos, Sparraten (als Umbuchung); unter „Einmalig“ geplante Einzelausgaben und -einnahmen. In der Prognose legst du beides mit „+ Wiederkehrend“ bzw. „+ Einmalig“ an.
3. **Änderungen ab einem Datum** legst du über „Anpassungen“ an, nicht durch Ändern des Grundbetrags. Eine Änderung am Grundbetrag wirkt rückwirkend auf alle Termine.
4. Trage ab und zu (z. B. monatlich) einen **Ist-Stand** ein. So bleibt die Prognose an der Realität ausgerichtet, und du siehst, wie genau sie war.

Regeln der Berechnung:

- Ein Ist-Stand ist der Kontostand **am Abend** des Tages. Buchungen am selben Tag gelten als darin enthalten.
- Fällt ein Termin auf den 31. und der Monat ist kürzer, wird der Monatsletzte genommen.
- Anpassungen werden in zeitlicher Reihenfolge angewendet. Ein neuer fester Betrag ersetzt alle früheren Anpassungen.

## Entwicklung und Tests

Empfohlen ist ein **Dev-Container** (VS Code mit der Erweiterung „Dev Containers“ und Docker):

1. Ordner in VS Code öffnen und **„Reopen in Container“** wählen. Der Container bringt Python 3.12, installiert die Abhängigkeiten (`requirements-dev.txt`) und legt `data/backup` an.
2. **F5** startet die App („Finanzprognose (dev)“, ohne Passwort). VS Code leitet Port 8000 weiter: `http://localhost:8000`. Haltepunkte funktionieren. Die Variante „with login“ startet die App mit Passwort `dev`.
3. Die Tests laufen im Testing-Panel von VS Code oder mit `pytest -q`.

**Claude Code im Dev-Container:** Die CLI (`claude`) und die VS-Code-Erweiterung sind im Container vorinstalliert. Beim ersten Mal im Terminal `claude` starten und im Browser anmelden (öffnet sich kein Browser, die angezeigte Login-URL manuell öffnen und den Code ins Terminal einfügen). Die Anmeldung und Einstellungen liegen im Docker-Volume `finanzprognose-claude-config` und bleiben bei „Rebuild Container“ erhalten. Zum Zurücksetzen das Volume löschen (`docker volume rm finanzprognose-claude-config`).

Die Entwicklungsdaten liegen in `./data` und sind nicht im Git. Der Dev-Container setzt `BACKUP_REQUIRE_MARKER=0`, damit die Sicherung auch ohne NAS-Markierungsdatei läuft.

Ohne Dev-Container: Python 3.12, `pip install -r requirements-dev.txt`, dann `mkdir -p data/backup` und
`DB_PATH=./data/finanzen.sqlite BACKUP_DIR=./data/backup BACKUP_REQUIRE_MARKER=0 APP_PASSWORD= uvicorn app.main:app`.

Die API-Dokumentation findest du unter `/api/docs`.

### Release erstellen

1. Änderungen per Pull Request in `main` mergen (`main` ist geschützt, direkte Pushes sind nicht möglich).
2. Auf GitHub unter *Releases → Draft a new release* einen neuen Tag im Format `vX.Y.Z` anlegen (z. B. `v1.4.0`), Release-Notizen schreiben und veröffentlichen.
3. Der Workflow `.github/workflows/release.yml` führt die Tests aus, baut das Image, lädt es als `ghcr.io/robert2611/finanzprognose:vX.Y.Z` und `:latest` hoch und hängt `install.sh` an das Release.
4. Der Server installiert es innerhalb von etwa 15 Minuten selbst (bei `AUTO_UPDATE=notify` nach einem Klick auf **Version → Jetzt aktualisieren**).

Ein Release mit dem Haken **„Set as a pre-release“** (z. B. `v1.4.0-rc1`) bekommt kein `latest`. Es lässt sich gezielt mit `update.sh v1.4.0-rc1` testen, ohne dass `update.sh` ohne Versionsangabe oder das automatische Update es installiert.

Das Image lokal bauen und mit der Produktions-Compose-Datei starten (braucht eine `.env` im Projektordner, siehe `.env.example`; der Ordner aus `BACKUP_HOST_DIR` muss eine `.nas-marker` enthalten):

```bash
docker build -t ghcr.io/robert2611/finanzprognose:dev . && APP_VERSION=dev docker compose --project-directory . -f deploy/docker-compose.yml up -d
```
