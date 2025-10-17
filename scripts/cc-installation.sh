#!/bin/bash

# Setup script for ClusterCockpit with cc-backend and cc-metric-store

# Exit on any error
set -euo pipefail

# Function to check for required commands
check_dependencies() {
    local missing_deps=()
    local required_commands=(
        openssl curl wget tar getent awk
    )

    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo "Error: The following required commands are not installed or not in your PATH:"
        printf ' - %s\n' "${missing_deps[@]}"
        echo "Please install them and try again."
        exit 1
    fi
}

# Run dependency check
check_dependencies

# Get the directory where the script is located
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Default installation directory
INSTALL_DIR="/opt/monitoring"
CLUSTER_NAME=""
SESSION_KEY=$(openssl rand -base64 32)
ADMIN_USER="admin"
ADMIN_PASS=$(openssl rand -base64 18)
API_USER="apiuser"
API_PASS=$(openssl rand -base64 18)
CC_USER="clustercockpit"
CC_GROUP="clustercockpit"

# Function to display usage
usage() {
    echo "Usage: $0 -c <cluster_name> [-d <install_dir>] [-u <user:group>]"
    echo "  -c  Cluster name (required)"
    echo "  -d  Installation directory (default: /opt/monitoring)"
    echo "  -u  User and group for the services (default: clustercockpit:clustercockpit)"
    exit 1
}

# Function to check if directory is non-empty
check_dir_non_empty() {
    local dir=$1
    if [ -d "$dir" ] && [ -n "$(ls -A "$dir")" ]; then
        return 0
    else
        echo "Error: Directory $dir is empty or does not exist"
        ls -l "$dir" 2>/dev/null || echo "Directory does not exist"
        exit 1
    fi
}

# Parse command line arguments
while getopts "c:d:u:" opt; do
    case $opt in
        c) CLUSTER_NAME="$OPTARG" ;;
        d) INSTALL_DIR="$OPTARG" ;;
        u)
            if [[ "$OPTARG" == *":"* ]]; then
                CC_USER=$(echo "$OPTARG" | cut -d':' -f1)
                CC_GROUP=$(echo "$OPTARG" | cut -d':' -f2)
            else
                CC_USER="$OPTARG"
                CC_GROUP="$OPTARG"
            fi
            ;;
        *) usage ;;
    esac
done

# Check if cluster name is provided
if [ -z "$CLUSTER_NAME" ]; then
    echo "Error: Cluster name is required"
    usage
fi

# Check if user and group exist
if ! id -u "$CC_USER" >/dev/null 2>&1; then
    echo "Error: User '$CC_USER' not found. Please create it first."
    exit 1
fi

if ! getent group "$CC_GROUP" >/dev/null 2>&1; then
    echo "Error: Group '$CC_GROUP' not found. Please create it first."
    exit 1
fi

# Create installation directory and subdirectories
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
mkdir -p cc-backend
mkdir -p cc-metric-store

# Define the actual base path for metric store data using the chosen INSTALL_DIR
METRIC_STORE_DATA_BASE_DIR="$INSTALL_DIR/cc-metric-store"


# Function to get the latest release URL from GitHub
get_latest_release() {
    local repo=$1
    local asset_pattern=$2
    local url
    url=$(curl -s https://api.github.com/repos/ClusterCockpit/$repo/releases/latest | \
        grep "browser_download_url.*$asset_pattern" | \
        cut -d '"' -f 4)
    if [ -z "$url" ]; then
        echo "Error: Could not find latest release for $repo with pattern $asset_pattern"
        exit 1
    fi
    echo "$url"
}

# Download and extract cc-backend
echo "Downloading cc-backend..."
CC_BACKEND_URL=$(get_latest_release "cc-backend" "cc-backend_Linux_x86_64.tar.gz")
wget --progress=dot:giga -O cc-backend.tar.gz "$CC_BACKEND_URL"
if [ ! -s cc-backend.tar.gz ]; then
    echo "Error: Downloaded cc-backend.tar.gz is empty or invalid"
    exit 1
fi
mkdir -p cc-backend-tmp
echo "Extracting cc-backend..."
tar -xzf cc-backend.tar.gz -C cc-backend-tmp
mv cc-backend-tmp/* cc-backend/ 2>/dev/null || mv cc-backend-tmp/cc-backend*/* cc-backend/ 2>/dev/null || true
rm -rf cc-backend-tmp cc-backend.tar.gz
check_dir_non_empty cc-backend
echo "cc-backend directory contents:"
ls -l cc-backend
echo "cc-backend extracted successfully"

# Download and extract cc-metric-store
echo "Downloading cc-metric-store..."
CC_METRIC_STORE_URL=$(get_latest_release "cc-metric-store" "cc-metric-store_Linux_x86_64.tar.gz")
wget --progress=dot:giga -O cc-metric-store.tar.gz "$CC_METRIC_STORE_URL"
if [ ! -s cc-metric-store.tar.gz ]; then
    echo "Error: Downloaded cc-metric-store.tar.gz is empty or invalid"
    exit 1
fi
mkdir -p cc-metric-store-tmp
echo "Extracting cc-metric-store..."
tar -xzf cc-metric-store.tar.gz -C cc-metric-store-tmp
mv cc-metric-store-tmp/* cc-metric-store/ 2>/dev/null || mv cc-metric-store-tmp/cc-metric-store*/* cc-metric-store/ 2>/dev/null || true
rm -rf cc-metric-store-tmp cc-metric-store.tar.gz
check_dir_non_empty cc-metric-store
echo "cc-metric-store directory contents:"
ls -l cc-metric-store
echo "cc-metric-store extracted successfully"

# Create job archive directory for cluster.json
mkdir -p "cc-backend/var/job-archive/$CLUSTER_NAME" # This is relative to $INSTALL_DIR

# Generate JWT keypair
echo "Generating JWT keypair..."
pushd "$INSTALL_DIR/cc-backend"
if [ ! -f ./gen-keypair ]; then
    echo "Error: gen_keypair binary not found in cc-backend directory ($PWD)"
    ls -l
    exit 1
fi
chmod +x ./gen-keypair
./gen-keypair >keypair.txt
if [ ! -f keypair.txt ]; then
    echo "Error: keypair.txt not generated by gen-keypair in $PWD"
    exit 1
fi
JWT_PUBLIC_KEY=$(grep "ED25519 PUBLIC_KEY" keypair.txt | cut -d '"' -f 2)
JWT_PRIVATE_KEY=$(grep "ED25519 PRIVATE_KEY" keypair.txt | cut -d '"' -f 2)
if [ -z "$JWT_PUBLIC_KEY" ] || [ -z "$JWT_PRIVATE_KEY" ]; then
    echo "Error: Could not extract JWT keys from keypair.txt"
    cat keypair.txt
    exit 1
fi
rm keypair.txt

# Create cc-backend config.json from template
echo "Creating cc-backend config.json from template..."
BACKEND_CONFIG_TEMPLATE_FILE="$SCRIPT_DIR/templates/cc-backend.json.template"
BACKEND_CONFIG_FILE="./config.json" 

if [ ! -f "$BACKEND_CONFIG_TEMPLATE_FILE" ]; then
    echo "Error: Template file '$BACKEND_CONFIG_TEMPLATE_FILE' not found!"
    echo "SCRIPT_DIR is '$SCRIPT_DIR'. Please ensure 'templates/cc-backend.json.template' exists relative to SCRIPT_DIR."
    exit 1
fi
cp "$BACKEND_CONFIG_TEMPLATE_FILE" "$BACKEND_CONFIG_FILE"
sed -i "s/__CLUSTER_NAME__/$CLUSTER_NAME/g" "$BACKEND_CONFIG_FILE"

# Create cluster.json from template
echo "Creating cluster.json from template..."
CLUSTER_JSON_TEMPLATE_FILE="$SCRIPT_DIR/templates/cluster.json.template"
CLUSTER_JSON_FILE="./var/job-archive/$CLUSTER_NAME/cluster.json" 

if [ ! -f "$CLUSTER_JSON_TEMPLATE_FILE" ]; then
    echo "Error: Template file '$CLUSTER_JSON_TEMPLATE_FILE' not found!"
    echo "SCRIPT_DIR is '$SCRIPT_DIR'. Please ensure 'templates/cluster.json.template' exists relative to SCRIPT_DIR."
    exit 1
fi
cp "$CLUSTER_JSON_TEMPLATE_FILE" "$CLUSTER_JSON_FILE"
sed -i "s/__CLUSTER_NAME__/$CLUSTER_NAME/g" "$CLUSTER_JSON_FILE"

# Create cc-metric-store config.json from template
echo "Creating cc-metric-store config.json from template..."
METRIC_STORE_CONFIG_TEMPLATE_FILE="$SCRIPT_DIR/templates/cc-metric-store.config.json.template"
METRIC_STORE_CONFIG_FILE="../cc-metric-store/config.json" 

if [ ! -f "$METRIC_STORE_CONFIG_TEMPLATE_FILE" ]; then
    echo "Error: Template file '$METRIC_STORE_CONFIG_TEMPLATE_FILE' not found!"
    echo "SCRIPT_DIR is '$SCRIPT_DIR'. Please ensure 'templates/cc-metric-store.config.json.template' exists relative to SCRIPT_DIR."
    exit 1
fi
cp "$METRIC_STORE_CONFIG_TEMPLATE_FILE" "$METRIC_STORE_CONFIG_FILE"

ESCAPED_METRIC_STORE_DATA_BASE_DIR=$(printf '%s\n' "$METRIC_STORE_DATA_BASE_DIR" | sed 's:[&/\\]:\\&:g')
ESCAPED_JWT_PUBLIC_KEY=$(printf '%s\n' "$JWT_PUBLIC_KEY" | sed 's:[&@\\]:\\&:g')


sed -i "s@__METRIC_STORE_BASE_PATH__@$ESCAPED_METRIC_STORE_DATA_BASE_DIR@g" "$METRIC_STORE_CONFIG_FILE"
sed -i "s/__CLUSTER_NAME__/$CLUSTER_NAME/g" "$METRIC_STORE_CONFIG_FILE"
sed -i "s@__JWT_PUBLIC_KEY__@$ESCAPED_JWT_PUBLIC_KEY@g" "$METRIC_STORE_CONFIG_FILE"


# Set environment variables for cc-backend
cat > .env <<EOF
SESSION_KEY="$SESSION_KEY"
JWT_PRIVATE_KEY="$JWT_PRIVATE_KEY"
JWT_PUBLIC_KEY="$JWT_PUBLIC_KEY"
EOF

# Initialize database and add users
echo "Initializing cc-backend database..."
if [ ! -f ./cc-backend ]; then
    echo "Error: cc-backend binary not found in cc-backend directory ($PWD)"
    ls -l
    exit 1
fi
chmod +x ./cc-backend
./cc-backend -init
echo 2 > ./var/job-archive/version.txt 
./cc-backend -migrate-db
echo "Adding users..."
./cc-backend -add-user "$ADMIN_USER:admin:$ADMIN_PASS"
./cc-backend -add-user "$API_USER:api:$API_PASS"

# Generate API key and store full output in apikey.txt
echo "Generating API key..."
./cc-backend -jwt "$API_USER" | tee apikey.txt

API_KEY=$(awk -F': ' '/Successfully generated JWT/ {print $3}' apikey.txt)

if [[ -z "$API_KEY" ]]; then
  echo "Error: Failed to extract JWT token from apikey.txt"
  exit 1
fi

escaped_key=$(printf '%s\n' "$API_KEY" | sed 's:[&/\\]:\\&:g')

sed -i "s/__API_TOKEN__/$escaped_key/g" "$BACKEND_CONFIG_FILE" 

# Store passwords
echo "$ADMIN_PASS" > admin_password.txt 
echo "$API_PASS" > apiuser_password.txt 

popd # Back to $INSTALL_DIR

echo "Generating systemd service files..."

CC_BACKEND_SERVICE_TEMPLATE="$SCRIPT_DIR/templates/clustercockpit.service.template"
CC_BACKEND_SERVICE_FILE="$INSTALL_DIR/clustercockpit.service"

CC_METRIC_STORE_SERVICE_TEMPLATE="$SCRIPT_DIR/templates/cc-metric-store.service.template"
CC_METRIC_STORE_SERVICE_FILE="$INSTALL_DIR/cc-metric-store.service"

ESCAPED_INSTALL_DIR=$(printf '%s\n' "$INSTALL_DIR" | sed 's:[&/\\]:\\&:g') # Escape &, / and \

# generate clustercockpit.service
if [ -f "$CC_BACKEND_SERVICE_TEMPLATE" ]; then
    cp "$CC_BACKEND_SERVICE_TEMPLATE" "$CC_BACKEND_SERVICE_FILE"
    sed -i "s@__INSTALL_DIR__@$ESCAPED_INSTALL_DIR@g" "$CC_BACKEND_SERVICE_FILE"
    sed -i "s/__CC_USER__/$CC_USER/g" "$CC_BACKEND_SERVICE_FILE"
    sed -i "s/__CC_GROUP__/$CC_GROUP/g" "$CC_BACKEND_SERVICE_FILE"
    echo "Generated: $CC_BACKEND_SERVICE_FILE"
else
    echo "Warning: Template file '$CC_BACKEND_SERVICE_TEMPLATE' not found. Skipping clustercockpit.service generation."
fi

# generate cc-metric-store.service
if [ -f "$CC_METRIC_STORE_SERVICE_TEMPLATE" ]; then
    cp "$CC_METRIC_STORE_SERVICE_TEMPLATE" "$CC_METRIC_STORE_SERVICE_FILE"
    sed -i "s@__INSTALL_DIR__@$ESCAPED_INSTALL_DIR@g" "$CC_METRIC_STORE_SERVICE_FILE"
    sed -i "s/__CC_USER__/$CC_USER/g" "$CC_METRIC_STORE_SERVICE_FILE"
    sed -i "s/__CC_GROUP__/$CC_GROUP/g" "$CC_METRIC_STORE_SERVICE_FILE"
    echo "Generated: $CC_METRIC_STORE_SERVICE_FILE"
else
    echo "Warning: Template file '$CC_METRIC_STORE_SERVICE_TEMPLATE' not found. Skipping cc-metric-store.service generation."
fi

echo "Changing ownership of $INSTALL_DIR to $CC_USER:$CC_GROUP..."
chown -R "$CC_USER:$CC_GROUP" "$INSTALL_DIR"

echo ""
echo "Setup completed successfully!"
echo "Admin user: $ADMIN_USER, password stored in $INSTALL_DIR/cc-backend/admin_password.txt"
echo "API user: $API_USER, password stored in $INSTALL_DIR/cc-backend/apiuser_password.txt, JWT in $INSTALL_DIR/cc-backend/apikey.txt"
echo "Installation directory: $INSTALL_DIR"
echo "Services will run as user '$CC_USER' and group '$CC_GROUP'."
echo ""
echo "To start cc-backend: cd $INSTALL_DIR/cc-backend && ./cc-backend -server"
echo "To start cc-metric-store: cd $INSTALL_DIR/cc-metric-store && ./cc-metric-store"
echo ""
echo "--- systemd Service Setup (requires root privileges) ---"
echo "The following service files have been generated in '$INSTALL_DIR':"
echo "  - clustercockpit.service"
echo "  - cc-metric-store.service"
echo ""
echo "To install and enable them, run the following commands as root:"
echo "  sudo mv $INSTALL_DIR/clustercockpit.service /etc/systemd/system/"
echo "  sudo mv $INSTALL_DIR/cc-metric-store.service /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable clustercockpit.service"
echo "  systemctl enable cc-metric-store.service"
echo "  systemctl start clustercockpit.service"
echo "  systemctl start cc-metric-store.service"
echo ""
echo "To check their status:"
echo "  systemctl status clustercockpit.service"
echo "  systemctl status cc-metric-store.service"
echo "---------------------------------------------------------"
