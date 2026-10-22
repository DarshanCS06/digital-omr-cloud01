import cv2
import os
import numpy as np

base = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"
img = cv2.imread(os.path.join(base, "backend", "app", "omr", "assets", "vidyakashi_official_omr.jpg"))
canon = cv2.resize(img, (1654, 2338))
crop = canon[400:540, 200:900]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

bin_img = (gray < 200).astype(np.uint8) * 255
contours, _ = cv2.findContours(bin_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
boxes = []
for c in contours:
    x, y, w, h = cv2.boundingRect(c)
    if w > 200 and 35 <= h <= 80:
        boxes.append((x, y, w, h))

print(f"Found {len(boxes)} name box candidates:")
for i, b in enumerate(boxes):
    print(f"  Name Box {i}: x={b[0]}, y={b[1]}, w={b[2]}, h={b[3]} (Absolute y={400+b[1]}..{400+b[1]+b[3]}, x={200+b[0]}..{200+b[0]+b[2]})")
