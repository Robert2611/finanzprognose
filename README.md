# Finanzprognose

Eine selbst gehostete Web-App, die dir zeigt, wie viel Geld du in den kommenden Monaten haben wirst. Sie ersetzt das Excel-Sheet.

## Was die App kann

| Bereich | Funktion |
|---|---|
| **Konten** | Beliebig viele Konten (Giro, Tagesgeld, Depot …) |
| **Buchungen** | Einnahmen, Ausgaben und Umbuchungen zwischen Konten, wiederkehrend (monatlich, quartalsweise, jährlich …) oder einmalig, mit Start- und Enddatum |
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
- Nach einem Fehler versucht die App es stündlich erneut.

---

## Installation auf Proxmox

Empfohlener Aufbau: **Debian-LXC mit Docker.** Die NAS-Freigabe wird auf dem Proxmox-Host eingebunden und per Bind-Mount in den Container gereicht. Unprivilegierte LXC-Container können NFS oder SMB nicht selbst einbinden.

### 1. NAS-Freigabe auf dem Proxmox-Host einbinden

Lege auf dem NAS eine Freigabe an, z. B. `finanzbackup`.

Unprivilegierte LXC-Container sehen Dateien als Benutzer **100000** des Hosts. Diese Benutzerkennung braucht Schreibrechte.

**Variante SMB/CIFS** (auf dem Proxmox-Host als root):

```bash
apt install -y cifs-utils
mkdir -p /mnt/nas-finanzen
cat > /root/.smb-nas <<'EOF'
username=DEIN_NAS_BENUTZER
password=DEIN_NAS_PASSWORT
EOF
chmod 600 /root/.smb-nas

echo '//NAS-IP/finanzbackup /mnt/nas-finanzen cifs credentials=/root/.smb-nas,uid=100000,gid=100000,file_mode=0660,dir_mode=0770,_netdev,nofail 0 0' >> /etc/fstab
mount /mnt/nas-finanzen
```

**Variante NFS:** Gib die Freigabe auf dem NAS für die IP des Proxmox-Hosts frei. Stelle die Benutzerzuordnung (squash) so ein, dass alle Zugriffe auf einen NAS-Benutzer mit Schreibrecht abgebildet werden („Map all users to admin“ bzw. `all_squash`). Danach:

```bash
mkdir -p /mnt/nas-finanzen
echo 'NAS-IP:/volume1/finanzbackup /mnt/nas-finanzen nfs defaults,_netdev,nofail 0 0' >> /etc/fstab
mount /mnt/nas-finanzen
```

Lege dann den Zielordner und die Markierungsdatei an:

```bash
mkdir -p /mnt/nas-finanzen/finanzprognose
touch /mnt/nas-finanzen/finanzprognose/.nas-marker
```

### 2. LXC-Container anlegen

Lege in der Proxmox-Oberfläche einen Container aus dem Template **Debian 12** an, z. B. mit 1 CPU, 512 MB RAM und 4 GB Platte. Setze unter *Optionen → Features* den Haken bei **Nesting**, das braucht Docker. Danach auf dem Host:

```bash
# CTID durch die Nummer des Containers ersetzen
pct set CTID -mp0 /mnt/nas-finanzen/finanzprognose,mp=/mnt/nas-backup/finanzprognose
pct reboot CTID
```

### 3. Docker im Container installieren

```bash
pct enter CTID
apt update && apt install -y curl
curl -fsSL https://get.docker.com | sh
```

### 4. App starten

Kopiere den Ordner `finanzprognose` in den Container, z. B. nach `/opt/finanzprognose` (per `scp` oder `pct push`). Dann:

```bash
cd /opt/finanzprognose
cp .env.example .env
nano .env            # APP_PASSWORD setzen, BACKUP_HOST_DIR=/mnt/nas-backup/finanzprognose
docker compose up -d --build
```

Öffne `http://IP-DES-CONTAINERS:8080` im Browser. Geh einmal auf **Sicherung → Jetzt sichern** und prüfe, ob auf dem NAS eine Datei ankommt.

### Updates

```bash
cd /opt/finanzprognose
# neue Dateien einspielen, dann:
docker compose up -d --build
```

Deine Daten liegen in `./data` und bleiben bei Updates erhalten.

---

## Wiederherstellen aus einer Sicherung

```bash
cd /opt/finanzprognose
docker compose stop
mkdir -p data/alt && mv data/finanzen.sqlite* data/alt/       # aktuellen Stand aufheben (inkl. -wal/-shm!)
cp /mnt/nas-backup/finanzprognose/finanzen_2026-11-08_030000_v57.sqlite data/finanzen.sqlite
docker compose start
```

Du musst nicht immer den ganzen Stand zurückholen. Für einzelne Fehler reicht meist **Verlauf → Rückgängig**.

## Zusätzlicher Schutz (empfohlen)

- **Snapshots auf dem NAS** für die Backup-Freigabe aktivieren, z. B. Synology Snapshot Replication oder ZFS-Snapshots. Die App hat Schreibzugriff auf den Backup-Ordner. Schreibgeschützte Snapshots schützen die Sicherungen auch dann, wenn der Server kompromittiert wird.
- **Proxmox-Backup (vzdump)** des LXC-Containers einplanen.
- Die App **nicht ins Internet freigeben.** Für den Zugriff von unterwegs besser ein VPN wie WireGuard oder Tailscale nutzen.

## Bedienung in Kürze

1. **Konto anlegen** mit aktuellem Kontostand und Datum. Dieser Stand ist der Startpunkt der Prognose.
2. **Buchungen eintragen:** Gehalt, Miete, Versicherungen, Abos, Sparraten (als Umbuchung), geplante Einmalausgaben.
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

Die Entwicklungsdaten liegen in `./data` und sind nicht im Git. Der Dev-Container setzt `BACKUP_REQUIRE_MARKER=0`, damit die Sicherung auch ohne NAS-Markierungsdatei läuft.

Ohne Dev-Container: Python 3.12, `pip install -r requirements-dev.txt`, dann `mkdir -p data/backup` und
`DB_PATH=./data/finanzen.sqlite BACKUP_DIR=./data/backup BACKUP_REQUIRE_MARKER=0 APP_PASSWORD= uvicorn app.main:app`.

Die API-Dokumentation findest du unter `/api/docs`.
