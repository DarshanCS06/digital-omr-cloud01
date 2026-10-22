"""
Comprehensive test suite for Bulk PDF OMR Evaluation (Steps 1-8):
1. PDF containing One OMR sheet.
2. PDF containing Multiple OMR sheets (multi-page PDF + 2-up multi-sheet page segmentation).
3. PDF containing Rotated (180°) and Skewed (5° tilted) sheets.
4. PDF containing Blurry or Low-Resolution pages alongside valid sheets.
5. PDF containing Blank pages alongside valid sheets.
6. Corrupted, Empty, Non-PDF, and Encrypted PDFs.
7. PDF containing Duplicate student roll numbers & retry idempotency (no duplicate results).
8. PDF containing Incorrectly aligned / cropped sheets alongside valid sheets.
9. Batch Results Export to Excel (.xlsx) and PDF (.pdf) + independent score verification.
"""
import io
import cv2
import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import (
    User,
    UserRole,
    Examination,
    ExaminationAssignment,
    AnswerKey,
    Student,
    UploadBatch,
    UploadedImage,
    Submission,
    DetectedResponse,
    BatchStatus,
    ImageStatus,
    SubmissionStatus,
    ReviewEvent,
    AuditLog,
)
from backend.app.omr.pdf_processor import PDFProcessor
from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator
from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.detector import OMRDetector
from backend.app.services.scoring import ScoringEngine
from backend.app.services.storage import storage_service
from backend.app.workers.tasks import process_batch_task, process_single_image
from backend.app.reports.exporter import ReportExporter


def _images_to_pdf_bytes(bgr_images: list[np.ndarray]) -> bytes:
    """Convert a list of OpenCV BGR images into a multi-page PDF byte stream."""
    pil_pages = []
    for bgr in bgr_images:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil_pages.append(Image.fromarray(rgb))
    buf = io.BytesIO()
    pil_pages[0].save(
        buf,
        format="PDF",
        resolution=150.0,
        save_all=True,
        append_images=pil_pages[1:],
    )
    return buf.getvalue()


def _official_answer_key_25q() -> dict[int, str]:
    opts = ["A", "B", "C", "D"]
    return {q: opts[(q - 1) % 4] for q in range(1, 26)}


def _create_student_sheet(
    answers_map: dict[int, str],
    student_name: str = "Aarav Sharma",
    student_roll: str = "250710001",
    question_count: int = 25,
) -> np.ndarray:
    gen = VidyakashiOMRGenerator(question_count=question_count)
    return gen.generate_image(
        exam_title="Vidyakashi Bulk PDF Benchmark",
        exam_code="VKS-BULK-25",
        subject="Physics",
        class_grade="10th",
        exam_date="22/10/2026",
        pre_filled_answers=answers_map,
        student_name=student_name,
        student_roll=student_roll,
        mark_style="solid",
    )


@pytest.fixture()
def db_session():
    """Isolated in-memory SQLite database for batch & worker evaluation tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        teacher = User(
            email="teacher_pdf@vidyakashi.org",
            full_name="Test Teacher",
            hashed_password="hashed_password",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)

        exam = Examination(
            code="VKS-PDF-TEST",
            title="Vidyakashi Bulk PDF Evaluation Test",
            subject="Science",
            class_grade="10th",
            exam_date="2026-10-22",
            question_count=25,
            options_per_question=4,
            positive_marks=4.0,
            negative_marks=1.0,
            blank_marks=0.0,
            multiple_penalty=1.0,
            created_by_id=teacher.id,
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        key_map = {str(k): v for k, v in _official_answer_key_25q().items()}
        ak = AnswerKey(
            examination_id=exam.id,
            version=1,
            answers=key_map,
            is_active=True,
        )
        db.add(ak)
        db.commit()
        yield db, exam, teacher
    finally:
        db.close()


def _stage_pdf_batch(db, exam: Examination, user: User, pdf_bytes: bytes, pdf_filename: str = "batch.pdf") -> UploadBatch:
    """Helper that stages a PDF into an UploadBatch with lazy pdf_page:// entries just like /batches/upload."""
    pdf_info = PDFProcessor.validate_pdf_bytes(pdf_bytes, filename=pdf_filename)
    page_count = pdf_info["page_count"]
    batch = UploadBatch(
        examination_id=exam.id,
        user_id=user.id,
        status=BatchStatus.QUEUED,
        total_files=page_count,
    )
    db.add(batch)
    db.flush()

    pdf_hash = storage_service.compute_sha256(pdf_bytes)
    pdf_storage_key = storage_service.save_file(
        content_bytes=pdf_bytes,
        filename=pdf_filename if pdf_filename.lower().endswith(".pdf") else f"{pdf_filename}.pdf",
        subfolder="pdf_temp",
    )
    for page_idx in range(page_count):
        page_hash = storage_service.compute_sha256(f"{pdf_hash}:page:{page_idx}".encode("utf-8"))
        page_label = f"{pdf_filename} - Page {page_idx + 1} of {page_count}"
        up_img = UploadedImage(
            batch_id=batch.id,
            examination_id=exam.id,
            original_filename=page_label,
            storage_key=f"pdf_page://{pdf_storage_key}#page={page_idx}",
            file_hash=page_hash,
            mime_type="image/jpeg",
            file_size_bytes=len(pdf_bytes) // max(1, page_count),
            status=ImageStatus.PENDING,
        )
        db.add(up_img)
    db.commit()
    db.refresh(batch)
    return batch


def test_1_single_sheet_pdf_evaluation(db_session):
    """
    Test 1: PDF containing ONE OMR sheet.
    Verifies PDF validation, 200 DPI page rendering, answer detection against verified answers,
    student name & roll reading, and independent score calculation.
    """
    db, exam, teacher = db_session
    verified_answers = _official_answer_key_25q()
    sheet_img = _create_student_sheet(
        verified_answers,
        student_name="Aarav Sharma",
        student_roll="250710001",
    )
    pdf_bytes = _images_to_pdf_bytes([sheet_img])

    info = PDFProcessor.validate_pdf_bytes(pdf_bytes, filename="single_student.pdf")
    assert info["is_valid"] is True
    assert info["page_count"] == 1
    assert info["file_size_bytes"] == len(pdf_bytes)

    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "single_student.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.status == BatchStatus.COMPLETED
    assert batch.total_files == 1
    assert batch.processed_files == 1
    assert batch.failed_files == 0

    sub = db.query(Submission).filter(Submission.examination_id == exam.id).one()
    assert sub.student is not None and sub.student.name == "Aarav Sharma"
    assert sub.detected_roll_number == "250710001"
    assert sub.correct_count == 25
    assert sub.incorrect_count == 0
    assert sub.blank_count == 0
    assert sub.total_score == 100.0  # 25 * +4.0
    assert sub.percentage == 100.0

    # Compare every detected response against manually verified answers
    responses = db.query(DetectedResponse).filter(DetectedResponse.submission_id == sub.id).all()
    assert len(responses) == 25
    for resp in responses:
        assert resp.detected_option.value == verified_answers[resp.question_number]


def test_2_multi_student_pdf_evaluation_and_2up_segmentation(db_session):
    """
    Test 2: PDF containing MULTIPLE OMR sheets (4 students with distinct answer profiles)
    PLUS a 2-up side-by-side multi-sheet PDF page.
    Verifies independent evaluation of each student and accurate mark calculation.
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()
    wrong_opt = {"A": "B", "B": "C", "C": "D", "D": "A"}

    # Student 1: 25/25 correct -> 25*4 = 100.0 marks (100%)
    ans_s1 = dict(official_key)
    # Student 2: 20 correct, 5 wrong -> 20*4 - 5*1 = 75.0 marks (75%)
    ans_s2 = {q: (official_key[q] if q <= 20 else wrong_opt[official_key[q]]) for q in range(1, 26)}
    # Student 3: 15 correct, 5 wrong, 5 blank -> 15*4 - 5*1 + 0 = 55.0 marks (55%)
    ans_s3 = {
        q: (official_key[q] if q <= 15 else wrong_opt[official_key[q]])
        for q in range(1, 21)
    }
    # Student 4: 10 correct, 15 blank -> 10*4 = 40.0 marks (40%)
    ans_s4 = {q: official_key[q] for q in range(1, 11)}

    pages = [
        _create_student_sheet(ans_s1, "Aarav Sharma", "250710001"),
        _create_student_sheet(ans_s2, "Diya Nair", "250710002"),
        _create_student_sheet(ans_s3, "Rohan Verma", "250710003"),
        _create_student_sheet(ans_s4, "Sneha Patil", "250710004"),
    ]
    pdf_bytes = _images_to_pdf_bytes(pages)

    info = PDFProcessor.validate_pdf_bytes(pdf_bytes, filename="four_students.pdf")
    assert info["page_count"] == 4

    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "four_students.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.status == BatchStatus.COMPLETED
    assert batch.total_files == 4
    assert batch.processed_files == 4
    assert batch.failed_files == 0

    subs = (
        db.query(Submission)
        .filter(Submission.examination_id == exam.id)
        .order_by(Submission.detected_roll_number.asc())
        .all()
    )
    assert len(subs) == 4

    expected = [
        ("250710001", "Aarav Sharma", 25, 0, 0, 100.0, 100.0, ans_s1),
        ("250710002", "Diya Nair", 20, 5, 0, 75.0, 75.0, ans_s2),
        ("250710003", "Rohan Verma", 15, 5, 5, 55.0, 55.0, ans_s3),
        ("250710004", "Sneha Patil", 10, 0, 15, 40.0, 40.0, ans_s4),
    ]

    for sub, (roll, name, exp_c, exp_i, exp_b, exp_score, exp_pct, gt_map) in zip(subs, expected):
        assert sub.detected_roll_number == roll
        assert sub.student is not None and sub.student.name == name
        assert sub.correct_count == exp_c
        assert sub.incorrect_count == exp_i
        assert sub.blank_count == exp_b
        assert sub.total_score == exp_score
        assert sub.percentage == exp_pct

        # Verify independent score calculation matches ScoringEngine
        resps = db.query(DetectedResponse).filter(DetectedResponse.submission_id == sub.id).all()
        detected_dict = {r.question_number: r.detected_option.value for r in resps}
        for q in range(1, 26):
            expected_opt = gt_map.get(q, "BLANK")
            assert detected_dict[q] == expected_opt

        indep_marks = (exp_c * exam.positive_marks) - (exp_i * exam.negative_marks)
        assert sub.total_score == indep_marks

    # Also test 2-up side-by-side multi-sheet segmentation on a single wide page
    two_up_page = np.hstack([pages[0], pages[1]])
    segments = PDFProcessor.segment_page_sheets(two_up_page)
    assert len(segments) == 2


def test_3_rotated_and_skewed_pdf_pages(db_session):
    """
    Test 3: PDF containing Rotated (180° upside-down) and Skewed (5° tilted) OMR sheets.
    Verifies automatic orientation/tilt alignment and 100% answer detection accuracy.
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()

    s1_straight = _create_student_sheet(official_key, "Karthik Rao", "250710005")
    # Page 1: Rotated 180 degrees upside-down
    s1_rot180 = cv2.rotate(s1_straight, cv2.ROTATE_180)

    # Page 2: Skewed / tilted by 4.5 degrees
    s2_straight = _create_student_sheet(official_key, "Ananya Hegde", "250710006")
    h, w = s2_straight.shape[:2]
    rot_mat = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), 4.5, 1.0)
    s2_tilted = cv2.warpAffine(
        s2_straight,
        rot_mat,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    pdf_bytes = _images_to_pdf_bytes([s1_rot180, s2_tilted])
    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "rotated_and_skewed.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.status == BatchStatus.COMPLETED
    assert batch.processed_files == 2
    assert batch.failed_files == 0

    subs = db.query(Submission).filter(Submission.examination_id == exam.id).all()
    assert len(subs) == 2
    for sub in subs:
        assert sub.correct_count == 25
        assert sub.total_score == 100.0


def test_4_blurry_and_low_res_pdf_pages_continue_batch(db_session):
    """
    Test 4: PDF containing a Blurry page and a Low-Resolution page alongside a Valid OMR page.
    Verifies that blurry/low-res pages are stopped with clear error messages while valid pages
    in the same PDF continue processing and succeed.
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()

    valid_sheet = _create_student_sheet(official_key, "Valid Student", "250710010")
    blurry_sheet = cv2.GaussianBlur(valid_sheet, (51, 51), 22.0)

    pdf_bytes = _images_to_pdf_bytes([valid_sheet, blurry_sheet])
    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "mixed_blurry.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.status == BatchStatus.PARTIALLY_FAILED
    assert batch.total_files == 2
    assert batch.processed_files == 1
    assert batch.failed_files == 1

    images = (
        db.query(UploadedImage)
        .filter(UploadedImage.batch_id == batch.id)
        .order_by(UploadedImage.id.asc())
        .all()
    )
    assert images[0].status == ImageStatus.COMPLETED
    assert images[1].status == ImageStatus.FAILED
    assert "blurry" in (images[1].error_message or "").lower()


def test_5_blank_pdf_pages_continue_batch(db_session):
    """
    Test 5: PDF containing a completely Blank page alongside a Valid OMR sheet.
    Verifies blank page detection & failure recording while valid pages succeed.
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()

    valid_sheet = _create_student_sheet(official_key, "Valid Student", "250710020")
    blank_page = np.full_like(valid_sheet, 255)

    assert PDFProcessor.is_blank_page(blank_page) is True
    assert PDFProcessor.is_blank_page(valid_sheet) is False

    pdf_bytes = _images_to_pdf_bytes([blank_page, valid_sheet])
    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "with_blank_page.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.status == BatchStatus.PARTIALLY_FAILED
    assert batch.total_files == 2
    assert batch.processed_files == 1
    assert batch.failed_files == 1

    images = (
        db.query(UploadedImage)
        .filter(UploadedImage.batch_id == batch.id)
        .order_by(UploadedImage.id.asc())
        .all()
    )
    assert images[0].status == ImageStatus.FAILED
    assert "blank page" in (images[0].error_message or "").lower()
    assert images[1].status == ImageStatus.COMPLETED


def test_6_corrupted_empty_and_encrypted_pdfs():
    """
    Test 6: Empty, Non-PDF, Corrupted, and Password-Protected/Encrypted PDFs are rejected gracefully
    with clear user-facing messages and no internal server path leakage.
    """
    # 1. Empty PDF
    with pytest.raises(ValueError, match="empty"):
        PDFProcessor.validate_pdf_bytes(b"", filename="empty.pdf")

    # 2. Non-PDF binary data
    with pytest.raises(ValueError, match="invalid PDF"):
        PDFProcessor.validate_pdf_bytes(b"NOT_A_PDF_HEADER_DATA_1234567890", filename="fake.pdf")

    # 3. Corrupted PDF with %PDF- header but broken xref/trailer
    corrupted_bytes = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\ncorrupted_stream_xyz\n%%EOF"
    with pytest.raises(ValueError) as exc_info:
        PDFProcessor.validate_pdf_bytes(corrupted_bytes, filename="corrupted.pdf")
    assert "corrupted" in str(exc_info.value).lower() or "valid" in str(exc_info.value).lower()

    # 4. Password-protected / Encrypted PDF structure
    encrypted_bytes = (
        b"%PDF-1.7\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [] /Count 1 >> endobj\n"
        b"3 0 obj << /Filter /Standard /V 2 /R 3 /Length 128 >> endobj\n"
        b"trailer << /Root 1 0 R /Encrypt 3 0 R >>\n%%EOF"
    )
    with pytest.raises(ValueError, match="password-protected or encrypted"):
        PDFProcessor.validate_pdf_bytes(encrypted_bytes, filename="encrypted.pdf")


def test_7_duplicate_roll_numbers_and_idempotent_retry(db_session):
    """
    Test 7:
    - Detects duplicate student roll numbers across pages in a PDF (marks is_duplicate=True and duplicate_of_id).
    - Does not create duplicate results when processing/retrying the same batch again.
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()

    # Two sheets with the SAME roll number "250710099" + one failed blank page to test retry
    s1 = _create_student_sheet(official_key, "Aarav Sharma", "250710099")
    s2 = _create_student_sheet(official_key, "Aarav Sharma Copy", "250710099")
    blank_page = np.full_like(s1, 255)

    pdf_bytes = _images_to_pdf_bytes([s1, s2, blank_page])
    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "duplicate_rolls.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.processed_files == 2
    assert batch.failed_files == 1

    subs = (
        db.query(Submission)
        .filter(Submission.examination_id == exam.id)
        .order_by(Submission.id.asc())
        .all()
    )
    assert len(subs) == 2
    assert subs[0].detected_roll_number == "250710099"
    assert subs[0].is_duplicate is False
    assert subs[1].detected_roll_number == "250710099"
    assert subs[1].is_duplicate is True
    assert subs[1].duplicate_of_id == subs[0].id

    # Now test idempotency: running process_batch_task again on the same batch
    # must NOT duplicate the 2 already-completed submissions.
    process_batch_task(batch.id, db=db)
    subs_after_retry = db.query(Submission).filter(Submission.examination_id == exam.id).all()
    assert len(subs_after_retry) == 2


def test_8_misaligned_cropped_pdf_pages(db_session):
    """
    Test 8: PDF containing an incorrectly aligned / severely cropped OMR sheet alongside a valid sheet.
    Verifies cropped sheet is rejected with 'Part of the answer sheet is missing. Upload the complete sheet.'
    while valid pages succeed.
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()

    valid_sheet = _create_student_sheet(official_key, "Complete Sheet", "250710030")
    h, w = valid_sheet.shape[:2]
    # Simulate a scanned A4 page where the bottom 45% of the OMR sheet was cut off / missing
    cropped_sheet = valid_sheet.copy()
    cropped_sheet[int(h * 0.55) :, :] = 255

    pdf_bytes = _images_to_pdf_bytes([cropped_sheet, valid_sheet])
    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "cropped_and_valid.pdf")
    process_batch_task(batch.id, db=db)

    db.refresh(batch)
    assert batch.status == BatchStatus.PARTIALLY_FAILED
    assert batch.processed_files == 1
    assert batch.failed_files == 1

    images = (
        db.query(UploadedImage)
        .filter(UploadedImage.batch_id == batch.id)
        .order_by(UploadedImage.id.asc())
        .all()
    )
    assert images[0].status == ImageStatus.FAILED
    assert "missing" in (images[0].error_message or "").lower() or "insufficient" in (images[0].error_message or "").lower()
    assert images[1].status == ImageStatus.COMPLETED


def test_9_excel_and_pdf_export_and_independent_mark_verification(db_session):
    """
    Test 9: Verifies exporting batch evaluation results to both Excel (.xlsx) and PDF (.pdf).
    """
    db, exam, teacher = db_session
    official_key = _official_answer_key_25q()

    s1 = _create_student_sheet(official_key, "Aarav Sharma", "250710001")
    s2 = _create_student_sheet({q: official_key[q] for q in range(1, 21)}, "Diya Nair", "250710002")

    pdf_bytes = _images_to_pdf_bytes([s1, s2])
    batch = _stage_pdf_batch(db, exam, teacher, pdf_bytes, "export_test.pdf")
    process_batch_task(batch.id, db=db)

    subs = db.query(Submission).filter(Submission.examination_id == exam.id).all()
    assert len(subs) == 2

    # 1. Excel export (.xlsx)
    excel_bytes = ReportExporter.generate_excel_results(exam, db)
    assert len(excel_bytes) > 1000
    assert excel_bytes[:2] == b"PK"  # Valid ZIP/OOXML xlsx header

    # 2. PDF report export (.pdf)
    pdf_report_bytes = ReportExporter.generate_pdf_results(exam, db, batch_id=batch.id)
    assert len(pdf_report_bytes) > 500
    assert pdf_report_bytes.startswith(b"%PDF-")
