import cv2
import os

base = r'C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud'
p = os.path.join(base, 'backend', 'app', 'omr', 'assets', 'vidyakashi_sample_100q_filled.jpg')
img = cv2.imread(p)
canon = cv2.resize(img, (1654, 2338))

# Crop candidate name and roll number regions
name_crop = canon[430:510, 220:860]
roll_crop = canon[570:650, 1070:1610]

cv2.imwrite(os.path.join(base, 'generated', 'sample_name_crop.png'), name_crop)
cv2.imwrite(os.path.join(base, 'generated', 'sample_roll_crop.png'), roll_crop)
print("Saved sample crops to generated/")
