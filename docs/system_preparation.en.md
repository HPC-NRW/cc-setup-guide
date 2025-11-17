# Server preparation

Before installing ClusterCockpit you should prepare the involved systems and make sure the basic requirements are in place.  
The following sections describe the system roles together with recommended hardware and storage parameters.

---

## Target systems and roles

You need the following systems:

- **Monitoring server**  
  (Dedicated machine that runs `cc-backend` and `cc-metric-store`)
- **Compute nodes**  
  (Run `cc-metric-collector` and LIKWID)
- **SLURM management node**  
  (Later hosts the `cc-slurm-adapter`)

---

## Monitoring server – hardware and storage

- **CPU:** At least 8 cores
- **RAM:** At least 32 GB
- **Storage:** At least 500 GB, ideally as a dedicated Btrfs volume.

### Recommended Btrfs partition setup

**Example: create and mount a Btrfs file system**

```bash
# Create a new Btrfs volume (example device: /dev/vg_opt/lv_opt_btrfs)
mkfs.btrfs -L opt-btrfs /dev/vg_opt/lv_opt_btrfs

# /etc/fstab entry:
LABEL=opt-btrfs  /opt  btrfs  rw,noatime,compress=zstd:8,autodefrag  0 0
```

**Important notes:**

* Size the partition generously (see below).
* **btrfs** is strongly recommended for the database (cc-metric-store) and the backend because ext4 performed considerably worse during testing.
* Btrfs makes storage usage efficient and simplifies snapshots/backups.

### Estimating storage requirements

* Rough rule of thumb:  
  A cluster with roughly 400 nodes / 20,000 cores and a sampling interval of 60 seconds generates around **250 GB of metric data per year**.
* **Inodes:**  
  Each job needs roughly **4 inodes** (data, metadata, ...).  
  If you use a different file system than btrfs you have to provision a larger inode budget.

---

## Compute nodes – prerequisites

* **go > 1.24.3**
* **Perl**
* **Python 3**

---

## Network and ports

* **Monitoring server:**

  * During installation the web frontend listens on port `8080`.
  * In production the web frontend should run on port `443` (HTTPS).
  * Port `443` must be reachable from the SLURM management node (cc-slurm-adapter).

* **cc-metric-store:**

  * Listens on port `8081`.
  * The port must be reachable from the compute nodes (or intermediate routing hosts if you relay traffic).
  * Configure corresponding firewall/routing rules.

---

With these preparations in place the system is ready to install ClusterCockpit.

