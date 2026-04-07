# AADE — Autonomous Adaptive Deception Environment

This next-generation adaptive honeypot system relies heavily on features exclusive to Linux environments, primarily KVM virtualisation, Linux AF_VSOCK (port 40) out-of-band communication, and iptables network manipulation.

All the backend code for the framework has been generated here. 

## Moving to Kali Linux (or any Linux Host)
Move this entire directory (`aade`) over to your Kali Linux host (either bare-metal or VMware with Nested Virtualisation enabled).

### 1. Execute the Master Installer
Run the master installation script to install all dependencies, download tools, and prepare firecracker and cowrie instances.
```bash
chmod +x master_install.sh
./master_install.sh
```

### 2. Generate the Gold Image (Phase 2)
Generate a rootfs filled with fake data that tricks the attacker into believing it's a real machine.
```bash
# Assuming you mounted an ext4 filesystem to /mnt/gold
sudo python3 generate_noise.py
```

### 3. Setup Honeywall (Phase 4)
This prevents malware and attacks launched inside the honeypot from escaping into the real network.
```bash
sudo chmod +x honeywall_setup.sh
sudo ./honeywall_setup.sh
```

### 4. Running the System
Once everything is downloaded and the gold image is built and sealed, you can launch the ecosystem in separate terminals:

**Terminal 1:** Start the vsock listener (Needs to run before Firecracker so the MicroVM can connect on boot)
```bash
python3 vsock_listener.py
```

**Terminal 2:** Start the C2 mitmproxy sinkhole
```bash
mitmproxy -p 8080 -s c2_sinkhole.py --ssl-insecure
```

**Terminal 3:** Launch the Cowrie honeypot (from `~/aade/cowrie` directory created by installer)
```bash
cd ~/aade/cowrie
bin/cowrie start
```

**Terminal 4:** Launch the Dashboard
```bash
python3 dashboard.py
# Dashboard will be available at http://localhost:5000
```

**Terminal 5:** Launch the Orchestrator
```bash
python3 orchestrator.py
```

- When the attacker connects to `Cowrie` and executes a suspicious command, the **Orchestrator** triggers the live-migration from Cowrie into an active Firecracker MicroVM.
- Any actions inside the MicroVM are piped out to the host via **AF_VSOCK**.
- The **Dashboard** actively polls the `.jsonl` logs to show you what's happening live using MITRE ATT&CK mappings.
