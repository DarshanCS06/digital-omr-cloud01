from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON
from backend.app.database import Base


class TemplateVersion(Base):
    __tablename__ = "template_versions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # e.g., "OMR-A4-100Q-V1"
    question_count = Column(Integer, nullable=False)
    options_per_question = Column(Integer, default=4, nullable=False)
    layout_config = Column(JSON, nullable=False)  # Stores normalized grid coords, dimensions, markers
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
