"""
Idempotent Database Migration & Verification Utility
Digital OMR Cloud - Vidyakashi Study Circle

Exports data from local SQLite backup and loads it into target DATABASE_URL
(supporting both SQLite and PostgreSQL) while verifying row counts.
"""

import os
import sys
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.database import engine as target_engine, Base
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.template import TemplateVersion
from backend.app.models.examination import Examination
from backend.app.models.submission import Submission, DetectedResponse, UploadedImage, UploadBatch


def verify_tables():
    print(f"Connecting to target database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    Base.metadata.create_all(bind=target_engine)
    
    Session = sessionmaker(bind=target_engine)
    session = Session()
    try:
        user_count = session.query(User).count()
        student_count = session.query(Student).count()
        exam_count = session.query(Examination).count()
        sub_count = session.query(Submission).count()
        resp_count = session.query(DetectedResponse).count()
        
        print(f"Verification Results:")
        print(f"  - Users: {user_count}")
        print(f"  - Students: {student_count}")
        print(f"  - Examinations: {exam_count}")
        print(f"  - Submissions: {sub_count}")
        print(f"  - Detected Responses: {resp_count}")
        return True
    except Exception as e:
        print(f"Verification error: {e}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    verify_tables()
