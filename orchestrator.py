import json
import os
import subprocess
import time
import threading
import tailer
import requests
from rl_orchestrator import RLAgent
from ttp_mapper import map_command_to_ttpx

COWRIE_LOG = os.path.expanduser('~/aade/cowrie/var/log/cowrie/cowrie.json')
KERNEL_PATH = os.path.expanduser('~/aade/kernels/vmlinux.bin')
ROOTFS_PATH = os.path.expanduser('~/aade/images/rootfs_gold.ext4')
FC_API_URL = "http://localhost/api" # Firecracker API

class MasterOrchestrator:
    def __init__(self):
        print("[*] AADE Master Orchestrator: Initializing Advanced Logic...")
        self.rl_agent = RLAgent("aade_agent.zip")
        self.session_start = time.time()
        self.cmd_count = 0
        self.max_ttp_severity = 0
        self.risk_score = 0
        self.vm_proc = None

    def calculate_risk(self, cmd_count, ttp_list):
        # Weighted risk calculation
        severity_weight = len(ttp_list) * 20
        risk = (cmd_count * 2) + severity_weight
        return min(risk, 100)

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

        # In a real environment, use tailer.follow(open(COWRIE_LOG))
        # This skeleton simulates the event loop
        for line in tailer.follow(open(COWRIE_LOG)) if os.path.exists(COWRIE_LOG) else []:
            try:
                event = json.loads(line)
                if event.get("eventid") == "cowrie.command.input":
                    cmd = event.get("input", "")
                    self.cmd_count += 1
                    
                    # 1. Map to MITRE TTPs
                    ttps = map_command_to_ttpx(cmd)
                    if ttps:
                        print(f"[!] TTP Detected: {ttps[0]['name']} ({ttps[0]['id']})")
                        self.max_ttp_severity += 5 
                    
                    # 2. Update Risk State
                    self.risk_score = self.calculate_risk(self.cmd_count, ttps)
                    duration = time.time() - self.session_start
                    
                    # 3. RL AGENT DECISION
                    action = self.rl_agent.decide(self.cmd_count, self.max_ttp_severity, duration, self.risk_score)
                    
                    if action == 1: # ESCALATE
                        print(f"[*] RL ACTION: ESCALATE (Risk: {self.risk_score})")
                        self.start_firecracker()
                    elif action == 2: # TERMINATE
                        print(f"[*] RL ACTION: TERMINATE (Risk: {self.risk_score})")
                        # Logic to block IP or kill session
                        break
            except Exception as e:
                pass

if __name__ == '__main__':
    orch = MasterOrchestrator()
    orch.monitor_cowrie()
