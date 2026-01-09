import os
from celery import Celery
from app.database import get_session
from app.models import OCRJob
from app.services.ocr import ocr_service
import asyncio

# Configure Celery
# Use Redis as Broker and Backend
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="run_ocr_job")
def run_ocr_job(job_id: str):
    """
    Celery task to run OCR processing asynchronously.
    """
    # Since we are running in a sync worker, we need to bridge to async service if needed,
    # or better yet, make the service agnostic.
    # For now, we will perform a blocking call or run loop.
    
    # 1. Get Job/DB Session
    from sqlmodel import Session, create_engine, select
    
    # We create a new engine/session for the worker
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        job = session.get(OCRJob, job_id)
        if not job:
            return "Job not found"
        
        job.status = "processing"
        session.add(job)
        session.commit()
        
        try:
            # 2. Run OCR (Synchronously or bridge)
            # Since P2T is CPU/GPU intensive, it IS blocking.
            # We call a synchronous version of the logic.
            result_markdown = ocr_service.process_image_sync(job.file_path)
            
            job.result = {
                "markdown": result_markdown,
                "confidence": 0.95 # Mock or derive
            }
            job.status = "completed"
            
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            
        session.add(job)
        session.commit()
        
    return "OK"
