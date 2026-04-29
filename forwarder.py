import time
import json
import requests
import os
import glob
from datetime import datetime

DASHBOARD_URL = 'http://127.0.0.1:5000/api/ingest'
COWRIE_LOG = os.path.expanduser('~/aade/cowrie/var/log/cowrie/cowrie.json')
AADE_LOG_DIR = os.path.expanduser('~/aade/logs')

print(f"[*] AADE Log Forwarder Started.")
print(f"[*] Target Dashboard: {DASHBOARD_URL}")

def forward_line(line):
    try:
        ev = json.loads(line)
        # Normalize Cowrie events for the dashboard
        if 'eventid' in ev:
            if ev['eventid'] == 'cowrie.command.input':
                ev['cmd'] = ev.get('input', '')
                ev['hostname'] = 'cowrie_entry'
                ev['user'] = ev.get('username', 'root')
            elif ev['eventid'] == 'cowrie.session.connect':
                ev['cmd'] = '[CONNECTED]'
                ev['hostname'] = 'cowrie_entry'
        
        # Only forward if it's an actionable event
        if 'cmd' in ev or 'eventid' in ev:
            print(f"[*] Attempting to send event {ev.get('cmd', ev.get('eventid'))} to {DASHBOARD_URL}...")
            response = requests.post(DASHBOARD_URL, json=ev, timeout=5)
            if response.status_code == 200:
                print(f"[✓] Successfully forwarded to Windows Dashboard.")
            else:
                print(f"[!] Dashboard responded with error: {response.status_code}")
    except Exception as e:
        print(f"[!] Forwarding error: {e}")

def follow(file_path):
    if not os.path.exists(file_path):
        print(f"[!] Waiting for log file: {file_path}")
        while not os.path.exists(file_path):
            time.sleep(1)
            
    with open(file_path, 'r') as f:
        # Go to the end of the file
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line

if __name__ == '__main__':
    # For now, we follow the main Cowrie log. 
    # In a full setup, you'd run multiple threads or use watchdog.
    try:
        for line in follow(COWRIE_LOG):
            forward_line(line)
    except KeyboardInterrupt:
        print("\n[*] Stopping forwarder.")
