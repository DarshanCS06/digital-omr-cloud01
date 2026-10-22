import pytest
from backend.app.models.submission import Submission, SubmissionStatus, DetectedResponse, OptionClassification
from backend.app.models.batch import UploadBatch, UploadedImage, BatchStatus, ImageStatus


def test_examination_creation_and_cross_access(client, teacher_headers, second_teacher_headers, admin_headers):
    # 1. Teacher 1 creates an exam
    create_payload = {
        "code": "MATH-2026",
        "title": "Final Mathematics Examination",
        "subject": "Mathematics",
        "class_grade": "Grade 10",
        "exam_date": "2026-10-21",
        "question_count": 50,
        "options_per_question": 4,
        "positive_marks": 1.0,
        "negative_marks": 0.25,
        "blank_marks": 0.0,
        "multiple_penalty": 0.25,
        "initial_answers": {"1": "A", "2": "B", "3": "C"}
    }
    resp = client.post("/api/examinations", json=create_payload, headers=teacher_headers)
    assert resp.status_code == 201
    exam_data = resp.json()
    exam_id = exam_data["id"]

    # 2. Teacher 1 can access it
    resp_t1 = client.get(f"/api/examinations/{exam_id}", headers=teacher_headers)
    assert resp_t1.status_code == 200

    # 3. Teacher 2 CANNOT access it (403 Forbidden)
    resp_t2 = client.get(f"/api/examinations/{exam_id}", headers=second_teacher_headers)
    assert resp_t2.status_code == 403

    # 4. Admin CAN access it
    resp_admin = client.get(f"/api/examinations/{exam_id}", headers=admin_headers)
    assert resp_admin.status_code == 200

    # 5. Admin assigns Teacher 2 to this exam
    # Get Teacher 2 id from token
    # Let's assign teacher 2 via /assign
    # Get teacher 2 id
    t2_profile = client.get("/api/auth/me", headers=second_teacher_headers).json()
    t2_id = t2_profile["id"]

    assign_resp = client.post(
        f"/api/examinations/{exam_id}/assign",
        json={"teacher_ids": [t2_id]},
        headers=admin_headers
    )
    assert assign_resp.status_code == 200

    # 6. Now Teacher 2 CAN access it!
    resp_t2_assigned = client.get(f"/api/examinations/{exam_id}", headers=second_teacher_headers)
    assert resp_t2_assigned.status_code == 200


def test_review_override_workflow(client, db_session, teacher_user, teacher_headers):
    # Setup exam
    exam_payload = {
        "code": "SCI-101",
        "title": "General Science Test",
        "subject": "Science",
        "class_grade": "Grade 9",
        "exam_date": "2026-10-21",
        "question_count": 10,
        "initial_answers": {"1": "B", "2": "A"}
    }
    exam_resp = client.post("/api/examinations", json=exam_payload, headers=teacher_headers)
    exam_id = exam_resp.json()["id"]

    # Create dummy batch and image
    batch = UploadBatch(examination_id=exam_id, user_id=teacher_user.id, status=BatchStatus.COMPLETED)
    db_session.add(batch)
    db_session.commit()

    img = UploadedImage(
        batch_id=batch.id,
        examination_id=exam_id,
        original_filename="sheet1.jpg",
        storage_key="uploads/dummy.jpg",
        file_hash="dummyhash123",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        status=ImageStatus.COMPLETED
    )
    db_session.add(img)
    db_session.commit()

    # Create submission needing review
    sub = Submission(
        examination_id=exam_id,
        uploaded_image_id=img.id,
        detected_roll_number="123456",
        status=SubmissionStatus.NEEDS_REVIEW,
        total_score=0.0,
        max_score=10.0,
        review_count=1
    )
    db_session.add(sub)
    db_session.commit()

    # Response for Q1 was REVIEW
    dr = DetectedResponse(
        submission_id=sub.id,
        question_number=1,
        detected_option=OptionClassification.REVIEW,
        confidence_score=0.4,
    )
    db_session.add(dr)
    db_session.commit()

    # Check review queue
    q_resp = client.get(f"/api/reviews/exam/{exam_id}", headers=teacher_headers)
    assert q_resp.status_code == 200
    queue = q_resp.json()
    assert len(queue) >= 1

    # Override Q1 to "B" (correct answer)
    override_payload = {
        "question_number": 1,
        "selected_option": "B",
        "reason": "Student shaded bubble faintly with blue ink, clearly intended B"
    }
    ov_resp = client.post(
        f"/api/reviews/override/{sub.id}",
        json=override_payload,
        headers=teacher_headers
    )
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()
    assert ov_data["remaining_review_count"] == 0
    assert ov_data["new_score"] == 1.0  # Correct answer awarded


def test_export_reports(client, teacher_headers):
    # Create simple exam
    exam_payload = {
        "code": "EXP-2026",
        "title": "Export Test Exam",
        "subject": "English",
        "class_grade": "Grade 11",
        "exam_date": "2026-10-21",
        "question_count": 25,
        "initial_answers": {"1": "A"}
    }
    exam_resp = client.post("/api/examinations", json=exam_payload, headers=teacher_headers)
    exam_id = exam_resp.json()["id"]

    # Test CSV export
    csv_resp = client.get(f"/api/reports/csv/{exam_id}", headers=teacher_headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Examination Results Report" in csv_resp.text

    # Test Excel export
    excel_resp = client.get(f"/api/reports/excel/{exam_id}", headers=teacher_headers)
    assert excel_resp.status_code == 200
    assert "spreadsheetml" in excel_resp.headers["content-type"]
    assert len(excel_resp.content) > 1000
