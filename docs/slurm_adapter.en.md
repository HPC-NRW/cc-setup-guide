ClusterCockpit needs a component that reliably transfers running and finished Slurm jobs to `cc-backend`. For Slurm ≥ 24.05 the recommended solution is `cc-slurm-adapter`. Older Slurm versions must use `cc-slurm-sync` (see the [chapter](slurm_sync.md)).

## Overview

The adapter is part of the ClusterCockpit ecosystem and continuously syncs job data to `cc-backend`. It runs on the same node as `slurmctld` and talks exclusively to Slurm CLI tools (`sacct`, `squeue`, `sacctmgr`, `scontrol`). It does not need `slurmrestd`, but it **does** require `slurmdbd`. A periodic timer (default: 1 minute) triggers the synchronization between Slurm and `cc-backend`. Restarting the backend, Slurm, or the adapter should not lose jobs; once the peer is back online the queued jobs are transmitted. Optionally you can trigger the adapter immediately from a Slurm prolog/epilog hook to reduce delays.

## Limitations

Slurmdbd does not keep all job information indefinitely. Resource data gathered via `scontrol show job --json` vanishes a few minutes after the job ends (controlled by `MinJobAge` in `slurm.conf`, default 300 seconds). If the adapter is down for longer, this information is lost. `cc-backend` can still list the job, but metrics cannot be attached. Do not keep `cc-slurm-adapter` stopped for long periods if historic resource assignments matter.

## Command-line usage

Option | Description
--- | ---
`-config <path>` | Path to the configuration file
`-daemon` | Run the adapter as daemon
`-debug <log-level>` | Set the log level (default 2)
`-help` | List all flags

Without `-daemon` the adapter expects to be launched from a Slurm hook (prolog/epilog mode).

## Configuration

### Example

Most keys are optional; unset fields use the defaults (see reference).

```json
{
    "pidFilePath": "/run/cc-slurm-adapter/daemon.pid",
    "prepSockListenPath": "/run/cc-slurm-adapter/daemon.sock",
    "prepSockConnectPath": "/run/cc-slurm-adapter/daemon.sock",
    "lastRunPath": "/var/lib/cc-slurm-adapter/last_run",
    "slurmPollInterval": 60,
    "slurmQueryDelay": 1,
    "slurmQueryMaxSpan": 604800,
    "slurmQueryMaxRetries": 5,
    "ccRestUrl": "https://my-cc-backend-instance.example",
    "ccRestJwt": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "gpuPciAddrs": {
        "^nodehostname0[0-9]$": [
            "00000000:00:10.0",
            "00000000:00:3F.0"
        ]
    },
    "ignoreHosts": "^nodehostname9\\w+$"
}
```

For initial tests you often only need to set `ccRestUrl`, `ccRestJwt`, and a matching `gpuPciAddrs` block.

### Reference

Key | Optional | Description
--- | --- | ---
`pidFilePath` | yes | Path to the PID file to avoid concurrent starts.
`prepSockListenPath` | yes | PrEp socket path for the daemon (Unix or TCP socket, e.g. `tcp:127.0.0.1:12345`).
`prepSockConnectPath` | yes | PrEp socket path used in prolog/epilog mode; same format as above.
`lastRunPath` | yes | File whose timestamp marks the last successful synchronization.
`slurmPollInterval` | yes | Seconds between sync runs when no hook event is received.
`slurmQueryDelay` | yes | Delay (seconds) between hook invocation and query to give Slurm time to update its state.
`slurmQueryMaxSpan` | yes | Maximum time span (seconds) for retrospective synchronization to avoid massive imports.
`slurmMaxRetries` | yes | Number of fast retry attempts after a hook event.
`ccRestUrl` | no | Base URL of the cc-backend REST API (no trailing slash).
`ccRestJwt` | no | JWT from cc-backend used for authentication.
`gpuPciAddrs` | yes | Mapping of hostname regexes to ordered lists of GPU PCI addresses so NVML IDs match.
`ignoreHosts` | yes | Regex of hostnames to ignore. If it matches all hosts of a job, that job is discarded.

## Admin guide

### Build

```bash
make
```

### Daemon

#### Deploy binary and configuration

Place the binary and config wherever you like. Because the config contains sensitive data (cc-backend JWT), keep permissions restrictive.

#### Install the systemd service

```ini
[Unit]
Description=cc-slurm-adapter

Wants=network.target
After=network.target

[Service]
User=cc-slurm-adapter
Group=slurm
ExecStart=/opt/cc-slurm-adapter/cc-slurm-adapter -daemon -config /opt/cc-slurm-adapter/config.json
WorkingDirectory=/opt/cc-slurm-adapter/
RuntimeDirectory=cc-slurm-adapter
RuntimeDirectoryMode=0750
Restart=on-failure
RestartSec=15s

[Install]
WantedBy=multi-user.target
```

The service runs as user `cc-slurm-adapter`. The runtime directory `/run/cc-slurm-adapter` hosts the PID file and PrEp socket. Group `slurm` needs access so the prolog/epilog hooks (running as the Slurm user) can connect to the socket.

#### Grant Slurm permissions

Depending on your Slurm configuration only privileged users may run `sacct` or `scontrol`. To run the adapter as its own user give it access, e.g.:

```bash
sacctmgr add user cc-slurm-adapter Account=root AdminLevel=operator
```

Missing permissions mean no jobs are reported.

#### Debugging

The daemon logs to stderr. Use `-log-level 5` for verbose output and easier troubleshooting. The default level (2) already includes all important warnings.

### Slurmctld prolog/epilog hook (optional)

To minimize latency you can trigger `cc-slurm-adapter` via a Slurmctld hook. Add this to `slurm.conf`:

```ini
PrEpPlugins=prep/script
PrologSlurmctld=/some_path/hook.sh
EpilogSlurmctld=/some_path/hook.sh
```

Example script:

```bash
#!/bin/sh

/opt/cc-slurm-adapter/cc-slurm-adapter

exit 0
```

If you use the default PrEp socket (`/run/cc-slurm-adapter/daemon.sock`), the hook does not need extra parameters. For custom paths add `-config /path/to/config.json` and make sure the `slurm` user can read it. The script should always exit with code 0 so Slurm job starts are not blocked when the adapter is temporarily unavailable.

