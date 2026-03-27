#!/bin/bash

# === CONFIG ===
SERVICE_NAME="monitor-cpu"
INSTALL_PATH="/usr/libexec/tuned"
CONFIG_PATH="/usr/lib/tuned"
SERVICE_PATH="/etc/systemd/system"

echo "[+] Uninstalling backdoor service..."

# === Stop service ===
echo "[+] Stopping service..."
sudo systemctl stop $SERVICE_NAME.service 2>/dev/null

# === Disable service ===
echo "[+] Disabling service..."
sudo systemctl disable $SERVICE_NAME.service 2>/dev/null

# === Remove service file ===
echo "[+] Removing service file..."
sudo rm -f $SERVICE_PATH/$SERVICE_NAME.service

# === Remove cron persistence ===
echo "[+] Removing backup cron job..."
sudo rm -f /etc/cron.d/tuned-monitor

# === Reload systemd ===
echo "[+] Reloading systemd..."
sudo systemctl daemon-reload

# === Remove agent ===
echo "[+] Removing agent..."
sudo rm -f $INSTALL_PATH/$SERVICE_NAME

# === Remove config ===
echo "[+] Removing config..."
sudo rm -f $CONFIG_PATH/config.json

echo "[+] Uninstallation complete!"