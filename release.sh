#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
REMOTE_USER="debian"
REMOTE_HOST="51.195.119.32"
REMOTE_PORT="21021"
REMOTE_PATH="/home/debian/apps/rent-scraper"
SERVICE_NAME="kv-monitor"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TAR_FILE="rent-scraper-${TIMESTAMP}.tar.gz"

cd "$SCRIPT_DIR"

echo "=== Rental Monitor Release ==="
echo "Pack -> Upload -> Deploy & Restart"
echo ""

# 1. Pack
echo "[1/3] Packing..."
tar -czf "$TAR_FILE" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='venv' \
    --exclude='data' \
    --exclude='logs' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='*.pyc' \
    scraper.py city24_scraper.py database.py monitor.py service.py config.py \
    requirements.txt install-service.sh kv-monitor.service

echo "  -> ${TAR_FILE}"

# 2. Upload
echo "[2/3] Uploading..."
scp -P "$REMOTE_PORT" "$TAR_FILE" "${REMOTE_USER}@${REMOTE_HOST}:/tmp/"
echo "  -> Uploaded"

# 3. Deploy on remote
echo "[3/3] Deploying..."
ssh -p "$REMOTE_PORT" "${REMOTE_USER}@${REMOTE_HOST}" <<EOF
set -e
cd ${REMOTE_PATH}
sudo systemctl stop ${SERVICE_NAME} 2>/dev/null || true

# Backup current to /tmp (not inside the deployment dir)
TIMESTAMP=\$(date +%Y%m%d-%H%M%S)
sudo tar -czf /tmp/backup-\${TIMESTAMP}.tar.gz -C ${REMOTE_PATH} --exclude='backup*' --exclude='*.tar.gz' --exclude='data' --exclude='logs' --exclude='__pycache__' --exclude='venv' . 2>/dev/null || true
# Clean up old backups (keep last 3)
sudo ls -t /tmp/backup-*.tar.gz 2>/dev/null | tail -n +4 | xargs sudo rm -f 2>/dev/null || true

# Extract new files
cd ${REMOTE_PATH}
tar -xzf /tmp/${TAR_FILE}

# Update systemd service file
sudo cp ${REMOTE_PATH}/kv-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start
sudo systemctl start ${SERVICE_NAME}

# Verify
if sudo systemctl is-active ${SERVICE_NAME} >/dev/null 2>&1; then
    echo "  ✓ ${SERVICE_NAME} is running"
else
    echo "  ✗ ${SERVICE_NAME} is NOT running"
fi
sudo journalctl -u ${SERVICE_NAME} --no-pager -n 5
EOF

rm -f "$TAR_FILE"
echo ""
echo "=== Done ==="
