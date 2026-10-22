import cv2
import os
import numpy as np

base = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"
img = cv2.imread(os.path.join(base, "backend", "app", "omr", "assets", "vidyakashi_official_omr.jpg"))
canon = cv2.resize(img, (1654, 2338))
crop = canon[550:660, 1050:1620]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

# Threshold to find boxes
bin_img = (gray < 200).astype(np.uint8) * 255
# Find rectangular contours
contours, _ = cv2.findContours(bin_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
boxes = []
for c in contours:
    x, y, w, h = cv2.boundingRect(c)
    # Box should be roughly 45..60 wide, 35..60 high
    if 40 <= w <= 70 and 30 <= h <= 65:
        boxes.append((x, y, w, h))

boxes = sorted(boxes, key=lambda b: b[0])
print(f"Found {len(boxes)} candidate roll boxes:")
for i, b in enumerate(boxes):
    print(f"  Box {i}: x={b[0]}, y={b[1]}, w={b[2]}, h={b[3]} (Absolute y={550+b[1]}..{550+b[1]+b[3]}, x={1050+b[0]}..{1050+b[0]+b[2]})")
