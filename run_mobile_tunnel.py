"""
Auto-reconnecting HTTPS Mobile Tunnel Manager for Digital OMR Cloud.
Maintains a live public HTTPS tunnel to 127.0.0.1:8000 via localhost.run
and keeps .mobile_tunnel_url.txt updated for the Android QR Code modal.
"""
import os
import re
import subprocess
import time

TUNNEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mobile_tunnel_url.txt")
URL_PATTERN = re.compile(r"(https://[a-zA-Z0-9.-]+\.lhr\.life)")


def run_tunnel_forever():
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=20",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-R", "80:127.0.0.1:8000",
        "nokey@localhost.run",
    ]
    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                 encoding="utf-8",
                errors="replace",
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                m = URL_PATTERN.search(line)
                if m:
                    url = m.group(1).strip()
                    with open(TUNNEL_FILE, "w", encoding="utf-8") as f:
                        f.write(url + "\n")
                    print(f"[MOBILE_TUNNEL_ACTIVE] {url}", flush=True)
            proc.wait()
        except Exception as e:
            print(f"[MOBILE_TUNNEL_ERROR] {e}", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    run_tunnel_forever()
