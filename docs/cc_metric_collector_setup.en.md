# Install cc-metric-collector

`cc-metric-collector` is the data hub on the compute nodes.  
For easier handling you can install it on a shared filesystem such as `/cluster/monitoring/cc-metric-collector`.  
Make sure the LIKWID `bin` directory is part of `PATH` during build and runtime.

## Installation

```bash
git clone git@github.com:ClusterCockpit/cc-metric-collector.git
export PATH=/opt/likwid/bin:$PATH
make
```

The build directory contains a couple of files that control the behavior:

- `config.json`: Paths to other files, sampling interval.
- `collectors.json`: Which collectors run and how they are configured.
- `router.json`: Transformations (rename, filter, change units, …).
- `sinks.json`: Destinations (e.g., `cc-metric-store`).
- `receivers.json`: Optional forwarding of incoming data (keep empty for the base setup).

## Basic configuration

For quick tests you can temporarily set `interval` inside `config.json` to `10s`.  
Leave `receivers.json` empty (`{}`) and add a `stdout` output in `sinks.json`:

```json
{
  "mystdout": {
    "type": "stdout",
    "meta_as_tags": ["unit"]
  }
}
```

Save it as `sinks_stdout.json` and create `config_stdout.json`, which is identical to `config.json` except that it references `sinks_stdout.json`.  
Now you can run `./cc-metric-collector -config ./config_stdout.json [-once]` to inspect the metrics without sending anything to the `cc-metric-store`.

For production runs, point `sinks.json` to the metric store (replace the placeholders):

```json
{
  "cc-metric-store": {
    "type": "http",
    "url": "http://<monitoring-server>:8081/api/write/?cluster=__CLUSTER__",
    "jwt": "__APIKEY__",
    "precision": "s",
    "meta_as_tags": ["unit"],
    "idle_connection_timeout": "60s",
    "max_retries": 1,
    "timeout": "10s"
  }
}
```

Adjust `max_retries` and `timeout` to your needs.

Use a minimal `router.json` so that every sample carries the cluster name as tag:

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
  "normalize_units": true
}
```

Start with an empty `collectors.json` (`{}`) and fill it in the next step.

---

# Choose the metric set

Before configuring `cc-metric-collector` it pays off to take inventory: each collector can expose dozens of metrics. For most of them you can come up with a useful purpose, but ClusterCockpit is first and foremost **job monitoring**, not a full cluster monitoring replacement. Only ingest metrics that you will actually use.

During several roll-outs the most common answer to “Which metrics do you need?” was “The default” or “Whatever others collect”. This guide deliberately focuses on that default set because it addresses typical operations and troubleshooting scenarios. If you want to go beyond it, dive into the upstream repository and pick the collectors that match your requirements: [collectors/README.md](https://github.com/ClusterCockpit/cc-metric-collector/blob/main/collectors/README.md).

---

## Next steps

You can proceed in two different ways:

- **Step-by-step tutorial:** Start with [Set up the first metric](metrics.md) and then continue with [Additional metrics & thresholds](more_metrics.md). Great if you want to understand the collector/router/store concept in depth.
- **Quick setup:** Follow the [cc-metric-collector fast track](cc_metric_collector_quicksetup.md) for a compact workflow that uses ready-made examples.

