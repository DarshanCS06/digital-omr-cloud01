import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base


class BatchStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIALLY_FAILED = "PARTIALLY_FAILED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ImageStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    examination_id = Column(Integer, ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(BatchStatus), default=BatchStatus.QUEUED, nullable=False)
    
    total_files = Column(Integer, default=0, nullable=False)
    processed_files = Column(Integer, default=0, nullable=False)
    failed_files = Column(Integer, default=0, nullable=False)
    review_needed_files = Column(Integer, default=0, nullable=False)
    progress_percentage = Column(Float, default=0.0, nullable=False)
    
    error_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    examination = relationship("Examination", back_populates="upload_batches")
    user = relationship("User", back_populates="upload_batches")
    images = relationship("UploadedImage", back_populates="batch", cascade="all, delete-orphan")


class UploadedImage(Base):
    __tablename__ = "uploaded_images"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False)
    examination_id = Column(Integer, ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(500), nullable=False)  # Path in local / s3 private storage
    rectified_storage_key = Column(String(500), nullable=True)
    diagnostic_storage_key = Column(String(500), nullable=True)
    file_hash = Column(String(64), index=True, nullable=False)  # SHA-256
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    
    status = Column(Enum(ImageStatus), default=ImageStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    batch = relationship("UploadBatch", back_populates="images")
    submission = relationship("Submission", back_populates="uploaded_image", uselist=False, cascade="all, delete-orphan")
