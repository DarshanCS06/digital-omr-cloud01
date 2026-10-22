from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.models.examination import Examination, ExaminationAssignment
from backend.app.models.answer_key import AnswerKey
from backend.app.models.submission import Submission, SubmissionStatus
from backend.app.schemas.examination import (
    ExaminationCreate,
    ExaminationUpdate,
    ExaminationResponse,
    AssignmentCreate,
)
from backend.app.schemas.answer_key import AnswerKeyResponse, RescoreRequest
from backend.app.auth.dependencies import (
    get_current_user,
    require_admin,
    require_teacher_or_admin,
    check_exam_access,
)
from backend.app.services.scoring import ScoringEngine
from backend.app.services.audit import log_audit_action

router = APIRouter(prefix="/examinations", tags=["Examinations"])


@router.get("", response_model=List[ExaminationResponse])
def list_examinations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Lists examinations accessible to the current user (RBAC enforced)."""
    if current_user.role == UserRole.ADMIN:
        exams = db.query(Examination).order_by(Examination.id.desc()).all()
    else:
        # Teacher: created by teacher OR assigned to teacher
        assigned_ids = [
            a.examination_id
            for a in db.query(ExaminationAssignment).filter(ExaminationAssignment.user_id == current_user.id).all()
        ]
        exams = (
            db.query(Examination)
            .filter((Examination.created_by_id == current_user.id) | (Examination.id.in_(assigned_ids)))
            .order_by(Examination.id.desc())
            .all()
        )

    results = []
    for e in exams:
        sub_count = db.query(Submission).filter(Submission.examination_id == e.id).count()
        rev_count = db.query(Submission).filter(
            Submission.examination_id == e.id,
            Submission.status == SubmissionStatus.NEEDS_REVIEW
        ).count()
        resp = ExaminationResponse.model_validate(e)
        resp.submissions_count = sub_count
        resp.pending_review_count = rev_count
        results.append(resp)

    return results


@router.post("", response_model=ExaminationResponse, status_code=status.HTTP_201_CREATED)
def create_examination(
    exam_in: ExaminationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Creates a new examination with optional initial answer key."""
    existing = db.query(Examination).filter(Examination.code == exam_in.code.upper().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Examination with this code already exists")

    new_exam = Examination(
        code=exam_in.code.upper().strip(),
        title=exam_in.title.strip(),
        subject=exam_in.subject.strip(),
        class_grade=exam_in.class_grade.strip(),
        exam_date=exam_in.exam_date.strip(),
        question_count=exam_in.question_count,
        options_per_question=exam_in.options_per_question,
        positive_marks=exam_in.positive_marks,
        negative_marks=exam_in.negative_marks,
        blank_marks=exam_in.blank_marks,
        multiple_penalty=exam_in.multiple_penalty,
        allow_teacher_override=exam_in.allow_teacher_override,
        is_published=exam_in.is_published,
        created_by_id=current_user.id,
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)

    # Automatically save initial answer key (or default cyclic A/B/C/D key if none provided)
    opts = ["A", "B", "C", "D"]
    initial_key = (
        exam_in.initial_answers
        if exam_in.initial_answers
        else {str(i): opts[(i - 1) % 4] for i in range(1, new_exam.question_count + 1)}
    )
    ak = AnswerKey(
        examination_id=new_exam.id,
        version=1,
        answers=initial_key,
        is_active=True,
        updated_by_id=current_user.id,
    )
    db.add(ak)
    db.commit()

    log_audit_action(
        db=db,
        action="EXAMINATION_CREATED",
        resource_type="EXAMINATION",
        user_id=current_user.id,
        resource_id=str(new_exam.id),
        details={"code": new_exam.code, "questions": new_exam.question_count}
    )
    return ExaminationResponse.model_validate(new_exam)


@router.get("/{exam_id}", response_model=ExaminationResponse)
def get_examination(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Retrieves examination details with RBAC access check."""
    exam = check_exam_access(exam_id, current_user, db)
    sub_count = db.query(Submission).filter(Submission.examination_id == exam.id).count()
    rev_count = db.query(Submission).filter(
        Submission.examination_id == exam.id,
        Submission.status == SubmissionStatus.NEEDS_REVIEW
    ).count()
    resp = ExaminationResponse.model_validate(exam)
    resp.submissions_count = sub_count
    resp.pending_review_count = rev_count
    return resp


@router.put("/{exam_id}", response_model=ExaminationResponse)
def update_examination(
    exam_id: int,
    exam_in: ExaminationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Updates examination configuration."""
    exam = check_exam_access(exam_id, current_user, db)

    for field, val in exam_in.dict(exclude_unset=True).items():
        setattr(exam, field, val)

    db.commit()
    db.refresh(exam)

    log_audit_action(
        db=db,
        action="EXAMINATION_UPDATED",
        resource_type="EXAMINATION",
        user_id=current_user.id,
        resource_id=str(exam.id),
    )
    return ExaminationResponse.model_validate(exam)


@router.post("/{exam_id}/assign")
def assign_teachers(
    exam_id: int,
    assign_in: AssignmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assigns teachers to an examination (Administrator only)."""
    exam = db.query(Examination).filter(Examination.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    # Clear existing and re-assign
    db.query(ExaminationAssignment).filter(ExaminationAssignment.examination_id == exam_id).delete()
    for t_id in assign_in.teacher_ids:
        t_user = db.query(User).filter(User.id == t_id, User.role == UserRole.TEACHER).first()
        if t_user:
            assignment = ExaminationAssignment(examination_id=exam_id, user_id=t_id)
            db.add(assignment)

    db.commit()
    log_audit_action(
        db=db,
        action="TEACHERS_ASSIGNED",
        resource_type="EXAMINATION",
        user_id=admin.id,
        resource_id=str(exam_id),
        details={"assigned_teacher_ids": assign_in.teacher_ids}
    )
    return {"message": "Teachers assigned successfully"}


@router.get("/{exam_id}/answer-key", response_model=Optional[AnswerKeyResponse])
def get_active_answer_key(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Fetches the active answer key for an examination."""
    check_exam_access(exam_id, current_user, db)
    key = (
        db.query(AnswerKey)
        .filter(AnswerKey.examination_id == exam_id, AnswerKey.is_active == True)
        .order_by(AnswerKey.version.desc())
        .first()
    )
    return key


@router.post("/{exam_id}/rescore")
def rescore_exam(
    exam_id: int,
    rescore_req: RescoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Rescores all examination sheets with a new answer key and mandatory audit explanation."""
    exam = check_exam_access(exam_id, current_user, db)

    # Deactivate older keys
    db.query(AnswerKey).filter(AnswerKey.examination_id == exam_id).update({"is_active": False})

    new_version = db.query(AnswerKey).filter(AnswerKey.examination_id == exam_id).count() + 1
    new_key = AnswerKey(
        examination_id=exam.id,
        version=new_version,
        answers=rescore_req.new_answers,
        is_active=True,
        rescore_reason=rescore_req.reason,
        updated_by_id=current_user.id,
    )
    db.add(new_key)
    db.commit()

    rescored_count = ScoringEngine.rescore_examination(
        examination=exam,
        new_answer_key=rescore_req.new_answers,
        user_id=current_user.id,
        reason=rescore_req.reason,
        db=db,
    )

    return {
        "message": f"Successfully rescored {rescored_count} submissions.",
        "version": new_version,
    }


@router.post("/{exam_id}/publish")
def publish_results(
    exam_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Publishes finalized examination scores (Administrator only)."""
    exam = db.query(Examination).filter(Examination.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examination not found")

    # Check if there are unresolved reviews
    unresolved = (
        db.query(Submission)
        .filter(Submission.examination_id == exam_id, Submission.status == SubmissionStatus.NEEDS_REVIEW)
        .count()
    )
    if unresolved > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish results: {unresolved} submissions still require human review.",
        )

    exam.is_published = True
    db.commit()

    log_audit_action(
        db=db,
        action="EXAMINATION_RESULTS_PUBLISHED",
        resource_type="EXAMINATION",
        user_id=admin.id,
        resource_id=str(exam_id),
    )
    return {"message": "Examination results published successfully"}


@router.delete("/{exam_id}")
def delete_examination(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Deletes an examination and all its associated submissions and batches."""
    from backend.app.models.batch import UploadBatch, UploadedImage
    from backend.app.models.submission import DetectedResponse, FinalScore
    from backend.app.models.audit import ReviewEvent

    exam = check_exam_access(exam_id, current_user, db)
    title = exam.title
    sub_ids = [
        s.id
        for s in db.query(Submission.id).filter(Submission.examination_id == exam_id).all()
    ]
    if sub_ids:
        db.query(ReviewEvent).filter(ReviewEvent.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(DetectedResponse).filter(DetectedResponse.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(FinalScore).filter(FinalScore.submission_id.in_(sub_ids)).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.examination_id == exam_id).delete(synchronize_session=False)
    db.query(UploadedImage).filter(UploadedImage.examination_id == exam_id).delete(synchronize_session=False)
    db.query(UploadBatch).filter(UploadBatch.examination_id == exam_id).delete(synchronize_session=False)
    db.query(AnswerKey).filter(AnswerKey.examination_id == exam_id).delete(synchronize_session=False)
    db.query(ExaminationAssignment).filter(ExaminationAssignment.examination_id == exam_id).delete(synchronize_session=False)
    db.delete(exam)
    db.commit()
    return {"message": f"Examination '{title}' deleted successfully"}
