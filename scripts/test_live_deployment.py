import json
import urllib.request
import urllib.error

LIVE_URL = "https://vidyakashi-digital-omr.onrender.com"

def test_endpoint(name, url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    print(f"\n--- Testing: {name} ({method} {url}) ---")
    body = None
    if data:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            print(f"Status: {resp.status} OK")
            print(f"Response: {content[:200]}...")
            return True, content
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')[:300]}")
        return False, None
    except Exception as e:
        print(f"Error: {e}")
        return False, None

def run_all_tests():
    # 1. Health check
    ok, _ = test_endpoint("Health Check", f"{LIVE_URL}/health")

    # 2. Frontend HTML
    ok, html = test_endpoint("Frontend SPA Landing Page", LIVE_URL)
    if ok and "<div id=\"root\">" in html:
        print("Frontend React SPA successfully served!")

    # 3. Admin Login
    admin_payload = {
        "email": "admin@digitalomr.edu",
        "password": "AdminSecurePassword123!"
    }
    ok, auth_res = test_endpoint("Admin Login", f"{LIVE_URL}/api/auth/login", method="POST", data=admin_payload)
    token = None
    if ok:
        token_data = json.loads(auth_res)
        token = token_data.get("access_token")
        print("JWT Admin Access Token received successfully!")

    # 4. Teacher Login
    teacher_payload = {
        "email": "teacher@digitalomr.edu",
        "password": "Teacher1234!"
    }
    ok, t_res = test_endpoint("Teacher Login (Vidyakashi)", f"{LIVE_URL}/api/auth/login", method="POST", data=teacher_payload)
    if ok:
        print("Teacher authentication validated!")

    # 5. Authenticated route: Templates
    if token:
        auth_headers = {"Authorization": f"Bearer {token}"}
        ok, tmpl_res = test_endpoint("Get Templates", f"{LIVE_URL}/api/templates", headers=auth_headers)
        if ok:
            templates = json.loads(tmpl_res)
            print(f"Found {len(templates)} bootstrapped OMR templates!")

if __name__ == "__main__":
    run_all_tests()
