from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from backend.app.models.batch import BatchStatus, ImageStatus


class ImageResponse(BaseModel):
    id: int
    batch_id: int
    examination_id: int
    original_filename: str
    file_size_bytes: int
    status: ImageStatus
    error_message: Optional[str] = None
    created_at: datetime
    submission_id: Optional[int] = None
    page_number: Optional[int] = None
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    total_score: Optional[float] = None
    max_score: Optional[float] = None
    percentage: Optional[float] = None
    correct_count: Optional[int] = None
    incorrect_count: Optional[int] = None
    blank_count: Optional[int] = None
    multiple_count: Optional[int] = None
    review_count: Optional[int] = None
    is_duplicate: bool = False
    submission_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BatchResponse(BaseModel):
    id: int
    examination_id: int
    user_id: int
    status: BatchStatus
    total_files: int
    processed_files: int
    failed_files: int
    review_needed_files: int
    duplicate_count: int = 0
    current_page: int = 0
    status_message: Optional[str] = None
    progress_percentage: float
    error_summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    images: Optional[List[ImageResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class UploadBatchResponse(BaseModel):
    batch_id: int
    examination_id: int
    files_received: int
    message: str

