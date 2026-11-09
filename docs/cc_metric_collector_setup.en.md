# Install cc-metric-collector

The collector runs on the compute nodes. This chapter builds **v0.8.4** with LIKWID **5.5.1** headers and installs the basic configuration files. The first test collects only `loadavg`, which requires neither a LIKWID runtime library nor privileged hardware access.

The prerequisites are a running backend and a [matching cluster and node definition](cluster_minimal.md). Before HTTP transmission, the [HTTPS endpoint](https_setup.md) must also be reachable, the API must allow the collector's source address, and a protected copy of the raw JWT from `cc-backend/apikey.txt` must be available on the target system. The first stdout check does not send data to that endpoint.

## Source and build

The AlmaLinux 9 build system needs Git, a C compiler with libc development files, Go **1.25.0 or newer**, Python3, and `install`. The build runs as a normal user. Go downloads only modules pinned in `go.mod` and `go.sum`; the LIKWID 5.5.1 headers come from a fixed source revision. A matching full LIKWID installation is needed later only for optional hardware collection.

```bash
# Start in the guide checkout; use a normal build account.
GUIDE_DIR="$(pwd -P)"
BUILD_DIR="$HOME/build/cc-metric-collector-v0.8.4"
install -d "$BUILD_DIR"
git clone --branch v0.8.4 https://github.com/ClusterCockpit/cc-metric-collector.git "$BUILD_DIR/source"
cd "$BUILD_DIR/source"
test "$(git rev-parse HEAD)" = 6df8da8fe9e3fe9459aa0538b3d4027ad4f906b0
git clone --branch v5.5.1 https://github.com/RRZE-HPC/likwid.git "$BUILD_DIR/likwid-headers"
test "$(git -C "$BUILD_DIR/likwid-headers" rev-parse HEAD)" = a7dee7f35ccd68ce0717503a942238e740a01a1d
install -d collectors/likwid
install -m 0644 "$BUILD_DIR/likwid-headers/src/includes/"likwid*.h collectors/likwid/
export GOTOOLCHAIN=local
go version  # must be Go 1.25.0 or newer; no implicit toolchain download
go build -mod=readonly -o cc-metric-collector .
```

Repeating the build requires inspection of the existing destination and a new empty build path. The build produces the binary. Configuration files come from this guide rather than the collector source tree.

## Files and basic configuration

The following steps run as root on the compute node, in its image, or on the intended shared filesystem. `GUIDE_DIR` and `BUILD_DIR` must point to the absolute paths from the build step; changing accounts does not automatically carry over shell variables. The example installs into `/cluster/monitoring/cc-metric-collector`.

```bash
# Run these installation steps as root on the compute-node image/shared filesystem.
# Set GUIDE_DIR and BUILD_DIR to the absolute paths used by the build account.
COLLECTOR_DIR=/cluster/monitoring/cc-metric-collector
install -d -m 0750 "$COLLECTOR_DIR"
install -m 0755 "$BUILD_DIR/source/cc-metric-collector" "$COLLECTOR_DIR/"
install -m 0600 "$GUIDE_DIR/docs/examples/minimal/cc-metric-collector/"*.json "$COLLECTOR_DIR/"
install -m 0600 "$COLLECTOR_DIR/base-router.json" "$COLLECTOR_DIR/router.json"
cd "$COLLECTOR_DIR"
```

On a shared filesystem, directories and permissions must suit the intended service accounts. The HTTP token must not be readable by all cluster users. The root service used here can read files with mode `0600`. The basic setup enables only `loadavg`; additional collectors are enabled individually later.

The main configuration, `config.json`, is:

```json
--8<-- "examples/minimal/cc-metric-collector/config.json"
```

All referenced files are in the same working directory. `main.interval` sets the collection interval, while `main.duration` sets the measuring duration for collectors that require one. `receivers.json` contains `{}`. The test configuration `config_stdout.json` uses `sinks_stdout.json` and writes only to the terminal. The [metric data flow](metric_flow.md) explains the role of each file.

For HTTP transmission, the sink file still needs the cluster, server address, and **raw** JWT from `cc-backend/apikey.txt`. The optional [configure-collector.py](scripts/configure-collector.py) helper sets the `cluster` entry under `add_tags` in `router.json`, plus `url` and `jwt` in the HTTP sink in `sinks.json`. It reads the JWT from a file without printing it and sets both JSON files to mode `0600`. Collector selection and the backend's `cluster.json` remain unchanged.

This script belongs to the guide, not the official collector. The same fields can be edited directly in the JSON files, followed by `chmod 0600 router.json sinks.json` to set their permissions.

```bash
# TOKEN_FILE is a securely transferred local copy of cc-backend/apikey.txt.
TOKEN_FILE=/root/cc-backend-apikey.txt
chmod 0600 "$TOKEN_FILE"
python3 "$GUIDE_DIR/docs/scripts/configure-collector.py" \
  --directory "$COLLECTOR_DIR" --cluster demo_cluster \
  --url 'https://monitoring.example.org/api/write/?cluster=demo_cluster' \
  --token-file "$TOKEN_FILE"
./cc-metric-collector -config ./config_stdout.json -once
```

`GUIDE_DIR` must keep pointing to the guide after a `cd`. The example HTTPS address, cluster name, and token file need the installation's actual values. The hostname sent by the collector must match the node pattern in `cluster.json`; FQDNs and short names must be used consistently. The `hostname` command shows the name for comparison.

The stdout test should show `load_one` and the other loadavg values for the expected cluster and node. The next step renames `load_one` to `cpu_load`. Only then is the configuration ready for the HTTP check with `./cc-metric-collector -config ./config.json -once`. Transmission errors appear in the collector log; the backend provides a further check of the node and cluster assignment.

## Choose the metric set

A collector can expose dozens of measurements, but job monitoring usually needs only a subset. ClusterCockpit does not replace full system monitoring. Metric selection should therefore follow the analyses the installation actually needs.

The guide starts with `cpu_load` and adds metrics for common operational and troubleshooting tasks. The [upstream collector overview](https://github.com/ClusterCockpit/cc-metric-collector/blob/v0.8.4/collectors/README.md) describes further options.

## Next steps

There are two alternative routes to the first metric:

- The [quick setup](cc_metric_collector_quicksetup.md) uses the complete minimal router configuration.
- The [first-metric walkthrough](metrics.md) explains collection, renaming, filtering, and the backend definition individually.

Both routes lead to [running the collector as a service](collector_service.md) and a populated node time series, followed by [Slurm integration](slurm_setup.md). [Additional metrics](more_metrics.md) and the [RUB example profile](example_profiles.md) are optional extensions.
