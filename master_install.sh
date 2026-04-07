#!/bin/bash
# AADE Master Installation Script v1.1
# Consolidated Environment Setup for Kali Linux
set -e

echo "[*] AADE: Starting master installation..."

# 1. System Packages (APT)
echo "[+] Installing core system dependencies..."
sudo apt update && sudo apt install -y \
  qemu-kvm libvirt-daemon-system virtinst bridge-utils cpu-checker \
  dnsmasq iptables-persistent tcpdump wireshark tshark debootstrap \
  python3-pip python3-venv git curl wget jq net-tools iproute2 \
  e2fsprogs squashfs-tools

# 2. Directory Structure
echo "[+] Initializing project directory structure..."
mkdir -p ~/aade/logs
mkdir -p ~/aade/kernels
mkdir -p ~/aade/images
mkdir -p ~/aade/cowrie

# 3. Python Environment & Core Dependencies
echo "[+] Installing unified Python dependencies..."
# Using --break-system-packages for Kali/Debian environments if not using venv
pip3 install --user --break-system-packages \
  faker selenium pyautogui scapy twisted paramiko psutil watchdog \
  mitmproxy requests flask flask-socketio tailer \
  elasticsearch mitreattack-python numpy pandas pyyaml

# 4. [ADVANCED] AI & RL Dependencies
echo "[+] Installing advanced AI/ML components (RL & LLM)..."
pip3 install --user --break-system-packages \
  openai stable-baselines3[extra] gymnasium[all] torch

# 5. Firecracker & Jailer Binaries
echo "[+] Downloading Firecracker v1.7.0..."
RELEASE=v1.7.0; ARCH=$(uname -m)
if [ ! -f "/usr/local/bin/firecracker" ]; then
    curl -LO https://github.com/firecracker-microvm/firecracker/releases/download/${RELEASE}/firecracker-${RELEASE}-${ARCH}.tgz
    tar -xzf firecracker-${RELEASE}-${ARCH}.tgz
    sudo mv release-${RELEASE}-${ARCH}/firecracker-${RELEASE}-${ARCH} /usr/local/bin/firecracker
    sudo mv release-${RELEASE}-${ARCH}/jailer-${RELEASE}-${ARCH} /usr/local/bin/jailer
    sudo chmod +x /usr/local/bin/firecracker /usr/local/bin/jailer
    rm firecracker-${RELEASE}-${ARCH}.tgz
    rm -rf release-${RELEASE}-${ARCH}
fi

# 6. Cowrie Honeypot Setup
if [ ! -d "~/aade/cowrie/.git" ]; then
    echo "[+] Cloning Cowrie honeypot..."
    git clone https://github.com/cowrie/cowrie ~/aade/cowrie
    cd ~/aade/cowrie
    python3 -m venv cowrie-env
    source cowrie-env/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -e .
    cp etc/cowrie.cfg.dist etc/cowrie.cfg
    cd ~-
fi

# 7. Default Kernel for MicroVMs
if [ ! -f "~/aade/kernels/vmlinux.bin" ]; then
    echo "[+] Fetching Firecracker default kernel..."
    curl -fsSL https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/x86_64/kernels/vmlinux.bin \
      -o ~/aade/kernels/vmlinux.bin
fi

echo ""
echo "[✓] AADE Environment setup complete."
echo "[!] IMPORTANT: Log out and log back in to ensure shell groups (kvm, libvirt) take effect."
echo "[!] Use 'python3 orchestrator.py' to launch the system on your Kali host."
