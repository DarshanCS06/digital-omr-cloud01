import hashlib
from typing import Optional, Dict
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.answer_key import AnswerKey
from backend.app.models.batch import UploadBatch, UploadedImage, BatchStatus, ImageStatus
from backend.app.auth.dependencies import (
    require_teacher_or_admin,
    require_teacher_or_admin_flexible,
    check_exam_access,
)
from backend.app.services.storage import storage_service
from backend.app.workers.tasks import process_single_image
from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator

router = APIRouter(prefix="/templates", tags=["OMR Template Generator"])


def _get_exam_or_default_answers(db: Session, exam_id: Optional[int], question_count: int) -> Dict[int, str]:
    """Returns answers from the exam's active AnswerKey if present, else cyclic A/B/C/D."""
    opts = ["A", "B", "C", "D"]
    default_answers = {i: opts[(i - 1) % 4] for i in range(1, question_count + 1)}
    if not exam_id:
        return default_answers

    active_key = (
        db.query(AnswerKey)
        .filter(AnswerKey.examination_id == exam_id, AnswerKey.is_active == True)
        .order_by(AnswerKey.version.desc())
        .first()
    )
    if active_key and active_key.answers:
        merged = dict(default_answers)
        for k, v in active_key.answers.items():
            try:
                q_num = int(k)
                if 1 <= q_num <= question_count and str(v).upper() in opts:
                    merged[q_num] = str(v).upper()
            except ValueError:
                pass
        return merged
    return default_answers


def _build_realistic_student_answers(answer_key_map: Dict[int, str], question_count: int) -> Dict[int, str]:
    """
    Creates a realistic student response map (~86% correct, ~14% wrong) relative to the exam's answer key
    so that OMR evaluation demonstrates genuine right/wrong correction rather than a hardcoded 100%.
    """
    opts = ["A", "B", "C", "D"]
    wrong_questions_100 = {10, 15, 20, 25, 30, 35, 44, 50, 55, 65, 73, 80, 85, 95}
    student_answers: Dict[int, str] = {}
    for q in range(1, question_count + 1):
        correct_opt = answer_key_map.get(q, opts[(q - 1) % 4])
        is_wrong = (q in wrong_questions_100) if question_count == 100 else (q % 7 == 0)
        if is_wrong:
            idx = opts.index(correct_opt) if correct_opt in opts else 0
            student_answers[q] = opts[(idx + 1) % 4]
        else:
            student_answers[q] = correct_opt
    return student_answers


@router.get("/omr-pdf/{exam_id}")
def download_omr_pdf(
    exam_id: int,
    db: Session = Depends(get_db),
):
    """
    Generates and serves the official Vidyakashi-branded A4 printable OMR PDF.
    """
    from backend.app.models.examination import Examination
    from fastapi import HTTPException
    exam = db.query(Examination).filter(Examination.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    generator = VidyakashiOMRGenerator(question_count=exam.question_count)
    pdf_bytes, _ = generator.generate_pdf(
        exam_title=exam.title,
        exam_code=exam.code,
        subject=exam.subject,
        class_grade=exam.class_grade,
        exam_date=str(exam.exam_date),
    )

    filename = f"VKS_OMR_{exam.code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/omr-image/{exam_id}")
def download_omr_image(
    exam_id: int,
    db: Session = Depends(get_db),
):
    """Serves the official Vidyakashi blank OMR template as a high-res JPEG image."""
    from backend.app.models.examination import Examination
    from fastapi import HTTPException
    exam = db.query(Examination).filter(Examination.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    generator = VidyakashiOMRGenerator(question_count=exam.question_count)
    img_bytes = generator.generate_image_bytes(ext=".jpg")
    filename = f"VKS_OMR_Blank_{exam.code}.jpg"
    return Response(
        content=img_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/sample-pdf")
def download_sample_pdf(question_count: int = 100):
    """Generates an official Vidyakashi-branded sample OMR PDF (no auth required)."""
    question_count = max(1, min(100, question_count))

    generator = VidyakashiOMRGenerator(question_count=question_count)
    pdf_bytes, _ = generator.generate_pdf(
        exam_title="Sample Test - Vidyakashi Study Circle",
        exam_code="VKS-DEMO",
        subject="Science",
        class_grade="10th",
        exam_date="2026-10-21",
        sheet_id="SAMPLE-001",
    )

    filename = f"Vidyakashi_Sample_OMR_{question_count}Q.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/sample-filled-pdf")
def download_sample_filled_pdf(
    question_count: int = 100,
    exam_id: Optional[int] = None,
    mark_style: str = "solid",
    db: Session = Depends(get_db),
):
    """Returns a pre-filled official Vidyakashi OMR PDF for testing the detection & correction pipeline."""
    question_count = max(1, min(100, question_count))
    key_answers = _get_exam_or_default_answers(db, exam_id, question_count)
    student_answers = _build_realistic_student_answers(key_answers, question_count)

    generator = VidyakashiOMRGenerator(question_count=question_count)
    pdf_bytes, _ = generator.generate_pdf(
        exam_title="Sample Filled Sheet - Vidyakashi Study Circle",
        exam_code="VKS-DEMO",
        subject="Science",
        class_grade="10th",
        exam_date="2026-10-21",
        sheet_id="FILLED-001",
        pre_filled_answers=student_answers,
        student_name="Rahul Gowda",
        student_roll="250710003",
        mark_style=mark_style,
    )

    filename = f"Vidyakashi_Filled_OMR_{question_count}Q.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/sample-bulk-pdf")
def download_sample_bulk_pdf(
    question_count: int = 100,
    exam_id: Optional[int] = None,
    student_count: int = 4,
    db: Session = Depends(get_db),
):
    """Generates a multi-page PDF containing multiple students' completed OMR sheets for bulk evaluation testing."""
    import io
    import cv2
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    question_count = max(1, min(100, question_count))
    student_count = max(2, min(20, student_count))
    key_answers = _get_exam_or_default_answers(db, exam_id, question_count)
    generator = VidyakashiOMRGenerator(question_count=question_count)

    roster = [
        ("Rahul Gowda", "250710003", 0),
        ("Rohit Kumar", "250710004", 1),
        ("Ananya Sharma", "250710005", 2),
        ("Karthik Nair", "250710006", 3),
        ("Priya Verma", "250710007", 4),
    ]
    opts = ["A", "B", "C", "D"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pw, ph = A4

    for idx in range(student_count):
        s_name, s_roll, variant = roster[idx % len(roster)]
        if idx >= len(roster):
            s_roll = f"250710{idx + 1:03d}"
        s_answers: Dict[int, str] = {}
        for q in range(1, question_count + 1):
            corr = key_answers.get(q, opts[(q - 1) % 4])
            # Give each student a distinct realistic score
            if (q + variant * 3) % (6 + variant) == 0:
                c_idx = opts.index(corr) if corr in opts else 0
                s_answers[q] = opts[(c_idx + 1) % 4]
            else:
                s_answers[q] = corr

        sheet_bgr = generator.generate_image(
            exam_title="Vidyakashi Bulk OMR Test",
            exam_code=f"VKS-{question_count}Q",
            subject="Science",
            class_grade="10th",
            exam_date="22/10/2026",
            pre_filled_answers=s_answers,
            student_name=s_name,
            student_roll=s_roll,
            mark_style="solid",
        )
        _, jpg_buf = cv2.imencode(".jpg", sheet_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_reader = ImageReader(io.BytesIO(jpg_buf.tobytes()))
        c.drawImage(img_reader, 0, 0, width=pw, height=ph)
        c.showPage()

    c.save()
    filename = f"Vidyakashi_Bulk_{student_count}_Students_{question_count}Q.pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sample-filled-image")
def download_sample_filled_image(
    question_count: int = 100,
    exam_id: Optional[int] = None,
    mark_style: str = "solid",
    db: Session = Depends(get_db),
):
    """Returns a pre-filled official Vidyakashi OMR JPEG image ready to upload and evaluate."""
    import os
    question_count = max(1, min(100, question_count))
    if question_count == 100 and mark_style == "solid":
        official_sample_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "omr",
            "assets",
            "vidyakashi_sample_100q_filled.jpg",
        )
        if os.path.exists(official_sample_path):
            with open(official_sample_path, "rb") as f:
                img_bytes = f.read()
            return Response(
                content=img_bytes,
                media_type="image/jpeg",
                headers={"Content-Disposition": 'inline; filename="Vidyakashi_Sample_Filled_100Q.jpg"'},
            )

    key_answers = _get_exam_or_default_answers(db, exam_id, question_count)
    student_answers = _build_realistic_student_answers(key_answers, question_count)

    generator = VidyakashiOMRGenerator(question_count=question_count)
    img_bytes = generator.generate_image_bytes(
        ext=".jpg",
        exam_title="Vidyakashi Assessment",
        exam_code="VKS-SAMPLE",
        subject="Science",
        class_grade="10th",
        exam_date="21/10/2026",
        pre_filled_answers=student_answers,
        student_name="Rahul Gowda",
        student_roll="250710003",
        mark_style=mark_style,
    )

    filename = f"Vidyakashi_Sample_Filled_{question_count}Q_{mark_style}.jpg"
    return Response(
        content=img_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/evaluate-sample/{exam_id}")
def evaluate_sample_sheet_for_exam(
    exam_id: int,
    mark_style: str = "solid",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Generates or loads a sample filled official Vidyakashi OMR sheet,
    evaluates it through the live OpenCV OMR pipeline against the exam's Answer Key,
    and saves the corrected submission with Right (✓) and Wrong (✗) answers.
    """
    import os
    exam = check_exam_access(exam_id, current_user, db)
    q_count = min(100, exam.question_count)

    # Ensure the exam has an active answer key
    active_key = (
        db.query(AnswerKey)
        .filter(AnswerKey.examination_id == exam.id, AnswerKey.is_active == True)
        .order_by(AnswerKey.version.desc())
        .first()
    )
    opts = ["A", "B", "C", "D"]
    if not active_key or not active_key.answers:
        default_key = {str(i): opts[(i - 1) % 4] for i in range(1, q_count + 1)}
        active_key = AnswerKey(
            examination_id=exam.id,
            version=1,
            answers=default_key,
            is_active=True,
            updated_by_id=current_user.id,
        )
        db.add(active_key)
        db.commit()
        db.refresh(active_key)

    official_sample_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "omr",
        "assets",
        "vidyakashi_sample_100q_filled.jpg",
    )
    if q_count == 100 and os.path.exists(official_sample_path):
        with open(official_sample_path, "rb") as f:
            img_bytes = f.read()
    else:
        key_answers = _get_exam_or_default_answers(db, exam.id, q_count)
        student_answers = _build_realistic_student_answers(key_answers, q_count)
        generator = VidyakashiOMRGenerator(question_count=q_count)
        img_bytes = generator.generate_image_bytes(
            ext=".jpg",
            exam_title=exam.title,
            exam_code=exam.code,
            subject=exam.subject,
            class_grade=exam.class_grade,
            exam_date=str(exam.exam_date),
            pre_filled_answers=student_answers,
            student_name="Rahul Gowda",
            student_roll="250710003",
            mark_style=mark_style,
        )

    batch = UploadBatch(
        examination_id=exam.id,
        uploaded_by_id=current_user.id,
        total_files=1,
        processed_files=0,
        failed_files=0,
        review_needed_files=0,
        progress_percentage=0.0,
        status=BatchStatus.PROCESSING,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    filename = f"vidyakashi_sample_{exam.code}_{mark_style}.jpg"
    storage_key = storage_service.save_file(
        content_bytes=img_bytes,
        filename=filename,
        subfolder="uploads",
    )
    file_hash = hashlib.sha256(img_bytes).hexdigest()

    img_record = UploadedImage(
        batch_id=batch.id,
        examination_id=exam.id,
        original_filename=filename,
        storage_key=storage_key,
        mime_type="image/jpeg",
        file_size_bytes=len(img_bytes),
        file_hash=file_hash,
        status=ImageStatus.PENDING,
    )
    db.add(img_record)
    db.commit()
    db.refresh(img_record)

    process_single_image(img_record.id, db)
    db.refresh(img_record)

    batch.processed_files = 1 if img_record.status == ImageStatus.COMPLETED else 0
    batch.failed_files = 1 if img_record.status == ImageStatus.FAILED else 0
    batch.progress_percentage = 100.0
    batch.status = BatchStatus.COMPLETED if img_record.status == ImageStatus.COMPLETED else BatchStatus.FAILED
    db.commit()

    sub = img_record.submission
    return {
        "message": "Official Vidyakashi OMR sheet corrected and scored!",
        "batch_id": batch.id,
        "submission_id": sub.id if sub else None,
        "total_score": sub.total_score if sub else 0.0,
        "max_score": sub.max_score if sub else float(q_count),
        "percentage": sub.percentage if sub else 0.0,
        "correct_count": sub.correct_count if sub else 0,
        "incorrect_count": sub.incorrect_count if sub else 0,
        "blank_count": sub.blank_count if sub else 0,
        "review_count": sub.review_count if sub else 0,
    }
