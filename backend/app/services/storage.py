import os
import hashlib
from pathlib import Path
from typing import Optional
from backend.app.config import settings


class PrivateStorageService:
    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.local_dir = Path(settings.STORAGE_LOCAL_DIR).resolve()
        self.local_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize subdirectories for local storage
        (self.local_dir / "uploads").mkdir(parents=True, exist_ok=True)
        (self.local_dir / "rectified").mkdir(parents=True, exist_ok=True)
        (self.local_dir / "generated").mkdir(parents=True, exist_ok=True)

    def compute_sha256(self, content_bytes: bytes) -> str:
        """Computes the SHA-256 hash of the given bytes."""
        return hashlib.sha256(content_bytes).hexdigest()

    def save_file(self, content_bytes: bytes, filename: str, subfolder: str = "uploads") -> str:
        """Saves file securely to private storage and returns its storage key."""
        file_hash = self.compute_sha256(content_bytes)
        safe_ext = Path(filename).suffix.lower()
        if safe_ext not in [".jpg", ".jpeg", ".png", ".webp", ".pdf"]:
            safe_ext = ".jpg"
            
        storage_key = f"{subfolder}/{file_hash[:16]}_{filename}"

        if self.backend == "s3" and settings.S3_BUCKET_NAME:
            import boto3
            from botocore.client import Config
            
            s3_client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=Config(signature_version="s3v4")
            )
            s3_client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=storage_key,
                Body=content_bytes
            )
            return storage_key

        # Local storage fallback
        dest_path = self.local_dir / storage_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(content_bytes)

        return storage_key

    def get_file(self, storage_key: str) -> bytes:
        """Retrieves raw file bytes from private storage."""
        if self.backend == "s3" and settings.S3_BUCKET_NAME:
            import boto3
            s3_client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION
            )
            resp = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_key)
            return resp["Body"].read()

        file_path = self.local_dir / storage_key
        if not file_path.exists():
            raise FileNotFoundError(f"Storage key {storage_key} not found")
        with open(file_path, "rb") as f:
            return f.read()

    def get_local_path(self, storage_key: str) -> Optional[str]:
        """Returns local absolute filepath if available on disk."""
        file_path = self.local_dir / storage_key
        if file_path.exists():
            return str(file_path)
        return None

    def delete_file(self, storage_key: str) -> bool:
        """Safely removes file from storage."""
        try:
            if self.backend == "s3" and settings.S3_BUCKET_NAME:
                import boto3
                s3_client = boto3.client("s3")
                s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_key)
                return True
            file_path = self.local_dir / storage_key
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception:
            return False
        return False


storage_service = PrivateStorageService()
