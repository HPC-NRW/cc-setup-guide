# Install server components (cc-backend & cc-metric-store)

This chapter shows how to install ClusterCockpit on the dedicated monitoring server.  
All steps can either be automated via the provided script or executed manually.

---

## Create a dedicated system user

A dedicated service user is recommended so that the web UI does not run as `root`. In that case you usually run a reverse proxy such as `nginx`, because the unprivileged user cannot bind to port 443. See the [`Operations & Troubleshooting`](operation.md) chapter for additional details.

```bash
useradd --system --no-create-home --user-group --shell "$(command -v nologin || echo /sbin/nologin)" clustercockpit
mkdir -p /opt/monitoring
chown -R clustercockpit:clustercockpit /opt/monitoring
```

## Install via script (recommended)

For a consistent installation with minimal risk of mistakes we recommend using the bundled script.  
You find the script and all templates inside `scripts/` and `scripts/templates/` in this repository.

**Layout**

```
cc-setup-guide/
├── scripts/
│   ├── cc-installation.sh
│   └── templates/
│       ├── cc-backend.json.template
│       ├── cc-metric-store.config.json.template
│       ├── cluster.json.template
│       ├── clustercockpit.service.template
│       └── cc-metric-store.service.template
```

The script expects the template files to reside in `scripts/templates/`.

> **Note about metric-store runtime parameters**  
> The generated `cc-metric-store/config.json` defines `retention-in-memory` as the time window in which metric data stays in RAM. Configure it to be at least as large as the maximum job runtime so that running jobs do not end up with gaps in their series.  
> The parameters `checkpoints.interval`, `checkpoints.restore`, and `archive.interval` are closely tied to job durations:  
> - `checkpoints.interval` is usually much shorter than `retention-in-memory` so that checkpoints are written regularly.  
> - `checkpoints.restore` must be at least as large as `retention-in-memory` so that all active jobs can be restored after a restart.  
> - `archive.interval` should be greater than or equal to `retention-in-memory` to make sure data gets archived before being evicted.  
> Pick the exact values based on maximum job length and available resources.

---

**Clone the repository**

```bash
git clone https://git-ce.rwth-aachen.de/hpc.nrw/ap3/energieeffizienter-betrieb.git cc-setup-guide
cd cc-setup-guide
```

---

**Example invocation**

```bash
bash scripts/cc-installation.sh -c demo_cluster
```

Alternative installation directory:

```bash
bash scripts/cc-installation.sh -c demo_cluster -d /srv/monitoring
```

Install under an existing user:

```bash
bash scripts/cc-installation.sh -c demo_cluster -d /srv/monitoring -u clustercockpit:clustercockpit
```

---

**Note:**  
Before executing the script, make sure it and all template files are present and executable. Adapt the template files (for example `cluster.json` or the service units) in `scripts/templates/` if you need site-specific defaults.

---

**The script takes care of all required steps—from creating directories to initial configuration, database, and user creation.  
Afterwards you will find all credentials and configuration files inside the installation directory.**

---

## Overview of the performed steps

Below you find all major installation steps in detail.  
Feel free to run them manually if you prefer not to use the script.

---

### 1. Create the directory hierarchy

```bash
export INSTALL_DIR="/opt/monitoring"
export CLUSTER_NAME="demo_cluster"

mkdir -p "$INSTALL_DIR/cc-backend"
```

---

### 2. Download and extract the components

Always download the latest releases directly from GitHub:

```bash
# Download and extract cc-backend
cd "$INSTALL_DIR"
CC_BACKEND_URL=$(curl -s https://api.github.com/repos/ClusterCockpit/cc-backend/releases/latest | grep "browser_download_url.*Linux_x86_64.tar.gz" | cut -d '"' -f 4)
wget -O cc-backend.tar.gz "$CC_BACKEND_URL"
tar -xzf cc-backend.tar.gz -C cc-backend --strip-components=1
rm cc-backend.tar.gz

# Download and extract cc-metric-store
CC_METRIC_STORE_URL=$(curl -s https://api.github.com/repos/ClusterCockpit/cc-metric-store/releases/latest | grep "browser_download_url.*Linux_x86_64.tar.gz" | cut -d '"' -f 4)
wget -O cc-metric-store.tar.gz "$CC_METRIC_STORE_URL"
tar -xzf cc-metric-store.tar.gz -C cc-metric-store --strip-components=1
rm cc-metric-store.tar.gz
```

---

### 3. Generate a JWT keypair

```bash
cd "$INSTALL_DIR/cc-backend"
chmod +x ./gen-keypair
./gen-keypair > keypair.txt

export JWT_PUBLIC_KEY=$(grep "ED25519 PUBLIC_KEY" keypair.txt | cut -d '"' -f 2)
export JWT_PRIVATE_KEY=$(grep "ED25519 PRIVATE_KEY" keypair.txt | cut -d '"' -f 2)
rm keypair.txt
```

---

### 4. Create and customize the configuration files

Use the supplied templates and replace the placeholders. For example, set the cluster name inside `config.json`:

```bash
cp templates/cc-backend.json.template ./config.json
sed -i "s/__CLUSTER_NAME__/$CLUSTER_NAME/g" ./config.json
```

Do the same for `cluster.json` and the metric-store config.

---

### 5. Create `cluster.json` (minimal setup)

Create  
`$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTERNAME/cluster.json`  
inside the installation directory.  
You can start from the provided `templates/cluster.json.template`:

<details>
<summary>Minimal example: cluster.json</summary>

```json
{
  "name": "demo_cluster",
  "metricConfig": [
    {
      "name": "cpu_load",
      "unit": {
        "base": ""
      },
      "scope": "node",
      "aggregation": "avg",
      "footprint": "avg",
      "timestep": 60,
      "peak": 1,
      "normal": 1,
      "caution": 1,
      "alert": 1
    }
  ],
  "subClusters": [
    {
      "name": "first_subcluster",
      "nodes": "node001",
      "processorType": "Demo CPU Type",
      "socketsPerNode": 1,
      "coresPerSocket": 1,
      "threadsPerCore": 1,
      "flopRateScalar": {
        "unit": {
          "base": "F/s",
          "prefix": "G"
        },
        "value": 1
      },
      "flopRateSimd": {
        "unit": {
          "base": "F/s",
          "prefix": "G"
        },
        "value": 1
      },
      "memoryBandwidth": {
        "unit": {
          "base": "B/s",
          "prefix": "G"
        },
        "value": 1
      },
      "topology": {
        "node": [
          0
        ],
        "socket": [
          [0]
        ],
        "memoryDomain": [
          [0]
        ],
        "core": [
          [0]
        ]
      }
    }
  ]
}
```
</details>

---

### 6. Configure environment variables for the backend service

```bash
cat > .env <<EOF
SESSION_KEY="$(openssl rand -base64 32)"
JWT_PRIVATE_KEY="$JWT_PRIVATE_KEY"
JWT_PUBLIC_KEY="$JWT_PUBLIC_KEY"
EOF
```

---

### 7. Initialize the backend and database

```bash
chmod +x ./cc-backend
./cc-backend -init
echo 2 > ./var/job-archive/version.txt
./cc-backend -migrate-db
```

---

### 8. Create the users

Generate random passwords:

```bash
ADMIN_USER="admin"
ADMIN_PASS=$(openssl rand -base64 18)
API_USER="apiuser"
API_PASS=$(openssl rand -base64 18)

./cc-backend -add-user "$ADMIN_USER:admin:$ADMIN_PASS"
./cc-backend -add-user "$API_USER:api:$API_PASS"
```

Store the passwords for later use:

```bash
echo "$ADMIN_PASS" > admin_password.txt
echo "$API_PASS" > apiuser_password.txt
```

---

### 9. Generate and save the API token

```bash
./cc-backend -jwt "$API_USER" | tee apikey.txt
```

> **Note:** In the generated `config.json` the `jwts.max-age` entry is empty by default, which means API tokens never expire. Set a duration there (for example `8760h` for one year) if you want to enforce an expiry. Afterwards you must generate a new token.  
> It also makes sense to restrict `apiAllowedIPs` to trusted sources. The default configuration accepts every address (`"*"`). Only individual IP addresses are supported—no CIDR notation for subnets.

---

### 10. Create the service units

Generate the systemd unit files based on the templates:

```bash
cp templates/clustercockpit.service.template "$INSTALL_DIR/clustercockpit.service"
sed -i "s@__INSTALL_DIR__@$INSTALL_DIR@g" "$INSTALL_DIR/clustercockpit.service"
cp templates/cc-metric-store.service.template "$INSTALL_DIR/cc-metric-store.service"
sed -i "s@__INSTALL_DIR__@$INSTALL_DIR@g" "$INSTALL_DIR/cc-metric-store.service"
```

Copy the units to `/etc/systemd/system/` and enable them.

## Start the services

Either start the services manually or via systemd.

**systemd start-up**

```bash
systemctl daemon-reload
systemctl enable clustercockpit.service
systemctl enable cc-metric-store.service

systemctl start clustercockpit.service
systemctl start cc-metric-store.service
```

**Check their status**

```bash
systemctl status clustercockpit.service
systemctl status cc-metric-store.service
```

---

## Status after the installation

After completing the steps above the server components are ready:

- **Services active:** `cc-backend` (web/API) and `cc-metric-store` run and can be controlled via systemd.
- **Credentials:** Admin password, API password, and API token were created.  
    - `$INSTALL_DIR/cc-backend/admin_password.txt`  
    - `$INSTALL_DIR/cc-backend/apiuser_password.txt`  
    - `$INSTALL_DIR/cc-backend/apikey.txt`
- **Configuration & secrets:**  
    - Backend: `$INSTALL_DIR/cc-backend/config.json` and `$INSTALL_DIR/cc-backend/.env`  
    - Metric store: `$INSTALL_DIR/cc-metric-store/config.json`
- **Cluster configuration:**  
    - File: `$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/cluster.json` (subclusters, metrics, thresholds, …).
- **Data & directory layout:**  
    - Archive/metadata directory: `$INSTALL_DIR/cc-backend/var/job-archive/$CLUSTER_NAME/`  
    - Archive format version: `$INSTALL_DIR/cc-backend/var/job-archive/version.txt`

At this point `cluster.json` only contains the **cluster name** and an **example subcluster list**. The detailed configuration (subclusters, metrics, thresholds) is handled in the following chapters:

- [Web interface](webinterface.md)
- [Metrics & collectors](metrics.md)

