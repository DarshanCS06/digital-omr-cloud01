import os
import sys
import cv2
import numpy as np

sys.path.insert(0, r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud")

from backend.app.omr.layout import OMRLayoutConfig, CANONICAL_WIDTH, CANONICAL_HEIGHT
from backend.app.omr.generator import OMRSheetGenerator

# 1. Output paths
out_dir = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated"
artifact_dir = r"C:\Users\rahul\.gemini\antigravity\brain\f9891136-5e91-4fcb-baf2-cf8007c6bf8c"
os.makedirs(out_dir, exist_ok=True)
os.makedirs(artifact_dir, exist_ok=True)

layout = OMRLayoutConfig(question_count=100)

# 2. Render blank clean OMR sheet image
img = np.ones((CANONICAL_HEIGHT, CANONICAL_WIDTH, 3), dtype=np.uint8) * 255

# 4 Corner registration squares
half_m = layout.marker_size // 2
for name, (cx, cy) in layout.markers.items():
    cv2.rectangle(img, (cx - half_m, cy - half_m), (cx + half_m, cy + half_m), (10, 10, 10), -1)

# Header Title & Instructions
cv2.putText(img, "DIGITAL OMR CLOUD - OFFICIAL ANSWER SHEET", (120, 130), cv2.FONT_HERSHEY_DUPLEX, 0.95, (15, 15, 15), 2)
cv2.putText(img, "EXAM CODE: OMR-100-PROD  |  SUBJECT: GENERAL SCIENCE & MATH  |  CLASS: GRADE 10", (120, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1)

cv2.putText(img, "STUDENT NAME: ________________________________________________", (120, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)

# Instructions
cv2.putText(img, "INSTRUCTIONS: Use black or dark blue ballpoint pen. Darken bubbles completely.", (120, 245), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1)
cv2.putText(img, "Do not fold, staple, or tear sheet. Ensure all 4 corner registration marks remain intact.", (120, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1)
cv2.putText(img, "CORRECT: ( * )   WRONG: ( / ) ( X ) ( . )", (120, 305), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (20, 20, 20), 1)

# Roll Number Header & Matrix
cv2.putText(img, "ROLL NUMBER", (760, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (20, 20, 20), 2)
for col in range(layout.roll_digit_count):
    bx = 760 + (col * 38) - 10
    by = 148
    cv2.rectangle(img, (bx, by), (bx + 26, by + 20), (50, 50, 50), 1)

for rb in layout.roll_bubbles:
    cv2.circle(img, (rb.cx, rb.cy), rb.radius, (40, 40, 40), 1)
    cv2.putText(img, str(rb.digit), (rb.cx - 4, rb.cy + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (60, 60, 60), 1)

# QR Code placement box
qr_box = layout.qr_box
cv2.rectangle(img, (qr_box["x"], qr_box["y"]), (qr_box["x"] + qr_box["width"], qr_box["y"] + qr_box["height"]), (20, 20, 20), 2)
cv2.putText(img, "SHEET QR ID", (qr_box["x"] + 35, qr_box["y"] + 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 60, 60), 1)

# Dividing separator line
cv2.line(img, (100, 410), (layout.width - 100, 410), (30, 30, 30), 2)

# Questions 1 to 100
for q_num, opt_map in layout.bubbles.items():
    first_b = next(iter(opt_map.values()))
    cv2.putText(img, f"{q_num:02d}.", (first_b.cx - 52, first_b.cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1)
    for opt_key, bubble in opt_map.items():
        cv2.circle(img, (bubble.cx, bubble.cy), bubble.radius, (40, 40, 40), 1)
        cv2.putText(img, opt_key, (bubble.cx - 4, bubble.cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (60, 60, 60), 1)

# Footer
footer = "Digital OMR Cloud | Template Version: OMR-A4-100Q-V1 | Always Print at 100% Scale (Do Not Fit / Shrink)"
cv2.putText(img, footer, (CANONICAL_WIDTH // 2 - 420, CANONICAL_HEIGHT - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100), 1)

# Save blank sheet image
blank_png_path = os.path.join(out_dir, "OMR_Sheet_100Q_Printable.png")
artifact_png_path = os.path.join(artifact_dir, "OMR_Sheet_100Q_Printable.png")
cv2.imwrite(blank_png_path, img)
cv2.imwrite(artifact_png_path, img)

# Also generate a pre-shaded student sample sheet for testing!
img_sample = img.copy()
# Shade roll number: 408215
sample_roll = [4, 0, 8, 2, 1, 5]
for col_idx, dig in enumerate(sample_roll):
    matching_bubble = next(b for b in layout.roll_bubbles if b.column_index == col_idx and b.digit == dig)
    cv2.circle(img_sample, (matching_bubble.cx, matching_bubble.cy), matching_bubble.radius - 2, (20, 20, 25), -1)

# Shade sample answers for Q1 - Q100
sample_answers = ["A", "B", "C", "D"] * 25
for q_num in range(1, 101):
    opt = sample_answers[q_num - 1]
    b = layout.bubbles[q_num][opt]
    cv2.circle(img_sample, (b.cx, b.cy), b.radius - 2, (25, 20, 30), -1)

sample_png_path = os.path.join(out_dir, "OMR_Sheet_100Q_Filled_Sample.png")
sample_artifact_path = os.path.join(artifact_dir, "OMR_Sheet_100Q_Filled_Sample.png")
cv2.imwrite(sample_png_path, img_sample)
cv2.imwrite(sample_artifact_path, img_sample)

# Copy PDF to artifact dir
pdf_src = os.path.join(out_dir, "Sample_OMR_100Q.pdf")
pdf_dst = os.path.join(artifact_dir, "Sample_OMR_100Q.pdf")
if os.path.exists(pdf_src):
    import shutil
    shutil.copy2(pdf_src, pdf_dst)

print("Generated and copied OMR sheets successfully:")
print("1. Blank PNG:", blank_png_path)
print("2. Filled Sample PNG:", sample_png_path)
print("3. PDF:", pdf_src)
