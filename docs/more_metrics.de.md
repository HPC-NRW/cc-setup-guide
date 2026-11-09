<a id="schritt-fur-schritt-weitere-metriken"></a>

# Weitere Metriken auswählen

!!! info "Optionale Erweiterungen"
    Voraussetzung ist eine funktionierende [erste Metrik](metrics.de.md). Die folgenden Rezepte erweitern dieses Setup nach Bedarf. Welche Collectoren sinnvoll sind, hängt von Hardware, Dateisystemen und den Fragen an das Job-Monitoring ab.

| Bereich | Collectoren | Voraussetzungen und Scope |
|---|---|---|
| [CPU](#cpu) | `loadavg`, `schedstat` | Linux-Prozess- und CPU-Statistiken; `node` oder `hwthread` |
| [Arbeitsspeicher](#arbeitsspeicher) | `memstat`, `slurm_cgroup` | Passende NUMA-Topologie; für Jobwerte lesbare Slurm-cgroups; `node`, `memoryDomain` oder `hwthread` |
| [Lokaler Speicher](#lokaler-speicher) | `diskstat` | Passende Mount- und Gerätefilter; `node` |
| [Netzwerk](#netzwerk) | `ibstat`, `netstat` | Vorhandene Interfaces; für Raten mindestens zwei Messungen; `node` |
| [Dateisysteme](#filesysteme) | `lustrestat`, `nfsiostat` | Genutztes Dateisystem und dessen Werkzeuge; `node` |
| [GPU](#gpu) | `nvidia` | NVIDIA-GPUs und Zugriff auf ihre Messwerte; `accelerator` |

Die [offizielle Collector-Übersicht](https://github.com/ClusterCockpit/cc-metric-collector/tree/v0.8.4/collectors) beschreibt weitere Messwerte und Optionen. Sofern ein Rezept nichts anderes angibt, gilt `scope: node`. Die zusätzliche Erfassung von Hardwarezählern ist unter [LIKWID-Metriken](likwid_metrics.de.md) beschrieben.

## Rezepte in die bestehende Konfiguration übernehmen

Jede Erweiterung betrifft drei Stellen: den Collector, das Routing und den Eintrag in `cluster.json`. Der [Weg eines Messwerts](metric_flow.de.md) zeigt die beteiligten Dateien. Die [Backendkonfiguration](metric_receive_display.de.md#minimaler-eintrag) beschreibt Namen, Scope, Einheit, Aggregation und Intervall.

Die Ausschnitte zeigen eine schrittweise wachsende Beispielkonfiguration. Einzelne Rezepte können unabhängig ausgewählt werden; ihre kumulativen Positivlisten enthalten teilweise auch Namen aus vorherigen Rezepten. In der eigenen Konfiguration muss die Positivliste alle bewusst aktivierten Zielmetriken einschließlich `cpu_load` enthalten.

- Die vorhandene `stage_order` bleibt erhalten: zuerst umbenennen, dann filtern, Metadaten ergänzen und Einheiten skalieren.
- Neue `rename_messages`- und `change_unit_prefix`-Einträge ergänzen die bestehenden Einträge. Bestehende `add_meta_if`-Regeln bleiben ebenfalls erhalten.
- Ein vollständiger `drop_messages_if`-Block ersetzt die bisherige Liste. Benötigte Geräte- und Exportfilter dürfen dabei nicht verloren gehen.
- Filter und Umrechnungen verwenden die Namen nach dem Routing. Der Backend-Eintrag muss genau zu diesem Namen und zum Scope passen.

Nach jeder Erweiterung helfen die ungerundete stdout-Ausgabe, der Vergleich von Cluster-/Hostnamen und ein Blick auf die passende Node-Zeitreihe. Für abgeleitete Werte ist ein Lauf über mehrere Messintervalle nötig. Die Prüfung und der Übergang zum Dauerbetrieb stehen [am Ende dieser Seite](#konfiguration-prufen).

<a id="cpustat"></a>
<a id="numastats"></a>
<a id="iostat"></a>
<a id="nfs4stat"></a>

Die Rezepte verwenden Einheiten des unveränderten Upstreamschemas. Prozentwerte, Paketraten und Operationszähler sind deshalb nicht Teil des Backendprofils. Das betrifft hier `cpustat`, `numastats`, `iostat` und `nfs4stat` sowie einzelne Werte der Netzwerk-, Lustre- und GPU-Collectoren. [Einheiten und Validierung](units.de.md) erklärt die Auswahl.

## CPU

### loadavg (Recap)

Der Collector `loadavg` liefert `load_one`, `load_five`, `load_fifteen`, `proc_run` und `proc_total`. Das Beispiel verwendet weiterhin nur `load_one` und benennt den Wert in `cpu_load` um.

`collectors.json`:
```json
"loadavg": {}
```

`router.json` (Auszug):
```json
"process_messages": {
  "stage_order": [
    "add_tag",
    "rename",
    "rename_if",
    "drop_by_type",
    "drop_by_name",
    "drop_if",
    "add_meta",
    "change_unit_prefix",
    "normalize_unit"
  ],
  "hostname_tag": "hostname",
  "rename_messages": {
    "load_one": "cpu_load"
  },
  "drop_messages_if": [
    "!(name in ['cpu_load'])"
  ]
}
```
Die folgenden Ausschnitte erweitern die Positivliste und die Umbenennungen in derselben `router.json`. Alle `drop_messages_if`- und `change_unit_prefix`-Blöcke gehören zu deren Abschnitt `process_messages`.


### schedstat

`schedstat` liefert mit `cpu_load_core` die dimensionslose Auslastung pro Hardware-Thread (`scope: hwthread`). Unterschiede zwischen Threads können auf unpassendes Pinning hinweisen.

`collectors.json`:

```json
"schedstat": {}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core'])"
]
```

##  Arbeitsspeicher
### memstat
`memstat` liest unter anderem folgende Werte aus `/proc/meminfo`:
```
MemTotal:       32278500 kB
MemFree:         8472384 kB
MemAvailable:   19816380 kB
Buffers:            6656 kB
Cached:         12963688 kB
```
Das Beispiel verwendet `mem_used`, berechnet als `mem_total − (mem_free + mem_buffers + mem_cached)`.

NUMA-Werte benötigen `scope: memoryDomain` und die passende Topologie in `cluster.json`. Das RUB-Beispiel speichert `mem_used` auf dieser Ebene. Die zusätzlich gelieferte Node-Metrik lässt sich unter demselben Namen nicht als zweite Speicherdimension ablegen.

`collectors.json`:
```json
"memstat": {
  "node_stats": true,
  "numa_stats": true
}
```

Collector 0.8.4 übernimmt das Linux-Label `kB` unverändert, obwohl `/proc/meminfo` damit KiB bezeichnet. Die folgende Regel korrigiert deshalb nur für `mem_used` das Label zu `KiB`, bevor sie nach GB skaliert. So ergeben 1.048.576 Quelleinheiten 1,073741824 GB. Bestehende `add_meta_if`-Regeln bleiben erhalten; `add_meta` muss vor `change_unit_prefix` laufen. Die [Einheitenübersicht](units.de.md) erklärt den Unterschied genauer.

`router.json`:
```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used'])"
],
"add_meta_if": [
  {
    "if": "name == 'mem_used' && meta.unit == 'kB'",
    "key": "unit",
    "value": "KiB"
  }
],
"change_unit_prefix": {
  "name == 'mem_used'": "G"
}
```

### slurm_cgroup

Collector v0.8.4 legt `hwthread` als Scope fest; ein zusätzliches Configfeld `scope` ist ungültig. Erforderlich sind lesbare Slurm-cgroups und eine `cgroup_base`, die zum lokalen Layout passt. Die erste Prüfung erfolgt ohne `use_sudo` mit gezielten Leserechten. Eine pauschale sudo-Freigabe ist dafür nicht vorgesehen.

`slurm_cgroup` liest den Arbeitsspeicherverbrauch aus den Slurm-cgroups eines Jobs und verteilt ihn auf dessen belegte Kerne. Die Metrik `job_mem_used` erscheint dadurch pro Hardware-Thread und lässt sich den CPU-Kernen des Jobs zuordnen.

`collectors.json`:
```json
"slurm_cgroup": {}
```

`router.json`:
```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used'])"
],
"change_unit_prefix": {
  "name == 'job_mem_used'": "G"
}
```


## Lokaler Speicher
`diskstat` erfasst den freien Speicher einer ausgewählten lokalen Partition.
### diskstat

`diskstat` liest `/proc/self/mounts` und liefert pro Mountpunkt die Größe (`disk_total`), den freien Platz (`disk_free`) und den Belegungsgrad (`part_max_used`). Mountpunkte mit `loop` oder `boot` im Namen werden ignoriert.
Weitere auszuschließende Mountpunkte stehen in `collectors.json`, hier beispielsweise `log`:

```json
"diskstat": {
  "exclude_mounts": [
    "log"
  ]
}
```

Das Beispiel übernimmt ausschließlich `disk_free`.

Für das folgende Partitionslayout
```bash
/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=winnt,errors=remount-ro 0 0
/dev/nvme0n1p2 / xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,noquota 0 0
/dev/nvme0n1p3 /var/log xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
/dev/nvme0n1p4 /var/slurm-tmpfs xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
```
bleiben zwei Nachrichten übrig:
```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p2,hostname=cpu001,type=node,unit=GB value=41u 1757426394108539349
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```

Die Nachrichten unterscheiden sich nur im `device`-Tag. In dieser Konfiguration verarbeitet `cc-backend` für die Metrik nur die zuerst eingehende Nachricht; die Werte werden nicht addiert. Das Root-Dateisystem `/` lässt sich hier nicht über `exclude_mounts` herausfiltern.
Der `messageProcessor` begrenzt die Ausgabe auf das gewünschte Gerät:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free'])",
  "name == 'disk_free' && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'disk_free'": "G"
}
```

Danach bleibt nur die gewünschte Partition:

```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```


## Netzwerk

### ibstat

`ibstat` erfasst Link- und Traffic-Metriken für InfiniBand und Omni-Path. Beide stellen ihre Geräte unter Linux über `/sys/class/infiniband/<dev>/ports/<port>/...` bereit.

Standardmäßig liefert der Collector absolute Zählerstände. Das Beispiel deaktiviert diese Werte und aktiviert abgeleitete Raten. Der Router übernimmt daraus nur die Bandbreiten in Byte pro Sekunde.

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
  "ib_xmit_bw": "ib_xmit"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free', 'ib_recv', 'ib_xmit'])",
  "(name in ['disk_free']) && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'ib_recv'": "M",
  "name == 'ib_xmit'": "M"
}
```

Abgeleitete Werte benötigen mindestens zwei Messungen. Bei einem Start mit `-once` erscheinen sie deshalb nicht.

---

### netstat

`netstat` erfasst Netzwerkmetriken für Ethernet-Interfaces. Mehrere konfigurierte Interfacenamen erlauben eine gemeinsame Konfiguration für unterschiedliche Knotengruppen.

Das Beispiel übernimmt die Bandbreiten `net_bytes_in_bw` und `net_bytes_out_bw` in Byte/s. Paketraten werden vom Router verworfen.

`collectors.json`:

```json
"netstat": {
  "include_devices": [
    "eth0",
    "eno1",
    "eno1no0"
  ],
  "send_abs_values": false,
  "send_derived_values": true
}
```

`router.json`:

```json
"rename_messages": {
  "net_bytes_in_bw": "net_bytes_in",
  "net_bytes_out_bw": "net_bytes_out"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free', 'ib_recv', 'ib_xmit', 'net_bytes_in', 'net_bytes_out'])",
  "(name in ['disk_free']) && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'net_bytes_in'": "M",
  "name == 'net_bytes_out'": "M"
}
```

Die `rename_messages`-Einträge geben den Bandbreiten die Zielnamen `net_bytes_in` und `net_bytes_out`.

---

## Filesysteme

### lustrestat

`lustrestat` liest mit `lctl` die Lustre-Client-Statistik. Das Beispiel übernimmt `lustre_read_bw` und `lustre_write_bw`, also die Lese- und Schreibbandbreite in Byte/s. Operationszähler bleiben ausgeschlossen.

`collectors.json`:

```json
"lustrestat": {
  "send_abs_values": false,
  "send_diff_values": false,
  "send_derived_values": true
}
```

`router.json`:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free', 'ib_recv', 'ib_xmit', 'net_bytes_in', 'net_bytes_out', 'lustre_read_bw', 'lustre_write_bw'])",
  "(name in ['disk_free']) && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'lustre_read_bw'": "M",
  "name == 'lustre_write_bw'": "M"
}
```

---


### nfsiostat

`nfsiostat` liefert Statistiken für NFS-Mounts. Das Beispiel übernimmt die abgeleiteten Lese- und Schreibbandbreiten `nfsio_nread` und `nfsio_nwrite` in Byte/s.

`collectors.json`:

```json
"nfsiostat": {
  "send_abs_values": false,
  "send_derived_values": true,
  "use_server_as_stype": true
}
```

`router.json`:

```json
"rename_messages": {
  "nfsio_nread_bw": "nfsio_nread",
  "nfsio_nwrite_bw": "nfsio_nwrite"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free', 'ib_recv', 'ib_xmit', 'net_bytes_in', 'net_bytes_out', 'lustre_read_bw', 'lustre_write_bw', 'nfsio_nread', 'nfsio_nwrite'])",
  "name == 'disk_free' && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'nfsio_nread'": "M",
  "name == 'nfsio_nwrite'": "M"
}
```

## GPU

### nvidia

`nvidia` erfasst GPU-Messwerte. Das Beispiel übernimmt Speicherbelegung und Leistungsaufnahme; Prozentwerte und Prozesszähler werden verworfen. Die optionalen Flags im Beispiel vereinfachen MIG-Geräte und unterdrücken zusätzliche Metadaten, um das Datenvolumen zu begrenzen.

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
  "nv_fb_mem_used": "acc_mem_used",
  "nv_power_usage": "acc_power"
},
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free', 'ib_recv', 'ib_xmit', 'net_bytes_in', 'net_bytes_out', 'lustre_read_bw', 'lustre_write_bw', 'nfsio_nread', 'nfsio_nwrite', 'acc_mem_used', 'acc_power'])",
  "(name in ['disk_free']) && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'acc_mem_used'": "G"
}
```

<details>
<summary><strong>customcmd: Eigene Skripte einbinden</strong></summary>

`customcmd` übernimmt die Ausgabe eines ausführbaren Skripts als Metrik. Das folgende Beispiel liest die Gesamtleistungsaufnahme eines Knotens mit `ipmi-sensors` und gibt sie als `node_total_power` im InfluxDB Line Protocol aus.

Das veröffentlichte CPU-Profil aktiviert diesen optionalen Collector nicht. Eine lokale Einrichtung benötigt passende Sensoren, Berechtigungen und einen Clusternamen. Außerdem muss das Skript über `customcmd` eingebunden sein und `node_total_power` sowohl in der Router-Positivliste als auch in `cluster.json` vorkommen.

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
<summary><strong>Vollständige collectors.json des Beispiels</strong></summary>

```json
{
  "loadavg": {},
  "schedstat": {},
  "memstat": {
    "node_stats": true,
    "numa_stats": true
  },
  "slurm_cgroup": {},
  "diskstat": {
    "exclude_mounts": [
      "log"
    ]
  },
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
  "lustrestat": {
    "send_abs_values": false,
    "send_diff_values": false,
    "send_derived_values": true
  },
  "nfsiostat": {
    "send_abs_values": false,
    "send_derived_values": true,
    "use_server_as_stype": true
  },
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
<summary><strong>Vollständige router.json des Beispiels</strong></summary>

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
    "stage_order": [
      "add_tag",
      "rename",
      "rename_if",
      "drop_by_type",
      "drop_by_name",
      "drop_if",
      "add_meta",
      "change_unit_prefix",
      "normalize_unit"
    ],
    "rename_messages": {
      "load_one": "cpu_load",
      "net_bytes_in_bw": "net_bytes_in",
      "net_bytes_out_bw": "net_bytes_out",
      "ib_recv_bw": "ib_recv",
      "ib_xmit_bw": "ib_xmit",
      "nv_fb_mem_used": "acc_mem_used",
      "nv_power_usage": "acc_power",
      "nfsio_nread_bw": "nfsio_nread",
      "nfsio_nwrite_bw": "nfsio_nwrite"
    },
    "drop_messages_if": [
      "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free', 'ib_recv', 'ib_xmit', 'net_bytes_in', 'net_bytes_out', 'lustre_read_bw', 'lustre_write_bw', 'nfsio_nread', 'nfsio_nwrite', 'acc_mem_used', 'acc_power'])",
      "(name in ['disk_free']) && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
    ],
    "add_meta_if": [
      {
        "if": "name == 'mem_used' && meta.unit == 'kB'",
        "key": "unit",
        "value": "KiB"
      }
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

Weitere hardwareabhängige Erweiterungen stehen unter [LIKWID-Metriken](likwid_metrics.de.md). Die [RUB-Beispielkonfiguration](example_profiles.de.md) zeigt ein vollständiges Standortprofil.


## Konfiguration prüfen

Nach dem Kopieren des vollständigen Routers muss die Standortidentität erneut gesetzt werden. Dafür gelten dieselben Cluster-/HTTPS-Zielwerte und dieselbe geschützte Tokendatei wie im Setup. `__CLUSTER__` ist ein Platzhalter und darf nicht stehen bleiben. Der einmalige stdout-Test prüft `cpu_load`, Cluster und Hostname. Abgeleitete Metriken sind bei diesem Aufruf noch nicht zu erwarten.

Hilfsskript [configure-collector.py öffnen oder herunterladen](scripts/configure-collector.py).

```bash
python3 "$GUIDE_DIR/docs/scripts/configure-collector.py" \
  --directory "$COLLECTOR_DIR" --cluster demo_cluster \
  --url 'https://monitoring.example.org/api/write/?cluster=demo_cluster' \
  --token-file "$TOKEN_FILE"
cd "$COLLECTOR_DIR"
./cc-metric-collector -config ./config_stdout.json -once
```


Für abgeleitete Metriken läuft der Collector anschließend über mehrere Messintervalle:

```bash
./cc-metric-collector -config ./config_stdout.json
```

Der Lauf endet mit `Strg+C`. Die Ausgabe muss jetzt zusätzlich die bewusst aktivierten Metriken mit passenden Namen, Einheiten und Hardware-IDs enthalten. Ein Vergleich mit [Einheiten und Validierung](units.de.md) hilft, doppelte Umrechnungen und falsche Scopes zu erkennen. Nach dem Eintrag der Metriken im Backend und der [Prüfung des Empfangs](metric_receive_display.de.md) folgt der [Collector als Dienst](collector_service.de.md).
