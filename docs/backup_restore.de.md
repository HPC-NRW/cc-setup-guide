# Backup und Wiederherstellung

Ein vollständiges Backup umfasst Daten und den dazugehörigen Betriebszustand: Datenbank, Jobarchiv, Store-Dateien, Konfigurationen, Schlüssel, Binaries und Dienstdefinitionen. Nur das Jobarchiv zu kopieren reicht für eine vollständige Wiederherstellung nicht aus.

Dieses Kapitel beschreibt ein Offlinebackup für die im Guide verwendeten SQLite-Installationen mit Backend 1.5.3 oder 1.5.4, Datenbankschema 11 und Archivformat 3. Für die ältere Installation gilt der eigene [Migrationsweg von 1.4.4 auf 1.5.3](migration_1_4_4_to_1_5_3.de.md). MySQL/MariaDB erfordert einen gesonderten Datenbank-Backupplan.

## Umfang festlegen

Die tatsächlichen Pfade ergeben sich aus `config.json`, `.env`, systemd-Units und deren Drop-ins. Zum Inventar gehören:

- Die Datenbank einschließlich vorhandener SQLite-Begleitdateien und das vollständige Jobarchiv.
- Backendbinary, Konfigurationen, UI-Datei und JWT-, Session- sowie weitere Schlüssel.
- Checkpoints, archivierte Store-Dateien und gegebenenfalls WAL-Dateien.
- Units, Drop-ins und systemweite Environment-Dateien.
- Collector- und Schedulerkonfigurationen einschließlich der verwendeten Tokens.

Verzeichnisbackups enthalten deren Inhalt. Daten außerhalb dieser Verzeichnisse benötigen eigene Einträge, auch bei Symlinks. `systemctl cat clustercockpit.service` und `find /opt/monitoring -type l -ls` helfen beim Inventarisieren; Pfade aus Konfigurationswerten müssen zusätzlich berücksichtigt werden. Auf anderen Knoten liegende Konfigurationen benötigen eigene Sicherungen auf den jeweiligen Systemen.

Das folgende Inventar passt zum Standardpfad des Installers, bei dem Datenbank und Jobarchiv unterhalb des Backendverzeichnisses liegen. Externe Archive oder Store-Verzeichnisse aus einer anderen Konfiguration benötigen zusätzliche Einträge. Beispielpfade, die nicht existieren, gehören nicht ins Inventar.

```json
{
  "paths": [
    "/opt/monitoring/cc-backend",
    "/etc/systemd/system/clustercockpit.service"
  ]
}
```

Der [Backuphelper](scripts/cc-offline-backup.py) lehnt fehlende und überlappende Pfade, `/` als Quelle sowie nicht inventarisierte externe Symlinkziele ab. Er findet keine externen Pfade automatisch in Konfigurationswerten. Ein vollständiges Inventar bleibt deshalb Voraussetzung.

## Dienste anhalten

Für eine konsistente Sicherung dürfen keine Prozesse mehr in die Daten schreiben:

1. Neue Jobstarts mit der Slurm-Administration aussetzen.
2. Laufende Jobs beenden lassen und deren erfolgreiche Archivierung prüfen.
3. Collectoren, Scheduleranbindung und andere API-Schreiber auf den jeweiligen Systemen stoppen.
4. Erst danach das Backend anhalten.

```bash
systemctl stop clustercockpit.service
```

Backend 1.5.3 und 1.5.4 verwenden in diesem Guide den integrierten Store. Ein zusätzlicher `cc-metric-store.service` gehört nur zu einer entsprechenden älteren Installation. Ein Backup bei laufenden Schreibern ist mit diesem Verfahren nicht konsistent.

## Sichern und Restoreprobe durchführen

Voraussetzungen sind root, Python 3 und GNU tar mit ACL-/xattr-Unterstützung. Alle folgenden Befehle laufen in derselben root-Bash-Sitzung. `GUIDE_DIR`, Datenpfade und Backupverzeichnis müssen zur Installation passen. Das vorhandene Backupverzeichnis ist geschützt und bietet genügend Platz für Sicherung und Restoreprobe. Die beiden Zielverzeichnisse `BACKUP` und `RESTORE` dürfen noch nicht existieren und müssen außerhalb der Quellen liegen.

Das angepasste Inventar liegt im Beispiel als `/srv/cc-backups/backup-paths.json` vor.

```bash
set -eu
umask 077
GUIDE_DIR=/path/to/cc-setup-guide
BACKEND_DIR=/opt/monitoring/cc-backend
ARCHIVE_DIR="$BACKEND_DIR/var/job-archive"
BACKUP_ROOT=/srv/cc-backups
BACKUP="$BACKUP_ROOT/before-maintenance"
RESTORE="$BACKUP_ROOT/restore-check"
RECORD="$BACKUP_ROOT/before.json"
python3 "$GUIDE_DIR/docs/scripts/cc-migration-check.py" snapshot \
  --database "$BACKEND_DIR/var/job.db" --archive "$ARCHIVE_DIR" \
  --record "$RECORD" --db-version 11 --archive-version 3
python3 "$GUIDE_DIR/docs/scripts/cc-offline-backup.py" backup \
  --inventory "$BACKUP_ROOT/backup-paths.json" --destination "$BACKUP"
python3 "$GUIDE_DIR/docs/scripts/cc-offline-backup.py" restore \
  --backup "$BACKUP" --destination "$RESTORE"
python3 "$GUIDE_DIR/docs/scripts/cc-migration-check.py" verify \
  --database "$RESTORE$BACKEND_DIR/var/job.db" --archive "$RESTORE$ARCHIVE_DIR" \
  --record "$RECORD" --db-version 11 --archive-version 3
```

Der Restore liegt unter einem neuen Verzeichnis; er überschreibt die Installation nicht. Absolute Pfade sind darunter abgebildet, etwa `/opt/monitoring/cc-backend` als `$RESTORE/opt/monitoring/cc-backend`. Bei ausgelagerten Daten müssen die Prüfpfade dem Inventar folgen. Absolute Symlinks zeigen nach dem Entpacken weiterhin auf ihre ursprünglichen Ziele; die Probe darf dadurch nicht versehentlich die Originaldaten prüfen.

Der Migrationscheck prüft Datenbankintegrität und Version, Jobanzahl, Identitäten und Ressourcen, Archivmetadaten sowie die Hashes der `data.json`-Dateien. Er ersetzt keine Prüfung der gesicherten Schlüssel, Konfigurationen und Betriebssystemrechte. GNU tar sichert ACLs, xattrs und Eigentümer; die Wiederherstellung der Eigentümer erfordert root.

Das Backupverzeichnis hat `0700`, Dateien entstehen unter `umask 077`. Backup, Inventar und `before.json` gehören zusammen auf ein geeignetes geschütztes Backupmedium. Dort bestätigt eine erneute Prüfsummenprüfung die übertragene Kopie. Nur eine erfolgreiche Restoreprobe belegt, dass das Backup lesbar ist.

## Gesicherten Stand wiederherstellen

Die Wiederherstellung beginnt mit demselben Stopp aller Schreiber. Ein neuer Restore in ein leeres Stagingverzeichnis und die obige Prüfung müssen erfolgreich sein, bevor Dateien der Installation ersetzt werden.

Für jeden inventarisierten Pfad gilt: Der bisherige Stand bleibt unter einem noch unbenutzten Diagnosenamen erhalten; der geprüfte Restore wird mit erhaltenen Eigentümern und Rechten an den ursprünglichen Ort kopiert. Das betrifft auch externe Symlinkziele, Schlüssel, Units und Drop-ins. Bereits vorhandene Diagnose- oder Zielpfade erfordern eine Prüfung und dürfen nicht blind überschrieben werden.

Datenbank, Archiv, Konfiguration und Binary bilden einen gemeinsamen Stand. Ein altes Binary darf nicht mit einer zwischenzeitlich migrierten Datenbank starten. Falls seit dem Backup neue Jobs eingegangen sind, gehören diese vor dem Rückweg in eine eigene konsistente Sicherung; das alte Backup enthält sie nicht.

Nach dem Zurückspielen der Units folgen `systemctl daemon-reload` und der Backendstart. Gesicherte Collector- und Schedulerziele, Ports und Tokens müssen zum wiederhergestellten Backend passen. Vor der Freigabe neuer Jobstarts gehören Login, Rollen, bekannte archivierte Jobs und ein [vollständiger Testjob](first_job.de.md) zur Abnahme. Die [Persistenzgrenzen](operation.de.md#persistenzgrenzen-des-integrierten-stores) des integrierten Stores gelten weiterhin.
