#!/bin/bash
# Sync catalog data from this Mac to the Pi (aryabhata.local).
# Usage: ./sync-data.sh

set -e
PI_HOST="aathreyak@aryabhata.local"
REMOTE_DIR="~/Documents/software/cataloger"
LOCAL_DATA="$(dirname "$0")/data"

echo "=== Syncing catalog data to Pi ==="
echo "From: $LOCAL_DATA"
echo "To:   $PI_HOST:$REMOTE_DIR/data/"
echo ""

# Pull latest code via git
echo "[1/3] Pulling latest code on Pi..."
ssh "$PI_HOST" "cd $REMOTE_DIR && git pull" || echo "Warning: git pull failed"

# Sync data directory
echo "[2/3] Syncing data..."
rsync -avz --progress "$LOCAL_DATA/" "$PI_HOST:$REMOTE_DIR/data/"

echo "[3/3] Restarting server..."
ssh "$PI_HOST" "sudo systemctl restart cataloger 2>/dev/null || echo '(cataloger service not installed yet — skipping)'" || true

echo ""
echo "=== Done! ==="
echo ""
echo "If the cataloger service is not installed on the Pi, run setup-pi.sh there first."
