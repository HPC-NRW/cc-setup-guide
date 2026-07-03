# cc-metric-collector Quick Setup

Diese Anleitung richtet sich an Administratoren, die sich schnell an einer bereits funktionierenden Konfiguration entlanghangeln wollen.  

## collectors.json (Beispiel für AMD Zen 4)

Die folgende Konfiguration basiert auf dem Elysium-Cluster der RUB und deckt typische CPU-, GPU-, Speicher-, Netzwerk- und Dateisystemmetriken ab.

```json
{
  "loadavg": {},
  "schedstat": {},
  "cpustat": {},
  "memstat": {
    "node_stats": true,
    "numa_stats": true
  },
  "slurm_cgroup": {
    "use_sudo": true
  },
  "numastats": {
    "send_abs_values": false,
    "send_derived_values": true
  },
  "diskstat": {
    "exclude_mounts": [
      "/scratch/slurm-tmpfs"
    ]
  },
  "iostat": {
    "exclude_devices": [
      "nvme0n1",
      "nvme0n1p1",
      "nvme0n1p2",
      "nvme0n1p3",
      "nvme1n1",
      "nvme1n1p1",
      "nvme2n1",
      "nvme2n1p1"
    ]
  },
  "lustrestat": {
    "lctl_command": "/usr/sbin/lctl",
    "send_abs_values": false,
    "send_derived_values": true,
    "send_diff_values": true,
    "use_sudo": true
  },
  "netstat": {
    "include_devices": [
      "eno1"
    ],
    "send_abs_values": false,
    "send_derived_values": true,
    "interface_aliases": {
      "eno1": [
        "eno1np0"
      ]
    }
  },
  "nfs4stat": {
    "nfsstat": "/usr/sbin/nfsstat"
  },
  "nfsiostat": {
    "use_server_as_stype": true,
    "send_abs_values": false,
    "send_derived_values": true
  },
  "ibstat": {
    "send_abs_values": false,
    "send_derived_values": true
  },
  "customcmd": {
    "commands": [
      "/usr/bin/total_node_power"
    ]
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
  },
  "likwid": {
    "force_overwrite": true,
    "invalid_to_zero": true,
    "access_mode": "accessdaemon",
    "accessdaemon_path": "/opt/likwid/sbin",
    "liblikwid_path": "/opt/likwid/lib/liblikwid.so",
    "lockfile_path": "/opt/cc-metric-collector/likwid.lock",
    "eventsets": [
      {
        "events": {
          "FIXC1": "ACTUAL_CPU_CLOCK",
          "PMC0": "RETIRED_INSTRUCTIONS",
          "PMC1": "CPU_CLOCKS_UNHALTED",
          "PMC2": "RETIRED_SSE_AVX_FLOPS_ALL",
          "PMC3": "MERGE",
          "PWR0": "RAPL_CORE_ENERGY"
        },
        "metrics": [
          {
            "calc": "1.0E-06*FIXC1/time",
            "name": "clock",
            "publish": true,
            "type": "hwthread"
          },
          {
            "calc": "PMC0/PMC1",
            "name": "ipc",
            "publish": true,
            "type": "hwthread"
          },
          {
            "calc": "time",
            "name": "Runtime (RDTSC) [s]",
            "publish": false,
            "type": "hwthread"
          },
          {
            "calc": "PWR0/time",
            "name": "core_power",
            "publish": true,
            "type": "hwthread"
          },
          {
            "calc": "1.0E-09*(PMC2)/time",
            "name": "flops_any",
            "publish": true,
            "type": "hwthread"
          }
        ]
      },
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
    ],
    "globalmetrics": [
      {
        "name": "mem_bw",
        "calc": "mem_read+mem_write",
        "type": "socket",
        "unit": "Gbyte/s",
        "publish": true
      }
    ]
  }
}
```

# **Collector-Übersicht nach Kategorien**

---

## CPU & Load

| Collector     | Metrik                                    | Scope    | Beschreibung                           |
| ------------- | ----------------------------------------- | -------- | ---------------------------------------|
| **loadavg**   | `cpu_load`                                | node     | 1-Minuten Load                         |
| **schedstat** | `cpu_load_core`                           | hwthread | Auslastung je Hardware-Thread          |
| **cpustat**   | `cpu_user`                                | hwthread | Nutzer-CPU-Anteile pro Hardware-Thread |
| **likwid**    | `clock`, `ipc`, `flops_any`, `core_power` | hwthread | CPU-Performance-Counter                |

---

## Memory & NUMA

| Collector        | Metrik             | Scope               | Beschreibung                        |
| ---------------- | ------------------ | ------------------- | ----------------------------------- |
| **memstat**      | `mem_used`         | node / memoryDomain | RAM-Belegung pro Node & NUMA-Domain |
| **slurm_cgroup** | `job_mem_used`     | hwthread            | Jobbezogene RAM-Auslastung          |
| **numastats**    | `numastats_*_rate` | memoryDomain        | NUMA-Migrationen & Misses/Sekunde   |
| **likwid**       | `mem_bw`           | socket              | Memory-Bandbreite pro Socket        |

---

## Storage (Lokal, Lustre, NFS)

| Collector      | Metrik                             | Scope | Beschreibung                               |
| -------------- | ---------------------------------- | ----- | ------------------------------------------ |
| **diskstat**   | `disk_free`                        | node  | Freier lokaler Plattenspeicher             |
| **iostat**     | `io_reads`, `io_writes`            | node  | Block-I/O, gefiltert auf gewünschte Geräte |
| **lustrestat** | diverse (`read_bw`, `open_diff`)   | node  | Lustre-Bandbreite & Operationen            |
| **nfs4stat**   | `nfs4_open`, `nfs4_close`          | node  | NFSv4-Aufrufstatistik                      |
| **nfsiostat**  | `nread`, `nwrite`, `n*_bw`         | node  | NFS-I/O pro Export                         |

---

## Netzwerk

| Collector   | Metrik                               | Scope | Beschreibung           |
| ----------- | ------------------------------------ | ----- | ---------------------- |
| **netstat** | `net_bytes_in_bw`, `net_pkts_out_bw` | node  | Ethernet-Durchsatz     |
| **ibstat**  | `ib_recv_bw`, `ib_xmit_pkts_bw`      | node  | InfiniBand-Performance |

---

## GPU

| Collector  | Metrik                                         | Scope       | Beschreibung                        |
| ---------- | ---------------------------------------------- | ----------- | ----------------------------------- |
| **nvidia** | `acc_utilization`, `acc_mem_used`, `acc_power` | accelerator | GPU-Auslastung, Verbrauch, Prozesse |

---

Folgende Anpassungen sind für eine eigene Konfiguration nötig:

- `use_sudo` nur auf `true` setzen, falls der Collector nicht als `root` läuft.
- `netstat`: Den Namen des Ethernet-Interfaces anpassen.
- `diskstat`: Filter auf die passende Partition abstimmen.
- `iostat`: Filter auf die gewünschte Partition abstimmen.
- `lustrestat` und `nfsstat`: Pfade für die Binaries anpassen.
- `likwid`: `"accessdaemon_path"`, `"liblikwid_path"` und `"lockfile_path"` auf die lokale LIKWID-Installation einstellen und passende Eventsets für die eigene CPU-Architektur hinterlegen (siehe [LIKWID Metriken](likwid_metrics.md)).


## router.json

```json
{
  "add_tags": [
    { "key": "cluster", "value": "elysium", "if": "*" }
  ],
  "interval_timestamp": false,
  "num_cache_intervals": 0,
  "process_messages": {
    "stage_order": ["add_tag","rename","rename_if","drop_by_type","drop_by_name","drop_if","change_unit_prefix","normalize_unit"],
    "hostname_tag": "hostname",
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
    "rename_messages_if": {},
    "drop_messages_if": [
      "name == 'disk_free' && !(tag.device == '/dev/nvme0n1p4' || tag.device == 'nvme0n1p4')",
      "name == 'io_reads'  && !(tag.device == '/dev/nvme0n1p4' || tag.device == 'nvme0n1p4')",
      "name == 'io_writes' && !(tag.device == '/dev/nvme0n1p4' || tag.device == 'nvme0n1p4')",
      "name == 'nfsio_nread'  && !(tag.stypeid matches 'home:/home')",
      "name == 'nfsio_nwrite' && !(tag.stypeid matches 'home:/home')",
      "messagetype == 'metric' && !(name in ['cpu_load','cpu_load_core','cpu_user','mem_used','numastats_interleave_hit','numastats_local_node','numastats_numa_foreign','numastats_numa_hit','numastats_numa_miss','numastats_other_node','disk_free','io_reads','io_writes','lustre_read_bw','lustre_write_bw','lustre_open','lustre_close','lustre_statfs','net_bytes_in','net_bytes_out','net_pkts_in','net_pkts_out','ib_recv','ib_xmit','ib_recv_pkts','ib_xmit_pkts','nfs4_open','nfs4_close','nfsio_nread','nfsio_nwrite','nread','nwrite','acc_utilization','acc_mem_used','acc_power','acc_mem_util','nv_compute_processes','mem_bw','flops_any','clock','ipc','core_power','node_total_power','job_mem_used'])"
    ],
    "change_unit_prefix": {
      "name == 'mem_used'": "G",
      "name == 'acc_mem_used'": "G",
      "name == 'lustre_read_bw'": "M",
      "name == 'lustre_write_bw'": "M",
      "name == 'ib_recv'": "M",
      "name == 'ib_xmit'": "M",
      "name == 'disk_free'": "G",
      "name == 'net_bytes_in'": "M",
      "name == 'net_bytes_out'": "M",
      "name == 'nfsio_nread'": "M",
      "name == 'nfsio_nwrite'": "M",
      "name == 'job_mem_used'": "G"
    }
  },
  "normalize_units": true
}
```

### Erklärung der wichtigsten Verarbeitungsschritte

- **add_tags** – versieht jede Nachricht mit dem Clusternamen `elysium` und sorgt so für eindeutige Zuordnung.
- **stage_order** – definiert die Reihenfolge der Verarbeitungsschritte; wichtig, wenn zusätzliche Transformationen ergänzt werden.
- **hostname_tag** – legt fest, dass der Hostname aus dem Tag `hostname` gelesen wird.
- **rename_messages** – bringt die Rohmetriken auf die in `cc-backend` verwendeten Namen. Im Wesentlichen werden die Suffixe `_bw` und `_rate` entfernt, außerdem werden GPU-Metriken auf den allgemeinen Präfix `acc` abgebildet.
- **drop_messages_if** – filtert unerwünschte Partitionen und Exporte heraus und reduziert den Datenstrom auf die benötigten Metriken. Da `rename_messages` vorher ausgeführt wird, beziehen sich die Filter auf die umbenannten Metriknamen.
- **change_unit_prefix** – vereinheitlicht Einheiten (z. B. Byte → GB oder MB) für die Anzeige. Auch diese Regeln verwenden die umbenannten Metriknamen.
- **normalize_units** – sorgt dafür, dass Einheiten nach den Umrechnungen konsistent geschrieben werden.

Wenn eine Metrik nicht eindeutig ist, wie bei `disk_free`, wo alle Partitionen aller Festplatten ausgegeben werden, verarbeitet `cc-backend` nur die erste eingehende Nachricht. Die übrigen werden verworfen. Daher ist eine gezielte Filterung notwendig.
Nachrichten mit demselben Namen für denselben Knoten – aber unterschiedlichen `stype`-Werten oder anderen Tags – können in dieser Konfiguration nicht nebeneinander im selben Graphen dargestellt werden.

In unserem Beispiel werden die `nfsio`-Metriken nur für den Export `/home` behalten, `/cluster` wird verworfen. Alternativ ließen sich die Metriken in der Rename-Stage umbenennen, z. B. zu `cluster_nfsio_nread`.
Dasselbe gilt für andere Metriken: Bei mehreren GPFS-Dateisystemen können diese umbenannt und getrennt erhoben werden. 


## Produktivbetrieb

Den Collector auf den gewünschten Knoten verteilen und dort als dedizierten Dienst starten, z. B. per systemd user service:

```ini
[Unit]
Description=ClusterCockpit metric collector
Documentation=https://github.com/ClusterCockpit/cc-metric-collector
After=lustre.mount
Requires=lustre.mount
Wants=network-online.target
Wants=lnet.service

[Service]
EnvironmentFile=/cluster/monitoring/cc-metric-collector/default
Environment="LD_LIBRARY_PATH=/cluster/monitoring/likwid/lib/:$LD_LIBRARY_PATH"
Environment="PATH=/usr/bin:/cluster/monitoring/likwid/sbin:/cluster/monitoring/likwid/bin:$PATH"
User=root
Type=simple
Restart=on-failure
WorkingDirectory=/cluster/monitoring/cc-metric-collector
ExecStart=/cluster/monitoring/cc-metric-collector/cc-metric-collector
LimitNOFILE=10000
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target

```

Nach dem Aktivieren des Service werden die Metriken im 60‑Sekunden-Intervall an `cc-backend` übertragen. Weitere Collectoren oder Umbenennungen lassen sich jederzeit durch Ergänzen der obigen JSON-Dateien hinzufügen.
