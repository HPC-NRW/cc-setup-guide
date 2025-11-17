## Overview

`cc-slurm-sync` is a Python script developed by Paderborn University / PC². It synchronizes Slurm jobs with `cc-backend` using Slurm CLI tools (`squeue`, `sacct`, `scontrol`). Based on that data it stops all jobs in `cc-backend` that Slurm considers finished and creates new running jobs. The script must run on the `slurmctld` node and needs access to the Slurm state save directory.

For ClusterCockpit installations with Slurm versions up to 23.11 this is still the right tool. Starting with Slurm 24.05 you should switch to `cc-slurm-adapter`.

## Requirements and branches

### Slurm ≥ 22.05

Because the Slurm REST API (OpenAPI) changes with every major release, PC² maintains a dedicated branch per Slurm version. Example: for Slurm 23.11.2 checkout branch `slurm-23-11`. The `main` branch reflects current development and currently targets Slurm 24.05.

### Slurm < 22.05

For Slurm 21.08 and older use tag `openapi_0.0.37` because the JSON output from `squeue`/`sacct` changed between 21.08 and 22.05. Note: the repository includes a Slurm patch (fix for core IDs in `squeue --json`). Rebuild it against your Slurm if you need per-core assignments.

## Getting started

Clone the repository and change into it:

```bash
git clone https://github.com/pc2/cc-slurm-sync.git
cd cc-slurm-sync
```

## Configuration

Create a configuration file `config.json` before running the script, e.g. based on `config.json.example`.

### Example

```json
{
    "clustername": "yournamehere",
    "slurm": {
        "squeue": "/usr/bin/squeue",
        "sacct": "/usr/bin/sacct",
        "scontrol": "/usr/bin/scontrol",
        "state_save_location": "/var/spool/SLURM/StateSaveLocation"
    },
    "cc-backend": {
        "host": "https://some.cc.instance",
        "apikey": "<jwt token>"
    },
    "accelerators": {
        ...
    },
    "node_regex": "^(n2(lcn|cn|fpga|gpu)[\\d{2,4}\\,\\-\\[\\]]+)+$",
    "nodes": {
        "sockets": 2,
        "cores_per_socket": 64
    }
}
```

### Options

**clustername**  
Cluster name as seen by `cc-backend` (may differ from the Slurm cluster name).

**slurm**  
- `squeue` Path to the binary (`/usr/bin/squeue` default)  
- `sacct` Path to the binary (`/usr/bin/sacct`)  
- `scontrol` Path to the binary (`/usr/bin/scontrol`)  
- `state_save_location` Slurm state save directory (required)

**cc-backend**  
- `host` Base URL of the REST API without `/api` (required)  
- `apikey` JWT from `cc-backend` (required)

**accelerators**  
Mapping between GPU/accelerator identifiers: the first key is the hostname prefix (e.g., `n2gpu`), the second key the Slurm device ID, the value is the PCI address (`00000000:03:00.0`). All hosts with the same prefix must share the same mapping. You can retrieve the PCI addresses with `nvidia-smi`.

**nodes**  
Describes the node layout (`sockets`, `cores_per_socket`). Attention: with Slurm 23.x and older, `cc-slurm-sync` only supports a single configuration here. Heterogeneous clusters with varying core counts per node cannot be represented accurately.

**node_regex**  
Regex that matches all compute node hostnames (escape backslashes twice). Example:  
`^(n2(lcn|cn|fpga|gpu)[\\d{2,4}\\,\\-\\[\\]]+)+$`

## Script invocation

Run `slurm-clustercockpit-sync.py` in the directory holding `config.json`. It terminates after each sync:

- `-c, --config` Use a different config path (default: `config.json` in the current directory)
- `-j, --jobid` Sync only specific job IDs (testing)
- `-l, --limit` Limit the number of jobs to sync (in both directions)
- `--direction` Only perform start or stop actions (`start`, `stop`, default both)

