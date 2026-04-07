import sys
import socket
import json
import os

AF_VSOCK = getattr(socket, 'AF_VSOCK', 40)
HOST_CID = 2 # Firecracker host CID
PORT = 5005

def main():
    if len(sys.argv) < 3:
        return
    
    exit_code = sys.argv[1]
    cmd = sys.argv[2]
    user = os.getenv('USER', 'unknown')
    cwd = os.getcwd()
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown"

    event = {
        "cmd": cmd.strip(),
        "exit_code": exit_code,
        "user": user,
        "cwd": cwd,
        "hostname": hostname
    }

    try:
        s = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        s.connect((HOST_CID, PORT))
        s.sendall(json.dumps(event).encode('utf-8'))
        s.close()
    except Exception as e:
        # Silently fail so attacker doesn't know
        pass

if __name__ == '__main__':
    main()
