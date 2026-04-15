import requests
import json

base_url = "http://localhost:5000"

def test_api():
    try:
        print("[*] Testing /api/stats...")
        r = requests.get(f"{base_url}/api/stats")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Stats: {json.dumps(data, indent=2)[:500]}...")
        else:
            print(f"Error: {r.text}")

        print("\n[*] Testing /api/intel...")
        r = requests.get(f"{base_url}/api/intel")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Intel events count: {len(data.get('events', []))}")
            print(f"Server time: {data.get('server_time')}")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"[!] Request failed: {e}")

if __name__ == "__main__":
    test_api()
