import os
import sys

# Ensure backend package is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.generator import OMRSheetGenerator


def main():
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "generated"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Sample_OMR_100Q.pdf")

    layout = OMRLayoutConfig(question_count=100)
    generator = OMRSheetGenerator(layout)
    pdf_bytes = generator.generate_pdf(
        exam_title="Digital OMR Cloud - Model Examination 2026",
        exam_code="OMR-100-PROD",
        subject="Mathematics & General Science",
        class_grade="Grade 10 / Secondary",
        exam_date="2026-10-21",
        sheet_id="SHEET-DEMO-001",
    )

    with open(out_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"Generated sample OMR PDF successfully: {out_path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    main()
