# LIKWID-basierte Performance-Metriken

Diese Erweiterung ist für Hardwaremetriken wie Speicherbandbreite und FLOPS vorgesehen. Ein funktionierendes [Basissetup](metrics.de.md) reicht für den Einstieg aus; LIKWID-Metriken kommen nur bei Bedarf hinzu.

## Was sind Performance-Counter?

CPUs besitzen Hardwarezähler, sogenannte Performance-Monitoring-Counter (PMC).
Sie erfassen Ereignisse der Mikroarchitektur, etwa ausgeführte Instruktionen und Cache-Misses. Daraus lassen sich unter anderem Leistungs-, Bandbreiten- und Energiemetriken ableiten.
Der Zugriff erfolgt über Kernel-Schnittstellen oder herstellerspezifische Mechanismen. [LIKWID](https://github.com/RRZE-HPC/likwid) fasst die architekturspezifischen Zähler in Performance-Gruppen zusammen und liest sie für Kerne, Sockets oder den ganzen Knoten aus.

Viele Zähler werden über Model Specific Registers (MSR) programmiert und gelesen. LIKWID nutzt dafür den `accessdaemon` oder direkten Gerätezugriff. Gerätedateirechte, Capabilities und die Schreibregeln des Kernels sind dabei getrennte Schutzebenen. Der [MSR-Treiber des Linux-Kernels](https://github.com/torvalds/linux/blob/v6.12/arch/x86/kernel/msr.c) verlangt bereits zum Öffnen `CAP_SYS_RAWIO`; Kernel-Lockdown kann Schreibzugriffe zusätzlich verhindern.

`msr.allow_writes=off` verweigert MSR-Schreibzugriffe. `on` lässt sie durch diesen Filter und unterdrückt dessen Warnungen. Der verlinkte Kernelstand erlaubt solche Zugriffe standardmäßig und begrenzt die Warnungen bereits per Rate-Limit. Ein Wechsel von `off` zu `on` hebt also einen Schreibschutz auf. Welche Regeln tatsächlich gelten, hängt vom LIKWID-Modus, dem Distributionskernel und dessen Backports ab.

Beim LIKWID-`accessdaemon` vermittelt ein privilegierter Helfer den Zugriff. Seine Zugriffsregeln müssen zu den MSR-Gerätedateirechten und zur Kernelpolicy passen. Die [LIKWID-Build-/Zugriffsdokumentation](https://github.com/RRZE-HPC/likwid/wiki/Build) beschreibt die Betriebsarten. Capabilities oder MSR-Geräterechte dürfen nicht pauschal an alle Konten gehen; Lockdown sollte nicht zur Unterdrückung von Warnungen abgeschaltet werden. Jede Metrik benötigt eine Prüfung auf Verfügbarkeit und plausible Werte auf der tatsächlichen Hardware.

## AMD vs. Intel – Unterschiede bei FLOPS und Energie

- **Intel** unterscheidet bei den FLOPS-Gruppen zwischen einfacher und doppelter Genauigkeit:  
  - `FLOPS_SP` (Single Precision)  
  - `FLOPS_DP` (Double Precision)  
  Eine zusätzliche Größe `FLOPS_ANY` kombiniert beide gewichtet als `FLOPS_SP + 2 · FLOPS_DP`.
  Für die Anzeige kommen entweder die gemeinsame Größe `FLOPS_ANY` oder getrennte SP-/DP-Werte infrage. Nur die gemeinsame Größe zu speichern reduziert die Datenmenge pro Core.
  Außerdem können Intel-Prozessoren den Energieverbrauch einzelner Domains – etwa `package`, `cores` und `dram` – über RAPL zur Verfügung stellen.

- **AMD Zen4:** Die hier verwendete LIKWID-Gruppe liefert einen gemeinsamen FLOPS-Zähler. Getrennte SP-/DP-Raten lassen sich daraus nicht zuverlässig ableiten. **AMD Zen5 mit LIKWID 5.5.1** bietet dagegen eigene SP-Scalar-/Packed-, DP-Scalar-/Packed- und BF16-Ereignisse. Hier kann `flops_any` die ungewichtete Summe `flops_sp + flops_dp + flops_bf16` bilden, jeweils in GF/s. Jedes Ereignis zählt genau einmal; das unterscheidet sich von einer SP-äquivalenten Gewichtung. Die verfügbaren RAPL-/Energiedomains hängen vom Prozessormodell ab.

Eine gemeinsame Bezeichnung allein macht die Werte verschiedener Architekturen noch nicht vergleichbar. Die gewählte FLOPS-Konvention und die verfügbaren Energiedomains gehören deshalb zur Planung des Metrikprofils. Zusätzliche Core-Metriken erhöhen außerdem die Datenmenge.

## Konfiguration mit `likwid_perfgroup_to_cc_config.py`

Im Repository des `cc-metric-collector` liegt unter `scripts/` das Tool [`likwid_perfgroup_to_cc_config.py`](https://github.com/ClusterCockpit/cc-metric-collector/blob/6df8da8fe9e3fe9459aa0538b3d4027ad4f906b0/scripts/likwid_perfgroup_to_cc_config.py).
Es übersetzt LIKWID-Performance-Gruppen in eine `likwid`-Konfiguration für den Collector. Der Ablauf besteht aus vier Schritten: Gruppe ausgeben, benötigte Zähler und Metriken auswählen, Namen und Einheiten festlegen und die Zielmetrik veröffentlichen.

### Vorbereitung

* Erforderlich sind LIKWID **5.5.1**, Python3 und die ausgecheckten Collectorquellen aus dem Installationskapitel.
  Unter `/cluster/software/likwid/share/likwid/perfgroups/` befinden sich die architekturspezifischen Gruppen, z. B. `zen4`, `zen3`, `SPR` oder `ICX`.
* Architektur und Performance-Gruppe entsprechen Verzeichnis- und Dateiname ohne `.txt`, beispielsweise `zen4/MEMREAD` oder `SPR/MEM`.
Groß- und Kleinschreibung müssen mit den Dateinamen übereinstimmen, etwa `SPR` statt `spr`.

### Aufruf

```bash
COLLECTOR_SOURCE="$(pwd -P)"  # Run in the pinned cc-metric-collector source checkout.
export PATH=/cluster/software/likwid/bin:$PATH
python3 "$COLLECTOR_SOURCE/scripts/likwid_perfgroup_to_cc_config.py" zen4 MEMREAD
```

Die Ausgabe beschreibt Events und berechnete Metriken. Beispiel für Zen4 `MEMREAD`:

<details>
<summary>Vollständige Ausgabe für Zen4 MEMREAD</summary>

```json
{
  "events": {
    "UMC0C0": "CAS_CMD_RD",
    "UMC1C0": "CAS_CMD_RD",
    "UMC10C0": "CAS_CMD_RD",
    "UMC11C0": "CAS_CMD_RD",
    "UMC2C0": "CAS_CMD_RD",
    "UMC3C0": "CAS_CMD_RD",
    "UMC4C0": "CAS_CMD_RD",
    "UMC5C0": "CAS_CMD_RD",
    "UMC6C0": "CAS_CMD_RD",
    "UMC7C0": "CAS_CMD_RD",
    "UMC8C0": "CAS_CMD_RD",
    "UMC9C0": "CAS_CMD_RD",
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
      "calc": "1.0E-06*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
      "name": "Memory read bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0",
      "name": "Memory read data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>

Für die gesamte Speicherbandbreite gehört zusätzlich die Gruppe `MEMWRITE` dazu:

<details>
<summary>Vollständige Ausgabe für Zen4 MEMWRITE</summary>

```json
{
  "events": {
    "UMC0C0": "CAS_CMD_WR",
    "UMC1C0": "CAS_CMD_WR",
    "UMC10C0": "CAS_CMD_WR",
    "UMC11C0": "CAS_CMD_WR",
    "UMC2C0": "CAS_CMD_WR",
    "UMC3C0": "CAS_CMD_WR",
    "UMC4C0": "CAS_CMD_WR",
    "UMC5C0": "CAS_CMD_WR",
    "UMC6C0": "CAS_CMD_WR",
    "UMC7C0": "CAS_CMD_WR",
    "UMC8C0": "CAS_CMD_WR",
    "UMC9C0": "CAS_CMD_WR",
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
      "calc": "1.0E-06*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
      "name": "Memory write bandwidth [MBytes/s]",
      "publish": true,
      "type": "socket"
    },
    {
      "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0",
      "name": "Memory write data volume [GBytes]",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>
Die `collectors.json` übernimmt nur die benötigten Zähler und zwei Zwischenmetriken. Die kurzen Namen `mem_read` und `mem_write` erleichtern die weitere Berechnung. `publish: false` verhindert, dass diese Zwischenwerte als eigene Nachrichten versendet werden:

<details>
<summary>Ausgewählte Zen4-Zähler und Zwischenmetriken</summary>

```json
      {
        "events": {
          "UMC0C0": "CAS_CMD_RD",
          "UMC1C0": "CAS_CMD_RD",
          "UMC10C0": "CAS_CMD_RD",
          "UMC11C0": "CAS_CMD_RD",
          "UMC2C0": "CAS_CMD_RD",
          "UMC3C0": "CAS_CMD_RD",
          "UMC4C0": "CAS_CMD_RD",
          "UMC5C0": "CAS_CMD_RD",
          "UMC6C0": "CAS_CMD_RD",
          "UMC7C0": "CAS_CMD_RD",
          "UMC8C0": "CAS_CMD_RD",
          "UMC9C0": "CAS_CMD_RD"
        },
        "metrics": [
          {
            "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
            "name": "mem_read",
            "publish": false,
            "type": "socket"
          }
        ]
      },
      {
        "events": {
          "UMC0C0": "CAS_CMD_WR",
          "UMC1C0": "CAS_CMD_WR",
          "UMC10C0": "CAS_CMD_WR",
          "UMC11C0": "CAS_CMD_WR",
          "UMC2C0": "CAS_CMD_WR",
          "UMC3C0": "CAS_CMD_WR",
          "UMC4C0": "CAS_CMD_WR",
          "UMC5C0": "CAS_CMD_WR",
          "UMC6C0": "CAS_CMD_WR",
          "UMC7C0": "CAS_CMD_WR",
          "UMC8C0": "CAS_CMD_WR",
          "UMC9C0": "CAS_CMD_WR"
        },
        "metrics": [
          {
            "calc": "1.0E-09*(UMC0C0+UMC1C0+UMC2C0+UMC3C0+UMC4C0+UMC5C0+UMC6C0+UMC7C0+UMC8C0+UMC9C0+UMC10C0+UMC11C0)*64.0/time",
            "name": "mem_write",
            "publish": false,
            "type": "socket"
          }
        ]
      }
```

</details>
`globalmetrics` bildet daraus die Zielmetrik `mem_bw`. Diese Summe wird anschließend veröffentlicht:

```json
"globalmetrics": [
  {
    "name": "mem_bw",
    "calc": "mem_read + mem_write",
    "type": "socket",
    "unit": "GBytes/s",
    "publish": true
  }
]
```

## Beispiel Intel Sapphire Rapids
Für Intel Sapphire Rapids (`SPR MEM`) liefert das Skript andere Counter (z. B. `MBOX*C*`):
<details>
<summary>Vollständige Ausgabe für Intel Sapphire Rapids</summary>

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

</details>

Für die Zielmetrik `mem_bw` bleiben nur die benötigten Zähler und Metriken erhalten. Der Faktor `1e-9` ersetzt `1e-6`, damit die Ausgabe GByte/s statt MByte/s enthält. Dazu passen `unit: GBytes/s` im Collector und `unit: {base: B/s, prefix: G}` im Backend. Beispielsweise müssen 1.000.000.000 Byte pro Sekunde den Wert `1` ergeben, nicht `1000`.

<details>
<summary>Bereinigte SPR-Konfiguration für mem_bw</summary>

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
      "calc": "1.0E-09*(MBOX0C0+MBOX1C0+MBOX2C0+MBOX3C0+MBOX4C0+MBOX5C0+MBOX6C0+MBOX7C0+MBOX8C0+MBOX9C0+MBOX10C0+MBOX11C0+MBOX0C1+MBOX1C1+MBOX2C1+MBOX3C1+MBOX4C1+MBOX5C1+MBOX6C1+MBOX7C1+MBOX8C1+MBOX9C1+MBOX10C1+MBOX11C1)*64.0/time",
      "name": "mem_bw",
      "unit": "GBytes/s",
      "publish": true,
      "type": "socket"
    }
  ]
}
```

</details>

## weitere Metriken

Weitere häufig genutzte LIKWID-Metriken:

- `flops_any`
- `clock`
- `core_power`
- `ipc` (aus den Performance-Gruppen fällt meist `CPI`, also der Kehrwert, heraus)

Nach der Collector-Konfiguration folgen die passenden Einträge in [router.json und cluster.json](metric_flow.de.md). Die Prüfung über mehrere Messintervalle und die Übergabe an den [Collector-Dienst](collector_service.de.md) entsprechen den übrigen Metriken. Namen, Scope und Einheiten müssen auf beiden Seiten übereinstimmen.
