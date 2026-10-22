import os
import sys
import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pypdfium2 as pdfium

sys.path.insert(0, r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud")
from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.generator import OMRSheetGenerator

def make_multipage_pdf(out_path, num_pages):
    layout = OMRLayoutConfig(question_count=100)
    generator = OMRSheetGenerator(layout)
    single_page_bytes = generator.generate_pdf(
        exam_title="Digital OMR Cloud - Model Examination 2026",
        exam_code="OMR-100-PROD",
        subject="Mathematics & General Science",
        class_grade="Grade 10 / Secondary",
        exam_date="2026-10-21",
        sheet_id="SHEET-DEMO-001",
    )
    
    # Use pypdfium2 to duplicate pages into a multi-page PDF
    src_doc = pdfium.PdfDocument(single_page_bytes)
    dest_doc = pdfium.PdfDocument.new()
    for _ in range(num_pages):
        dest_doc.import_pages(src_doc, [0])
    
    with open(out_path, "wb") as f:
        dest_doc.save(f)
    print(f"Created {out_path} with {num_pages} pages ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    out_dir = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated"
    make_multipage_pdf(os.path.join(out_dir, "test_5_pages.pdf"), 5)
    make_multipage_pdf(os.path.join(out_dir, "test_20_pages.pdf"), 20)
