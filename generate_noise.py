import os
import random
import datetime
from faker import Faker
import json

fake = Faker()
Faker.seed(42)

def create_fake_file(filepath, content):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, 'w') as f:
            f.write(content)
    except Exception as e:
        print(f"[!] Failed to create {filepath}: {e}")

class GoldImageGenerator:
    """
    Phase 2: Gold Image Creation & Human Noise
    Generates a realistic filesystem environment to fool human attackers.
    """
    def __init__(self, mount_point='/mnt/gold'):
        self.root = mount_point
        self.home = os.path.join(self.root, 'home/devuser')

    def generate_all(self):
        print(f"[*] AADE: Generating advanced noise at {self.root}...")
        self.create_bash_history()
        self.create_ssh_keys()
        self.create_bait_documents()
        self.create_dev_projects()
        self.create_browser_history()
        self.create_system_logs()
        print("[+] Advanced Noise Generation Complete.")

    def create_bash_history(self):
        # 500-line realistic history
        cmds = [
            'ls -la', 'cd projects/react-app', 'npm start', 'git pull origin main',
            'ssh-keygen -t rsa', 'curl -X GET http://internal-api:8080/health',
            'sudo apt update', 'nano .env', 'docker ps', 'ps aux | grep python',
            'cat /etc/hosts', 'ping 192.168.1.1', 'python3 -m venv venv',
            'source venv/bin/activate', 'pip install -r requirements.txt'
        ]
        history = '\n'.join([random.choice(cmds) for _ in range(500)])
        create_fake_file(os.path.join(self.home, '.bash_history'), history)

    def create_ssh_keys(self):
        ssh_dir = os.path.join(self.home, '.ssh')
        create_fake_file(os.path.join(ssh_dir, 'id_rsa'), "-----BEGIN RSA PRIVATE KEY-----\n" + fake.sha256() + "\n-----END RSA PRIVATE KEY-----")
        create_fake_file(os.path.join(ssh_dir, 'authorized_keys'), "ssh-rsa " + fake.sha256() + " devuser@workstation")
        
        hosts = '\n'.join([f"10.0.0.{random.randint(2,254)} ssh-rsa {fake.sha256()}" for _ in range(15)])
        create_fake_file(os.path.join(ssh_dir, 'known_hosts'), hosts)

    def create_bait_documents(self):
        docs_dir = os.path.join(self.home, 'Documents')
        baits = {
            'Q1_Revenue_Forecast.xlsx': 'Binary content: ' + fake.text(1000),
            'Network_Topology_2025.pdf': '%PDF-1.4\n' + fake.text(2000),
            'database_credentials.txt': f"DB_USER: root\nDB_PASS: {fake.password()}\nHOST: 10.0.0.50",
            'vpn_config.ovpn': "client\ndev tun\nremote vpn.internal.company 1194\n" + fake.text(500)
        }
        for name, content in baits.items():
            create_fake_file(os.path.join(docs_dir, name), content)

    def create_dev_projects(self):
        # Fake React/Python projects
        proj_dir = os.path.join(self.home, 'projects/internal-dashboard')
        create_fake_file(os.path.join(proj_dir, 'package.json'), json.dumps({"name": "internal-dashboard", "version": "1.0.0", "dependencies": {"express": "^4.17.1"}}, indent=2))
        create_fake_file(os.path.join(proj_dir, '.env'), f"SECRET_KEY={fake.sha256()}\nDB_URL=mongodb://admin:{fake.password()}@10.0.0.21:27017")

    def create_browser_history(self):
        # Realistic 'pre-aging' browser artifacts
        browser_dir = os.path.join(self.home, '.config/google-chrome/Default')
        # Placeholder for history sqlite or json
        history_data = [
            {"url": "https://github.com/internal/repo", "title": "Internal Repo"},
            {"url": "http://jira.company.com/browse/SEC-101", "title": "[SEC-101] Fix database leak"},
            {"url": "https://stackoverflow.com/questions/...", "title": "How to secure KVM"}
        ]
        create_fake_file(os.path.join(browser_dir, 'History_Stub.json'), json.dumps(history_data, indent=2))

    def create_system_logs(self):
        log_dir = os.path.join(self.root, 'var/log')
        syslog = ""
        now = datetime.datetime.now()
        for i in range(1000):
            ts = now - datetime.timedelta(minutes=i*2)
            syslog += f"{ts.strftime('%b %d %H:%M:%S')} workstation systemd[1]: Started Deceptive Service {i}.\n"
        create_fake_file(os.path.join(log_dir, 'syslog'), syslog)

if __name__ == '__main__':
    # Usage: python3 generate_noise.py /mnt/gold
    import sys
    mount = sys.argv[1] if len(sys.argv) > 1 else '/mnt/gold'
    gen = GoldImageGenerator(mount)
    gen.generate_all()
