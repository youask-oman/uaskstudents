from sqlmodel import Session, select, create_engine
from app.models import OCRJob
from app.database import DATABASE_URL

# Adjust DB URL for local script execution if needed, or run inside container
# Inside container, DATABASE_URL env var should be set.
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    jobs = session.exec(select(OCRJob)).all()
    print(f"Found {len(jobs)} jobs:")
    for job in jobs:
        print(f"ID: {job.id} | Hash: {job.file_hash[:8]}... | Path: {job.file_path} | Status: {job.status}")
