# Connect Slurm

Collectors supply node measurements. To associate those measurements with individual jobs, the backend also needs Slurm job data: user, project, runtime, and allocated resources.

The integration depends on the Slurm version:

| Slurm version | Path in this guide | Notes |
| --- | --- | --- |
| 24.05 and newer | [cc-slurm-adapter](slurm_adapter.md) | Recommended path; a service on the `slurmctld` node, with `slurmdbd` required |
| 23.11 | No validated setup path in this guide | The checked unchanged sync is incompatible with backend 1.5.4; [details](slurm_sync.md) |
| Other older versions | Separate verification required | No blanket compatibility claim for these versions |

The documented setup uses the official adapter without changes to its source code. Older Slurm installations need a compatibility assessment before setup.

## Prerequisites

- The backend cluster and node topology are configured.
- Compute-node names agree across Slurm, collector tags, and the cluster definition.
- The management node can reach the backend [HTTPS endpoint](https_setup.md) and has a valid backend JWT.
- The integration can access the required Slurm commands and accounting data.
- GPU PCI addresses and CPU/thread mappings match the identities used by the collector.

## Check the result

A running service does not yet confirm correct resource mapping. The next step is a [test job from start to archival](first_job.md), checking job data and measurements together. Slurm retention limits and the selected integration's polling interval still matter after a successful service start.
