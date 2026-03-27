#!/bin/bash

# --- Color formatting ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[*] Starting Behavioral Anomaly Scan...${NC}"
echo "--------------------------------------------------"

# 1. Hunt for "Orphaned" Python Processes
# Legitimate system services (like firewalld or tuned) usually have a Parent Process ID (PPID) 
# of 1 (systemd). If a Python script is running with a strange PPID or no controlling tty, 
# it's a major red flag.
echo -e "${YELLOW}[1] Hunting for orphaned/background Python processes...${NC}"
ORPHANS=$(ps -ef | grep python | awk '$3 != 1 && $6 == "?"' | grep -v "grep")
if [ -n "$ORPHANS" ]; then
    echo -e "${RED}[!] Found Python processes running without a terminal or systemd parent:${NC}"
    echo "$ORPHANS"
else
    echo -e "${GREEN}[+] No suspicious orphaned Python processes found.${NC}"
fi

# 2. Keyword-Based Detection (The "Smoking Gun" Hunter)
# Searches for obvious red-flag words in the process list and service names.
echo -e "\n${YELLOW}[2] Scanning for high-risk keywords (backdoor, shell, c2)...${NC}"
KEYWORDS="backdoor|shell|c2|payload|exploit|nc -e|reverse"
SMOKING_GUN=$(ps -ef | grep -Ei "$KEYWORDS" | grep -v "grep" | grep -v "detector.sh")

if [ -n "$SMOKING_GUN" ]; then
    echo -e "${RED}[!] ALERT: Found processes containing high-risk keywords!${NC}"
    echo "$SMOKING_GUN"
else
    echo -e "${GREEN}[+] No obvious 'smoking gun' keywords found in active processes.${NC}"
fi


# 3. Identify Disguised Processes (The "ctypes" hunter)
# This compares the 'comm' (internal name) with the actual command line 'args'.
# If 'comm' is 'kworker' but 'args' contains 'python', someone is lying.
echo -e "\n${YELLOW}[3] Detecting process name mismatches (Spoofing)...${NC}"
ps -e -o pid,comm,args | grep -v "grep" | while read -r line; do
    PID=$(echo $line | awk '{print $1}')
    COMM=$(echo $line | awk '{print $2}')
    ARGS=$(echo $line | awk '{$1=$2=""; print $0}')
    
    # If the name looks like a kernel thread but the binary is python
    if [[ "$COMM" == *"kworker"* ]] && [[ "$ARGS" == *"python"* ]]; then
        echo -e "${RED}[!] ALERT: Process $PID is claiming to be '$COMM' but is actually running Python!${NC}"
        echo "    Full Command: $ARGS"
    fi
done

# 4. Hidden Network Sockets
# Instead of looking for port 4444, we look for ANY established connection 
# from a process that doesn't usually talk to the internet.
echo -e "\n${YELLOW}[4] Scanning for unusual outbound network sockets...${NC}"
# Looking for ESTABLISHED connections from Python
NET_ANOMALY=$(ss -tpue | grep "python")
if [ -n "$NET_ANOMALY" ]; then
    echo -e "${RED}[!] Found active network connections from Python:${NC}"
    echo "$NET_ANOMALY"
else
    echo -e "${GREEN}[+] No unusual Python network activity detected.${NC}"
fi

echo "--------------------------------------------------"
echo -e "${YELLOW}[*] Scan Complete.${NC}"