from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.database import Base


class Examination(Base):
    __tablename__ = "examinations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=False)
    class_grade = Column(String(50), nullable=False)
    exam_date = Column(String(20), nullable=False)  # ISO string YYYY-MM-DD
    question_count = Column(Integer, default=100, nullable=False)
    options_per_question = Column(Integer, default=4, nullable=False)
    
    # Marking scheme
    positive_marks = Column(Float, default=1.0, nullable=False)
    negative_marks = Column(Float, default=0.25, nullable=False)
    blank_marks = Column(Float, default=0.0, nullable=False)
    multiple_penalty = Column(Float, default=0.25, nullable=False)
    
    allow_teacher_override = Column(Boolean, default=True, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by_id], back_populates="created_examinations")
    assignments = relationship("ExaminationAssignment", back_populates="examination", cascade="all, delete-orphan")
    answer_keys = relationship("AnswerKey", back_populates="examination", cascade="all, delete-orphan")
    upload_batches = relationship("UploadBatch", back_populates="examination", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="examination", cascade="all, delete-orphan")


class ExaminationAssignment(Base):
    __tablename__ = "examination_assignments"

    id = Column(Integer, primary_key=True, index=True)
    examination_id = Column(Integer, ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (UniqueConstraint("examination_id", "user_id", name="uq_exam_user"),)

    # Relationships
    examination = relationship("Examination", back_populates="assignments")
    user = relationship("User", back_populates="assigned_examinations")
