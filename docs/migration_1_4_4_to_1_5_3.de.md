# Migration von 1.4.4 auf 1.5.3

Diese Migration führt Backend **1.4.4 auf 1.5.3**, SQLite-Schema **8 auf 11** und das Jobarchiv von **Format 2 auf 3**. Grundlage sind die [Release Notes](https://github.com/ClusterCockpit/cc-backend/blob/300108664774c5561b6838382876e247d0b043b9/ReleaseNotes.md). Für eine neue Installation ist dieser Schritt nicht nötig. Das anschließende [Update von 1.5.3 auf 1.5.4](updates.de.md) ist ein eigener Vorgang.

Die Befehle benötigen root, GNU tar mit ACL-/xattr-Unterstützung, Python 3, Perl mit `DBI` und `DBD::SQLite`, curl, Git, sudo und Go ≥1.25.0. Pfade und Dienstkonto `clustercockpit` müssen zur vorhandenen Installation passen. Der Ablauf gilt für SQLite; MySQL/MariaDB benötigt einen gesonderten Export- und Migrationsplan.

## Änderungen und Wartungsplanung

Ab 1.5.3 läuft der Store im Backend. Der alte separate Store wird beim Wechsel stillgelegt. Die Konfiguration ist in `main`, `auth`, `archive` und `metric-store` gegliedert; Clusterdefinitionen liegen im Jobarchiv.

Die Migration braucht ein Wartungsfenster. Zunächst setzt die Slurm-Administration neue Jobstarts aus. Laufende Jobs müssen beendet und ihre Messwerte im Archiv lesbar sein. Danach stoppen die vorhandene Scheduleranbindung einschließlich etwaiger Timer, Collectoren und weitere API-Schreiber. Backend und alter Store stoppen zuletzt.

**Der neue Store beginnt nach der Offline-Migration mit frischen Checkpoints.** Die alte Store-Konfiguration und ihre Checkpoints bleiben für den Rückweg im Backup.

## Neue Binaries getrennt vorbereiten

Die Vorbereitung beginnt im geklonten Guide und verändert die bestehende Installation nicht. Das neue Release und das passende Migrationstool liegen in einem eigenen Verzeichnis. Das Release enthält bereits das Webfrontend; Node.js ist für diesen Weg nicht nötig. Die SHA-256-Prüfung gleicht den Download mit der erwarteten Prüfsumme ab.

Unter Ubuntu/Debian stellt das folgende Paketkommando die Perl-Abhängigkeiten bereit:

```bash
apt-get install perl libdbi-perl libdbd-sqlite3-perl
```

```bash
set -eu
GUIDE_ROOT=$(pwd -P)
PREP=/opt/monitoring/prepare-1.5.3
test ! -e "$PREP" && test ! -L "$PREP"
install -d -o root -g clustercockpit -m 0750 "$PREP"
cd "$PREP"
curl --fail --location --max-time 120 -o backend.tar.gz https://github.com/ClusterCockpit/cc-backend/releases/download/v1.5.3/cc-backend_Linux_x86_64.tar.gz
printf '%s  backend.tar.gz\n' e3e1257e1f3b8063e8b9a90a155e184e12251d318a0451b09bbb07c87c0facfb | sha256sum -c -
mkdir release
tar -xzf backend.tar.gz -C release
test -x release/cc-backend
./release/cc-backend -version
git clone https://github.com/ClusterCockpit/cc-backend.git source
git -C source checkout --detach 300108664774c5561b6838382876e247d0b043b9
test "$(git -C source rev-parse HEAD)" = 300108664774c5561b6838382876e247d0b043b9
cd source/tools/archive-migration
GOTOOLCHAIN=local go build -o "$PREP/archive-migration" .
cd "$PREP"
```

`-version` muss 1.5.3 ausgeben. Die neue `$PREP/config.json` folgt der Struktur im [manuellen Installationskapitel](monitoringserver.de.md). Bestehende Cluster- und Archivpfade, LDAP-/JWT-Regeln und Ports werden dabei bewusst übernommen. `.env` und Signaturschlüssel bleiben erhalten. Das [RUB-Beispiel](examples/rub/cc-backend/config.json) zeigt die Struktur, enthält aber Standortwerte, die angepasst werden müssen.

`ui-file` verweist auf `ui-config.json`; als Ausgangspunkt dienen die [Standardwerte](examples/minimal/cc-backend/ui-config.json). Die Store-Konfiguration verwendet frische Checkpointpfade. Das Dienstkonto benötigt Zugriff auf `$PREP/archive-migration` und dessen übergeordnete Verzeichnisse.

Das RUB-Skript [updateUserconfig.pl](scripts/updateUserconfig.pl) benennt gespeicherte UI-Einstellungen anhand von [configmap_v11.json](scripts/configmap_v11.json) um. Werte und Cluster-/Subcluster-Zuordnungen bleiben erhalten. Die Guide-Fassung unterstützt wählbare Pfade und übernimmt die Schlüsseländerungen in einer Transaktion. UI-Datei, Skript und Zuordnungsdatei werden gemeinsam vorbereitet:

```bash
install -m 0600 "$GUIDE_ROOT/docs/examples/minimal/cc-backend/ui-config.json" "$PREP/ui-config.json"
install -o root -g clustercockpit -m 0640 "$GUIDE_ROOT/docs/scripts/updateUserconfig.pl" "$PREP/updateUserconfig.pl"
install -o root -g clustercockpit -m 0640 "$GUIDE_ROOT/docs/scripts/configmap_v11.json" "$PREP/configmap_v11.json"
```

Nach diesem Kopierschritt gehören vorhandene eigene UI-Anpassungen in `$PREP/ui-config.json`.

## Vollständiger konsistenter Offline-Backup-Satz

Die allgemeinen Regeln stehen unter [Backup und Wiederherstellung](backup_restore.de.md). Für diese Migration braucht das Inventar zusätzlich den alten Store und die alten Formatstände. Vor dem Stoppen ergibt sich die vollständige Pfadliste aus Konfigurationen, `.env`, Units/Drop-ins und Symlinks:

- Datenbank einschließlich vorhandener SQLite-Begleitdateien und vollständiges Jobarchiv.
- Backendbinary, Konfigurationen/UI und JWT-, Session- sowie weitere Schlüssel.
- Alter Store einschließlich Binary, Konfiguration, Checkpoints, Archiv und WAL.
- Units, Drop-ins, systemweite Environment-Dateien und Schlüssel.
- Collector-/Schedulerkonfigurationen und Tokenkopien für den Rückweg.

Verzeichnisbackups umfassen ihren Inhalt. Externe Datenbanken und andere ausgelagerte Pfade benötigen eigene Einträge. `systemctl cat` zeigt Units und Drop-ins, `find /opt/monitoring -type l -ls` die Symlinks. Externe Pfade aus Konfigurationswerten müssen zusätzlich ins Inventar.

Ein angepasstes `$PREP/backup-paths.json` kann beispielsweise so aussehen:

```json
{
  "paths": [
    "/opt/monitoring/cc-backend",
    "/opt/monitoring/job-archive",
    "/opt/monitoring/cc-metric-store",
    "/etc/systemd/system/clustercockpit.service",
    "/etc/systemd/system/cc-metric-store.service"
  ]
}
```

Das Inventar darf keine überlappenden Eltern-/Kindpfade, fehlenden Beispielpfade oder `/` als Quelle enthalten. Tatsächliche externe Symlinkziele und weitere Dateien oder Drop-in-Verzeichnisse gehören ausdrücklich hinein. Der [Backuphelper](scripts/cc-offline-backup.py) lehnt fehlende Pfade und nicht inventarisierte externe Symlinkziele ab. Er findet keine externen Pfade automatisch in Konfigurationswerten; das vollständige Inventar bleibt Aufgabe des Betriebs.

Das Backupziel muss neu sein, außerhalb aller Quellen liegen und genügend Platz bieten. GNU tar sichert ACLs, xattrs und Eigentümer; deren Wiederherstellung erfolgt als root. Während der Sicherung dürfen keine Schreiber mehr laufen.

Nach Abschluss aller Jobs und Stoppen von Collectoren, Scheduleranbindung und anderen Schreibern folgen Backend und alter Store:

```bash
systemctl stop clustercockpit.service cc-metric-store.service
```

```bash
umask 077
BACKUP=/opt/monitoring/backup-before-1.5.3
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" snapshot \
  --database /opt/monitoring/cc-backend/var/job.db \
  --archive /opt/monitoring/job-archive --record "$PREP/before.json" \
  --db-version 8 --archive-version 2
python3 "$GUIDE_ROOT/docs/scripts/cc-offline-backup.py" backup \
  --inventory "$PREP/backup-paths.json" --destination "$BACKUP"
python3 "$GUIDE_ROOT/docs/scripts/cc-offline-backup.py" restore \
  --backup "$BACKUP" --destination "$PREP/restore-check"
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" verify \
  --database "$PREP/restore-check/opt/monitoring/cc-backend/var/job.db" \
  --archive "$PREP/restore-check/opt/monitoring/job-archive" \
  --record "$PREP/before.json" --db-version 8 --archive-version 2
```

Das Backupverzeichnis hat `0700`, Dateien entstehen unter `umask 077`. Backup, Inventar und `before.json` gehören gemeinsam auf ein geeignetes geschütztes Backupmedium. Eine erneute Prüfsummenprüfung dort bestätigt die Kopie.

Der [Migrationscheck](scripts/cc-migration-check.py) prüft Datenbankintegrität und Version, Jobanzahl, Identitäten und Ressourcen, Archivmetadaten einschließlich Exklusivitätsabbildung sowie alle `data.json`-Hashes. Externe Pfade werden unter dem Stagingverzeichnis anhand des Inventars geprüft. Absolute Symlinks zeigen dort weiterhin auf Originalziele; eine Restoreprobe darf diese nicht mit den gesicherten Daten verwechseln.

## Vorwärtsmigration

Erst nach erfolgreicher Backup- und Restoreprobe kommen die vorbereitete Konfiguration und das Binary zum Einsatz. Beispielkonto und Gruppen müssen zur Installation passen. `set -eu` bleibt aktiv; Toolausgaben sind auf Fehler zu prüfen. Die Bestätigungsfrage des Archivtools setzt die Prüfung dieser Voraussetzungen voraus.

```bash
set -eu
cd /opt/monitoring/cc-backend
install -o root -g root -m 0755 "$PREP/release/cc-backend" ./cc-backend
install -o clustercockpit -g clustercockpit -m 0600 "$PREP/config.json" ./config.json
install -o clustercockpit -g clustercockpit -m 0600 "$PREP/ui-config.json" ./ui-config.json
sudo -u clustercockpit ./cc-backend -migrate-db
sudo -u clustercockpit perl "$PREP/updateUserconfig.pl" \
  --database /opt/monitoring/cc-backend/var/job.db --mapping "$PREP/configmap_v11.json"
sudo -u clustercockpit "$PREP/archive-migration" -archive /opt/monitoring/job-archive
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" verify \
  --database /opt/monitoring/cc-backend/var/job.db \
  --archive /opt/monitoring/job-archive --record "$PREP/before.json" \
  --db-version 11 --archive-version 3
sudo -u clustercockpit ./cc-backend -optimize-db
```

**`version.txt` darf nicht von Hand auf 3 gesetzt werden.** Das Archivtool setzt den Marker nach erfolgreichem Abschluss. Anschließend prüft der Migrationscheck Datenbank und Archiv wie oben gezeigt. Bei einem Fehler bleiben die Dienste gestoppt. Nach Klärung der Ursache beginnt der nächste Versuch wieder mit dem konsistenten Backup.

`-optimize-db` führt ANALYZE/VACUUM aus und benötigt zusätzlichen temporären Speicherplatz. Die Laufzeit hängt von Datenbankgröße und Storage ab.

## Cutover und Nachkontrollen

Beim Wechsel wird der alte Store mit `systemctl disable cc-metric-store.service` deaktiviert. Danach startet Backend 1.5.3; sein Journal zeigt mögliche Startfehler. Die Collector-Sinks benötigen nun die Backend-URL `/api/write/`, passende Port-/TLS-Einstellungen und den rohen Backend-JWT. Alte Storetokens und Backendtokens sind nicht austauschbar. Auch die Scheduleranbindung braucht die Backend-URL und einen gültigen API-Token. Ihre Kompatibilität mit dem Zielbackend muss vor dem Wechsel feststehen. Der [dokumentierte Adapterweg](slurm_setup.de.md) setzt Slurm ab 24.05 voraus.

Vor der Freigabe regulärer Jobstarts werden Collector und Scheduleranbindung aktiviert und ein kleiner [Testjob vollständig abgeschlossen](first_job.de.md). Zur Abnahme gehören Login, Benutzer- und Rollenbindung, Jobanzahl, repräsentative alte Jobs mit bekannten Metrikreihen, neue Host-/Core-/GPU-Zuordnungen, laufende Werte und erfolgreiche Archivierung. Vorher-/Nachher-API-Antworten ausgewählter alter Jobs müssen übereinstimmen.

Erst nach diesen Prüfungen endet das Wartungsfenster. Die JSON-Checkpointgrenzen für nachgelieferte historische Daten und Rundung bleiben bestehen; siehe [Betrieb](operation.de.md).

## Rollback / separater Restore

Bei einem Fehlschlag vor der Freigabe bleiben alle Schreiber gestoppt. Bereits neu aufgenommene Jobs benötigen zuerst eine eigene konsistente Sicherung und einen gesonderten Rückweg: Das alte Backup enthält diese Jobs nicht. Ein 1.4.4-Binary darf nicht mit einer 1.5.3-Datenbank starten.

Der folgende Rückweg stellt den vollständigen inventarisierten Stand wieder her. Die fehlgeschlagenen Pfade bleiben als `.failed-1.5.3` für die Diagnose erhalten; sie werden nicht pauschal gelöscht.

```bash
set -eu
systemctl stop clustercockpit.service cc-metric-store.service
python3 "$GUIDE_ROOT/docs/scripts/cc-offline-backup.py" restore \
  --backup "$BACKUP" --destination "$PREP/rollback-staging"
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" verify \
  --database "$PREP/rollback-staging/opt/monitoring/cc-backend/var/job.db" \
  --archive "$PREP/rollback-staging/opt/monitoring/job-archive" \
  --record "$PREP/before.json" --db-version 8 --archive-version 2
python3 - "$BACKUP/paths.json" "$PREP/rollback-staging" <<'RESTORE'
import json, pathlib, subprocess, sys
paths = [pathlib.Path(p) for p in json.loads(pathlib.Path(sys.argv[1]).read_text())['paths']]
staging = pathlib.Path(sys.argv[2])
# Preflight every source and destination before replacing any tree.
for path in paths:
    saved = staging / path.relative_to('/')
    if not (saved.exists() or saved.is_symlink()):
        raise SystemExit('Missing restored path: ' + str(path))
    quarantine = pathlib.Path(str(path) + '.failed-1.5.3')
    if quarantine.exists() or quarantine.is_symlink():
        raise SystemExit('Quarantine already exists: ' + str(path))
for path in paths:
    if path.exists() or path.is_symlink():
        path.rename(str(path) + '.failed-1.5.3')
    subprocess.run(['cp', '-a', '--', str(staging / path.relative_to('/')), str(path)], check=True)
RESTORE
systemctl daemon-reload
systemctl start cc-metric-store.service
systemctl start clustercockpit.service
```

Anschließend benötigen Collectoren und Scheduleranbindung wieder die gesicherten Ziele, Ports und Tokens. Nach deren Aktivierung müssen die alten bekannten Metrikreihen über die 1.4.4-API lesbar sein. Erst dann können neue Jobstarts wieder freigegeben werden. Externe Symlinkziele und Unit-Drop-ins gehören zum selben Restoreinventar. Vorhandene Quarantäne- oder Stagingpfade führen zum Abbruch und dürfen nicht blind überschrieben werden.
