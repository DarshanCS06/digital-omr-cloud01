import json
import time
import urllib.request
import urllib.error

RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
SERVICE_ID = "srv-dbd2qoon74is7380jgkg"
DEPLOY_ID = "dep-dbd2qpgn74is7380jjk0"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json",
}

def check_deploy_status():
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys/{DEPLOY_ID}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status")
            print(f"Deploy Status: {status}")
            return status
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')}")
        return None

if __name__ == "__main__":
    check_deploy_status()
