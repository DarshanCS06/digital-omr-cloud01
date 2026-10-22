import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.models.examination import Examination, ExaminationAssignment
from backend.app.models.submission import Submission, SubmissionStatus
from backend.app.models.batch import UploadBatch, UploadedImage, BatchStatus, ImageStatus
from backend.app.models.audit import AuditLog
from backend.app.schemas.stats import DashboardStatsResponse, ExamStatsResponse
from backend.app.auth.dependencies import require_teacher_or_admin, check_exam_access

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Statistics"])


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Calculates overall operational metrics."""
    if current_user.role == UserRole.ADMIN:
        total_exams = db.query(Examination).count()
        total_submissions = db.query(Submission).count()
        pending_batches = db.query(UploadBatch).filter(UploadBatch.status.in_([BatchStatus.QUEUED, BatchStatus.PROCESSING])).count()
        failed_imgs = db.query(UploadedImage).filter(UploadedImage.status == ImageStatus.FAILED).count()
        awaiting_review = db.query(Submission).filter(Submission.status == SubmissionStatus.NEEDS_REVIEW).count()
        published_results = db.query(Examination).filter(Examination.is_published == True).count()
        
        recent_audits = (
            db.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .limit(10)
            .all()
        )
    else:
        # Teacher perspective
        assigned_ids = [
            a.examination_id
            for a in db.query(ExaminationAssignment).filter(ExaminationAssignment.user_id == current_user.id).all()
        ]
        my_exams = db.query(Examination).filter((Examination.created_by_id == current_user.id) | (Examination.id.in_(assigned_ids))).all()
        exam_ids = [e.id for e in my_exams]

        total_exams = len(my_exams)
        total_submissions = db.query(Submission).filter(Submission.examination_id.in_(exam_ids)).count() if exam_ids else 0
        pending_batches = db.query(UploadBatch).filter(UploadBatch.examination_id.in_(exam_ids), UploadBatch.status.in_([BatchStatus.QUEUED, BatchStatus.PROCESSING])).count() if exam_ids else 0
        failed_imgs = db.query(UploadedImage).filter(UploadedImage.examination_id.in_(exam_ids), UploadedImage.status == ImageStatus.FAILED).count() if exam_ids else 0
        awaiting_review = db.query(Submission).filter(Submission.examination_id.in_(exam_ids), Submission.status == SubmissionStatus.NEEDS_REVIEW).count() if exam_ids else 0
        published_results = db.query(Examination).filter(Examination.id.in_(exam_ids), Examination.is_published == True).count() if exam_ids else 0

        recent_audits = (
            db.query(AuditLog)
            .filter(AuditLog.user_id == current_user.id)
            .order_by(AuditLog.id.desc())
            .limit(10)
            .all()
        )

    activity_list = [
        {
            "id": a.id,
            "action": a.action,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "timestamp": a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for a in recent_audits
    ]

    return DashboardStatsResponse(
        total_examinations=total_exams,
        total_students_evaluated=total_submissions,
        pending_batches=pending_batches,
        failed_images=failed_imgs,
        sheets_awaiting_review=awaiting_review,
        published_results=published_results,
        recent_activity=activity_list,
    )


@router.get("/exam-stats/{exam_id}", response_model=ExamStatsResponse)
def get_exam_stats(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Calculates granular examination score analytics and score distribution histograms."""
    exam = check_exam_access(exam_id, current_user, db)

    subs = db.query(Submission).filter(Submission.examination_id == exam.id).all()
    total_count = len(subs)
    finalized_count = sum(1 for s in subs if s.status == SubmissionStatus.FINALIZED)
    review_count = sum(1 for s in subs if s.status == SubmissionStatus.NEEDS_REVIEW)

    if total_count == 0:
        return ExamStatsResponse(
            examination_id=exam.id,
            code=exam.code,
            title=exam.title,
            total_submissions=0,
            finalized_submissions=0,
            pending_review=0,
            average_score=0.0,
            highest_score=0.0,
            lowest_score=0.0,
            average_percentage=0.0,
            pass_percentage=0.0,
            score_distribution={"0-20%": 0, "21-40%": 0, "41-60%": 0, "61-80%": 0, "81-100%": 0},
        )

    scores = [s.total_score for s in subs]
    percentages = [s.percentage for s in subs]

    # Distribution brackets
    dist = {"0-20%": 0, "21-40%": 0, "41-60%": 0, "61-80%": 0, "81-100%": 0}
    for p in percentages:
        if p <= 20:
            dist["0-20%"] += 1
        elif p <= 40:
            dist["21-40%"] += 1
        elif p <= 60:
            dist["41-60%"] += 1
        elif p <= 80:
            dist["61-80%"] += 1
        else:
            dist["81-100%"] += 1

    pass_count = sum(1 for p in percentages if p >= 40.0)

    return ExamStatsResponse(
        examination_id=exam.id,
        code=exam.code,
        title=exam.title,
        total_submissions=total_count,
        finalized_submissions=finalized_count,
        pending_review=review_count,
        average_score=round(float(np.mean(scores)), 2),
        highest_score=round(float(np.max(scores)), 2),
        lowest_score=round(float(np.min(scores)), 2),
        average_percentage=round(float(np.mean(percentages)), 2),
        pass_percentage=round((pass_count / total_count) * 100.0, 2),
        score_distribution=dist,
    )


@router.delete("/clear-history")
def clear_portal_history(
    scope: str = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Clears portal history:
    - scope='audit': clears recent audit activity logs only.
    - scope='all': clears all evaluated submissions, batches, uploaded image records, and audit logs.
    - scope='everything': also deletes all examinations.
    """
    from backend.app.models.submission import DetectedResponse, FinalScore
    from backend.app.models.audit import ReviewEvent
    from backend.app.models.answer_key import AnswerKey

    if scope == "audit":
        deleted_audits = db.query(AuditLog).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Cleared {deleted_audits} audit log entries."}

    db.query(ReviewEvent).delete(synchronize_session=False)
    db.query(DetectedResponse).delete(synchronize_session=False)
    db.query(FinalScore).delete(synchronize_session=False)
    deleted_subs = db.query(Submission).delete(synchronize_session=False)
    db.query(UploadedImage).delete(synchronize_session=False)
    db.query(UploadBatch).delete(synchronize_session=False)
    db.query(AuditLog).delete(synchronize_session=False)

    if scope == "everything":
        db.query(AnswerKey).delete(synchronize_session=False)
        db.query(ExaminationAssignment).delete(synchronize_session=False)
        db.query(Examination).delete(synchronize_session=False)

    db.commit()
    return {
        "message": f"Successfully cleared history ({deleted_subs} evaluated sheets removed).",
        "deleted_submissions": deleted_subs,
    }
