# Operations regressions

All tests read the **current working tree**, including untracked helpers. They require a new explicit work directory and synthetic data only.
Never pass a production installation. Main entry points accept `--source`
and `--work`; no `/home/robert` path is embedded. Use a private TMPDIR and caches
on a filesystem with enough space before running builds.

## Sync compatibility, migration, backup and LDAP

Requirements: Python>=3.9, requests2.32.5, Git and GNU tar with
ACL/xattr support. Install Python dependencies in a disposable venv. Obtain:

- Official cc-backend1.4.4 Linux-x86_64 release, including adjacent gen-keypair;
  release tar SHA256 `f7c0bb056271d0c7599e1814763e8906968e6a4f6528994f3b6f4cdd0cafc3ef`.
- Backend1.5.3 and 1.5.4 releases from `versions.json`.
- archive-migration built from backend commit
  `300108664774c5561b6838382876e247d0b043b9`, as in the migration chapter.
- Read-only PC² cc-slurm-sync checkout at
  `4e700768d4ff63b9ce8e7cbd02d227e6a350c367`.

```sh
python3 tests/operations.py --source "$PWD" --work "$WORK/new-operations" \
  --sync-source "$DEPS/cc-slurm-sync" \
  --backend144 "$DEPS/backend144/cc-backend" \
  --backend153 "$DEPS/backend153/cc-backend" \
  --backend154 "$DEPS/backend154/cc-backend" \
  --migration-tool "$DEPS/archive-migration"
```

The sync check copies the pinned upstream source and rejects local tracked
changes. It applies no patch. The original Python job-start method and HTTP
client send a synthetic Slurm job to the official backend1.5.4 binary. The
expected result is HTTP400 with `unknown field "exclusive"`, with no job added.
This is a negative compatibility regression for the documented Slurm23.11
limit, not a supported installation path. Only Slurm command output is mocked;
no scheduler daemon is started. The test never alters the generated payload.

The migration uses genuine old/new binaries, three freshly authored archived
jobs, exact known series `[1,2,3]`, DB/archive versions and metadata/hash checks.
The current documented backup helper is also the test's backup/restore path:
no additional hidden full backup. Missing symlink targets, malformed/incomplete
checksums and dangling destinations must fail before output. Actual LDAP
configuration decoding covers both optional language snippets; the RUB example
uses local accounts and JWTs. No LDAP bind is claimed.

A failed assertion exits nonzero. `evidence/results.json` records checks;
artificial secrets remain in private work directories and never in output.
Loopback backend processes are stopped in `finally` blocks. JSON checkpoint
rounding and historical-backfill limits are not waived by these tests.

## Adapter

Requires Git, Go>=1.25.0 and a read-only adapter checkout at the commit in
`versions.json`. Source and build caches are copied/created under the new work
directory; `GOTOOLCHAIN=local` prevents an invisible toolchain update.

```sh
python3 tests/adapter_contract.py --source "$PWD" --work "$WORK/new-adapter" \
  --adapter-source "$DEPS/cc-slurm-adapter" --go /path/to/go1.25/bin/go
```

Build, vet, loading the current shared guide config (`slurmMaxRetries=5`) and
`-debug 5 -help` are executed. No scheduler or systemd manager is started.

## Reverse proxy

Requires bwrap, existing subordinate-UID/GID mappings, `newuidmap/newgidmap`
and an **independent disposable rootfs copy** containing nginx, OpenSSL and
Python. Bootstrap packages only inside that rootfs with service starts disabled.
Use the artificial target153 produced above, not an existing installation.

```sh
python3 tests/proxy_contract.py --source "$PWD" --work "$WORK/new-proxy" \
  --rootfs "$WORK/disposable-nginx-rootfs" \
  --backend-instance "$WORK/new-operations/target153" \
  --backend "$DEPS/backend153/cc-backend"
```

The test follows the shared configuration include in both current Markdown
chapters and applies each language's documented opt-in method expansion.
Certificate/name placeholders use a private self-signed fixture. Actual nginx
and backend run in a private network/PID/rootfs namespace. The restricted policy
forwards GET, POST and HEAD; PUT, PATCH, DELETE and OPTIONS must return403. The
opt-in policy forwards all seven methods with status matching direct backend
requests. Unauthorized API requests stay401 and TRACE is denied under both
policies. Security headers are checked on success, unauthorized and denied
responses, along with hidden server versions and HTTP-to-HTTPS redirection.
Mutation probes use invalid payloads or a nonexistent job; their direct backend
responses are compared with the proxy, without claiming a successful edit or
deletion. Unit startup,
privileged scheduler access and real Slurm/hardware remain deployment checks.
