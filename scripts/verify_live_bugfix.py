import httpx
import time
import sys

LIVE_URL = "https://vidyakashi-digital-omr.onrender.com"

print("==================================================")
print("DIGITAL OMR CLOUD - LIVE BUGFIX VERIFICATION SUITE")
print("Target:", LIVE_URL)
print("==================================================")

# 1. Login
with httpx.Client(timeout=60.0) as client:
    login_res = client.post(f"{LIVE_URL}/api/auth/login", json={
        "email": "teacher@digitalomr.edu",
        "password": "Teacher1234!"
    })
    if login_res.status_code != 200:
        print("Login failed:", login_res.status_code, login_res.text)
        sys.exit(1)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] Teacher authenticated successfully.")

    # 2. Check active exam
    exam_res = client.get(f"{LIVE_URL}/api/examinations/1", headers=headers)
    assert exam_res.status_code == 200, f"Exam fetch failed: {exam_res.text}"
    exam = exam_res.json()
    print(f"[PASS] Active examination found: '{exam['title']}' (ID: {exam['id']}, Questions: {exam['question_count']})")

    # 3. Test PDF inspection for 1-page, 5-page, and 20-page PDFs
    test_cases = [
        ("1-page PDF", r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated\Sample_OMR_25Q.pdf", 1),
        ("5-page PDF", r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated\test_5_pages.pdf", 5),
        ("20-page PDF", r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated\test_20_pages.pdf", 20),
    ]

    for label, file_path, expected_pages in test_cases:
        print(f"\n--- Testing {label}: {file_path.split('\\')[-1]} ---")
        t0 = time.time()
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split('\\')[-1], f, "application/pdf")}
            res = client.post(f"{LIVE_URL}/api/batches/validate-preview/1", headers=headers, files=files)
        elapsed = time.time() - t0

        if res.status_code != 200:
            print(f"[FAIL] Inspection HTTP {res.status_code}: {res.text}")
            sys.exit(1)

        data = res.json()
        print(f"Elapsed: {elapsed:.2f}s | HTTP {res.status_code} OK")
        print(f"Page Count: {data.get('page_count')} (Expected: {expected_pages})")
        print(f"Is Valid: {data.get('is_valid')}")
        print(f"Validation Message: {data.get('validation_message')}")
        
        orig_url = data.get("original_preview_url", "")
        corr_url = data.get("corrected_preview_url", "")
        print(f"Original Preview Generated: {bool(orig_url and orig_url.startswith('data:image/jpeg;base64,'))} ({len(orig_url)} chars)")
        print(f"Corrected Preview Generated: {bool(corr_url and corr_url.startswith('data:image/jpeg;base64,'))} ({len(corr_url)} chars)")

        assert data.get("page_count") == expected_pages, f"Page count mismatch: {data.get('page_count')} != {expected_pages}"
        assert data.get("is_valid") is True, f"Validation is not true: {data.get('validation_message')}"
        assert orig_url.startswith("data:image/jpeg;base64,"), "Missing original preview URL"
        assert corr_url.startswith("data:image/jpeg;base64,"), "Missing corrected preview URL"
        print(f"[PASS] {label} inspection, page counting, and preview verified successfully!")

    # 4. Test progression to Automatic Evaluation
    print("\n--- Testing Progression to Automatic Evaluation (Upload Batch) ---")
    batch_pdf = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated\test_5_pages.pdf"
    with open(batch_pdf, "rb") as f:
        files = [("files", ("test_5_pages.pdf", f, "application/pdf"))]
        upload_res = client.post(f"{LIVE_URL}/api/batches/upload-pdf/1", headers=headers, files=files)

    if upload_res.status_code not in (200, 202):
        print(f"[FAIL] Upload failed: {upload_res.status_code} - {upload_res.text}")
        sys.exit(1)

    batch_info = upload_res.json()
    batch_id = batch_info.get("batch_id") or batch_info.get("id")
    print(f"[PASS] Batch created and queued with ID: {batch_id}, total files received: {batch_info.get('files_received')}")

    # 5. Monitor evaluation progress
    print("Polling batch progress on live cloud worker...")
    for _ in range(15):
        time.sleep(2)
        b_res = client.get(f"{LIVE_URL}/api/batches/{batch_id}", headers=headers)
        b_data = b_res.json()
        print(f"  Status: {b_data['status']} | Processed: {b_data['processed_files']}/{b_data['total_files']} | Successful: {b_data['successful_files']}")
        if b_data["status"] in ("COMPLETED", "FAILED"):
            break

    assert b_data["status"] == "COMPLETED", f"Batch did not complete: {b_data.get('error_summary')}"
    print(f"\n[PASS] Automatic evaluation completed successfully: {b_data['successful_files']} sheets evaluated!")
    print("\nALL VERIFICATION TESTS PASSED ON LIVE WEBSITE!")
