from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.audit import AuditLog, ReviewEvent


def log_audit_action(
    db: Session,
    action: str,
    resource_type: str,
    user_id: Optional[int] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Records a secure audit log entry."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def log_review_event(
    db: Session,
    submission_id: int,
    user_id: int,
    question_number: int,
    old_value: str,
    new_value: str,
    reason: str
) -> ReviewEvent:
    """Records human teacher/admin override event for full transparency."""
    event = ReviewEvent(
        submission_id=submission_id,
        user_id=user_id,
        question_number=question_number,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
