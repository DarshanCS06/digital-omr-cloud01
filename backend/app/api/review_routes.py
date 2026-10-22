from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.submission import (
    Submission,
    SubmissionStatus,
    DetectedResponse,
    OptionClassification,
)
from backend.app.models.examination import Examination
from backend.app.models.answer_key import AnswerKey
from backend.app.schemas.submission import ReviewOverrideRequest, SubmissionResponse
from backend.app.auth.dependencies import require_teacher_or_admin, check_exam_access
from backend.app.services.scoring import ScoringEngine
from backend.app.services.audit import log_review_event

router = APIRouter(prefix="/reviews", tags=["Human Review Queue"])


@router.get("/exam/{exam_id}", response_model=List[SubmissionResponse])
def get_review_queue(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Retrieves all submissions in an examination that require human review."""
    check_exam_access(exam_id, current_user, db)

    submissions = (
        db.query(Submission)
        .filter(Submission.examination_id == exam_id, Submission.status == SubmissionStatus.NEEDS_REVIEW)
        .order_by(Submission.id.asc())
        .all()
    )

    results = []
    for sub in submissions:
        resp = SubmissionResponse.model_validate(sub)
        if sub.student:
            resp.student_name = sub.student.name
            resp.student_roll = sub.student.roll_number
        else:
            resp.student_roll = sub.detected_roll_number
        results.append(resp)

    return results


@router.post("/override/{submission_id}")
def override_question_response(
    submission_id: int,
    req: ReviewOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Overrides a detected question response with human judgment, updating scores and audit logs."""
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    exam = check_exam_access(sub.examination_id, current_user, db)
    if not exam.allow_teacher_override and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Teacher override has been disabled for this examination")

    response_record = (
        db.query(DetectedResponse)
        .filter(
            DetectedResponse.submission_id == sub.id,
            DetectedResponse.question_number == req.question_number,
        )
        .first()
    )
    if not response_record:
        raise HTTPException(status_code=404, detail="Question response not found")

    old_val = response_record.final_option
    response_record.is_reviewed = True
    response_record.reviewed_option = req.selected_option
    response_record.reviewed_by_id = current_user.id
    response_record.review_timestamp = datetime.now(timezone.utc)
    response_record.review_reason = req.reason
    db.commit()

    # Log immutable review audit event
    log_review_event(
        db=db,
        submission_id=sub.id,
        user_id=current_user.id,
        question_number=req.question_number,
        old_value=old_val,
        new_value=req.selected_option.value,
        reason=req.reason,
    )

    # Recalculate score with updated responses
    active_key = (
        db.query(AnswerKey)
        .filter(AnswerKey.examination_id == exam.id, AnswerKey.is_active == True)
        .order_by(AnswerKey.version.desc())
        .first()
    )
    answer_dict = active_key.answers if active_key else {}

    ScoringEngine.update_submission_score(
        submission=sub,
        examination=exam,
        answer_key=answer_dict,
        db=db,
    )

    return {
        "message": f"Question {req.question_number} updated to {req.selected_option.value}.",
        "new_score": sub.total_score,
        "remaining_review_count": sub.review_count,
        "status": sub.status.value,
    }
