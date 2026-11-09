# Backup and recovery

A complete backup includes both data and the state needed to operate the system: database, job archive, store files, configuration, keys, binaries, and service definitions. Copying the job archive alone is not enough for full recovery.

This chapter covers offline backups of the guide's SQLite installations using backend 1.5.3 or 1.5.4, database schema 11, and archive format 3. Older installations follow the separate [1.4.4 to 1.5.3 migration](migration_1_4_4_to_1_5_3.md). MySQL/MariaDB requires a separate database backup plan.

## Define the scope

Actual paths come from `config.json`, `.env`, systemd units, and their drop-ins. The inventory includes:

- The database, any SQLite companion files, and the complete job archive.
- Backend binary, configuration, UI file, JWT/session keys, and other secrets.
- Checkpoints, archived store files, and WAL files where present.
- Units, drop-ins, and system-wide environment files.
- Collector and scheduler configuration, including their tokens.

Directory backups contain their contents. Data outside those directories needs separate entries, including symlink targets. `systemctl cat clustercockpit.service` and `find /opt/monitoring -type l -ls` help identify paths; paths stored in configuration values also need review. Configuration on other nodes needs a separate backup on each relevant system.

The following inventory matches the installer's standard layout, with the database and job archive below the backend directory. External archive or store directories need extra entries. Example paths that do not exist must not appear in the inventory.

```json
{
  "paths": [
    "/opt/monitoring/cc-backend",
    "/etc/systemd/system/clustercockpit.service"
  ]
}
```

The [backup helper](scripts/cc-offline-backup.py) rejects missing or overlapping paths, `/` as a source, and unlisted external symlink targets. It does not discover external paths stored in configuration values. A complete inventory remains a prerequisite.

## Stop the services

A consistent backup requires all writers to stop:

1. New job starts are suspended in agreement with the Slurm administrators.
2. Running jobs finish and their successful archival is verified.
3. Collectors, scheduler integration, and other API writers stop on their respective systems.
4. The backend stops last.

```bash
systemctl stop clustercockpit.service
```

Backend 1.5.3 and 1.5.4 use the integrated store in this guide. An additional `cc-metric-store.service` belongs only to an older installation that uses it. This procedure does not produce a consistent backup while writers are running.

## Create the backup and test a restore

The prerequisites are root, Python 3, and GNU tar with ACL/xattr support. The following commands share one root Bash session. `GUIDE_DIR`, data paths, and the backup directory must match the installation. The existing backup directory is protected and has space for both the backup and its restore test. `BACKUP` and `RESTORE` must be new directories outside all source paths.

The adjusted inventory in this example is `/srv/cc-backups/backup-paths.json`.

```bash
set -eu
umask 077
GUIDE_DIR=/path/to/cc-setup-guide
BACKEND_DIR=/opt/monitoring/cc-backend
ARCHIVE_DIR="$BACKEND_DIR/var/job-archive"
BACKUP_ROOT=/srv/cc-backups
BACKUP="$BACKUP_ROOT/before-maintenance"
RESTORE="$BACKUP_ROOT/restore-check"
RECORD="$BACKUP_ROOT/before.json"
python3 "$GUIDE_DIR/docs/scripts/cc-migration-check.py" snapshot \
  --database "$BACKEND_DIR/var/job.db" --archive "$ARCHIVE_DIR" \
  --record "$RECORD" --db-version 11 --archive-version 3
python3 "$GUIDE_DIR/docs/scripts/cc-offline-backup.py" backup \
  --inventory "$BACKUP_ROOT/backup-paths.json" --destination "$BACKUP"
python3 "$GUIDE_DIR/docs/scripts/cc-offline-backup.py" restore \
  --backup "$BACKUP" --destination "$RESTORE"
python3 "$GUIDE_DIR/docs/scripts/cc-migration-check.py" verify \
  --database "$RESTORE$BACKEND_DIR/var/job.db" --archive "$RESTORE$ARCHIVE_DIR" \
  --record "$RECORD" --db-version 11 --archive-version 3
```

The restore uses a new directory and does not overwrite the installation. Absolute paths are reproduced below it: `/opt/monitoring/cc-backend` becomes `$RESTORE/opt/monitoring/cc-backend`. Checks of external data need paths from the inventory. Absolute symlinks still point at their original targets after extraction; a restore test must not accidentally inspect live data through those links.

The migration checker verifies database integrity and version, job count, identities and resources, archive metadata, and `data.json` hashes. It does not replace checks of saved keys, configuration, and operating-system permissions. GNU tar preserves ACLs, xattrs, and owners; restoring ownership requires root.

The backup directory has permissions `0700`; files are created under `umask 077`. The backup, inventory, and `before.json` belong together on a suitable protected backup medium. Another checksum check there verifies the transferred copy. A successful restore test establishes that the backup is readable.

## Recover the saved state

Recovery starts with the same shutdown of all writers. A fresh restore into an empty staging directory and the checks above must succeed before installation files are replaced.

For each inventoried path, the current contents remain under an unused diagnostic name. The verified restore is then copied to the original location with owners and permissions preserved. This includes external symlink targets, keys, units, and drop-ins. Existing diagnostic or destination paths need review before any replacement.

Database, archive, configuration, and binary form one consistent state. An old binary must not start against a database that has since been migrated. Jobs received after the backup need a separate consistent backup before recovery; the older backup does not contain them.

After units are restored, `systemctl daemon-reload` and a backend start apply the saved setup. Collector and scheduler destinations, ports, and tokens must match the restored backend. Login, roles, known archived jobs, and a [complete test job](first_job.md) must pass before new job starts are released. The integrated store's [persistence limits](operation.md#integrated-store-persistence-limits) still apply.
