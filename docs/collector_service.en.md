# Running the collector as a service

The quick setup and detailed metric walkthrough finish with the same service. It collects continuously and, with the default profile, sends measurements to `cc-backend` every 60 seconds.

## Prerequisites

Before startup, the single stdout check must show `cpu_load` with the intended cluster and hostname. The subsequent HTTP check must complete without transmission errors. The [backend definition](metrics.md#backend-definition), HTTPS endpoint, allowed API source address, and JWT must agree.

This example installs a system-wide systemd service on each intended compute node. A shared collector directory distributes the files but does not automatically start a service on individual nodes.

## systemd unit

The supplied unit uses `/cluster/monitoring/cc-metric-collector`. A different destination requires corresponding changes to both `WorkingDirectory` and `ExecStart`.

```ini
--8<-- "examples/minimal/cc-metric-collector/cc-metric-collector.service"
```

The unit does not need an additional environment file. `PATH` and the library path contain complete values; systemd does not expand `$PATH` there. A different LIKWID installation requires matching paths. The plain `loadavg` profile needs no LIKWID runtime library.

Site-specific Lustre/lnet dependencies may need their own `After` and `Requires` entries; they are not prerequisites for the minimal profile. A custom service account needs deliberate access to enabled sensors and protected configuration files. The example unit runs as root.

## Service activation and checks

The following commands run as root from the guide checkout's root directory on the compute node. If paths have been customized, the edited unit must be installed instead of the unchanged example file.

```bash
GUIDE_DIR="$(pwd -P)"
install -m 0644 "$GUIDE_DIR/docs/examples/minimal/cc-metric-collector/cc-metric-collector.service" /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/cc-metric-collector.service
systemctl daemon-reload
systemctl enable --now cc-metric-collector.service
systemctl status cc-metric-collector.service --no-pager
journalctl -u cc-metric-collector.service -n 50 --no-pager
```

The status must show a running service. The journal should contain no recurring authentication, connection, or configuration errors. After several intervals, the [node view](metrics.md#expected-result-in-the-web-interface) should show a time series for the expected node.

`-once` remains useful for individual identity and transmission checks. Difference and derived metrics require several measurements; their absence from the first sample does not by itself indicate a problem. Those checks require collection across multiple intervals.

This completes the collector path. The next steps are the [appropriate Slurm integration](slurm_setup.md) and a [test job through to archival](first_job.md). Additional collectors or renaming rules belong in the JSON configuration files; [Additional metrics](more_metrics.md) explains their setup.
