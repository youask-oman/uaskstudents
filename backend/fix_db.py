import os
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel
# Import all models to ensure they are registered with SQLModel
from app.models import (
    User, ChatSession, ChatMessage, UsageLog, OCRJob,
    Upload, Crop, OCRArtifact, OCRConfirmation,
    CanonicalProblem, CanonicalSolution, UserSavedSolution,
    OCRQuestion, OCRChoice, OCRFigure
)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@postgres:5432/uask_db")
engine = create_engine(DATABASE_URL)

def fix_db():
    print(f"Connecting to {DATABASE_URL}...")
    with engine.connect() as conn:
        # 1. Add missing columns to ocrartifact
        cols = [
            ("doc_type", "VARCHAR"),
            ("page_metadata", "JSON"),
            ("instructions", "JSON"),
            ("coverage_checklist", "JSON")
        ]
        for col_name, col_type in cols:
            try:
                # Use sub-transaction or just ignore error
                conn.execute(text(f"ALTER TABLE ocrartifact ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Successfully added column: {col_name}")
            except Exception as e:
                print(f"Could not add column {col_name} (likely already exists): {e}")
                conn.rollback()

    # 2. Create new tables if they don't exist
    print("Creating missing tables...")
    SQLModel.metadata.create_all(engine)
    print("Database sync complete.")

if __name__ == "__main__":
    fix_db()
