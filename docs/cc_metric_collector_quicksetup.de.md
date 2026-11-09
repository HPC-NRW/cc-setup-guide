# cc-metric-collector Quick Setup

Dieser kurze Weg übernimmt die fertige Minimalkonfiguration und führt bis zur ersten Node-Zeitreihe. Voraussetzungen sind die [Collectorinstallation](cc_metric_collector_setup.de.md), ein [passender Cluster- und Knoteneintrag](cluster_minimal.de.md) und ein vom Compute-Knoten erreichbarer [HTTPS-Endpunkt](https_setup.de.md) mit erlaubter API-Quelladresse und gültigem JWT.

## Minimaler Start ohne Hardwareabhängigkeiten

Das Minimalprofil erfasst nur `loadavg`; es benötigt keine LIKWID-Laufzeitbibliothek und keine privilegierten Hardwarezugriffe. Hauptkonfiguration und die leere `receivers.json` stammen bereits aus dem Setup.

Die folgenden Befehle laufen als root auf dem Compute-Knoten. `GUIDE_DIR`, `COLLECTOR_DIR` und `TOKEN_FILE` müssen weiterhin auf den Guide, das Collectorverzeichnis und die geschützte Tokendatei aus dem Setup zeigen. Clustername und HTTPS-Adresse sind durch die Werte der Installation zu ersetzen.

```bash
install -m 0600 "$GUIDE_DIR/docs/examples/minimal/cc-metric-collector/router.json" "$COLLECTOR_DIR/router.json"
python3 "$GUIDE_DIR/docs/scripts/configure-collector.py" \
  --directory "$COLLECTOR_DIR" --cluster demo_cluster \
  --url 'https://monitoring.example.org/api/write/?cluster=demo_cluster' \
  --token-file "$TOKEN_FILE"
cd "$COLLECTOR_DIR"
./cc-metric-collector -config ./config_stdout.json -once
./cc-metric-collector -config ./config.json -once
```

Das optionale [configure-collector.py](scripts/configure-collector.py) gehört zu diesem Guide, nicht zum offiziellen Collector. Alternativ lassen sich die Dateien wie unter [Collector einrichten](cc_metric_collector_setup.de.md) direkt bearbeiten: der Clusterwert im `add_tags`-Eintrag der `router.json` sowie URL und roher JWT im HTTP-Sink der `sinks.json`.

Die stdout-Ausgabe muss `cpu_load` mit dem erwarteten Cluster und Hostnamen enthalten. Der zweite Aufruf überträgt eine Messung an das Backend; Übertragungsfehler stehen im Collectorlog. Der vorhandene `cpu_load`-Eintrag in `cluster.json` muss dazu passen. Ein erfolgreicher `-once`-Aufruf prüft eine einzelne Messung und ersetzt noch keinen Dauerbetrieb.

## Produktivbetrieb

Der nächste Schritt ist [Collector als Dienst betreiben](collector_service.de.md). Dort stehen die gemeinsame systemd-Unit, ihre Aktivierung und die Prüfung mehrerer Messintervalle. Anschließend zeigt die [Node-Ansicht](metrics.de.md#erwartetes-ergebnis-im-webinterface), ob die Zeitreihe beim richtigen Knoten ankommt. Für fehlende Daten hilft [Metriken empfangen und anzeigen](metric_receive_display.de.md).

Nach dieser Prüfung folgen die [Slurm-Anbindung](slurm_setup.de.md) und ein [Testjob](first_job.de.md). Damit ist der minimale Weg vom Messwert zum Job-Monitoring vollständig.

## Optionale Erweiterungen

Das [RUB-Beispielprofil](example_profiles.de.md) enthält eine vollständige Zen4-Konfiguration mit `collectors.json`, Routerregeln, Gerätefiltern und einer Collectorübersicht. Diese Einstellungen sind standortspezifisch und setzen passende Geräte, Dateisysteme und Zugriffsrechte voraus. Auch das vollständige Profil verwendet nur [Einheiten aus dem offiziellen Schema](units.de.md#strikte-schemaprufung) und besteht die Schemaprüfung ohne Ausnahmen.

<span id="collectorsjson-beispiel-fur-amd-zen-4"></span>
<span id="collector-ubersicht-nach-kategorien"></span>
<span id="cpu-load"></span>
<span id="memory-numa"></span>
<span id="storage-lokal-lustre-nfs"></span>
<span id="netzwerk"></span>
<span id="node-leistung"></span>
<span id="gpu-optional"></span>

<span id="routerjson"></span>
<span id="erklarung-der-wichtigsten-verarbeitungsschritte"></span>

[Weitere Metriken](more_metrics.de.md) erklärt die einzelnen Erweiterungen für CPU, Speicher, Datenträger, Netzwerk, Dateisysteme und GPUs. [LIKWID-Metriken](likwid_metrics.de.md) beschreibt die Hardwareereignisse.
