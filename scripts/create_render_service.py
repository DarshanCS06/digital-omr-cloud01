import json
import urllib.request
import urllib.error

RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
OWNER_ID = "tea-dbd2pjtg1s2s73evp610"
REPO_URL = "https://github.com/DarshanCS06/digital-omr-cloud01"

headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

payload = {
    "type": "web_service",
    "name": "vidyakashi-digital-omr",
    "ownerId": OWNER_ID,
    "repo": REPO_URL,
    "branch": "main",
    "autoDeploy": "yes",
    "serviceDetails": {
        "env": "docker",
        "dockerfilePath": "./Dockerfile",
        "plan": "free",
        "region": "singapore",
        "envVars": [
            {"key": "ENVIRONMENT", "value": "production"},
            {"key": "DEBUG", "value": "false"},
            {"key": "SECRET_KEY", "value": "c8b0e774591f46399672809e5170d9a6914948a3181823eb9b8cf442e3995f5a"},
            {"key": "STORAGE_BACKEND", "value": "local"}
        ]
    }
}

def create_service():
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("https://api.render.com/v1/services", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            print("Create Service Response:")
            print(json.dumps(res_data, indent=2))
            svc = res_data.get("service", res_data)
            print("SERVICE_ID:", svc.get("id"))
            print("SERVICE_URL:", svc.get("serviceDetails", {}).get("url"))
            return svc
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')}")
        return None

if __name__ == "__main__":
    create_service()
