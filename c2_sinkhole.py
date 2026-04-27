import json
import os
from datetime import datetime
from mitmproxy import http

LOG_DIR = os.path.expanduser('~/aade/logs')


def request(flow: http.HTTPFlow):
    os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(LOG_DIR, f'c2_traffic_{today}.jsonl')

    req = flow.request
    event = {
        "timestamp": datetime.now().isoformat(),
        "method": req.method,
        "url": req.pretty_url,
        "headers": dict(req.headers),
        "body": req.text
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(event) + '\n')

    # Return fake 200 OK
    flow.response = http.Response.make(
        200,
        json.dumps({"status": "ok", "message": "beacon received"}),
        {"Content-Type": "application/json"}
    )
