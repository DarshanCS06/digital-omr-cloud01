import os
import sys
import json
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add repo to path
sys.path.insert(0, os.path.abspath("."))

from backend.app.database import Base
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.template import TemplateVersion
from backend.app.models.examination import Examination, ExaminationAssignment
from backend.app.models.answer_key import AnswerKey
from backend.app.models.batch import UploadBatch, UploadedImage
from backend.app.models.submission import Submission, DetectedResponse, FinalScore
from backend.app.models.audit import AuditLog, ReviewEvent

SQLITE_PATH = os.path.abspath("backups/omr_backup_pre_postgres.db")
PG_URL = "postgresql+psycopg2://vidyakashi_user:CemjwfuW4GbhBz1q8NjigsX4SYKfOuGg@dpg-dbe7v0avcj2c73c1tf1g-a.singapore-postgres.render.com:5432/vidyakashi_omr?sslmode=require"

def migrate():
    print("=" * 60)
    print("STARTING SQLITE -> POSTGRESQL DATA MIGRATION VIA ORM")
    print(f"Source SQLite: {SQLITE_PATH}")
    print("Target Postgres: Render Singapore Instance")
    print("=" * 60)

    # 1. Initialize tables in PostgreSQL
    pg_engine = create_engine(PG_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=pg_engine)
    print("[PASS] Schema created.")

    # 2. SQLite engine & session
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    s_db = SqliteSession()
    p_db = PgSession()

    model_list = [
        (User, "users"),
        (Student, "students"),
        (TemplateVersion, "template_versions"),
        (Examination, "examinations"),
        (ExaminationAssignment, "examination_assignments"),
        (AnswerKey, "answer_keys"),
        (UploadBatch, "upload_batches"),
        (UploadedImage, "uploaded_images"),
        (Submission, "submissions"),
        (DetectedResponse, "detected_responses"),
        (FinalScore, "final_scores"),
        (AuditLog, "audit_logs"),
        (ReviewEvent, "review_events"),
    ]

    for model, t_name in model_list:
        records = s_db.query(model).all()
        print(f"[MIGRATE] {t_name}: {len(records)} records...")
        for r in records:
            # Expunge from sqlite session and merge into postgres session
            s_db.expunge(r)
            p_db.merge(r)
        p_db.commit()

        # Update serial sequence
        if hasattr(model, 'id'):
            with pg_engine.begin() as conn:
                try:
                    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{t_name}', 'id'), COALESCE((SELECT MAX(id) FROM \"{t_name}\"), 1));"))
                except Exception as seq_err:
                    pass

        print(f"[PASS] {t_name} migrated successfully.")

    # Summary
    print("\n[VERIFY] PostgreSQL Record Counts:")
    for model, t_name in model_list:
        count = p_db.query(model).count()
        print(f" - {t_name}: {count} rows")

    exams = p_db.query(Examination).all()
    print("\n[EXAMINATIONS IN POSTGRESQL]:")
    for e in exams:
        print(f" - #{e.id}: {e.code} - {e.title} ({e.question_count}Q)")

    s_db.close()
    p_db.close()
    print("=" * 60)
    print("SQLITE -> POSTGRESQL MIGRATION FINISHED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    migrate()
