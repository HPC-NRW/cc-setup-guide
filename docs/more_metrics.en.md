# Step-by-step: additional metrics

!!! info "Step-by-step · part 2/2"
    This chapter builds directly on [Step-by-step: first metric](metrics.md).  
    Work through part 1 first so that all base files and renames are in place.

This is the second part of the walkthrough and assumes the first metric (`cpu_load`) is already configured.  
Find the full list of collectors at https://github.com/ClusterCockpit/cc-metric-collector/tree/main/collectors

Each collector README documents its metrics and configuration options.  
Unless stated otherwise in a section, the `scope` is `node`.

> Note: In `cc-lib` versions up to and including `v0.10.1` the `drop_messages_if` and `change_unit_prefix` expressions had to use the *original* metric names. In the current release the renamed names (after `rename_messages`) apply. The examples below follow the new behavior.

## CPU

### loadavg (recap)

`loadavg` emits `load_one`, `load_five`, `load_fifteen`, `proc_run`, and `proc_total`. ClusterCockpit only needs `load_one`, which is renamed to `cpu_load`.

`collectors.json`:

```json
"loadavg": {}
```

`router.json` (excerpt):

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

The whitelist in `drop_messages_if` and the `rename_messages` dictionary will grow over the course of this chapter. All following `drop_messages_if` and `change_unit_prefix` blocks reference the same `process_messages` section inside this router.

### cpustat

`cpustat` reads `/proc/stat` and reports CPU times per hardware thread. For job monitoring we only keep `cpu_user`, which shows the user time per core (scope: `hwthread`). The measurement automatically covers every hardware thread.

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

Add `cpu_user` to the whitelist (see snippet above). The remaining columns such as `cpu_system` or `cpu_idle` are dropped.

### schedstat

`schedstat` emits `cpu_load_core`, the per-core utilization (`hwthread` scope) that uncovers incorrect pinning.

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

## Memory

### memstat

`memstat` collects several metrics from `/proc/meminfo`:

```
MemTotal:       32278500 kB
MemFree:         8472384 kB
MemAvailable:   19816380 kB
Buffers:            6656 kB
Cached:         12963688 kB
```

The derived metric is `mem_used` (= `mem_total` − (`mem_free` + `mem_buffers` + `mem_cached`)).

You can enable NUMA subcluster sampling (`scope: memoryDomain`), but `cc-backend` from the `main` branch cannot display those values yet.

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

`slurm_cgroup` reads the cgroups created by Slurm, derives the job-level memory consumption, and distributes it across the allocated cores. This yields the `job_mem_used` metric (scope `hwthread`) that is directly correlated to each job’s CPU cores.

`collectors.json`:

```json
"slurm_cgroup": {
  "scope": "hwthread"
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

`numastats` parses `/sys/devices/system/node/node*/numastat` and reports derived per-second counters (`count/s`) per NUMA domain (`scope: memoryDomain`). This makes it easy to spot interleave behavior or remote memory accesses.

`collectors.json`:

```json
"numastats": {
  "send_abs_values": false,
  "send_derived_values": true
}
```

`router.json` (excerpt):

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

## Local storage

Stateful nodes typically use two collectors:

### diskstat

Reads `/proc/self/mounts` and reports per-mount disk size (`disk_total`), free space (`disk_free`), and utilization (`part_max_used`). Mounts containing `loop` or `boot` are ignored. You can exclude additional mount points (e.g., `log`) in `collectors.json`:

```json
"diskstat": {
    "exclude_mounts": [
      "log"
    ]
}
```

Keep only `disk_free`.

Given the partition layout

```bash
/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=winnt,errors=remount-ro 0 0
/dev/nvme0n1p2 / xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,noquota 0 0
/dev/nvme0n1p3 /var/log xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
/dev/nvme0n1p4 /var/slurm-tmpfs xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
```

two messages are emitted:

```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p2,hostname=cpu001,type=node,unit=GB value=41u 1757426394108539349
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```

They only differ by the `device` tag. `cc-backend` does not aggregate the values; only the first message counts. Because this is the root filesystem (`/`) we cannot exclude it via `exclude_mounts`.  
Filter via the message processor:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free'])",

  "name == 'disk_free' && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'disk_free'": "G"
}
```

Result:

```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```

### iostat

Reads I/O statistics from `/proc/diskstats`. Only differences to the previous measurement are transmitted. Like `diskstat` we filter to the desired partition and only keep `io_reads` and `io_writes`.

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

## Network

### ibstat

`ibstat` captures link and traffic metrics for high-speed interconnects on Linux. It works with InfiniBand and Omni-Path since both expose their devices under `/sys/class/infiniband/<dev>/ports/<port>/...`.

By default it sends absolute counters. Switch to derived values so you get per-second bandwidth and packet rates.

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

Note: derived values need two measurements. They do not show up when `cc-metric-collector` runs with `-once`.

### netstat

`netstat` reports Ethernet metrics. To share a single configuration across heterogeneous nodes you can specify multiple names.

Enable derived values for direct bandwidth readings. The collector exposes:

* `net_bytes_in_bw` (bytes/s)
* `net_bytes_out_bw` (bytes/s)
* `net_pkts_in_bw` (packets/s)
* `net_pkts_out_bw` (packets/s)

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

The rename list ensures the resulting metrics are called `net_bytes_*` and `net_pkts_*`.

---

## Filesystems

### lustrestat

`lustrestat` uses `lctl` and produces Lustre client statistics. It exposes many counters; for most use cases you can focus on:

* `lustre_read_bw` (read bandwidth in bytes/sec)
* `lustre_write_bw` (write bandwidth in bytes/sec)
* `lustre_open` (open operations since the previous measurement)
* `lustre_close` (close operations since the previous measurement)
* `lustre_statfs` (differences in `statfs` calls)

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

### nfs4stat

`nfs4stat` wraps the `nfsstat` command and records NFSv4 client counters. The most relevant metrics are:

* `open_diff` (opens since the last measurement)
* `close_diff` (closes since the last measurement)

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

### nfsiostat

`nfsiostat` provides detailed stats for NFS mounts (similar to the CLI tool). Focus on the derived bandwidth values:

* `nfsio_nread` (bytes/s read)
* `nfsio_nwrite` (bytes/s written)

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

`nvidia` collects key GPU metrics such as utilization, memory usage, and power draw. Optional flags simplify MIG handling and suppress additional metadata so the data volume stays manageable.

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
  "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs', 'open_diff', 'close_diff', 'nfsio_nread', 'nfsio_nwrite', 'acc_utilization', 'acc_mem_used', 'acc_power', 'acc_mem_util'])",
  "(name in ['disk_free', 'io_reads', 'io_writes']) && tag.device != '/dev/nvme0n1p4'"
],
"change_unit_prefix": {
  "name == 'acc_mem_used'": "G"
}
```

<details>
<summary><strong>customcmd: integrate your own scripts</strong></summary>

When no dedicated collector exists you can use `customcmd` to run arbitrary scripts and reuse their output. That way you can integrate vendor-specific sensors or edge cases quickly. The script only needs to be executable and emit data in the desired format. The following example reads the node-wide power consumption via `ipmi-sensors` and outputs an InfluxDB line protocol metric called `node_total_power`:

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
<summary><strong>collectors.json built so far</strong></summary>

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
<summary><strong>router.json built so far</strong></summary>

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
          "!(name in ['cpu_load', 'cpu_user', 'cpu_load_core', 'mem_used', 'job_mem_used', 'numastats_interleave_hit', 'numastats_local_node', 'numastats_numa_foreign', 'numastats_numa_hit', 'numastats_numa_miss', 'numastats_other_node', 'disk_free', 'io_reads', 'io_writes', 'ib_recv', 'ib_xmit', 'ib_recv_pkts', 'ib_xmit_pkts', 'net_bytes_in', 'net_bytes_out', 'net_pkts_in', 'net_pkts_out', 'lustre_read_bw', 'lustre_write_bw', 'lustre_open', 'lustre_close', 'lustre_statfs', 'open_diff', 'close_diff', 'nfsio_nread', 'nfsio_nwrite', 'acc_utilization', 'acc_mem_used', 'acc_power', 'acc_mem_util'])",
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

Next up: [LIKWID metrics](likwid_metrics.md).
