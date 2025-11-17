# Receive and display metrics

The collector configured in [Set up cc-metric-collector](cc_metric_collector_setup.md) already sends values, but `cc-metric-store` and `cc-backend` only accept them if the metrics are explicitly configured.  
This section shows how to register new or changed metrics on the monitoring server so that

1. `cc-metric-store` ingests the data, and
2. the web interface (`cc-backend`) discovers the metrics through entries in `cluster.json`.

> **TL;DR:** Every new metric requires exactly two entries: one in `cc-metric-store/config.json` and one in `cluster.json`. Only then will it appear in the monitoring stack.

---

## 1. Extend `cc-metric-store/config.json`

Default path (following this guide):  
`$INSTALL_DIR/cc-metric-store/config.json`

Add an entry in the `metrics` section for every new metric:

```json
"cpu_load": {
  "frequency": 60,
  "aggregation": "avg"
}
```

**Fields**

- `frequency`: Expected interval in seconds. Must match the `interval` from the collector’s `config.json` (60 s by default in this guide).
- `aggregation`: Defines how values are merged across the hierarchy (`hwthreads` → `socket` → `node`). Use `avg` for state metrics (load, temperature), `sum` for counting metrics (FLOPS, energy, bandwidth), and `nil` to disable aggregation.

Restart `cc-metric-store` afterwards:

```bash
systemctl restart cc-metric-store.service
```

---

## 2. Update `cc-backend/cluster.json`

Path:  
`$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/cluster.json`

`cluster.json` describes both subclusters and the metrics shown in the web UI. Every metric is represented by an object inside the `metricConfig` array.

### Minimal entry

```json
{
  "name": "cpu_load",
  "unit": { "base": "" },
  "scope": "node",
  "aggregation": "avg",
  "timestep": 60,
  "peak": 48,
  "normal": 48,
  "caution": 10,
  "alert": 1
}
```

**Key fields**

- `name`: Must exactly match the name published after routing (e.g., after `rename_messages`).
- `unit`: Base unit (optional `prefix`: `"M"`, `"G"`, ...). Keep it consistent with the units defined in `router.json`.
- `scope`: Granularity (`node`, `socket`, `hwthread`, `memoryDomain`, `accelerator`).
- `aggregation`: Typically `avg` for state metrics and `sum` for cumulative ones.
- `timestep`: Display interval (seconds); should match the store’s `frequency`.
- `peak`, `normal`, `caution`, `alert`: Thresholds for the UI. Graphs between `normal` and `caution` remain neutral. Values between `caution` and `alert` are highlighted yellow (= keep an eye on it) and values below `alert` red (= immediate action).

### Configuration options

#### Invert the alert logic

Set `"lowerIsBetter": true` if alerts should trigger on *higher* values rather than lower ones. Useful for metrics like `cpu_load_core`, network bandwidth, or IOPS.

#### Show a metric only for specific subclusters

If you want to display GPU metrics only on GPU nodes, remove the metric from the other subclusters:

```json
            "name": "nv_compute_processes",
            "unit": {
                "base": "processes"
            },
            "scope": "accelerator",
            "aggregation": "sum",
            "timestep": 60,
            "peak": 100, 
            "normal": 50,
            "caution": 80,
            "alert": 90,
            "subClusters": [
                {
                    "name": "cpu",
                    "remove": true 
                },
                ...
            ]
        },
```

**Note:** Removed metrics disappear from the job view and cannot be selected. In the admin node view you will see blue placeholders indicating that the metric is disabled for that subcluster:

![Disabled metric indicator](img/removed_metric.png)

#### Different thresholds per subcluster

If subclusters differ in CPUs, memory, or GPU memory, you can override the thresholds per subcluster. All clusters not listed inherit the defaults from the main object:

```json
        {
            "name": "cpu_load",
            ...
            "subClusters": [
                {
                    "name": "fatcpu",
                    "peak": 96,
                    "normal": 96,
                    "caution": 10,
                    "alert": 1
                },
                ...
            ]
        },
```

#### Define footprint metrics

Add `"footprint": "avg"` (or `sum`, depending on the aggregation) to include the metric in the footprint view and polar plot.

Footprint example:

![Footprint example](img/footprint.png)

Polar plot example:

![Polar plot example](img/polar.png)

Metrics flagged with `"lowerIsBetter": true` show an arrow pointing left. In this example only metrics with `hwthread` scope are used because they are the most meaningful on shared nodes.

