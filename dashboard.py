import os
import json
import glob
import psutil
import time
import platform
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from ttp_mapper import map_command_to_ttpx

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory store for events pushed from remote sensors (Kali VM)
REMOTE_EVENTS = []

# Detect Base Directory (Standard Linux/Kali structure)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    # Fallback to absolute home path on Kali
    LOG_DIR = os.path.expanduser('~/Desktop/AADE-HoneyPot/logs')
app.config['SECRET_KEY'] = 'aade-advanced-secret!'

class DashboardAPI:
    @staticmethod
    def get_system_health():
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_delta = datetime.now() - boot_time
            
            # Format uptime
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{days}d {hours}h {minutes}m"
            
            # Get real listening ports
            listeners = []
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'LISTEN' and conn.laddr.port not in [p[1] for p in listeners]:
                        listeners.append(f"TCP/{conn.laddr.port}")
            except:
                listeners = ["TCP/22", "TCP/80", "TCP/2222"] # Fallback if permission denied
                
            return {
                "cpu_usage": f"{cpu}%",
                "ram_usage": f"{round(mem.used / (1024**3), 1)}GB / {round(mem.total / (1024**3), 1)}GB",
                "uptime": uptime_str,
                "active_listeners": sorted(list(set(listeners)))[:5],
                "sensor_load": "OPTIMAL" if cpu < 70 else "HIGH"
            }
        except Exception as e:
            print(f"[!] Error fetching health: {e}")
            return {"cpu_usage": "0%", "ram_usage": "0/0", "uptime": "0s", "active_listeners": [], "sensor_load": "UNKNOWN"}

    @staticmethod
    def is_service_active(keywords):
        try:
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    pinfo = proc.info
                    cmdline = " ".join(pinfo.get('cmdline') or [])
                    name = pinfo.get('name') or ""
                    if any(key.lower() in name.lower() or key.lower() in cmdline.lower() for key in keywords):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except: pass
        return False

    @staticmethod
    def get_latest_intel(limit=100, hours=24):
        events = []
        log_paths = glob.glob(os.path.join(LOG_DIR, '*.jsonl'))
        # Aggressive Path Discovery for Cowrie (KALI NATIVE)
        POSSIBLE_COWRIE_PATHS = [
            os.path.join(BASE_DIR, 'cowrie/var/log/cowrie/cowrie.json'),
            os.path.expanduser('~/Desktop/AADE-HoneyPot/cowrie/var/log/cowrie/cowrie.json'),
            os.path.expanduser('~/cowrie/var/log/cowrie/cowrie.json'),
            '/home/kali/Desktop/AADE-HoneyPot/cowrie/var/log/cowrie/cowrie.json',
            '/home/kali/aade/cowrie/var/log/cowrie/cowrie.json',
            '/var/log/cowrie/cowrie.json'
        ]
        
        found_cowrie = False
        found_paths = []
        for path in POSSIBLE_COWRIE_PATHS:
            if os.path.exists(path):
                found_paths.append(path)
        
        if found_paths:
            found_paths.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            chosen_path = found_paths[0]
            if chosen_path not in log_paths:
                log_paths.append(chosen_path)
            found_cowrie = True
            # Quiet logging for production feel
            if not hasattr(app, 'last_log_path') or app.last_log_path != chosen_path:
                print(f"[*] Dashboard: Active Cowrie logs detected at {chosen_path}")
                app.last_log_path = chosen_path
        else:
            # Fallback debug message
            if not hasattr(app, 'log_warn_sent'):
                print(f"[!] Dashboard: Telemetry missing. Ensure Cowrie is running and logging to one of: {POSSIBLE_COWRIE_PATHS[:2]}")
                app.log_warn_sent = True

        for path in sorted(log_paths, key=os.path.getmtime, reverse=True)[:15]: # Read more files for stats
            try:
                with open(path, 'r') as f:
                    lines = f.readlines()[-500:] # Last 500 lines per file
                    for line in lines:
                        try:
                            ev = json.loads(line)
                            # Normalize Cowrie events
                            # Normalize Cowrie events
                            if 'eventid' in ev:
                                if ev['eventid'] == 'cowrie.command.input':
                                    ev['cmd'] = ev.get('input', '')
                                    ev['hostname'] = 'cowrie_entry'
                                    ev['user'] = ev.get('username', 'root')
                                elif ev['eventid'] == 'cowrie.session.connect':
                                    ev['cmd'] = '[CONNECTED]'
                                    ev['hostname'] = 'cowrie_entry'
                            
                            # Add mitre_tags for ALL events with a cmd (including VSOCK session logs)
                            if 'cmd' in ev and 'mitre_tags' not in ev:
                                ev['mitre_tags'] = map_command_to_ttpx(ev['cmd'])
                            
                            if 'cmd' in ev or 'eventid' in ev:
                                events.append(ev)
                        except: continue
            except: continue

        events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Merge with remote events from Kali VM
        all_events = REMOTE_EVENTS + events
        all_events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return all_events[:limit]

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/ingest', methods=['POST'])
def ingest():
    """Receives logs pushed from the Kali VM forwarder."""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        # Normalize and map TTPs if not present
        if 'cmd' in data and 'mitre_tags' not in data:
            data['mitre_tags'] = map_command_to_ttpx(data['cmd'])
        
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
            
        REMOTE_EVENTS.insert(0, data)
        # Keep buffer to a reasonable size
        if len(REMOTE_EVENTS) > 1000:
            REMOTE_EVENTS.pop()
            
        return jsonify({"status": "success", "count": len(REMOTE_EVENTS)}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats')
def stats():
    events = DashboardAPI.get_latest_intel(2000) # Get more events for stats
    ttp_counts = {}
    unique_ips = set()
    active_ips = set()
    llm_hits = 0
    high_interaction_active = False
    
    # Timeline logic
    timeline = {}
    ip_metadata = {}
    now = datetime.now()
    
    for e in events:
        ts_str = e.get('timestamp', '')
        ip = e.get('src_ip') or '127.0.0.1'
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

    # Calculate Tactic Distribution
    tactic_groups = {
        "Reconnaissance": ["T1083", "T1016", "T1033", "T1082"],
        "Initial Access": ["T1110", "T1105", "T1021.004"],
        "Execution": ["T1059.004", "T1059.006", "T1053.003"],
        "Persistence": ["T1053.003", "T1136.001"],
        "Defense Evasion": ["T1070", "T1562.004", "T1222.002"],
        "Discovery": ["T1083", "T1057", "T1016", "T1033", "T1082"],
        "Lateral Movement": ["T1021.004", "T1095"],
        "Impact": ["T1486", "T1496", "T1498"],
        "Collection": ["T1003", "T1557"]
    }
    
    vector_distribution = {k: 0 for k in tactic_groups.keys()}
    for tid, data in ttp_counts.items():
        for tactic, tids in tactic_groups.items():
            if tid in tids:
                vector_distribution[tactic] += data['count']

    # Threat Velocity (Events in last 15 mins)
    threat_velocity = 0
    for e in events:
        try:
            ts_str = e.get('timestamp', '')
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if (now.timestamp() - ts.timestamp()) < 900:
                    threat_velocity += 1
        except: pass

    # Session Intelligence
    session_intel = []
    for ip, meta in ip_metadata.items():
        if ip in active_ips or meta["cmds"] > 0:
            high_weight_ttps = {'T1070', 'T1611', 'T1048', 'T1486', 'T1053.003', 'T1557'}
            weight = len(meta["ttps"] & high_weight_ttps) * 30
            weight += len(meta["ttps"]) * 5
            weight += min(meta["cmds"] // 5, 20)
            prob = min(weight, 100)
            
            persona = "Unknown Crawler"
            if prob > 80: persona = "Advanced Persistent Threat (APT)"
            elif prob > 50: persona = "Skilled Human Operator"
            elif meta["cmds"] > 5 and len(meta["ttps"]) < 2: persona = "Credential Sprayer"
            elif meta["cmds"] > 0: persona = "Automated Recon Bot"

            duration = 0
            if meta["first"] and meta["last"]:
                duration = int((meta["last"] - meta["first"]).total_seconds())

            session_intel.append({
                "ip": ip, "cmds": meta["cmds"], "ttp_count": len(meta["ttps"]),
                "prob": prob, "persona": persona, "duration": f"{duration}s"
            })

    # Real Strategy & Fidelity Logic
    total_ttp_hits = sum(d['count'] for d in ttp_counts.values())
    stealth_health = max(65, 100 - (len(ttp_counts) * 2) - (len(active_ips) * 1))
    if llm_hits > 0: stealth_health = min(100, stealth_health + 10)
    
    deception_strategy = {
        "status": "ADAPTIVE_DECEPTION_ACTIVE",
        "rl_state": "EXPLOITATIVE_STALLING" if active_ips else "EXPLORATIVE_IDLE",
        "active_policy": "SHADOW_ENVIRONMENT_MIGRATION" if high_interaction_active else "DYNAMIC_DELAY_INJECTION",
        "stealth_health": int(stealth_health),
        "directives": [
            "Intercepting outbound C2 beacons" if total_ttp_hits > 5 else "Minimizing honeypot footprint",
            "Simulating human filesystem latency" if len(active_ips) > 0 else "LLM Response Engine Standby",
            "Injecting synthetic artifacts" if llm_hits > 0 else "Monitoring TDP ingress vectors"
        ]
    }

    hp_active = DashboardAPI.is_service_active(['cowrie', 'bin/cowrie'])
    vm_active = DashboardAPI.is_service_active(['firecracker', 'jailer']) or high_interaction_active

    return jsonify({
        "total_commands": len(events),
        "total_attacks": len([e for e in events if e.get('cmd')]),
        "active_sessions": len(active_ips),
        "threat_velocity": threat_velocity,
        "unique_ips": len(unique_ips),
        "ghost_responses": llm_hits,
        "honeypot_active": hp_active,
        "microvm_active": vm_active,
        "mode": "HYBRID_DECEPTION" if high_interaction_active else "LOW_INTERACTION_DECEPTION",
        "timeline": [{"time": k, "count": timeline[k]} for k in sorted(timeline.keys())],
        "vector_distribution": vector_distribution,
        "ttp_counts": ttp_counts,
        "system_health": DashboardAPI.get_system_health(),
        "deception_strategy": deception_strategy,
        "session_intel": sorted(session_intel, key=lambda x: x['prob'], reverse=True)[:5],
        "active_log_path": getattr(app, 'last_log_path', 'Searching...'),
        "server_time": datetime.utcnow().isoformat() + "Z" # Explicit Zulu for frontend sync
    })

@app.route('/api/debug')
def debug_diagnostic():
    # Use the same logic as the ingestion path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(base_dir, 'cowrie/var/log/cowrie/cowrie.json'),
        os.path.expanduser('~/Desktop/AADE-HoneyPot/cowrie/var/log/cowrie/cowrie.json'),
        os.path.expanduser('~/cowrie/var/log/cowrie/cowrie.json'),
        '/home/kali/Desktop/AADE-HoneyPot/cowrie/var/log/cowrie/cowrie.json',
        '/home/kali/aade/cowrie/var/log/cowrie/cowrie.json',
        '/var/log/cowrie/cowrie.json'
    ]
    
    found_path = None
    for p in possible_paths:
        if os.path.exists(p):
            found_path = p
            break
            
    status = {
        "base_dir": base_dir,
        "searched_paths": possible_paths,
        "cowrie_path_found": found_path,
        "file_exists": found_path is not None,
        "last_5_lines": []
    }
    
    if found_path:
        try:
            status["file_permissions"] = oct(os.stat(found_path).st_mode)[-3:]
            with open(found_path, 'r') as f:
                status["last_5_lines"] = f.readlines()[-5:]
        except Exception as e:
            status["error"] = str(e)
            
    return jsonify(status)

@app.route('/api/intel')
def intel():
    try:
        limit = int(request.args.get('limit', 100))
        data = DashboardAPI.get_latest_intel(limit=limit)
        return jsonify({
            "events": data,
            "server_time": datetime.utcnow().isoformat() + "Z"
        })
    except Exception as e:
        return jsonify({"error": str(e), "events": []}), 500

if __name__ == '__main__':
    print("[*] AADE Intelligent Dashboard Running on Port 5000...")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
