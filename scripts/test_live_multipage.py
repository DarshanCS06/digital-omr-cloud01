import httpx
import sys
import time

LIVE_URL = "https://vidyakashi-digital-omr.onrender.com"

# 1. Login to get token
login_data = {
    "email": "teacher@digitalomr.edu",
    "password": "Teacher1234!"
}
print("Logging in to live server...")
with httpx.Client(timeout=60.0) as client:
    resp = client.post(f"{LIVE_URL}/api/auth/login", json=login_data)
    if resp.status_code != 200:
        print("Login failed:", resp.status_code, resp.text)
        sys.exit(1)

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful, token received.")

    for test_file in ["test_5_pages.pdf", "test_20_pages.pdf"]:
        pdf_path = f"C:\\Users\\rahul\\.gemini\\antigravity\\scratch\\digital-omr-cloud\\generated\\{test_file}"
        print(f"\n--- Testing upload of {test_file} ---")
        t0 = time.time()
        with open(pdf_path, "rb") as f:
            files = {"file": (test_file, f, "application/pdf")}
            try:
                val_resp = client.post(
                    f"{LIVE_URL}/api/batches/validate-preview/1",
                    headers=headers,
                    files=files,
                )
                dur = time.time() - t0
                print(f"Validation status code: {val_resp.status_code} in {dur:.2f}s")
                print("Validation response (truncated):", val_resp.text[:300])
            except Exception as e:
                print(f"Request failed with exception: {e}")
