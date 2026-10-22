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
    resp.has_original_image = sub.uploaded_image is not None
    resp.has_rectified_image = sub.uploaded_image is not None and sub.uploaded_image.rectified_storage_key is not None
    resp.has_diagnostic_image = sub.uploaded_image is not None and getattr(sub.uploaded_image, "diagnostic_storage_key", None) is not None
    return resp


@router.get("/{submission_id}/images/original")
def get_original_image(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Securely streams the original unrectified image from private storage.
    Preserved and available even if OMR detection or rectification fails.
    Requires teacher or admin access for the associated examination.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub or not sub.uploaded_image:
        raise HTTPException(status_code=404, detail="Submission image record not found")

    check_exam_access(sub.examination_id, current_user, db)

    try:
        data = storage_service.get_file(sub.uploaded_image.storage_key)
        return Response(
            content=data,
            media_type=sub.uploaded_image.mime_type or "image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Original image file not found in storage")


@router.get("/{submission_id}/images/rectified")
def get_rectified_image(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Securely streams the rectified perspective-corrected image.
    Falls back gracefully to the original image if rectification is pending.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub or not sub.uploaded_image:
        raise HTTPException(status_code=404, detail="Submission image record not found")

    check_exam_access(sub.examination_id, current_user, db)

    # Prefer rectified image; fallback to original if rectified key is missing
    storage_key = sub.uploaded_image.rectified_storage_key or sub.uploaded_image.storage_key
    media_type = "image/jpeg" if sub.uploaded_image.rectified_storage_key else (sub.uploaded_image.mime_type or "image/jpeg")

    try:
        data = storage_service.get_file(storage_key)
        return Response(
            content=data,
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Rectified image file not found in storage")


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
    - Classification color-codes (Green=Single, Red=Multiple, Orange=Review, Gray=Blank)
    - Ink density measurements
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub or not sub.uploaded_image:
        raise HTTPException(status_code=404, detail="Submission image record not found")

    check_exam_access(sub.examination_id, current_user, db)

    diag_key = getattr(sub.uploaded_image, "diagnostic_storage_key", None)
    storage_key = diag_key or sub.uploaded_image.rectified_storage_key or sub.uploaded_image.storage_key

    try:
        data = storage_service.get_file(storage_key)
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Diagnostic image file not found in storage")


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

