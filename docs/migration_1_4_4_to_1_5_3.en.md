# Migration from 1.4.4 to 1.5.3

This migration moves backend **1.4.4 to 1.5.3**, SQLite schema **8 to 11**, and the job archive from **format 2 to 3**, following the [release notes](https://github.com/ClusterCockpit/cc-backend/blob/300108664774c5561b6838382876e247d0b043b9/ReleaseNotes.md). A new installation does not need this step. The subsequent [1.5.3 to 1.5.4 update](updates.md) is a separate operation.

The commands require root, GNU tar with ACL/xattr support, Python 3, Perl with `DBI` and `DBD::SQLite`, curl, Git, sudo, and Go ≥1.25.0. Paths and the `clustercockpit` service account must match the existing installation. This procedure covers SQLite; MySQL/MariaDB needs a separate export and migration plan.

## Changes and maintenance planning

In 1.5.3, the store runs inside the backend. The old separate store is retired at cutover. Configuration has `main`, `auth`, `archive`, and `metric-store` sections, and cluster definitions reside in the job archive.

Migration needs a maintenance window. The Slurm administrators first suspend new job starts. Running jobs must finish and their measurements must be readable from the archive. The existing scheduler integration, including any timers, collectors, and other API writers stop next. The backend and old store stop last.

**After the offline migration, the new store starts with fresh checkpoints.** The old store configuration and checkpoints remain in the backup for rollback.

## Prepare new binaries separately

Preparation starts in the cloned guide and leaves the existing installation untouched. The new release and matching migration tool have their own directory. The release includes the web frontend, so Node.js is not needed for this path. The SHA-256 check compares the download with the expected checksum.

On Ubuntu/Debian, this package command provides the Perl dependencies:

```bash
apt-get install perl libdbi-perl libdbd-sqlite3-perl
```

```bash
set -eu
GUIDE_ROOT=$(pwd -P)
PREP=/opt/monitoring/prepare-1.5.3
test ! -e "$PREP" && test ! -L "$PREP"
install -d -o root -g clustercockpit -m 0750 "$PREP"
cd "$PREP"
curl --fail --location --max-time 120 -o backend.tar.gz https://github.com/ClusterCockpit/cc-backend/releases/download/v1.5.3/cc-backend_Linux_x86_64.tar.gz
printf '%s  backend.tar.gz\n' e3e1257e1f3b8063e8b9a90a155e184e12251d318a0451b09bbb07c87c0facfb | sha256sum -c -
mkdir release
tar -xzf backend.tar.gz -C release
test -x release/cc-backend
./release/cc-backend -version
git clone https://github.com/ClusterCockpit/cc-backend.git source
git -C source checkout --detach 300108664774c5561b6838382876e247d0b043b9
test "$(git -C source rev-parse HEAD)" = 300108664774c5561b6838382876e247d0b043b9
cd source/tools/archive-migration
GOTOOLCHAIN=local go build -o "$PREP/archive-migration" .
cd "$PREP"
```

`-version` must report 1.5.3. The new `$PREP/config.json` follows the structure in the [manual installation chapter](monitoringserver.md). Existing cluster/archive paths, LDAP/JWT policy, and ports need deliberate transfer. `.env` and signing keys remain unchanged. The [RUB example](examples/rub/cc-backend/config.json) shows the structure, but its site values need adjustment.

`ui-file` points to `ui-config.json`, initially based on the [default settings](examples/minimal/cc-backend/ui-config.json). The store configuration uses fresh checkpoint paths. The service account needs access to `$PREP/archive-migration` and its parent directories.

The RUB [updateUserconfig.pl script](scripts/updateUserconfig.pl) renames saved UI preferences using [configmap_v11.json](scripts/configmap_v11.json). Values and cluster/subcluster suffixes remain unchanged. The guide adaptation supports configurable paths and applies all key changes in one transaction. The UI file, script, and mapping are prepared together:

```bash
install -m 0600 "$GUIDE_ROOT/docs/examples/minimal/cc-backend/ui-config.json" "$PREP/ui-config.json"
install -o root -g clustercockpit -m 0640 "$GUIDE_ROOT/docs/scripts/updateUserconfig.pl" "$PREP/updateUserconfig.pl"
install -o root -g clustercockpit -m 0640 "$GUIDE_ROOT/docs/scripts/configmap_v11.json" "$PREP/configmap_v11.json"
```

Existing UI customisations belong in `$PREP/ui-config.json` after this copy step.

## Complete consistent offline backup

[Backup and recovery](backup_restore.md) explains the general rules. This migration also needs the old store and its original format versions. Before shutdown, configurations, `.env`, units/drop-ins, and symlinks provide the complete path inventory:

- Database, any SQLite companion files, and the full job archive.
- Backend binary, configuration/UI, JWT/session keys, and other secrets.
- Old store binary, configuration, checkpoints, archive, and WAL.
- Units, drop-ins, system-wide environment files, and keys.
- Collector/scheduler configuration and token copies needed for rollback.

Directory backups contain their contents. External databases and other relocated paths need separate entries. `systemctl cat` shows units and drop-ins; `find /opt/monitoring -type l -ls` shows symlinks. External paths referenced in configuration values must also appear in the inventory.

An adjusted `$PREP/backup-paths.json` might look like this:

```json
{
  "paths": [
    "/opt/monitoring/cc-backend",
    "/opt/monitoring/job-archive",
    "/opt/monitoring/cc-metric-store",
    "/etc/systemd/system/clustercockpit.service",
    "/etc/systemd/system/cc-metric-store.service"
  ]
}
```

The inventory must not contain overlapping parent/child paths, nonexistent example paths, or `/` as a source. Actual external symlink targets and other files or drop-in directories need explicit entries. The [backup helper](scripts/cc-offline-backup.py) rejects missing paths and unlisted external symlink targets. It cannot discover external paths inside configuration values; completing the inventory remains an operational responsibility.

The backup destination must be new, outside every source, and large enough. GNU tar preserves ACLs, xattrs, and ownership; restoring owners requires root. All writers must remain stopped during the backup.

After all jobs finish and collectors, scheduler integration, and other writers stop, the backend and old store can stop:

```bash
systemctl stop clustercockpit.service cc-metric-store.service
```

```bash
umask 077
BACKUP=/opt/monitoring/backup-before-1.5.3
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" snapshot \
  --database /opt/monitoring/cc-backend/var/job.db \
  --archive /opt/monitoring/job-archive --record "$PREP/before.json" \
  --db-version 8 --archive-version 2
python3 "$GUIDE_ROOT/docs/scripts/cc-offline-backup.py" backup \
  --inventory "$PREP/backup-paths.json" --destination "$BACKUP"
python3 "$GUIDE_ROOT/docs/scripts/cc-offline-backup.py" restore \
  --backup "$BACKUP" --destination "$PREP/restore-check"
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" verify \
  --database "$PREP/restore-check/opt/monitoring/cc-backend/var/job.db" \
  --archive "$PREP/restore-check/opt/monitoring/job-archive" \
  --record "$PREP/before.json" --db-version 8 --archive-version 2
```

The backup directory has permissions `0700`; files are created under `umask 077`. The backup, inventory, and `before.json` belong together on suitable protected backup storage. Another checksum check there verifies the transferred copy.

The [migration checker](scripts/cc-migration-check.py) verifies database integrity and version, job count, identities and resources, archive metadata including sharing conversion, and every `data.json` hash. Checks of external paths follow the inventory beneath the staging directory. Absolute symlinks still point at original targets there; a restore test must not mistake them for restored data.

## Forward migration

The prepared configuration and binary are installed only after a successful backup and restore test. The example account and groups must match the installation. `set -eu` remains active, and tool output needs review for errors. Confirmation of the archive tool's prompt depends on these prerequisites being satisfied.

```bash
set -eu
cd /opt/monitoring/cc-backend
install -o root -g root -m 0755 "$PREP/release/cc-backend" ./cc-backend
install -o clustercockpit -g clustercockpit -m 0600 "$PREP/config.json" ./config.json
install -o clustercockpit -g clustercockpit -m 0600 "$PREP/ui-config.json" ./ui-config.json
sudo -u clustercockpit ./cc-backend -migrate-db
sudo -u clustercockpit perl "$PREP/updateUserconfig.pl" \
  --database /opt/monitoring/cc-backend/var/job.db --mapping "$PREP/configmap_v11.json"
sudo -u clustercockpit "$PREP/archive-migration" -archive /opt/monitoring/job-archive
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" verify \
  --database /opt/monitoring/cc-backend/var/job.db \
  --archive /opt/monitoring/job-archive --record "$PREP/before.json" \
  --db-version 11 --archive-version 3
sudo -u clustercockpit ./cc-backend -optimize-db
```

**`version.txt` must not be set to 3 manually.** The archive tool writes the marker after successful completion. The migration checker then verifies the database and archive as shown above. A failure leaves the services stopped. Once the cause is resolved, another attempt starts again from the consistent backup.

`-optimize-db` runs ANALYZE/VACUUM and needs additional temporary disk space. Runtime depends on database size and storage.

## Cutover and checks

At cutover, `systemctl disable cc-metric-store.service` disables the old store. Backend 1.5.3 then starts, with its journal showing any startup errors. Collector sinks now need the backend `/api/write/` URL, matching port/TLS settings, and a raw backend JWT. Old store tokens and backend tokens are not interchangeable. The scheduler integration also needs the backend URL and a valid API token. Its compatibility with the target backend must be established before cutover. The [documented adapter path](slurm_setup.md) requires Slurm 24.05 or newer.

Collectors and scheduler integration resume, followed by a small [test job from start to archival](first_job.md), before general job starts are released. Acceptance checks include login, user/role assignments, job count, representative old jobs with known series, new host/core/GPU mappings, live values, and successful archival. Before/after API responses for selected old jobs must agree.

The maintenance window ends only after these checks. Historical-backfill and rounding limits of JSON checkpoints remain; see [operation](operation.md).

## Rollback / separate restore

A failure before reopening leaves all writers stopped. Jobs already accepted since the backup first need a separate consistent backup and recovery plan: the older backup does not contain them. A 1.4.4 binary must not start with a 1.5.3 database.

The rollback below restores the complete inventory. Failed paths remain as `.failed-1.5.3` for investigation rather than being deleted wholesale.

```bash
set -eu
systemctl stop clustercockpit.service cc-metric-store.service
python3 "$GUIDE_ROOT/docs/scripts/cc-offline-backup.py" restore \
  --backup "$BACKUP" --destination "$PREP/rollback-staging"
python3 "$GUIDE_ROOT/docs/scripts/cc-migration-check.py" verify \
  --database "$PREP/rollback-staging/opt/monitoring/cc-backend/var/job.db" \
  --archive "$PREP/rollback-staging/opt/monitoring/job-archive" \
  --record "$PREP/before.json" --db-version 8 --archive-version 2
python3 - "$BACKUP/paths.json" "$PREP/rollback-staging" <<'RESTORE'
import json, pathlib, subprocess, sys
paths = [pathlib.Path(p) for p in json.loads(pathlib.Path(sys.argv[1]).read_text())['paths']]
staging = pathlib.Path(sys.argv[2])
# Preflight every source and destination before replacing any tree.
for path in paths:
    saved = staging / path.relative_to('/')
    if not (saved.exists() or saved.is_symlink()):
        raise SystemExit('Missing restored path: ' + str(path))
    quarantine = pathlib.Path(str(path) + '.failed-1.5.3')
    if quarantine.exists() or quarantine.is_symlink():
        raise SystemExit('Quarantine already exists: ' + str(path))
for path in paths:
    if path.exists() or path.is_symlink():
        path.rename(str(path) + '.failed-1.5.3')
    subprocess.run(['cp', '-a', '--', str(staging / path.relative_to('/')), str(path)], check=True)
RESTORE
systemctl daemon-reload
systemctl start cc-metric-store.service
systemctl start clustercockpit.service
```

Collectors and scheduler integration then need their saved destinations, ports, and tokens. Once those services resume, known old metric series must be readable through the 1.4.4 API before new jobs start. External symlink targets and unit drop-ins are part of the same restore inventory. Existing quarantine or staging paths cause an abort and must not be blindly overwritten.
