import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.database import Base


class SubmissionStatus(str, enum.Enum):
    PROVISIONAL = "PROVISIONAL"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FINALIZED = "FINALIZED"


class OptionClassification(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    BLANK = "BLANK"
    MULTIPLE = "MULTIPLE"
    REVIEW = "REVIEW"


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    examination_id = Column(Integer, ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    uploaded_image_id = Column(Integer, ForeignKey("uploaded_images.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    sheet_identifier = Column(String(100), index=True, nullable=True)  # Read from QR or barcode
    detected_roll_number = Column(String(50), index=True, nullable=True)  # Read from roll bubbles
    
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.PROVISIONAL, nullable=False)
    
    # Computed metrics
    total_score = Column(Float, default=0.0, nullable=False)
    max_score = Column(Float, default=0.0, nullable=False)
    percentage = Column(Float, default=0.0, nullable=False)
    
    correct_count = Column(Integer, default=0, nullable=False)
    incorrect_count = Column(Integer, default=0, nullable=False)
    blank_count = Column(Integer, default=0, nullable=False)
    multiple_count = Column(Integer, default=0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)
    
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey("submissions.id"), nullable=True)
    
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    finalized_at = Column(DateTime, nullable=True)

    # Relationships
    examination = relationship("Examination", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")
    uploaded_image = relationship("UploadedImage", back_populates="submission")
    responses = relationship("DetectedResponse", back_populates="submission", cascade="all, delete-orphan")
    review_events = relationship("ReviewEvent", back_populates="submission", cascade="all, delete-orphan")
    final_score = relationship("FinalScore", back_populates="submission", uselist=False, cascade="all, delete-orphan")


class DetectedResponse(Base):
    __tablename__ = "detected_responses"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    question_number = Column(Integer, nullable=False)
    
    detected_option = Column(Enum(OptionClassification), nullable=False)
    confidence_score = Column(Float, default=1.0, nullable=False)  # 0.0 to 1.0
    
    # Diagnostic ink densities (0.0 to 1.0)
    ink_density_a = Column(Float, default=0.0, nullable=False)
    ink_density_b = Column(Float, default=0.0, nullable=False)
    ink_density_c = Column(Float, default=0.0, nullable=False)
    ink_density_d = Column(Float, default=0.0, nullable=False)
    
    # Human Review
    is_reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_option = Column(Enum(OptionClassification), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_timestamp = Column(DateTime, nullable=True)
    review_reason = Column(String(500), nullable=True)

    __table_args__ = (UniqueConstraint("submission_id", "question_number", name="uq_sub_question"),)

    # Relationships
    submission = relationship("Submission", back_populates="responses")
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])

    @property
    def final_option(self) -> str:
        """Returns the human-reviewed option if reviewed, else the detected option."""
        if self.is_reviewed and self.reviewed_option:
            return self.reviewed_option.value
        return self.detected_option.value


class FinalScore(Base):
    __tablename__ = "final_scores"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False)
    examination_id = Column(Integer, ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    
    score = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    grade = Column(String(10), nullable=True)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    submission = relationship("Submission", back_populates="final_score")
