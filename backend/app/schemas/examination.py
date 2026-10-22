from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class ExaminationBase(BaseModel):
    code: str = Field(..., max_length=50)
    title: str = Field(..., max_length=255)
    subject: str = Field(..., max_length=100)
    class_grade: str = Field(..., max_length=50)
    exam_date: str = Field(..., max_length=20)  # YYYY-MM-DD
    question_count: int = Field(default=100, ge=1, le=200)
    options_per_question: int = Field(default=4, ge=2, le=5)
    
    # Marking scheme
    positive_marks: float = Field(default=1.0, ge=0.0)
    negative_marks: float = Field(default=0.25, ge=0.0)
    blank_marks: float = Field(default=0.0)
    multiple_penalty: float = Field(default=0.25, ge=0.0)
    allow_teacher_override: bool = True
    is_published: bool = False


class ExaminationCreate(ExaminationBase):
    initial_answers: Optional[Dict[str, str]] = None  # e.g., {"1": "A", "2": "C"}


class ExaminationUpdate(BaseModel):
    title: Optional[str] = None
    subject: Optional[str] = None
    class_grade: Optional[str] = None
    exam_date: Optional[str] = None
    question_count: Optional[int] = None
    positive_marks: Optional[float] = None
    negative_marks: Optional[float] = None
    blank_marks: Optional[float] = None
    multiple_penalty: Optional[float] = None
    allow_teacher_override: Optional[bool] = None
    is_published: Optional[bool] = None


class ExaminationAssignmentResponse(BaseModel):
    user_id: int
    user_name: str
    user_email: str
    assigned_at: datetime


class ExaminationResponse(ExaminationBase):
    id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    submissions_count: int = 0
    pending_review_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AssignmentCreate(BaseModel):
    teacher_ids: List[int]
