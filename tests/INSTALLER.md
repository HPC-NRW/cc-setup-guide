# Installer regressions

The tests read the selected **working tree**, including uncommitted/new files.
They never use an existing ClusterCockpit installation. The work directory must
be new and outside the repository. Test failures return nonzero.

## Fast tests

Python 3.9+, Bash and the installer command dependencies (curl, OpenSSL, coreutils,
getent) are needed; no root, network, third-party Python modules or containers:

```bash
python3 tests/installer_unit.py --source "$PWD" --work /tmp/cc-installer-unit-unique
bash -n scripts/cc-installation.sh
shellcheck scripts/cc-installation.sh
```

Use a different work path for each invocation. The 34 checks cover dependency
failures, strict release JSON and asset selection, archive hashes/layout/link
rejection, and token extraction failures. They do not replace real authentication.

## Real Ubuntu userspace installation

`installer.py` requires Linux x86_64, Python3, bubblewrap, newuidmap/newgidmap and an
**already configured** subordinate UID/GID range of at least 65536 for the caller.
Do not change host accounts/mappings to work around a failure. The test creates
actual service/test users only inside the disposable rootfs and uses an isolated
network namespace. It does not boot systemd: unit-parser and actual service-user
backend/API checks are separate from systemd-manager integration.

Provide a fresh, disposable Ubuntu 24.04 rootfs containing Python3, curl, OpenSSL,
CA certificates and systemd. This rootfs is writable test input; never supply a
production rootfs or an installation to preserve. Release HTTP responses are
replayed from the supplied real archives; production SHA256 validation remains
active. A minimal reproducible bootstrap, run as your normal unprivileged user:

```bash
SOURCE=$(pwd -P)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/cc-installer.XXXXXX")
chmod 0700 "$WORK"
mkdir "$WORK/rootfs" "$WORK/downloads"
curl --fail --location --connect-timeout 15 --max-time 300 \
  https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.3-base-amd64.tar.gz \
  -o "$WORK/downloads/ubuntu-base.tar.gz"
printf '%s  %s\n' 6bc2cde3930ad088b3bb46fa45279e96d25bc3810f209850ecbe4722711874f9 \
  "$WORK/downloads/ubuntu-base.tar.gz" | sha256sum --check -
tar --no-same-owner -xzf "$WORK/downloads/ubuntu-base.tar.gz" -C "$WORK/rootfs"
python3 - "$WORK/rootfs" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for name in ('audit', 'proc', 'dev', 'run', 'tmp'):
    (root / name).mkdir(exist_ok=True)
resolver = root / 'etc/resolv.conf'
if resolver.is_symlink():
    resolver.unlink()
resolver.write_bytes(Path('/etc/resolv.conf').read_bytes())
policy = root / 'usr/sbin/policy-rc.d'
policy.write_text('#!/bin/sh\nexit 101\n')
policy.chmod(0o755)
PY
python3 tests/installer_namespace.py bwrap \
  --unshare-pid --unshare-uts --unshare-ipc --die-with-parent --new-session \
  --bind "$WORK/rootfs" / --proc /proc --dev /dev --clearenv \
  --setenv PATH /usr/sbin:/usr/bin:/sbin:/bin \
  --setenv DEBIAN_FRONTEND noninteractive --chdir / /bin/bash -c \
  'set -e; apt-get -o APT::Sandbox::User=root -o Acquire::Retries=0 -o Acquire::http::Timeout=20 update; apt-get -y -o APT::Sandbox::User=root --no-install-recommends install python3 curl openssl ca-certificates systemd'
for version in 1.5.3 1.5.4; do
  curl --fail --location --connect-timeout 15 --max-time 300 \
    "https://github.com/ClusterCockpit/cc-backend/releases/download/v$version/cc-backend_Linux_x86_64.tar.gz" \
    -o "$WORK/downloads/backend-v$version.tar.gz"
done
python3 tests/installer.py --source "$SOURCE" --work "$WORK/result" \
  --rootfs "$WORK/rootfs" \
  --archive153 "$WORK/downloads/backend-v1.5.3.tar.gz" \
  --archive154 "$WORK/downloads/backend-v1.5.4.tar.gz"
```

Only the APT bootstrap has network access inside the rootfs. `policy-rc.d` blocks
package service starts. All installed packages/accounts stay inside that rootfs;
no host `/etc`, system sockets or container storage are mounted there.

The integration cases exercise both releases, the default and alternative
paths, a separate service user/group, permissions under caller umask022, safe
reruns with byte hashes and DB sentinel/users, real JWT authentication and expiry,
manual commands extracted directly from both language documents, matching default
release selection in script and manual installation, missing/corrupt
templates and bad download/input/interrupt cases. Every service uses a dynamically
selected loopback port inside the namespace, and its owning namespace exits.

`result/results.json` and individual logs record the checks. **`result/export/`
contains private generated credentials/database state** for subsequent runtime
tests, marked `.guide-test-fixture`; keep the whole work directory private.
These are independent copies, with ownership normalized for the unprivileged
harness; this normalization is not a production installation recommendation.
Do not publish exports/rootfs with logs. The production API token file is always
`cc-backend/apikey.txt`, raw JWT, root-only mode0600; new tokens expire after8760h.

For an old source snapshot, select that read-only directory with `--source` and
add `--old-snapshot` in a separate fresh rootfs. The same read-denial assertion
should fail nonzero; this switch does not convert failure into success.

After saving required logs and stopping any additional runtime tests, optional
cleanup restores ownership only inside the generated rootfs before removing it:

```bash
python3 tests/installer_namespace.py bwrap \
  --unshare-pid --unshare-uts --unshare-ipc --unshare-net --die-with-parent --new-session \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
  --proc /proc --dev /dev --bind "$WORK/rootfs" /rootfs /bin/chown -R 0:0 /rootfs
rm -rf -- "$WORK"
```

The variable `WORK` above is created by mktemp for this test only. Do not replace
it with an existing deployment or a generic system directory.
