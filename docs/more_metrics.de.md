# Schritt-für-Schritt: Weitere Metriken

Dies ist der zweite Teil der Schritt-für-Schritt-Reihe und baut auf der ersten Metrik (`cpu_load`) auf.  
Eine Übersicht über alle verfügbaren Collectoren gibt es unter https://github.com/ClusterCockpit/cc-metric-collector/tree/main/collectors

In den READMEs jedes Collectors werden die erhebbaren Metriken und Konfigurationsmöglichkeiten aufgezeigt.

## CPU

### cpustat



### schedstat
Erhebt die Metrik `cpu_load_core`, die die Last pro Kern angibt. Sehr gut, um fehlerhaftes Pinning oder Oversubscription zu erkennen. (scope: hwthread)

`collectors.json`:
```json
"schedstat" : {}
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
Wir wollen `mem_used` erheben (=`mem_total`-(`mem_free`
 + `mem_buffers` + `mem_cached`))

Scope: Node

Man kann konfigurieren, dass die Metriken auf Ebene der NUMA Subcluster erhoben werden (scope: memoryDomain), allerdings kann `cc-backend` in der Version aus dem `main`-Branch diese Werte nicht zuordnen.

`collectors.json`:
```json
"memstat" : {}
```
`router.json`:
```json
"drop_messages_if": [
  "!(name in ['load_one', 'mem_used'])",
],
"change_unit_prefix": {
		"name == 'mem_used'" : "G"
	}
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

Wir wollen nur `disk_free` erheben.

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

Die beiden Nachrichten unterscheiden sich nur durch das `device`-Tag unterscheiden. Die Werte werden vom `cc-metric-store` nicht aufsummiert. Es wird nur der Wert der ersten Nachricht verarbeitet. Da es sich um das Dateisystem "`/`" handelt, kann es mit `exclude_mounts` nicht herausgefiltert werden.
Die Filterung erfolgt über den `messageProcessor`:

```json
"drop_messages_if": [
  "!(name in ['load_one', 'mem_used', 'disk_free'])",

  "name == 'disk_free' && tag.device != '/dev/nvme0n1p4'"
],
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
  "!(name in ['load_one', 'mem_used', 'disk_free', `io_reads`, `io_writes`])",

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
  "!(name in ['load_one', 'cpu_user', 'cpu_load_core', 'mem_used', 'disk_free', 'io_reads', 'io_writes', 'ib_recv_bw', 'ib_xmit_bw', 'ib_recv_pkts_bw', 'ib_xmit_pkts_bw'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
]
```

Hinweis: Abgeleitete Werte entstehen aus zwei Messungen. Diese Metriken erscheinen nicht, wenn `cc-metric-collector` mit der Option `-once` läuft.

---

### netstat

Der Collector `netstat` liefert Netzwerkmetriken für Ethernet-Interfaces. Um eine einzige Konfiguration für heterogene Knotengruppen wiederzuverwenden kann man mehrere Namen angeben.

Wir aktivieren abgeleitete Werte, damit wir die Bandbreiten erhalten. Die vom Collector gelieferten Metriken lauten:

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
"drop_messages_if": [
  "!(name in ['load_one', 'cpu_user', 'cpu_load_core', 'mem_used', 'disk_free', 'io_reads', 'io_writes', 'ib_recv_bw', 'ib_xmit_bw', 'ib_recv_pkts_bw', 'ib_xmit_pkts_bw', 'net_bytes_in_bw', 'net_bytes_out_bw', 'net_pkts_in_bw', 'net_pkts_out_bw'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
]
```

Wir benennen die Metriken über `rename_messages` um:

`router.json`
```json
"rename_messages": {
  "net_bytes_in_bw": "net_bytes_in",
  "net_bytes_out_bw": "net_bytes_out",
  "net_pkts_in_bw": "net_pkts_in",
  "net_pkts_out_bw": "net_pkts_out"
}
```

---

## Filesysteme

### lustrestat

Der Collector `lustrestat` verwendet das Kommando `lctl` und liefert Statistiken zu Lustre-Clients. Standardmäßig werden eine Vielzahl von Countern erhoben.
Für die meisten Anwendungsfälle reicht es, sich auf folgende Metriken zu konzentrieren:

* `lustre_read_bw` (Lese-Bandbreite in bytes/sec)
* `lustre_write_bw` (Schreib-Bandbreite in bytes/sec)
* `lustre_open_diff` (Anzahl geöffneter Dateien seit der letzten Messung)
* `lustre_close_diff` (Anzahl geschlossener Dateien seit der letzten Messung)
* `lustre_statfs_diff` (Differenzen aus `statfs`-Aufrufen)

`collectors.json`:

```json
"lustrestat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['load_one', 'cpu_user', 'cpu_load_core', 'mem_used', 'disk_free', 'io_reads', 'io_writes', 'ib_recv_bw', 'ib_xmit_bw', 'ib_recv_pkts_bw', 'ib_xmit_pkts_bw', 'net_bytes_in_bw', 'net_bytes_out_bw', 'net_pkts_in_bw', 'net_pkts_out_bw', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open_diff', 'lustre_close_diff', 'lustre_statfs_diff'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
]
```

---

### nfs4stat

Der Collector `nfs4stat` basiert auf dem Kommando `nfsstat` und erhebt NFSv4-Client-Counter.
Wir wollen hier vor allem Dateizugriffe erfassen:

* `open_diff` (Anzahl der Dateiöffnungen seit letzter Messung)
* `close_diff` (Anzahl der Dateischließungen seit letzter Messung)

`collectors.json`:

```json
"nfs4stat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['load_one', 'cpu_user', 'cpu_load_core', 'mem_used', 'disk_free', 'io_reads', 'io_writes', 'ib_recv_bw', 'ib_xmit_bw', 'ib_recv_pkts_bw', 'ib_xmit_pkts_bw', 'net_bytes_in_bw', 'net_bytes_out_bw', 'net_pkts_in_bw', 'net_pkts_out_bw', 'open_diff', 'close_diff'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
]
```

---

### nfsiostat

Der Collector `nfsiostat` liefert detaillierte Statistiken für NFS-Mounts, ähnlich dem bekannten Kommando `nfsiostat`.
Wir wollen uns hier auf die übertragenen Daten beschränken:

* `nread` (gelese Daten, bytes/sec bei abgeleiteten Werten)
* `nwrite` (geschriebene Daten, bytes/sec bei abgeleiteten Werten)

`collectors.json`:

```json
"nfsiostat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['load_one', 'cpu_user', 'cpu_load_core', 'mem_used', 'disk_free', 'io_reads', 'io_writes', 'ib_recv_bw', 'ib_xmit_bw', 'ib_recv_pkts_bw', 'ib_xmit_pkts_bw', 'net_bytes_in_bw', 'net_bytes_out_bw', 'net_pkts_in_bw', 'net_pkts_out_bw', 'nread', 'nwrite'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
]
```

## GPU
### nvidia

---

Weitere Beispielkonfigurationen finden sich in der [Collector-Übersicht](collectors.de.md) sowie bei den [LIKWID Metriken](likwid_metrics.de.md).
