#!/bin/bash

# --- Color formatting for readability ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[*] Starting C2 Backdoor Detection Scan...${NC}"
echo "--------------------------------------------------"

# 1. Check for suspicious Systemd services
echo -e "${YELLOW}[1] Checking for suspicious Systemd services...${NC}"
# Look for services running from /usr/libexec/ (a common hiding spot)
SUSPICIOUS_SVC=$(systemctl list-units --type=service --all | grep -E "monitor|tuned|backdoor")
if [ -n "$SUSPICIOUS_SVC" ]; then
    echo -e "${RED}[!] Found suspicious service(s):${NC}"
    echo "$SUSPICIOUS_SVC"
else
    echo -e "${GREEN}[+] No obvious suspicious services found.${NC}"
fi

# 2. Check for Process Name Spoofing
echo -e "\n${YELLOW}[2] Checking for Python scripts masquerading as Kernel Threads...${NC}"
# This looks for processes named 'kworker' that are actually running via the Python interpreter
SPOOFED_PROC=$(ps -ef | grep -i "python" | grep -E "kworker|syslogd|dbus")
if [ -n "$SPOOFED_PROC" ]; then
    echo -e "${RED}[!] ALERT: Found Python process masquerading as a system thread!${NC}"
    echo "$SPOOFED_PROC"
else
    echo -e "${GREEN}[+] No spoofed Python processes detected.${NC}"
fi

# 3. Check for Network Beaconing (Persistent Connections)
echo -e "\n${YELLOW}[3] Checking for active connections to suspicious ports...${NC}"
# Look for anything connected to your C2 port (4444)
BEACON=$(netstat -antp 2>/dev/null | grep ":4444")
if [ -n "$BEACON" ]; then
    echo -e "${RED}[!] ALERT: Active connection to C2 port 4444 detected!${NC}"
    echo "$BEACON"
else
    echo -e "${GREEN}[+] No active C2 network beacons found.${NC}"
fi

echo "--------------------------------------------------"
echo -e "${YELLOW}[*] Scan Complete.${NC}"