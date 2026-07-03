# Schritt-für-Schritt: Weitere Metriken

!!! info "Schritt-für-Schritt · Teil 2/2"
    Dieses Kapitel baut direkt auf [Schritt-für-Schritt: Erste Metrik](metrics.de.md) auf.  
    Arbeiten Sie zuerst Teil 1 durch, damit alle Basisdateien und Umbenennungen vorhanden sind.

Dies ist der zweite Teil der Schritt-für-Schritt-Reihe und baut auf der ersten Metrik (`cpu_load`) auf.  
Eine Übersicht über alle verfügbaren Collectoren gibt es unter https://github.com/ClusterCockpit/cc-metric-collector/tree/main/collectors

In den READMEs jedes Collectors werden die erhebbaren Metriken und Konfigurationsmöglichkeiten aufgezeigt.  
Sofern im jeweiligen Abschnitt nichts anderes erwähnt wird, gilt `scope: node`.

> Hinweis: In `cc-lib`-Versionen bis einschließlich `v0.10.1` mussten `drop_messages_if` und `change_unit_prefix` mit den *originalen* Metriknamen befüllt werden. Seit der aktuellen Version gelten die umbenannten Namen (also nach `rename_messages`). Die Beispiele unten orientieren sich an diesem neuen Verhalten.

## CPU

### loadavg (Recap)

Der Collector `loadavg` liefert `load_one`, `load_five`, `load_fifteen`, `proc_run` und `proc_total`. Für ClusterCockpit genügt weiterhin `load_one`, das in `cpu_load` umbenannt wird.  

`collectors.json`:
```json
"loadavg": {}
```

`router.json` (Auszug):
```json
"process_messages": {
  "hostname_tag": "hostname",
  "rename_messages": {
    "load_one": "cpu_load"
  },
  "drop_messages_if": [
    "!(name in ['cpu_load'])"
  ]
}
```
Die Positivliste in `drop_messages_if` und die `rename_messages` Liste wird im Laufe dieses Kapitels um weitere Metriken ergänzt. Sämtliche folgenden `drop_messages_if`- und `change_unit_prefix`-Blöcke beziehen sich weiterhin auf den Abschnitt `process_messages` in derselben `router.json`.

### cpustat

`cpustat` zapft `/proc/stat` an und liefert CPU-Zeiten pro Hardware-Thread. Für das Job-Monitoring genügt `cpu_user`, das die Nutzerzeit je Kern anzeigt (scope: `hwthread`). Die Messung wird automatisch auf jeden Hardware-Thread angewendet.

`collectors.json`:
```json
"cpustat": {}
```

`router.json`:
```json
  "drop_messages_if": [
    "!(name in ['cpu_load', 'cpu_user'])"
  ]
```
Damit `cpu_user` erhalten bleibt, wird es der Positivliste `drop_messages_if` hinzugefügt (siehe Router-Auszug oben). Weitere vom Collector gelieferte Spalten wie `cpu_system` oder `cpu_idle` werden damit verworfen.

### schedstat

Der Collector `schedstat` liefert `cpu_load_core`, das die Auslastung pro Kern (scope: `hwthread`) zeigt und falsches Pinning sichtbar macht.

`collectors.json`:
```json
"schedstat": {}
```

`router.json`:
```json
  "drop_messages_if": [
    "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core'])"
  ]
```
##  Arbeitsspeicher
## memstat
Der Collector `memstat` sammelt einige Metriken aus `/proc/meminfo`:
```
MemTotal:       32278500 kB
MemFree:         8472384 kB
MemAvailable:   19816380 kB
Buffers:            6656 kB
Cached:         12963688 kB
```
Erfasst wird `mem_used` (=`mem_total`-(`mem_free` + `mem_buffers` + `mem_cached`)).

Man kann konfigurieren, dass die Metriken auf Ebene der NUMA Subcluster erhoben werden (scope: memoryDomain), allerdings kann `cc-backend` in der Version aus dem `main`-Branch diese Werte nicht zuordnen.

`collectors.json`:
```json
  "memstat": {
    "node_stats": true,
    "numa_stats": true
  }
```

`router.json`:
```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used'])"
],
"change_unit_prefix": {
  "name == 'mem_used'": "G"
}
```

### slurm_cgroup

Der Collector `slurm_cgroup` liest die von Slurm angelegten cgroups aus, ermittelt daraus den Arbeitsspeicherverbrauch pro Job und verteilt den Wert auf die vom Job belegten Kerne. Dadurch entsteht eine pro Hardware-Thread (`scope: hwthread`) sichtbare Metrik `job_mem_used`, die direkt mit den CPU-Kernen eines Jobs korreliert.

`collectors.json`:
```json
"slurm_cgroup": {
}
```

`router.json`:
```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used'])"
],
"change_unit_prefix": {
  "name == 'job_mem_used'": "G"
}
```

### numastats

`numastats` wertet `/sys/devices/system/node/node*/numastat` aus und liefert daraus abgeleitete Ereigniszähler pro Sekunde (`count/s`) für die einzelnen NUMA-Domains (`scope: memoryDomain`). Damit lässt sich schnell erkennen, ob Interleave-Strategien greifen oder Speicherzugriffe häufig außerhalb der lokalen NUMA-Domain stattfinden.

`collectors.json`:

```json
"numastats": {
  "send_abs_values": false,
  "send_derived_values": true
}
```

`router.json` (Auszug):

```json
"rename_messages": {
  "numastats_interleave_hit_rate": "numastats_interleave_hit",
  "numastats_local_node_rate": "numastats_local_node",
  "numastats_numa_foreign_rate": "numastats_numa_foreign",
  "numastats_numa_hit_rate": "numastats_numa_hit",
  "numastats_numa_miss_rate": "numastats_numa_miss",
  "numastats_other_node_rate": "numastats_other_node"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node'])"
]
```


## Lokaler Speicher
Für stateful Knoten bieten sich zwei Collectoren an:
### diskstat

Liest `/proc/self/mounts` aus und liefert pro Mountpunkt Festplattengröße (`disk_total`), freien Platz (`disk_free`) und Belegungsgrad (`part_max_used`). Dabei werden Mountpunkte mit `loop` und `boot` im Namen ignoriert.
In der `collectors.json` können weitere zu exkludierende Mountpunkte angegeben werden, z.B. `log`:

```json
"diskstat": {
    "exclude_mounts": [
      "log"
    ]
}
```

Erfasst wird ausschließlich `disk_free`.

Bei unserem Partitionslayout
```bash
/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=winnt,errors=remount-ro 0 0
/dev/nvme0n1p2 / xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,noquota 0 0
/dev/nvme0n1p3 /var/log xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
/dev/nvme0n1p4 /var/slurm-tmpfs xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
```
werden noch zwei Nachrichten versendet:
```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p2,hostname=cpu001,type=node,unit=GB value=41u 1757426394108539349
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```

Die beiden Nachrichten unterscheiden sich nur durch das `device`-Tag. Die Werte werden von `cc-backend` nicht aufsummiert. Es wird nur der Wert der ersten Nachricht verarbeitet. Da es sich um das Dateisystem "`/`" handelt, kann es mit `exclude_mounts` nicht herausgefiltert werden.
Die Filterung erfolgt über den `messageProcessor`:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free'])",

  "name == 'disk_free' && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'disk_free'": "G"
}
```

Danach erhalten wir nur noch gewünschte Partition:

```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```

### iostat

Liest Daten zu I/O Statistiken aus `/proc/diskstats` aus. Dabei werden nur die Differenzwerte zur letzen Messung gesendet. Ähnlich wie bei `diskstat` filtern wir nur nach der gewünschten Partition. Außerdem interessieren uns nur `io_reads` und `io_writes`:

`collectors.json`:
```json
"iostat": {}
```

`router.json`:
```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes'])",

  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
```
---

## Netzwerk

### ibstat

Der Collector `ibstat` erfasst Link- und Traffic-Metriken für Highspeed-Interconnects unter Linux. Er funktioniert nicht nur mit InfiniBand, sondern auch mit Omni-Path, da beide ihre Geräte unter `/sys/class/infiniband/<dev>/ports/<port>/...` exponieren.

Standardmäßig werden absolute Zählerstände gesendet. Für eine aussagekräftige Zeitreihe benötigen wir Bandbreitenwerte, also pro Sekunde (abgeleitet aus Differenzen). Dafür schalten wir absolute Werte aus und abgeleitete Werte ein.

`collectors.json`:

```json
"ibstat": {
  "send_abs_values": false,
  "send_derived_values": true
}
```

`router.json`:

```json
"rename_messages": {
  "ib_recv_bw": "ib_recv",
  "ib_xmit_bw": "ib_xmit",
  "ib_recv_pkts_bw": "ib_recv_pkts",
  "ib_xmit_pkts_bw": "ib_xmit_pkts"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'ib_recv'": "M",
  "name == 'ib_xmit'": "M"
}
```

Hinweis: Abgeleitete Werte entstehen aus zwei Messungen. Diese Metriken erscheinen nicht, wenn `cc-metric-collector` mit der Option `-once` läuft.

---

### netstat

Der Collector `netstat` liefert Netzwerkmetriken für Ethernet-Interfaces. Um eine einzige Konfiguration für heterogene Knotengruppen wiederzuverwenden kann man mehrere Namen angeben.

Abgeleitete Werte werden aktiviert, damit die Bandbreiten direkt vorliegen. Der Collector liefert:

* `net_bytes_in_bw`  Einheit bytes/s
* `net_bytes_out_bw` Einheit bytes/s
* `net_pkts_in_bw`   Einheit packets/s
* `net_pkts_out_bw`  Einheit packets/s

`collectors.json`:

```json
"netstat": {
  "include_devices": [
    "eth0", "eno1", "eno1no0"
    ],
  "send_abs_values": false,
  "send_derived_values": true,
  }
```

`router.json`:

```json
"rename_messages": {
  "net_bytes_in_bw": "net_bytes_in",
  "net_bytes_out_bw": "net_bytes_out",
  "net_pkts_in_bw": "net_pkts_in",
  "net_pkts_out_bw": "net_pkts_out"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'net_bytes_in'": "M",
  "name == 'net_bytes_out'": "M"
}
```

Die zuvor definierte `rename_messages`-Liste sorgt dafür, dass die Bandbreitenkennzahlen als `net_bytes_*` bzw. `net_pkts_*` geführt werden.

---

## Filesysteme

### lustrestat

Der Collector `lustrestat` verwendet das Kommando `lctl` und liefert Statistiken zu Lustre-Clients. Standardmäßig werden eine Vielzahl von Countern erhoben.
Für die meisten Anwendungsfälle reicht es, sich auf folgende Metriken zu konzentrieren:

* `lustre_read_bw` (Lese-Bandbreite in bytes/sec)
* `lustre_write_bw` (Schreib-Bandbreite in bytes/sec)
* `lustre_open` (Anzahl geöffneter Dateien seit der letzten Messung)
* `lustre_close` (Anzahl geschlossener Dateien seit der letzten Messung)
* `lustre_statfs` (Differenzen aus `statfs`-Aufrufen)

`collectors.json`:

```json
"lustrestat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'lustre_read_bw'": "M",
  "name == 'lustre_write_bw'": "M"
}
```

---

### nfs4stat

Der Collector `nfs4stat` basiert auf dem Kommando `nfsstat` und erhebt NFSv4-Client-Counter.
Im Vordergrund stehen die Dateizugriffszähler:

* `open_diff` (Anzahl der Dateiöffnungen seit letzter Messung)
* `close_diff` (Anzahl der Dateischließungen seit letzter Messung)

`collectors.json`:

```json
"nfs4stat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs', 'open_diff', 'close_diff'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
]
```

---

### nfsiostat

Der Collector `nfsiostat` liefert detaillierte Statistiken für NFS-Mounts, ähnlich dem bekannten Kommando `nfsiostat`.
Der Schwerpunkt liegt auf den abgeleiteten Bandbreiten:

* `nfsio_nread` (gelesene Daten in bytes/s)
* `nfsio_nwrite` (geschriebene Daten in bytes/s)

`collectors.json`:

```json
"nfsiostat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs', 'open_diff', 'close_diff', 'nfsio_nread', 'nfsio_nwrite'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'nfsio_nread'": "M",
  "name == 'nfsio_nwrite'": "M"
}
```

## GPU

### nvidia

Der Collector `nvidia` liefert zentrale GPU-Kennzahlen wie Auslastung, Speichernutzung und Leistungsaufnahme. Über optionale Flags lassen sich MIG-Geräte vereinfachen und zusätzliche Metadaten unterdrücken, damit das Datenvolumen überschaubar bleibt.

Scope: `accelerator`

`collectors.json`:

```json
"nvidia": {
  "process_mig_devices": false,
  "use_pci_info_as_type_id": true,
  "add_pci_info_tag": true,
  "add_uuid_meta": false,
  "add_board_number_meta": false,
  "add_serial_meta": false,
  "use_uuid_for_mig_device": false,
  "use_slice_for_mig_device": false
}
```

`router.json`:

```json
"rename_messages": {
  "nv_util": "acc_utilization",
  "nv_fb_mem_used": "acc_mem_used",
  "nv_power_usage": "acc_power",
  "nv_mem_util": "acc_mem_util"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs', 'open_diff', 'close_diff', 'nfsio_nread', 'nfsio_nwrite', 'acc_utilization', 'acc_mem_used', 'acc_power', 'acc_mem_util', 'nv_compute_processes'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'acc_mem_used'": "G"
}
```

<details>
<summary><strong>customcmd: Eigene Skripte einbinden</strong></summary>

Wenn kein dedizierter Collector existiert, kann `customcmd` ein beliebiges Skript starten und dessen Ausgabe als Metrik übernehmen. So lassen sich individuelle Sensoren oder Spezialfälle unkompliziert einbinden. Das Skript muss lediglich ausführbar sein und die Ausgabe im passenden Format liefern. Das folgende Beispiel liest die Gesamtleistungsaufnahme eines Knotens über `ipmi-sensors` aus und sendet sie im InfluxDB Line Protocol als `node_total_power` weiter:

```bash
#!/bin/bash
# Script to extract the overall node power consumption from ipmi-sensors output.
# It searches for "NODE_PWR" first, and if not found, then for "SYS_POWER".
# The extracted value is output in InfluxDB Line Protocol format:
#   Measurement: node_total_power
#   Tags: cluster, hostname, type, unit
#   Field: value
#   Timestamp: current time in nanoseconds

output=$(sudo /usr/sbin/ipmi-sensors --comma-separated-output)

# Search for "NODE_PWR" and extract the fourth field (reading)
value=$(echo "$output" | awk -F, '$2 == "NODE_PWR" {print $4; exit}')

# If "NODE_PWR" is not found, search for "SYS_POWER"
if [ -z "$value" ]; then
  value=$(echo "$output" | awk -F, '$2 ~ /SYS_POWER/ {print $4; exit}')
fi

# Exit with an error if no valid power metric is found
if [ -z "$value" ]; then
  echo "No valid power metric found" >&2
  exit 1
fi

host=$(hostname)
timestamp=$(date +%s%N)

echo "node_total_power,cluster=elysium,hostname=${host},type=node,unit=W value=${value} ${timestamp}"
```
</details>

---
<details>
<summary><strong>bis hierher erstellte collectors.json</strong></summary>

```json
    {
      "loadavg": {},
      "cpustat": {},
      "schedstat": {},
      "memstat": {
        "node_stats": true,
        "numa_stats": true
      },
      "slurm_cgroup": {
        "scope": "hwthread"
      },
      "numastats": {
        "send_abs_values": false,
        "send_derived_values": true
      },
      "diskstat": {
        "exclude_mounts": [
          "log"
        ]
      },
      "iostat": {},
      "ibstat": {
        "send_abs_values": false,
        "send_derived_values": true
      },
      "netstat": {
        "include_devices": [
          "eth0",
          "eno1",
          "eno1no0"
        ],
        "send_abs_values": false,
        "send_derived_values": true
      },
      "lustrestat": {},
      "nfs4stat": {},
      "nfsiostat": {},
      "nvidia": {
        "process_mig_devices": false,
        "use_pci_info_as_type_id": true,
        "add_pci_info_tag": true,
        "add_uuid_meta": false,
        "add_board_number_meta": false,
        "add_serial_meta": false,
        "use_uuid_for_mig_device": false,
        "use_slice_for_mig_device": false
      }
    }
```

</details>

<details>
<summary><strong>Beispiel: bis hierher erstellte router.json</strong></summary>

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
      "normalize_units": true,
      "process_messages": {
        "rename_messages": {
          "load_one": "cpu_load",
          "net_bytes_in_bw": "net_bytes_in",
          "net_bytes_out_bw": "net_bytes_out",
          "net_pkts_in_bw": "net_pkts_in",
          "net_pkts_out_bw": "net_pkts_out",
          "ib_recv_bw": "ib_recv",
          "ib_xmit_bw": "ib_xmit",
          "ib_recv_pkts_bw": "ib_recv_pkts",
          "ib_xmit_pkts_bw": "ib_xmit_pkts",
          "lustre_open_diff": "lustre_open",
          "lustre_close_diff": "lustre_close",
          "lustre_statfs_diff": "lustre_statfs",
          "nv_util": "acc_utilization",
          "nv_fb_mem_used": "acc_mem_used",
          "nv_power_usage": "acc_power",
          "nv_mem_util": "acc_mem_util",
          "nfsio_nread_bw": "nfsio_nread",
          "nfsio_nwrite_bw": "nfsio_nwrite",
          "numastats_interleave_hit_rate": "numastats_interleave_hit",
          "numastats_local_node_rate": "numastats_local_node",
          "numastats_numa_foreign_rate": "numastats_numa_foreign",
          "numastats_numa_hit_rate": "numastats_numa_hit",
          "numastats_numa_miss_rate": "numastats_numa_miss",
          "numastats_other_node_rate": "numastats_other_node"
        },
        "drop_messages_if": [
          "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs', 'open_diff', 'close_diff', 'nfsio_nread', 'nfsio_nwrite', 'acc_utilization', 'acc_mem_used', 'acc_power', 'acc_mem_util', 'nv_compute_processes'])",
          "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
        ],
        "change_unit_prefix": {
          "name == 'mem_used'": "G",
          "name == 'job_mem_used'": "G",
          "name == 'disk_free'": "G",
          "name == 'ib_recv'": "M",
          "name == 'ib_xmit'": "M",
          "name == 'net_bytes_in'": "M",
          "name == 'net_bytes_out'": "M",
          "name == 'lustre_read_bw'": "M",
          "name == 'lustre_write_bw'": "M",
          "name == 'nfsio_nread'": "M",
          "name == 'nfsio_nwrite'": "M",
          "name == 'acc_mem_used'": "G"
        }
      }
    }
```
</details>

Als letztes fehlen nur noch die [LIKWID Metriken](likwid_metrics.de.md).
