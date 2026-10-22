from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    total_examinations: int
    total_students_evaluated: int
    pending_batches: int
    failed_images: int
    sheets_awaiting_review: int
    published_results: int
    recent_activity: List[Dict[str, Any]] = []


class ExamStatsResponse(BaseModel):
    examination_id: int
    code: str
    title: str
    total_submissions: int
    finalized_submissions: int
    pending_review: int
    average_score: float
    highest_score: float
    lowest_score: float
    average_percentage: float
    pass_percentage: float  # >= 40%
    score_distribution: Dict[str, int]  # e.g., "0-20": 2, "21-40": 5, ...
