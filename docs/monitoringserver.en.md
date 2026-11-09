# Install server components

This chapter covers a **new installation on a dedicated Ubuntu/Debian monitoring server (Linux x86_64)**. Installation runs as `root`; the service later uses a separate account. Existing installations follow the separate [update and migration guidance](operation.md).

The recommended route uses the installation script. The [manual path](#manual-path) performs the same work in individual steps and is an alternative. Both routes finish with [service installation and verification](#install-start-and-verify-the-service).

## Prerequisites and service account

Installation requires Bash, Python ≥3.9 with its standard library, curl, OpenSSL, GNU coreutils, getent, and systemd tools for unit validation. On the new monitoring server, the following commands install the packages, create the service account, and download the guide:

```bash
apt-get update
apt-get install python3 curl openssl ca-certificates git systemd
useradd --system --no-create-home --user-group --shell /usr/sbin/nologin clustercockpit
git clone https://github.com/HPC-NRW/cc-setup-guide.git
cd cc-setup-guide
```

If the service account already exists, the `useradd` command is unnecessary. The installation target must not exist yet; it must not be created or prepared with a recursive `chown` in advance. `/opt` or `/srv` must already exist, be owned by root, and deny write access to the group and other users. Every parent must also be a real directory rather than a symlink.

## Install via script

The script requires the complete checkout, including `versions.json`, `scripts/templates/`, and `docs/examples/minimal/`. Its source is in [cc-installation.sh](https://github.com/hpc-nrw/cc-setup-guide/blob/main/scripts/cc-installation.sh) and [install_support.py](https://github.com/hpc-nrw/cc-setup-guide/blob/main/scripts/install_support.py).

The following command installs into `/opt/monitoring` with the example cluster `demo_cluster`:

```bash
bash scripts/cc-installation.sh -c demo_cluster
```

A different target directory and service account can be supplied explicitly. This target must not exist yet either:

```bash
bash scripts/cc-installation.sh -c demo_cluster -d /srv/monitoring -u clustercockpit:clustercockpit
```

<details>
<summary>Accepted cluster names, paths, and account names</summary>

Cluster names must match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Paths must be absolute and contain at least two components. Letters, digits, `_`, `-`, and `.` are allowed within a component. The script rejects `.`/`..`, relative paths, symlinks, spaces, newlines, quotes, backslashes, `&`, `@`, and `%`.

Account names must match `[a-z_][a-z0-9_-]{0,31}`. `-u name` uses the group with the same name; `-u name:group` specifies the account and group separately.

</details>

Before downloading anything, the script checks accounts, paths, the version manifest, templates, and UI configuration. It rejects an existing target without modifying it, including an empty directory or the remains of an interrupted attempt. There is no update or resume mode. An interrupted installation retains its private state for diagnosis; that state needs inspection before deletion or reuse.

`umask 077` applies before the first write. Passwords and JWT are not printed to stdout, and the private diagnostics in `.install-tmp` must not be published either. A successful run prepares the installation. **The service has not been installed or started yet.** The next step is [service installation and verification](#install-start-and-verify-the-service).

## Manual path

The following steps replace the installation script. They require a **separate fresh target** and run in order in the same root Bash session, starting in the cloned guide. The Python helpers in [install_support.py](https://github.com/hpc-nrw/cc-setup-guide/blob/main/scripts/install_support.py) validate inputs and archives, create secure key files, and set permissions. They do not perform installation, downloads, or service starts in the background here.

### 1. Check the environment and reserve a new target

The following block selects the same release as the installation script. `GUIDE_DIR` retains the absolute path to the template source after later `cd` commands.

<!-- installer-manual-1 -->
```bash
set +x
set -euo pipefail
umask 077
# Run in the cloned guide, in the same root Bash session for all steps.
GUIDE_DIR=$(pwd -P)
INSTALL_DIR=/opt/monitoring
CLUSTER_NAME=demo_cluster
CC_USER=clustercockpit
CC_GROUP=clustercockpit
HELPER="$GUIDE_DIR/scripts/install_support.py"
for command in python3 curl openssl install mkdir rm cp sed stat uname systemd-analyze; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done
VERSION=$(python3 "$HELPER" default-version "$GUIDE_DIR")
python3 "$HELPER" preflight "$GUIDE_DIR" "$INSTALL_DIR" "$CLUSTER_NAME" "$CC_USER" "$CC_GROUP" "$VERSION"
test "$(uname -s):$(uname -m)" = Linux:x86_64
mkdir -m 0700 -- "$INSTALL_DIR"
install -d -m 0700 "$INSTALL_DIR/cc-backend" "$INSTALL_DIR/.install-tmp"
TEMP_DIR="$INSTALL_DIR/.install-tmp"
```

### 2. Download and extract the pinned release with validation

The helper validates the download and extracts the release without overwriting existing files.

<details>
<summary>Release validation details</summary>

Validation requires valid release JSON with exactly one matching asset, the expected SHA256 checksum, and exactly six flat regular files. Links, path traversal, and unexpected archive layouts are rejected. Extraction does not use `--strip-components=1`.

</details>

<!-- installer-manual-2 -->
```bash
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 120 --retry 2 \
    "https://api.github.com/repos/ClusterCockpit/cc-backend/releases/tags/v$VERSION" > "$TEMP_DIR/release.json"
URL=$(python3 "$HELPER" release-url "$GUIDE_DIR" "$VERSION" "$TEMP_DIR/release.json")
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 300 --retry 2 "$URL" > "$TEMP_DIR/backend.tar.gz"
python3 "$HELPER" extract "$GUIDE_DIR" "$VERSION" "$TEMP_DIR/backend.tar.gz" "$INSTALL_DIR/cc-backend"
cd "$INSTALL_DIR/cc-backend"
test -x ./cc-backend && test -x ./gen-keypair
```

### 3. Generate new keys and session secret

`gen-keypair` generates new Ed25519 keys. The helper checks their number and lengths and adds a random session secret. Key contents are not printed.

<!-- installer-manual-3 -->
```bash
./gen-keypair > "$TEMP_DIR/keypair.txt"
python3 "$HELPER" environment "$TEMP_DIR/keypair.txt" .env
rm -- "$TEMP_DIR/keypair.txt"
```

### 4. Create backend, UI, cluster and service configuration

The minimal template already contains `cpu_load` and example host `node001` in subcluster `first_subcluster`. Host names, topology, and thresholds must match the actual hardware before site data is collected; [first cluster setup](cluster_minimal.md) describes those changes.

The supplied [ui-config.json](examples/minimal/cc-backend/ui-config.json) belongs in the backend working directory alongside `config.json`. It contains the web interface defaults; `ui-file` in `config.json` points to it. Later display customizations belong in that file.

<!-- installer-manual-4 -->
```bash
cp "$GUIDE_DIR/scripts/templates/cc-backend.json.template" config.json
cp "$GUIDE_DIR/docs/examples/minimal/cc-backend/ui-config.json" ui-config.json
mkdir -p "var/job-archive/$CLUSTER_NAME"
python3 - "$GUIDE_DIR" "$CLUSTER_NAME" <<'CONFIG'
import json, pathlib, sys
source = pathlib.Path(sys.argv[1]) / 'scripts/templates/cluster.json.template'
cluster = json.loads(source.read_text())
cluster['name'] = sys.argv[2]
with (pathlib.Path('var/job-archive') / sys.argv[2] / 'cluster.json').open('x') as output:
    json.dump(cluster, output, indent=2)
    output.write('\n')
CONFIG
# Only this newly created, empty archive: never change an existing format marker.
printf '3\n' > var/job-archive/version.txt
sed -e "s@__INSTALL_DIR__@$INSTALL_DIR@g" \
    -e "s@__CC_USER__@$CC_USER@g" -e "s@__CC_GROUP__@$CC_GROUP@g" \
    "$GUIDE_DIR/scripts/templates/clustercockpit.service.template" > "$INSTALL_DIR/clustercockpit.service"
```

### 5. Create an empty database and users

`-migrate-db` creates the empty database. **`-init` is unsuitable here:** it would replace custom configuration and secrets with upstream examples, or do nothing if `var` already exists. The archive marker `3` set earlier applies only to the new empty archive and does not replace a migration.

The CLI prints the JWT alongside other text. The helper extracts exactly one structurally valid EdDSA token into `apikey.txt`.

<!-- installer-manual-5 -->
```bash
./cc-backend -migrate-db > "$TEMP_DIR/database.log" 2>&1
ADMIN_PASS=$(openssl rand -base64 24)
API_PASS=$(openssl rand -base64 24)
./cc-backend -add-user "admin:admin:$ADMIN_PASS" > "$TEMP_DIR/admin.log" 2>&1
./cc-backend -add-user "apiuser:api:$API_PASS" > "$TEMP_DIR/apiuser.log" 2>&1
printf '%s\n' "$ADMIN_PASS" > admin_password.txt
printf '%s\n' "$API_PASS" > apiuser_password.txt
unset ADMIN_PASS API_PASS
./cc-backend -jwt apiuser > "$TEMP_DIR/jwt.txt" 2> "$TEMP_DIR/jwt.log"
python3 "$HELPER" token "$TEMP_DIR/jwt.txt" apikey.txt
rm -- "$TEMP_DIR/jwt.txt"
```

**Upstream CLI limit:** `-add-user` accepts the password as a command-line argument and has no stdin or password-file option. On systems exposing process arguments, other local users may see the password during this short call. Account creation therefore belongs on the fresh dedicated monitoring server before untrusted local access is enabled. Protected files and suppressed log output do not remove this limitation.

### 6. Finalize ownership/permissions and verify the unit

The helper validates the created database users and changes permissions only inside the new target: root owns binaries and configuration, while the service account owns runtime state beneath `var`. The API file is readable only by root. Any required copies belong in protected client configurations; a broad `chown -R` on an unrelated installation prefix is unsuitable.

<!-- installer-manual-6 -->
```bash
# Validate the database/users and set explicit final owners and permissions.
python3 "$HELPER" finish "$INSTALL_DIR" "$CC_USER" "$CC_GROUP"
# Expected: root:service-group 0750 for installation/backend directories;
# root:service-group 0640 for .env/config, root-only 0600 for password/JWT files;
# service-user:service-group 0700 directories / 0600 files beneath var.
stat -c '%U:%G %a %n' . .env config.json ui-config.json apikey.txt var var/job.db
systemd-analyze verify "$INSTALL_DIR/clustercockpit.service"
```

## Install, start and verify the service

This final step applies to both installation routes. `INSTALL_DIR` must match the selected target: `/opt/monitoring` for the default command, or `/srv/monitoring` for the example with `-d`. The assignment below runs in the current shell; the installation script does not set a variable in its parent shell.

The configuration, cluster host names, and network access need checking before startup. The following commands run as root:

```bash
INSTALL_DIR=/opt/monitoring
install -o root -g root -m 0644 "$INSTALL_DIR/clustercockpit.service" /etc/systemd/system/clustercockpit.service
systemctl daemon-reload
systemctl enable --now clustercockpit.service
systemctl status clustercockpit.service
journalctl -u clustercockpit.service -n 50 --no-pager
```

The service should report an active state, with no configuration-loading or database-opening errors in the journal. The web interface initially listens on port `8080`. The next checks are the [first login](webinterface.md) and [cluster and node configuration](cluster_minimal.md).

Before the first collector connection over HTTPS, the [reverse proxy and TLS](https_setup.md) and allowed API source addresses must be configured. The collector steps use this HTTPS endpoint.

Password files and the **raw JWT** are stored in `$INSTALL_DIR/cc-backend/`: `admin_password.txt`, `apiuser_password.txt`, and `apikey.txt`, each with mode `0600`. `.env` holds the private signing and session values with mode `0640`, owned by root and the service group. These files must not be published.

The template sets `auth.jwts.max-age` to `8760h` (365 days). Replacement tokens must reach all clients before expiry. An empty value would create tokens without expiry; later configuration changes do not alter tokens already issued. `main.api-allowed-ips` accepts individual IP addresses, not CIDR networks. The default `*` needs deliberate restriction for the site.

`metric-store.retention-in-memory` sets retention in memory. The memory cap, active jobs, restarts, and JSON-checkpoint rounding also affect retention. Limits and backups are covered in [Operations](operation.md). The [first metric](metrics.md) and [metric reception and display](metric_receive_display.md) follow the collector setup.
