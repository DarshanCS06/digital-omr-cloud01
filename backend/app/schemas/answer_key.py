from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class AnswerKeyBase(BaseModel):
    answers: Dict[str, str] = Field(..., description="Mapping of question numbers to options, e.g. {'1': 'A', '2': 'C'}")


class AnswerKeyCreate(AnswerKeyBase):
    rescore_reason: Optional[str] = None


class RescoreRequest(BaseModel):
    new_answers: Dict[str, str]
    reason: str = Field(..., min_length=3, description="Mandatory audit explanation for changing answer key & rescoring")


class AnswerKeyResponse(AnswerKeyBase):
    id: int
    examination_id: int
    version: int
    is_active: bool
    rescore_reason: Optional[str] = None
    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

