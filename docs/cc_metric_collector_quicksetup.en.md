# cc-metric-collector quick setup

This short route uses the complete minimal configuration and leads to the first node time series. It requires the [collector installation](cc_metric_collector_setup.md), a [matching cluster and node definition](cluster_minimal.md), and an [HTTPS endpoint](https_setup.md) reachable from the compute node, with an allowed API source address and valid JWT.

## Minimal start without hardware dependencies

The minimal profile collects only `loadavg`; it needs neither a LIKWID runtime library nor privileged hardware access. The main configuration and empty `receivers.json` are already supplied by the setup.

The following commands run as root on the compute node. `GUIDE_DIR`, `COLLECTOR_DIR`, and `TOKEN_FILE` must still point to the guide, collector directory, and protected token file from setup. The cluster name and HTTPS address need the installation's actual values.

```bash
install -m 0600 "$GUIDE_DIR/docs/examples/minimal/cc-metric-collector/router.json" "$COLLECTOR_DIR/router.json"
python3 "$GUIDE_DIR/docs/scripts/configure-collector.py" \
  --directory "$COLLECTOR_DIR" --cluster demo_cluster \
  --url 'https://monitoring.example.org/api/write/?cluster=demo_cluster' \
  --token-file "$TOKEN_FILE"
cd "$COLLECTOR_DIR"
./cc-metric-collector -config ./config_stdout.json -once
./cc-metric-collector -config ./config.json -once
```

The optional [configure-collector.py](scripts/configure-collector.py) belongs to this guide rather than the official collector. Alternatively, the files can be edited directly as described in [collector setup](cc_metric_collector_setup.md): the cluster value in the `add_tags` entry of `router.json`, plus the URL and raw JWT in the HTTP sink in `sinks.json`.

The stdout output must contain `cpu_load` with the expected cluster and hostname. The second call sends one measurement to the backend; transmission errors appear in the collector log. The existing `cpu_load` entry in `cluster.json` must match. A successful `-once` call checks one measurement and does not provide continuous collection.

## Production use

The next step is [running the collector as a service](collector_service.md), which contains the shared systemd unit, activation commands, and checks across several intervals. The [node view](metrics.md#expected-result-in-the-web-interface) then shows whether the time series arrives for the intended node. [Metric reception and display](metric_receive_display.md) covers missing data.

After this check come [Slurm integration](slurm_setup.md) and a [test job](first_job.md), completing the minimal route from measurements to job monitoring.

## Optional extensions

The [RUB example profile](example_profiles.md) contains a complete Zen4 configuration with `collectors.json`, router rules, device filters, and a collector overview. These settings are site-specific and require matching devices, filesystems, and access permissions. The complete profile also uses only [units from the official schema](units.md#strict-schema-validation) and passes schema validation without exceptions.

<span id="collectorsjson-example-for-amd-zen-4"></span>
<span id="collector-overview-by-category"></span>
<span id="cpu-load"></span>
<span id="memory-numa"></span>
<span id="storage-local-lustre-nfs"></span>
<span id="network"></span>
<span id="node-power"></span>
<span id="gpu-optional"></span>

<span id="routerjson"></span>
<span id="explanation-of-the-main-processing-stages"></span>

[Additional metrics](more_metrics.md) explains the individual extensions for CPU, memory, storage, networking, filesystems, and GPUs. [LIKWID metrics](likwid_metrics.md) covers hardware events.
