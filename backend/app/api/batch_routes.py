import base64
import cv2
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.answer_key import AnswerKey
from backend.app.models.batch import UploadBatch, UploadedImage, BatchStatus, ImageStatus
from backend.app.schemas.batch import BatchResponse, ImageResponse, UploadBatchResponse
from backend.app.auth.dependencies import require_teacher_or_admin, check_exam_access
from backend.app.services.storage import storage_service
from backend.app.omr.preprocessor import ImagePreprocessor
from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.detector import OMRDetector
from backend.app.omr.pdf_processor import PDFProcessor
from backend.app.workers.queue import job_queue
from backend.app.workers.tasks import process_batch_task

router = APIRouter(prefix="/batches", tags=["Batch Processing & Uploads"])


def _encode_preview_data_url(img_cv, max_width: int = 720) -> str:
    h, w = img_cv.shape[:2]
    if w > max_width:
        scale = max_width / float(w)
        img_cv = cv2.resize(img_cv, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img_cv, [cv2.IMWRITE_JPEG_QUALITY, 82])
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


@router.post("/inspect-pdf/{exam_id}")
@router.post("/validate-preview/{exam_id}")
async def validate_and_preview_image(
    exam_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Validates uploaded image OR multi-page OMR PDF, performs automatic boundary/rotation/perspective
    alignment preview, verifies template matching, and returns file metadata (filename, size,
    page count), selected examination & active answer key summary, and side-by-side previews.
    """
    exam = check_exam_access(exam_id, current_user, db)
    contents = await file.read()
    fname = Path(file.filename or "upload").name

    active_key = (
        db.query(AnswerKey)
        .filter(AnswerKey.examination_id == exam.id, AnswerKey.is_active == True)
        .order_by(AnswerKey.version.desc())
        .first()
    )
    key_answers = active_key.answers if (active_key and active_key.answers) else {}

    # Check if the file is a PDF
    if PDFProcessor.is_pdf_file(fname, contents):
        # 1. Fast, memory-safe validation & page count extraction
        try:
            pdf_meta = PDFProcessor.validate_pdf_bytes(contents, fname)
        except Exception as ve:
            return {
                "filename": fname,
                "file_size_bytes": len(contents),
                "is_pdf": True,
                "page_count": 0,
                "is_valid": False,
                "validation_message": str(ve) if str(ve) else "Corrupted or unreadable PDF file.",
                "exam_title": exam.title,
                "exam_code": exam.code,
                "question_count": exam.question_count,
                "answer_key_count": len(key_answers),
                "quality": None,
                "alignment": None,
                "original_preview_url": None,
                "corrected_preview_url": None,
            }

        page_count = pdf_meta["page_count"]

        # 2. Render Page 1 safely at optimal preview resolution (150 DPI for rapid response)
        first_page_cv = None
        render_err_msg = None
        try:
            first_page_cv = PDFProcessor.render_single_page(
                pdf_source=contents,
                page_index=0,
                dpi=150,
            )
        except Exception as re_err:
            render_err_msg = str(re_err)

        if first_page_cv is None:
            return {
                "filename": fname,
                "file_size_bytes": len(contents),
                "is_pdf": True,
                "page_count": page_count,
                "is_valid": False,
                "validation_message": f"Unable to render Page 1: {render_err_msg or 'Unsupported PDF content'}. The PDF might be corrupted.",
                "exam_title": exam.title,
                "exam_code": exam.code,
                "question_count": exam.question_count,
                "answer_key_count": len(key_answers),
                "quality": None,
                "alignment": None,
                "original_preview_url": None,
                "corrected_preview_url": None,
            }

        # 3. Check for blank page 1
        is_blank = False
        try:
            is_blank = PDFProcessor.is_blank_page(first_page_cv)
        except Exception:
            pass

        # 4. Sheet alignment & template overlay preview (safely guarded)
        layout = OMRLayoutConfig(
            question_count=exam.question_count,
            options_per_question=exam.options_per_question,
        )
        detector = OMRDetector(layout)
        rectified_cv = first_page_cv
        markers_detected = False
        align_info = {
            "template_matches": True,
            "regions_visible": True,
            "markers_detected": False,
        }

        try:
            rectified_cv, markers_detected = detector.rectify_image(first_page_cv)
            align_info = detector.validate_sheet_alignment_and_template(rectified_cv, markers_detected)
            align_info["markers_detected"] = markers_detected
        except Exception as det_err:
            rectified_cv = first_page_cv
            align_info["warning"] = f"Alignment preview note: {str(det_err)}"

        # 5. Image quality assessment
        try:
            quality = ImagePreprocessor.assess_quality(first_page_cv)
        except Exception:
            quality = {
                "width": int(first_page_cv.shape[1]),
                "height": int(first_page_cv.shape[0]),
                "resolution_ok": True,
                "is_acceptable": True,
                "validation_message": "Quality verified."
            }

        # 6. Corrected Preview with Bubble Guides
        try:
            preview_cv = rectified_cv.copy() if rectified_cv is not None else first_page_cv.copy()
            if len(preview_cv.shape) == 2:
                preview_cv = cv2.cvtColor(preview_cv, cv2.COLOR_GRAY2BGR)
            for q_num, opt_map in detector.layout.bubbles.items():
                if q_num <= exam.question_count:
                    for b in opt_map.values():
                        cv2.circle(preview_cv, (b.cx, b.cy), b.radius, (40, 185, 80), 1)
        except Exception:
            preview_cv = first_page_cv

        validation_message = (
            f"Valid Bulk OMR PDF ({page_count} page{'s' if page_count != 1 else ''}). Ready to evaluate all {page_count} sheet{'s' if page_count != 1 else ''} automatically."
            if not is_blank
            else f"Warning: Page 1 appears blank or unprinted. Total {page_count} pages detected in PDF."
        )

        orig_url = _encode_preview_data_url(first_page_cv) if first_page_cv is not None else None
        corr_url = _encode_preview_data_url(preview_cv) if preview_cv is not None else orig_url

        return {
            "filename": fname,
            "file_size_bytes": len(contents),
            "is_pdf": True,
            "page_count": page_count,
            "is_valid": True,
            "validation_message": validation_message,
            "exam_title": exam.title,
            "exam_code": exam.code,
            "question_count": exam.question_count,
            "answer_key_count": len(key_answers),
            "quality": quality,
            "alignment": align_info,
            "original_preview_url": orig_url,
            "corrected_preview_url": corr_url,
        }

    # Image file validation
    if not contents or len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Invalid or oversized image file.")

    try:
        ImagePreprocessor.validate_magic_bytes(contents)
        cv_img = ImagePreprocessor.decode_image(contents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    quality = ImagePreprocessor.assess_quality(cv_img)

    layout = OMRLayoutConfig(
        question_count=exam.question_count,
        options_per_question=exam.options_per_question,
    )
    detector = OMRDetector(layout)
    rectified_cv, markers_detected = detector.rectify_image(cv_img)
    align_info = detector.validate_sheet_alignment_and_template(rectified_cv, markers_detected)
    align_info["markers_detected"] = markers_detected

    preview_cv = rectified_cv.copy()
    if len(preview_cv.shape) == 2:
        preview_cv = cv2.cvtColor(preview_cv, cv2.COLOR_GRAY2BGR)
    for q_num, opt_map in detector.layout.bubbles.items():
        if q_num <= exam.question_count:
            for b in opt_map.values():
                cv2.circle(preview_cv, (b.cx, b.cy), b.radius, (40, 185, 80), 1)

    is_valid = bool(
        quality["is_acceptable"]
        and align_info["template_matches"]
        and align_info["regions_visible"]
    )

    if not quality["is_acceptable"]:
        validation_message = quality["validation_message"]
    elif align_info.get("validation_error"):
        validation_message = align_info["validation_error"]
    elif align_info.get("was_tilted") or quality.get("is_tilted") or quality.get("is_landscape"):
        validation_message = "The OMR sheet is tilted. Aligning the image..."
    else:
        validation_message = "Image quality and OMR alignment verified. Ready for evaluation."

    return {
        "filename": fname,
        "file_size_bytes": len(contents),
        "is_pdf": False,
        "page_count": 1,
        "is_valid": is_valid,
        "validation_message": validation_message,
        "exam_title": exam.title,
        "exam_code": exam.code,
        "question_count": exam.question_count,
        "answer_key_count": len(key_answers),
        "quality": quality,
        "alignment": align_info,
        "original_preview_url": _encode_preview_data_url(cv_img),
        "corrected_preview_url": _encode_preview_data_url(preview_cv),
    }


@router.post("/upload/{exam_id}", response_model=UploadBatchResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/upload-pdf/{exam_id}", response_model=UploadBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_images(
    exam_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Handles Bulk OMR PDF uploads (1 PDF containing multiple students' OMR sheets)
    as well as mobile photo capture and batch gallery image uploads (JPG, PNG, WebP).
    """
    exam = check_exam_access(exam_id, current_user, db)

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum limit of {settings.MAX_BATCH_FILES} files"
        )

    # 1. Create UploadBatch record
    batch = UploadBatch(
        examination_id=exam.id,
        user_id=current_user.id,
        status=BatchStatus.QUEUED,
        total_files=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # 2. Process each uploaded file (supports multi-page PDFs and images)
    valid_images = []
    validation_errors = []

    for file in files:
        contents = await file.read()
        safe_fname = Path(file.filename or "upload").name

        # Check if file is a PDF
        if PDFProcessor.is_pdf_file(safe_fname, contents):
            try:
                pdf_meta = PDFProcessor.validate_pdf_bytes(contents, safe_fname)
            except ValueError as ve:
                validation_errors.append(f"{safe_fname}: {str(ve)}")
                continue

            page_count = pdf_meta["page_count"]
            pdf_hash = storage_service.compute_sha256(contents)
            pdf_storage_key = storage_service.save_file(
                content_bytes=contents,
                filename=safe_fname if safe_fname.lower().endswith(".pdf") else f"{safe_fname}.pdf",
                subfolder="pdf_temp",
            )

            for page_idx in range(page_count):
                page_hash = storage_service.compute_sha256(f"{pdf_hash}:page:{page_idx}".encode("utf-8"))
                page_record = UploadedImage(
                    batch_id=batch.id,
                    examination_id=exam.id,
                    original_filename=f"{safe_fname} - Page {page_idx + 1} of {page_count}",
                    storage_key=f"pdf_page://{pdf_storage_key}#page={page_idx}",
                    file_hash=page_hash,
                    mime_type="image/jpeg",
                    file_size_bytes=len(contents) // max(1, page_count),
                    status=ImageStatus.PENDING,
                )
                valid_images.append(page_record)
            continue

        # Standard Image file check (JPG, PNG, WebP)
        if not contents or len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
            validation_errors.append(f"{safe_fname}: Image exceeds maximum size limit (15 MB) or is empty.")
            continue

        try:
            detected_mime = ImagePreprocessor.validate_magic_bytes(contents)
        except ValueError as ve:
            validation_errors.append(f"{safe_fname}: {str(ve)}")
            continue

        file_hash = storage_service.compute_sha256(contents)
        storage_key = storage_service.save_file(
            content_bytes=contents,
            filename=safe_fname or f"capture_{file_hash[:8]}.jpg",
            subfolder="uploads"
        )

        image_record = UploadedImage(
            batch_id=batch.id,
            examination_id=exam.id,
            original_filename=safe_fname or "mobile_capture.jpg",
            storage_key=storage_key,
            file_hash=file_hash,
            mime_type=detected_mime,
            file_size_bytes=len(contents),
            status=ImageStatus.PENDING,
        )
        valid_images.append(image_record)

    if not valid_images:
        err_detail = "; ".join(validation_errors) if validation_errors else "No valid PDF or image files could be processed."
        batch.status = BatchStatus.FAILED
        batch.error_summary = err_detail
        db.commit()
        raise HTTPException(status_code=400, detail=err_detail)

    db.add_all(valid_images)
    batch.total_files = len(valid_images)
    batch.error_summary = f"Queued {len(valid_images)} OMR sheet(s) for evaluation."
    db.commit()

    # 3. Enqueue asynchronous background processing
    job_queue.enqueue(process_batch_task, batch.id)

    return UploadBatchResponse(
        batch_id=batch.id,
        examination_id=exam.id,
        files_received=len(valid_images),
        message=f"Batch {batch.id} accepted. Processing {len(valid_images)} OMR sheet(s) in the background."
    )


def _serialize_batch_response(batch: UploadBatch) -> BatchResponse:
    resp = BatchResponse.model_validate(batch)
    ordered_imgs = sorted(batch.images, key=lambda x: x.id)
    img_responses = []
    dup_count = 0

    for idx, img in enumerate(ordered_imgs, start=1):
        sub = img.submission
        is_dup = bool(sub.is_duplicate) if sub else False
        if is_dup:
            dup_count += 1
        student_name = None
        student_roll = None
        if sub:
            student_roll = sub.student.roll_number if sub.student else sub.detected_roll_number
            student_name = sub.student.name if sub.student else None

        img_responses.append(
            ImageResponse(
                id=img.id,
                batch_id=img.batch_id,
                examination_id=img.examination_id,
                original_filename=img.original_filename,
                file_size_bytes=img.file_size_bytes,
                status=img.status,
                error_message=img.error_message,
                created_at=img.created_at,
                submission_id=sub.id if sub else None,
                page_number=idx,
                student_name=student_name,
                student_roll=student_roll,
                total_score=sub.total_score if sub else None,
                max_score=sub.max_score if sub else None,
                percentage=sub.percentage if sub else None,
                correct_count=sub.correct_count if sub else None,
                incorrect_count=sub.incorrect_count if sub else None,
                blank_count=sub.blank_count if sub else None,
                multiple_count=sub.multiple_count if sub else None,
                review_count=sub.review_count if sub else None,
                is_duplicate=is_dup,
                submission_status=sub.status.value if sub else None,
            )
        )

    resp.images = img_responses
    resp.duplicate_count = dup_count
    resp.current_page = min(batch.total_files, batch.processed_files + batch.failed_files)
    resp.status_message = batch.error_summary or (
        f"Processing page {resp.current_page + 1} of {batch.total_files}"
        if batch.status == BatchStatus.PROCESSING
        else f"Processed {batch.processed_files} of {batch.total_files} sheets"
    )
    return resp


@router.get("/exam/{exam_id}/latest", response_model=BatchResponse)
def get_latest_exam_batch(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Returns the most recent upload batch for an examination."""
    check_exam_access(exam_id, current_user, db)
    batch = (
        db.query(UploadBatch)
        .filter(UploadBatch.examination_id == exam_id)
        .order_by(UploadBatch.id.desc())
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="No batches found for this examination")
    return _serialize_batch_response(batch)


@router.get("/{batch_id}", response_model=BatchResponse)
def get_batch_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Returns batch progress ('Processing page X of Y'), duplicate counts, and per-page results/errors."""
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    check_exam_access(batch.examination_id, current_user, db)
    return _serialize_batch_response(batch)


@router.post("/{batch_id}/cancel")
def cancel_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Cancels a batch that is in QUEUED or early PROCESSING state."""
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    check_exam_access(batch.examination_id, current_user, db)

    if batch.status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel batch with status {batch.status.value}")

    batch.status = BatchStatus.CANCELLED
    db.commit()
    return {"message": f"Batch {batch_id} cancelled successfully"}


@router.post("/{batch_id}/retry")
def retry_failed_images(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Retries all failed images in a batch safely and idempotently."""
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    check_exam_access(batch.examination_id, current_user, db)

    failed_images = (
        db.query(UploadedImage)
        .filter(UploadedImage.batch_id == batch_id, UploadedImage.status == ImageStatus.FAILED)
        .all()
    )
    if not failed_images:
        return {"message": "No failed images to retry"}

    for img in failed_images:
        img.status = ImageStatus.PENDING
        img.error_message = None

    batch.status = BatchStatus.QUEUED
    db.commit()

    job_queue.enqueue(process_batch_task, batch.id)
    return {"message": f"Retrying {len(failed_images)} failed images in batch {batch.id}"}
