# Migration von 1.4.4 auf 1.5.3

Diese Seite beschreibt das Update einer bestehenden ClusterCockpit-Installation von `cc-backend` 1.4.4 auf 1.5.3. Die Schritte basieren auf dem RUB-Update vom 16.04.2026 und den offiziellen [Release Notes für cc-backend 1.5.3](https://git.clustercockpit.org/ClusterCockpit/cc-backend/src/commit/300108664774c5561b6838382876e247d0b043b9/ReleaseNotes.md).

## Wichtige Änderungen

- `cc-metric-store` ist ab 1.5 im `cc-backend` integriert. Es gibt keinen separaten `cc-metric-store.service` und keine separate Metric-Store-Config mehr.
- `config.json` verwendet jetzt durchgehend `kebab-case`, z. B. `api-allowed-ips` statt `apiAllowedIPs`.
- Der frühere `clusters`-Abschnitt entfällt. Clusterinformationen werden aus dem Job-Archive gelesen.
- MySQL/MariaDB wird nicht mehr unterstützt; produktive Setups müssen SQLite verwenden.
- Das Job-Archive wird auf Version 3 migriert, die Datenbank auf Version 11.
- Für gute SQLite-Performance wird nach der Migration `./cc-backend -optimize-db` empfohlen.
- Alte UI-User-Configs aus der Datenbank passen nicht mehr vollständig zu den neuen UI-Keys. Metrikauswahl sollte über `ui-config.json` bzw. die neue UI-Konfiguration gesetzt werden.

## Vorbereitung

Lege vor dem Update Backups an:

```bash
systemctl stop clustercockpit.service cc-metric-store.service

cp -a /opt/monitoring/cc-backend/var/job.db /root/job.db.before-1.5.3
cp -a /opt/monitoring/job-archive /root/job-archive.before-1.5.3
cp -a /opt/monitoring/cc-backend/config.json /root/config.json.before-1.5.3
```

Wenn `job.db` sehr groß ist, kann ein vorheriges `VACUUM` sinnvoll sein. Im RUB-Update wurde ein separates temporäres Verzeichnis genutzt:

```bash
TMPDIR=/opt/monitoring/sqlite-tmp sqlite3 /opt/monitoring/cc-backend/var/job.db "VACUUM;"
```

## Build-Voraussetzungen

Für 1.5.3 wurde Node.js 22 installiert, danach wurde `cc-backend` aus dem aktuellen `main` gebaut:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
apt-get install -y nodejs

cd /opt/monitoring/cc-backend
git fetch origin
git checkout main
make
```

Alternativ kann ein passendes Release-Archiv verwendet werden. Wichtig ist, dass Binary, Config und Migrationswerkzeuge aus derselben 1.5.3-Version stammen.

## Config umstellen

Ersetze die alte 1.4.4-Config durch eine 1.5.3-kompatible `config.json` und ergänze eine `ui-config.json`, falls die UI-Vorgaben zentral gesetzt werden sollen.

Als Orientierung kann eine 1.5.3-kompatible Beispielkonfiguration verwendet werden:

### `cc-backend/config.json`

[Datei öffnen](examples/rub/cc-backend/config.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/cc-backend/config.json"
```

</details>

### `job-archive/cluster.json`

[Datei öffnen](examples/rub/job-archive/cluster.json)

<details>
<summary>Inhalt anzeigen</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

Im Update wurde die vorbereitete Konfiguration nach `/opt/monitoring/cc-backend/` kopiert:

```bash
mv /root/update_1.5.3/config.json /opt/monitoring/cc-backend/config.json
mv /root/update_1.5.3/ui-config.json /opt/monitoring/cc-backend/ui-config.json
```

## Datenbank und Job-Archive migrieren

Führe zuerst die Datenbankmigration aus:

```bash
cd /opt/monitoring/cc-backend
./cc-backend -migrate-db
```

Danach das Job-Archive migrieren. Das Tool liegt im cc-backend-Quellbaum:

```bash
cd /opt/monitoring/cc-backend/tools/archive-migration
go build
./archive-migration -archive ../../../job-archive/
```

Setze anschließend die Job-Archive-Version auf 3, falls das Migrationstool bzw. die lokale Struktur das nicht bereits erledigt hat:

```bash
echo 3 > /opt/monitoring/job-archive/version.txt
```

## Performance-Optimierung

Nach der Migration:

```bash
cd /opt/monitoring/cc-backend
./cc-backend -optimize-db
```

Laut Release Notes führt `-optimize-db` SQLite `ANALYZE` und `VACUUM` aus. Bei Datenbanken über 40 GB kann `VACUUM` bis zu ca. zwei Stunden dauern.

## Alten Metric-Store deaktivieren

Da der Metric-Store ab 1.5.3 im Backend läuft, wird der alte Dienst deaktiviert:

```bash
systemctl disable --now cc-metric-store.service
```

Die bisherigen Checkpoints und Archive sollten erst gelöscht werden, wenn klar ist, dass die neue Installation stabil läuft und die Daten nicht mehr gebraucht werden.

## User-Konfiguration aktualisieren

Im RUB-Update wurde ein lokales Hilfsskript für die User-Config ausgeführt:

```bash
cd /root/update_1.5.3
chmod +x updateUserconfig.pl
./updateUserconfig.pl
```

Wenn kein solches Skript vorhanden ist, sollten alte UI-User-Config-Einträge geprüft oder entfernt werden. Die Release Notes weisen darauf hin, dass alte UI-Keys nicht weiterverwendet werden.

## Start und Prüfung

```bash
systemctl start clustercockpit.service
systemctl status clustercockpit.service
journalctl -u clustercockpit.service -f
```

Danach prüfen:

- Login und Navigation funktionieren.
- Cluster und Subcluster werden aus dem Job-Archive angezeigt.
- Neue Metriken kommen über `/api/write/` an.
- Alte Jobs und Jobdetails sind sichtbar.
- Der ehemalige `cc-metric-store.service` bleibt deaktiviert.
