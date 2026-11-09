#!/bin/bash
# Fresh installation only. See docs/monitoringserver.en.md for the manual path.
set +x
set -euo pipefail
umask 077
usage() {
    cat <<'HELP'
Usage: cc-installation.sh -c CLUSTER [-d DIRECTORY] [-u USER[:GROUP]] [-v VERSION]
  -c  Cluster: [A-Za-z0-9][A-Za-z0-9_-]{0,63}
  -d  New absolute directory, default /opt/monitoring; existing targets rejected
  -u  Existing service account, default clustercockpit:clustercockpit
  -v  Pinned backend release; default is backend.default in versions.json
  -h  Show help
Run as root on Linux x86_64. Dependencies: bash, python3 >= 3.9, curl,
openssl, coreutils (install/id/uname/chown/chmod/mkdir/rm/dirname), getent.
Directory components: letters, digits, underscore, hyphen and dot; no '.'/'..',
symlinks, spaces, shell metacharacters or systemd specifiers. Parent must exist
and be root-owned without group/other write access. No update/resume mode.
HELP
}
INSTALL_DIR=/opt/monitoring
CLUSTER_NAME=
CC_USER=clustercockpit
CC_GROUP=clustercockpit
VERSION=
while getopts ':c:d:u:v:h' option; do
    case "$option" in
        c) CLUSTER_NAME=$OPTARG ;;
        d) INSTALL_DIR=$OPTARG ;;
        u) CC_USER=${OPTARG%%:*}; CC_GROUP=${OPTARG#*:} ;;
        v) VERSION=$OPTARG ;;
        h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
shift "$((OPTIND - 1))"
if (( $# )); then usage >&2; exit 2; fi
for command in python3 curl openssl install id uname chown chmod mkdir rm dirname getent; do
    command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
HELPER="$SCRIPT_DIR/install_support.py"
GUIDE_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
if [[ -z $VERSION ]]; then VERSION=$(python3 "$HELPER" default-version "$GUIDE_DIR"); fi
# Read-only, including templates and every existing path component.
python3 "$HELPER" preflight "$GUIDE_DIR" "$INSTALL_DIR" "$CLUSTER_NAME" "$CC_USER" "$CC_GROUP" "$VERSION"
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
    echo 'Only Linux x86_64 release assets are supported.' >&2; exit 1
fi
# No -p: exclusively reserve the target against concurrent starts.
mkdir -m 0700 -- "$INSTALL_DIR"
trap 'echo "Installation interrupted. Private partial state retained at $INSTALL_DIR; inspect it before choosing a new empty target." >&2' ERR
trap 'echo "Installation interrupted; private partial state retained." >&2; exit 130' INT
trap 'echo "Installation interrupted; private partial state retained." >&2; exit 143' TERM
install -d -m 0700 "$INSTALL_DIR/.install-tmp" "$INSTALL_DIR/cc-backend"
TEMP_DIR="$INSTALL_DIR/.install-tmp"
echo "Downloading pinned cc-backend $VERSION..."
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 120 --retry 2 \
    "https://api.github.com/repos/ClusterCockpit/cc-backend/releases/tags/v$VERSION" > "$TEMP_DIR/release.json"
URL=$(python3 "$HELPER" release-url "$GUIDE_DIR" "$VERSION" "$TEMP_DIR/release.json")
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 300 --retry 2 "$URL" > "$TEMP_DIR/backend.tar.gz"
python3 "$HELPER" extract "$GUIDE_DIR" "$VERSION" "$TEMP_DIR/backend.tar.gz" "$INSTALL_DIR/cc-backend"
python3 "$HELPER" render "$GUIDE_DIR" "$INSTALL_DIR" "$CLUSTER_NAME" "$CC_USER" "$CC_GROUP"
cd "$INSTALL_DIR/cc-backend"
./gen-keypair > "$TEMP_DIR/keypair.txt"
python3 "$HELPER" environment "$TEMP_DIR/keypair.txt" .env
rm -- "$TEMP_DIR/keypair.txt"
# -init would overwrite custom configuration with upstream example credentials.
# Create a fresh DB; render supplied the format marker for the NEW empty archive.
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
python3 "$HELPER" finish "$INSTALL_DIR" "$CC_USER" "$CC_GROUP"
trap - ERR INT TERM
echo "Installed cc-backend $VERSION; database and two users created. No service started."
echo "Private credentials: $INSTALL_DIR/cc-backend/{admin_password.txt,apiuser_password.txt,apikey.txt}"
echo "Unit: $INSTALL_DIR/clustercockpit.service. Inspect configuration, then install the unit as documented."
