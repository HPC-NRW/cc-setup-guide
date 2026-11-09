# Versions and updates

A new installation uses backend **1.5.4**. An existing system needs a separate update procedure: the installer never overwrites an installation and has no update or resume mode.

## Documented versions

| Component or operation | Version covered by this guide |
| --- | --- |
| New backend installation | 1.5.4, SQLite schema 11, job archive format 3 |
| Older backend migration | [1.4.4 → 1.5.3](migration_1_4_4_to_1_5_3.md), schema 8 → 11, archive format 2 → 3 |
| Backend update without a format change | 1.5.3 → 1.5.4, described below |
| Metric collector | v0.8.4 |
| LIKWID | 5.5.1 |
| Slurm adapter | Pinned source revision for Slurm 24.05 and newer |

For Slurm 23.11, there is [no validated unpatched setup path to backend 1.5.4](slurm_sync.md). The sync entry in the version manifest records only the incompatible revision checked for this finding.

The [version manifest](https://github.com/hpc-nrw/cc-setup-guide/blob/main/versions.json) records exact commits and checksums. Combinations outside this table need a separate review of release notes and configuration changes. These chapters are not a general upgrade procedure for arbitrary backend or Slurm versions.

## Update backend 1.5.3 to 1.5.4

This path applies to the guide's SQLite installation already using schema 11 and archive format 3. The [1.5.4 release notes](https://github.com/ClusterCockpit/cc-backend/blob/c94f5918f3126bacabd91e9ae6e194f3de6ea83c/ReleaseNotes.md) state that this version change needs no database migration. Configuration, `.env`, UI file, and data remain in place; the backend binary is replaced. A rehearsal on a separate test copy is part of preparation for a production update.

### Prepare the release separately

The following commands run as root. `BACKEND_DIR`, service account, and `PREP` must match the installation; `PREP` is a new directory outside the running installation. The existing binary must report version 1.5.3 before the update.

```bash
set -eu
BACKEND_DIR=/opt/monitoring/cc-backend
PREP=/opt/monitoring/prepare-1.5.4
"$BACKEND_DIR/cc-backend" -version
test ! -e "$PREP" && test ! -L "$PREP"
install -d -o root -g clustercockpit -m 0750 "$PREP"
cd "$PREP"
curl --fail --location --max-time 120 -o backend.tar.gz \
  https://github.com/ClusterCockpit/cc-backend/releases/download/v1.5.4/cc-backend_Linux_x86_64.tar.gz
printf '%s  backend.tar.gz\n' ecfba842a1882ccb4285e8f274029ef4afcc7442417e00aafe0a204fc734f698 | sha256sum -c -
mkdir release
tar -xzf backend.tar.gz -C release
test -x release/cc-backend
./release/cc-backend -version
```

The new binary must report 1.5.4. This checksum applies to the linked Linux-x86_64 release. A different build needs its own verified source.

### Maintenance window and backup

The complete [backup and recovery procedure](backup_restore.md) precedes replacement: new job starts are suspended, running jobs finish and are archived, all writers stop, and the backend stops last. The inventory must include the binary, data, configuration, and keys. Replacement follows only after a successful restore test.

The backup checks already verify schema 11 and archive format 3. This update does not need `-init-db`, `-migrate-db`, or the archive migration tool. A different schema or archive format needs another migration plan.

### Replace the binary and verify

The backend remains stopped after the successful backup. The prepared binary replaces the installed one; release examples do not replace existing configuration or data.

```bash
set -eu
BACKEND_DIR=/opt/monitoring/cc-backend
PREP=/opt/monitoring/prepare-1.5.4
install -o root -g root -m 0755 "$PREP/release/cc-backend" "$BACKEND_DIR/cc-backend"
"$BACKEND_DIR/cc-backend" -version
systemctl start clustercockpit.service
systemctl status clustercockpit.service
journalctl -u clustercockpit.service -n 100 --no-pager
```

Acceptance checks cover login, roles and project assignments, and representative old jobs with known measurements. The saved database/archive snapshot also supports comparison with the migration checker. Collectors and scheduler integration resume only after these checks, followed by a complete [test job](first_job.md). Regular job starts can then resume.

A failure keeps new job starts suspended. The [recovery procedure](backup_restore.md#recover-the-saved-state) restores the complete saved state. Data received since the backup needs separate handling. Checkpoint and historical-backfill persistence limits still apply after the update.
