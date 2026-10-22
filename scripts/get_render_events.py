import json
import urllib.request
import urllib.error

RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
SERVICE_ID = "srv-dbd2qoon74is7380jgkg"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json",
}

# Check service events
url = f"https://api.render.com/v1/services/{SERVICE_ID}/events?limit=20"
req = urllib.request.Request(url, headers=headers, method="GET")
try:
    with urllib.request.urlopen(req) as resp:
        events = json.loads(resp.read().decode("utf-8"))
        print("Events count:", len(events))
        for ev in events:
            print(f"[{ev.get('timestamp')}] {ev.get('type')}: {ev.get('details')}")
except Exception as e:
    print("Error fetching events:", e)
