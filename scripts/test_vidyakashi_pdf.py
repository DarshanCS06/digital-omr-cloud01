import httpx

LIVE_URL = "https://vidyakashi-digital-omr.onrender.com"

login_data = {
    "email": "teacher@digitalomr.edu",
    "password": "Teacher1234!"
}

with httpx.Client(timeout=60.0) as client:
    resp = client.post(f"{LIVE_URL}/api/auth/login", json=login_data)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for pdf_name in ["Vidyakashi_OMR_Sheet_25Q.pdf", "Vidyakashi_Ticked_25Q.pdf"]:
        pdf_path = f"C:\\Users\\rahul\\.gemini\\antigravity\\scratch\\digital-omr-cloud\\generated\\{pdf_name}"
        print(f"\n--- Testing upload of {pdf_name} to exam 1 ---")
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_name, f, "application/pdf")}
            try:
                val_resp = client.post(
                    f"{LIVE_URL}/api/batches/validate-preview/1",
                    headers=headers,
                    files=files,
                )
                print(f"Validation status code: {val_resp.status_code}")
                print("Validation response:", val_resp.text[:400])
            except Exception as e:
                print("Exception:", e)
