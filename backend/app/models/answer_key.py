from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.database import Base


class AnswerKey(Base):
    __tablename__ = "answer_keys"

    id = Column(Integer, primary_key=True, index=True)
    examination_id = Column(Integer, ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    answers = Column(JSON, nullable=False)  # Dict e.g. {"1": "A", "2": "C", ...}
    is_active = Column(Boolean, default=True, nullable=False)
    rescore_reason = Column(String(500), nullable=True)
    
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    examination = relationship("Examination", back_populates="answer_keys")
    updated_by = relationship("User", foreign_keys=[updated_by_id])
