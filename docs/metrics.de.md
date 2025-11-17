# Schritt-für-Schritt: Erste Metrik

!!! info "Schritt-für-Schritt · Teil 1/2"
    Dieses Kapitel eröffnet die zweiteilige Schritt-für-Schritt-Reihe nach dem [cc-metric-collector Setup](cc_metric_collector_setup.de.md).  
    Im Anschluss geht es mit [Schritt-für-Schritt: Weitere Metriken](more_metrics.de.md) weiter.

Dieser Abschnitt ist Teil der Schritt-für-Schritt-Anleitung nach dem Setup des `cc-metric-collector`.  
Um Metriken hinzuzufügen, werden immer drei Schritte benötigt:
1. Metrik mit `cc-metric-collector` erheben.
2. Im `cc-metric-store` die `config.json` anpassen, damit die Werte gespeichert werden.
3. in `cc-backend/var/job-archive/$CLUSTERNAME/` die `cluster.json` erweitern, damit die Metrik im Webinterface angezeigt wird.

Eine Übersicht über alle Collectoren erhält man [im offiziellen Git-Repo](https://github.com/ClusterCockpit/cc-metric-collector/blob/main/collectors/README.md)

Wir beginnen mit einer einfach Metrik: `cpu_load`, diese ist auch verpflichtend.
`cpu_load` wird mit dem Collector `loadavg` erhoben.
Wir tragen `loadavg` in die `collectors.json` ein:
```json
{
  "loadavg" : {}
}
```
und führen `./cc-metric-collector -config ./config_stdout.json -once` aus und erhalte folgende Ausgabe:
```bash
load_one,cluster=testcluster,hostname=cpu001,type=node value=0.27 1752156889208064633
load_five,cluster=testcluster,hostname=cpu001,type=node value=0.82 1752156889208064633
load_fifteen,cluster=testcluster,hostname=cpu001,type=node value=0.94 1752156889208064633
proc_run,cluster=testcluster,hostname=cpu001,type=node value=1i 1752156889208064633
proc_total,cluster=testcluster,hostname=cpu001,type=node value=1712i 1752156889208064633
```
Jede Zeile ist eine Message im Lineprotocol Format an den `cc-metric-store`. Die erste Spalte enthält den Metriknamen, Clusternamen, Hostnamen und den Typ der Metrik (neben Node sind auch Socket, MemoryDomain (=NUMA Domain) und hwthread (=CPU Core) möglich). Bei anderen Metriken taucht hier auch die Einheit und wenn die Granularität feiner als `Node` ist ein Identifier auf. Die zweite Spalte enthält den Wert, das endständige `i` markiert einen Wert als Integer. Die dritte Spalte ist der Unix Timestamp in Nanosekunden.

Wie wir sehen erhebt der Collector fünf Werte: Den Load Average über 1, 5 und 15 Minuten, die Anzahl der laufenden Prozesse und die Gesamtzahl der Prozesse. Wir wollen `load_one` für die Metrik `cpu_load` erheben und die anderen Messages verwerfen. Daher müssen wir jetzt zwei Dinge tun: Die unerwünschten Werte herausfiltern und `load_one` in `cpu_load` umbenennen.

Dafür nutzen wir den `messageProcessor` aus der `cc-lib`, der über die `router.json` konfiguriert wird. Wir fügen "process_messages" ein:

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
  "normalize_units": true,
  "process_messages": {
    "hostname_tag": "hostname",
    "rename_messages": {
      "load_one": "cpu_load"
    },
    "drop_messages_if": [
      "!(name in [`load_one`])"
    ]
  }
}
```

Die Liste in `drop_messages_if` wird als Positivliste für alle weiteren Collectoren benutzt.

Wir erhalten jetzt nur noch unsere gewünschte Metrik mit dem neuen Namen:
```bash
cpu_load,cluster=testcluster,hostname=cpu001,type=node value=1.58 1752158115922836909
```

Wichtig: Beim Verwerfen der Metrik muss der originale Name und nicht der umbenannte Name eingetragen werden!

Anmerkung:
Eine weitere Funktion des `messageProcessor`, die wir im weiteren Verlauf noch benutzen werden, ist das Ändern der Einheit. Wenn wir z.B. den belegten Arbeitsspeicher in Byte erheben, in unserem Webinterface aber in GB haben wollen, erreichen wir das auf folgende Weise:

```json
{
  "process_messages": {
    "change_unit_prefix": {
      "name == 'mem_used'": "G"
    }
  }
}
```

Die Metrik `cpu_load` wird jetzt an den `cc-metric-store` gesendet. Damit dieser die Werte auch speichert, müssen wir einen Eintrag in der `config.json` auf dem Monitoring-Server vornehmen:

```json
{
  "metrics": {
    "cpu_load": {
      "frequency": 60,
      "aggregation": "avg"
    }
  }
}
```

`frequency` gibt an, in welchem Interval der store die Werte erwartet. Dieser Wert sollte also mit `interval` aus der `config.json` von `cc-metric-collector` übereinstimmen.
Für die `aggregation` stehen 3 verschiedene Typen zur Verfügung: `avg`, `sum` und `nil`.
Wir wählen `avg` für Zustands- oder Intensitätswerte pro Einheit, wie z.B. Frequenz, CPU/GPU-Auslastung oder Temperatur und `sum` für Werte, die sich addieren lassen, wie FLOPS oder Energieverbräuche.

---
Weiter mit Schritt 2: [Weitere Metriken & Thresholds](more_metrics.de.md).
