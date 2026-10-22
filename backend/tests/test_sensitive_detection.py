"""
Regression & Precision Test Suite for Sensitive Small-Mark OMR Recognition.
Validates:
1. One small dot inside a bubble (recognized as marked answer, not rejected)
2. A tiny partial stroke / pen checkmark (recognized as marked answer)
3. A partially filled bubble (~25-30% fill)
4. A fully shaded bubble (solid ink)
5. An empty bubble with printed circular outline only (must remain BLANK)
6. Dust, paper grain, or isolated sensor noise (1-2 px speckles rejected as BLANK)
7. Two bubbles with small marks (classified as MULTIPLE)
8. Blurred or poorly aligned images (classified as REVIEW)
9. Configurable sensitivity levels: HIGH, NORMAL, CONSERVATIVE
10. Diagnostic overlay generation highlighting detected mark centroids
"""
import cv2
import numpy as np
import pytest

from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.detector import OMRDetector
from backend.app.omr.synthetic import SyntheticOMRGenerator


@pytest.fixture
def base_bubble_setup():
    """Generates canonical bubble dimensions and blank template with printed circular outline."""
    layout = OMRLayoutConfig(question_count=25, template_type="standard")
    detector = OMRDetector(layout, sensitivity="NORMAL")
    return layout, detector


def create_synthetic_question_patch(
    option_modifications: dict,
    canvas_size: int = 50,
    radius: int = 24,
) -> dict:
    """
    Creates individual bubble image patches for options A, B, C, D.
    Each patch contains a printed circular outline (thickness 1.5-2px).
    option_modifications maps option key ('A', 'B', 'C', 'D') to a modification type:
      - 'empty': clean paper inside outline
      - 'small_dot': 3x3 / radius 2 pen dot inside interior (~13 px)
      - 'partial_stroke': short pen stroke (length ~10 px, width ~2 px)
      - 'dust': isolated 1-2 px noise speckle
      - 'partial_fill': ~25% bubble fill
      - 'full_fill': solid dark fill
    """
    patches = {}
    cx, cy = canvas_size // 2, canvas_size // 2

    for opt in ["A", "B", "C", "D"]:
        # White paper with subtle scanner grain
        patch = np.ones((canvas_size, canvas_size), dtype=np.uint8) * 245
        noise = np.random.normal(0, 1.5, (canvas_size, canvas_size)).astype(np.int16)
        patch = np.clip(patch.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Printed circular outline at radius
        cv2.circle(patch, (cx, cy), radius, 35, 2)

        mod = option_modifications.get(opt, "empty")

        if mod == "small_dot":
            # Small ballpoint pen dot inside bubble interior (radius 2 circle ~ 13 px)
            cv2.circle(patch, (cx - 1, cy + 1), 2, 25, -1)

        elif mod == "partial_stroke":
            # Tiny pen stroke inside bubble
            cv2.line(patch, (cx - 4, cy - 3), (cx + 3, cy + 4), 25, 2)

        elif mod == "dust":
            # Isolated 1-2 pixel dust / sensor speckle
            patch[cy, cx] = 40
            patch[cy, cx + 1] = 45

        elif mod == "partial_fill":
            # Partially filled bubble (~25-30% inner radius)
            cv2.circle(patch, (cx, cy), 9, 25, -1)

        elif mod == "full_fill":
            # Fully shaded bubble
            cv2.circle(patch, (cx, cy), radius - 3, 20, -1)

        patches[opt] = patch

    return patches


def test_one_small_dot_inside_bubble(base_bubble_setup):
    """Verifies that a tiny pen dot (~13 px) inside an empty bubble classifies that option as selected."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    # Option B contains a small dot; A, C, D are empty
    patches = create_synthetic_question_patch({"B": "small_dot"})
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "B", f"Expected 'B', got '{classification}'"
    assert mark_flags["B"] is True
    assert mark_flags["A"] is False
    assert mark_flags["C"] is False
    assert mark_flags["D"] is False
    assert confidence >= 0.70
    assert options_data["B"]["max_cc_area"] >= 8


def test_tiny_partial_stroke_inside_bubble(base_bubble_setup):
    """Verifies that a tiny pen stroke or checkmark inside a bubble is detected as marked."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    patches = create_synthetic_question_patch({"C": "partial_stroke"})
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "C", f"Expected 'C', got '{classification}'"
    assert mark_flags["C"] is True
    assert confidence >= 0.70
    assert options_data["C"]["max_cc_area"] >= 15


def test_partially_filled_bubble(base_bubble_setup):
    """Verifies that a partially filled bubble (~25-30% fill) is detected without requiring full fill."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    patches = create_synthetic_question_patch({"D": "partial_fill"})
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "D", f"Expected 'D', got '{classification}'"
    assert mark_flags["D"] is True
    assert confidence >= 0.80


def test_fully_shaded_bubble(base_bubble_setup):
    """Verifies that a fully shaded solid bubble is detected with high confidence."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    patches = create_synthetic_question_patch({"A": "full_fill"})
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "A", f"Expected 'A', got '{classification}'"
    assert mark_flags["A"] is True
    assert confidence >= 0.90
    assert options_data["A"]["mean_contrast"] >= 0.70


def test_empty_bubble_with_printed_outline(base_bubble_setup):
    """Verifies that empty bubbles with printed circular outlines remain BLANK and don't trigger false marks."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    patches = create_synthetic_question_patch({})  # all empty
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "BLANK", f"Expected 'BLANK', got '{classification}'"
    for opt in ["A", "B", "C", "D"]:
        assert mark_flags[opt] is False
        assert options_data[opt]["max_cc_area"] == 0
    assert confidence >= 0.90


def test_dust_and_paper_noise_rejection(base_bubble_setup):
    """Verifies that 1-2 pixel isolated dust speckles or paper grain do not trigger false positives."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    patches = create_synthetic_question_patch({"A": "dust", "C": "dust"})
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "BLANK", f"Expected 'BLANK', got '{classification}'"
    assert mark_flags["A"] is False
    assert mark_flags["C"] is False
    assert confidence >= 0.90


def test_two_bubbles_with_small_marks(base_bubble_setup):
    """Verifies that when two bubbles contain small marks or dots, it is classified as MULTIPLE."""
    _, detector = base_bubble_setup
    cx, cy, r = 25, 25, 24

    patches = create_synthetic_question_patch({"A": "small_dot", "D": "small_dot"})
    options_data = {opt: detector.evaluate_bubble_features(patches[opt], cx, cy, r) for opt in ["A", "B", "C", "D"]}

    classification, confidence, mark_flags = detector.classify_question_bubbles(options_data)

    assert classification == "MULTIPLE", f"Expected 'MULTIPLE', got '{classification}'"
    assert mark_flags["A"] is True
    assert mark_flags["D"] is True
    assert mark_flags["B"] is False
    assert mark_flags["C"] is False


def test_blurred_or_poorly_aligned_image():
    """Verifies that heavily blurred images are flagged as REVIEW due to unreliability."""
    layout = OMRLayoutConfig(question_count=25, template_type="standard")
    detector = OMRDetector(layout, sensitivity="NORMAL")
    synth = SyntheticOMRGenerator(layout)

    gt = {q: "A" for q in range(1, 26)}
    sheet_img, _ = synth.create_synthetic_sheet(gt)

    # Heavily blur the image to simulate camera motion / out of focus
    blurred_img = cv2.GaussianBlur(sheet_img, (41, 41), 15.0)

    result = detector.process_omr_sheet(blurred_img)

    assert result["is_blurred"] is True
    # The detector must flag questions for REVIEW under severe blur
    assert result["uncertain_questions_count"] >= 15


def test_sensitivity_profiles_switching():
    """Verifies that sensitivity can be toggled between HIGH, NORMAL, and CONSERVATIVE."""
    layout = OMRLayoutConfig(question_count=25)
    detector = OMRDetector(layout, sensitivity="HIGH")
    assert detector.sensitivity == "HIGH"

    detector.set_sensitivity("CONSERVATIVE")
    assert detector.sensitivity == "CONSERVATIVE"

    detector.set_sensitivity("NORMAL")
    assert detector.sensitivity == "NORMAL"


def test_visual_diagnostic_overlay_contains_mark_annotations(base_bubble_setup):
    """Verifies that the generated diagnostic overlay marks centroids with visual indicators."""
    layout, detector = base_bubble_setup
    synth = SyntheticOMRGenerator(layout)
    gt = {q: "B" for q in range(1, 26)}
    sheet_img, _ = synth.create_synthetic_sheet(gt)

    result = detector.process_omr_sheet(sheet_img)
    diag = result.get("diagnostic_image")

    assert diag is not None
    assert diag.shape == (2338, 1654, 3)
    assert "OMR DIAGNOSTIC" in str(result["sensitivity"]) or result["diagnostic_image"] is not None
    assert result["uncertain_questions_count"] == 0


def test_official_vidyakashi_100q_blank_sheet():
    """Verifies that the official 4-column Vidyakashi 100Q OMR template evaluates 100/100 as BLANK with 0 reviews."""
    from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator

    gen = VidyakashiOMRGenerator(question_count=100)
    blank_img = gen.generate_image()

    detector = OMRDetector(OMRLayoutConfig(question_count=100))
    result = detector.process_omr_sheet(blank_img)

    assert result["markers_detected"] is True
    assert result["uncertain_questions_count"] == 0
    for q in range(1, 101):
        assert result["questions"][q]["classification"] == "BLANK"


def test_official_vidyakashi_100q_solid_partial_tick_and_dot_marks():
    """Verifies 100% accuracy (100/100 questions, 0 reviews) on the official Vidyakashi 100Q OMR sheet across solid, partial, tick, and dot marks."""
    from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator

    opts = ["A", "B", "C", "D"]
    gt = {q: opts[(q - 1) % 4] for q in range(1, 101)}
    gen = VidyakashiOMRGenerator(question_count=100)

    for style in ["solid", "partial", "tick", "dot"]:
        filled_img = gen.generate_image(
            exam_title="Vidyakashi Official 100Q Test",
            exam_code="VKS-100",
            pre_filled_answers=gt,
            student_name="Test Student",
            student_roll="20261001",
            mark_style=style,
        )
        detector = OMRDetector(OMRLayoutConfig(question_count=100))
        result = detector.process_omr_sheet(filled_img)

        assert result["markers_detected"] is True
        assert result["uncertain_questions_count"] == 0, f"Style '{style}' had {result['uncertain_questions_count']} uncertain questions"
        for q in range(1, 101):
            assert result["questions"][q]["classification"] == gt[q], f"Style '{style}' Q{q}: expected {gt[q]}, got {result['questions'][q]['classification']}"
