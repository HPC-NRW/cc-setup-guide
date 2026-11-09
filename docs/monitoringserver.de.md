# Server-Komponenten installieren

Dieses Kapitel beschreibt eine **Neuinstallation auf einem dedizierten Ubuntu-/Debian-Monitoringserver (Linux x86_64)**. Die Installation läuft als `root`; der spätere Dienst verwendet ein eigenes Konto. Für bestehende Installationen gilt der gesonderte [Update- und Migrationsweg](operation.de.md).

Der empfohlene Weg verwendet das Installationsskript. Der [manuelle Weg](#manueller-weg) zeigt dieselben Schritte einzeln und ist eine Alternative. Beide Wege enden mit [Dienst installieren, starten und prüfen](#dienst-installieren-starten-und-prufen).

## Voraussetzungen und Dienstkonto

Die Installation benötigt Bash, Python ≥3.9 mit Standardbibliothek, curl, OpenSSL, GNU coreutils, getent und systemd-Werkzeuge zur Unitprüfung. Auf dem neuen Monitoringserver richten die folgenden Befehle die Pakete und das Dienstkonto ein und laden den Guide:

```bash
apt-get update
apt-get install python3 curl openssl ca-certificates git systemd
useradd --system --no-create-home --user-group --shell /usr/sbin/nologin clustercockpit
git clone https://github.com/HPC-NRW/cc-setup-guide.git
cd cc-setup-guide
```

Bei einem bereits vorhandenen Dienstkonto entfällt `useradd`. Das Installationsziel darf noch nicht existieren; es wird weder vorab angelegt noch durch ein rekursives `chown` vorbereitet. `/opt` beziehungsweise `/srv` müssen bereits existieren, root gehören und dürfen für Gruppe und andere Benutzer nicht beschreibbar sein. Auch alle übergeordneten Verzeichnisse müssen echte Verzeichnisse sein, keine Symlinks.

## Installation per Skript

Das Skript benötigt den vollständigen Checkout mit `versions.json`, `scripts/templates/` und `docs/examples/minimal/`. Der Quellcode liegt in [cc-installation.sh](https://github.com/hpc-nrw/cc-setup-guide/blob/main/scripts/cc-installation.sh) und [install_support.py](https://github.com/hpc-nrw/cc-setup-guide/blob/main/scripts/install_support.py).

Für die Installation unter `/opt/monitoring` mit dem Beispielcluster `demo_cluster`:

```bash
bash scripts/cc-installation.sh -c demo_cluster
```

Alternativ lassen sich Zielpfad und Dienstkonto angeben. Auch dieses Ziel darf noch nicht existieren:

```bash
bash scripts/cc-installation.sh -c demo_cluster -d /srv/monitoring -u clustercockpit:clustercockpit
```

<details>
<summary>Zulässige Cluster-, Pfad- und Kontonamen</summary>

Clusternamen müssen dem Muster `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` entsprechen. Pfade müssen absolut sein und mindestens zwei Komponenten enthalten. Innerhalb einer Komponente sind Buchstaben, Ziffern, `_`, `-` und `.` erlaubt. Das Skript lehnt `.`/`..`, relative Pfade, Symlinks, Leerzeichen, Zeilenumbrüche, Anführungszeichen, Backslashes, `&`, `@` und `%` ab.

Für Kontonamen gilt `[a-z_][a-z0-9_-]{0,31}`. `-u name` verwendet die gleichnamige Gruppe; `-u name:group` legt Benutzer und Gruppe getrennt fest.

</details>

Vor dem Download prüft das Skript Konten, Pfade, Versionsmanifest, Templates und UI-Konfiguration. Bei einem vorhandenen Ziel bricht es ohne Änderungen ab. Das gilt auch für leere Verzeichnisse und Reste eines abgebrochenen Versuchs. Es gibt keinen Update- oder Resume-Modus. Nach einem Abbruch bleibt der private Zustand für die Diagnose erhalten und muss vor dem Löschen oder einer erneuten Verwendung geprüft werden.

`umask 077` gilt bereits vor dem ersten Schreibzugriff. Passwörter und JWT erscheinen nicht auf stdout; die privaten Diagnosedateien in `.install-tmp` dürfen ebenfalls nicht veröffentlicht werden. Nach erfolgreichem Durchlauf ist die Installation vorbereitet. **Der Dienst ist noch nicht installiert oder gestartet.** Weiter geht es direkt mit [Dienst installieren, starten und prüfen](#dienst-installieren-starten-und-prufen).

## Manueller Weg

Die folgenden Schritte ersetzen das Installationsskript. Sie setzen ein **eigenes frisches Ziel** voraus und laufen nacheinander in derselben root-Bash-Sitzung, beginnend im geklonten Guide. Die Python-Helfer aus [install_support.py](https://github.com/hpc-nrw/cc-setup-guide/blob/main/scripts/install_support.py) prüfen Eingaben und Archive, erzeugen sichere Schlüsseldateien und setzen Rechte. Sie führen hier keine Installation, Downloads oder Dienststarts im Hintergrund aus.

### 1. Umgebung prüfen und neues Ziel reservieren

Der folgende Block wählt dasselbe Release wie das Installationsskript. `GUIDE_DIR` hält den absoluten Pfad zur Templatequelle fest, auch nach späteren `cd`-Aufrufen.

<!-- installer-manual-1 -->
```bash
set +x
set -euo pipefail
umask 077
# Run in the cloned guide, in the same root Bash session for all steps.
GUIDE_DIR=$(pwd -P)
INSTALL_DIR=/opt/monitoring
CLUSTER_NAME=demo_cluster
CC_USER=clustercockpit
CC_GROUP=clustercockpit
HELPER="$GUIDE_DIR/scripts/install_support.py"
for command in python3 curl openssl install mkdir rm cp sed stat uname systemd-analyze; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done
VERSION=$(python3 "$HELPER" default-version "$GUIDE_DIR")
python3 "$HELPER" preflight "$GUIDE_DIR" "$INSTALL_DIR" "$CLUSTER_NAME" "$CC_USER" "$CC_GROUP" "$VERSION"
test "$(uname -s):$(uname -m)" = Linux:x86_64
mkdir -m 0700 -- "$INSTALL_DIR"
install -d -m 0700 "$INSTALL_DIR/cc-backend" "$INSTALL_DIR/.install-tmp"
TEMP_DIR="$INSTALL_DIR/.install-tmp"
```

### 2. Festes Release herunterladen und geprüft entpacken

Der Helfer prüft den Download und entpackt das Release, ohne vorhandene Dateien zu überschreiben.

<details>
<summary>Details der Releaseprüfung</summary>

Die Prüfung verlangt gültiges Release-JSON mit genau einem passenden Asset, eine passende SHA256-Prüfsumme und genau sechs flache reguläre Dateien. Links, Pfad-Traversal und abweichende Archivlayouts werden abgelehnt. Das Entpacken erfolgt ohne `--strip-components=1`.

</details>

<!-- installer-manual-2 -->
```bash
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 120 --retry 2 \
    "https://api.github.com/repos/ClusterCockpit/cc-backend/releases/tags/v$VERSION" > "$TEMP_DIR/release.json"
URL=$(python3 "$HELPER" release-url "$GUIDE_DIR" "$VERSION" "$TEMP_DIR/release.json")
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 300 --retry 2 "$URL" > "$TEMP_DIR/backend.tar.gz"
python3 "$HELPER" extract "$GUIDE_DIR" "$VERSION" "$TEMP_DIR/backend.tar.gz" "$INSTALL_DIR/cc-backend"
cd "$INSTALL_DIR/cc-backend"
test -x ./cc-backend && test -x ./gen-keypair
```

### 3. Neue Schlüssel und Sessionsecret erzeugen

`gen-keypair` erzeugt neue Ed25519-Schlüssel. Der Helfer prüft Anzahl und Länge und ergänzt eine zufällige Sessionkennung. Schlüsselinhalt wird dabei nicht ausgegeben.

<!-- installer-manual-3 -->
```bash
./gen-keypair > "$TEMP_DIR/keypair.txt"
python3 "$HELPER" environment "$TEMP_DIR/keypair.txt" .env
rm -- "$TEMP_DIR/keypair.txt"
```

### 4. Backend-, UI-, Cluster- und Dienstkonfiguration erzeugen

Das Minimaltemplate enthält bereits `cpu_load` und den Beispielhost `node001` im Subcluster `first_subcluster`. Hostnamen, Topologie und Grenzwerte müssen vor dem Erfassungseinsatz zur tatsächlichen Hardware passen; das beschreibt [Ersten Cluster einrichten](cluster_minimal.de.md).

Die mitgelieferte [ui-config.json](examples/minimal/cc-backend/ui-config.json) gehört zusammen mit `config.json` ins Backend-Arbeitsverzeichnis. Sie enthält die Standardwerte der Weboberfläche; `ui-file` in `config.json` verweist darauf. Anpassungen der Darstellung erfolgen später in dieser Datei.

<!-- installer-manual-4 -->
```bash
cp "$GUIDE_DIR/scripts/templates/cc-backend.json.template" config.json
cp "$GUIDE_DIR/docs/examples/minimal/cc-backend/ui-config.json" ui-config.json
mkdir -p "var/job-archive/$CLUSTER_NAME"
python3 - "$GUIDE_DIR" "$CLUSTER_NAME" <<'CONFIG'
import json, pathlib, sys
source = pathlib.Path(sys.argv[1]) / 'scripts/templates/cluster.json.template'
cluster = json.loads(source.read_text())
cluster['name'] = sys.argv[2]
with (pathlib.Path('var/job-archive') / sys.argv[2] / 'cluster.json').open('x') as output:
    json.dump(cluster, output, indent=2)
    output.write('\n')
CONFIG
# Only this newly created, empty archive: never change an existing format marker.
printf '3\n' > var/job-archive/version.txt
sed -e "s@__INSTALL_DIR__@$INSTALL_DIR@g" \
    -e "s@__CC_USER__@$CC_USER@g" -e "s@__CC_GROUP__@$CC_GROUP@g" \
    "$GUIDE_DIR/scripts/templates/clustercockpit.service.template" > "$INSTALL_DIR/clustercockpit.service"
```

### 5. Leere Datenbank und Benutzer erzeugen

`-migrate-db` erzeugt die leere Datenbank. **`-init` ist hier ungeeignet:** Das Kommando würde eigene Konfiguration und Secrets durch Upstream-Beispiele ersetzen oder bei einem vorhandenen `var` nichts tun. Der vorher gesetzte Archivmarker `3` gilt ausschließlich für das neue leere Archiv und ersetzt keine Migration.

Die CLI gibt den JWT zusammen mit weiterem Text aus. Der Helfer extrahiert genau einen strukturell gültigen EdDSA-Token und speichert ihn in `apikey.txt`.

<!-- installer-manual-5 -->
```bash
./cc-backend -migrate-db > "$TEMP_DIR/database.log" 2>&1
ADMIN_PASS=$(openssl rand -base64 24)
API_PASS=$(openssl rand -base64 24)
./cc-backend -add-user "admin:admin:$ADMIN_PASS" > "$TEMP_DIR/admin.log" 2>&1
./cc-backend -add-user "apiuser:api:$API_PASS" > "$TEMP_DIR/apiuser.log" 2>&1
printf '%s\n' "$ADMIN_PASS" > admin_password.txt
printf '%s\n' "$API_PASS" > apiuser_password.txt
unset ADMIN_PASS API_PASS
./cc-backend -jwt apiuser > "$TEMP_DIR/jwt.txt" 2> "$TEMP_DIR/jwt.log"
python3 "$HELPER" token "$TEMP_DIR/jwt.txt" apikey.txt
rm -- "$TEMP_DIR/jwt.txt"
```

**Grenze der Upstream-CLI:** `-add-user` nimmt das Passwort als Kommandozeilenargument entgegen und bietet dafür keine stdin- oder Passwortdatei-Option. Auf Systemen mit allgemein sichtbaren Prozessargumenten können andere lokale Benutzer das Passwort während dieses kurzen Aufrufs sehen. Die Kontoanlage erfolgt deshalb auf dem frischen dedizierten Monitoringserver, bevor nicht vertrauenswürdige lokale Zugänge freigeschaltet werden. Geschützte Dateien und unterdrückte Logausgabe beseitigen diese Grenze nicht.

### 6. Eigentümer und Rechte abschließen, Unit prüfen

Der Helfer prüft die erzeugten Datenbankbenutzer und setzt die Rechte ausschließlich im neuen Ziel: root besitzt Binaries und Konfiguration, das Dienstkonto den Laufzeitzustand unter `var`. Die API-Datei ist nur für root lesbar. Benötigte Kopien gehören gezielt in geschützte Konfigurationen der jeweiligen Clients; ein allgemeines `chown -R` auf ein fremdes Installationspräfix ist dafür ungeeignet.

<!-- installer-manual-6 -->
```bash
# Validate the database/users and set explicit final owners and permissions.
python3 "$HELPER" finish "$INSTALL_DIR" "$CC_USER" "$CC_GROUP"
# Expected: root:service-group 0750 for installation/backend directories;
# root:service-group 0640 for .env/config, root-only 0600 for password/JWT files;
# service-user:service-group 0700 directories / 0600 files beneath var.
stat -c '%U:%G %a %n' . .env config.json ui-config.json apikey.txt var var/job.db
systemd-analyze verify "$INSTALL_DIR/clustercockpit.service"
```

## Dienst installieren, starten und prüfen

Dieser Abschluss gilt für beide Installationswege. `INSTALL_DIR` muss dem zuvor gewählten Ziel entsprechen: beim Standardaufruf `/opt/monitoring`, beim Beispiel mit `-d` dagegen `/srv/monitoring`. Die Zuweisung im folgenden Block erfolgt in der aktuellen Shell; das Installationsskript setzt dort keine Variable.

Vor dem Start `config.json`, Clusterhostnamen und Netzwerkzugriff prüfen. Die folgenden Befehle laufen als root:

```bash
INSTALL_DIR=/opt/monitoring
install -o root -g root -m 0644 "$INSTALL_DIR/clustercockpit.service" /etc/systemd/system/clustercockpit.service
systemctl daemon-reload
systemctl enable --now clustercockpit.service
systemctl status clustercockpit.service
journalctl -u clustercockpit.service -n 50 --no-pager
```

Der Dienst sollte als aktiv erscheinen; das Journal sollte keine Fehler beim Laden der Konfiguration oder beim Öffnen der Datenbank melden. Die Weboberfläche ist zunächst auf Port `8080` erreichbar. Der nächste Kontrollpunkt ist der [erste Login](webinterface.de.md), danach folgt die [Cluster- und Knotenkonfiguration](cluster_minimal.de.md).

Vor dem ersten Collectorzugriff über HTTPS sind [Reverse Proxy und TLS](https_setup.de.md) sowie die erlaubten API-Quelladressen einzurichten. Der spätere Collectorpfad verwendet diesen HTTPS-Endpunkt.

Passwortdateien und der **rohe JWT** liegen unter `$INSTALL_DIR/cc-backend/`: `admin_password.txt`, `apiuser_password.txt` und `apikey.txt`, jeweils mit Modus `0600`. `.env` enthält die privaten Signatur- und Sessionwerte und hat Modus `0640` mit root als Eigentümer und der Dienstgruppe als Gruppe. Diese Dateien dürfen nicht veröffentlicht werden.

`auth.jwts.max-age` steht im Template auf `8760h` (365 Tage). Vor Ablauf müssen neue Tokens erzeugt und an alle Clients verteilt werden. Ein leerer Wert würde nicht ablaufende Tokens erzeugen; eine spätere Konfigurationsänderung verändert bereits ausgegebene Tokens nicht. `main.api-allowed-ips` akzeptiert einzelne IP-Adressen, keine CIDR-Netze. Der Standardwert `*` muss für den Standort bewusst eingegrenzt werden.

`metric-store.retention-in-memory` legt die Aufbewahrungszeit im Arbeitsspeicher fest. Speicherlimit, aktive Jobs, Neustarts und die Rundung in JSON-Checkpoints beeinflussen die Datenhaltung ebenfalls. Grenzen und Backups sind unter [Betrieb](operation.de.md) beschrieben. Die [erste Metrik](metrics.de.md) und die [Metrikannahme und Darstellung](metric_receive_display.de.md) folgen nach der Collectoreinrichtung.
