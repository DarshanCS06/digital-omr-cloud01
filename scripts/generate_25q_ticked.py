import os
import sys
import cv2
import numpy as np

sys.path.insert(0, r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud")

from backend.app.omr.layout import OMRLayoutConfig, CANONICAL_WIDTH, CANONICAL_HEIGHT
from backend.app.omr.generator import OMRSheetGenerator
from backend.app.omr.detector import OMRDetector

out_dir = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated"
artifact_dir = r"C:\Users\rahul\.gemini\antigravity\brain\f9891136-5e91-4fcb-baf2-cf8007c6bf8c"
os.makedirs(out_dir, exist_ok=True)
os.makedirs(artifact_dir, exist_ok=True)

# 1. Setup 25-question layout (single clear column)
layout_25 = OMRLayoutConfig(question_count=25)

# 2. Generate clean vector PDF for 25 questions
gen_25 = OMRSheetGenerator(layout_25)
pdf_bytes = gen_25.generate_pdf(
    exam_title="Digital OMR Cloud - 25 Questions Assessment",
    exam_code="OMR-25Q-TEST",
    subject="Mathematics / Science",
    class_grade="Grade 10",
    exam_date="2026-10-21",
    sheet_id="SHEET-25Q-001"
)
pdf_path = os.path.join(out_dir, "Sample_OMR_25Q.pdf")
with open(pdf_path, "wb") as f:
    f.write(pdf_bytes)
with open(os.path.join(artifact_dir, "Sample_OMR_25Q.pdf"), "wb") as f:
    f.write(pdf_bytes)

# 3. Create High-Resolution 25Q Base Image
img_blank = np.ones((CANONICAL_HEIGHT, CANONICAL_WIDTH, 3), dtype=np.uint8) * 255

# Corner registration markers
half_m = layout_25.marker_size // 2
for name, (cx, cy) in layout_25.markers.items():
    cv2.rectangle(img_blank, (cx - half_m, cy - half_m), (cx + half_m, cy + half_m), (10, 10, 10), -1)

# Header Title & Instructions
cv2.putText(img_blank, "DIGITAL OMR CLOUD - 25 QUESTIONS ANSWER SHEET", (120, 130), cv2.FONT_HERSHEY_DUPLEX, 0.95, (15, 15, 15), 2)
cv2.putText(img_blank, "EXAM CODE: OMR-25Q-TEST  |  SUBJECT: ASSESSMENT  |  QUESTIONS: 25 ONLY", (120, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1)

cv2.putText(img_blank, "STUDENT NAME: ________________________________________________", (120, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)
cv2.putText(img_blank, "INSTRUCTIONS: Use dark pen. 25 Multiple Choice Questions (A, B, C, D).", (120, 245), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1)
cv2.putText(img_blank, "Ensure corner squares are clearly printed and unsoiled.", (120, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1)

# Roll Number Matrix (Roll: 102534)
cv2.putText(img_blank, "ROLL NUMBER", (760, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (20, 20, 20), 2)
for col in range(layout_25.roll_digit_count):
    bx = 760 + (col * 38) - 10
    by = 148
    cv2.rectangle(img_blank, (bx, by), (bx + 26, by + 20), (50, 50, 50), 1)

for rb in layout_25.roll_bubbles:
    cv2.circle(img_blank, (rb.cx, rb.cy), rb.radius, (40, 40, 40), 1)
    cv2.putText(img_blank, str(rb.digit), (rb.cx - 4, rb.cy + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (60, 60, 60), 1)

# QR box
qr_box = layout_25.qr_box
cv2.rectangle(img_blank, (qr_box["x"], qr_box["y"]), (qr_box["x"] + qr_box["width"], qr_box["y"] + qr_box["height"]), (20, 20, 20), 2)
cv2.putText(img_blank, "OMR-25Q", (qr_box["x"] + 45, qr_box["y"] + 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 2)

# Dividing line
cv2.line(img_blank, (100, 410), (layout_25.width - 100, 410), (30, 30, 30), 2)

# Questions 1 to 25
for q_num, opt_map in layout_25.bubbles.items():
    first_b = next(iter(opt_map.values()))
    cv2.putText(img_blank, f"Q{q_num:02d}.", (first_b.cx - 65, first_b.cy + 5), cv2.FONT_HERSHEY_DUPLEX, 0.55, (20, 20, 20), 1)
    for opt_key, bubble in opt_map.items():
        cv2.circle(img_blank, (bubble.cx, bubble.cy), bubble.radius, (40, 40, 40), 1)
        cv2.putText(img_blank, opt_key, (bubble.cx - 4, bubble.cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (60, 60, 60), 1)

footer = "Digital OMR Cloud | Template: OMR-A4-25Q-V1 | 25 Questions Assessment Sheet | 100% Print Scale"
cv2.putText(img_blank, footer, (CANONICAL_WIDTH // 2 - 380, CANONICAL_HEIGHT - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100), 1)

# Save clean blank 25Q sheet
blank_25q_path = os.path.join(out_dir, "OMR_Sheet_25Q_Blank.png")
cv2.imwrite(blank_25q_path, img_blank)
cv2.imwrite(os.path.join(artifact_dir, "OMR_Sheet_25Q_Blank.png"), img_blank)

# 4. Now create the 25 QUESTIONS ONLY TICKED ANSWER Sheet!
img_ticked = img_blank.copy()

# Fill roll number with pen shade: 1 0 2 5 3 4
roll_digits = [1, 0, 2, 5, 3, 4]
for col_idx, dig in enumerate(roll_digits):
    rb = next(b for b in layout_25.roll_bubbles if b.column_index == col_idx and b.digit == dig)
    cv2.circle(img_ticked, (rb.cx, rb.cy), rb.radius - 2, (15, 15, 20), -1)

# Ticked Answer Key pattern for all 25 questions
# Pattern: A, B, C, D, A, B, C, D, ...
target_options = ["A", "B", "C", "D"] * 7
ticked_ground_truth = {}

for q_num in range(1, 26):
    opt = target_options[q_num - 1]
    ticked_ground_truth[q_num] = opt
    bubble = layout_25.bubbles[q_num][opt]
    
    # Draw a distinct, realistic pen checkmark / tick mark (?) across the bubble
    # Short down stroke: (cx - 7, cy) -> (cx - 1, cy + 7)
    # Long up stroke:   (cx - 1, cy + 7) -> (cx + 10, cy - 9)
    pt1 = (bubble.cx - 7, bubble.cy)
    pt2 = (bubble.cx - 1, bubble.cy + 7)
    pt3 = (bubble.cx + 10, bubble.cy - 9)
    
    # Draw tick mark in dark blue / black pen with anti-aliasing
    cv2.line(img_ticked, pt1, pt2, (150, 20, 20), 3, cv2.LINE_AA)  # Blue pen BGR
    cv2.line(img_ticked, pt2, pt3, (150, 20, 20), 3, cv2.LINE_AA)

ticked_png_path = os.path.join(out_dir, "OMR_Sheet_25Q_Ticked_Answers.png")
ticked_artifact_path = os.path.join(artifact_dir, "OMR_Sheet_25Q_Ticked_Answers.png")
cv2.imwrite(ticked_png_path, img_ticked)
cv2.imwrite(ticked_artifact_path, img_ticked)

# 5. Run OMR Detector on the ticked sheet to verify CV detection behavior
detector_25 = OMRDetector(layout_25)
det_res = detector_25.process_omr_sheet(img_ticked)

print("25-Question OMR Sheets Generated:")
print("1. Blank 25Q PNG:", blank_25q_path)
print("2. 25 Ticked Answers PNG:", ticked_png_path)
print("3. Vector PDF (25Q):", pdf_path)
print(f"Detector Roll Number Read: {det_res['detected_roll_number']} (Expected: 102534)")
print(f"Uncertain / Review Questions flagged: {det_res['uncertain_questions_count']}")

# Sample first 5 detected answers
for q in range(1, 6):
    info = det_res['questions'][q]
    print(f"Q{q:02d}: Detected = {info['classification']} (Expected {ticked_ground_truth[q]}), Conf = {info['confidence']}, Densities = {info['densities']}")
