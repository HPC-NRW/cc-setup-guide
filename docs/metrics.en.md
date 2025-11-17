# Step-by-step: first metric

!!! info "Step-by-step · part 1/2"
    This is the first part of the two-step walkthrough that follows the [cc-metric-collector setup](cc_metric_collector_setup.md).  
    Continue with [Step-by-step: additional metrics](more_metrics.md) afterwards.

This chapter builds upon the `cc-metric-collector` setup.  
Adding a metric always involves three stages:

1. Collect the metric with `cc-metric-collector`.
2. Adjust `config.json` on the `cc-metric-store` so the values are stored.
3. Extend `cc-backend/var/job-archive/$CLUSTERNAME/cluster.json` so the metric shows up in the web UI.

You can find an overview of all collectors in the [upstream repository](https://github.com/ClusterCockpit/cc-metric-collector/blob/main/collectors/README.md).

We start with `cpu_load`, which is mandatory anyway.  
`cpu_load` is provided by the `loadavg` collector.  
Add it to `collectors.json`:

```json
{
  "loadavg" : {}
}
```

Run `./cc-metric-collector -config ./config_stdout.json -once` to inspect the output:

```bash
load_one,cluster=testcluster,hostname=cpu001,type=node value=0.27 1752156889208064633
load_five,cluster=testcluster,hostname=cpu001,type=node value=0.82 1752156889208064633
load_fifteen,cluster=testcluster,hostname=cpu001,type=node value=0.94 1752156889208064633
proc_run,cluster=testcluster,hostname=cpu001,type=node value=1i 1752156889208064633
proc_total,cluster=testcluster,hostname=cpu001,type=node value=1712i 1752156889208064633
```

Each line is a message in line protocol that would be sent to the metric store. The first column contains the metric name, cluster name, hostname, and the metric type (`node`, `socket`, `memoryDomain` (=NUMA domain), or `hwthread`). Other metrics also add the unit and an identifier if the granularity is finer than node level. The second column contains the value (the trailing `i` marks integers), and the third column is the Unix timestamp in nanoseconds.

The collector reports five values: the 1, 5, and 15 minute load averages, the number of running processes, and the total number of processes. We only need `load_one` for `cpu_load` and want to drop the other messages. That means we have to filter out the unwanted values and rename `load_one` to `cpu_load`.

This is handled by the `messageProcessor` in `cc-lib`, which is configured through `router.json`. Add a `process_messages` block:

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
  "normalize_units": true,
  "process_messages": {
    "hostname_tag": "hostname",
    "rename_messages": {
      "load_one": "cpu_load"
    },
    "drop_messages_if": [
      "!(name in [`load_one`])"
    ]
  }
}
```

The `drop_messages_if` list acts as a whitelist for all collectors.

Now only the desired metric remains:

```bash
cpu_load,cluster=testcluster,hostname=cpu001,type=node value=1.58 1752158115922836909
```

Important: when dropping metrics you must refer to their original name, not the renamed one!

Note: another `messageProcessor` feature we will use later is unit conversion. For example, if we collect memory consumption in bytes but want to display GB in the UI, we can write:

```json
{
  "process_messages": {
    "change_unit_prefix": {
      "name == 'mem_used'": "G"
    }
  }
}
```

`cpu_load` is now sent to the metric store. To persist the values we have to add an entry to `config.json` on the monitoring server:

```json
{
  "metrics": {
    "cpu_load": {
      "frequency": 60,
      "aggregation": "avg"
    }
  }
}
```

`frequency` specifies the expected interval in seconds. It should match the `interval` configured in the collector’s `config.json`.  
You can choose between three aggregation modes: `avg`, `sum`, and `nil`.  
Use `avg` for state or intensity metrics per entity (frequency, CPU/GPU utilization, temperature) and `sum` for additive metrics such as FLOPS or energy consumption.

---

Proceed with part 2: [Additional metrics & thresholds](more_metrics.md).

