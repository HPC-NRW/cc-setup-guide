# cc-metric-collector installieren

Der `cc-metric-collector` bildet die Datendrehscheibe auf den Compute-Knoten.  
Zur besseren Handhabung kann die Installation auf einem gesharten Filesystem erfolgen, z. B. `/cluster/monitoring/cc-metric-collector`.  
Für Build und Betrieb sollte der `bin`-Ordner von LIKWID im `PATH` liegen.

## Installation

```bash
git clone git@github.com:ClusterCockpit/cc-metric-collector.git
export PATH=/opt/likwid/bin:$PATH
make
```

Im Installationsverzeichnis entstehen folgende Dateien, die das Verhalten steuern:

- `config.json`: Pfade zu weiteren Dateien, Intervall für das Sampling.
- `collectors.json`: Welche Collectoren aktiv sind und wie sie konfiguriert werden.
- `router.json`: Transformationen (Umbenennen, Filtern, Einheiten ändern).
- `sinks.json`: Ziele (z. B. `cc-metric-store`).
- `receivers.json`: Optionale Weiterleitung eingehender Daten (im Basissetup leer halten).

## Grundkonfiguration

Für erste Tests kann `interval` in `config.json` temporär auf `10s` gesetzt werden.  
Die `receivers.json` bleibt leer (`{}`) und wir ergänzen eine zusätzliche Ausgabe über `stdout`:

```json
{
  "mystdout": {
    "type": "stdout",
    "meta_as_tags": ["unit"]
  }
}
```
Der Inhalt wird als `sinks_stdout.json` abgelegt; zusätzlich entsteht eine `config_stdout.json`, in der das ursprüngliche `sinks.json` durch `sinks_stdout.json` ersetzt wird.  
Mit `./cc-metric-collector -config ./config_stdout.json [-once]` lassen sich Metriken prüfen, ohne sie an den `cc-metric-store` zu senden.

Für den regulären Betrieb verweisen wir in `sinks.json` auf den `cc-metric-store` (Platzhalter ersetzen):

```json
{
  "cc-metric-store": {
    "type": "http",
    "url": "http://<monitoring-server>:8081/api/write/?cluster=__CLUSTER__",
    "jwt": "__APIKEY__",
    "precision": "s",
    "meta_as_tags": ["unit"],
    "idle_connection_timeout": "60s",
    "max_retries": 1,
    "timeout": "10s"
  }
}
```
`max_retries` und `timeout` können je nach Standort angepasst werden.

Eine minimale `router.json` sorgt dafür, dass jedes Sample mit dem gewünschten Clusternamen getaggt wird:

```json
{
  "add_tags": [
    {
      "key": "cluster",
      "value": "__CLUSTER__",
      "if": "*"
    }
  ],
  "interval_timestamp": false,
  "num_cache_intervals": 0,
  "hostname_tag": "hostname",
  "normalize_units": true
}
```

Die `collectors.json` startet leer (`{}`) und wird im nächsten Schritt gefüllt.

---

# Metrikliste auswählen

Bevor `cc-metric-collector` konfiguriert wird, lohnt sich eine kurze Bestandsaufnahme: Jeder Collector kann eine ganze Reihe von Messwerten liefern, schnell Dutzende Messwerte. Für viele dieser Werte ließen sich sinnvolle Nutzungsszenarien finden. Trotzdem ist ClusterCockpit in erster Linie ein *Job*-Monitoring und kein Ersatz für ein umfassendes Cluster-monitoring. Deshalb sollten ausschließlich Metriken erfasst werden, die tatsächlich genutzt werden.

Bei mehreren Roll-outs kam auf die Frage „Welche Metriken wollt ihr erheben?“ häufig die Antwort „Den Standard“ oder „Was alle haben“. Der vorliegende Guide greift genau diesen Standardumfang auf, weil er typische Betriebs- und Troubleshooting-Szenarien abdeckt. Wer über diesen Rahmen hinausgehen möchte, kann sich gezielt mit dem offiziellen Repository beschäftigen und dort prüfen, welche Collectoren zu den eigenen Anforderungen passen: [collectors/README.md](https://github.com/ClusterCockpit/cc-metric-collector/blob/main/collectors/README.md).

---

## Nächste Schritte

Für den weiteren Verlauf stehen zwei Wege bereit:

- **Schritt-für-Schritt-Anleitung:** [Erste Metrik einrichten](metrics.de.md) und anschließend [weitere Metriken & Thresholds](more_metrics.de.md). Ideal, um das Konzept hinter Collectoren, Router und Store im Detail zu verstehen.
- **Quick Setup:** [Schnellstart cc-metric-collector](cc_metric_collector_quicksetup.de.md) – eine kompakte Variante, die mit vorgefertigten Beispielen schnell in Betrieb geht.
