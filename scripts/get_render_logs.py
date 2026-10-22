import json
import urllib.request
import urllib.error

RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
SERVICE_ID = "srv-dbd2qoon74is7380jgkg"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json",
}

for endpoint in [
    f"https://api.render.com/v1/services/{SERVICE_ID}/logs",
    f"https://api.render.com/v1/services/{SERVICE_ID}/deploys/dep-dbd2qpgn74is7380jjk0/logs"
]:
    print("Testing:", endpoint)
    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            print("Response:", data[:400])
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode('utf-8')[:200]}")
