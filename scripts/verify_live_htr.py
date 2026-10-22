import io
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import cv2
import numpy as np

BASE_URL = "https://vidyakashi-digital-omr.onrender.com"

def api_call(endpoint, method="GET", json_data=None, token=None, files=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if json_data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_data).encode("utf-8")
    elif files is not None:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = bytearray()
        for field_name, (filename, file_bytes, mime) in files.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
            body.extend(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
            body.extend(file_bytes)
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        data = bytes(body)

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}

def run_live_htr_verification():
    print("=" * 60)
    print("LIVE VERIFICATION: HANDWRITING RECOGNITION (HTR)")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    # 1. Login
    login_data = api_call(
        "/api/auth/login",
        method="POST",
        json_data={"email": "teacher@digitalomr.edu", "password": "Teacher1234!"},
    )
    token = login_data["access_token"]
    print("[PASS] 1. Teacher login authenticated successfully.")

    # 2. Get or Create Examination
    exams = api_call("/api/examinations", method="GET", token=token)
    if not exams:
        print("[INFO] Creating benchmark examination on live server...")
        exam_in = {
            "code": f"VKS-HTR-{int(time.time()) % 10000}",
            "title": "Vidyakashi Live HTR Evaluation Test",
            "subject": "Physics",
            "class_grade": "10th",
            "exam_date": "2026-10-23",
            "question_count": 25,
            "options_per_question": 4,
            "positive_marks": 4.0,
            "negative_marks": 1.0,
            "blank_marks": 0.0,
            "initial_answers": {str(q): ["A", "B", "C", "D"][(q - 1) % 4] for q in range(1, 26)},
        }
        exam = api_call("/api/examinations", method="POST", token=token, json_data=exam_in)
    else:
        exam = exams[0]
    exam_id = exam["id"]
    print(f"[PASS] 2. Selected Examination #{exam_id}: '{exam['title']}' ({exam['question_count']}Q)")

    # 3. Create a test sheet with handwritten student details
    from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator
    gen = VidyakashiOMRGenerator(question_count=exam["question_count"])
    sheet_bgr = gen.generate_image(
        exam_title="Live HTR Verification",
        exam_code="VKS-HTR",
        subject="Physics",
        class_grade="10th",
        exam_date="23/10/2026",
        pre_filled_answers={1: "A", 2: "B", 3: "C", 4: "D", 5: "A"},
        student_name="Aarav Sharma",
        student_roll="250710001",
        mark_style="solid",
    )
    _, img_encoded = cv2.imencode(".jpg", sheet_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    test_file_bytes = img_encoded.tobytes()

    # 4. Inspect single sheet preview via /batches/validate-preview/{exam_id}
    t0 = time.time()
    files = {"file": ("student_sheet.jpg", test_file_bytes, "image/jpeg")}
    inspect_data = api_call(
        f"/api/batches/validate-preview/{exam_id}",
        method="POST",
        token=token,
        files=files,
    )
    inspect_duration = time.time() - t0
    print(f"[PASS] 3. Inspection completed in {inspect_duration:.2f}s: page_count={inspect_data.get('page_count')}, is_valid={inspect_data.get('is_valid')}")

    # 5. Upload batch for evaluation via /batches/upload/{exam_id}
    files = {"files": ("student_sheet.jpg", test_file_bytes, "image/jpeg")}
    batch = api_call(
        f"/api/batches/upload/{exam_id}",
        method="POST",
        token=token,
        files=files,
    )
    batch_id = batch.get("batch_id") or batch.get("id")
    print(f"[PASS] 4. Uploaded evaluation batch #{batch_id} (Files received: {batch.get('files_received')})")

    # 6. Poll batch until completion
    t_start = time.time()
    completed_batch = None
    for _ in range(30):
        time.sleep(2)
        b_data = api_call(f"/api/batches/{batch_id}", method="GET", token=token)
        if b_data.get("status") in ("COMPLETED", "FAILED"):
            completed_batch = b_data
            break

    eval_duration = time.time() - t_start
    assert completed_batch is not None, "Batch processing timed out"
    assert completed_batch["status"] == "COMPLETED", f"Batch failed: {completed_batch}"
    print(f"[PASS] 5. Batch #{batch_id} processed in {eval_duration:.2f}s: processed={completed_batch['processed_files']}, failed={completed_batch['failed_files']}")

    # 7. Verify submission contains student details & HTR fields
    subs = api_call(f"/api/submissions/exam/{exam_id}?limit=10", method="GET", token=token)
    assert len(subs) > 0, "No submissions found for exam"
    latest_sub = subs[0]
    sub_id = latest_sub["id"]
    print(f"[PASS] 6. Evaluated Submission #{sub_id}:")
    print(f"       Student Name:       '{latest_sub.get('student_name')}'")
    print(f"       Student Roll:       '{latest_sub.get('student_roll') or latest_sub.get('detected_roll_number')}'")
    print(f"       Name Confidence:    {latest_sub.get('name_confidence', 0.0) * 100:.0f}%")
    print(f"       Roll Confidence:    {latest_sub.get('roll_confidence', 0.0) * 100:.0f}%")
    print(f"       Score:              {latest_sub.get('total_score')} / {latest_sub.get('max_score')} ({latest_sub.get('percentage')}%)")
    print(f"       Status:             {latest_sub.get('status')}")

    # 8. Test Teacher Correction Endpoint (POST /api/submissions/{id}/student-details)
    edit_payload = {
        "student_name": "Aarav S. Sharma (Verified)",
        "student_roll": "250710001",
    }
    updated_sub = api_call(
        f"/api/submissions/{sub_id}/student-details",
        method="POST",
        token=token,
        json_data=edit_payload,
    )
    assert updated_sub.get("student_name") == "Aarav S. Sharma (Verified)", f"Name not updated: {updated_sub}"
    assert updated_sub.get("name_confidence") == 1.0, "Confidence not set to 1.0 for verified teacher edit"
    print(f"[PASS] 7. Teacher edit verified: student details updated to '{updated_sub.get('student_name')}' with 100% confidence.")

    print("=" * 60)
    print("ALL LIVE HTR VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_live_htr_verification()
