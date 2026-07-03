# Migration from 1.4.4 to 1.5.3

This page describes how to update an existing ClusterCockpit installation from `cc-backend` 1.4.4 to 1.5.3. It is based on the RUB update performed on 2026-04-16 and the official [cc-backend 1.5.3 release notes](https://git.clustercockpit.org/ClusterCockpit/cc-backend/src/commit/300108664774c5561b6838382876e247d0b043b9/ReleaseNotes.md).

## Important changes

- `cc-metric-store` is integrated into `cc-backend` as of 1.5. There is no separate `cc-metric-store.service` and no separate metric-store config anymore.
- `config.json` now consistently uses `kebab-case`, for example `api-allowed-ips` instead of `apiAllowedIPs`.
- The old `clusters` section was removed. Cluster information is read from the job archive.
- MySQL/MariaDB support was removed; production setups must use SQLite.
- The job archive is migrated to version 3, the database to version 11.
- Run `./cc-backend -optimize-db` after the migration for SQLite performance.
- Old UI user config entries in the database no longer fully match the new UI keys. Configure metric defaults through `ui-config.json` or the new UI config instead.

## Preparation

Create backups before updating:

```bash
systemctl stop clustercockpit.service cc-metric-store.service

cp -a /opt/monitoring/cc-backend/var/job.db /root/job.db.before-1.5.3
cp -a /opt/monitoring/job-archive /root/job-archive.before-1.5.3
cp -a /opt/monitoring/cc-backend/config.json /root/config.json.before-1.5.3
```

For very large `job.db` files, running `VACUUM` beforehand can be useful. The RUB update used a separate temporary directory:

```bash
TMPDIR=/opt/monitoring/sqlite-tmp sqlite3 /opt/monitoring/cc-backend/var/job.db "VACUUM;"
```

## Build prerequisites

For 1.5.3, Node.js 22 was installed and `cc-backend` was built from the current `main` branch:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
apt-get install -y nodejs

cd /opt/monitoring/cc-backend
git fetch origin
git checkout main
make
```

Using a matching release archive is also fine. Binary, config, and migration tools should come from the same 1.5.3 version.

## Update the config

Replace the old 1.4.4 config with a 1.5.3-compatible `config.json` and add `ui-config.json` if UI defaults should be managed centrally.

Use the following 1.5.3-compatible example configuration as a reference:

### `cc-backend/config.json`

[Open file](examples/rub/cc-backend/config.json)

<details>
<summary>Show contents</summary>

```json
--8<-- "examples/rub/cc-backend/config.json"
```

</details>

### `job-archive/cluster.json`

[Open file](examples/rub/job-archive/cluster.json)

<details>
<summary>Show contents</summary>

```json
--8<-- "examples/rub/job-archive/cluster.json"
```

</details>

During the update, the prepared config was copied into `/opt/monitoring/cc-backend/`:

```bash
mv /root/update_1.5.3/config.json /opt/monitoring/cc-backend/config.json
mv /root/update_1.5.3/ui-config.json /opt/monitoring/cc-backend/ui-config.json
```

## Migrate database and job archive

Run the database migration first:

```bash
cd /opt/monitoring/cc-backend
./cc-backend -migrate-db
```

Then migrate the job archive. The tool is part of the cc-backend source tree:

```bash
cd /opt/monitoring/cc-backend/tools/archive-migration
go build
./archive-migration -archive ../../../job-archive/
```

Set the job archive version to 3 afterwards if the migration tool or local layout did not already do it:

```bash
echo 3 > /opt/monitoring/job-archive/version.txt
```

## Performance optimization

After the migration:

```bash
cd /opt/monitoring/cc-backend
./cc-backend -optimize-db
```

According to the release notes, `-optimize-db` runs SQLite `ANALYZE` and `VACUUM`. For databases larger than 40 GB, `VACUUM` can take up to about two hours.

## Disable the old metric store

Because the metric store runs inside the backend as of 1.5.3, disable the old service:

```bash
systemctl disable --now cc-metric-store.service
```

Keep old checkpoints and archives until the new setup has been verified and the data is no longer needed.

## Update user configuration

The RUB update ran a local helper script for user config migration:

```bash
cd /root/update_1.5.3
chmod +x updateUserconfig.pl
./updateUserconfig.pl
```

If no such script exists, review or remove old UI user config entries. The release notes state that old UI keys are no longer reused.

## Start and verify

```bash
systemctl start clustercockpit.service
systemctl status clustercockpit.service
journalctl -u clustercockpit.service -f
```

Verify:

- Login and navigation work.
- Cluster and subclusters are loaded from the job archive.
- New metrics arrive through `/api/write/`.
- Old jobs and job details are visible.
- The former `cc-metric-store.service` remains disabled.
