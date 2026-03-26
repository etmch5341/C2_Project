#!/bin/bash

CRON_MARKER="# system-helper-cron"

echo "[+] Removing cron persistence..."

# Remove only our job
crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab -

echo "[+] Cron job removed!"

# Show remaining crontab
echo "[+] Current crontab:"
crontab -l