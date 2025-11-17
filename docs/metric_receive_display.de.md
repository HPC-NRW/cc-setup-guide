# Metriken empfangen und anzeigen

Der im Abschnitt [cc-metric-collector einrichten](cc_metric_collector_setup.de.md) konfigurierte Collector sendet zwar bereits Werte, allerdings akzeptieren `cc-metric-store` und `cc-backend` sie nur, wenn sie dort explizit hinterlegt sind.  
In diesem Abschnitt wird beschrieben, wie neue oder geänderte Metriken auf dem Monitoring-Server hinterlegt werden, damit

1. der `cc-metric-store` die Daten entgegennimmt und
2. das Webinterface (`cc-backend`) die Metriken über Einträge in der `cluster.json` erkennt.

> **Kurzfassung:** Jede neue Metrik benötigt genau zwei Einträge: einen in der `cc-metric-store/config.json` und einen in der `cluster.json`. Erst dann erscheinen sie im Monitoring.

---

## 1. cc-metric-store: `config.json` ergänzen

Dateipfad (Standardinstallation gemäß Guide):  
`$INSTALL_DIR/cc-metric-store/config.json`

Im JSON wird in `metrics` für jede neue Metrik ein Eintrag ergänzt:

```json
"cpu_load": {
  "frequency": 60,
  "aggregation": "avg"
}
```

**Felder:**
- `frequency`: Erwartetes Intervall in Sekunden. Dieser Wert muss zu `interval` aus `config.json` des `cc-metric-collector` passen (Standard im Guide: 60 s).
- `aggregation`: Legt fest, wie Messpunkte über die Hierarchie (`hwthreads` -> `socket` -> `node`) zusammengeführt werden (`avg`, `sum`, `nil`). Üblich ist `avg` für Zustandsgrößen (Auslastung, Temperatur), `sum` für zählende Größen (FLOPS, Energie, Bandbreite) und `nil`, wenn keine Aggregation stattfinden soll.

Nach dem Speichern muss `cc-metric-store` neu gestartet werden:

```bash
systemctl restart cc-metric-store.service
```

---

## 2. cc-backend: `cluster.json` aktualisieren

Dateipfad:  
`$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/cluster.json`

`cluster.json` beschreibt sowohl die Subcluster als auch alle Metriken, die im Webinterface angezeigt werden sollen. Jede Metrik steht als Objekt innerhalb des Arrays `metricConfig`.

### Minimaler Eintrag

```json
{
  "name": "cpu_load",
  "unit": { "base": "" },
  "scope": "node",
  "aggregation": "avg",
  "timestep": 60,
  "peak": 48,
  "normal": 48,
  "caution": 10,
  "alert": 1
}
```

**Wichtige Felder:**
- `name`: Muss exakt mit dem Namen übereinstimmen, der nach dem Routing (z. B. `rename_messages`) publiziert wird.
- `unit`: Basiseinheit (optional `prefix`: `"M"`, `"G"`, ...), konsistent zu den in `router.json` gesetzten Einheiten.
- `scope`: Granularität (`node`, `socket`, `hwthread`, `memoryDomain`, `accelerator`).
- `aggregation`: Üblicherweise `avg` für Zustände oder `sum` für kumulative Metriken.
- `timestep`: Anzeigeintervall (in Sekunden), sollte `frequency` im Metric-Store entsprechen.
- `peak`, `normal`, `caution`, `alert`: Schwellenwerte für das UI. Graphen zwischen `normal` und `caution` bleiben neutral. Werte zwischen `caution` und `alert` werden gelb markiert (= genauer hinschauen), Werte unter `alert` rot (= sofort reagieren).

### Konfigurationsmöglichkeiten

#### Alert-Logik umkehren
Durch Setzen von `"lowerIsBetter": true` wird der Alarm nicht bei zu kleinen, sondern bei zu hohen Werten ausgelöst. Das ist z. B. für `cpu_load_core`, Netzwerkbandbreiten oder IOPS sinnvoll.

#### Metrik nur für bestimmte Subcluster
Um z. B. GPU-Metriken nur für Subcluster anzuzeigen, die auch GPUs verbaut haben, können Metriken aus einzelnen Subclustern entfernt werden:

```json
            "name": "nv_compute_processes",
            "unit": {
                "base": "processes"
            },
            "scope": "accelerator",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100, 
            "normal": 50,
            "caution": 80,
            "alert": 90,
            "subClusters": [
                {
                    "name": "cpu",
                    "remove": true 
                },   
                {    
                    "name": "cpu_abs2",
                    "remove": true 
                },   
                {    
                    "name": "fatcpu",
                    "remove": true 
                }
            ]
        },
```

**Anmerkung:** Gelöschte Metriken sind in der Jobview nicht mehr sichtbar und können bei der Metrikauswahl auch nicht ausgewählt werden. In der Node-View für Administratoren tauchen blaue Felder auf, die darauf hinweisen, dass die Metrik für diesen Subcluster deaktiviert ist:

![Deaktivierte Metrik Hinweis](img/removed_metric.png)


#### Unterschiedliche Thresholds für verschiedene Subcluster
Bei unterschiedlicher Ausstattung mit Cores, Memory, GPU-Memory usw. können die Thresholds pro Subcluster angegeben werden. Alle nicht genannten Subcluster erhalten die Konfiguration aus dem Hauptteil:

```json
        {
            "name": "cpu_load",
            "unit": {
                "base": "load"
            },
            "scope": "node",
            "aggregation": "avg",
            "timestep": 60,
            "peak": 48,
            "normal": 48,
            "caution": 10,
            "alert": 1,
            "subClusters": [
                {
                    "name": "fatcpu",
                    "peak": 96,
                    "normal": 96,
                    "caution": 10,
                    "alert": 1
                },
                {
                    "name": "fatgpu",
                    "peak": 96,
                    "normal": 96,
                    "caution": 10,
                    "alert": 1
                }
            ]
        },
```

#### Footprint-Metriken definieren
Um die Metriken zu definieren, die im Footprint und im Polar Plot angezeigt werden, wird `"footprint": "avg"` (oder `sum`, je nach `aggregation`) ergänzt.

Darstellung im Footprint:

![Footprint Beispiel](img/footprint.png)

Darstellung im Polar Plot:

![Polar Plot Beispiel](img/polar.png)

Hat die Metrik den Eintrag `"lowerIsBetter": true`, wird dies durch einen Pfeil nach links dargestellt.
In diesem Beispiel wurden ausschließlich Metriken verwendet, deren Scope `hwthread` ist, da nur diese Metriken bei shared Nodes aussagekräftig sind.

#### Energy Footprint definieren
Um festzulegen, ob eine Metrik in den Energy Footprint einfließt, wird `"energy": "power"` ergänzt, wenn die Einheit Watt ist, oder `"energy": "energy"`, wenn die Einheit Joule ist.
Aus allen `energy`-Metriken wird ein Gesamtverbrauch errechnet.

Für CPU-only-Jobs:

![Energy Footprint CPU-only](img/energy.png)

Wenn GPUs zum Einsatz kommen, wird deren Verbrauch einzeln aufgeführt:

![Energy Footprint mit GPU](img/energy_gpu.png)

Auf Intel-Systemen ist es ebenfalls möglich, den Stromverbrauch des Arbeitsspeichers auszulesen, bei AMD stehen keine Counter dafür zur Verfügung.

Optional kann in der `config.json` von `cc-backend` der Parameter `emission-constant` gesetzt werden. Er beschreibt den CO₂-Faktor des Rechenzentrumsstroms in g/kWh. Auf Basis dieses Werts und des gemessenen Energieverbrauchs wird automatisch die (theoretische) CO₂-Emission pro Job berechnet und im UI angezeigt.

### Änderungen aktivieren

Damit die Änderungen wirksam werden, muss `cc-backend` neu gestartet werden:
```bash
systemctl restart clustercockpit.service
```

---

## 3. Prüfen, ob Metriken ankommen
Für jeden Host, auf dem `cc-metric-collector` läuft, sollten sich nach und nach die Graphen mit Daten füllen.
Falls stattdessen ein gelbes Feld angezeigt wird, kommen keine Daten an:

![Hinweis fehlende Metrik](img/missing_metric.png)

Es sollte überprüft werden, ob die Metrik vom `cc-metric-collector` mit *diesem* Namen gesendet und vom `cc-metric-store` empfangen wird.


<details>
<summary><strong>Beispiel: vollständige `cc-metric-store` config.json (RUB)</strong></summary>

```json
{
  "metrics": {
    "cpu_load": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "cpu_user": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "cpu_load_core": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "mem_used": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "mem_bw": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "net_bytes_in": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "net_bytes_out": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "net_pkts_in": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "net_pkts_out": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "disk_free": {
      "frequency": 60,
      "aggregation": null
    },
    "io_reads": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "io_writes": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "lustre_open": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "lustre_close": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "lustre_statfs": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "lustre_read_bw": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "lustre_write_bw": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "nfs4_open": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "nfs4_close": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "nfsio_nread": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "nfsio_nwrite": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "numastats_interleave_hit": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "numastats_local_node": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "numastats_numa_foreign": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "numastats_numa_hit": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "numastats_numa_miss": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "numastats_other_node": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "ib_recv": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "ib_xmit": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "ib_recv_pkts": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "ib_xmit_pkts": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "nv_compute_processes": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "acc_utilization": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "acc_mem_used": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "acc_power": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "acc_mem_util": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "clock": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "ipc": {
      "frequency": 60,
      "aggregation": "avg"
    },
    "core_power": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "flops_any": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "node_total_power": {
      "frequency": 60,
      "aggregation": "sum"
    },
    "job_mem_used": {
      "frequency": 60,
      "aggregation": "sum"
    }
  },
  "checkpoints": {
    "interval": "12h",
    "directory": "/opt/monitoring/cc-metric-store/var/checkpoints",
    "restore": "48h"
  },
  "archive": {
    "interval": "50h",
    "directory": "/opt/monitoring/cc-metric-store/var/archive"
  },
  "http-api": {
    "address": "0.0.0.0:8081",
    "https-cert-file": null,
    "https-key-file": null
  },
  "retention-in-memory": "48h",
  "jwt-public-key": "XXX"
}
```

</details>

<details>
<summary><strong>Beispiel: vollständige `cluster.json` (RUB)</strong></summary>

```json
{
    "name": "elysium",
    "metricConfig": [
        {
            "name": "cpu_load",
            "unit": {
                "base": "load"
            },
            "scope": "node",
            "aggregation": "avg",
            "timestep": 60,
            "peak": 48,
            "normal": 48,
            "caution": 10,
            "alert": 1,
            "subClusters": [
                { "name": "fatcpu", "peak": 96, "normal": 96, "caution": 10, "alert": 1 },
                { "name": "fatgpu", "peak": 96, "normal": 96, "caution": 10, "alert": 1 }
            ]
        },
        {
            "name": "cpu_user",
            "unit": {
                "base": "%",
                "description": "Percentage of CPU time spent in user mode"
            },
            "scope": "hwthread",
            "aggregation": "avg",
            "footprint": "avg",
            "timestep": 60,
            "peak": 100,
            "normal": 70,
            "caution": 50,
            "alert": 30
        },
        {
            "name": "cpu_load_core",
            "unit": {
                "base": "load"
            },
            "scope": "hwthread",
            "aggregation": "avg",
            "timestep": 60,
            "peak": 12,
            "normal": 1.1,
            "caution": 2,
            "alert": 3,
            "lowerIsBetter": true
        },
        {
            "name": "mem_used",
            "unit": {
                "base": "B",
                "prefix": "G"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 384,
            "normal": 384,
            "caution": 384,
            "alert": 384,
            "subClusters": [
                { "name": "fatcpu", "peak": 2304, "normal": 2304, "caution": 2304, "alert": 2304 },
                { "name": "cpu_abs2", "peak": 768, "normal": 768, "caution": 768, "alert": 768 },
                { "name": "fatgpu", "peak": 1152, "normal": 1152, "caution": 1152, "alert": 1152 },
                { "name": "vis", "peak": 1152, "normal": 1152, "caution": 1152, "alert": 1152 }
            ]
        },
        {
            "name": "mem_bw",
            "unit": {
                "base": "B/s",
                "prefix": "G"
            },
            "scope": "socket",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 1000,
            "normal": 350,
            "caution": 350,
            "alert": 350
        },
        {
            "name": "net_bytes_in",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "lowerIsBetter": true,
            "peak": 125,
            "normal": 10,
            "caution": 20,
            "alert": 40
        },
        {
            "name": "net_bytes_out",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "lowerIsBetter": true,
            "timestep": 60,
            "peak": 125,
            "normal": 10,
            "caution": 20,
            "alert": 40
        },
        {
            "name": "net_pkts_in",
            "unit": {
                "base": "packets/s"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "net_pkts_out",
            "unit": {
                "base": "packets/s"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "disk_free",
            "unit": {
                "base": "B",
                "prefix": "G"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 3755,
            "normal": 1878,
            "caution": 939,
            "alert": 376,
            "subClusters": [
                { "name": "cpu", "peak": 876, "normal": 876, "caution": 219, "alert": 88 },
                { "name": "cpu_abs2", "peak": 3755, "normal": 3755, "caution": 939, "alert": 376 },
                { "name": "gpu", "peak": 1836, "normal": 1836, "caution": 459, "alert": 184 },
                { "name": "fatcpu", "peak": 1836, "normal": 1836, "caution": 459, "alert": 184 },
                { "name": "fatgpu", "peak": 1836, "normal": 1836, "caution": 459, "alert": 184 },
                { "name": "vis", "peak": 876, "normal": 876, "caution": 219, "alert": 88 }
            ]
        },
        {
            "name": "io_reads",
            "unit": {
                "base": "ops/s"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "io_writes",
            "unit": {
                "base": "ops/s"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "lustre_open",
            "unit": {
                "base": "operations"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 50000,
            "normal": 25000,
            "caution": 40000,
            "alert": 45000
        },
        {
            "name": "lustre_close",
            "unit": {
                "base": "operations"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 50000,
            "normal": 25000,
            "caution": 40000,
            "alert": 45000
        },
        {
            "name": "lustre_statfs",
            "unit": {
                "base": "operations"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 50,
            "caution": 80,
            "alert": 90
        },
        {
            "name": "lustre_read_bw",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 60000,
            "normal": 60000,
            "caution": 60000,
            "alert": 60000
        },
        {
            "name": "lustre_write_bw",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 60000,
            "normal": 60000,
            "caution": 60000,
            "alert": 60000
        },
        {
            "name": "nfs4_open",
            "unit": {
                "base": "operations"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "nfs4_close",
            "unit": {
                "base": "operations"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "nfsio_nread",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "nfsio_nwrite",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "numastats_interleave_hit",
            "unit": {
                "base": "count/s"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "numastats_local_node",
            "unit": {
                "base": "count/s"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "numastats_numa_foreign",
            "unit": {
                "base": "count/s"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "numastats_numa_hit",
            "unit": {
                "base": "count/s"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "numastats_numa_miss",
            "unit": {
                "base": "count/s"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "numastats_other_node",
            "unit": {
                "base": "count/s"
            },
            "scope": "memoryDomain",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 100,
            "caution": 100,
            "alert": 100
        },
        {
            "name": "ib_recv",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 12000,
            "normal": 10000,
            "caution": 0,
            "alter": 0
        },
        {
            "name": "ib_xmit",
            "unit": {
                "base": "B/s",
                "prefix": "M"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 12000,
            "normal": 10000,
            "caution": 0,
            "alter": 0
        },
        {
            "name": "ib_recv_pkts",
            "unit": {
                "base": "packets/s"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 1100000,
            "normal": 800000,
            "caution": 0,
            "alert": 0
        },
        {
            "name": "ib_xmit_pkts",
            "unit": {
                "base": "packets/s"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 1100000,
            "normal": 800000,
            "caution": 0,
            "alert": 0
        },
        {
            "name": "nv_compute_processes",
            "unit": {
                "base": "processes"
            },
            "scope": "accelerator",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100,
            "normal": 50,
            "caution": 80,
            "alert": 90,
            "subClusters": [
                { "name": "cpu", "remove": true },
                { "name": "cpu_abs2", "remove": true },
                { "name": "fatcpu", "remove": true }
            ]
        },
        {
            "name": "acc_utilization",
            "unit": {
                "base": "%",
                "description": "GPU Utilization Percentage"
            },
            "scope": "accelerator",
            "aggregation": "avg",
            "footprint": "avg",
            "timestep": 60,
            "peak": 100,
            "normal": 90,
            "caution": 70,
            "alert": 60,
            "subClusters": [
                { "name": "cpu", "remove": true },
                { "name": "cpu_abs2", "remove": true },
                { "name": "fatcpu", "remove": true }
            ]
        },
        {
            "name": "acc_mem_used",
            "unit": {
                "base": "B",
                "prefix": "G"
            },
            "scope": "accelerator",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 80,
            "normal": 24,
            "caution": 38,
            "alert": 45,
            "subClusters": [
                { "name": "cpu", "remove": true },
                { "name": "cpu_abs2", "remove": true },
                { "name": "fatcpu", "remove": true },
                { "name": "gpu", "scope": "accelerator", "aggregation": "sum", "timestep": 60, "peak": 24 },
                { "name": "fatgpu", "scope": "accelerator", "aggregation": "sum", "timestep": 60, "peak": 80 },
                { "name": "vis", "scope": "accelerator", "aggregation": "sum", "timestep": 60, "peak": 48 }
            ]
        },
        {
            "name": "acc_power",
            "unit": {
                "base": "W"
            },
            "scope": "accelerator",
            "aggregation": "sum",
            "timestep": 60,
            "energy": "power",
            "peak": 300,
            "normal": 150,
            "caution": 250,
            "alert": 280,
            "subClusters": [
                { "name": "cpu", "remove": true },
                { "name": "cpu_abs2", "remove": true },
                { "name": "fatcpu", "remove": true },
                { "name": "gpu", "scope": "accelerator", "aggregation": "sum", "energy": "power", "timestep": 60, "peak": 165 },
                { "name": "fatgpu", "scope": "accelerator", "aggregation": "sum", "energy": "power", "timestep": 60, "peak": 700 },
                { "name": "vis", "scope": "accelerator", "aggregation": "sum", "energy": "power", "timestep": 60, "peak": 300 }
            ]
        },
        {
            "name": "acc_mem_util",
            "unit": {
                "base": "%",
                "description": "GPU Memory Utilization Percentage"
            },
            "scope": "accelerator",
            "aggregation": "avg",
            "timestep": 60,
            "peak": 100,
            "normal": 80,
            "caution": 50,
            "alert": 20,
            "subClusters": [
                { "name": "cpu", "remove": true },
                { "name": "cpu_abs2", "remove": true },
                { "name": "fatcpu", "remove": true }
            ]
        },
        {
            "name": "clock",
            "unit": {
                "base": "MHz"
            },
            "scope": "hwthread",
            "aggregation": "avg",
            "timestep": 60,
            "peak": 4000,
            "normal": 4000,
            "caution": 4600,
            "alert": 4700
        },
        {
            "name": "ipc",
            "unit": {
                "base": "IPC"
            },
            "scope": "hwthread",
            "aggregation": "avg",
            "footprint": "avg",
            "timestep": 60,
            "peak": 6,
            "normal": 6,
            "caution": 1,
            "alert": 0
        },
        {
            "name": "core_power",
            "unit": {
                "base": "W"
            },
            "scope": "hwthread",
            "aggregation": "sum",
            "energy": "power",
            "timestep": 60,
            "peak": 280,
            "normal": 240,
            "caution": 300,
            "alert": 330
        },
        {
            "name": "flops_any",
            "unit": {
                "base": "FLOPS",
                "prefix": "G"
            },
            "scope": "hwthread",
            "aggregation": "sum",
            "footprint": "avg",
            "timestep": 60,
            "peak": 3000,
            "normal": 3000,
            "caution": 100,
            "alert": 50
        },
        {
            "name": "node_total_power",
            "unit": {
                "base": "W"
            },
            "scope": "node",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 6000,
            "normal": 5000,
            "caution": 0,
            "alert": 0,
            "subClusters": [
                { "name": "cpu", "peak": 600, "normal": 400, "caution": 0, "alert": 0 },
                { "name": "cpu_abs2", "peak": 600, "normal": 400, "caution": 0, "alert": 0 },
                { "name": "gpu", "peak": 2000, "normal": 1500, "caution": 0, "alert": 0 },
                { "name": "fatcpu", "peak": 1200, "normal": 1000, "caution": 0, "alert": 0 },
                { "name": "fatgpu", "peak": 6000, "normal": 5000, "caution": 0, "alert": 0 },
                { "name": "vis", "peak": 700, "normal": 500, "caution": 0, "alert": 0 }
            ]
        },
        {
            "name": "job_mem_used",
            "unit": {
                "base": "B",
                "prefix": "G"
            },
            "scope": "hwthread",
            "aggregation": "sum",
            "timestep": 60,
            "subClusters": [
                { "name": "cpu", "peak": 8, "normal": 6, "caution": 7, "alert": 7 },
                { "name": "cpu_abs2", "peak": 16, "normal": 12, "caution": 14, "alert": 15 },
                { "name": "gpu", "peak": 8, "normal": 6, "caution": 7, "alert": 7 },
                { "name": "fatcpu", "peak": 24, "normal": 19, "caution": 21, "alert": 22 },
                { "name": "fatgpu", "peak": 12, "normal": 9, "caution": 10, "alert": 11 },
                { "name": "vis", "peak": 24, "normal": 19, "caution": 21, "alert": 22 }
            ]
        }
    ],
    "subClusters": [
        {
            "name": "cpu",
            "processorType": "AMD EPYC 9254 24-Core Processor                ",
            "socketsPerNode": 2,
            "coresPerSocket": 24,
            "threadsPerCore": 1,
            "flopRateScalar": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 517
            },
            "flopRateSimd": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 3175
            },
            "memoryBandwidth": {
                "unit": {
                    "base": "B/s",
                    "prefix": "G"
                },
                "value": 591
            },
            "nodes": "cpu[001-284]",
            "topology": {
                "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
                "socket": [
                    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23],
                    [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47]
                ],
                "memoryDomain": [
                    [0,1,2,3,4,5],
                    [6,7,8,9,10,11],
                    [12,13,14,15,16,17],
                    [18,19,20,21,22,23],
                    [24,25,26,27,28,29],
                    [30,31,32,33,34,35],
                    [36,37,38,39,40,41],
                    [42,43,44,45,46,47]
                ],
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]]
            }
        },
        {
            "name": "cpu_abs2",
            "processorType": "AMD EPYC 9254 24-Core Processor                ",
            "socketsPerNode": 2,
            "coresPerSocket": 24,
            "threadsPerCore": 1,
            "flopRateScalar": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 517
            },
            "flopRateSimd": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 3175
            },
            "memoryBandwidth": {
                "unit": {
                    "base": "B/s",
                    "prefix": "G"
                },
                "value": 591
            },
            "nodes": "cpu[285-336]",
            "topology": {
                "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
                "socket": [
                    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23],
                    [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47]
                ],
                "memoryDomain": [
                    [0,1,2,3,4,5],
                    [6,7,8,9,10,11],
                    [12,13,14,15,16,17],
                    [18,19,20,21,22,23],
                    [24,25,26,27,28,29],
                    [30,31,32,33,34,35],
                    [36,37,38,39,40,41],
                    [42,43,44,45,46,47]
                ],
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]]
            }
        },
        {
            "name": "fatcpu",
            "processorType": "AMD EPYC 9454 48-Core Processor                ",
            "socketsPerNode": 2,
            "coresPerSocket": 48,
            "threadsPerCore": 1,
            "flopRateScalar": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 972
            },
            "flopRateSimd": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 5809
            },
            "memoryBandwidth": {
                "unit": {
                    "base": "B/s",
                    "prefix": "G"
                },
                "value": 778
            },
            "nodes": "fatcpu[001-013]",
            "topology": {
                "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95],
                "socket": [
                    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
                    [48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95]
                ],
                "memoryDomain": [
                    [0,1,2,3,4,5],
                    [6,7,8,9,10,11],
                    [12,13,14,15,16,17],
                    [18,19,20,21,22,23],
                    [24,25,26,27,28,29],
                    [30,31,32,33,34,35],
                    [36,37,38,39,40,41],
                    [42,43,44,45,46,47],
                    [48,49,50,51,52,53],
                    [54,55,56,57,58,59],
                    [60,61,62,63,64,65],
                    [66,67,68,69,70,71],
                    [72,73,74,75,76,77],
                    [78,79,80,81,82,83],
                    [84,85,86,87,88,89],
                    [90,91,92,93,94,95]
                ],
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47],[48],[49],[50],[51],[52],[53],[54],[55],[56],[57],[58],[59],[60],[61],[62],[63],[64],[65],[66],[67],[68],[69],[70],[71],[72],[73],[74],[75],[76],[77],[78],[79],[80],[81],[82],[83],[84],[85],[86],[87],[88],[89],[90],[91],[92],[93],[94],[95]]
            }
        },
        {
            "name": "gpu",
            "processorType": "AMD EPYC 9254 24-Core Processor                ",
            "socketsPerNode": 2,
            "coresPerSocket": 24,
            "threadsPerCore": 1,
            "flopRateScalar": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 508
            },
            "flopRateSimd": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 3163
            },
            "memoryBandwidth": {
                "unit": {
                    "base": "B/s",
                    "prefix": "G"
                },
                "value": 587
            },
            "nodes": "gpu[001-020]",
            "topology": {
                "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
                "socket": [
                    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23],
                    [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47]
                ],
                "memoryDomain": [
                    [0,1,2,3,4,5],
                    [6,7,8,9,10,11],
                    [12,13,14,15,16,17],
                    [18,19,20,21,22,23],
                    [24,25,26,27,28,29],
                    [30,31,32,33,34,35],
                    [36,37,38,39,40,41],
                    [42,43,44,45,46,47]
                ],
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]],
                "accelerators": [
                    {
                        "id": "00000000:21:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia A30"
                    },
                    {
                        "id": "00000000:41:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia A30"
                    },
                    {
                        "id": "00000000:A1:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia A30"
                    }
                ]
            }
        },
        {
            "name": "fatgpu",
            "processorType": "AMD EPYC 9454 48-Core Processor                ",
            "socketsPerNode": 2,
            "coresPerSocket": 48,
            "threadsPerCore": 1,
            "flopRateScalar": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 962
            },
            "flopRateSimd": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 5796
            },
            "memoryBandwidth": {
                "unit": {
                    "base": "B/s",
                    "prefix": "G"
                },
                "value": 779
            },
            "nodes": "fatgpu[001-007]",
            "topology": {
                "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95],
                "socket": [
                    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
                    [48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95]
                ],
                "memoryDomain": [
                    [0,1,2,3,4,5],
                    [6,7,8,9,10,11],
                    [12,13,14,15,16,17],
                    [18,19,20,21,22,23],
                    [24,25,26,27,28,29],
                    [30,31,32,33,34,35],
                    [36,37,38,39,40,41],
                    [42,43,44,45,46,47],
                    [48,49,50,51,52,53],
                    [54,55,56,57,58,59],
                    [60,61,62,63,64,65],
                    [66,67,68,69,70,71],
                    [72,73,74,75,76,77],
                    [78,79,80,81,82,83],
                    [84,85,86,87,88,89],
                    [90,91,92,93,94,95]
                ],
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47],[48],[49],[50],[51],[52],[53],[54],[55],[56],[57],[58],[59],[60],[61],[62],[63],[64],[65],[66],[67],[68],[69],[70],[71],[72],[73],[74],[75],[76],[77],[78],[79],[80],[81],[82],[83],[84],[85],[86],[87],[88],[89],[90],[91],[92],[93],[94],[95]],
                "accelerators": [
                    {
                        "id": "00000000:26:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:2F:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:46:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:54:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:A6:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:AF:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:C6:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    },
                    {
                        "id": "00000000:CF:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia H100"
                    }
                ]
            }
        },
        {
            "name": "vis",
            "processorType": "AMD EPYC 9254 24-Core Processor                ",
            "socketsPerNode": 2,
            "coresPerSocket": 24,
            "threadsPerCore": 1,
            "flopRateScalar": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 517
            },
            "flopRateSimd": {
                "unit": {
                    "base": "F/s",
                    "prefix": "G"
                },
                "value": 3175
            },
            "memoryBandwidth": {
                "unit": {
                    "base": "B/s",
                    "prefix": "G"
                },
                "value": 588
            },
            "nodes": "vis[001-003]",
            "topology": {
                "node": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47],
                "socket": [
                    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23],
                    [24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47]
                ],
                "memoryDomain": [
                    [0,1,2,3,4,5],
                    [6,7,8,9,10,11],
                    [12,13,14,15,16,17],
                    [18,19,20,21,22,23],
                    [24,25,26,27,28,29],
                    [30,31,32,33,34,35],
                    [36,37,38,39,40,41],
                    [42,43,44,45,46,47]
                ],
                "core": [[0],[1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12],[13],[14],[15],[16],[17],[18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30],[31],[32],[33],[34],[35],[36],[37],[38],[39],[40],[41],[42],[43],[44],[45],[46],[47]],
                "accelerators": [
                    {
                        "id": "00000000:81:00.0",
                        "type": "Nvidia GPU",
                        "model": "Nvidia A40"
                    }
                ]
            }
        }
    ]
}
```

</details>