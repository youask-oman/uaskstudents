import os
import time
import logging
import traceback
from pathlib import Path
from celery import Celery
from kombu import Queue
from sqlmodel import Session, create_engine
from app.database import get_session
from app.models import OCRJob
from app.services.ocr import ocr_service
from datetime import datetime
import asyncio
from app.services.ocr.block_parser import markdown_block_parser
from app.services.ocr.refinement_service import figure_refinement_service
from app.services.ocr.post_process_service import post_process_service
from app.services.voice.voice_service import voice_service

logger = logging.getLogger(__name__)

# Optional file logging for worker visibility in admin UI.
_log_path = os.environ.get("WORKER_LOG_PATH") or os.environ.get("CELERY_LOG_PATH")
if not _log_path:
    try:
        base_dir = Path(__file__).resolve().parents[1]
        _log_path = str(base_dir / "logs" / "worker.log")
    except Exception:
        _log_path = None

if _log_path:
    try:
        Path(_log_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(_log_path)
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root_logger = logging.getLogger()
        if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
            root_logger.addHandler(file_handler)
            root_logger.setLevel(logging.INFO)
    except Exception as exc:
        logger.warning(f"Worker file logging disabled: {exc}")

def redact_pii(text: str) -> str:
    """Simple regex to mask emails and potential PII in logs"""
    import re
    # Mask emails
    text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL_REDACTED]", text)
    # Mask potential auth tokens (UUIDs)
    text = re.sub(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", "[UUID_REDACTED]", text, flags=re.I)
    return text

# P2: Graceful Shutdown handling
import signal
def handle_exit(sig, frame):
    logger.info(f"Worker received signal {sig}. Closing connections...")
    # SQLModel engine cleanup would go here if we had a global one
    # Celery usually handles this, but explicit logging helps audit

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
    task_default_queue="celery",
    task_queues=(
        Queue("celery"),
        Queue("whatsapp"),
    ),
    task_routes={
        "whatsapp_ocr_extract": {"queue": "whatsapp"},
        "whatsapp_solve": {"queue": "whatsapp"},
    },
    task_annotations={
        "whatsapp_ocr_extract": {
            "rate_limit": os.environ.get("WHATSAPP_OCR_RATE_LIMIT", "20/m"),
        },
        "whatsapp_solve": {
            "rate_limit": os.environ.get("WHATSAPP_SOLVE_RATE_LIMIT", "30/m"),
        },
    },
)

# Register additional task modules
import app.tasks.whatsapp_tasks  # noqa: E402,F401
import app.tasks.subscription_tasks # noqa: E402,F401
import app.tasks.ocr_tasks  # noqa: E402,F401

celery_app.conf.beat_schedule = {
    "daily_subscription_grant": {
        "task": "subscription_grant_job",
        "schedule": 3600.0 * 24, # Daily
    },
    "hourly_subscription_expiry": {
        "task": "subscription_expiry_job",
        "schedule": 3600.0, # Hourly
    },
    "ocr_hold_release_job": {
        "task": "ocr_hold_release_job",
        "schedule": 300.0, # Every 5 minutes
    },
}

# Register signals
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

@celery_app.task(
    name="run_ocr_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=120, # 2 minutes
    hard_time_limit=150  # 2.5 minutes
)
def run_ocr_job(self, job_id: str):
    """
    Celery task to run OCR processing asynchronously.
    """
    from app.models import OCRJob, OCRArtifact, Crop, User, OCRQuestion, OCRChoice, OCRFigure
    
    # Use the same database configuration as the main app
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        job = session.get(OCRJob, job_id)
        if not job:
            return "Job not found"
        
        job.status = "processing"
        job.started_at = datetime.utcnow()
        session.add(job)
        session.commit()
        
        try:
            # 1. Get Crop and Engine info
            crop = session.get(Crop, job.crop_id)
            if not crop:
                raise Exception("Crop not found")
            
            assets_dir = f"storage/ocr_assets/{job_id}"
            os.makedirs(assets_dir, exist_ok=True)

            fast_mode = os.getenv("OCR_FAST_MODE", "0") == "1"
            skip_inventory = fast_mode or os.getenv("OCR_SKIP_INVENTORY", "0") == "1"
            skip_refinement = fast_mode or os.getenv("OCR_SKIP_REFINEMENT", "0") == "1"
            max_refinements = int(os.getenv("OCR_MAX_FIGURE_REFINEMENTS", "3"))

            # Resolve engine: use requested engine, or fall back to "auto" (uses OCR_ENGINE env var)
            engine_to_use = job.requested_engine if job.requested_engine != "auto" else "auto"
            
            # --- STAGE 1: OCR Extraction (Pass 1) ---
            logger.info(f"Running Pass 1 (OCR) for job {job_id} with engine={engine_to_use}...")
            start_time = time.time()
            ocr_result = ocr_service.process_job(
                crop.cropped_storage_url, 
                engine_name=engine_to_use,
                out_dir=assets_dir if engine_to_use == "local" else None
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log which engine was actually used (may differ from requested due to fallback)
            engine_used = ocr_result.get("engine_used", engine_to_use)
            logger.info(f"OCR completed: engine_used={engine_used}, latency={latency_ms}ms")
            
            raw_markdown = ocr_result.get("markdown", "")
            blocks = markdown_block_parser.parse(raw_markdown)

            # Update figure blocks with web URLs
            for b in blocks:
                if b["type"] == "figure" and "asset_id" in b:
                    b["url"] = f"/storage/ocr_assets/{job_id}/{b['asset_id']}"

            # --- STAGE 2: Page-Level Inventory (Pass 2) ---
            if skip_inventory:
                inventory = {
                    "doc_type": "mixed",
                    "questions": [
                        {"id": "1", "prompt": raw_markdown, "choices": [], "has_figure": False}
                    ],
                    "figures": [],
                    "coverage_checklist": {"warnings": ["INVENTORY_SKIPPED"]}
                }
            else:
                logger.info(f"Running Pass 2 (Inventory) for job {job_id}...")
                inventory = post_process_service.process(raw_markdown, None)

            # --- STAGE 3: Figure Refinement (Pass 3) ---
            refined_blocks = blocks
            if not skip_refinement:
                refined_blocks = figure_refinement_service.refine_blocks(
                    blocks,
                    crop.cropped_storage_url,
                    base_dir=assets_dir,
                    max_refinements=max_refinements if max_refinements > 0 else None
                )
            
            # --- STAGE 4: Entity Mapping & Storage ---
            # We merge the Inventory (structural) with OCR (textual)
            # Create the Artifact first
            artifact = OCRArtifact(
                crop_id=crop.id,
                job_id=job.id,
                engine_used=job.requested_engine,
                doc_type=inventory.get("doc_type"),
                page_metadata=inventory.get("page_metadata"),
                instructions=inventory.get("instructions"),
                raw_markdown=raw_markdown,
                plain_text=ocr_result.get("plain_text", ""),
                confidence_score=ocr_result.get("confidence", 0.0),
                provider=ocr_result.get("provider"),
                provider_model=ocr_result.get("provider_model"),
                blocks=refined_blocks,
                derived_json=inventory, # Use inventory as the source of truth for structure
                coverage_checklist=inventory.get("coverage_checklist"),
                timings=ocr_result.get("timings", {}),
                warnings=inventory.get("coverage_checklist", {}).get("warnings", [])
            )
            session.add(artifact)
            session.flush() # Get artifact.id

            # Map Figures
            figure_map = {} # Map external_id -> DB object
            for fig_data in inventory.get("figures", []):
                # Check for refined data in blocks if ids match
                ext_id = fig_data.get("id")
                # Look for matching block to get refined_content/data_json
                description = fig_data.get("description")
                data_json = fig_data.get("data", {})
                
                # Check blocks for refined figure with same ID or content
                for b in refined_blocks:
                    if b["type"] == "refined_figure" and b.get("asset_id") == ext_id:
                        data_json = b.get("data_json", data_json)
                        break

                figure = OCRFigure(
                    artifact_id=artifact.id,
                    external_id=ext_id or "unknown",
                    type=fig_data.get("type", "mixed"),
                    description=description,
                    data_json=data_json
                )
                session.add(figure)
                figure_map[ext_id] = figure
            
            # Map Questions & Choices
            for q_data in inventory.get("questions", []):
                question = OCRQuestion(
                    artifact_id=artifact.id,
                    external_id=q_data.get("id") or "unknown",
                    prompt=q_data.get("prompt", ""),
                    has_figure=q_data.get("has_figure", False),
                    math_expressions=q_data.get("math_expressions", []),
                    notes=q_data.get("notes")
                )
                session.add(question)
                session.flush()

                for c_data in q_data.get("choices", []):
                    choice = OCRChoice(
                        question_id=question.id,
                        label=c_data.get("label", "?"),
                        text=c_data.get("text", "[ILLEGIBLE]")
                    )
                    session.add(choice)

            # --- STAGE 5: Post-Extraction Audit ---
            warnings = artifact.warnings or []
            question_count = inventory.get("coverage_checklist", {}).get("question_count", 0)
            if len(inventory.get("questions", [])) < question_count:
                warnings.append(f"AUDIT_MISSING_QUESTIONS: Found {len(inventory['questions'])} but expected {question_count}")
            
            for q in inventory.get("questions", []):
                # Check for missing choices (typical MCQ has 4)
                if len(q.get("choices", [])) > 0 and len(q.get("choices", [])) < 3:
                     warnings.append(f"AUDIT_MISSING_CHOICES: Question {q.get('id')} has only {len(q['choices'])} choices.")
                
                # Check for missing figure refinement
                if q.get("has_figure") and not q.get("figure_refs"):
                     warnings.append(f"AUDIT_MISSING_FIGURE_REF: Question {q.get('id')} mentions a figure but none linked.")

            artifact.warnings = list(set(warnings))
            session.commit()
            session.refresh(artifact)
            
            # 5. Finalize Job
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            
            # Update Audit Log latency
            from app.services.ocr.audit_log_service import audit_log_service
            audit_log_service.update_latency(session, job.id, latency_ms, artifact.id)

        except Exception as e:
            session.rollback()
            import traceback
            error_msg = redact_pii(f"OCR Job {job_id} failed: {e}\n{traceback.format_exc()}")
            logger.error(error_msg)
            job.status = "failed"
            job.error_message = str(e)
            
        session.add(job)
        session.commit()
        
    return "OK"

@celery_app.task(
    name="run_voice_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    hard_time_limit=90
)
def run_voice_job(self, job_id: int):
    """
    Celery task to run Voice processing asynchronously.
    """
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        voice_service.run_voice_job(session, job_id)
        
    return "OK"
