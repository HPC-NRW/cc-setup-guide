# Versionen und Updates

Die Neuinstallation verwendet Backend **1.5.4**. Ein vorhandenes System braucht einen eigenen Updateweg; das Installationsskript überschreibt keine Installation und hat keinen Update- oder Resume-Modus.

## Dokumentierte Versionsstände

| Komponente oder Vorgang | Stand dieses Guides |
| --- | --- |
| Neuinstallation des Backends | 1.5.4, SQLite-Schema 11, Jobarchivformat 3 |
| Ältere Backendmigration | [1.4.4 → 1.5.3](migration_1_4_4_to_1_5_3.de.md), Schema 8 → 11, Archivformat 2 → 3 |
| Backendupdate ohne Formatwechsel | 1.5.3 → 1.5.4, wie unten beschrieben |
| Metric Collector | v0.8.4 |
| LIKWID | 5.5.1 |
| Slurm-Adapter | Festgelegter Quellstand für Slurm ab 24.05 |

Für Slurm 23.11 besteht [kein validierter ungepatchter Einrichtungsweg zu Backend 1.5.4](slurm_sync.de.md). Der Sync-Eintrag im Versionsmanifest dokumentiert ausschließlich diesen geprüften inkompatiblen Referenzstand.

Exakte Commits und Prüfsummen stehen im [Versionsmanifest](https://github.com/hpc-nrw/cc-setup-guide/blob/main/versions.json). Versionskombinationen außerhalb dieser Tabelle benötigen eine eigene Prüfung der jeweiligen Release Notes und Konfigurationsänderungen. Die Kapitel ersetzen keine allgemeine Updateanleitung für beliebige Backend- oder Slurm-Versionen.

## Backend 1.5.3 auf 1.5.4 aktualisieren

Dieser Weg gilt für die SQLite-Installation des Guides mit bereits vorhandenem Schema 11 und Archivformat 3. Laut den [Release Notes von 1.5.4](https://github.com/ClusterCockpit/cc-backend/blob/c94f5918f3126bacabd91e9ae6e194f3de6ea83c/ReleaseNotes.md) ist für diesen Versionswechsel keine Datenbankmigration nötig. Konfiguration, `.env`, UI-Datei und Daten bleiben erhalten; ausgetauscht wird das Backendbinary. Ein Durchlauf mit einer separaten Testkopie gehört zur Vorbereitung auf ein Update des Produktivsystems.

### Release getrennt vorbereiten

Die folgenden Befehle laufen als root. `BACKEND_DIR`, Dienstkonto und `PREP` müssen zur Installation passen; `PREP` ist ein neues Verzeichnis außerhalb der laufenden Installation. Das bestehende Binary muss vor dem Update Version 1.5.3 melden.

```bash
set -eu
BACKEND_DIR=/opt/monitoring/cc-backend
PREP=/opt/monitoring/prepare-1.5.4
"$BACKEND_DIR/cc-backend" -version
test ! -e "$PREP" && test ! -L "$PREP"
install -d -o root -g clustercockpit -m 0750 "$PREP"
cd "$PREP"
curl --fail --location --max-time 120 -o backend.tar.gz \
  https://github.com/ClusterCockpit/cc-backend/releases/download/v1.5.4/cc-backend_Linux_x86_64.tar.gz
printf '%s  backend.tar.gz\n' ecfba842a1882ccb4285e8f274029ef4afcc7442417e00aafe0a204fc734f698 | sha256sum -c -
mkdir release
tar -xzf backend.tar.gz -C release
test -x release/cc-backend
./release/cc-backend -version
```

Die neue Versionsausgabe muss 1.5.4 nennen. Die Prüfsumme gilt für das verlinkte Linux-x86_64-Release. Ein anderer Build benötigt einen eigenen geprüften Bezug.

### Wartungsfenster und Sicherung

Vor dem Austausch gilt der vollständige Ablauf unter [Backup und Wiederherstellung](backup_restore.de.md): neue Jobstarts aussetzen, laufende Jobs beenden und archivieren, alle Schreiber stoppen, danach das Backend stoppen. Das Inventar muss Binary, Daten, Konfiguration und Schlüssel enthalten. Erst nach einer erfolgreichen Restoreprobe folgt der Austausch.

Schema 11 und Archivformat 3 werden bereits bei der Sicherung geprüft. `-init-db`, `-migrate-db` und das Archivmigrationstool sind für diesen Updateweg nicht erforderlich. Ein abweichendes Schema oder Archivformat gehört in einen anderen Migrationsplan.

### Binary austauschen und prüfen

Nach erfolgreicher Sicherung bleibt das Backend gestoppt. Der Austausch übernimmt das vorbereitete Binary; Konfiguration und Daten werden nicht aus Releasebeispielen ersetzt.

```bash
set -eu
BACKEND_DIR=/opt/monitoring/cc-backend
PREP=/opt/monitoring/prepare-1.5.4
install -o root -g root -m 0755 "$PREP/release/cc-backend" "$BACKEND_DIR/cc-backend"
"$BACKEND_DIR/cc-backend" -version
systemctl start clustercockpit.service
systemctl status clustercockpit.service
journalctl -u clustercockpit.service -n 100 --no-pager
```

Zur Abnahme gehören Login, Rollen und Projektzuordnungen sowie repräsentative alte Jobs mit bekannten Messwerten. Die gesicherte Datenbank-/Archivaufnahme ermöglicht zusätzlich einen Vergleich mit dem Migrationscheck. Erst nach diesen Prüfungen werden Collectoren und Scheduleranbindung wieder aktiviert und ein [Testjob](first_job.de.md) vollständig abgeschlossen. Danach können reguläre Jobstarts wieder freigegeben werden.

Bei einem Fehler bleiben neue Jobstarts gesperrt. Der [Wiederherstellungsweg](backup_restore.de.md#gesicherten-stand-wiederherstellen) setzt den vollständigen gesicherten Stand zurück. Bereits seit dem Backup eingegangene Daten müssen dabei gesondert berücksichtigt werden. Die Persistenzgrenzen für Checkpoints und historische Nachlieferungen bleiben auch nach dem Update bestehen.
