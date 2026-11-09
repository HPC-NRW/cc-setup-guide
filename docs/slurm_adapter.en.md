# cc-slurm-adapter

For Slurm 24.05 and newer, `cc-slurm-adapter` is the recommended integration. It sends running and completed jobs to `cc-backend`. [Choosing the Slurm integration](slurm_setup.md) also covers the compatibility limits of older Slurm versions.

## Overview

The adapter runs on the same node as `slurmctld` and uses the Slurm commands `sacct`, `squeue`, `sacctmgr`, and `scontrol`. It requires `slurmdbd`, but not `slurmrestd`. A periodic timer triggers synchronisation every minute by default.

After an interruption, the adapter attempts to supply missing job data. Slurm's retention limits still apply. An optional prolog/epilog hook can trigger the query immediately and reduce delay.

## Limitations

Slurmdbd does not retain all job information indefinitely. Resource data from `scontrol show job --json` disappears a few minutes after completion. `MinJobAge` in `slurm.conf` controls this interval; its default is 300 seconds.

A longer outage can therefore lose resource information. The backend may still list the job but cannot attach metrics to it. Long adapter interruptions during job operation are consequently a problem.

## Command-line usage

Option | Description
--- | ---
`-config <path>` | Path to the configuration file
`-daemon` | Starts the adapter as a daemon
`-debug <log-level>` | Sets the log level (default 2)
`-help` | Lists all flags

Without `-daemon`, the adapter expects a Slurm hook invocation in prolog/epilog mode.

## Configuration

### Example

Many fields are optional and use defaults when absent. [adapter.json](examples/slurm/adapter.json) contains the complete example:

```json
--8<-- "examples/slurm/adapter.json"
```

An initial test system often needs changes only to `ccRestUrl`, `ccRestJwt`, and a matching `gpuPciAddrs` block. Hostnames and GPU mappings must match collector tags.

### Reference

Key | Optional | Description
--- | --- | ---
`pidFilePath` | yes | PID file used to prevent concurrent starts.
`prepSockListenPath` | yes | Daemon PrEp socket, as a Unix or TCP socket, such as `tcp:127.0.0.1:12345`.
`prepSockConnectPath` | yes | PrEp socket in prolog/epilog mode, using the same format.
`lastRunPath` | yes | File whose timestamp records the last successful synchronisation.
`slurmPollInterval` | yes | Seconds between synchronisation runs without a hook event.
`slurmQueryDelay` | yes | Delay in seconds between the hook invocation and Slurm query.
`slurmQueryMaxSpan` | yes | Maximum retrospective query interval in seconds, limiting large imports.
`slurmMaxRetries` | yes | Number of fast Slurm query retries after a hook event.
`ccRestUrl` | no | Base URL of the backend REST API without a trailing slash.
`ccRestJwt` | no | Backend JWT for authentication.
`gpuPciAddrs` | yes | Mapping of hostname regexes to ordered GPU PCI addresses for NVML IDs.
`ignoreHosts` | yes | Regex for ignored hosts. A job is discarded if every host matches.

## Admin guide

### Prepare the build

The build needs Git, Make, Python 3, and Go ≥1.25.0. The checkout pins the source revision for the configuration shown here. `GOTOOLCHAIN=local` uses the installed Go toolchain. These commands run as the build user on the Slurm controller, initially from the cloned guide:

```bash
GUIDE_ROOT=$(pwd -P)
git clone https://github.com/ClusterCockpit/cc-slurm-adapter.git cc-slurm-adapter-src
cd cc-slurm-adapter-src
git checkout --detach a8131f9ffe635303b7457f019999ad64add99dd6
test "$(git rev-parse HEAD)" = a8131f9ffe635303b7457f019999ad64add99dd6
go version
GOTOOLCHAIN=local make
```

### Service account, configuration and unit

Installation runs as root on a new target. The Slurm group must already exist. An existing installation needs a state review first; its accounts and configuration must not be overwritten. In the root session, `GUIDE_ROOT` must still contain the absolute guide path, and the working directory must be the adapter build directory.

A protected copy of the raw backend token from `/opt/monitoring/cc-backend/apikey.txt` must already be available as `/root/cc-backend-apikey.txt` with permissions `0600`. Transfer uses the approved secure channel; the JWT must not appear in command-line arguments.

```bash
getent group slurm
useradd --system --user-group --home-dir /opt/cc-slurm-adapter --no-create-home --shell /usr/sbin/nologin cc-slurm-adapter
install -d -m 0755 /opt/cc-slurm-adapter
install -m 0755 cc-slurm-adapter /opt/cc-slurm-adapter/cc-slurm-adapter
install -d -o root -g cc-slurm-adapter -m 0750 /etc/cc-slurm-adapter
install -o root -g cc-slurm-adapter -m 0640 "$GUIDE_ROOT/docs/examples/slurm/adapter.json" /etc/cc-slurm-adapter/config.json
install -o root -g cc-slurm-adapter -m 0640 /root/cc-backend-apikey.txt /etc/cc-slurm-adapter/apikey.txt
python3 - <<'CONFIG'
import json
from pathlib import Path
path = Path('/etc/cc-slurm-adapter/config.json')
config = json.loads(path.read_text())
config['ccRestJwt'] = Path('/etc/cc-slurm-adapter/apikey.txt').read_text().strip()
path.write_text(json.dumps(config, indent=2) + '\n')
CONFIG
install -m 0644 "$GUIDE_ROOT/docs/examples/slurm/cc-slurm-adapter.service" /etc/systemd/system/cc-slurm-adapter.service
```

In `/etc/cc-slurm-adapter/config.json`, `ccRestUrl` and host/GPU mappings need the cluster's actual values. GPU PCI addresses must match collector tags. The file retains permissions `0640` and ownership `root:cc-slurm-adapter`. The service account reads it through its supplementary group; the Slurm group only gains access to the runtime/hook socket and state directory.

The complete unit:

```ini
--8<-- "examples/slurm/cc-slurm-adapter.service"
```

`StateDirectory` creates `/var/lib/cc-slurm-adapter`; `RuntimeDirectory` creates `/run/cc-slurm-adapter`. The account needs access to `sacct`, `squeue`, `scontrol`, and accounting data. The Slurm grant below is site-specific: its account and AdminLevel need agreement with the Slurm administrators. Root can then activate the service:

```bash
sacctmgr add user cc-slurm-adapter Account=root AdminLevel=operator
systemctl daemon-reload
systemctl enable --now cc-slurm-adapter.service
systemctl status cc-slurm-adapter.service
journalctl -u cc-slurm-adapter.service -n 100 --no-pager
```

A [test job from start to archival](first_job.md) is required before production use. User, hosts, core/GPU allocation, job state, and measurements must agree in the backend.

The valid diagnostic flag is `-debug 5`. The normal service must be stopped first. A diagnostic invocation uses `-daemon -debug 5 -config /etc/cc-slurm-adapter/config.json` under the service account. A second daemon must not run concurrently.

### Slurmctld prolog/epilog hook (optional)

A Slurmctld hook can trigger the adapter immediately. It uses these additions to `slurm.conf`:

```ini
PrEpPlugins=prep/script
PrologSlurmctld=/some_path/hook.sh
EpilogSlurmctld=/some_path/hook.sh
```

The corresponding example script:

```bash
#!/bin/sh

/opt/cc-slurm-adapter/cc-slurm-adapter

exit 0
```

The default PrEp socket `/run/cc-slurm-adapter/daemon.sock` needs no configuration argument in the hook. Other paths require `-config /path/to/config.json` and suitable access for `slurm`. The script should always exit with code `0` so a temporarily unavailable adapter does not block Slurm job starts.
