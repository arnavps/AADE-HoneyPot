#!/bin/bash
# Honeywall Setup Script
# Assumes eth0 = external, virbr0 / tap0 = honeypot 

EXT_IF="eth0"
HONEY_SUBNET="192.168.100.0/24"
HONEY_IF="tap0"

# Flush old rules
iptables -F
iptables -t nat -F

# Default Policies
iptables -P FORWARD DROP

# Allow ESTABLISHED/RELATED return traffic
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow inbound traffic to honeypot subnet
iptables -A FORWARD -i $EXT_IF -o $HONEY_IF -d $HONEY_SUBNET -j ACCEPT

# Log all outbound attempts from honeypots
iptables -A FORWARD -i $HONEY_IF -s $HONEY_SUBNET -j LOG --log-prefix "[HONEYPOT-OUTBOUND] "

# BLOCK all outbound from honeypots internet
iptables -A FORWARD -i $HONEY_IF -s $HONEY_SUBNET -o $EXT_IF -j DROP

# Redirect DNS (53) to local sinkhole (5353)
iptables -t nat -A PREROUTING -i $HONEY_IF -p udp --dport 53 -j REDIRECT --to-port 5353
iptables -t nat -A PREROUTING -i $HONEY_IF -p tcp --dport 53 -j REDIRECT --to-port 5353

# Redirect HTTP (80) to mitmproxy (8080)
iptables -t nat -A PREROUTING -i $HONEY_IF -p tcp --dport 80 -j REDIRECT --to-port 8080

# Redirect HTTPS (443) to mitmproxy (8443)
iptables -t nat -A PREROUTING -i $HONEY_IF -p tcp --dport 443 -j REDIRECT --to-port 8443

echo "[*] Honeywall deployed."
