# Server preparation

A ClusterCockpit installation spans several systems. The first step is to assign their roles and check that each has the hardware, software, and network access it needs.

## Target systems and roles

The installation uses three types of system:

- A **dedicated monitoring server** for `cc-backend`.
- **Compute nodes** running `cc-metric-collector`, with LIKWID added when hardware metrics are needed.
- A **SLURM management node**, which will later host `cc-slurm-adapter`. The documented path requires Slurm 24.05 or newer.

### Versions, platforms, and accounts

These entries describe the examples in this guide, rather than an exhaustive list of platforms supported by each project. The exact source revisions and checksums are recorded in `versions.json` in the guide checkout.

| Component | Documented version | System and account |
|---|---|---|
| `cc-backend` | 1.5.4 for new installations; 1.5.3 as the target of the documented migration | Dedicated Ubuntu/Debian server, Linux x86_64. Installation as root; the service uses a dedicated account. |
| `cc-metric-collector` | 0.8.4 | Build example for AlmaLinux 9 under a normal account; installation on compute nodes as root. The minimal service example runs as root. |
| LIKWID | 5.5.1 | Build under a normal account; installation into the protected destination with administrator privileges. Hardware collection and its access mode are configured separately. |
| `cc-slurm-adapter` | Pinned development revision for the Slurm 24.05 and later path | Build under a normal account on the Slurm controller; setup as root, operation under a dedicated service account. |

[Choosing a Slurm integration](slurm_setup.md) explains the prerequisites and the limits for older Slurm versions. The [update overview](updates.md) distinguishes new installations from version changes.

### Installation details

The following details should be settled before installation begins:

- Cluster and node names, including the choice between short names and FQDNs. The collector, Slurm, and `cluster.json` must identify the same nodes.
- Installation paths, service accounts, and a build system with the required toolchain.
- A reachable monitoring hostname, HTTPS endpoint, and permitted API source addresses. [HTTPS setup](https_setup.md) must be complete before the first collector HTTP test.
- Working clock synchronisation on the monitoring server, compute nodes, and management node. Measurements and job times are matched through their timestamps.

Credentials and JWTs are generated during setup. Transfers between systems use the site's approved protected channel.

## Monitoring server – hardware and storage

The monitoring server needs at least:

- **CPU:** 8 cores
- **RAM:** 32 GB
- **Storage:** 500 GB, preferably on a dedicated Btrfs volume

### Recommended Btrfs partition setup

The example below creates a Btrfs file system on `/dev/vg_opt/lv_opt_btrfs` and shows the `/etc/fstab` entry for mounting it at `/opt`.

```bash
# Create a new Btrfs volume (example device: /dev/vg_opt/lv_opt_btrfs)
mkfs.btrfs -L opt-btrfs /dev/vg_opt/lv_opt_btrfs

# /etc/fstab entry:
LABEL=opt-btrfs  /opt  btrfs  rw,noatime,compress=zstd:8,autodefrag  0 0
```

The partition needs enough space for the expected volume of data. The estimates below help with sizing.

Btrfs is strongly recommended for the database, job archive, and backend metric-store data. In the tests reported by this guide, ext4 performed considerably worse. Btrfs also uses storage efficiently and makes snapshots and backups easier.

### Estimating storage requirements

As a rough guide, a cluster with about 400 nodes and 20,000 cores generates around **250 GB of metric data per year** when measurements are taken every 60 seconds.

Each job needs roughly **4 inodes** for job data, metadata, and related files. With a file system other than Btrfs, the inode limit must accommodate the expected number of jobs.

## Compute nodes – prerequisites

Building the collector version used in this guide, **v0.8.4**, requires the following on the build system:

- **Go ≥1.25.0**, with `GOTOOLCHAIN=local`. This prevents Go from automatically downloading a newer toolchain and hiding a missing prerequisite.
- Git, GCC or another suitable C compiler, GNU Make, and the development files for libc and the target platform.
- Python ≥3.9 for the guide's helper scripts.
- LIKWID 5.5.1 headers for the collector build. The matching runtime library and the required CPU and driver access are only needed for enabled hardware collectors.
- Perl with `JSON::PP` for the optional topology helper. The package is called `libjson-pp-perl` on Debian/Ubuntu and `perl-JSON-PP` on AlmaLinux.

Compute nodes running a prebuilt collector binary do not need Go or C toolchains. The initial setup with `loadavg` does not require privileged PMU or GPU access.

Build and installation should use separate roles. The [collector setup](cc_metric_collector_setup.md) chapter gives the paths to use for each step.

## Network and ports

During installation, the web frontend listens on port `8080` on the monitoring server. In production, the frontend should use HTTPS on port `443`. The SLURM management node must be able to reach port `443` so that `cc-slurm-adapter` can connect to the backend.

The `cc-backend` write API uses the same HTTPS endpoint, usually on port `443`. The compute nodes need access to this endpoint. If other hosts relay their traffic, those hosts need access instead. Firewall rules and routing must allow these connections.
