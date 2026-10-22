import httpx
import sys

LIVE_URL = "https://vidyakashi-digital-omr.onrender.com"

# 1. Login to get token
login_data = {
    "email": "teacher@digitalomr.edu",
    "password": "Teacher1234!"
}
print("Logging in to live server...")
with httpx.Client(timeout=30.0) as client:
    resp = client.post(f"{LIVE_URL}/api/auth/login", json=login_data)
    if resp.status_code != 200:
        print("Login failed:", resp.status_code, resp.text)
        sys.exit(1)

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful, token received.")

    # 2. Check exam 1
    print("Checking exam 1...")
    exam_resp = client.get(f"{LIVE_URL}/api/examinations/1", headers=headers)
    print("Exam 1 status:", exam_resp.status_code)
    if exam_resp.status_code == 200:
        print("Exam 1 details:", exam_resp.json().get("title"))
    else:
        print("Exam 1 response:", exam_resp.text)

    # 3. Post PDF to /api/batches/validate-preview/1
    pdf_path = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated\Sample_OMR_25Q.pdf"
    print(f"Uploading PDF {pdf_path} to /api/batches/validate-preview/1...")

    with open(pdf_path, "rb") as f:
        files = {"file": ("Sample_OMR_25Q.pdf", f, "application/pdf")}
        try:
            val_resp = client.post(
                f"{LIVE_URL}/api/batches/validate-preview/1",
                headers=headers,
                files=files,
            )
            print("Validation status code:", val_resp.status_code)
            print("Validation response:", val_resp.text[:500])
        except httpx.TimeoutException:
            print("REQUEST TIMED OUT AFTER 30 SECONDS!")
        except Exception as e:
            print("Request failed with exception:", e)
