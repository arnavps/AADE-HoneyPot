import os
import json
import glob
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from ttp_mapper import map_command_to_ttpx

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

LOG_DIR = os.path.expanduser('~/aade/logs')
app.config['SECRET_KEY'] = 'aade-advanced-secret!'

class DashboardAPI:
    @staticmethod
    def get_latest_intel(limit=100):
        events = []
        # Support both custom vsock logs and cowrie logs
        log_paths = glob.glob(os.path.join(LOG_DIR, '*.jsonl'))
        COWRIE_PATH = os.path.expanduser('~/aade/cowrie/var/log/cowrie/cowrie.json')
        if os.path.exists(COWRIE_PATH):
            log_paths.append(COWRIE_PATH)

        for path in sorted(log_paths, reverse=True)[:5]:
            try:
                with open(path, 'r') as f:
                    lines = f.readlines()[-200:] # Last 200 lines per file
                    for line in lines:
                        try:
                            ev = json.loads(line)
                            # Normalize Cowrie events
                            if 'eventid' in ev and ev['eventid'] == 'cowrie.command.input':
                                ev['cmd'] = ev.get('input', '')
                                ev['mitre_tags'] = map_command_to_ttpx(ev['cmd'])
                                ev['hostname'] = 'cowrie_entry'
                            
                            if 'cmd' in ev:
                                events.append(ev)
                        except: continue
            except: continue

        events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return events[:limit]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/intel')
def intel():
    return jsonify(DashboardAPI.get_latest_intel())

@app.route('/api/stats')
def stats():
    events = DashboardAPI.get_latest_intel(1000)
    ttps = set()
    llm_hits = 0
    high_interaction_active = False

    for e in events:
        for t in e.get('mitre_tags', []):
            ttps.add(t['id'])
        if e.get('llm_synthesized'):
            llm_hits += 1
        if e.get('hostname') != 'cowrie_entry':
            high_interaction_active = True

    return jsonify({
        "total_commands": len(events),
        "unique_ttps": len(ttps),
        "synthetic_responses": llm_hits,
        "mode": "ADAPTIVE (High Interaction)" if high_interaction_active else "MONITORING (Low Interaction)"
    })

if __name__ == '__main__':
    print("[*] AADE Intelligent Dashboard Running...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
