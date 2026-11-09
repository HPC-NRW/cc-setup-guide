# Example profiles and configuration files

The [minimal profile](cc_metric_collector_quicksetup.md) establishes the first working data path. The RUB profile documented here shows a more extensive configuration from the Elysium cluster. The metric selection has been adapted to the official unit schema for this guide. Its hardware choices and operating assumptions are examples, not requirements for a ClusterCockpit installation.

!!! info "Units from the upstream schema"
    This profile uses only units from the unchanged official schema. Load values are dimensionless, clock frequencies use MHz (`Hz` with prefix `M`), and FLOP rates use GFLOP/s (`F/s` with prefix `G`). Optional percentage and counter metrics without a matching schema unit are excluded from this example. [Units and validation](units.md) explains this selection.

The following sections explain the metric selection, site-specific changes, and routing. Complete backend and collector files follow under [Example configurations](#example-configurations). [The collector as a service](collector_service.md) covers continuous operation.

## collectors.json (example for AMD Zen 4)

The [collectors.json](examples/rub/cc-metric-collector/collectors.json) is based on the configuration of an AMD Zen4 CPU node in Ruhr University Bochum’s Elysium cluster. It uses official collector options and the unit and routing rules in this guide. LIKWID event sets, network interfaces, and device filters are specific to that site and must match the target hardware.

<details>
<summary>Collector configuration</summary>

```json
--8<-- "examples/rub/cc-metric-collector/collectors.json"
```

</details>

## Collector overview by category

The tables show names after routing, as used in `cluster.json`. The optional GPU collector `nvidia` is not enabled in the CPU example.


### CPU & Load

| Collector     | Metric                                    | Scope    | Description                          |
| ------------- | ----------------------------------------- | -------- | ------------------------------------ |
| **loadavg**   | `cpu_load`                                | node     | 1-minute load                        |
| **schedstat** | `cpu_load_core`                           | hwthread | Utilization per hardware thread      |
| **likwid**    | `clock`, `ipc`, `flops_any`, `core_power` | hwthread | CPU performance counters             |


### Memory & NUMA

| Collector        | Metric             | Scope               | Description                              |
| ---------------- | ------------------ | ------------------- | ---------------------------------------- |
| **memstat**      | `mem_used`         | node / memoryDomain | RAM usage per node and NUMA domain       |
| **slurm_cgroup** | `job_mem_used`     | hwthread            | Job-specific memory consumption          |
| **likwid**       | `mem_bw`           | socket              | Memory bandwidth per socket              |


### Storage (local, Lustre, NFS)

| Collector      | Metric                           | Scope | Description                                 |
| -------------- | -------------------------------- | ----- | ------------------------------------------- |
| **diskstat**   | `disk_free`                      | node  | Free local disk space                       |
| **lustrestat** | `lustre_read_bw`, `lustre_write_bw` | node | Lustre read and write bandwidth |
| **nfsiostat**  | `nfsio_nread`, `nfsio_nwrite`    | node  | NFS I/O bandwidth for the selected export   |

[Units and validation](units.md) explains the units. `main.interval` and the corresponding `timestep` values in `cluster.json` must agree.


### Network

| Collector   | Metric                               | Scope | Description            |
| ----------- | ------------------------------------ | ----- | ---------------------- |
| **netstat** | `net_bytes_in`, `net_bytes_out` | node | Ethernet bandwidth |
| **ibstat**  | `ib_recv`, `ib_xmit` | node | InfiniBand bandwidth |

### Node power

| Source | Metric | Scope | Description |
|---|---|---|---|
| External site-specific power source, optional | `node_total_power` | node | Total node power consumption in Watts |

The CPU example enables no source for `node_total_power`. This metric needs a separate power source through a supported interface. [Additional metrics](more_metrics.md) includes an example with the official `customcmd` collector. Without such a source, `node_total_power` can be omitted from `cluster.json`.


### GPU (optional)

| Collector  | Metric                                         | Scope       | Description                          |
| ---------- | ---------------------------------------------- | ----------- | ------------------------------------ |
| **nvidia** | `acc_mem_used`, `acc_power` | accelerator | GPU memory usage and power |


The following settings depend on the site:

- `use_sudo` can be `true` only when the collector does not run as `root`.
- `netstat` needs the local Ethernet interface name.
- The `diskstat` filter must select the intended partition.
- The `lctl` path for `lustrestat` must match the installation.
- For `likwid`, `accessdaemon_path`, `liblikwid_path`, and `lockfile_path` must match the LIKWID installation. Event sets depend on the CPU architecture; [LIKWID metrics](likwid_metrics.md) covers their setup.

## router.json

The complete file appears [below](#cc-metric-collectorrouterjson).

### Explanation of the main processing stages

- **add_tags** sets the cluster name `elysium` to identify each message.
- **stage_order** defines the processing order. New stages must run at the appropriate point.
- **hostname_tag** reads the hostname from the `hostname` tag.
- **rename_messages** maps raw metrics to the names for `cc-backend`. The `_bw` suffix is removed from several bandwidth metrics, and GPU metrics receive the general `acc` prefix.
- **drop_messages_if** removes unwanted partitions, exports, and metrics. Renaming runs first, so filters use the target names.
- **add_meta_if** corrects the Linux label `kB` specifically for `mem_used` to `KiB` before memory values are scaled.
- **change_unit_prefix** scales units for display, for example bytes to GB or MB. These rules also use the target names.
- **normalize_units** makes unit spelling consistent after conversion.

Device filters depend on the hostname: `startsWith` selects a node group, then the comparison with `tag.device` selects the partition. The `cpu` prefix allows only `nvme0n1p4` here. For `disk_free`, the same device name can begin with `/dev/`. Hostnames and devices are site-specific. The router filters must allow the intended partition.

Some collectors emit several values with the same metric name per node, such as `disk_free` for multiple partitions. In this configuration, `cc-backend` processes only the first message and discards the rest. A filter therefore selects the intended source. Different `stype` values or other tags do not produce separate curves for messages with the same name and node.

The example retains `nfsio` only for the `/home` export and drops `/cluster`. Separate target names from the rename stage, such as `cluster_nfsio_nread`, provide an alternative. The same approach works for other metrics, for example multiple GPFS filesystems collected separately.


## Example configurations

The following files form the backend, UI, cluster, and collector profile. They contain no credentials or keys. Paths, hardware, names, and authentication must match the target site.

The [installation chapter](monitoringserver.md) describes the standard setup. The [unit overview](units.md) explains the adopted metrics. The cluster definition is checked against the unchanged official schema, without exceptions for individual units.

### `cc-backend/config.json`

`main.api-allowed-ips` contains the placeholder `__API_CLIENT_IP__`.
Before startup, the placeholder must be replaced with the permitted API client IP
addresses (one entry per IPv4 or IPv6 address; no CIDR networks).

[Open backend configuration](examples/rub/cc-backend/config.json)

<details>
<summary>Show backend configuration</summary>

```json
--8<-- "examples/rub/cc-backend/config.json"
```

</details>

### `job-archive/cluster.json`

[Open cluster definition](examples/rub/job-archive/cluster.json)

<details>
<summary>Show cluster definition</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

### `cc-backend/ui-config.json`

[Open UI configuration](examples/rub/cc-backend/ui-config.json)

<details>
<summary>Show UI configuration</summary>

```json
--8<-- "examples/rub/cc-backend/ui-config.json"
```

</details>

### `cc-metric-collector/config.json`

[Open collector main configuration](examples/rub/cc-metric-collector/config.json)

<details>
<summary>Show collector main configuration</summary>

```json
--8<-- "examples/rub/cc-metric-collector/config.json"
```

</details>

### `cc-metric-collector/router.json`

[Open router configuration](examples/rub/cc-metric-collector/router.json)

<details>
<summary>Show router configuration</summary>

```json
--8<-- "examples/rub/cc-metric-collector/router.json"
```

</details>

### `cc-metric-collector/receivers.json`

This setup enables no collector receivers; the file contains `{}`.

[Open receiver configuration](examples/rub/cc-metric-collector/receivers.json)

<details>
<summary>Show receiver configuration</summary>

```json
--8<-- "examples/rub/cc-metric-collector/receivers.json"
```

</details>

### `cc-metric-collector/sinks.json`

[Open sink configuration](examples/rub/cc-metric-collector/sinks.json)

<details>
<summary>Show sink configuration</summary>

```json
--8<-- "examples/rub/cc-metric-collector/sinks.json"
```

</details>
