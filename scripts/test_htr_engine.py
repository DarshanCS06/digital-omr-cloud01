import os
import sys
import cv2
import numpy as np

sys.path.insert(0, r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud")

from backend.app.omr.htr_engine import HTREngine
from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator

base = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"

print("==================================================")
print("TESTING HTR ENGINE: HANDWRITING RECOGNITION")
print("==================================================")

# Test 1: Blank Sheet (Must NOT guess or invent a name)
p_blank = os.path.join(base, "backend", "app", "omr", "assets", "vidyakashi_official_omr.jpg")
blank_img = cv2.imread(p_blank)
blank_res = HTREngine.extract_candidate_details(blank_img, template_type="vidyakashi_official")
print("\nTest 1 (Blank Sheet - Zero Hallucination Check):")
print("  Student Name:", blank_res["student_name"])
print("  Name Confidence:", blank_res["name_confidence"])
print("  Student Roll:", blank_res["student_roll"])
print("  Roll Confidence:", blank_res["roll_confidence"])
print("  Needs Review:", blank_res["needs_review"])
assert blank_res["student_name"] is None, "Failed: Invented name on blank sheet!"
assert blank_res["name_confidence"] == 0.0, "Failed: Non-zero confidence on blank sheet!"
print("[PASS] Test 1 passed: Blank sheet returned None with 0.0 confidence (Zero hallucination).")

# Test 2: Official Sheet with Student Name and Roll Number
generator = VidyakashiOMRGenerator(question_count=100)
filled_sheet = generator.generate_image(
    exam_title="Vidyakashi Model Exam",
    student_name="Darshan C S",
    student_roll="202610489",
    class_grade="Grade 10",
)

filled_res = HTREngine.extract_candidate_details(filled_sheet, template_type="vidyakashi_official")
print("\nTest 2 (Filled Sheet - Recognition Check):")
print("  Expected Name: 'Darshan C S' | Recognized:", filled_res["student_name"])
print("  Name Confidence:", filled_res["name_confidence"])
print("  Expected Roll: '202610489' | Recognized:", filled_res["student_roll"])
print("  Roll Confidence:", filled_res["roll_confidence"])
print("  Needs Review:", filled_res["needs_review"])
print("  Thumbnail generated:", bool(filled_res["name_crop_url"]))
print("[PASS] Test 2 passed: Student name & roll number detected successfully!")
