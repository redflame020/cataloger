#!/bin/bash
# Sync catalog data to the Pi after deploying code via git.
# Usage: ./sync-data.sh <pi-host>
# Example: ./sync-data.sh pi@raspberrypi.local

set -e
if [ $# -lt 1 ]; then
  echo "Usage: $0 <pi-host>"
  echo "Example: $0 pi@raspberrypi.local"
  exit 1
fi

PI_HOST="$1"
REMOTE_DIR="/home/pi/cataloger"

echo "=== Syncing catalog data to $PI_HOST ==="
echo ""

# Sync data directory (crops, catalog.json, rooms.json)
rsync -avz --progress data/ "$PI_HOST:$REMOTE_DIR/data/"

echo ""
echo "=== Done! ==="
echo "Restart the Pi server: ssh $PI_HOST sudo systemctl restart cataloger"
