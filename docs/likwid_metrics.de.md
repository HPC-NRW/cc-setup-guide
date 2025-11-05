# LIKWID-basierte Performance-Metriken

## Was sind Performance-Counter?

Moderne CPUs enthalten spezielle Hardware-Register, sogenannte Performance-Monitoring-Counter (PMC).  
Diese Zähler erfassen interne Ereignisse der Mikroarchitektur – etwa ausgeführte Instruktionen, Cache-Misses, Speicherbandbreite oder Stromverbrauch.  
Zugriff erfolgt über Kernel-Schnittstellen oder herstellerspezifische Mechanismen. Tools wie [LIKWID](https://github.com/RRZE-HPC/likwid) abstrahieren die Architekturdetails, gruppieren Counters zu sprechenden „Performance-Gruppen“ und lesen sie für einzelne Kerne, Sockets oder den ganzen Knoten aus.

Viele dieser Counter sind über Model Specific Registers (MSR) zugänglich. LIKWID nutzt kernelnah Dienste (`likwid-accessdaemon`), um die MSR auszulesen.  
Wird der Kernel-Parameter `msr.allow_writes=on` nicht oder fehlerhaft gesetzt, protokolliert der Kernel bei jedem Zugriff Warnungen wie „Write to unrecognized MSR“ ins Syslog.  
Der Parameter deaktiviert lediglich das Rate-Limiting dieser Meldungen; er erlaubt _keine_ willkürlichen Schreibzugriffe auf MSRs und verringert damit die Systemsicherheit nicht.

## AMD vs. Intel – Unterschiede bei FLOPS und Energie

- **Intel** unterscheidet bei den FLOPS-Gruppen zwischen einfacher und doppelter Genauigkeit:  
  - `FLOPS_SP` (Single Precision)  
  - `FLOPS_DP` (Double Precision)  
  Zusätzlich lässt sich eine aggregierte Größe `FLOPS_ANY` bilden (`FLOPS_SP + 2 · FLOPS_DP`), die beide Präzisionen gewichtet kombiniert.  
  Für die Visualisierung im ClusterCockpit sollte entschieden werden, ob nur `FLOPS_ANY` (weniger Daten pro Core) oder `FLOPS_SP` und `FLOPS_DP` getrennt angezeigt werden.  
  Außerdem können Intel-Prozessoren den Energieverbrauch einzelner Domains – etwa `package`, `cores` und `dram` – über RAPL zur Verfügung stellen.

- **AMD** veröffentlicht mit LIKWID aktuell nur `FLOPS_ANY` und bietet keine getrennte SP/DP-Auswertung.  
  Auch die Energiecounter sind weniger granular; beispielsweise steht kein eigener Memory-Domain-Zähler zur Verfügung.

Die Unterschiede sollten bei der Planung der Metriken berücksichtigt werden, um unnötige Datenmengen (Core-Grenze) zu vermeiden und die Vergleichbarkeit zu wahren.

## Konfiguration mit `likwid_perfgroup_to_cc_config.py`

Im Repository des `cc-metric-collector` befindet sich unter `scripts/` das Tool [`likwid_perfgroup_to_cc_config.py`](https://github.com/ClusterCockpit/cc-metric-collector/blob/main/scripts/likwid_perfgroup_to_cc_config.py).  
Damit lassen sich die LIKWID-Perf-Gruppen in eine `likwid`-Konfiguration für den Collector übersetzen.

### Vorbereitung

* LIKWID installiert haben (damit die Perf-Gruppen verfügbar sind).  
  Unter `/cluster/monitoring/likwid/share/likwid/perfgroups/` befinden sich die architekturspezifischen Gruppen, z. B. `zen4`, `zen3`, `SPR` oder `ICX`.  
* Gewünschte Architektur (Verzeichnisname) und Performance-Gruppe (Dateiname ohne `.txt`) auswählen, etwa `zen4/MEMREAD` oder `SPR/MEM`.
Der Aufruf ist case-sensitive; Architektur- und Gruppenname müssen exakt mit den Dateinamen übereinstimmen (z. B. `SPR`, nicht `spr`).

### Aufruf

```bash
cd /cluster/monitoring/likwid/share/likwid/perfgroups/
./likwid_perfgroup_to_cc_config.py zen4 MEMREAD
```

Die Ausgabe beschreibt Events und berechnete Metriken. Beispiel für Zen4 `MEMREAD`:

```json
{
  "events": {
    "DFC0": "DRAM_READS_LOCAL_CHANNEL_0",
    "DFC1": "DRAM_READS_LOCAL_CHANNEL_1",
    "DFC10": "DRAM_READS_LOCAL_CHANNEL_10",
    "DFC11": "DRAM_READS_LOCAL_CHANNEL_11",
    "DFC2": "DRAM_READS_LOCAL_CHANNEL_2",
    "DFC3": "DRAM_READS_LOCAL_CHANNEL_3",
    "DFC4": "DRAM_READS_LOCAL_CHANNEL_4",
    "DFC5": "DRAM_READS_LOCAL_CHANNEL_5",
    "DFC6": "DRAM_READS_LOCAL_CHANNEL_6",
    "DFC7": "DRAM_READS_LOCAL_CHANNEL_7",
    "DFC8": "DRAM_READS_LOCAL_CHANNEL_8",
    "DFC9": "DRAM_READS_LOCAL_CHANNEL_9",
    "FIXC1": "ACTUAL_CPU_CLOCK",
    "FIXC2": "MAX_CPU_CLOCK",
    "PMC0": "RETIRED_INSTRUCTIONS",
    "PMC1": "CPU_CLOCKS_UNHALTED"
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1*inverseClock",
      "name": "Runtime unhalted [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.E-06*(FIXC1/FIXC2)/inverseClock",
      "name": "Clock [MHz]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "PMC1/PMC0",
      "name": "CPI",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.0E-06*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0/time",
      "name": "Memory read bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0",
      "name": "Memory read data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

Um die Memory Bandwidth zu erhalten, muss zusätzlich `MEMWRITE` ausgegeben werden:

```json
{
  "events": {
    "DFC0": "DRAM_WRITES_LOCAL_CHANNEL_0",
    "DFC1": "DRAM_WRITES_LOCAL_CHANNEL_1",
    "DFC10": "DRAM_WRITES_LOCAL_CHANNEL_10",
    "DFC11": "DRAM_WRITES_LOCAL_CHANNEL_11",
    "DFC2": "DRAM_WRITES_LOCAL_CHANNEL_2",
    "DFC3": "DRAM_WRITES_LOCAL_CHANNEL_3",
    "DFC4": "DRAM_WRITES_LOCAL_CHANNEL_4",
    "DFC5": "DRAM_WRITES_LOCAL_CHANNEL_5",
    "DFC6": "DRAM_WRITES_LOCAL_CHANNEL_6",
    "DFC7": "DRAM_WRITES_LOCAL_CHANNEL_7",
    "DFC8": "DRAM_WRITES_LOCAL_CHANNEL_8",
    "DFC9": "DRAM_WRITES_LOCAL_CHANNEL_9",
    "FIXC1": "ACTUAL_CPU_CLOCK",
    "FIXC2": "MAX_CPU_CLOCK",
    "PMC0": "RETIRED_INSTRUCTIONS",
    "PMC1": "CPU_CLOCKS_UNHALTED"
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1*inverseClock",
      "name": "Runtime unhalted [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.E-06*(FIXC1/FIXC2)/inverseClock",
      "name": "Clock [MHz]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "PMC1/PMC0",
      "name": "CPI",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.0E-06*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0/time",
      "name": "Memory write bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0",
      "name": "Memory write data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```
In der `collectors.json` beschränken wir uns auf die benötigten Counter und die beiden Metriken. Zur besseren Handhabung benennen wir sie kurz `mem_read` und `mem_write` und setzen `publish` auf `false`, damit keine Nachrichten mit diesen beiden Metriken versendet werden:

```json
      {
        "events": {
          "DFC0": "DRAM_READS_LOCAL_CHANNEL_0",
          "DFC1": "DRAM_READS_LOCAL_CHANNEL_1",
          "DFC10": "DRAM_READS_LOCAL_CHANNEL_10",
          "DFC11": "DRAM_READS_LOCAL_CHANNEL_11",
          "DFC2": "DRAM_READS_LOCAL_CHANNEL_2",
          "DFC3": "DRAM_READS_LOCAL_CHANNEL_3",
          "DFC4": "DRAM_READS_LOCAL_CHANNEL_4",
          "DFC5": "DRAM_READS_LOCAL_CHANNEL_5",
          "DFC6": "DRAM_READS_LOCAL_CHANNEL_6",
          "DFC7": "DRAM_READS_LOCAL_CHANNEL_7",
          "DFC8": "DRAM_READS_LOCAL_CHANNEL_8",
          "DFC9": "DRAM_READS_LOCAL_CHANNEL_9"
        },
        "metrics": [
          {
            "calc": "1.0E-09*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0/time",
            "name": "mem_read",
            "publish": false,
            "type": "socket"
          }
        ]
      },
      {
        "events": {
          "DFC0": "DRAM_WRITES_LOCAL_CHANNEL_0",
          "DFC1": "DRAM_WRITES_LOCAL_CHANNEL_1",
          "DFC10": "DRAM_WRITES_LOCAL_CHANNEL_10",
          "DFC11": "DRAM_WRITES_LOCAL_CHANNEL_11",
          "DFC2": "DRAM_WRITES_LOCAL_CHANNEL_2",
          "DFC3": "DRAM_WRITES_LOCAL_CHANNEL_3",
          "DFC4": "DRAM_WRITES_LOCAL_CHANNEL_4",
          "DFC5": "DRAM_WRITES_LOCAL_CHANNEL_5",
          "DFC6": "DRAM_WRITES_LOCAL_CHANNEL_6",
          "DFC7": "DRAM_WRITES_LOCAL_CHANNEL_7",
          "DFC8": "DRAM_WRITES_LOCAL_CHANNEL_8",
          "DFC9": "DRAM_WRITES_LOCAL_CHANNEL_9"
        },
        "metrics": [
          {
            "calc": "1.0E-09*(DFC0+DFC1+DFC2+DFC3+DFC4+DFC5+DFC6+DFC7+DFC8+DFC9+DFC10+DFC11)*64.0/time",
            "name": "mem_write",
            "publish": false,
            "type": "socket"
          }
        ]
      }
```
Zum Schluss wird in `globalmetrics` die Memory Bandwidth `mem_bw` als abgeleitete Metrik definiert, die anschließend versendet wird:

```json
"globalmetrics": [
  {
    "name": "mem_bw",
    "calc": "mem_read + mem_write",
    "type": "socket",
    "unit": "Gbyte/s",
    "publish": true
  }
]
```

# Beispiel Intel Sapphire Rapids
Für Intel Sapphire Rapids (`SPR MEM`) liefert das Skript andere Counter (z. B. `MBOX*C*`):
```json
{
  "events": {
    "FIXC0": "INSTR_RETIRED_ANY",
    "FIXC1": "CPU_CLK_UNHALTED_CORE",
    "FIXC2": "CPU_CLK_UNHALTED_REF",
    "FIXC3": "TOPDOWN_SLOTS",
    "MBOX0C0": "CAS_COUNT_RD",
    "MBOX0C1": "CAS_COUNT_WR",
    "MBOX10C0": "CAS_COUNT_RD",
    "MBOX10C1": "CAS_COUNT_WR",
    "MBOX11C0": "CAS_COUNT_RD",
    "MBOX11C1": "CAS_COUNT_WR",
    "MBOX1C0": "CAS_COUNT_RD",
    "MBOX1C1": "CAS_COUNT_WR",
    "MBOX2C0": "CAS_COUNT_RD",
    "MBOX2C1": "CAS_COUNT_WR",
    "MBOX3C0": "CAS_COUNT_RD",
    "MBOX3C1": "CAS_COUNT_WR",
    "MBOX4C0": "CAS_COUNT_RD",
    "MBOX4C1": "CAS_COUNT_WR",
    "MBOX5C0": "CAS_COUNT_RD",
    "MBOX5C1": "CAS_COUNT_WR",
    "MBOX6C0": "CAS_COUNT_RD",
    "MBOX6C1": "CAS_COUNT_WR",
    "MBOX7C0": "CAS_COUNT_RD",
    "MBOX7C1": "CAS_COUNT_WR",
    "MBOX8C0": "CAS_COUNT_RD",
    "MBOX8C1": "CAS_COUNT_WR",
    "MBOX9C0": "CAS_COUNT_RD",
    "MBOX9C1": "CAS_COUNT_WR"
  },
  "metrics": [
    {
      "calc": "time",
      "name": "Runtime (RDTSC) [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1*inverseClock",
      "name": "Runtime unhalted [s]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.E-06*(FIXC1/FIXC2)/inverseClock",
      "name": "Clock [MHz]",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "FIXC1/FIXC0",
      "name": "CPI",
      "publish": true,
      "type": "hwthread"
    },
    {
      "calc": "1.0E-06*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0)*64.0/time",
      "name": "Memory read bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0)*64.0",
      "name": "Memory read data volume [GBytes]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-06*(MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "Memory write bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0",
      "name": "Memory write data volume [GBytes]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-06*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "Memory bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0",
      "name": "Memory data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

Hier ist es einfacher, die Memory Bandwidth zu erheben. Es genügt, die ungenutzten Counter und Metriken zu entfernen und `Memory bandwidth [MBytes/s]` umzubenennen:

```json
{
  "events": {
    "MBOX0C0": "CAS_COUNT_RD",
    "MBOX0C1": "CAS_COUNT_WR",
    "MBOX10C0": "CAS_COUNT_RD",
    "MBOX10C1": "CAS_COUNT_WR",
    "MBOX11C0": "CAS_COUNT_RD",
    "MBOX11C1": "CAS_COUNT_WR",
    "MBOX1C0": "CAS_COUNT_RD",
    "MBOX1C1": "CAS_COUNT_WR",
    "MBOX2C0": "CAS_COUNT_RD",
    "MBOX2C1": "CAS_COUNT_WR",
    "MBOX3C0": "CAS_COUNT_RD",
    "MBOX3C1": "CAS_COUNT_WR",
    "MBOX4C0": "CAS_COUNT_RD",
    "MBOX4C1": "CAS_COUNT_WR",
    "MBOX5C0": "CAS_COUNT_RD",
    "MBOX5C1": "CAS_COUNT_WR",
    "MBOX6C0": "CAS_COUNT_RD",
    "MBOX6C1": "CAS_COUNT_WR",
    "MBOX7C0": "CAS_COUNT_RD",
    "MBOX7C1": "CAS_COUNT_WR",
    "MBOX8C0": "CAS_COUNT_RD",
    "MBOX8C1": "CAS_COUNT_WR",
    "MBOX9C0": "CAS_COUNT_RD",
    "MBOX9C1": "CAS_COUNT_WR"
  },
  "metrics": [
    {
      "calc": "1.0E-06*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "mem_bw",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

# weitere Metriken

Weitere häufig genutzte LIKWID-Metriken:

- `flops_any`
- `clock`
- `core_power`
- `ipc` (aus den Performance-Gruppen fällt meist `CPI`, also der Kehrwert, heraus)