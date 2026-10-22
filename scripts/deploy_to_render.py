import json
import urllib.request
import urllib.error

RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
REPO_URL = "https://github.com/DarshanCS06/digital-omr-cloud01"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def get_owner_id():
    req = urllib.request.Request("https://api.render.com/v1/owners", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("Owners response:", json.dumps(data, indent=2))
            if data and isinstance(data, list) and len(data) > 0:
                owner = data[0].get("owner", data[0])
                return owner.get("id")
            return None
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.read().decode('utf-8')}")
        return None

if __name__ == "__main__":
    owner_id = get_owner_id()
    print("Found Owner ID:", owner_id)
