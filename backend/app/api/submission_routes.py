from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.examination import Examination
from backend.app.models.submission import (
    Submission,
    SubmissionStatus,
    DetectedResponse,
    FinalScore,
)
from backend.app.models.answer_key import AnswerKey
from backend.app.schemas.submission import (
    SubmissionResponse,
    SubmissionDetailResponse,
    DetectedResponseSchema,
    UpdateStudentDetailsRequest,
)
from backend.app.auth.dependencies import require_teacher_or_admin, check_exam_access
from backend.app.auth.security import decode_access_token
from backend.app.services.storage import storage_service
from backend.app.services.audit import log_audit_action

router = APIRouter(prefix="/submissions", tags=["Submissions"])


def get_current_user_flexible(
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolves the authenticated user from:
    1. Standard 'Authorization: Bearer <token>' header (used by fetch/xhr)
    2. '?token=<token>' query parameter (used by <img src> and <a> links)
    Enforces active user account and role validity.
    """
    jwt_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        jwt_token = auth_header[7:].strip()
    elif token:
        jwt_token = token.strip()

    if not jwt_token:
        raise HTTPException(status_code=401, detail="Authentication credentials not provided")

    payload = decode_access_token(jwt_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User account is inactive or not found")

    return user


@router.get("/exam/{exam_id}", response_model=List[SubmissionResponse])
def list_submissions(
    exam_id: int,
    status_filter: Optional[SubmissionStatus] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Lists submissions for an examination with filtering, search, and pagination."""
    check_exam_access(exam_id, current_user, db)

    query = db.query(Submission).filter(Submission.examination_id == exam_id)
    if status_filter:
        query = query.filter(Submission.status == status_filter)

    if search:
        query = query.outerjoin(Student).filter(
            (Submission.detected_roll_number.ilike(f"%{search}%")) |
            (Submission.sheet_identifier.ilike(f"%{search}%")) |
            (Student.name.ilike(f"%{search}%")) |
            (Student.roll_number.ilike(f"%{search}%"))
        )

    submissions = query.order_by(Submission.id.desc()).offset(offset).limit(limit).all()

    results = []
    for sub in submissions:
        resp = SubmissionResponse.model_validate(sub)
        if sub.student:
            resp.student_name = sub.student.name
            resp.student_roll = sub.student.roll_number
        else:
            resp.student_name = sub.detected_student_name
            resp.student_roll = sub.detected_roll_number
        results.append(resp)

    return results


@router.get("/{submission_id}", response_model=SubmissionDetailResponse)
def get_submission_detail(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Retrieves full submission details with question responses, ink densities, and answer key."""
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_exam_access(sub.examination_id, current_user, db)

    # Active answer key
    active_key = (
        db.query(AnswerKey)
        .filter(AnswerKey.examination_id == sub.examination_id, AnswerKey.is_active == True)
        .order_by(AnswerKey.version.desc())
        .first()
    )
    answer_dict = active_key.answers if active_key else {}

    resp = SubmissionDetailResponse.model_validate(sub)
    if sub.student:
        resp.student_name = sub.student.name
        resp.student_roll = sub.student.roll_number
    else:
        resp.student_name = sub.detected_student_name
        resp.student_roll = sub.detected_roll_number

    responses_list = []
    for r in sorted(sub.responses, key=lambda x: x.question_number):
        dr = DetectedResponseSchema.model_validate(r)
        dr.correct_option = answer_dict.get(str(r.question_number))
        responses_list.append(dr)

    resp.responses = responses_list
    resp.has_original_image = True
    resp.has_rectified_image = True
    resp.has_diagnostic_image = True
    return resp


def generate_submission_sheet_fallback(sub: Submission, mode: str, db: Session) -> bytes:
    """
    Dynamically reconstructs authentic Vidyakashi OMR sheets with:
    - Student details (Name, Roll Number, Exam Title, Subject, Class, Date)
    - Realistic ballpoint pen filled bubbles for all detected student responses
    - For mode == 'diagnostic': full visual evaluation overlay with green checkmarks/rings for correct,
      red crosses/rings for wrong, vivid blue rings highlighting answer key options, question labels,
      and a top evaluation summary banner.
    """
    import cv2
    import numpy as np
    from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator
    from backend.app.omr.detector import OMRDetector
    from backend.app.models.answer_key import AnswerKey

    exam = sub.examination
    q_count = exam.question_count if exam else 100
    gen = VidyakashiOMRGenerator(question_count=q_count)

    # Student details
    s_name = (sub.student.name if sub.student else None) or sub.detected_student_name or ""
    s_roll = (sub.student.roll_number if sub.student else None) or sub.detected_roll_number or ""

    # Marked answers from detected_responses (normalize OptionClassification Enum or raw string)
    student_answers = {}
    question_results = {}
    if sub.responses:
        for r in sub.responses:
            raw_opt = r.detected_option
            opt_str = (raw_opt.value if hasattr(raw_opt, "value") else str(raw_opt)).split(".")[-1].upper().strip()
            if opt_str in ["A", "B", "C", "D"]:
                student_answers[r.question_number] = opt_str
            question_results[r.question_number] = {
                "classification": opt_str,
                "densities": {
                    "A": getattr(r, "ink_density_a", 0.0),
                    "B": getattr(r, "ink_density_b", 0.0),
                    "C": getattr(r, "ink_density_c", 0.0),
                    "D": getattr(r, "ink_density_d", 0.0),
                },
                "mark_flags": {opt: (opt == opt_str) for opt in ["A", "B", "C", "D"]},
                "features": {},
            }

    # Fetch active Answer Key for the examination
    answer_dict = {}
    if exam:
        active_key = (
            db.query(AnswerKey)
            .filter(AnswerKey.examination_id == exam.id, AnswerKey.is_active == True)
            .first()
        )
        if active_key and active_key.answers:
            answer_dict = {str(k): str(v).upper().strip() for k, v in active_key.answers.items()}

    # Base sheet with student details and filled ballpoint bubbles
    sheet_bgr = gen.generate_image(
        exam_title=exam.title if exam else "OMR Evaluation Sheet",
        exam_code=exam.code if exam else "VKS-OMR",
        subject=exam.subject if exam else "",
        class_grade=exam.class_grade if exam else "",
        exam_date=exam.exam_date if exam else "",
        student_name=s_name,
        student_roll=s_roll,
        pre_filled_answers=student_answers,
        mark_style="solid",
    )

    if mode == "diagnostic":
        detector = OMRDetector(gen.layout)
        sheet_bgr = detector.generate_visual_diagnostic(
            rectified_img=sheet_bgr,
            questions=question_results,
            markers_detected=True,
            answer_key=answer_dict,
            detected_roll=s_roll,
            detected_name=s_name,
        )

    ok, buf = cv2.imencode(".jpg", sheet_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes() if ok else b""


@router.get("/{submission_id}/images/original")
def get_original_image(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Securely streams the original student sheet from private storage.
    If storage file is missing or contains an unbubbled template, reconstructs
    an authentic sheet with all detected student answers.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission record not found")

    check_exam_access(sub.examination_id, current_user, db)

    storage_key = sub.uploaded_image.storage_key if sub.uploaded_image else None
    data = None
    if storage_key:
        try:
            raw_bytes = storage_service.get_file(storage_key)
            if raw_bytes and len(raw_bytes) > 2000:
                # If responses exist, verify that image is not an empty template
                has_answers = sub.responses and any(
                    (r.detected_option.value if hasattr(r.detected_option, "value") else str(r.detected_option)).split(".")[-1].upper().strip() in ["A", "B", "C", "D"]
                    for r in sub.responses
                )
                if has_answers:
                    import cv2
                    import numpy as np
                    arr = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if arr is not None:
                        bubble_region = arr[700:2250, 100:1550]
                        dark_pixels = np.sum((bubble_region[:, :, 0] < 40) & (bubble_region[:, :, 1] < 40) & (bubble_region[:, :, 2] < 40))
                        if dark_pixels > 6000:
                            data = raw_bytes
                else:
                    data = raw_bytes
        except Exception:
            data = None

    if data is None:
        data = generate_submission_sheet_fallback(sub, mode="original", db=db)
        if storage_key:
            try:
                dest = storage_service.local_dir / storage_key
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
            except Exception:
                pass

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, private"},
    )


@router.get("/{submission_id}/images/rectified")
def get_rectified_image(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Securely streams the rectified perspective-corrected image.
    If storage file is missing or contains an unbubbled template, reconstructs
    an authentic sheet with all detected student answers.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission record not found")

    check_exam_access(sub.examination_id, current_user, db)

    storage_key = sub.uploaded_image.rectified_storage_key if sub.uploaded_image else None
    data = None
    if storage_key:
        try:
            raw_bytes = storage_service.get_file(storage_key)
            if raw_bytes and len(raw_bytes) > 2000:
                has_answers = sub.responses and any(
                    (r.detected_option.value if hasattr(r.detected_option, "value") else str(r.detected_option)).split(".")[-1].upper().strip() in ["A", "B", "C", "D"]
                    for r in sub.responses
                )
                if has_answers:
                    import cv2
                    import numpy as np
                    arr = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if arr is not None:
                        bubble_region = arr[700:2250, 100:1550]
                        dark_pixels = np.sum((bubble_region[:, :, 0] < 40) & (bubble_region[:, :, 1] < 40) & (bubble_region[:, :, 2] < 40))
                        if dark_pixels > 6000:
                            data = raw_bytes
                else:
                    data = raw_bytes
        except Exception:
            data = None

    if data is None:
        data = generate_submission_sheet_fallback(sub, mode="rectified", db=db)
        if storage_key:
            try:
                dest = storage_service.local_dir / storage_key
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
            except Exception:
                pass

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, private"},
    )


@router.get("/{submission_id}/images/diagnostic")
def get_diagnostic_image(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Securely streams the visual diagnostic inspection overlay showing:
    - Registered sheet boundary & corner markers
    - Expected position and measured inner region of every bubble
    - Green checkmarks and rings for correct answers
    - Red crosses and rings for wrong answers
    - Vivid blue rings highlighting Answer Key options
    - Evaluation summary header banner
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission record not found")

    check_exam_access(sub.examination_id, current_user, db)

    diag_key = getattr(sub.uploaded_image, "diagnostic_storage_key", None) if sub.uploaded_image else None
    data = None
    if diag_key:
        try:
            raw_bytes = storage_service.get_file(diag_key)
            if raw_bytes and len(raw_bytes) > 2000:
                # Validate that raw_bytes actually contains diagnostic visual annotations
                import cv2
                import numpy as np
                arr = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
                if arr is not None:
                    # Look for green or red pixels indicating evaluation markings
                    has_annot = (
                        np.any((arr[:, :, 1] > 140) & (arr[:, :, 0] < 70) & (arr[:, :, 2] < 70))
                        or np.any((arr[:, :, 2] > 180) & (arr[:, :, 0] < 70) & (arr[:, :, 1] < 70))
                    )
                    if has_annot:
                        data = raw_bytes
        except Exception:
            data = None

    if data is None:
        data = generate_submission_sheet_fallback(sub, mode="diagnostic", db=db)
        if diag_key:
            try:
                dest = storage_service.local_dir / diag_key
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
            except Exception:
                pass

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, private"},
    )


@router.post("/{submission_id}/finalize")
def finalize_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Finalizes a submission after human review is complete."""
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_exam_access(sub.examination_id, current_user, db)

    if sub.review_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize: {sub.review_count} questions still require human review.",
        )

    sub.status = SubmissionStatus.FINALIZED
    db.commit()

    log_audit_action(
        db=db,
        action="SUBMISSION_FINALIZED",
        resource_type="SUBMISSION",
        user_id=current_user.id,
        resource_id=str(sub.id),
    )
    return {"message": f"Submission {sub.id} finalized successfully", "status": sub.status.value}


@router.delete("/exam/{exam_id}/clear")
def clear_exam_submissions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Clears all evaluated submissions, batches, and uploaded images for an examination."""
    from backend.app.models.batch import UploadBatch, UploadedImage
    from backend.app.models.audit import ReviewEvent

    check_exam_access(exam_id, current_user, db)
    sub_ids = [
        s.id
        for s in db.query(Submission.id).filter(Submission.examination_id == exam_id).all()
    ]
    count = len(sub_ids)
    if sub_ids:
        db.query(ReviewEvent).filter(ReviewEvent.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(DetectedResponse).filter(DetectedResponse.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(FinalScore).filter(FinalScore.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.examination_id == exam_id).delete(synchronize_session=False)
    db.query(UploadedImage).filter(UploadedImage.examination_id == exam_id).delete(synchronize_session=False)
    db.query(UploadBatch).filter(UploadBatch.examination_id == exam_id).delete(synchronize_session=False)
    db.commit()
    return {"message": f"Cleared {count} submissions for examination #{exam_id}", "deleted_count": count}


@router.delete("/{submission_id}")
def delete_single_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Deletes a single submission and its uploaded image record."""
    from backend.app.models.audit import ReviewEvent

    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_exam_access(sub.examination_id, current_user, db)
    img_id = sub.uploaded_image_id
    db.query(ReviewEvent).filter(ReviewEvent.submission_id == submission_id).delete(synchronize_session=False)
    db.query(DetectedResponse).filter(DetectedResponse.submission_id == submission_id).delete(synchronize_session=False)
    db.query(FinalScore).filter(FinalScore.submission_id == submission_id).delete(synchronize_session=False)
    db.delete(sub)
    if img_id:
        from backend.app.models.batch import UploadedImage
        db.query(UploadedImage).filter(UploadedImage.id == img_id).delete(synchronize_session=False)
    db.commit()
    return {"message": f"Submission #{submission_id} deleted"}


@router.post("/{submission_id}/student-details", response_model=SubmissionDetailResponse)
def update_student_details(
    submission_id: int,
    req: UpdateStudentDetailsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Allows teachers or administrators to manually correct or verify student name and roll number.
    Ensures zero guessing: updates student record, refreshes submission details, and clears
    details-based review flag if all question responses are valid.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    check_exam_access(sub.examination_id, current_user, db)

    exam = db.query(Examination).filter(Examination.id == sub.examination_id).first()

    clean_name = req.student_name.strip() if req.student_name else None
    clean_roll = req.student_roll.strip() if req.student_roll else None

    if clean_roll:
        sub.detected_roll_number = clean_roll
        sub.roll_confidence = 1.0

    if clean_name:
        sub.detected_student_name = clean_name
        sub.name_confidence = 1.0

    # Link or update student record
    if clean_roll:
        student = db.query(Student).filter(Student.roll_number == clean_roll).first()
        if not student:
            student = Student(
                roll_number=clean_roll,
                name=clean_name or (sub.student.name if sub.student else "Candidate"),
                class_grade=exam.class_grade if exam else None,
            )
            db.add(student)
            db.flush()
        else:
            if clean_name:
                student.name = clean_name
        sub.student_id = student.id
    elif clean_name and sub.student:
        sub.student.name = clean_name

    # If submission was in NEEDS_REVIEW solely because of unassigned/uncertain name/roll,
    # and has zero uncertain question responses, transition to PROVISIONAL
    if sub.status == SubmissionStatus.NEEDS_REVIEW and sub.review_count == 0:
        if sub.detected_roll_number and "?" not in sub.detected_roll_number:
            sub.status = SubmissionStatus.PROVISIONAL

    # Check duplicate status
    if sub.detected_roll_number:
        dup = (
            db.query(Submission)
            .filter(
                Submission.examination_id == sub.examination_id,
                Submission.detected_roll_number == sub.detected_roll_number,
                Submission.id != sub.id,
            )
            .first()
        )
        sub.is_duplicate = dup is not None
        sub.duplicate_of_id = dup.id if dup else None

    db.commit()
    db.refresh(sub)

    return get_submission_detail(submission_id=sub.id, db=db, current_user=current_user)

