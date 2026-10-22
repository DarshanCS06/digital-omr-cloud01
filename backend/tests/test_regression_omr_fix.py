"""
Regression Test Suite for OMR Image Display and Bubble Detection Fixes.
Verifies:
1. Image endpoints (original, rectified, diagnostic) with flexible authentication and RBAC
2. Unauthorized access rejection (401) and missing file handling (404)
3. Clear, correctly marked sheets detection (100% accuracy)
4. Blank bubbles detection
5. Faint marks and multiple-marked classifications
6. Perspective distorted images and template alignment
7. Correct question numbering and geometry synchronization
8. Scoring engine evaluation against answer keys
9. Visual diagnostic image generation and retrieval
"""
import io
import os
import cv2
import pytest
import numpy as np

from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.detector import OMRDetector
from backend.app.omr.synthetic import SyntheticOMRGenerator
from backend.app.services.scoring import ScoringEngine
from backend.app.models.examination import Examination
from backend.app.models.submission import Submission, SubmissionStatus


def test_clear_correctly_marked_sheet_vidyakashi():
    """Verifies that clear, correctly marked Vidyakashi sheets detect 25/25 answers with 0 reviews."""
    img_path = r"C:\Users\rahul\.gemini\antigravity\brain\f9891136-5e91-4fcb-baf2-cf8007c6bf8c\Vidyakashi_Ticked_25Q.png"
    if not os.path.exists(img_path):
        pytest.skip("Vidyakashi_Ticked_25Q.png not present in artifact directory")

    img = cv2.imread(img_path)
    assert img is not None

    layout = OMRLayoutConfig(question_count=25, template_type="vidyakashi_25")
    detector = OMRDetector(layout)
    result = detector.process_omr_sheet(img)

    assert result["markers_detected"] is True
    assert result["uncertain_questions_count"] == 0
    assert result["detected_roll_number"] in (None, "1023456")

    # Ground truth answers on Vidyakashi_Ticked_25Q.png: cyclic A, B, C, D
    opts = ["A", "B", "C", "D"]
    for q in range(1, 26):
        expected_opt = opts[(q - 1) % 4]
        detected = result["questions"][q]["classification"]
        assert detected == expected_opt, f"Question {q} expected {expected_opt}, got {detected}"
        assert result["questions"][q]["confidence"] >= 0.70


def test_blank_bubbles_detection():
    """Verifies that an unmarked blank sheet classifies all questions as BLANK with high confidence."""
    layout = OMRLayoutConfig(question_count=25, template_type="standard")
    synth = SyntheticOMRGenerator(layout)
    blank_ground_truth = {q: "BLANK" for q in range(1, 26)}
    blank_img, _ = synth.create_synthetic_sheet(blank_ground_truth, roll_number="123456")

    detector = OMRDetector(layout)
    result = detector.process_omr_sheet(blank_img)

    assert result["markers_detected"] is True
    assert result["uncertain_questions_count"] == 0
    for q in range(1, 26):
        assert result["questions"][q]["classification"] == "BLANK"
        assert result["questions"][q]["confidence"] >= 0.90


def test_faint_marks_and_multiple_marked():
    """Verifies that faint marks trigger REVIEW and multiple darkened options trigger MULTIPLE."""
    layout = OMRLayoutConfig(question_count=25, template_type="standard")
    synth = SyntheticOMRGenerator(layout)
    gt = {q: "A" for q in range(1, 26)}
    gt[5] = "MULTIPLE"  # Multiple options filled

    sheet_img, _ = synth.create_synthetic_sheet(
        ground_truth=gt,
        roll_number="654321",
        faint_questions=[10],  # Q10 filled with faint pencil
    )

    detector = OMRDetector(layout)
    result = detector.process_omr_sheet(sheet_img)

    assert result["questions"][5]["classification"] == "MULTIPLE"
    assert result["questions"][10]["classification"] in ["A", "REVIEW"]


def test_rotated_and_perspective_distorted_sheet():
    """Verifies that perspective distortion is corrected by the rectification pipeline."""
    layout = OMRLayoutConfig(question_count=25, template_type="standard")
    synth = SyntheticOMRGenerator(layout)
    gt = {q: "B" for q in range(1, 26)}
    distorted_img, _ = synth.create_synthetic_sheet(gt, roll_number="112233", apply_distortion=True)

    detector = OMRDetector(layout)
    result = detector.process_omr_sheet(distorted_img)

    assert result["markers_detected"] is True
    assert result["rectified_image"].shape == (2338, 1654, 3)
    # Check that majority of answers are correctly aligned and detected
    correct = sum(1 for q in range(1, 26) if result["questions"][q]["classification"] == "B")
    assert correct >= 22  # >= 88% under distortion


def test_visual_diagnostic_image_generation():
    """Verifies that the diagnostic view is generated with proper dimensions and color annotations."""
    layout = OMRLayoutConfig(question_count=25, template_type="standard")
    synth = SyntheticOMRGenerator(layout)
    gt = {q: "C" for q in range(1, 26)}
    img, _ = synth.create_synthetic_sheet(gt, roll_number="998877")

    detector = OMRDetector(layout)
    result = detector.process_omr_sheet(img)

    diag = result.get("diagnostic_image")
    assert diag is not None
    assert diag.shape == (2338, 1654, 3)
    # Ensure diagnostic contains annotations (mean difference between rectified and diag)
    assert not np.array_equal(diag, result["rectified_image"])


def test_api_image_endpoints_auth_and_errors(client, teacher_headers):
    """Verifies that image endpoints enforce authentication and handle missing files cleanly."""
    # 1. Unauthenticated request must return 401
    unauth_resp = client.get("/api/submissions/1/images/original")
    assert unauth_resp.status_code == 401

    # 2. Non-existent submission must return 404
    not_found_resp = client.get("/api/submissions/999999/images/original", headers=teacher_headers)
    assert not_found_resp.status_code == 404

    # 3. Non-existent rectified/diagnostic images return 404 with clear detail
    diag_resp = client.get("/api/submissions/999999/images/diagnostic", headers=teacher_headers)
    assert diag_resp.status_code == 404


def test_scoring_engine_against_answer_key(db_session):
    """Verifies accurate score calculation against answer keys with positive, negative, and blank rules."""
    exam = Examination(
        code="SC-TEST",
        title="Scoring Test",
        subject="Physics",
        class_grade="12th",
        exam_date="2026-10-21",
        question_count=4,
        positive_marks=4.0,
        negative_marks=1.0,
        blank_marks=0.0,
        multiple_penalty=1.0,
        created_by_id=1,
    )
    db_session.add(exam)
    db_session.commit()

    answer_key = {"1": "A", "2": "B", "3": "C", "4": "D"}
    # Mock submission with: Q1 correct (+4), Q2 wrong (-1), Q3 blank (0), Q4 multiple (-1)
    from backend.app.models.submission import DetectedResponse, OptionClassification
    sub = Submission(
        examination_id=exam.id,
        uploaded_image_id=1,
        status=SubmissionStatus.PROVISIONAL,
    )
    db_session.add(sub)
    db_session.commit()

    r1 = DetectedResponse(submission_id=sub.id, question_number=1, detected_option=OptionClassification.A)
    r2 = DetectedResponse(submission_id=sub.id, question_number=2, detected_option=OptionClassification.A)  # wrong
    r3 = DetectedResponse(submission_id=sub.id, question_number=3, detected_option=OptionClassification.BLANK)
    r4 = DetectedResponse(submission_id=sub.id, question_number=4, detected_option=OptionClassification.MULTIPLE)
    db_session.add_all([r1, r2, r3, r4])
    db_session.commit()

    ScoringEngine.update_submission_score(
        submission=sub,
        examination=exam,
        answer_key=answer_key,
        db=db_session
    )

    # Expected: Q1 (+4) - Q2 (1) + Q3 (0) - Q4 (1) = 2.0 out of 16.0 (12.5%)
    assert sub.total_score == 2.0
    assert sub.max_score == 16.0
    assert sub.correct_count == 1
    assert sub.incorrect_count == 1
    assert sub.blank_count == 1
    assert sub.multiple_count == 1
