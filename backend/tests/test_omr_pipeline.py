import pytest
import numpy as np
import cv2

from backend.app.omr.layout import OMRLayoutConfig, CANONICAL_WIDTH, CANONICAL_HEIGHT
from backend.app.omr.generator import OMRSheetGenerator
from backend.app.omr.preprocessor import ImagePreprocessor
from backend.app.omr.detector import OMRDetector
from backend.app.omr.synthetic import SyntheticOMRGenerator
from backend.app.omr.calibration import CalibrationUtility


def test_layout_config():
    layout_100 = OMRLayoutConfig(question_count=100)
    assert len(layout_100.bubbles) == 100
    assert len(layout_100.roll_bubbles) == 60  # 6 cols * 10 digits
    assert "top_left" in layout_100.markers
    assert "bottom_right" in layout_100.markers

    layout_50 = OMRLayoutConfig(question_count=50)
    assert len(layout_50.bubbles) == 50

    layout_25 = OMRLayoutConfig(question_count=25)
    assert len(layout_25.bubbles) == 25


def test_pdf_generation():
    layout = OMRLayoutConfig(question_count=100)
    gen = OMRSheetGenerator(layout)
    pdf_bytes = gen.generate_pdf(
        exam_title="Unit Test Examination",
        exam_code="TEST-100",
        subject="Physics",
        class_grade="Grade 12",
        exam_date="2026-10-21"
    )
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_image_preprocessor_validation():
    # Valid JPEG header
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01"
    assert ImagePreprocessor.validate_magic_bytes(valid_jpeg) == "image/jpeg"

    # Valid PNG header
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert ImagePreprocessor.validate_magic_bytes(valid_png) == "image/png"

    # Invalid header (e.g., zip / exe / text)
    with pytest.raises(ValueError):
        ImagePreprocessor.validate_magic_bytes(b"PK\x03\x04\x14\x00\x00\x00")


def test_synthetic_sheet_omr_detection():
    layout = OMRLayoutConfig(question_count=25)
    synth_gen = SyntheticOMRGenerator(layout)
    detector = OMRDetector(layout)

    ground_truth = {
        1: "A", 2: "B", 3: "C", 4: "D",
        5: "BLANK", 6: "MULTIPLE", 7: "A", 8: "C"
    }
    for q in range(9, 26):
        ground_truth[q] = "B"

    sheet_img, _ = synth_gen.create_synthetic_sheet(
        ground_truth=ground_truth,
        roll_number="654321",
        apply_distortion=False
    )

    result = detector.process_omr_sheet(sheet_img)

    assert result["markers_detected"] is True
    assert result["detected_roll_number"] == "654321"

    # Verify detected questions
    q_res = result["questions"]
    assert q_res[1]["classification"] == "A"
    assert q_res[2]["classification"] == "B"
    assert q_res[3]["classification"] == "C"
    assert q_res[4]["classification"] == "D"
    assert q_res[5]["classification"] == "BLANK"
    assert q_res[6]["classification"] == "MULTIPLE"
    assert q_res[7]["classification"] == "A"
    assert q_res[8]["classification"] == "C"


def test_calibration_benchmark():
    calib = CalibrationUtility(question_count=40)
    benchmark_report = calib.run_benchmark()

    assert benchmark_report["total_questions"] == 40
    assert benchmark_report["accuracy_percentage"] >= 85.0
    assert benchmark_report["roll_number_match"] is True
    assert benchmark_report["markers_detected"] is True
