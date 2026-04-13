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
    def get_latest_intel(limit=100, hours=24):
        events = []
        log_paths = glob.glob(os.path.join(LOG_DIR, '*.jsonl'))
        COWRIE_PATH = os.path.expanduser('~/aade/cowrie/var/log/cowrie/cowrie.json')
        if os.path.exists(COWRIE_PATH):
            log_paths.append(COWRIE_PATH)

        for path in sorted(log_paths, reverse=True)[:10]: # Read more files for stats
            try:
                with open(path, 'r') as f:
                    lines = f.readlines()[-500:] # Last 500 lines per file
                    for line in lines:
                        try:
                            ev = json.loads(line)
                            # Normalize Cowrie events
                            if 'eventid' in ev:
                                if ev['eventid'] == 'cowrie.command.input':
                                    ev['cmd'] = ev.get('input', '')
                                    ev['mitre_tags'] = map_command_to_ttpx(ev['cmd'])
                                    ev['hostname'] = 'cowrie_entry'
                                    ev['user'] = ev.get('username', 'root')
                                elif ev['eventid'] == 'cowrie.session.connect':
                                    ev['cmd'] = '[CONNECTED]'
                                    ev['hostname'] = 'cowrie_entry'
                            
                            if 'cmd' in ev or 'eventid' in ev:
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
    return jsonify(DashboardAPI.get_latest_intel(100))

@app.route('/api/stats')
def stats():
    events = DashboardAPI.get_latest_intel(2000) # Get more events for stats
    ttp_counts = {}
    unique_ips = set()
    active_ips = set()
    llm_hits = 0
    high_interaction_active = False
    
    # Timeline: attacks per hour for last 24 hours
    timeline = {}
    now = datetime.now()
    
    for e in events:
        ts_str = e.get('timestamp', '')
        ip = e.get('src_ip') or e.get('src_ip', '127.0.0.1')
        unique_ips.add(ip)
        
        # TTP Counts
        for t in e.get('mitre_tags', []):
            tid = t['id']
            if tid not in ttp_counts:
                ttp_counts[tid] = {"name": t['name'], "count": 0}
            ttp_counts[tid]["count"] += 1
            
        if e.get('llm_synthesized'):
            llm_hits += 1
        if e.get('hostname') != 'cowrie_entry':
            high_interaction_active = True
            
        # Active Sessions (last 15 mins)
        try:
            if ts_str:
                # Handle ISO format
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if (now.timestamp() - ts.timestamp()) < 900: # 15 mins
                    active_ips.add(ip)
                
                # Timeline bucket (by hour)
                hour_key = ts.strftime('%H:00')
                timeline[hour_key] = timeline.get(hour_key, 0) + 1
        except: pass

    # Sort timeline keys
    sorted_timeline = [{"time": k, "count": timeline[k]} for k in sorted(timeline.keys())]

    return jsonify({
        "total_commands": len(events),
        "unique_ttps": len(ttp_counts),
        "unique_ips": len(unique_ips),
        "active_sessions": len(active_ips),
        "ttp_counts": ttp_counts,
        "synthetic_responses": llm_hits,
        "timeline": sorted_timeline,
        "mode": "ADAPTIVE (High Interaction)" if high_interaction_active else "MONITORING (Low Interaction)"
    })

if __name__ == '__main__':
    print("[*] AADE Intelligent Dashboard Running...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
