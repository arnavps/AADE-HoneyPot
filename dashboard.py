import os
import json
import glob
from datetime import datetime
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
        # Check alternative common paths for Cowrie logs
        ALT_COWRIE_PATHS = [
            os.path.expanduser('~/aade/cowrie/var/log/cowrie/cowrie.json.1'),
            os.path.expanduser('~/aade/cowrie/cowrie.json')
        ]
        
        if os.path.exists(COWRIE_PATH):
            log_paths.append(COWRIE_PATH)
        for alt_path in ALT_COWRIE_PATHS:
            if os.path.exists(alt_path):
                log_paths.append(alt_path)

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
    ip_metadata = {}
    now = datetime.now()
    
    for e in events:
        ts_str = e.get('timestamp', '')
        ip = e.get('src_ip') or e.get('src_ip', '127.0.0.1')
        unique_ips.add(ip)
        
        if ip not in ip_metadata:
            ip_metadata[ip] = {"cmds": 0, "ttps": set(), "first": None, "last": None}
        
        ip_metadata[ip]["cmds"] += 1
        
        # TTP Counts
        for t in e.get('mitre_tags', []):
            tid = t['id']
            ip_metadata[ip]["ttps"].add(tid)
            if tid not in ttp_counts:
                ttp_counts[tid] = {"name": t['name'], "count": 0}
            ttp_counts[tid]["count"] += 1
            
        if e.get('llm_synthesized'):
            llm_hits += 1
        if e.get('hostname') != 'cowrie_entry':
            high_interaction_active = True
            
        # Time logic
        try:
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if not ip_metadata[ip]["first"] or ts < ip_metadata[ip]["first"]:
                    ip_metadata[ip]["first"] = ts
                if not ip_metadata[ip]["last"] or ts > ip_metadata[ip]["last"]:
                    ip_metadata[ip]["last"] = ts
                    
                if (now.timestamp() - ts.timestamp()) < 900: # 15 mins
                    active_ips.add(ip)
                
                hour_key = ts.strftime('%H:00')
                timeline[hour_key] = timeline.get(hour_key, 0) + 1
        except: pass

    # Calculate Probability and Engagement for top active sessions
    session_intel = []
    for ip, meta in ip_metadata.items():
        if ip in active_ips:
            # Probability formula: based on TTP levels and variety
            # T1070 (Log removal), T1611 (Escape), T1048 (Exfil) = high weight
            high_weight_ttps = {'T1070', 'T1611', 'T1048', 'T1486', 'T1053.003'}
            weight = len(meta["ttps"] & high_weight_ttps) * 30
            weight += len(meta["ttps"]) * 5
            weight += min(meta["cmds"] // 5, 20)
            prob = min(weight, 100)
            
            duration = 0
            if meta["first"] and meta["last"]:
                duration = int((meta["last"] - meta["first"]).total_seconds())

            session_intel.append({
                "ip": ip,
                "cmds": meta["cmds"],
                "ttp_count": len(meta["ttps"]),
                "prob": prob,
                "duration": duration
            })

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
        "mode": "ADAPTIVE (High Interaction)" if high_interaction_active else "MONITORING (Low Interaction)",
        "session_intel": session_intel[:10]
    })

if __name__ == '__main__':
    print("[*] AADE Intelligent Dashboard Running...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
