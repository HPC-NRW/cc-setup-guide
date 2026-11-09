# cc-slurm-adapter

Für Slurm ab 24.05 ist `cc-slurm-adapter` der empfohlene Weg. Er überträgt laufende und abgeschlossene Jobs an `cc-backend`. Die [Auswahl der Slurm-Anbindung](slurm_setup.de.md) beschreibt auch die Kompatibilitätsgrenzen älterer Slurm-Versionen.

## Übersicht

Der Adapter läuft auf demselben Knoten wie `slurmctld` und verwendet die Slurm-Werkzeuge `sacct`, `squeue`, `sacctmgr` und `scontrol`. `slurmdbd` ist erforderlich, `slurmrestd` nicht. Ein periodischer Timer stößt die Synchronisation standardmäßig jede Minute an.

Nach Unterbrechungen versucht der Adapter, fehlende Jobdaten nachzuliefern. Dabei gelten die Aufbewahrungsgrenzen von Slurm. Ein optionaler Prolog-/Epilog-Hook kann die Abfrage unmittelbar auslösen und so die Verzögerung verringern.

## Einschränkungen

Slurmdbd hält nicht alle Jobinformationen dauerhaft vor. Ressourcendaten aus `scontrol show job --json` verschwinden wenige Minuten nach Jobende. Der Parameter `MinJobAge` in `slurm.conf` bestimmt diese Zeit; der Standardwert ist 300 Sekunden.

Nach einem längeren Ausfall können daher Ressourceninformationen fehlen. Das Backend kann den Job dann noch auflisten, ihm aber keine Metriken zuordnen. Längere Unterbrechungen des Adapters sind deshalb bei laufendem Jobbetrieb problematisch.

## Kommandozeilen-Aufruf

Option | Beschreibung
--- | ---
`-config <pfad>` | Pfad zur Konfigurationsdatei
`-daemon` | Startet den Adapter als Daemon
`-debug <log-level>` | Setzt das Log-Level (Standard 2)
`-help` | Listet alle Flags

Ohne `-daemon` erwartet der Adapter den Aufruf aus einem Slurm-Hook im Prolog-/Epilog-Modus.

## Konfiguration

### Beispiel

Viele Felder sind optional und verwenden ohne Eintrag ihre Standardwerte. Das vollständige Beispiel steht in [adapter.json](examples/slurm/adapter.json):

```json
--8<-- "examples/slurm/adapter.json"
```

Für ein Testsystem genügt häufig die Anpassung von `ccRestUrl`, `ccRestJwt` und einem passenden `gpuPciAddrs`-Block. Hostnamen und GPU-Zuordnung müssen dabei zu den Collector-Tags passen.

### Referenz

Schlüssel | Optional | Beschreibung
--- | --- | ---
`pidFilePath` | ja | PID-Datei zur Vermeidung paralleler Startversuche.
`prepSockListenPath` | ja | PrEp-Socket des Daemons, als Unix- oder TCP-Socket, etwa `tcp:127.0.0.1:12345`.
`prepSockConnectPath` | ja | PrEp-Socket im Prolog-/Epilog-Modus, im selben Format.
`lastRunPath` | ja | Datei, deren Zeitstempel die letzte erfolgreiche Synchronisation festhält.
`slurmPollInterval` | ja | Sekunden zwischen Synchronisationsläufen ohne Hook-Ereignis.
`slurmQueryDelay` | ja | Wartezeit in Sekunden zwischen Hook-Aufruf und Slurm-Abfrage.
`slurmQueryMaxSpan` | ja | Maximale rückwirkende Abfragezeit in Sekunden; begrenzt große Nachimporte.
`slurmMaxRetries` | ja | Anzahl schneller Slurm-Abfrageversuche nach einem Hook-Ereignis.
`ccRestUrl` | nein | Basis-URL der Backend-REST-API ohne abschließenden Slash.
`ccRestJwt` | nein | Backend-JWT zur Authentifizierung.
`gpuPciAddrs` | ja | Zuordnung von Hostname-Regex zu sortierten GPU-PCI-Adressen für die NVML-Zuordnung.
`ignoreHosts` | ja | Regex für zu ignorierende Hosts. Trifft sie auf alle Hosts eines Jobs zu, wird der Job verworfen.

## Admin-Anleitung

### Build vorbereiten

Der Build benötigt Git, Make, Python 3 und Go ≥1.25.0. Der Checkout legt den Quellstand für die gezeigte Konfiguration fest. `GOTOOLCHAIN=local` verwendet die lokal installierte Go-Toolchain. Die folgenden Befehle laufen als Buildbenutzer auf dem Slurmcontroller, zunächst im geklonten Guide:

```bash
GUIDE_ROOT=$(pwd -P)
git clone https://github.com/ClusterCockpit/cc-slurm-adapter.git cc-slurm-adapter-src
cd cc-slurm-adapter-src
git checkout --detach a8131f9ffe635303b7457f019999ad64add99dd6
test "$(git rev-parse HEAD)" = a8131f9ffe635303b7457f019999ad64add99dd6
go version
GOTOOLCHAIN=local make
```

### Dienstkonto, Konfiguration und Unit

Die Installation erfolgt als root auf einem neuen Ziel. Die Slurm-Gruppe muss bereits existieren. Eine vorhandene Installation erfordert zuerst eine Zustandsprüfung; Konten und Konfigurationen dürfen nicht überschrieben werden. Beim Wechsel zur root-Sitzung müssen `GUIDE_ROOT` weiterhin auf den absoluten Guidepfad und das Arbeitsverzeichnis auf den soeben gebauten Adapter zeigen.

Vorher liegt eine geschützte Kopie des rohen Backendtokens aus `/opt/monitoring/cc-backend/apikey.txt` als `/root/cc-backend-apikey.txt` mit `0600` bereit. Die Übertragung erfolgt über den freigegebenen sicheren Weg; der JWT gehört nicht in die Kommandozeile.

```bash
getent group slurm
useradd --system --user-group --home-dir /opt/cc-slurm-adapter --no-create-home --shell /usr/sbin/nologin cc-slurm-adapter
install -d -m 0755 /opt/cc-slurm-adapter
install -m 0755 cc-slurm-adapter /opt/cc-slurm-adapter/cc-slurm-adapter
install -d -o root -g cc-slurm-adapter -m 0750 /etc/cc-slurm-adapter
install -o root -g cc-slurm-adapter -m 0640 "$GUIDE_ROOT/docs/examples/slurm/adapter.json" /etc/cc-slurm-adapter/config.json
install -o root -g cc-slurm-adapter -m 0640 /root/cc-backend-apikey.txt /etc/cc-slurm-adapter/apikey.txt
python3 - <<'CONFIG'
import json
from pathlib import Path
path = Path('/etc/cc-slurm-adapter/config.json')
config = json.loads(path.read_text())
config['ccRestJwt'] = Path('/etc/cc-slurm-adapter/apikey.txt').read_text().strip()
path.write_text(json.dumps(config, indent=2) + '\n')
CONFIG
install -m 0644 "$GUIDE_ROOT/docs/examples/slurm/cc-slurm-adapter.service" /etc/systemd/system/cc-slurm-adapter.service
```

In `/etc/cc-slurm-adapter/config.json` benötigen `ccRestUrl` und Host-/GPU-Zuordnung die Werte des Clusters. GPU-PCI-Adressen müssen mit den Collector-Tags übereinstimmen. Die Datei behält `0640` und `root:cc-slurm-adapter`. Das Dienstkonto liest über seine zusätzliche Gruppe; die Slurm-Gruppe erhält nur Zugriff auf Runtime-/Hooksocket und Zustandsverzeichnis.

Die vollständige Unit:

```ini
--8<-- "examples/slurm/cc-slurm-adapter.service"
```

`StateDirectory` erzeugt `/var/lib/cc-slurm-adapter`, `RuntimeDirectory` erzeugt `/run/cc-slurm-adapter`. Das Konto braucht Zugriff auf `sacct`, `squeue`, `scontrol` und die Accountingdaten. Der folgende Slurm-Grant ist standortabhängig; Account und AdminLevel müssen mit der Slurm-Administration abgestimmt sein. Anschließend kann root den Dienst aktivieren:

```bash
sacctmgr add user cc-slurm-adapter Account=root AdminLevel=operator
systemctl daemon-reload
systemctl enable --now cc-slurm-adapter.service
systemctl status cc-slurm-adapter.service
journalctl -u cc-slurm-adapter.service -n 100 --no-pager
```

Vor der Freigabe gehört ein [Testjob vom Start bis zur Archivierung](first_job.de.md) zur Prüfung. Benutzer, Hosts, Kern-/GPU-Zuordnung, Jobzustand und Metriken müssen im Backend stimmen.

Für die Diagnose ist `-debug 5` der gültige Parameter. Der normale Dienst muss dafür gestoppt sein. Der Diagnoseaufruf läuft mit `-daemon -debug 5 -config /etc/cc-slurm-adapter/config.json` im Dienstkontokontext. Ein zweiter Daemon darf nicht parallel laufen.

### Slurmctld Prolog/Epilog Hook (optional)

Ein Slurmctld-Hook kann den Adapter unmittelbar anstoßen. Dazu gehören folgende Ergänzungen in `slurm.conf`:

```ini
PrEpPlugins=prep/script
PrologSlurmctld=/some_path/hook.sh
EpilogSlurmctld=/some_path/hook.sh
```

Das zugehörige Beispielskript:

```bash
#!/bin/sh

/opt/cc-slurm-adapter/cc-slurm-adapter

exit 0
```

Beim Standard-PrEp-Socket `/run/cc-slurm-adapter/daemon.sock` benötigt der Hook keine Konfigurationsangabe. Abweichende Pfade erfordern `-config /pfad/zur/config.json` und passende Zugriffsrechte für `slurm`. Der Exit-Code des Skripts sollte immer `0` sein, damit ein vorübergehend nicht erreichbarer Adapter keine Slurm-Jobstarts blockiert.
