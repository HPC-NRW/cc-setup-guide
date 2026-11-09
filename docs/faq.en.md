# FAQ

## cc-backend: navigation bar missing

A missing navigation bar can indicate an incomplete or malformed `cluster.json`. Invalid entries in `config.json` are another possible cause. Both JSON files need valid syntax, for example checked with `jq`, and values that match the installation. After comparison with working examples and a web-service reload, the interface should load correctly. The [first-login check](webinterface.md) covers paths and the cluster name.

## No new jobs or metrics

Job data and measurements reach the backend through different paths. The first check depends on what is missing:

| Observation | First check | Further detail |
| --- | --- | --- |
| Node metrics are visible, jobs are missing | Slurm adapter service, accounting access, and job submission | [Connect Slurm](slurm_setup.md) |
| Jobs are visible, measurements are missing | Collector output, write API, metric names, and resource identities | [Receive and display metrics](metric_receive_display.md) |
| Neither jobs nor measurements arrive | Backend reachability, HTTPS, API access rules, and both clients' tokens | [HTTPS and API access](https_setup.md) |
| A job has ended but is not archived yet | Next poll, accounting end data, and backend monitoring status | [Check the first job](first_job.md) |

The relevant service journals provide further evidence. Messages such as `Can't decode jwt` point towards the API token. An expired JWT is one possible cause; the selected token and backend must also match. Expiry requires a replacement token in every affected component. [Token rotation](operation.md#api-access-and-token-rotation) explains the associated limits.

## Slurm 23.11: job start fails on `exclusive`

The checked unchanged `cc-slurm-sync` sends `exclusive` when starting a job; backend 1.5.4 rejects this field with HTTP 400. This guide provides no setup path for that combination without a product code change. The [compatibility limit](slurm_sync.md) explains the finding and links to the official adapter path for Slurm 24.05 and newer.

## Metric collector does not send metrics

The relevant collector must first be enabled in `collectors.json`. The next check is whether `router.json` renames or filters out the metric. `diff` and `derived` metrics need multiple measurements; a run with `-once` is insufficient.

A small test configuration makes the path easier to inspect: `config_stdout.json` references `router_stdout.json` and `sinks_stdout.json`. The sink writes to `stdout` instead of HTTP. `./cc-metric-collector -config config_stdout.json` then prints measurements in the terminal. Only the necessary router rules belong in this test. [The first metric](metrics.md) demonstrates this workflow.

## Downloads start while scrolling

Unexpected downloads of job or node views while scrolling can result from script or content blockers interfering with the interface. An exception for ClusterCockpit, for example in NoScript, allows the required scripts to load.

## Metrics show the wrong scale

Repeated conversion can distort values, for example `0.0031 MB/s` instead of `3.1 MB/s`. The router's `change_unit_prefix` must match `unit` plus `prefix` in `cluster.json`. Checks start with the unrounded collector value and follow its unit and prefix through to the display. [Units and validation](units.md) covers examples and special cases.
