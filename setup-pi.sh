#!/bin/bash
set -e

echo "=== Cataloger: Raspberry Pi Setup ==="
echo ""

# System dependencies
echo "[1/5] Installing system packages..."
sudo apt update
sudo apt install -y tesseract-ocr libzbar0 git

# Micromamba
echo "[2/5] Setting up micromamba..."
if ! command -v micromamba &> /dev/null; then
  echo "Installing micromamba..."
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xvj bin/micromamba
  sudo mv bin/micromamba /usr/local/bin/
  rmdir bin 2>/dev/null || true
fi

# Python environment
echo "[3/5] Creating Python environment..."
micromamba create -n cataloger -c conda-forge -y \
  python=3.13 opencv pytesseract fastapi uvicorn pyzbar pillow requests numpy

# Project files
cd "$(dirname "$0")"

# SSL certificate
echo "[4/5] Generating self-signed SSL certificate..."
mkdir -p ssl
openssl req -x509 -newkey rsa:2048 -keyout ssl/key.pem \
  -out ssl/cert.pem -days 365 -nodes -subj "/CN=cataloger"

# Create data directories
mkdir -p data/crops data/uploads

# Install systemd service
echo "[5/5] Installing systemd service..."
SERVICE_DIR="$(pwd)"
MICROMAMBA_PATH="$(which micromamba)"

cat > /tmp/cataloger.service << EOF
[Unit]
Description=Cataloger
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SERVICE_DIR
ExecStart=$MICROMAMBA_PATH run -n cataloger python3 $SERVICE_DIR/run_server.py --ssl
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/cataloger.service /etc/systemd/system/cataloger.service
sudo systemctl daemon-reload
sudo systemctl enable cataloger
sudo systemctl start cataloger

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Server: https://$(hostname -I | awk '{print $1}'):8443"
echo ""
echo "To check status: sudo systemctl status cataloger"
echo "To view logs:    sudo journalctl -u cataloger -f"
