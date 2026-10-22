"""
Comprehensive test suite for Photo Quality Validation, Automatic Alignment,
Template Matching, and Detection Accuracy across:
1. Straight OMR images
2. Tilted OMR images (skewed in-plane rotation)
3. Rotated OMR images (90° landscape and 180° upside-down)
4. Blurry OMR images
5. Dark / underexposed OMR images
6. Shadowed / uneven lighting OMR images
7. Cropped / incomplete OMR images
8. Template mismatch OMR images (25Q sheet uploaded to 100Q exam)
"""
import cv2
import numpy as np
import pytest

from backend.app.omr.layout import OMRLayoutConfig, CANONICAL_WIDTH, CANONICAL_HEIGHT
from backend.app.omr.preprocessor import ImagePreprocessor
from backend.app.omr.detector import OMRDetector
from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator
from backend.app.omr.synthetic import SyntheticOMRGenerator


def _verified_25q_answers():
    opts = ["A", "B", "C", "D"]
    return {q: opts[(q - 1) % 4] for q in range(1, 26)}


def _create_straight_vidyakashi_sheet(answers_map):
    gen = VidyakashiOMRGenerator(question_count=25)
    return gen.generate_image(
        exam_title="Quality & Alignment Benchmark",
        exam_code="VKS-ALIGN",
        subject="Mathematics",
        class_grade="10th",
        exam_date="22/10/2026",
        pre_filled_answers=answers_map,
        student_name="Rahul Gowda",
        student_roll="250710003",
        mark_style="solid",
    )


def test_1_straight_omr_image_accuracy():
    """1. Straight OMR sheet passes all quality checks and achieves 100% detection accuracy."""
    gt = _verified_25q_answers()
    sheet = _create_straight_vidyakashi_sheet(gt)

    quality = ImagePreprocessor.assess_quality(sheet)
    assert quality["is_acceptable"] is True
    assert quality["is_blurry"] is False
    assert quality["is_too_dark"] is False
    assert quality["is_cropped"] is False

    detector = OMRDetector(OMRLayoutConfig(question_count=25, template_type="vidyakashi_official"))
    res = detector.process_omr_sheet(sheet, answer_key={str(k): v for k, v in gt.items()})

    assert res["markers_detected"] is True
    assert res["alignment_info"]["template_matches"] is True
    assert res["alignment_info"]["regions_visible"] is True

    matches = sum(1 for q, ans in gt.items() if res["questions"][q]["classification"] == ans)
    accuracy = (matches / 25.0) * 100.0
    assert accuracy == 100.0


def test_2_tilted_omr_image_alignment_and_accuracy():
    """2. Tilted OMR sheet (5° skew) is detected as tilted, aligned automatically, and achieves 100% accuracy."""
    gt = _verified_25q_answers()

    # Case A: Tilted Vidyakashi sheet (5.0° skew) aligned via orient_and_deskew_image
    vks_straight = _create_straight_vidyakashi_sheet(gt)
    vh, vw = vks_straight.shape[:2]
    vks_rot = cv2.getRotationMatrix2D((vw / 2.0, vh / 2.0), 5.0, 1.0)
    vks_tilted = cv2.warpAffine(
        vks_straight,
        vks_rot,
        (vw, vh),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    q_tilted = ImagePreprocessor.assess_quality(vks_tilted)
    assert q_tilted["is_tilted"] is True
    assert q_tilted["validation_message"] == "The OMR sheet is tilted. Aligning the image..."

    det_vks = OMRDetector(OMRLayoutConfig(question_count=25, template_type="vidyakashi_official"))
    res_vks = det_vks.process_omr_sheet(vks_tilted, answer_key={str(k): v for k, v in gt.items()})
    assert res_vks["alignment_info"]["was_tilted"] is True
    assert res_vks["alignment_info"]["alignment_message"] == "The OMR sheet is tilted. Aligning the image..."
    vks_matches = sum(1 for q, ans in gt.items() if res_vks["questions"][q]["classification"] == ans)
    assert vks_matches == 25

    # Case B: Tilted 4-marker sheet (5.0° skew) aligned via 4-marker perspective rectification
    synth = SyntheticOMRGenerator(OMRLayoutConfig(question_count=25))
    straight_sheet, _ = synth.create_synthetic_sheet(
        ground_truth=gt,
        roll_number="250710",
        apply_distortion=False,
    )
    h, w = straight_sheet.shape[:2]
    rot_mat = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), 5.0, 0.86)
    tilted_sheet = cv2.warpAffine(
        straight_sheet,
        rot_mat,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    detector = OMRDetector(OMRLayoutConfig(question_count=25))
    res = detector.process_omr_sheet(tilted_sheet, answer_key={str(k): v for k, v in gt.items()})

    assert res["markers_detected"] is True
    assert res["alignment_info"]["was_tilted"] is True
    assert res["alignment_info"]["alignment_message"] == "The OMR sheet is tilted. Aligning the image..."
    assert res["alignment_info"]["template_matches"] is True
    assert res["alignment_info"]["regions_visible"] is True

    matches = sum(1 for q, ans in gt.items() if res["questions"][q]["classification"] == ans)
    accuracy = (matches / 25.0) * 100.0
    assert accuracy == 100.0


def test_3_rotated_90_and_180_omr_images():
    """3. Rotated (90° landscape and 180° upside-down) OMR sheets are oriented upright with 100% accuracy."""
    gt = _verified_25q_answers()
    sheet = _create_straight_vidyakashi_sheet(gt)

    # 90° clockwise rotation (landscape)
    rotated_90 = cv2.rotate(sheet, cv2.ROTATE_90_CLOCKWISE)
    q90 = ImagePreprocessor.assess_quality(rotated_90)
    assert q90["is_landscape"] is True
    assert q90["validation_message"] == "The OMR sheet is tilted. Aligning the image..."

    det_90 = OMRDetector(OMRLayoutConfig(question_count=25, template_type="vidyakashi_official"))
    res_90 = det_90.process_omr_sheet(rotated_90)
    assert res_90["alignment_info"]["was_tilted"] is True
    assert res_90["alignment_info"]["rotation_deg"] in (90, 270)
    matches_90 = sum(1 for q, ans in gt.items() if res_90["questions"][q]["classification"] == ans)
    assert matches_90 == 25

    # 180° upside-down rotation
    rotated_180 = cv2.rotate(sheet, cv2.ROTATE_180)
    det_180 = OMRDetector(OMRLayoutConfig(question_count=25, template_type="vidyakashi_official"))
    res_180 = det_180.process_omr_sheet(rotated_180)
    assert res_180["alignment_info"]["was_tilted"] is True
    assert res_180["alignment_info"]["rotation_deg"] == 180
    matches_180 = sum(1 for q, ans in gt.items() if res_180["questions"][q]["classification"] == ans)
    assert matches_180 == 25


def test_4_blurry_omr_image_rejected():
    """4. Blurry OMR image is rejected with exact message: 'The image is blurry. Please take another photo.'"""
    gt = _verified_25q_answers()
    sheet = _create_straight_vidyakashi_sheet(gt)
    blurry = cv2.GaussianBlur(sheet, (51, 51), 18.0)

    quality = ImagePreprocessor.assess_quality(blurry)
    assert quality["is_blurry"] is True
    assert quality["is_acceptable"] is False
    assert quality["validation_message"] == "The image is blurry. Please take another photo."


def test_5_dark_omr_image_rejected():
    """5. Dark / underexposed OMR image is rejected with 'Image quality is insufficient for reliable evaluation.'"""
    gt = _verified_25q_answers()
    sheet = _create_straight_vidyakashi_sheet(gt)
    dark = (sheet.astype(np.float32) * 0.22).astype(np.uint8)

    quality = ImagePreprocessor.assess_quality(dark)
    assert quality["is_too_dark"] is True
    assert quality["is_acceptable"] is False
    assert quality["validation_message"] == "Image quality is insufficient for reliable evaluation."


def test_6_shadowed_omr_image_detection_and_accuracy():
    """6. Shadowed OMR image: moderate shadow is detected and accurately evaluated; severe shadow is rejected."""
    gt = _verified_25q_answers()
    sheet = _create_straight_vidyakashi_sheet(gt)
    h, w = sheet.shape[:2]

    # Moderate illumination gradient (top-left bright 1.0, bottom-right shaded 0.62)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    illum_mod = 1.0 - 0.38 * ((xx / w + yy / h) / 2.0)
    shadow_mod = np.clip(sheet.astype(np.float32) * illum_mod[:, :, None], 0, 255).astype(np.uint8)

    q_mod = ImagePreprocessor.assess_quality(shadow_mod)
    assert q_mod["has_shadows"] is True
    assert q_mod["is_acceptable"] is True

    detector = OMRDetector(OMRLayoutConfig(question_count=25, template_type="vidyakashi_official"))
    res_mod = detector.process_omr_sheet(shadow_mod)
    matches = sum(1 for q, ans in gt.items() if res_mod["questions"][q]["classification"] == ans)
    assert matches == 25

    # Severe shadow covering half the sheet in near-black darkness
    illum_sev = np.ones((h, w), dtype=np.float32)
    illum_sev[h // 2 :, :] = 0.08
    shadow_sev = np.clip(sheet.astype(np.float32) * illum_sev[:, :, None], 0, 255).astype(np.uint8)
    q_sev = ImagePreprocessor.assess_quality(shadow_sev)
    assert q_sev["is_severe_shadow"] is True
    assert q_sev["is_acceptable"] is False
    assert q_sev["validation_message"] == "Image quality is insufficient for reliable evaluation."


def test_7_cropped_incomplete_omr_image_rejected():
    """7. Cropped / incomplete OMR image is rejected with 'Part of the answer sheet is missing. Upload the complete sheet.'"""
    gt = _verified_25q_answers()
    sheet = _create_straight_vidyakashi_sheet(gt)
    h, w = sheet.shape[:2]

    # Case A: Dimension crop (bottom 45% cut off)
    cropped_dim = sheet[: int(h * 0.55), :]
    q_crop = ImagePreprocessor.assess_quality(cropped_dim)
    assert q_crop["is_cropped"] is True
    assert q_crop["is_acceptable"] is False
    assert q_crop["validation_message"] == "Part of the answer sheet is missing. Upload the complete sheet."

    # Case B: Answer region missing/occluded inside A4 frame (bottom rows wiped out)
    occluded = sheet.copy()
    occluded[int(h * 0.62) :, :] = 255
    detector = OMRDetector(OMRLayoutConfig(question_count=25, template_type="vidyakashi_official"))
    res_occ = detector.process_omr_sheet(occluded)
    assert res_occ["alignment_info"]["regions_visible"] is False
    assert (
        res_occ["alignment_info"]["validation_error"]
        == "Part of the answer sheet is missing. Upload the complete sheet."
    )


def test_8_template_mismatch_rejected():
    """8. Uploading a 25Q sheet to a 100Q examination stops with 'The sheet layout does not match the selected examination.'"""
    gt = _verified_25q_answers()
    synth_25 = SyntheticOMRGenerator(OMRLayoutConfig(question_count=25))
    sheet_25q, _ = synth_25.create_synthetic_sheet(ground_truth=gt, roll_number="123456", apply_distortion=False)

    # Evaluate 25Q sheet using a 100Q Examination Detector
    detector_100 = OMRDetector(OMRLayoutConfig(question_count=100))
    res = detector_100.process_omr_sheet(sheet_25q)

    assert res["alignment_info"]["template_matches"] is False
    assert (
        res["alignment_info"]["validation_error"]
        == "The sheet layout does not match the selected examination."
    )
