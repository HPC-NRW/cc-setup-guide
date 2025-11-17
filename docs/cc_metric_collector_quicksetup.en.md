# cc-metric-collector quick setup

> **Note:** The `numastats` collector and the NUMA output of `memstat` (`numa_stats`) require modifications to the upstream `cc-backend`. Without these patches the values do not show up in the web UI.

This guide is aimed at administrators who want to build upon a working configuration.

## collectors.json (example for AMD Zen 4)

The following configuration is based on Ruhr University Bochum’s Elysium cluster and covers representative CPU, GPU, memory, network, and filesystem metrics.

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

# Collector overview by category

---

## CPU & Load

| Collector     | Metric                                    | Scope    | Description                          |
| ------------- | ----------------------------------------- | -------- | ------------------------------------ |
| **loadavg**   | `cpu_load`                                | node     | 1-minute load                        |
| **schedstat** | `cpu_load_core`                           | hwthread | Utilization per hardware thread      |
| **cpustat**   | `cpu_user`                                | hwthread | User CPU share per hardware thread   |
| **likwid**    | `clock`, `ipc`, `flops_any`, `core_power` | hwthread | CPU performance counters             |

---

## Memory & NUMA

| Collector        | Metric             | Scope               | Description                              |
| ---------------- | ------------------ | ------------------- | ---------------------------------------- |
| **memstat**      | `mem_used`         | node / memoryDomain | RAM usage per node and NUMA domain       |
| **slurm_cgroup** | `job_mem_used`     | hwthread            | Job-specific memory consumption          |
| **numastats**    | `numastats_*_rate` | memoryDomain        | NUMA migrations and misses per second    |
| **likwid**       | `mem_bw`           | socket              | Memory bandwidth per socket              |

---

## Storage (local, Lustre, NFS)

| Collector      | Metric                           | Scope | Description                                 |
| -------------- | -------------------------------- | ----- | ------------------------------------------- |
| **diskstat**   | `disk_free`                      | node  | Free local disk space                       |
| **iostat**     | `io_reads`, `io_writes`          | node  | Block I/O filtered to the desired devices   |
| **lustrestat** | multiple (`read_bw`, `open_diff`) | node  | Lustre bandwidth and operations             |
| **nfs4stat**   | `nfs4_open`, `nfs4_close`        | node  | NFSv4 call statistics                       |
| **nfsiostat**  | `nread`, `nwrite`, `n*_bw`       | node  | NFS I/O per export                          |

---

## Network

| Collector   | Metric                               | Scope | Description            |
| ----------- | ------------------------------------ | ----- | ---------------------- |
| **netstat** | `net_bytes_in_bw`, `net_pkts_out_bw` | node  | Ethernet throughput    |
| **ibstat**  | `ib_recv_bw`, `ib_xmit_pkts_bw`      | node  | InfiniBand performance |

---

## GPU

| Collector  | Metric                                         | Scope       | Description                          |
| ---------- | ---------------------------------------------- | ----------- | ------------------------------------ |
| **nvidia** | `acc_utilization`, `acc_mem_used`, `acc_power` | accelerator | GPU utilization, consumption, jobs   |

---

Adjust the configuration to fit your site:

- Only set `use_sudo` to `true` if the collector does not run as `root`.
- `netstat`: update the Ethernet interface name.
- `diskstat`: adjust the filter to the desired partition.
- `iostat`: likewise adapt the filter to the desired devices.
- `lustrestat` and `nfsstat`: update the paths to the binaries.
- `likwid`: set `accessdaemon_path`, `liblikwid_path`, and `lockfile_path` to your local installation and supply event sets that match your CPU architecture (see [LIKWID metrics](likwid_metrics.md)).

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
      "name == 'nfsio_nread_bw'  && !(tag.stypeid matches 'home:/home')",
      "name == 'nfsio_nwrite_bw' && !(tag.stypeid matches 'home:/home')",
      "messagetype == 'metric' && !(name in ['load_one','cpu_load_core','cpu_user','mem_used','numastats_interleave_hit_rate','numastats_local_node_rate','numastats_numa_foreign_rate','numastats_numa_hit_rate','numastats_numa_miss_rate','numastats_other_node_rate','disk_free','io_reads','io_writes','lustre_read_bw','lustre_write_bw','lustre_open_diff','lustre_close_diff','lustre_statfs_diff','net_bytes_in_bw','net_bytes_out_bw','net_pkts_in_bw','net_pkts_out_bw','ib_recv_bw','ib_xmit_bw','ib_recv_pkts_bw','ib_xmit_pkts_bw','nfs4_open','nfs4_close','nfsio_nread_bw','nfsio_nwrite_bw','nread','nwrite','nv_util','nv_fb_mem_used','nv_power_usage','nv_mem_util','nv_compute_processes','mem_bw','flops_any','clock','ipc','core_power','node_total_power','job_mem_used'])"
    ],
    "change_unit_prefix": {
      "name == 'mem_used'": "G",
      "name == 'nv_fb_mem_used'": "G",
      "name == 'lustre_read_bw'": "M",
      "name == 'lustre_write_bw'": "M",
      "name == 'ib_recv_bw'": "M",
      "name == 'ib_xmit_bw'": "M",
      "name == 'disk_free'": "G",
      "name == 'net_bytes_in_bw'": "M",
      "name == 'net_bytes_out_bw'": "M",
      "name == 'nfsio_nread_bw'": "M",
      "name == 'nfsio_nwrite_bw'": "M",
      "name == 'job_mem_used'": "G"
    }
  },
  "normalize_units": true
}
```

> **Warning (as of 16 Oct 2025):** `change_unit_prefix` and `drop_messages_if` currently operate on the original metric names, i.e., before `rename_messages` runs. This is not intended and will be fixed upstream. After the next update you must make sure both the unit adjustments and filters reference the renamed metrics.

### Explanation of the main processing stages

- **add_tags** – injects the cluster tag `elysium` so every message is properly attributed.
- **stage_order** – defines the processing order, which becomes important once you extend the pipeline.
- **hostname_tag** – reads the hostname from the `hostname` tag.
- **rename_messages** – maps the raw metrics to the names used by `cc-backend`. Most suffixes such as `_bw` and `_rate` are removed and GPU metrics are normalized to the `acc_*` prefix.
- **drop_messages_if** – filters unwanted partitions and exports and reduces the data stream to the metrics you want to keep.
- **change_unit_prefix** – normalizes the displayed units (bytes → GB or MB, …).
- **normalize_units** – makes sure units stay consistent after conversions.

Some metrics are ambiguous—for example `disk_free`, which reports every partition from every disk. `cc-backend` only keeps the first message per metric and node, the rest is discarded. You therefore have to filter the desired partition explicitly. The development team plans to allow multiple messages with the same name but different `stype` or tags per node so they can be shown side by side in the same chart. This is not supported yet.

In the example the `nfsio` metrics are kept only for the `/home` export; `/cluster` is dropped. Alternatively you could rename them in the `rename` stage, e.g., `cluster_nfsio_nread`. The same principle applies to other metrics—if you have multiple GPFS filesystems, rename and track them separately.

## Production use

Distribute the collector to the desired nodes and run it as a dedicated service, e.g., via a systemd unit:

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

Once the service is active the metrics are sent to the `cc-metric-store` every 60 seconds. You can add further collectors or renames at any time by extending the JSON files above.

