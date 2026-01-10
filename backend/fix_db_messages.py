import os
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel
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
        # Add missing columns to chatmessage
        cols = [
            ("model_used", "VARCHAR"),
            ("tokens_used", "INTEGER DEFAULT 0")
        ]
        for col_name, col_type in cols:
            try:
                conn.execute(text(f"ALTER TABLE chatmessage ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Successfully added column to chatmessage: {col_name}")
            except Exception as e:
                print(f"Could not add column {col_name} (likely already exists): {e}")
                conn.rollback()

    print("Database sync complete.")

if __name__ == "__main__":
    fix_db()
