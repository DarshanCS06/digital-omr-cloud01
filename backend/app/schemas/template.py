from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, ConfigDict


class TemplateResponse(BaseModel):
    id: int
    name: str
    question_count: int
    options_per_question: int
    layout_config: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



class GenerateOMRRequest(BaseModel):
    examination_code: str
    exam_title: str
    question_count: int = 100
    options_per_question: int = 4
    include_qr: bool = True
