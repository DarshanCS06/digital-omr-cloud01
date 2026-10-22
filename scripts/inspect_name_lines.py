import cv2
import os
import numpy as np

base = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"
img = cv2.imread(os.path.join(base, "generated", "name_area.png"))
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape[:2]

# Detect horizontal lines
h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
h_lines = cv2.morphologyEx((gray < 180).astype(np.uint8) * 255, cv2.MORPH_OPEN, h_kernel)
lines_y = np.where(np.sum(h_lines, axis=1) > 255 * 100)[0]
print(f"Horizontal lines found at relative y (add 400 for absolute): {lines_y}")
