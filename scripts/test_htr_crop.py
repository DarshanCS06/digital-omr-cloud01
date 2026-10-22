import cv2
import os
import numpy as np

base = r'C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud'
p = os.path.join(base, 'backend', 'app', 'omr', 'assets', 'vidyakashi_sample_100q_filled.jpg')
img = cv2.imread(p)
canon = cv2.resize(img, (1654, 2338))

# Let's inspect different candidate regions
# 1. Left side name box: y=420..510, x=220..860
name_crop = canon[420:510, 220:860]

# 2. Right side roll number boxes: y=570..650, x=1070..1610
roll_crop = canon[570:650, 1070:1610]

# 3. Standard top header: y=180..240, x=180..800
header_name = canon[180:240, 180:800]

print("Images loaded successfully.")
print("name_crop shape:", name_crop.shape)
print("roll_crop shape:", roll_crop.shape)
