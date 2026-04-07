import socket
import json
import os
import time
from datetime import datetime
from ttp_mapper import map_command_to_ttpx
from llm_synthesizer import LLMSynthesizer

# VSOCK definitions
AF_VSOCK = getattr(socket, 'AF_VSOCK', 40)
VMADDR_CID_ANY = getattr(socket, 'VMADDR_CID_ANY', -1)
PORT = 5005

LOG_DIR = os.path.expanduser('~/aade/logs')

class VsockIntelligenceListener:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.llm = LLMSynthesizer(provider="ollama") # Default to local for Kali
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.log_file = os.path.join(LOG_DIR, f'session_{self.today}.jsonl')

    def start(self):
        try:
            s = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
            s.bind((VMADDR_CID_ANY, PORT))
            s.listen(5)
            print(f"[*] AADE Advanced Vsock Listener: Listening on port {PORT}")
        except Exception as e:
            print(f"[!] Error: Vsock bind failed (Linux-only): {e}")
            return

        while True:
            try:
                conn, addr = s.accept()
                data = conn.recv(16384) # Larger buffer for potential payloads
                if data:
                    self.process_event(data, conn)
                conn.close()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] Listener Error: {e}")

    def process_event(self, data, conn):
        try:
            event = json.loads(data.decode('utf-8'))
            event['timestamp'] = datetime.now().isoformat()
            
            cmd = event.get('cmd', '')
            user = event.get('user', 'unknown')
            cwd = event.get('cwd', '/')
            
            # 1. Advanced TTP Mapping
            event['mitre_tags'] = map_command_to_ttpx(cmd)
            
            # 2. LLM Behavioral Synthesis (Ghost in the Machine)
            # If the command is a recon or harmless command, we synthesize a 'distraction' response
            if not event['mitre_tags'] or any(t['id'] in ['T1083', 'T1082'] for t in event['mitre_tags']):
                # T1083: File and Directory Discovery
                # T1082: System Information Discovery
                fake_output = self.llm.synthesize_output(cmd, {"user": user, "cwd": cwd})
                event['llm_synthesized'] = True
                event['fake_output'] = fake_output
                
                # In an advanced setup, we would send this fake_output BACK to the guest
                # and have the logger_agent display it to the attacker.
                # conn.sendall(json.dumps({"type": "response", "data": fake_output}).encode('utf-8'))

            # 3. Secure Logging
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
            
            print(f"[INTEL] {user}@{event.get('hostname','guest')}:{cwd}$ {cmd}")
            if event.get('llm_synthesized'):
                print(f"       -> Synthetic Response Triggered.")

        except Exception as e:
            print(f"[!] Event Processing Error: {e}")

if __name__ == '__main__':
    listener = VsockIntelligenceListener()
    listener.start()
