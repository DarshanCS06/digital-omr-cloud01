import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Digital OMR Cloud"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./omr.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+psycopg2://", 1)
            if v.startswith("postgresql://") and not v.startswith("postgresql+psycopg2://"):
                return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    # Security
    SECRET_KEY: str = "c8b0e774591f46399672809e5170d9a6914948a3181823eb9b8cf442e3995f5a"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Task Queue
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_BACKEND: str = "local"  # 'local' or 's3'
    STORAGE_LOCAL_DIR: str = "./storage"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET_NAME: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # Uploads & Rate Limiting
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB for single images
    MAX_PDF_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB for bulk OMR PDFs
    MAX_PDF_PAGES: int = 300
    PDF_RENDER_DPI: int = 200
    MAX_BATCH_FILES: int = 500
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "webp", "pdf"]

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # OMR Detection Calibration
    OMR_SENSITIVITY: str = "NORMAL"  # "HIGH", "NORMAL", "CONSERVATIVE"

    # Initial Admin Bootstrap
    INITIAL_ADMIN_EMAIL: str = "admin@digitalomr.edu"
    INITIAL_ADMIN_PASSWORD: str = "AdminSecurePassword123!"
    INITIAL_ADMIN_NAME: str = "Vidyakashi"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
