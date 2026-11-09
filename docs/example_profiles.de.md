# Beispielprofile und Konfigurationsdateien

Das [Minimalprofil](cc_metric_collector_quicksetup.de.md) eignet sich für den ersten funktionierenden Datenweg. Das hier dokumentierte RUB-Profil zeigt dagegen eine umfangreiche Konfiguration des Elysium-Clusters. Für den Guide wurde die Metrikauswahl auf das offizielle Einheitenschema abgestimmt. Hardwareauswahl und Betriebsannahmen sind ein Beispiel, keine Voraussetzung für eine ClusterCockpit-Installation.

!!! info "Einheiten nach dem Upstreamschema"
    Das Profil verwendet ausschließlich Einheiten des unveränderten offiziellen Schemas. Lastwerte sind dimensionslos, Taktfrequenzen stehen in MHz (`Hz` mit Präfix `M`) und FLOP-Raten in GFLOP/s (`F/s` mit Präfix `G`). Optionale Prozent- und Zählermetriken ohne passende Schemaeinheit sind aus diesem Beispiel ausgeschlossen. [Einheiten und Validierung](units.de.md) erklärt die Auswahl.

Die folgenden Abschnitte erklären die Metrikauswahl, die standortspezifischen Anpassungen und das Routing. Die vollständigen Backend- und Collector-Dateien stehen anschließend zusammen unter [Beispielkonfigurationen](#beispielkonfigurationen). Der dauerhafte Start ist unter [Collector als Dienst](collector_service.de.md) beschrieben.

## collectors.json (Beispiel für AMD Zen 4)

Die [collectors.json](examples/rub/cc-metric-collector/collectors.json) basiert auf der Konfiguration eines AMD-Zen4-CPU-Knotens des Elysium-Clusters der Ruhr-Universität Bochum. Sie verwendet Optionen des offiziellen Collectors und die Einheiten- und Routingregeln dieses Guides. LIKWID-Eventsets, Netzwerkinterfaces und Gerätefilter sind auf diesen Standort abgestimmt und müssen zur jeweiligen Hardware passen.

<details>
<summary>Collector-Konfiguration</summary>

```json
--8<-- "examples/rub/cc-metric-collector/collectors.json"
```

</details>

## Collector-Übersicht nach Kategorien

Die Tabellen zeigen die Namen nach dem Routing, also die Namen aus `cluster.json`. Der optionale GPU-Collector `nvidia` ist im CPU-Beispiel nicht aktiviert.


### CPU & Load

| Collector     | Metrik                                    | Scope    | Beschreibung                           |
| ------------- | ----------------------------------------- | -------- | ---------------------------------------|
| **loadavg**   | `cpu_load`                                | node     | 1-Minuten Load                         |
| **schedstat** | `cpu_load_core`                           | hwthread | Auslastung je Hardware-Thread          |
| **likwid**    | `clock`, `ipc`, `flops_any`, `core_power` | hwthread | CPU-Performance-Counter                |


### Memory & NUMA

| Collector        | Metrik             | Scope               | Beschreibung                        |
| ---------------- | ------------------ | ------------------- | ----------------------------------- |
| **memstat**      | `mem_used`         | node / memoryDomain | RAM-Belegung pro Node & NUMA-Domain |
| **slurm_cgroup** | `job_mem_used`     | hwthread            | Jobbezogene RAM-Auslastung          |
| **likwid**       | `mem_bw`           | socket              | Memory-Bandbreite pro Socket        |


### Storage (Lokal, Lustre, NFS)

| Collector      | Metrik                             | Scope | Beschreibung                               |
| -------------- | ---------------------------------- | ----- | ------------------------------------------ |
| **diskstat**   | `disk_free`                        | node  | Freier lokaler Plattenspeicher             |
| **lustrestat** | `lustre_read_bw`, `lustre_write_bw` | node | Lustre-Lese- und Schreibbandbreite |
| **nfsiostat**  | `nfsio_nread`, `nfsio_nwrite`      | node  | NFS-I/O-Bandbreite des ausgewählten Exports |

[Einheiten und Validierung](units.de.md) erklärt die Einheiten. `main.interval` und die zugehörigen `timestep`-Werte in `cluster.json` müssen zusammenpassen.


### Netzwerk

| Collector   | Metrik                               | Scope | Beschreibung           |
| ----------- | ------------------------------------ | ----- | ---------------------- |
| **netstat** | `net_bytes_in`, `net_bytes_out` | node | Ethernet-Bandbreite |
| **ibstat**  | `ib_recv`, `ib_xmit` | node | InfiniBand-Bandbreite |

### Node-Leistung

| Quelle | Metrik | Scope | Beschreibung |
|---|---|---|---|
| Eigene externe Leistungsquelle, optional | `node_total_power` | node | Gesamtleistungsaufnahme des Knotens in Watt |

Das CPU-Beispiel aktiviert keine Quelle für `node_total_power`. Die Metrik benötigt eine eigene Leistungsquelle über eine unterstützte Schnittstelle. [Weitere Metriken](more_metrics.de.md) zeigt dafür ein Beispiel mit dem offiziellen `customcmd`-Collector. Ohne eine solche Quelle kann `node_total_power` aus `cluster.json` entfallen.


### GPU (optional)

| Collector  | Metrik                                         | Scope       | Beschreibung                        |
| ---------- | ---------------------------------------------- | ----------- | ----------------------------------- |
| **nvidia** | `acc_mem_used`, `acc_power` | accelerator | GPU-Speicherbelegung und Leistungsaufnahme |


Für einen anderen Standort sind folgende Angaben anzupassen:

- `use_sudo` kommt nur dann mit `true` infrage, wenn der Collector nicht als `root` läuft.
- `netstat` benötigt den lokalen Ethernet-Interfacenamen.
- Der `diskstat`-Filter muss die gewünschte Partition auswählen.
- Für `lustrestat` muss der Pfad zu `lctl` stimmen.
- Bei `likwid` müssen `accessdaemon_path`, `liblikwid_path` und `lockfile_path` zur LIKWID-Installation passen. Die Eventsets hängen von der CPU-Architektur ab; die Einrichtung steht unter [LIKWID-Metriken](likwid_metrics.de.md).


## router.json

Die vollständige Datei steht [weiter unten](#cc-metric-collectorrouterjson).

### Erklärung der wichtigsten Verarbeitungsschritte

- **add_tags** setzt den Clusternamen `elysium` für die Zuordnung jeder Nachricht.
- **stage_order** legt die Reihenfolge fest. Neue Verarbeitungsschritte müssen an der passenden Stelle stehen.
- **hostname_tag** liest den Hostnamen aus dem Tag `hostname`.
- **rename_messages** übersetzt Rohmetriken in die Namen für `cc-backend`. Dabei entfällt bei mehreren Bandbreiten das Suffix `_bw`; GPU-Metriken erhalten den allgemeinen Präfix `acc`.
- **drop_messages_if** entfernt nicht benötigte Partitionen, Exporte und Metriken. Da die Umbenennung vorher läuft, verwenden die Filter bereits die Zielnamen.
- **add_meta_if** korrigiert das Linux-Label `kB` gezielt für `mem_used` zu `KiB`, bevor die Speicherwerte skaliert werden.
- **change_unit_prefix** skaliert Einheiten für die Anzeige, beispielsweise Byte nach GB oder MB. Auch diese Regeln verwenden die Zielnamen.
- **normalize_units** vereinheitlicht die Schreibweise der Einheiten nach der Umrechnung.

Die Gerätefilter hängen vom Hostnamen ab: `startsWith` wählt eine Knotengruppe, der Vergleich mit `tag.device` die gewünschte Partition. Das Präfix `cpu` lässt hier nur `nvme0n1p4` durch. Bei `disk_free` kann derselbe Gerätename mit `/dev/` beginnen. Hostnamen und Geräte sind standortspezifisch. Die Routerfilter müssen die gewünschte Partition zulassen.

Manche Collectoren liefern mehrere Werte mit gleichem Metriknamen pro Knoten, etwa `disk_free` für mehrere Partitionen. In dieser Konfiguration verarbeitet `cc-backend` davon nur die erste Nachricht und verwirft die übrigen. Eine gezielte Filterung wählt deshalb die gewünschte Quelle aus.
Unterschiedliche `stype`-Werte oder andere Tags ermöglichen in dieser Konfiguration keine getrennten Kurven für Nachrichten mit demselben Namen und Knoten.

Das Beispiel behält `nfsio` nur für den Export `/home` und verwirft `/cluster`. Eine Alternative sind getrennte Zielnamen aus der Rename-Stage, etwa `cluster_nfsio_nread`.
Dasselbe Vorgehen ist für andere Metriken möglich, beispielsweise bei mehreren getrennt erfassten GPFS-Dateisystemen.



## Beispielkonfigurationen

Die folgenden Dateien bilden das Backend-, UI-, Cluster- und Collectorprofil ab. Sie enthalten keine Zugangsdaten oder Schlüssel. Pfade, Hardware, Namen und Authentifizierung müssen zum jeweiligen Standort passen.

Der Standardaufbau ist in der [Installationsanleitung](monitoringserver.de.md) beschrieben. Die [Einheitenübersicht](units.de.md) erläutert die übernommenen Metriken. Die Clusterdefinition wird gegen das unveränderte offizielle Schema geprüft; Ausnahmen für einzelne Einheiten sind nicht vorgesehen.

### `cc-backend/config.json`

`main.api-allowed-ips` enthält den Platzhalter `__API_CLIENT_IP__`.
Vor dem Start müssen an seiner Stelle die zulässigen IP-Adressen der API-Clients stehen
(je ein Eintrag pro IPv4- oder IPv6-Adresse; keine CIDR-Netze).

[Backend-Konfiguration öffnen](examples/rub/cc-backend/config.json)

<details>
<summary>Backend-Konfiguration anzeigen</summary>

```json
--8<-- "examples/rub/cc-backend/config.json"
```

</details>

### `job-archive/cluster.json`

[Clusterdefinition öffnen](examples/rub/job-archive/cluster.json)

<details>
<summary>Clusterdefinition anzeigen</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

### `cc-backend/ui-config.json`

[UI-Konfiguration öffnen](examples/rub/cc-backend/ui-config.json)

<details>
<summary>UI-Konfiguration anzeigen</summary>

```json
--8<-- "examples/rub/cc-backend/ui-config.json"
```

</details>

### `cc-metric-collector/config.json`

[Collector-Hauptkonfiguration öffnen](examples/rub/cc-metric-collector/config.json)

<details>
<summary>Collector-Hauptkonfiguration anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/config.json"
```

</details>

### `cc-metric-collector/router.json`

[Routerkonfiguration öffnen](examples/rub/cc-metric-collector/router.json)

<details>
<summary>Routerkonfiguration anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/router.json"
```

</details>

### `cc-metric-collector/receivers.json`

Für diesen Aufbau sind keine Collector-Receiver aktiv; die Datei enthält `{}`.

[Receiverkonfiguration öffnen](examples/rub/cc-metric-collector/receivers.json)

<details>
<summary>Receiverkonfiguration anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/receivers.json"
```

</details>

### `cc-metric-collector/sinks.json`

[Sinkkonfiguration öffnen](examples/rub/cc-metric-collector/sinks.json)

<details>
<summary>Sinkkonfiguration anzeigen</summary>

```json
--8<-- "examples/rub/cc-metric-collector/sinks.json"
```

</details>
