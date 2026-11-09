# Einheiten und Validierung

`cluster.json` beschreibt die Bedeutung und Anzeige eines Messwerts. Das Einheitenlabel verändert den eingehenden Zahlenwert nicht. Die Umrechnung geschieht vorher im Collector oder Router; die Backendkonfiguration muss dazu passen.

## Zahlenwerte skalieren

`change_unit_prefix` skaliert einen korrekt deklarierten Bytewert beispielsweise nach GB. Im folgenden Routerfragment bekommt `mem_used` das Präfix `G`. Die bestehende `stage_order` bleibt erhalten:

```json
{
  "process_messages": {
    "stage_order": ["add_tag", "rename", "rename_if", "drop_by_type", "drop_by_name", "drop_if", "add_meta", "change_unit_prefix", "normalize_unit"],
    "change_unit_prefix": {
      "name == 'mem_used'": "G"
    }
  }
}
```

Das Fragment ergänzt den vorhandenen `process_messages`-Abschnitt. Bestehende Regeln bleiben erhalten. Voraussetzung ist eine korrekte Quelleinheit: Bei Linux-Speicherwerten muss die weiter unten beschriebene `kB`-Korrektur vor der Skalierung stattfinden.

Byte → GB bedeutet eine Division durch 10⁹, Byte/s → MB/s eine Division durch 10⁶. `mem_bw` wird in GB/s angegeben. Watt bleibt Watt, IPC steht für Instructions/Cycle. Ein bereits skalierter Wert darf nicht ein zweites Mal umgerechnet werden.

## Einheiten im RUB-Profil

Das [RUB-Beispielprofil](examples/rub/job-archive/cluster.json) verwendet ausschließlich Einheiten aus dem unveränderten Upstream-Schema. Die Zahlen sind bereits im Collector oder Router skaliert; `base` und `prefix` beschreiben ihre Darstellung im Backend.

| Metriken | `base` / `prefix` | Bedeutung eines Beispielwerts |
|---|---|---|
| `cpu_load`, `cpu_load_core` | `""` | 1,5 bleibt 1,5; dimensionslose Last bzw. Laufzeitquote, kein Prozentwert |
| `clock` | `Hz` / `M` | 2000 bedeutet 2000 MHz |
| `flops_any`, `flops_sp`, `flops_dp`, `flops_bf16` | `F/s` / `G` | 64 bedeutet 64 GFLOP/s |
| `mem_used`, `job_mem_used`, `acc_mem_used`, `disk_free` | `B` / `G` | 1 bedeutet 1 GB |
| `mem_bw` | `B/s` / `G` | 2 bedeutet 2 GB/s |
| Netzwerk-, InfiniBand-, Lustre- und NFS-Bandbreiten | `B/s` / `M` | 10 bedeutet 10 MB/s |
| `ipc` | `IPC` | 1,5 bedeutet 1,5 Instructions/Cycle |
| `core_power`, `acc_power`, `node_total_power` | `W` | 200 bedeutet 200 Watt |

Für MHz steht also `{"base": "Hz", "prefix": "M"}` in der Konfiguration. Eine zusätzliche Multiplikation des Zahlenwerts mit einer Million wäre falsch. Dasselbe gilt für bereits in GFLOP/s, GB oder MB/s gelieferte Werte.

## Zählerdifferenzen und Raten

Eine Zählerdifferenz und eine Sekundenrate sind verschiedene Messgrößen. Ein Anstieg um 60 Operationen innerhalb von 60 Sekunden ergibt 60 Operationen pro Intervall oder, nach Division durch die Zeit, 1 Operation/s. Eine Änderung des Labels führt diese Umrechnung nicht aus.

Das veröffentlichte Profil enthält keine Metriken mit Prozent-, Paket-, Prozess- oder Operationslabels, die das Upstream-Schema nicht darstellen kann. Dazu gehören auch die NUMA-Ereignisraten. Die entsprechenden Nachrichten werden im Router verworfen. So bleibt die Auswahl im Backend auf die 24 Metriken mit unterstützten Einheiten begrenzt. Welche davon Werte liefern, hängt von den aktivierten Collectoren und der Hardware ab.

## Linux-Speicherwerte: kB und KiB

`/proc/meminfo` und NUMA-meminfo verwenden das Label `kB` für 1024-Byte-Einheiten. Der [Kernel verschiebt dazu Seitenzahlen um PAGE_SHIFT−10](https://github.com/torvalds/linux/blob/v6.12/fs/proc/meminfo.c#L26-L30). Der [memstat-Collector](https://github.com/ClusterCockpit/cc-metric-collector/blob/v0.8.4/collectors/memstatMetric.go) reicht dieses Label unverändert weiter.

Der [Beispielrouter](more_metrics.de.md#memstat) korrigiert deshalb nur `mem_used` mit `meta.unit == 'kB'`: `add_meta_if` setzt die Einheit auf `KiB`, bevor `change_unit_prefix` skaliert. Aus 1.048.576 Quelleinheiten werden so 1,073741824 GB. Eine Behandlung als SI-kB ergäbe fälschlich 1,048576 GB.

Andere Bytequellen behalten ihre eigenen Metadaten. Die Korrektur ist auf diesen Linux-Speicherwert beschränkt und darf nicht pauschal alle `kB`-Labels umschreiben.

## Rundung in Archiv, API und Checkpoints

Der [Series-Serializer](https://github.com/ClusterCockpit/cc-lib/blob/v2.12.0/schema/float.go#L116-L145) schreibt Messwerte mit zwei Nachkommastellen. Nach der JSON-Archivierung oder API-Serialisierung erscheint 1,073741824 GB daher als 1,07 GB. Für die Prüfung einer Routerumrechnung gehört die ungerundete Collectorausgabe zum Vergleich.

JSON-Checkpoints runden unabhängig davon auf eine Nachkommastelle. Dieser Unterschied ist insbesondere bei kleinen Werten und Neustartprüfungen relevant.

## Strikte Schemaprüfung

Minimalprofil und RUB-Profil erfüllen das unveränderte [Einheitenschema](https://github.com/ClusterCockpit/cc-lib/blob/v2.12.0/schema/schemas/unit.schema.json) ohne Ausnahmen. Die Guideprüfungen validieren die vollständigen Clusterdateien und prüfen den Start mit beiden dokumentierten Backend-Versionen.

Eine zusätzliche Metrik braucht eine unterstützte Einheit, passende Zahlenwerte und einen Eintrag in `metricConfig`. Erst danach wird sie in die Positivliste des Routers aufgenommen. Eine unbekannte Prozent- oder Ratenbasis durch eine leere Einheit zu ersetzen würde die Aussage der Anzeige verschleiern. Für solche Größen braucht es eine fachlich passende Darstellung in der verwendeten Upstream-Version; sie gehören bis dahin nicht in dieses Profil.

Die Schemaprüfung erkennt unzulässige Konfigurationswerte. Ob eine Zahl physikalisch richtig skaliert ist, prüft zusätzlich der Vergleich mit einem bekannten Messwert.

Der globale Laufzeitschalter `main.validate` prüft auch Jobarchive. In Backend 1.5.3 und 1.5.4 kann diese Prüfung vom Backend selbst geschriebene Metadaten ablehnen: Das [Archivschema](https://github.com/ClusterCockpit/cc-lib/blob/v2.12.0/schema/schemas/job-meta.schema.json) verlangt bestimmte Statistikmetriken und akzeptiert einige ausgegebene `null`-Felder nicht. Deshalb lässt die [Backend-Beispielkonfiguration](examples/rub/cc-backend/config.json) den Schalter beim Upstream-Standard und setzt ihn nicht. Die separate Prüfung der Clusterkonfiguration bleibt davon unabhängig; es werden weder Schemas verändert noch Ausnahmen zugelassen.

## Zuordnung der Messwerte prüfen

Bei `hwthread`, `socket` und `memoryDomain` müssen die IDs der Messreihen zur Topologie und zu den Jobressourcen passen. Eine aussagekräftige Prüfung verwendet unterschiedliche bekannte Werte für mehrere Hardwareeinheiten und lässt vorübergehend eine Messreihe fehlen. Der Vergleich umfasst IDs und Werte vor und nach der Archivierung. Fehlende Messwerte bleiben dabei fehlend und werden nicht durch erfundene Nullen ersetzt.
