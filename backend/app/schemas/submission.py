from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.submission import SubmissionStatus, OptionClassification


class DetectedResponseSchema(BaseModel):
    id: int
    question_number: int
    detected_option: OptionClassification
    final_option: str
    confidence_score: float
    ink_density_a: float
    ink_density_b: float
    ink_density_c: float
    ink_density_d: float
    is_reviewed: bool
    reviewed_option: Optional[OptionClassification] = None
    reviewed_by_id: Optional[int] = None
    review_timestamp: Optional[datetime] = None
    review_reason: Optional[str] = None
    correct_option: Optional[str] = None  # Populated from active answer key

    model_config = ConfigDict(from_attributes=True)


class ReviewOverrideRequest(BaseModel):
    question_number: int
    selected_option: OptionClassification
    reason: str = Field(..., min_length=2, description="Teacher/Admin explanation for override")


class FinalizeSubmissionRequest(BaseModel):
    confirm_all: bool = True


class UpdateStudentDetailsRequest(BaseModel):
    student_name: Optional[str] = None
    student_roll: Optional[str] = None


class SubmissionResponse(BaseModel):
    id: int
    examination_id: int
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    detected_roll_number: Optional[str] = None
    detected_student_name: Optional[str] = None
    name_confidence: float = 0.0
    roll_confidence: float = 0.0
    name_crop_url: Optional[str] = None
    sheet_identifier: Optional[str] = None
    status: SubmissionStatus
    total_score: float
    max_score: float
    percentage: float
    correct_count: int
    incorrect_count: int
    blank_count: int
    multiple_count: int
    review_count: int
    is_duplicate: bool
    submitted_at: datetime
    finalized_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionDetailResponse(SubmissionResponse):
    responses: List[DetectedResponseSchema] = []
    has_original_image: bool = True
    has_rectified_image: bool = True
    has_diagnostic_image: bool = False

