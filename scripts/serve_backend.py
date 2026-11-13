"""Start/reuse this workspace's loopback server without terminating other apps."""

import argparse
import hashlib
import http.client
import json
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORKSPACE = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]


def is_this_server(port):
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        conn.request("GET", "/api/health")
        response = conn.getresponse()
        data = json.loads(response.read())
        conn.close()
        return response.status == 200 and data.get("workspace_id") == WORKSPACE
    except Exception:
        return False


def choose_port():
    for port in range(8787, 8793):
        if is_this_server(port):
            return port, True
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
            return port, False
        except OSError:
            continue
    raise RuntimeError(
        "Ports 8787–8792 are busy. Close an old server window and try again."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    port, reuse = choose_port()
    url = f"http://localhost:{port}/benchmark.html"
    print(("Reusing" if reuse else "Starting") + " MedDesk: " + url, flush=True)
    if args.check_only:
        sys.exit(0)
    if not args.no_browser:

        def open_when_ready():
            for _ in range(60):
                if is_this_server(port):
                    webbrowser.open(url)
                    return
                time.sleep(0.5)

        threading.Thread(target=open_when_ready, daemon=True).start()
    if not reuse:
        import uvicorn

        uvicorn.run(
            "backend.app:app",
            host="127.0.0.1",
            port=port,
            log_level="info",
            ws_max_size=65536,
            ws_max_queue=4,
        )
