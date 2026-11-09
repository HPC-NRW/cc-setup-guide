# cc-metric-collector installieren

Der Collector läuft auf den Compute-Knoten. Dieses Kapitel baut **v0.8.4** mit den Headern von LIKWID **5.5.1** und richtet die Basisdateien ein. Der erste Test erfasst ausschließlich `loadavg`; eine LIKWID-Laufzeitbibliothek und privilegierte Hardwarezugriffe sind dafür nicht nötig.

Vorausgesetzt sind ein laufendes Backend und ein [passender Cluster- und Knoteneintrag](cluster_minimal.de.md). Vor der späteren Übertragung muss außerdem der [HTTPS-Endpunkt](https_setup.de.md) erreichbar sein. Die API muss die Quelladresse des Collectors zulassen, und eine geschützte Kopie des rohen JWT aus `cc-backend/apikey.txt` muss auf dem Zielsystem vorliegen. Die erste stdout-Prüfung sendet noch keine Daten an diesen Endpunkt.

## Quelle und Build

Auf dem AlmaLinux-9-Buildsystem sind Git, ein C-Compiler mit libc-Entwicklungsdateien, Go **mindestens 1.25.0**, Python3 und `install` erforderlich. Der Build läuft als normaler Benutzer. Go lädt nur die in `go.mod` und `go.sum` festgelegten Module; die LIKWID-5.5.1-Header stammen aus einem festen Quellstand. Eine passende vollständige LIKWID-Installation wird erst für die optionale Hardwareerfassung benötigt.

```bash
# Start in the guide checkout; use a normal build account.
GUIDE_DIR="$(pwd -P)"
BUILD_DIR="$HOME/build/cc-metric-collector-v0.8.4"
install -d "$BUILD_DIR"
git clone --branch v0.8.4 https://github.com/ClusterCockpit/cc-metric-collector.git "$BUILD_DIR/source"
cd "$BUILD_DIR/source"
test "$(git rev-parse HEAD)" = 6df8da8fe9e3fe9459aa0538b3d4027ad4f906b0
git clone --branch v5.5.1 https://github.com/RRZE-HPC/likwid.git "$BUILD_DIR/likwid-headers"
test "$(git -C "$BUILD_DIR/likwid-headers" rev-parse HEAD)" = a7dee7f35ccd68ce0717503a942238e740a01a1d
install -d collectors/likwid
install -m 0644 "$BUILD_DIR/likwid-headers/src/includes/"likwid*.h collectors/likwid/
export GOTOOLCHAIN=local
go version  # must be Go 1.25.0 or newer; no implicit toolchain download
go build -mod=readonly -o cc-metric-collector .
```

Bei einer Wiederholung zunächst das vorhandene Buildziel prüfen und einen neuen leeren Buildpfad wählen. Der Build erzeugt das Binary. Die Konfigurationsdateien stammen aus diesem Guide, nicht aus dem Quellverzeichnis des Collectors.

## Dateien und Grundkonfiguration

Die folgenden Schritte laufen als root auf dem Compute-Knoten, im Knotenimage oder auf dem vorgesehenen gemeinsamen Dateisystem. `GUIDE_DIR` und `BUILD_DIR` müssen dort auf die absoluten Pfade aus dem Buildschritt zeigen; ein Benutzerwechsel übernimmt Shellvariablen nicht automatisch. Das Beispiel installiert nach `/cluster/monitoring/cc-metric-collector`.

```bash
# Run these installation steps as root on the compute-node image/shared filesystem.
# Set GUIDE_DIR and BUILD_DIR to the absolute paths used by the build account.
COLLECTOR_DIR=/cluster/monitoring/cc-metric-collector
install -d -m 0750 "$COLLECTOR_DIR"
install -m 0755 "$BUILD_DIR/source/cc-metric-collector" "$COLLECTOR_DIR/"
install -m 0600 "$GUIDE_DIR/docs/examples/minimal/cc-metric-collector/"*.json "$COLLECTOR_DIR/"
install -m 0600 "$COLLECTOR_DIR/base-router.json" "$COLLECTOR_DIR/router.json"
cd "$COLLECTOR_DIR"
```

Auf einem gemeinsam genutzten Dateisystem müssen Verzeichnisse und Rechte zu den vorgesehenen Dienstkonten passen. Der HTTP-Token darf nicht für alle Clusterbenutzer lesbar sein. Der hier verwendete root-Dienst kann die Dateien mit Modus `0600` lesen. Das Basissetup aktiviert nur `loadavg`; zusätzliche Collectoren kommen später einzeln hinzu.

Die Hauptkonfiguration `config.json` lautet:

```json
--8<-- "examples/minimal/cc-metric-collector/config.json"
```

Alle referenzierten Dateien liegen im selben Arbeitsverzeichnis. `main.interval` legt das Erfassungsintervall fest, `main.duration` die Messdauer für messzeitabhängige Collectoren. `receivers.json` enthält `{}`. Die Testkonfiguration `config_stdout.json` verwendet `sinks_stdout.json` und schreibt ausschließlich ins Terminal. Die Rollen der Dateien zeigt der [Weg einer Metrik](metric_flow.de.md).

Für die HTTP-Übertragung fehlen in der Sinkdatei noch Cluster, Serveradresse und der **rohe** JWT aus `cc-backend/apikey.txt`. Das optionale Hilfsskript [configure-collector.py](scripts/configure-collector.py) setzt den `cluster`-Eintrag unter `add_tags` in `router.json` sowie `url` und `jwt` im HTTP-Sink in `sinks.json`. Es liest den JWT aus einer Datei, ohne ihn auszugeben, und setzt beide JSON-Dateien auf Modus `0600`. Die Collectorauswahl und die Backenddatei `cluster.json` bleiben unverändert.

Das Skript gehört zum Guide, nicht zum offiziellen Collector. Dieselben Felder lassen sich direkt in den JSON-Dateien bearbeiten; `chmod 0600 router.json sinks.json` setzt anschließend die Rechte.

```bash
# TOKEN_FILE is a securely transferred local copy of cc-backend/apikey.txt.
TOKEN_FILE=/root/cc-backend-apikey.txt
chmod 0600 "$TOKEN_FILE"
python3 "$GUIDE_DIR/docs/scripts/configure-collector.py" \
  --directory "$COLLECTOR_DIR" --cluster demo_cluster \
  --url 'https://monitoring.example.org/api/write/?cluster=demo_cluster' \
  --token-file "$TOKEN_FILE"
./cc-metric-collector -config ./config_stdout.json -once
```

`GUIDE_DIR` muss auch nach einem `cd` auf den Guide zeigen. Die HTTPS-Adresse, der Clustername und die Tokendatei im Beispiel sind durch die Werte der Installation zu ersetzen. Der vom Collector gesendete Hostname muss zum Knotenmuster in `cluster.json` passen; FQDN und Kurzname dürfen dabei nicht vermischt werden. Der Befehl `hostname` zeigt den Namen zum Abgleich.

Der stdout-Test sollte `load_one` und weitere loadavg-Werte für den erwarteten Cluster und Knoten zeigen. Im nächsten Schritt wird `load_one` in `cpu_load` umbenannt. Erst danach folgt die HTTP-Prüfung mit `./cc-metric-collector -config ./config.json -once`. Übertragungsfehler stehen im Collectorlog; die Zuordnung wird zusätzlich im Backend geprüft.

## Metrikliste auswählen

Ein Collector kann Dutzende Messwerte liefern. Für das Job-Monitoring ist meist nur ein Teil davon relevant; ein vollständiges Systemmonitoring ersetzt ClusterCockpit nicht. Die Auswahl sollte deshalb von den tatsächlich benötigten Auswertungen ausgehen.

Der Guide beginnt mit `cpu_load` und ergänzt typische Betriebs- und Fehlersuchmetriken. Weitere Möglichkeiten beschreibt die [Collectorübersicht im offiziellen Repository](https://github.com/ClusterCockpit/cc-metric-collector/blob/v0.8.4/collectors/README.md).

## Nächste Schritte

Ab hier stehen zwei alternative Wege zur ersten Metrik bereit:

- Der [Schnellstart](cc_metric_collector_quicksetup.de.md) übernimmt die fertige minimale Routerkonfiguration.
- [Erste Metrik einrichten](metrics.de.md) erklärt Erfassung, Umbenennung, Filterung und Backenddefinition einzeln.

Beide Wege führen zu [Collector als Dienst betreiben](collector_service.de.md) und zur gefüllten Node-Zeitreihe. Danach folgt die [Slurm-Anbindung](slurm_setup.de.md). [Weitere Metriken](more_metrics.de.md) und das [RUB-Beispielprofil](example_profiles.de.md) sind optionale Erweiterungen.
