import cv2
import os
import numpy as np

base = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"
p_blank = os.path.join(base, "backend", "app", "omr", "assets", "vidyakashi_official_omr.jpg")
blank_img = cv2.imread(p_blank)
canon = cv2.resize(blank_img, (1654, 2338))
roll_crop = canon[570:650, 1080:1610]

h, w = roll_crop.shape[:2]
gray = cv2.cvtColor(roll_crop, cv2.COLOR_BGR2GRAY)
box_w = w / 9.0

print(f"Roll crop size: {w}x{h}, box_w: {box_w}")
for i in range(9):
    x1 = int(round(i * box_w))
    x2 = int(round((i + 1) * box_w))
    cell = gray[:, x1:x2]
    # Check inner region (excluding 6px borders on all sides)
    inner = cell[8:h-8, 8:cell.shape[1]-8]
    ink_count = int(np.sum(inner < 180))
    print(f"Cell {i}: cell shape {cell.shape}, inner shape {inner.shape}, inner ink count: {ink_count}")
