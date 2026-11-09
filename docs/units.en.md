# Units and validation

`cluster.json` describes a measurement’s meaning and display. Its unit label does not change the incoming number. Conversion happens earlier in the collector or router, and the backend configuration must agree with it.

## Scaling numeric values

For example, `change_unit_prefix` scales a correctly labelled byte value to GB. The following router fragment gives `mem_used` the prefix `G` while preserving the existing `stage_order`:

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

The fragment extends the existing `process_messages` section without removing its other rules. It assumes a correct source unit. Linux memory values need the `kB` correction described below before scaling.

Byte → GB divides by 10⁹, and Byte/s → MB/s divides by 10⁶. `mem_bw` is expressed in GB/s. Watts remain Watts, and IPC means instructions/cycle. A value that has already been scaled must not be converted a second time.

## Units in the RUB profile

The [RUB example profile](examples/rub/job-archive/cluster.json) uses only units from the unmodified upstream schema. Values are already scaled by the collector or router; `base` and `prefix` describe their display in the backend.

| Metrics | `base` / `prefix` | Meaning of an example value |
|---|---|---|
| `cpu_load`, `cpu_load_core` | `""` | 1.5 remains 1.5; dimensionless load or run-time ratio, not percent |
| `clock` | `Hz` / `M` | 2000 means 2000 MHz |
| `flops_any`, `flops_sp`, `flops_dp`, `flops_bf16` | `F/s` / `G` | 64 means 64 GFLOP/s |
| `mem_used`, `job_mem_used`, `acc_mem_used`, `disk_free` | `B` / `G` | 1 means 1 GB |
| `mem_bw` | `B/s` / `G` | 2 means 2 GB/s |
| Network, InfiniBand, Lustre, and NFS bandwidth | `B/s` / `M` | 10 means 10 MB/s |
| `ipc` | `IPC` | 1.5 means 1.5 instructions/cycle |
| `core_power`, `acc_power`, `node_total_power` | `W` | 200 means 200 Watts |

MHz is therefore represented as `{"base": "Hz", "prefix": "M"}`. Multiplying the numeric value by a million as well would be incorrect. The same principle applies to values already expressed in GFLOP/s, GB, or MB/s.

## Counter differences and rates

A counter difference and a rate per second are different measurements. An increase of 60 operations over 60 seconds gives 60 operations per interval or, after division by time, 1 operation/s. Changing a label does not perform this conversion.

The published profile excludes metrics with percent, packet, process, or operation labels that the upstream schema cannot represent. This also covers NUMA event rates. The router drops the corresponding messages, leaving 24 metrics with supported units available in the backend. Which metrics receive data depends on the enabled collectors and hardware.

## Linux memory values: kB and KiB

`/proc/meminfo` and NUMA meminfo use the label `kB` for 1024-byte units. The [kernel shifts page counts by PAGE_SHIFT−10](https://github.com/torvalds/linux/blob/v6.12/fs/proc/meminfo.c#L26-L30) to produce these values. The [memstat collector](https://github.com/ClusterCockpit/cc-metric-collector/blob/v0.8.4/collectors/memstatMetric.go) forwards the label unchanged.

The [example router](more_metrics.md#memstat) therefore corrects only `mem_used` with `meta.unit == 'kB'`: `add_meta_if` sets the unit to `KiB` before `change_unit_prefix` scales the value. Thus 1,048,576 source units become 1.073741824 GB. Treating them as SI kB would incorrectly produce 1.048576 GB.

Other byte sources retain their own metadata. The correction applies specifically to this Linux memory value; it must not rewrite every `kB` label.

## Rounding in archives, APIs, and checkpoints

The [series serializer](https://github.com/ClusterCockpit/cc-lib/blob/v2.12.0/schema/float.go#L116-L145) writes values with two decimal places. After JSON archival or API serialisation, 1.073741824 GB therefore appears as 1.07 GB. Checking a router conversion also requires the unrounded collector output for comparison.

JSON checkpoints independently round to one decimal place. This distinction matters especially for small values and restart checks.

## Strict schema validation

Both the minimal and RUB profiles satisfy the unmodified [unit schema](https://github.com/ClusterCockpit/cc-lib/blob/v2.12.0/schema/schemas/unit.schema.json) without exceptions. The guide checks validate the complete cluster files and test startup with both documented backend versions.

An additional metric needs a supported unit, matching numeric values, and an entry in `metricConfig`. It can then be added to the router's allowlist. Replacing an unknown percent or rate base with an empty unit would obscure the meaning of the display. Such measurements need an appropriate representation in the upstream version in use before they can become part of this profile.

Schema validation detects invalid configuration values. Comparing against a known measurement additionally checks whether the numeric scaling is correct.

The global runtime switch `main.validate` also validates job archives. In backend 1.5.3 and 1.5.4, this check can reject metadata written by the backend itself: the [archive schema](https://github.com/ClusterCockpit/cc-lib/blob/v2.12.0/schema/schemas/job-meta.schema.json) requires specific statistic metrics and rejects some emitted `null` fields. The [backend example configuration](examples/rub/cc-backend/config.json) therefore leaves this switch unset, retaining the upstream default. Cluster configuration is validated separately; no schemas are modified and no exceptions are allowed.

## Check sample identity

For `hwthread`, `socket`, and `memoryDomain`, time-series IDs must match the topology and job resources. A useful check applies distinct known values to several hardware entities and temporarily leaves one series missing. The comparison covers IDs and values before and after archival. Missing measurements remain missing rather than being replaced with invented zeroes.
