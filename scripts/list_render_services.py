import json
import urllib.request
import urllib.error

RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def list_services():
    req = urllib.request.Request("https://api.render.com/v1/services", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("Services count:", len(data))
            for item in data:
                svc = item.get("service", item)
                print(f"Service: {svc.get('name')} | ID: {svc.get('id')} | URL: {svc.get('serviceDetails', {}).get('url')}")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.read().decode('utf-8')}")

if __name__ == "__main__":
    list_services()
