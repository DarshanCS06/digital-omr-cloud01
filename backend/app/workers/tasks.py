import cv2
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models.batch import UploadBatch, UploadedImage, BatchStatus, ImageStatus
from backend.app.models.examination import Examination
from backend.app.models.student import Student
from backend.app.models.submission import (
    Submission,
    DetectedResponse,
    SubmissionStatus,
    OptionClassification,
)
from backend.app.models.answer_key import AnswerKey
from backend.app.services.storage import storage_service
from backend.app.services.scoring import ScoringEngine
from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.preprocessor import ImagePreprocessor
from backend.app.omr.detector import OMRDetector
from backend.app.omr.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


def process_single_image(image_id: int, db: Session):
    """Processes a single uploaded OMR image or PDF page idempotently."""
    img_record = db.query(UploadedImage).filter(UploadedImage.id == image_id).first()
    if not img_record:
        return

    # Idempotency guard: if already completed with a valid submission, do not duplicate
    if img_record.status == ImageStatus.COMPLETED and img_record.submission is not None:
        return

    img_record.status = ImageStatus.PROCESSING
    db.commit()

    try:
        pdf_roll: Optional[str] = None
        pdf_name: Optional[str] = None
        # 1. Resolve image or render single PDF page on-demand without loading entire PDF in memory
        if img_record.storage_key.startswith("pdf_page://"):
            spec = img_record.storage_key[len("pdf_page://") :]
            pdf_storage_key, page_str = spec.split("#page=", 1)
            page_idx = int(page_str)

            local_pdf_path = storage_service.get_local_path(pdf_storage_key)
            pdf_source = local_pdf_path if local_pdf_path else storage_service.get_file(pdf_storage_key)

            pdf_roll, pdf_name = PDFProcessor.extract_page_candidate_text(pdf_source, page_idx)

            cv_img = PDFProcessor.render_single_page(
                pdf_source=pdf_source,
                page_index=page_idx,
                dpi=getattr(settings, "PDF_RENDER_DPI", 200),
            )

            # Check for multi-sheet page (e.g. 2 OMR sheets on 1 page)
            segments = PDFProcessor.segment_page_sheets(cv_img)
            if len(segments) > 1:
                cv_img, first_label = segments[0]
                if first_label and f"({first_label})" not in img_record.original_filename:
                    img_record.original_filename = f"{img_record.original_filename} ({first_label})"

                batch_obj = db.query(UploadBatch).filter(UploadBatch.id == img_record.batch_id).first()
                for seg_img, seg_label in segments[1:]:
                    _, seg_buf = cv2.imencode(".jpg", seg_img, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    seg_bytes = seg_buf.tobytes()
                    seg_hash = storage_service.compute_sha256(seg_bytes)
                    seg_key = storage_service.save_file(
                        content_bytes=seg_bytes,
                        filename=f"page_{img_record.id}_{seg_label.replace(' ', '_')}.jpg",
                        subfolder="uploads",
                    )
                    extra_rec = UploadedImage(
                        batch_id=img_record.batch_id,
                        examination_id=img_record.examination_id,
                        original_filename=f"{img_record.original_filename.replace(' (Sheet 1)', '')} ({seg_label})",
                        storage_key=seg_key,
                        file_hash=seg_hash,
                        mime_type="image/jpeg",
                        file_size_bytes=len(seg_bytes),
                        status=ImageStatus.PENDING,
                    )
                    db.add(extra_rec)
                    if batch_obj:
                        batch_obj.total_files += 1
                db.commit()

            # Persist the rendered page JPEG so original sheet inspection works and temp PDF can be cleaned up
            _, page_buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            page_bytes = page_buf.tobytes()
            page_hash = storage_service.compute_sha256(page_bytes)
            saved_page_key = storage_service.save_file(
                content_bytes=page_bytes,
                filename=f"pdf_page_{img_record.id}.jpg",
                subfolder="uploads",
            )
            img_record.storage_key = saved_page_key
            img_record.file_hash = page_hash
            img_record.file_size_bytes = len(page_bytes)
            img_record.mime_type = "image/jpeg"
            db.commit()
        else:
            raw_bytes = storage_service.get_file(img_record.storage_key)
            cv_img = ImagePreprocessor.decode_image(raw_bytes)

        # 2. Check for blank page before quality assessment
        if PDFProcessor.is_blank_page(cv_img):
            img_record.status = ImageStatus.FAILED
            img_record.error_message = "Blank page detected. No OMR answer sheet found on this page."
            db.commit()
            return

        # 3. Assess image quality
        quality = ImagePreprocessor.assess_quality(cv_img)

        if not quality["is_acceptable"]:
            fail_reason = quality.get("validation_message") or "Image quality is insufficient for reliable evaluation."
            img_record.status = ImageStatus.FAILED
            img_record.error_message = fail_reason.strip()
            db.commit()
            return

        # 4. Check for Duplicate File Hash Submissions
        existing_dup = (
            db.query(UploadedImage)
            .filter(
                UploadedImage.examination_id == img_record.examination_id,
                UploadedImage.file_hash == img_record.file_hash,
                UploadedImage.id != img_record.id,
                UploadedImage.status == ImageStatus.COMPLETED
            )
            .first()
        )
        is_dup = existing_dup is not None
        dup_of_id = existing_dup.submission.id if (existing_dup and existing_dup.submission) else None

        # 4. Fetch Exam and Active Answer Key
        exam = db.query(Examination).filter(Examination.id == img_record.examination_id).first()
        if not exam:
            img_record.status = ImageStatus.FAILED
            img_record.error_message = "Associated examination not found"
            db.commit()
            return

        active_key = (
            db.query(AnswerKey)
            .filter(AnswerKey.examination_id == exam.id, AnswerKey.is_active == True)
            .order_by(AnswerKey.version.desc())
            .first()
        )
        answer_dict = active_key.answers if active_key else {}
        if not answer_dict:
            opts_cycle = ["A", "B", "C", "D"]
            auto_key = {str(q_idx): opts_cycle[(q_idx - 1) % 4] for q_idx in range(1, exam.question_count + 1)}
            new_ak = AnswerKey(
                examination_id=exam.id,
                version=1,
                answers=auto_key,
                is_active=True,
                updated_by_id=exam.created_by_id,
            )
            db.add(new_ak)
            db.commit()
            answer_dict = auto_key

        # 5. Execute OMR Processing & Correction Pipeline
        logger.info(f"Processing image {image_id} for exam {exam.id} ({exam.question_count}Q)")
        layout = OMRLayoutConfig(
            question_count=exam.question_count,
            options_per_question=exam.options_per_question
        )
        detector = OMRDetector(layout)
        omr_res = detector.process_omr_sheet(cv_img, answer_key=answer_dict)
        logger.info(
            f"Image {image_id} processed: markers_aligned={omr_res['markers_detected']}, "
            f"uncertain={omr_res['uncertain_questions_count']}"
        )

        # 6. Save rectified and visual diagnostic images to private storage
        rectified_cv = omr_res["rectified_image"]
        _, encoded_buf = cv2.imencode(".jpg", rectified_cv, [cv2.IMWRITE_JPEG_QUALITY, 90])
        rect_storage_key = storage_service.save_file(
            content_bytes=encoded_buf.tobytes(),
            filename=f"rectified_{img_record.id}.jpg",
            subfolder="rectified"
        )
        img_record.rectified_storage_key = rect_storage_key

        diagnostic_cv = omr_res["diagnostic_image"]
        _, diag_buf = cv2.imencode(".jpg", diagnostic_cv, [cv2.IMWRITE_JPEG_QUALITY, 85])
        diag_storage_key = storage_service.save_file(
            content_bytes=diag_buf.tobytes(),
            filename=f"diagnostic_{img_record.id}.jpg",
            subfolder="diagnostics"
        )
        img_record.diagnostic_storage_key = diag_storage_key

        # 6b. Stop evaluation if template does not match or required answer regions are missing
        align_info = omr_res.get("alignment_info", {})
        if not align_info.get("template_matches", True) or not align_info.get("regions_visible", True):
            img_record.status = ImageStatus.FAILED
            img_record.error_message = (
                align_info.get("validation_error")
                or "The sheet layout does not match the selected examination."
            )
            db.commit()
            return

        # 7. Student Identification (Roll No. & Student Name from OMR Sheet or PDF text)
        detected_roll = omr_res.get("detected_roll_number") or pdf_roll
        detected_name = omr_res.get("detected_student_name") or pdf_name
        sheet_id = omr_res.get("sheet_identifier")
        student = None
        if detected_roll and "?" not in detected_roll:
            student = db.query(Student).filter(Student.roll_number == detected_roll).first()
            if not student:
                student = Student(
                    roll_number=detected_roll,
                    name=detected_name or "Unassigned",
                    class_grade=exam.class_grade,
                )
                db.add(student)
                db.commit()
                db.refresh(student)
            elif detected_name and student.name != detected_name:
                student.name = detected_name
                db.commit()
                db.refresh(student)

            # Check for duplicate roll number within the same examination
            existing_roll_sub = (
                db.query(Submission)
                .filter(
                    Submission.examination_id == exam.id,
                    Submission.detected_roll_number == detected_roll,
                    Submission.uploaded_image_id != img_record.id,
                )
                .order_by(Submission.id.asc())
                .first()
            )
            if existing_roll_sub is not None:
                is_dup = True
                dup_of_id = existing_roll_sub.id
        elif detected_name:
            # Student name was recognized on sheet, but Roll No. boxes were unshaded/blank
            student = db.query(Student).filter(Student.name == detected_name).first()
            if not student:
                assigned_roll = f"ROLL-{img_record.id:03d}"
                student = Student(
                    roll_number=assigned_roll,
                    name=detected_name,
                    class_grade=exam.class_grade,
                )
                db.add(student)
                db.commit()
                db.refresh(student)
            detected_roll = student.roll_number

        # 8. Idempotent Submission Handling (Delete existing if retrying)
        existing_sub = db.query(Submission).filter(Submission.uploaded_image_id == img_record.id).first()
        if existing_sub:
            db.delete(existing_sub)
            db.commit()

        submission = Submission(
            examination_id=exam.id,
            student_id=student.id if student else None,
            uploaded_image_id=img_record.id,
            sheet_identifier=sheet_id,
            detected_roll_number=detected_roll,
            is_duplicate=is_dup,
            duplicate_of_id=dup_of_id,
            status=SubmissionStatus.PROVISIONAL if omr_res["uncertain_questions_count"] == 0 else SubmissionStatus.NEEDS_REVIEW,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)

        # 9. Save Question Responses
        resp_objects = []
        for q_num, q_info in omr_res["questions"].items():
            densities = q_info["densities"]
            classification_str = q_info["classification"]
            
            # Map string to enum
            try:
                opt_enum = OptionClassification[classification_str]
            except KeyError:
                opt_enum = OptionClassification.REVIEW

            dr = DetectedResponse(
                submission_id=submission.id,
                question_number=q_num,
                detected_option=opt_enum,
                confidence_score=q_info["confidence"],
                ink_density_a=densities.get("A", 0.0),
                ink_density_b=densities.get("B", 0.0),
                ink_density_c=densities.get("C", 0.0),
                ink_density_d=densities.get("D", 0.0),
            )
            resp_objects.append(dr)

        db.add_all(resp_objects)
        db.commit()

        # 10. Calculate Score against Answer Key
        ScoringEngine.update_submission_score(
            submission=submission,
            examination=exam,
            answer_key=answer_dict,
            db=db
        )

        img_record.status = ImageStatus.COMPLETED
        db.commit()

    except ValueError as ve:
        logger.warning(f"Validation error on image {image_id}: {str(ve)}")
        img_record.status = ImageStatus.FAILED
        img_record.error_message = str(ve)
        db.commit()
    except Exception as e:
        logger.exception(f"Error processing image {image_id}: {str(e)}")
        img_record.status = ImageStatus.FAILED
        img_record.error_message = "Unable to evaluate this page due to an unreadable or unsupported sheet format."
        db.commit()


def process_batch_task(batch_id: int, db: Session | None = None):
    """
    Worker task that processes all images/PDF pages in a batch sequentially with
    live page-by-page progress tracking, retry idempotency, and safe temp PDF cleanup.
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    temp_pdf_keys_to_clean = set()
    batch = None
    try:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if not batch or batch.status == BatchStatus.CANCELLED:
            return

        batch.status = BatchStatus.PROCESSING
        db.commit()

        # Collect any temporary PDF storage keys referenced by this batch
        initial_imgs = db.query(UploadedImage).filter(UploadedImage.batch_id == batch_id).order_by(UploadedImage.id.asc()).all()
        for im in initial_imgs:
            if im.storage_key.startswith("pdf_page://"):
                pdf_k = im.storage_key[len("pdf_page://") :].split("#page=", 1)[0]
                temp_pdf_keys_to_clean.add(pdf_k)

        idx = 0
        while True:
            db.refresh(batch)
            if batch.status == BatchStatus.CANCELLED:
                batch.error_summary = "Batch processing cancelled by user."
                db.commit()
                break

            all_imgs = (
                db.query(UploadedImage)
                .filter(UploadedImage.batch_id == batch_id)
                .order_by(UploadedImage.id.asc())
                .all()
            )
            total_count = len(all_imgs)
            if idx >= total_count:
                break

            img = all_imgs[idx]
            batch.total_files = total_count
            batch.error_summary = f"Processing page {idx + 1} of {total_count}"
            db.commit()

            if img.status != ImageStatus.COMPLETED or img.submission is None:
                process_single_image(img.id, db)

            # Recompute aggregate batch counts
            all_imgs = (
                db.query(UploadedImage)
                .filter(UploadedImage.batch_id == batch_id)
                .order_by(UploadedImage.id.asc())
                .all()
            )
            total_count = len(all_imgs)
            processed_count = sum(1 for x in all_imgs if x.status == ImageStatus.COMPLETED)
            failed_count = sum(1 for x in all_imgs if x.status == ImageStatus.FAILED)
            review_count = sum(
                1
                for x in all_imgs
                if x.status == ImageStatus.COMPLETED
                and x.submission is not None
                and x.submission.status == SubmissionStatus.NEEDS_REVIEW
            )

            batch.total_files = total_count
            batch.processed_files = processed_count
            batch.failed_files = failed_count
            batch.review_needed_files = review_count
            if total_count > 0:
                batch.progress_percentage = round((float(idx + 1) / float(total_count)) * 100.0, 1)
            db.commit()
            idx += 1

        # Final batch state
        db.refresh(batch)
        all_imgs = db.query(UploadedImage).filter(UploadedImage.batch_id == batch_id).all()
        total_count = len(all_imgs)
        processed_count = sum(1 for x in all_imgs if x.status == ImageStatus.COMPLETED)
        failed_count = sum(1 for x in all_imgs if x.status == ImageStatus.FAILED)
        review_count = sum(
            1
            for x in all_imgs
            if x.status == ImageStatus.COMPLETED
            and x.submission is not None
            and x.submission.status == SubmissionStatus.NEEDS_REVIEW
        )
        batch.total_files = total_count
        batch.processed_files = processed_count
        batch.failed_files = failed_count
        batch.review_needed_files = review_count
        batch.completed_at = datetime.now(timezone.utc)

        if batch.status != BatchStatus.CANCELLED:
            if failed_count == 0:
                batch.status = BatchStatus.COMPLETED
                batch.error_summary = f"Completed all {total_count} sheets successfully."
            elif processed_count > 0:
                batch.status = BatchStatus.PARTIALLY_FAILED
                batch.error_summary = f"Evaluated {processed_count} of {total_count} sheets ({failed_count} failed)."
            else:
                batch.status = BatchStatus.FAILED
                batch.error_summary = f"All {total_count} sheets failed validation."

        db.commit()

        # Safely clean up temporary bulk PDF files if no pending pages still reference them
        for pdf_k in temp_pdf_keys_to_clean:
            still_needed = (
                db.query(UploadedImage)
                .filter(UploadedImage.storage_key.like(f"pdf_page://{pdf_k}%"))
                .count()
            )
            if still_needed == 0:
                storage_service.delete_file(pdf_k)

    except Exception as e:
        logger.exception(f"Fatal batch processing error for batch {batch_id}: {str(e)}")
        if batch:
            batch.status = BatchStatus.FAILED
            batch.error_summary = "Batch processing encountered an unexpected error."
            db.commit()
    finally:
        if owns_session:
            db.close()
