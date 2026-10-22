import cv2
import os
import pytesseract
import numpy as np

base = r'C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud'
p1 = os.path.join(base, 'backend', 'app', 'omr', 'assets', 'vidyakashi_official_omr.jpg')
p2 = os.path.join(base, 'backend', 'app', 'omr', 'assets', 'vidyakashi_sample_100q_filled.jpg')

for path, label in [(p1, "vidyakashi_official"), (p2, "vidyakashi_sample_filled")]:
    img = cv2.imread(path)
    if img is None:
        continue
    h, w = img.shape[:2]
    print(f"\n=== Inspecting {label} ({w}x{h}) ===")
    
    # Resize to canonical (1654, 2338) to check normalized coordinates
    canon = cv2.resize(img, (1654, 2338))
    
    # Save slices to see header regions
    # Header area is y=0..700
    header = canon[0:700, 0:1654]
    
    # Check text with tesseract if available
    try:
        data = pytesseract.image_to_data(canon[0:700, :], output_type=pytesseract.Output.DICT)
        n_boxes = len(data['text'])
        print(f"Detected {n_boxes} text elements in header:")
        for i in range(n_boxes):
            txt = data['text'][i].strip()
            if txt:
                x, y, bw, bh = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                print(f"  '{txt}' at x={x}, y={y}, w={bw}, h={bh}, conf={data['conf'][i]}")
    except Exception as e:
        print("Tesseract error:", e)
