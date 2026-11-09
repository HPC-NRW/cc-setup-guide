<a id="step-by-step-additional-metrics"></a>

# Choosing additional metrics

!!! info "Optional extensions"
    These recipes build on a working [first metric](metrics.md). Each extends the setup for a particular need. The useful collectors depend on the hardware, filesystems, and questions the job monitoring should answer.

| Area | Collectors | Requirements and scope |
|---|---|---|
| [CPU](#cpu) | `loadavg`, `schedstat` | Linux process and CPU statistics; `node` or `hwthread` |
| [Memory](#memory) | `memstat`, `slurm_cgroup` | Matching NUMA topology; readable Slurm cgroups for job values; `node`, `memoryDomain`, or `hwthread` |
| [Local storage](#local-storage) | `diskstat` | Matching mount and device filters; `node` |
| [Network](#network) | `ibstat`, `netstat` | Available interfaces; at least two measurements for rates; `node` |
| [Filesystems](#filesystems) | `lustrestat`, `nfsiostat` | The relevant filesystem and its tools; `node` |
| [GPU](#gpu) | `nvidia` | NVIDIA GPUs and access to their measurements; `accelerator` |

The [official collector overview](https://github.com/ClusterCockpit/cc-metric-collector/tree/v0.8.4/collectors) describes further measurements and options. Unless a recipe states otherwise, its scope is `node`. Hardware-counter collection is covered under [LIKWID metrics](likwid_metrics.md).

## Adding a recipe to the existing configuration

Each extension involves the collector, routing, and its entry in `cluster.json`. The [path of a measurement](metric_flow.md) shows the files involved. The [backend configuration](metric_receive_display.md#minimal-entry) explains names, scope, units, aggregation, and interval.

The excerpts show an example configuration growing one step at a time. Individual recipes can be selected independently; their cumulative allowlists sometimes include names from earlier recipes. The local allowlist must contain all deliberately enabled target metrics, including `cpu_load`.

- The existing `stage_order` stays in place: rename, filter, add metadata, then scale units.
- New `rename_messages` and `change_unit_prefix` entries extend the existing entries. Existing `add_meta_if` rules also remain in place.
- A complete `drop_messages_if` block replaces the previous list. Required device and export filters must remain present.
- Filters and conversions use the names after routing. The backend entry must match that name and scope exactly.

After each extension, the unrounded stdout output, matching cluster and host names, and the corresponding node time series provide checks. Derived values need a run over several collection intervals. The [end of this page](#checking-the-configuration) covers verification and the transition to continuous operation.

<a id="cpustat"></a>
<a id="numastats"></a>
<a id="iostat"></a>
<a id="nfs4stat"></a>

These recipes use units supported by the unchanged upstream schema. Percentage values, packet rates, and operation counters are therefore excluded from the backend profile. This affects `cpustat`, `numastats`, `iostat`, and `nfs4stat`, as well as individual network, Lustre, and GPU measurements. [Units and validation](units.md) explains this selection.

## CPU

### loadavg (recap)

`loadavg` emits `load_one`, `load_five`, `load_fifteen`, `proc_run`, and `proc_total`. The example still uses only `load_one`, renamed to `cpu_load`.

`collectors.json`:

```json
"loadavg": {}
```

`router.json` (excerpt):

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

The following excerpts extend the allowlist and renames in the same `router.json`. All `drop_messages_if` and `change_unit_prefix` blocks belong to its `process_messages` section.


### schedstat

`schedstat` reports dimensionless utilisation per hardware thread as `cpu_load_core` (`scope: hwthread`). Differences between threads can indicate unsuitable pinning.

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

## Memory

### memstat

`memstat` reads values from `/proc/meminfo`, including:

```
MemTotal:       32278500 kB
MemFree:         8472384 kB
MemAvailable:   19816380 kB
Buffers:            6656 kB
Cached:         12963688 kB
```

The example uses `mem_used`, calculated as `mem_total − (mem_free + mem_buffers + mem_cached)`.

NUMA values need `scope: memoryDomain` and a matching topology in `cluster.json`. The RUB example stores `mem_used` at this level. The additional node metric cannot be stored under the same name as a second memory dimension.

`collectors.json`:

```json
"memstat": {
  "node_stats": true,
  "numa_stats": true
}
```

Collector 0.8.4 preserves the Linux label `kB`, although `/proc/meminfo` uses it to mean KiB. The following rule corrects only the label of `mem_used` to `KiB` before scaling to GB. Thus 1,048,576 source units become 1.073741824 GB. Existing `add_meta_if` rules remain in place, and `add_meta` must run before `change_unit_prefix`. [Units and validation](units.md) explains the distinction.

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

Collector v0.8.4 fixes the scope to `hwthread`; an extra `scope` configuration field is invalid. Readable Slurm cgroups and a `cgroup_base` matching the local layout are required. The first check runs without `use_sudo`, using narrowly assigned read permissions rather than unrestricted sudo.

`slurm_cgroup` reads memory usage from a job’s Slurm cgroups and distributes the value across its allocated cores. The resulting `job_mem_used` metric appears per hardware thread and maps to the job’s CPU cores.

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


## Local storage

`diskstat` measures the free space on one selected local partition.

### diskstat

`diskstat` reads `/proc/self/mounts` and reports each mount’s size (`disk_total`), free space (`disk_free`), and utilisation (`part_max_used`). It ignores mounts with `loop` or `boot` in their names. Further exclusions belong in `collectors.json`, here for example `log`:

```json
"diskstat": {
  "exclude_mounts": [
    "log"
  ]
}
```

The example retains only `disk_free`.

With the following partition layout,

```bash
/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=ascii,shortname=winnt,errors=remount-ro 0 0
/dev/nvme0n1p2 / xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,noquota 0 0
/dev/nvme0n1p3 /var/log xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
/dev/nvme0n1p4 /var/slurm-tmpfs xfs rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,sunit=256,swidth=256,usrquota,prjquota,grpquota 0 0
```

two messages remain:

```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p2,hostname=cpu001,type=node,unit=GB value=41u 1757426394108539349
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```

The messages differ only in the `device` tag. In this configuration, `cc-backend` processes the first message for the metric; it does not add the values together. The root filesystem `/` cannot be excluded through `exclude_mounts` here.
The message processor limits the output to the selected device:

```json
"drop_messages_if": [
  "!(name in ['cpu_load', 'cpu_load_core', 'mem_used', 'job_mem_used', 'disk_free'])",
  "name == 'disk_free' && !(tag.device in ['/dev/nvme0n1p4', 'nvme0n1p4'])"
],
"change_unit_prefix": {
  "name == 'disk_free'": "G"
}
```

Only the selected partition remains:

```bash
disk_free,cluster=testcluster,device=/dev/nvme0n1p4,hostname=cpu001,type=node,unit=GB value=869u 1757426394108546859
```


## Network

### ibstat

`ibstat` collects link and traffic metrics for InfiniBand and Omni-Path. Both expose their devices under Linux through `/sys/class/infiniband/<dev>/ports/<port>/...`.

The collector sends absolute counters by default. The example disables these values and enables derived rates. The router retains only bandwidth in bytes per second.

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

Derived values require at least two measurements. They therefore do not appear when the collector starts with `-once`.

### netstat

`netstat` collects Ethernet interface metrics. Multiple configured interface names allow one configuration to cover different node groups.

The example retains `net_bytes_in_bw` and `net_bytes_out_bw`, both in bytes/s. The router drops packet rates.

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

The `rename_messages` entries give these bandwidths the target names `net_bytes_in` and `net_bytes_out`.

---

## Filesystems

### lustrestat

`lustrestat` reads Lustre client statistics through `lctl`. The example retains `lustre_read_bw` and `lustre_write_bw`, the read and write bandwidths in bytes/s. Operation counters remain excluded.

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


### nfsiostat

`nfsiostat` provides statistics for NFS mounts. The example retains the derived read and write bandwidths `nfsio_nread` and `nfsio_nwrite` in bytes/s.

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

`nvidia` collects GPU measurements. The example retains memory usage and power; percentage values and process counts are dropped. The example’s optional flags simplify MIG devices and suppress extra metadata to limit data volume.

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
<summary><strong>customcmd: external scripts</strong></summary>

`customcmd` turns an executable script’s output into a metric. The example reads total node power with `ipmi-sensors` and emits it as `node_total_power` in InfluxDB Line Protocol.

The published CPU profile does not enable this optional collector. A local setup needs matching sensors, permissions, and a cluster name. The script must also be configured through `customcmd`, and `node_total_power` must be present in both the router allowlist and `cluster.json`.

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
<summary><strong>Complete collectors.json for this example</strong></summary>

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
<summary><strong>Complete router.json for this example</strong></summary>

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

## Checking the configuration

After the complete router has been copied, the site identity must be set again. The cluster, HTTPS destination, and protected token file remain the same as in setup. `__CLUSTER__` is a placeholder and must not remain. The single stdout run checks `cpu_load`, the cluster, and the hostname. Derived metrics are not yet expected from this invocation.

Helper script: [open or download configure-collector.py](scripts/configure-collector.py).

```bash
python3 "$GUIDE_DIR/docs/scripts/configure-collector.py" \
  --directory "$COLLECTOR_DIR" --cluster demo_cluster \
  --url 'https://monitoring.example.org/api/write/?cluster=demo_cluster' \
  --token-file "$TOKEN_FILE"
cd "$COLLECTOR_DIR"
./cc-metric-collector -config ./config_stdout.json -once
```

Further hardware-dependent extensions are covered under [LIKWID metrics](likwid_metrics.md). The [RUB example configuration](example_profiles.md) shows a complete site profile.


For derived metrics, the collector then runs over several collection intervals:

```bash
./cc-metric-collector -config ./config_stdout.json
```

`Ctrl+C` ends the run. The output must now also contain the deliberately enabled metrics with matching names, units, and hardware IDs. [Units and validation](units.md) helps identify duplicate conversions and incorrect scopes. Once the metrics are registered in the backend and [ingestion is verified](metric_receive_display.md), the collector can run as a [system service](collector_service.md).
