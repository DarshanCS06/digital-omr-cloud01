import urllib.request
import urllib.parse
import json
import time

BASE_URL = "https://vidyakashi-digital-omr.onrender.com"
RENDER_API_KEY = "rnd_781tXXA4tD1x07uYnGmPyVonzSWY"
SERVICE_ID = "srv-dbd2qoon74is7380jgkg"

def api_call(endpoint, method="GET", json_data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if json_data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_data).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}

def run_persistence_test():
    print("=" * 65)
    print("VIDYAKASHI DIGITAL OMR CLOUD: DATABASE PERSISTENCE VERIFICATION")
    print(f"Target Live Site: {BASE_URL}")
    print("=" * 65)

    # 1. Login as teacher
    print("\n[STEP 1] Authenticating teacher account...")
    login_res = api_call("/api/auth/login", method="POST", json_data={"email": "teacher@digitalomr.edu", "password": "Teacher1234!"})
    token = login_res["access_token"]
    print("[PASS] Teacher logged in successfully.")

    # 2. Check initial examinations (ensure existing data is intact)
    initial_exams = api_call("/api/examinations", method="GET", token=token)
    print(f"[INFO] Initial examinations in database: {len(initial_exams)}")
    for e in initial_exams:
        print(f"       - #{e['id']}: {e['code']} - {e['title']}")

    # 3. Create examination PERSISTENCE TEST
    print("\n[STEP A-C] Creating examination 'PERSISTENCE TEST' with 10 questions & known key...")
    test_code = f"PTEST-{int(time.time()) % 10000}"
    known_answer_key = {
        "1": "A", "2": "B", "3": "C", "4": "D", "5": "A",
        "6": "B", "7": "C", "8": "D", "9": "A", "10": "B"
    }
    exam_payload = {
        "code": test_code,
        "title": "PERSISTENCE TEST",
        "subject": "General Science",
        "class_grade": "10th",
        "exam_date": "2026-10-24",
        "question_count": 10,
        "options_per_question": 4,
        "positive_marks": 1.0,
        "negative_marks": 0.25,
        "blank_marks": 0.0,
        "multiple_penalty": 0.25,
        "allow_teacher_override": True,
        "is_published": True,
        "initial_answers": known_answer_key
    }
    created_exam = api_call("/api/examinations", method="POST", json_data=exam_payload, token=token)
    test_exam_id = created_exam["id"]
    print(f"[PASS] Examination saved to PostgreSQL: ID #{test_exam_id}, Code: {created_exam['code']}, Title: '{created_exam['title']}'")

    # 4. Verify answer key
    ak_res = api_call(f"/api/examinations/{test_exam_id}/answer-key", method="GET", token=token)
    assert ak_res["answers"] == known_answer_key, f"Answer key mismatch: {ak_res['answers']}"
    print(f"[PASS] Answer key verified: all 10 questions saved with exact values.")

    # 5. Navigate to dashboard (verify stats endpoint)
    print("\n[STEP D] Navigating to Dashboard...")
    stats = api_call("/api/dashboard/stats", method="GET", token=token)
    print(f"[PASS] Dashboard stats loaded: total_examinations={stats['total_examinations']}")

    # 6. Return to examinations page
    print("\n[STEP E] Returning to Examinations page...")
    exams_after_nav = api_call("/api/examinations", method="GET", token=token)
    found = any(e["id"] == test_exam_id for e in exams_after_nav)
    assert found, "Created examination missing after navigation!"
    print(f"[PASS] Examination #{test_exam_id} found in list after navigation.")

    # 7. Refresh browser (fresh HTTP request session)
    print("\n[STEP F] Simulating browser refresh (cold request)...")
    time.sleep(1)
    refreshed_exams = api_call("/api/examinations", method="GET", token=token)
    found_refreshed = any(e["id"] == test_exam_id for e in refreshed_exams)
    assert found_refreshed, "Created examination missing after refresh!"
    print(f"[PASS] Examination #{test_exam_id} persists across page refresh.")

    # 8. Log out and log back in
    print("\n[STEP G] Logging out and logging back in...")
    token = None  # discard token
    relogin_res = api_call("/api/auth/login", method="POST", json_data={"email": "teacher@digitalomr.edu", "password": "Teacher1234!"})
    new_token = relogin_res["access_token"]
    relogin_exams = api_call("/api/examinations", method="GET", token=new_token)
    found_relogin = any(e["id"] == test_exam_id for e in relogin_exams)
    assert found_relogin, "Created examination missing after relogin!"
    print(f"[PASS] Examination #{test_exam_id} persists after logout and relogin.")

    # 9. Trigger Backend Restart on Render
    print("\n[STEP H] Restarting backend service on Render...")
    restart_req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE_ID}/restart",
        data=b"{}",
        headers={"Authorization": f"Bearer {RENDER_API_KEY}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(restart_req) as r:
        print(f"[INFO] Render restart triggered: HTTP {r.status}")

    # Wait for backend to finish restarting and become healthy
    print("[INFO] Waiting for service to restart and become available...")
    for attempt in range(25):
        time.sleep(4)
        try:
            health = api_call("/api/health")
            if health.get("status") == "healthy":
                print(f"[PASS] Backend restarted and healthy after {(attempt + 1) * 4}s.")
                break
        except Exception:
            pass

    # 10. Verify persistence after backend restart
    print("\n[STEP I] Verifying examination and answer key persistence after backend restart...")
    post_restart_login = api_call("/api/auth/login", method="POST", json_data={"email": "teacher@digitalomr.edu", "password": "Teacher1234!"})
    post_token = post_restart_login["access_token"]

    final_exams = api_call("/api/examinations", method="GET", token=post_token)
    target_exam = next((e for e in final_exams if e["id"] == test_exam_id), None)
    assert target_exam is not None, f"CRITICAL: Examination #{test_exam_id} disappeared after backend restart!"
    print(f"[PASS] Examination #{test_exam_id} ('{target_exam['title']}') survives backend restart!")

    target_ak = api_call(f"/api/examinations/{test_exam_id}/answer-key", method="GET", token=post_token)
    assert target_ak["answers"] == known_answer_key, f"CRITICAL: Answer key corrupted after restart: {target_ak}"
    print(f"[PASS] All 10 answer key entries survived restart with 100% fidelity:")
    print(f"       Answers: {target_ak['answers']}")

    # 11. Verify pre-existing data is also intact
    navodaya = next((e for e in final_exams if "NAVODAYA" in e["title"]), None)
    assert navodaya is not None, "Pre-existing NAVODAYA exam was lost!"
    print(f"[PASS] Pre-existing exam #{navodaya['id']} ('{navodaya['title']}') is fully intact.")

    print("\n" + "=" * 65)
    print("ALL PRODUCTION PERSISTENCE TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 65)

if __name__ == "__main__":
    run_persistence_test()
