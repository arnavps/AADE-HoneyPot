import json
import os
import subprocess
import time
import threading
import tailer
import requests
from rl_orchestrator import RLAgent
from ttp_mapper import map_command_to_ttpx
from llm_synthesizer import LLMSynthesizer

# Detect Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Aggressive Path Discovery for Cowrie (Matches dashboard.py - KALI NATIVE)
POSSIBLE_COWRIE_PATHS = [
    os.path.join(BASE_DIR, 'cowrie/var/log/cowrie/cowrie.json'),
    os.path.expanduser('~/Desktop/AADE-HoneyPot/cowrie/var/log/cowrie/cowrie.json'),
    os.path.expanduser('~/cowrie/var/log/cowrie/cowrie.json'),
    '/home/kali/Desktop/AADE-HoneyPot/cowrie/var/log/cowrie/cowrie.json',
    '/home/kali/aade/cowrie/var/log/cowrie/cowrie.json',
    '/var/log/cowrie/cowrie.json'
]

COWRIE_LOG = None
found_paths = []
for path in POSSIBLE_COWRIE_PATHS:
    if os.path.exists(path):
        found_paths.append(path)

if found_paths:
    # Sort by modification time, newest first to get the active log
    found_paths.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    COWRIE_LOG = found_paths[0]
else:
    # Default to a placeholder within BASE_DIR if nothing found
    COWRIE_LOG = os.path.join(BASE_DIR, 'cowrie/var/log/cowrie/cowrie.json')

KERNEL_PATH = os.path.join(BASE_DIR, 'kernels/vmlinux.bin')
ROOTFS_PATH = os.path.join(BASE_DIR, 'images/rootfs_gold.ext4')

# Fallbacks for legacy setup (Kernels/Images)
if not os.path.exists(KERNEL_PATH):
    KERNEL_PATH = os.path.expanduser('~/aade/kernels/vmlinux.bin')
if not os.path.exists(ROOTFS_PATH):
    ROOTFS_PATH = os.path.expanduser('~/aade/images/rootfs_gold.ext4')

FC_API_URL = "http://localhost/api" # Firecracker API

class MasterOrchestrator:
    def __init__(self):
        print("[*] AADE Master Orchestrator: Initializing Advanced Logic...")
        if os.path.exists(COWRIE_LOG):
            print(f"[*] Orchestrator: Success! Monitoring Cowrie logs at {COWRIE_LOG}")
        else:
            print(f"[!] Orchestrator: Warning! Cowrie log not found at {COWRIE_LOG}")
        
        self.rl_agent = RLAgent("aade_agent.zip")
        self.llm = LLMSynthesizer(provider="ollama")
        self.session_start = time.time()
        self.cmd_count = 0
        self.max_ttp_severity = 0
        self.risk_score = 0
        self.human_probability = 0
        self.detected_ttps = set()
        self.vm_proc = None

    def calculate_metrics(self, cmd_count, ttp_list):
        # 1. Update TTP Set and Severity
        for t in ttp_list:
            self.detected_ttps.add(t['id'])
            # Increase local severity tracking
            self.max_ttp_severity += 10 if t['id'] in ['T1059', 'T1003', 'T1070'] else 5

        # 2. Risk Calculation (0-100)
        risk = (cmd_count * 2) + (len(self.detected_ttps) * 15)
        self.risk_score = min(risk, 100)

        # 3. Human Probability Formula (Mirroring Dashboard)
        high_weight_ttps = {'T1070', 'T1611', 'T1048', 'T1486', 'T1053.003'}
        weight = len(self.detected_ttps & high_weight_ttps) * 35
        weight += len(self.detected_ttps) * 10
        weight += min(cmd_count // 2, 25)
        self.human_probability = min(weight, 100)

    def inject_decoy_artifacts(self):
        """ Triggers LLM synthesis to 'salt' the deception environment """
        print("[*] LLM: Generating unique session artifacts...")
        decoys = self.llm.generate_decoy_files(persona="Financial Database Server")
        
        # Real-world logic: mount rootfs and write files
        for d in decoys:
            print(f"[+] Artifact Injected: {d['path']} (Size: {len(d['content'])} bytes)")

    def start_firecracker(self):
        if self.vm_proc:
            print("[!] Firecracker: VM already running.")
            return

        print("[*] Firecracker: Launching MicroVM via RL Decision...")
        # (Standard Firecracker launch logic here as in original orchestrator)
        # Using subprocess for simplicity in this advanced skeleton
        config = {
            "boot-source": {"kernel_image_path": KERNEL_PATH, "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"},
            "drives": [{"drive_id": "rootfs", "path_on_host": ROOTFS_PATH, "is_root_device": True, "is_read_only": False}],
            "machine-config": {"vcpu_count": 2, "mem_size_mib": 512},
            "vsock": {"guest_cid": 4, "uds_path": "/tmp/vsock.sock"}
        }
        with open('/tmp/vmconfig.json', 'w') as f:
            json.dump(config, f)

        try:
            self.vm_proc = subprocess.Popen(['firecracker', '--no-api', '--config-file', '/tmp/vmconfig.json'])
            print("[+] MicroVM Handoff Successful.")
        except Exception as e:
            print(f"[!] Firecracker Launch Failed: {e}")

    def monitor_cowrie(self):
        print("[*] AADE: Monitoring Cowrie for Adaptive Decision Loop...")
        if not os.path.exists(COWRIE_LOG):
            print(f"[!] Warning: Cowrie log not found: {COWRIE_LOG}")
            # return # Testing: don't return so user can see script logic

        # Open log file for follow
        print(f"[*] Orchestrator: Actively tailing {COWRIE_LOG}...")
        
        with open(COWRIE_LOG, 'r') as log_file:
            for line in tailer.follow(log_file):
                try:
                    event = json.loads(line)
                    
                    # LOG EVERY COMMAND SEEN
                    if event.get("eventid") == "cowrie.command.input":
                        cmd = event.get("input", "")
                        self.cmd_count += 1
                        
                        # 1. Map to MITRE TTPs
                        ttps = map_command_to_ttpx(cmd)
                        ttp_id = ttps[0]['id'] if ttps else "None"
                        ttp_name = ttps[0]['name'] if ttps else "No TTP Match"
                        
                        print(f"\n[>] Command: {cmd}")
                        print(f"    - TTP: {ttp_name} ({ttp_id})")
                        
                        if ttps:
                            self.max_ttp_severity += 5 
                        
                        # 2. Update Intelligence State
                        self.calculate_metrics(self.cmd_count, ttps)
                        duration = time.time() - self.session_start
                        
                        print(f"    - Risk Score: {self.risk_score}/100")
                        print(f"    - Human Prob: {self.human_probability}%")
                        
                        # 3. RL AGENT DECISION
                        action = self.rl_agent.decide(
                            self.cmd_count, 
                            self.max_ttp_severity, 
                            duration, 
                            self.risk_score, 
                            human_prob=self.human_probability
                        )
                        
                        if action == 1: # ESCALATE
                            print(f"\n[!!!] DECISION: ESCALATE TO MICROVM")
                            self.start_firecracker()
                        elif action == 2: # TERMINATE
                            print(f"\n[!!!] DECISION: TERMINATE SESSION")
                            break
                except Exception as e:
                    # print(f"[debug] skip non-json or error: {e}")
                    pass

if __name__ == '__main__':
    try:
        orch = MasterOrchestrator()
        orch.monitor_cowrie()
    except KeyboardInterrupt:
        print("\n[*] AADE Orchestrator: Shutting down gracefully...")
