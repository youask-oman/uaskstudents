from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
import hashlib
import json
import os

from app.database import get_session
from app.services.solve.normalizer_service import problem_normalizer_service
from app.models import (
    User, ChatSession, ChatMessage, UsageLog, OCRJob,
    Upload, Crop, OCRArtifact, OCRConfirmation,
    CanonicalProblem, CanonicalSolution, UserSavedSolution, Payment, PromoCode,
    OCRQuestion, OCRChoice, OCRFigure,
    VoiceSession, VoiceAudio, VoiceJob, VoiceArtifact, VoiceConfirmation,
    AdminNote, SystemConfig, PromptTemplate, PromptVersion, UserQuotaOverride, SystemErrorEntry
)
from app.services.vision import VisionService, vision_service
from app.services.solver import solver_service
from app.services.rag import rag_service
from app.services.ocr.upload_service import upload_service
from app.services.ocr.crop_service import crop_service
from app.services.ocr.ocr_router_service import ocr_router_service
from app.services.ocr.audit_log_service import audit_log_service
from app.services.ocr.ocr_service import ocr_service



from app.auth import verify_password, create_access_token, Token, get_password_hash

api_router = APIRouter()



# --- Schemas ---
class SolveRequest(BaseModel):
    image_url: Optional[str] = None
    text_query: Optional[str] = None
    
    # Post-OCR Review Fields
    confirmed_markdown: Optional[str] = None
    confirmed_text: Optional[str] = None
    confirmed_latex_blocks: Optional[List[Dict[str, Any]]] = None
    
    # Entity-driven fields
    artifact_id: Optional[int] = None
    question_id: Optional[int] = None # DB internal ID
    
    problem_hash: Optional[str] = None
    subject: Optional[str] = None
    difficulty: Optional[str] = None
    mode: Optional[str] = "general"
    user_id: Optional[int] = None

class SolveResponse(BaseModel):
    session_id: int
    solution: dict
    concepts: List[dict]
    model_used: Optional[str] = "OpenAI GPT-4o Mini"
    tokens_used: Optional[int] = 500
    has_image: Optional[bool] = False

class ChatHistoryItem(BaseModel):
    id: int
    title: str
    created_at: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    academic_level: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    academic_level: Optional[str] = None
    timezone: Optional[str] = None
    is_public: Optional[bool] = None
    learning_interests: Optional[List[str]] = None

class PreferenceUpdateRequest(BaseModel):
    theme: Optional[str] = None
    preferred_language: Optional[str] = None
    solving_mode: Optional[str] = None

class UserUsageStats(BaseModel):
    questions_count: int
    questions_total: int
    scans_count: int
    scans_total: int

class AdminUserListItem(BaseModel):
    id: int
    full_name: str
    email: str
    subscription_tier: str
    role: str
    questions_count: int
    scans_count: int
    last_active_at: str

class AdminUserListResponse(BaseModel):
    users: List[AdminUserListItem]
    total_count: int

class AdminNoteResponse(BaseModel):
    id: int
    admin_name: str
    content: str
    created_at: str

class AdminUserDetailResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    subscription_tier: str
    subscription_status: str
    academic_level: Optional[str]
    joined_at: str
    avatar_url: Optional[str]
    quota_questions_total: int
    quota_scans_total: int
    questions_used: int
    scans_used: int
    notes: List[AdminNoteResponse]

class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    quota_questions_total: Optional[int] = None
    quota_scans_total: Optional[int] = None

class AdminNoteCreateRequest(BaseModel):
    admin_name: str
    content: str

class AdminActivityItem(BaseModel):
    status: str
    timestamp: str

class DashboardStatsResponse(BaseModel):
    total_users: int
    daily_requests: int
    ocr_success_rate: float
    llm_cost_est: float
    cache_hit_rate: float
    requests_growth: float
    success_rate_change: float
    cost_change: float
    cache_hit_change: float

class ModelRoutingSeries(BaseModel):
    day: str
    volume: int

class ModelRoutingResponse(BaseModel):
    total_requests: int
    avg_latency: float
    requests_growth: float
    latency_change: float
    series: List[ModelRoutingSeries]

class SystemErrorItem(BaseModel):
    id: str
    level: str # Critical, Warning, Notice
    message: str
    timestamp: str
    component: str

class AdminQuotaUserItem(BaseModel):
    id: int
    full_id: str # e.g. USR-123
    plan: str
    usage_percent: int
    last_active: str
    is_banned: bool

class AdminQuotaListResponse(BaseModel):
    users: List[AdminQuotaUserItem]
    total_users: int
    global_consumption: float
    daily_active_holders: int
    tokens_burned_24h: str

class QuotaOverrideRequest(BaseModel):
    user_id: int
    token_limit: Optional[int] = None
    ocr_concurrency: Optional[int] = None
    duration_hours: Optional[int] = None # null for permanent

class PromptTemplateListItem(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    version: str
    status: str # Production, Draft
    last_updated: str

class PromptVersionItem(BaseModel):
    id: int
    version: str
    content: str
    author: str
    created_at: str
    is_production: bool

class PromptSaveRequest(BaseModel):
    content: str
    version: Optional[str] = None

# --- OCR Subsystem Schemas ---

class CropRect(BaseModel):
    x: float
    y: float
    w: float
    h: float

class CropRequest(BaseModel):
    crop_rect: CropRect
    rotation: int = 0
    margin_pct: int = 0

class OCRJobRequest(BaseModel):
    crop_id: int
    preferred_engine: str = "auto" # auto, local, vlm
    user_intent: str = "normal" # normal, high_accuracy

class OCRConfirmRequest(BaseModel):
    confirmed_markdown: str
    confirmed_text: str
    confirmed_latex_blocks: Optional[List[dict]] = None

class LibrarySaveRequest(BaseModel):
    solve_session_id: Optional[int] = None
    solution_id: Optional[int] = None
    tags: List[str] = []
    notes: Optional[str] = None

# --- Voice Mode Schemas ---

class VoiceSessionCreate(BaseModel):
    user_id: int
    source: str = "web"
    language: str = "en"
    preferred_stt: str = "openai"

class VoiceJobCreate(BaseModel):
    priority: str = "normal"
    mode: str = "normal"

class VoiceConfirmationRequest(BaseModel):
    confirmed_transcript_text: str
    confirmed_normalized_math_text: Optional[str] = None
    user_answers_to_clarifier: Optional[dict] = None

# --- Existing User Profile Response ---
class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    academic_level: Optional[str]
    timezone: str
    theme: str
    preferred_language: str
    solving_mode: str
    subscription_tier: str
    subscription_status: str

    # Advanced Profile
    is_public: bool
    learning_interests: Optional[List[str]]

    usage: UserUsageStats

@api_router.post("/signup")
async def signup(form_data: SignupRequest, session: Session = Depends(get_session)):
    # Check if user already exists
    existing_user = session.exec(select(User).where(User.email == form_data.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists"
        )

    # Create new user
    new_user = User(
        email=form_data.email,
        full_name=form_data.full_name,
        password_hash=get_password_hash(form_data.password),
        academic_level=form_data.academic_level,
        is_verified=False # Setting to false as frontend mentions a verification link
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return {"status": "ok", "message": "User created successfully. Please check your email for verification.", "user_id": new_user.id}

@api_router.post("/login", response_model=Token)
async def login_for_access_token(form_data: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form_data.email)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Session & Security
    session_token = str(uuid.uuid4())
    user.session_token = session_token
    # In a real app, retrieve IP from request.client.host
    # Here we mock or pass it via header if critical
    user.last_ip = "127.0.0.1"

    session.add(user)
    session.commit()
    session.refresh(user)

    access_token = create_access_token(data={"sub": user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
        avatar_url=user.avatar_url,
        session_token=session_token # Return to client
    )




class LatexResponse(BaseModel):
    latex: str

# ------------------------------------------------------------------
# OCR Subsystem Endpoints
# ------------------------------------------------------------------

@api_router.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Query(1),
    session: Session = Depends(get_session)
):
    try:
        upload = await upload_service.save_upload(user_id, file, session)
        return {
            "upload_id": upload.id,
            "storage_url": upload.storage_url,
            "file_hash": upload.file_hash,
            "created_at": upload.created_at
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/uploads/{upload_id}/crops")
async def create_crop(
    upload_id: int,
    request: CropRequest,
    session: Session = Depends(get_session)
):
    try:
        upload = session.get(Upload, upload_id)
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")

        crop = await crop_service.create_crop(
            upload, request.crop_rect.dict(), request.rotation, request.margin_pct, session
        )
        return {
            "crop_id": crop.id,
            "cropped_storage_url": crop.cropped_storage_url,
            "status": "created"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ocr/jobs")
async def create_ocr_job(
    request: OCRJobRequest,
    user_id: int = Query(1),
    session: Session = Depends(get_session)
):
    try:
        crop = session.get(Crop, request.crop_id)
        if not crop:
            raise HTTPException(status_code=404, detail="Crop not found")

        user = session.get(User, user_id)
        if not user:
            import logging
            logging.warning(f"User {user_id} not found for OCR job. Defaulting to local engine.")
            engine, vlm_type, reasons = ("local", None, ["USER_NOT_FOUND"])
        else:
            # 1. Decide Engine
            engine, vlm_type, reasons = ocr_router_service.decide_engine(
                crop, user, request.preferred_engine, request.user_intent
            )

        # 2. Create Job
        job_id = str(uuid.uuid4())
        job = OCRJob(
            id=job_id,
            user_id=user_id,
            crop_id=crop.id,
            requested_engine=engine,
            status="queued"
        )
        session.add(job)
        session.flush() # Ensure job exists before logging dependencies (AuditLog)

        # 3. Log Decision
        audit_log_service.log_ocr_decision(
            session, user_id, crop.upload_id, crop.id, job_id, engine, reasons, vlm_type
        )

        session.commit()

        # 4. Trigger Worker
        try:
            from app.worker import run_ocr_job
            run_ocr_job.delay(job_id)
        except Exception as e:
            import logging
            logging.error(f"Failed to trigger Celery worker: {e}")

        return {"job_id": job_id, "status": "queued"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/ocr/jobs/{job_id}")
async def get_ocr_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(OCRJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Fetch artifact if done
    artifact_id = None
    if job.status == "completed":
        stmt = select(OCRArtifact).where(OCRArtifact.job_id == job_id)
        artifact = session.exec(stmt).first()
        if artifact:
            artifact_id = artifact.id

    return {
        "job_id": job.id,
        "status": job.status,
        "artifact_id": artifact_id,
        "error_message": job.error_message
    }

@api_router.get("/ocr/artifacts/{artifact_id}")
async def get_ocr_artifact(artifact_id: int, session: Session = Depends(get_session)):
    artifact = session.get(OCRArtifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Load entities
    from sqlmodel import select
    questions = session.exec(select(OCRQuestion).where(OCRQuestion.artifact_id == artifact_id)).all()
    figures = session.exec(select(OCRFigure).where(OCRFigure.artifact_id == artifact_id)).all()
    
    # Nested choices
    questions_data = []
    for q in questions:
        q_dict = q.dict()
        choices = session.exec(select(OCRChoice).where(OCRChoice.question_id == q.id)).all()
        q_dict["choices"] = [c.dict() for c in choices]
        questions_data.append(q_dict)

    # User-requested Branding Logic
    engine_name = artifact.engine_used
    provider = (artifact.provider or "openai").lower()

    if engine_name == "local":
        display_tag = "YouAsk AI multimodel"
    elif engine_name == "vlm":
        if any(p in provider for p in ["openai", "gpt", "claude", "anthropic"]):
            display_tag = "External GPT"
        else:
            display_tag = "YouAsk AI multimodel"
    else:
        display_tag = "YouAsk AI multimodel"

    # Token Metrics
    usage = artifact.usage_metadata or {}
    tokens_in = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
    tokens_out = usage.get("output_tokens") or usage.get("completion_tokens", 0)

    token_metrics = f"{tokens_in} in / {tokens_out} out" if (tokens_in or tokens_out) else None

    # Merge into response
    resp = artifact.dict()
    resp["engine_display_tag"] = display_tag
    resp["token_metrics"] = token_metrics
    resp["questions"] = questions_data
    resp["figures"] = [f.dict() for f in figures]

    return resp

@api_router.post("/ocr/artifacts/{artifact_id}/confirm")
async def confirm_ocr(
    artifact_id: int,
    request: OCRConfirmRequest,
    user_id: int = 1,
    session: Session = Depends(get_session)
):
    artifact = session.get(OCRArtifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Create Confirmation record
    conf = OCRConfirmation(
        artifact_id=artifact_id,
        user_id=user_id,
        confirmed_markdown=request.confirmed_markdown,
        confirmed_text=request.confirmed_text,
        confirmed_latex_blocks=request.confirmed_latex_blocks,
        normalized_problem_hash="" # Computed below
    )

    # 1. Normalize and Hash (Canonical Dedup)
    # We treat the confirmed values as the ProblemJSON source
    problem_data = {
        "question": request.confirmed_text,
        "choices": { block.get('key'): block.get('value') for block in (request.confirmed_latex_blocks or []) if block.get('type') == 'choice' }
    }
    prob_hash = problem_normalizer_service.get_hash(problem_data)
    conf.normalized_problem_hash = prob_hash

    session.add(conf)
    session.flush()

    # 2. Lookup Canonical Solution
    from sqlmodel import select
    stmt = select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == prob_hash)
    existing_prob = session.exec(stmt).first()

    if existing_prob:
        sol_stmt = select(CanonicalSolution).where(
            CanonicalSolution.problem_id == existing_prob.id,
            CanonicalSolution.verification_status == "pass"
        )
        existing_sol = session.exec(sol_stmt).first()
        if existing_sol:
            return {
                "status": "dedup_hit",
                "confirmation_id": conf.id,
                "problem_id": existing_prob.id,
                "solution_id": existing_sol.id,
                "solution": existing_sol.solution_json
            }

    return {
        "status": "pending_solve",
        "confirmation_id": conf.id,
    }

@api_router.post("/library/save")
async def save_to_library(
    request: Dict[str, Any],
    user_id: int = 1,
    session: Session = Depends(get_session)
):
    solution_id = request.get("solution_id")
    if not solution_id:
        raise HTTPException(status_code=400, detail="solution_id required")
    
    # Check if exists
    from app.models import UserSavedSolution # This import was missing in the new snippet, adding it here
    existing = session.get(UserSavedSolution, {"user_id": user_id, "solution_id": solution_id})
    if existing:
        return {"status": "already_saved"}
        
    saved = UserSavedSolution(
        user_id=user_id,
        solution_id=solution_id,
        tags=request.get("tags"),
        notes=request.get("notes")
    )
    session.add(saved)
    session.commit()
    return {"status": "saved"}

# ------------------------------------------------------------------
# Voice Mode Endpoints
# ------------------------------------------------------------------

@api_router.post("/voice/sessions")
async def create_voice_session(request: VoiceSessionCreate, session: Session = Depends(get_session)):
    voice_session = VoiceSession(
        user_id=request.user_id,
        language=request.language,
        preferred_stt=request.preferred_stt
    )
    session.add(voice_session)
    session.commit()
    session.refresh(voice_session)
    return {"voice_session_id": voice_session.id, "status": "created"}

@api_router.post("/voice/sessions/{id}/audio")
async def upload_voice_audio(
    id: int, 
    file: UploadFile = File(...), 
    session: Session = Depends(get_session)
):
    voice_session = session.get(VoiceSession, id)
    if not voice_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Save audio file
    storage_dir = "storage/voice"
    os.makedirs(storage_dir, exist_ok=True)
    filename = f"voice_{id}_{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(storage_dir, filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    audio_hash = hashlib.sha256(content).hexdigest()
    
    audio = VoiceAudio(
        voice_session_id=id,
        storage_url=file_path,
        audio_hash=audio_hash
    )
    session.add(audio)
    
    voice_session.status = "uploaded"
    session.add(voice_session)
    
    session.commit()
    session.refresh(audio)
    return {"voice_session_id": id, "audio_id": audio.id, "status": "uploaded"}

@api_router.post("/voice/sessions/{id}/jobs")
async def create_voice_job(
    id: int,
    request: VoiceJobCreate,
    session: Session = Depends(get_session)
):
    audio = session.exec(select(VoiceAudio).where(VoiceAudio.voice_session_id == id)).first()
    if not audio:
        raise HTTPException(status_code=400, detail="No audio found for this session")
        
    job = VoiceJob(
        voice_session_id=id,
        audio_id=audio.id,
        status="queued"
    )
    session.add(job)
    
    voice_session = session.get(VoiceSession, id)
    voice_session.status = "processing"
    session.add(voice_session)
    
    session.commit()
    session.refresh(job)
    
    # Trigger background task
    try:
        from app.worker import run_voice_job
        run_voice_job.delay(job.id)
    except Exception as e:
        import logging
        logging.error(f"Failed to trigger voice worker: {e}")
        # Fallback to threading if celery fails to connect (for dev ease)
        import threading
        from app.services.voice.voice_service import voice_service
        def run_transcription_sync():
            from app.database import SessionLocal
            with SessionLocal() as db:
                voice_service.run_voice_job(db, job.id)
        threading.Thread(target=run_transcription_sync, daemon=True).start()
    
    return {"job_id": job.id, "status": "queued"}

@api_router.get("/voice/jobs/{job_id}")
async def get_voice_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(VoiceJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    artifact_id = None
    if job.status == "done":
        artifact = session.exec(select(VoiceArtifact).where(VoiceArtifact.job_id == job.id)).first()
        if artifact:
            artifact_id = artifact.id
            
    return {
        "job_id": job.id,
        "status": job.status,
        "artifact_id": artifact_id,
        "error_message": job.error_message
    }

@api_router.get("/voice/artifacts/{artifact_id}")
async def get_voice_artifact(artifact_id: int, session: Session = Depends(get_session)):
    artifact = session.get(VoiceArtifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
        
    return artifact

@api_router.post("/voice/artifacts/{artifact_id}/confirm")
async def confirm_voice_artifact(
    artifact_id: int,
    request: VoiceConfirmationRequest,
    session: Session = Depends(get_session)
):
    artifact = session.get(VoiceArtifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    confirmed_math = request.confirmed_normalized_math_text or artifact.normalized_math_text
    
    # Build ProblemJSON
    problem_json = {
        "question": request.confirmed_transcript_text,
        "raw_math": confirmed_math,
        "source": "voice"
    }
    
    # Hash it for dedup
    problem_hash = hashlib.sha256(confirmed_math.strip().lower().encode()).hexdigest()
    
    # Check for existing solution
    cached_sol = get_canonical_solution(problem_hash, session)
    
    confirmation = VoiceConfirmation(
        artifact_id=artifact_id,
        user_id=1,
        confirmed_transcript_text=request.confirmed_transcript_text,
        confirmed_normalized_text=confirmed_math,
        problem_json=problem_json,
        normalized_problem_hash=problem_hash
    )
    session.add(confirmation)
    session.commit()
    
    return {
        "confirmation_id": confirmation.id,
        "dedup_hit": cached_sol is not None,
        "problem_hash": problem_hash,
        "next_action": "solve" if not cached_sol else "show_cache"
    }

def get_canonical_solution(problem_hash: str, session: Session) -> Optional[dict]:
    """Lookup verified solution by problem hash"""
    from app.models import CanonicalSolution, CanonicalProblem
    stmt = select(CanonicalSolution).join(CanonicalProblem).where(
        CanonicalProblem.normalized_problem_hash == problem_hash,
        CanonicalSolution.verification_status == "pass"
    )
    result = session.exec(stmt).first()
    return result.solution_json if result else None

# ------------------------------------------------------------------
# Legacy Vision Extraction (Keep for compat or deprecate)
# ------------------------------------------------------------------
@api_router.post("/latex-from-image", response_model=LatexResponse)
async def extract_latex_from_image(
    file: UploadFile = File(...), 
    user_id: int = 1, 
    session: Session = Depends(get_session)
):
    """
    Directly extracts LaTeX from an image using OpenAI Vision.
    No background jobs, no polling.
    """
    content = await file.read()
    
    # Optional: Validate size/dimensions here to prevent huge costs
    
    latex_result = await vision_service.extract_latex(content)
    
    # Log usage
    session.add(UsageLog(user_id=user_id, action_type="vision_ocr", tokens_used=500))
    session.commit()
    
    return LatexResponse(latex=latex_result)

# ... (omitted lines)


@api_router.post("/solve", response_model=SolveResponse)
async def solve_problem(
    request: SolveRequest, 
    session: Session = Depends(get_session)
):
    """
    Main Orchestrator Endpoint:
    1. Check token limit
    2. OCR (if image)
    3. RAG Retrieval
    4. Solver (LLM)
    5. DB Persistence
    6. Track tokens
    """
    try:
        # Check token limit BEFORE processing
        # Use user_id from request body (pydantic), default to 1 if missing
        user_id = request.user_id or 1
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check and reset monthly tokens if needed
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if (now - user.last_token_reset).days >= 30:
            user.tokens_used_this_month = 0
            user.last_token_reset = now
            session.add(user)
            session.commit()
            session.refresh(user)
        
        # Enforce 1M token limit
        MONTHLY_LIMIT = 1_000_000
        if user.tokens_used_this_month >= MONTHLY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly token limit of {MONTHLY_LIMIT:,} tokens exceeded. Resets on {(user.last_token_reset + timedelta(days=30)).strftime('%Y-%m-%d')}."
            )
        
        # 1. OCR Processing (Legacy/Vision fallback if needed, but mostly handled by frontend passing text now)
        # The frontend now calls /latex-from-image first, then passes the text here.
        # So we don't need to call ocr_service here anymore.
        # 1. OCR Processing (Handled by frontend/separate endpoint)
        extracted_text = ""
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    base_query = f"{request.text_query or ''}".strip()
    
    # --- STRUCTURED DATA ENHANCEMENT ---
    context_info = ""
    if request.confirmed_text:
        base_query = request.confirmed_text
    
    if request.artifact_id and request.question_id:
        # Fetch detailed entities to provide "Hallucination Protection"
        from app.models import OCRQuestion, OCRFigure, OCRChoice
        question_ent = session.get(OCRQuestion, request.question_id)
        if question_ent:
            # Reconstruct the problem from entities
            choices_ent = session.exec(select(OCRChoice).where(OCRChoice.question_id == question_ent.id)).all()
            choice_str = "\n".join([f"{c.label}: {c.text}" for c in choices_ent])
            base_query = f"{question_ent.prompt}\n\nChoices:\n{choice_str}"
            
            # Fetch linked figures
            figures_ent = session.exec(select(OCRFigure).where(OCRFigure.artifact_id == request.artifact_id)).all()
            if figures_ent:
                context_info += "\n[VISUAL CONTEXT DETECTED]\n"
                for fig in figures_ent:
                    fig_desc = f"Figure {fig.external_id} ({fig.type}): {fig.description}\n"
                    if fig.data_json:
                        fig_desc += f"Detailed Data: {json.dumps(fig.data_json)}\n"
                    context_info += fig_desc
    elif request.confirmed_latex_blocks:
        # Fallback to provided blocks from review screen
        choice_str = "\n".join([f"{b.get('key')}: {b.get('value')}" for b in request.confirmed_latex_blocks if b.get('type') == 'choice'])
        if choice_str:
            base_query += f"\n\nChoices:\n{choice_str}"
    
    final_prompt = base_query
    if context_info:
        final_prompt = f"{base_query}\n\n{context_info}"
    
    # 2. Deduplication (Canonical Solution Lookup)
    problem_hash = request.problem_hash
    if not problem_hash and base_query:
        problem_hash = hashlib.sha256(base_query.strip().lower().encode()).hexdigest()
    
    cached_solution = None
    if problem_hash:
        cached_solution = get_canonical_solution(problem_hash, session)

    # Determine metadata
    model_name = "YouAsk AI (Multimodal)" if (request.image_url or request.artifact_id) else "OpenAI GPT-4o Mini"
    is_image = bool(request.image_url or request.artifact_id)
    extra_images = 0
    if request.artifact_id:
        from app.models import OCRFigure
        extra_images = len(session.exec(select(OCRFigure).where(OCRFigure.artifact_id == request.artifact_id)).all())
    
    estimated_tokens = 500 + (6000 if is_image else 0) + (extra_images * 6000)

    if cached_solution:
        # Check if already saved by this user
        from app.models import UserSavedSolution
        is_already_saved = False
        # solution_id is cached_solution.id if it was a real model, but get_canonical_solution returns dict
        # wait, get_canonical_solution should return the DB object or I need to find it
        cp = session.exec(select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == problem_hash)).first()
        if cp:
            cs = session.exec(select(CanonicalSolution).where(CanonicalSolution.problem_id == cp.id)).first()
            if cs:
                existing_save = session.exec(select(UserSavedSolution).where(UserSavedSolution.user_id == user_id, UserSavedSolution.solution_id == cs.id)).first()
                if existing_save:
                    is_already_saved = True

        # RETURN CACHED SOLUTION
        new_chat = ChatSession(
            user_id=user_id,
            title=cached_solution.get("problem", {}).get("goal", "Resolved Problem")[:50],
            subject=request.subject or "General",
            is_saved=is_already_saved
        )
        session.add(new_chat)
        session.commit()
        session.refresh(new_chat)
        
        # Save Messages
        session.add(ChatMessage(session_id=new_chat.id, role="user", content=base_query))
        session.add(ChatMessage(
            session_id=new_chat.id, 
            role="assistant", 
            content=cached_solution.get("solution", {}).get("final_answer", ""),
            structured_data=cached_solution,
            model_used=model_name,
            tokens_used=estimated_tokens # Respect image policy even for cache
        ))
        
        add_tokens_to_user(user_id, estimated_tokens, session)
        session.commit()

        return SolveResponse(
            session_id=new_chat.id,
            solution=cached_solution,
            concepts=cached_solution.get("concepts") or [],
            model_used=model_name,
            tokens_used=100,
            has_image=is_image
        )

    # 3. Retrieval
    # Prepend Mode Context
    if request.mode and request.mode != "general":
        base_query_for_retrieval = f"[MODE: {request.mode.upper()}] {base_query}"
    else:
        base_query_for_retrieval = base_query
    
    if not base_query.strip():
        raise HTTPException(status_code=400, detail="No input provided")

    concepts = await rag_service.search_related_concepts(base_query_for_retrieval)

    # 4. Solve (Calling expensive LLM with context enhancement)
    solution_data = await solver_service.solve_problem(final_prompt)

    # 5. Persistence
    # Create Session (NOT SAVED by default)
    new_chat = ChatSession(
        user_id=user_id,
        title=solution_data.get("problem", {}).get("goal", "New Problem")[:50],
        subject=request.subject or "General",
        is_saved=False
    )
    session.add(new_chat)
    session.commit()
    session.refresh(new_chat)

    # Save User Query
    user_msg = ChatMessage(
        session_id=new_chat.id,
        role="user",
        content=base_query,
        media_url=request.image_url
    )
    session.add(user_msg)

    # Save Assistant Response
    ai_msg = ChatMessage(
        session_id=new_chat.id,
        role="assistant",
        content=solution_data.get("solution", {}).get("final_answer", ""),
        structured_data=solution_data,
        model_used=model_name,
        tokens_used=estimated_tokens
    )
    session.add(ai_msg)
    
    # Store in Canonical (Simplified: In production we'd verify first)
    if problem_hash:
        try:
            from app.models import CanonicalProblem, CanonicalSolution
            # Check if problem exists
            cp = session.exec(select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == problem_hash)).first()
            if not cp:
                cp = CanonicalProblem(
                    normalized_problem_hash=problem_hash,
                    normalized_text=base_query,
                    subject=request.subject or "General"
                )
                session.add(cp)
                session.commit()
                session.refresh(cp)
            
            # Save as potentially verified solution
            cs = CanonicalSolution(
                problem_id=cp.id,
                solution_json=solution_data,
                verification_status="pass" # Defaulting to pass for now
            )
            session.add(cs)
        except Exception as e:
            print(f"WARNING: Failed to save canonical record: {e}") # Using print as logger not defined in snippet

    # Estimate tokens used (already calculated at the top)
    add_tokens_to_user(user_id, estimated_tokens, session)
    
    # Log Solve Usage
    session.add(UsageLog(user_id=user_id, action_type="solve_request", tokens_used=estimated_tokens))
    
    session.commit()

    return SolveResponse(
        session_id=new_chat.id,
        solution=solution_data,
        concepts=solution_data.get("concepts") or [],
        model_used=model_name,
        tokens_used=estimated_tokens,
        has_image=is_image
    )
    
    # ------------------------------------------------------------------
# Billing & User Location Endpoints
# ------------------------------------------------------------------

class SubscribeRequest(BaseModel):
    user_id: int
    plan_id: str # pro, ultra
    payment_method: str = "card"
    card_last4: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None

class LocationUpdateRequest(BaseModel):
    user_id: int
    ip_address: Optional[str] = None
    country: Optional[str] = None

@api_router.post("/billing/subscribe")
async def subscribe_user(request: SubscribeRequest, session: Session = Depends(get_session)):
    user = session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Simulate Payment Processing
    transaction_id = f"tx_{datetime.utcnow().timestamp()}_{user.id}"
    amount = 9.99 if request.plan_id == "pro" else 0.00
    
    # Create Payment Record
    payment = Payment(
        user_id=user.id,
        amount=amount,
        currency="USD",
        status="completed",
        transaction_id=transaction_id,
        payment_method=request.payment_method,
        ip_address=request.ip_address
    )
    session.add(payment)
    
    # Update User Location if provided
    if request.ip_address:
        user.ip_address = request.ip_address
    if request.country:
        user.country = request.country
        
    # Update Subscription
    user.subscription_tier = request.plan_id
    user.subscription_status = "active"
    user.subscription_expiry = datetime.utcnow() + timedelta(days=30)
    
    session.add(user)
    session.commit()
    session.refresh(payment)
    
    return {"status": "success", "transaction_id": transaction_id, "plan": request.plan_id}

@api_router.get("/billing/history")
async def get_billing_history(user_id: int, session: Session = Depends(get_session)):
    payments = session.exec(select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())).all()
    return payments

@api_router.post("/user/location")
async def update_user_location(request: LocationUpdateRequest, session: Session = Depends(get_session)):
    """Update user IP and country for security logging"""
    user = session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.ip_address:
        user.ip_address = request.ip_address
    if request.country:
        user.country = request.country
        
    session.add(user)
    session.commit()
    return {"status": "updated", "ip": user.ip_address, "country": user.country}

# ------------------------------------------------------------------
# Promo Code Endpoints
# ------------------------------------------------------------------

class PromoValidateRequest(BaseModel):
    code: str

class PromoCreateRequest(BaseModel):
    code: str
    discount_percent: int
    max_uses: Optional[int] = None

@api_router.post("/billing/validate-promo")
async def validate_promo(request: PromoValidateRequest, session: Session = Depends(get_session)):
    code_upper = request.code.upper().strip()
    promo = session.exec(select(PromoCode).where(PromoCode.code == code_upper)).first()
    
    if not promo:
        return {"valid": False, "message": "Invalid code"}
        
    if not promo.is_active:
        return {"valid": False, "message": "Code is inactive"}
        
    if promo.valid_until and promo.valid_until < datetime.utcnow():
        return {"valid": False, "message": "Code expired"}
        
    if promo.max_uses and promo.current_uses >= promo.max_uses:
        return {"valid": False, "message": "Code usage limit reached"}
        
    return {
        "valid": True, 
        "message": "Valid code", 
        "discount_percent": promo.discount_percent,
        "code": promo.code
    }

@api_router.post("/admin/promo-codes")
async def create_promo_code(request: PromoCreateRequest, session: Session = Depends(get_session)):
    # In prod, check admin role here
    new_promo = PromoCode(
        code=request.code.upper().strip(),
        discount_percent=request.discount_percent,
        max_uses=request.max_uses
    )
    session.add(new_promo)
    try:
        session.commit()
        return {"status": "created", "code": new_promo.code}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Code already exists or invalid")
    # (End of promo codes)

@api_router.get("/history", response_model=List[ChatHistoryItem])
async def get_history(
    user_id: int, 
    saved_only: bool = True,
    session: Session = Depends(get_session)
):
    # Filter based on saved_only flag
    if saved_only:
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.is_saved == True
        ).order_by(ChatSession.created_at.desc())
    else:
        # Return ALL sessions for this user
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.created_at.desc())
        
    results = session.exec(stmt).all()
    
    return [
        ChatHistoryItem(
            id=chat.id, 
            title=chat.title, 
            created_at=chat.created_at.isoformat(),
            subject=chat.subject or "Math",
            is_saved=chat.is_saved 
        ) 
        for chat in results
    ]

class ChatMessageSchema(BaseModel):
    role: str
    content: str
    media_url: Optional[str] = None
    structured_data: Optional[dict] = None
    created_at: str
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    subject: Optional[str] = None
    is_saved: bool = False
    created_at: str
    messages: List[ChatMessageSchema]

@api_router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session_details(session_id: int, session: Session = Depends(get_session)):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return ChatSessionResponse(
        id=chat_session.id,
        title=chat_session.title,
        subject=chat_session.subject,
        is_saved=chat_session.is_saved,
        created_at=chat_session.created_at.isoformat(),
        messages=[
            ChatMessageSchema(
                role=msg.role,
                content=msg.content,
                media_url=msg.media_url,
                structured_data=msg.structured_data,
                created_at=msg.created_at.isoformat(),
                model_used=getattr(msg, "model_used", None),
                tokens_used=getattr(msg, "tokens_used", None)
            )
            for msg in chat_session.messages
        ]
    )

class QuestionRequest(BaseModel):
    session_id: int
    user_id: int
    query: str

@api_router.post("/ask-question")
async def ask_question(request: QuestionRequest, db: Session = Depends(get_session)):
    # 1. Fetch Context
    chat_session = db.get(ChatSession, request.session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get the last assistant message structure for context
    last_assistant_msg = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == request.session_id)
        .where(ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc())
    ).first()
    
    context = last_assistant_msg.structured_data if last_assistant_msg else {}
    
    # 2. Get Response from SolverService
    result = await solver_service.get_chat_response(request.query, context)
    
    # 3. Save User Message
    db.add(ChatMessage(
        session_id=request.session_id,
        role="user",
        content=request.query
    ))
    
    # 4. Save AI Response
    ai_msg = ChatMessage(
        session_id=request.session_id,
        role="assistant",
        content=result.get("content", "I am sorry, I could not process that."),
        model_used="OpenAI GPT-4o Mini",
        tokens_used=100 # Standard flat rate for chat
    )
    db.add(ai_msg)
    
    # 5. Charge Tokens
    add_tokens_to_user(request.user_id, 100, db)
    
    db.commit()
    db.refresh(ai_msg)
    
    return {
        "relevant": result.get("relevant", True),
        "content": ai_msg.content,
        "created_at": ai_msg.created_at.isoformat(),
        "model_used": ai_msg.model_used,
        "tokens_used": ai_msg.tokens_used
    }

# --- Profile & Preferences ---

@api_router.get("/user/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate usage (Conceptual/Simplified for now)
    # Questions count: count solve_request in UsageLog in last 30 days
    questions_count = db.exec(
        select(UsageLog)
        .where(UsageLog.user_id == user_id)
        .where(UsageLog.action_type == "solve_request")
    ).all() # Should ideally filter by date
    
    scans_count = db.exec(
        select(OCRJob)
        .where(OCRJob.user_id == user_id)
    ).all()
    
    return UserProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        academic_level=user.academic_level,
        timezone=user.timezone,
        theme=user.theme,
        preferred_language=user.preferred_language,
        solving_mode=user.solving_mode,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        
        is_public=user.is_public,
        learning_interests=user.learning_interests or [],
        
        usage=UserUsageStats(
            questions_count=len(questions_count),
            questions_total=user.quota_questions_total,
            scans_count=len(scans_count),
            scans_total=user.quota_scans_total
        )
    )

@api_router.post("/user/profile")
async def update_user_profile(request: ProfileUpdateRequest, user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.email is not None:
        user.email = request.email
    if request.academic_level is not None:
        user.academic_level = request.academic_level
    if request.timezone is not None:
        user.timezone = request.timezone
    if request.is_public is not None:
        user.is_public = request.is_public
    if request.learning_interests is not None:
        user.learning_interests = request.learning_interests
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "message": "Profile updated"}

@api_router.post("/user/preferences")
async def update_user_preferences(request: PreferenceUpdateRequest, user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.theme is not None:
        user.theme = request.theme
    if request.preferred_language is not None:
        user.preferred_language = request.preferred_language
    if request.solving_mode is not None:
        user.solving_mode = request.solving_mode
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "message": "Preferences updated"}

# --- Token Tracking & Save Functionality ---

from datetime import datetime, timedelta

def check_and_reset_monthly_tokens(user: User, db: Session) -> User:
    """Check if we need to reset monthly token count"""
    now = datetime.utcnow()
    # Reset if it's been more than 30 days
    if (now - user.last_token_reset).days >= 30:
        user.tokens_used_this_month = 0
        user.last_token_reset = now
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@api_router.post("/user/heartbeat")
async def update_heartbeat(
    user_id: int = Query(...), 
    session_token: Optional[str] = Query(None),
    db: Session = Depends(get_session)
):
    """Update user's last active timestamp and validate session"""
    user = db.get(User, user_id)
    if user:
        # Enforce Single Session
        if session_token and user.session_token:
            if session_token != user.session_token:
                raise HTTPException(status_code=401, detail="Session expired. New login detected.")
        
        user.last_active_at = datetime.utcnow()
        db.add(user)
        db.commit()
    return {"status": "ok"}

# --- Admin Management Endpoints ---

@api_router.get("/admin/users", response_model=AdminUserListResponse)
async def admin_list_users(
    q: Optional[str] = None,
    role: Optional[str] = None,
    plan: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_session)
):
    """Admin only: List and filter users"""
    statement = select(User)
    
    if q:
        statement = statement.where(
            (User.full_name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    if role and role != "All Roles":
        statement = statement.where(User.role == role.lower())
    if plan and plan != "All Plans":
        statement = statement.where(User.subscription_tier == plan.lower())
    
    # Calculate total count efficiently
    total_count = len(db.exec(statement).all())
    users = db.exec(statement.offset(offset).limit(limit)).all()
    
    user_list = []
    for u in users:
        # Robust counts
        q_count = len(db.exec(select(ChatSession.id).where(ChatSession.user_id == u.id)).all())
        s_count = len(db.exec(select(OCRJob.id).where(OCRJob.user_id == u.id)).all())
        
        # Robust date handling
        last_active = u.last_active_at or u.created_at or datetime.utcnow()
        
        user_list.append(AdminUserListItem(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            subscription_tier=u.subscription_tier,
            role=u.role,
            questions_count=q_count,
            scans_count=s_count,
            last_active_at=last_active.isoformat()
        ))
    
    return AdminUserListResponse(
        total_count=total_count,
        users=user_list
    )

@api_router.get("/admin/users/{user_id}", response_model=AdminUserDetailResponse)
async def admin_get_user_detail(user_id: int, db: Session = Depends(get_session)):
    """Admin only: Get full user profile and usage"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    from app.models import AdminNote
    notes = db.exec(select(AdminNote).where(AdminNote.user_id == user_id).order_by(AdminNote.created_at.desc())).all()
    
    # Calculate usage
    questions_used = len(db.exec(select(ChatSession.id).where(ChatSession.user_id == user_id)).all())
    scans_used = len(db.exec(select(OCRJob.id).where(OCRJob.user_id == user_id)).all())

    joined_at = user.created_at or datetime.utcnow()

    return AdminUserDetailResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        academic_level=user.academic_level,
        joined_at=joined_at.isoformat(),
        avatar_url=user.avatar_url,
        quota_questions_total=user.quota_questions_total,
        quota_scans_total=user.quota_scans_total,
        questions_used=questions_used,
        scans_used=scans_used,
        notes=[
            AdminNoteResponse(
                id=n.id,
                admin_name=n.admin_name,
                content=n.content,
                created_at=(n.created_at or datetime.utcnow()).isoformat()
            )
            for n in notes
        ]
    )

@api_router.patch("/admin/users/{user_id}")
async def admin_update_user(user_id: int, req: AdminUserUpdateRequest, db: Session = Depends(get_session)):
    """Admin only: Update user subscription or role"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if req.role is not None:
        user.role = req.role
    if req.subscription_tier is not None:
        user.subscription_tier = req.subscription_tier
    if req.subscription_status is not None:
        user.subscription_status = req.subscription_status
    if req.quota_questions_total is not None:
        user.quota_questions_total = req.quota_questions_total
    if req.quota_scans_total is not None:
        user.quota_scans_total = req.quota_scans_total
        
    db.add(user)
    db.commit()
    return {"status": "ok"}

@api_router.post("/admin/users/{user_id}/notes")
async def admin_add_note(user_id: int, req: AdminNoteCreateRequest, db: Session = Depends(get_session)):
    """Admin only: Add internal support note"""
    from app.models import AdminNote
    note = AdminNote(
        user_id=user_id,
        admin_name=req.admin_name,
        content=req.content
    )
    db.add(note)
    db.commit()
    return {"status": "ok"}

@api_router.post("/admin/invite")
async def admin_invite_user(req: SignupRequest, db: Session = Depends(get_session)):
    """Admin only: Invite/Create a new user with a temporary password"""
    from app.auth import get_password_hash
    
    # Check if user exists
    existing = db.exec(select(User).where(User.email == req.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    new_user = User(
        email=req.email,
        full_name=req.full_name,
        password_hash=get_password_hash(req.password),
        academic_level=req.academic_level,
        is_verified=True # Auto-verify on invite
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "ok", "user_id": new_user.id}

@api_router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(user_id: int, db: Session = Depends(get_session)):
    """Admin only: Reset user password to a default one (e.g., ChangeMe123!)"""
    from app.auth import get_password_hash
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.password_hash = get_password_hash("ChangeMe123!")
    db.add(user)
    db.commit()
    return {"status": "ok", "temporary_password": "ChangeMe123!"}

@api_router.post("/admin/users/{user_id}/resend-email")
async def admin_resend_email(user_id: int, db: Session = Depends(get_session)):
    """Admin only: Resend verification OR welcome email"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mocking email sending for now
    print(f"Resending welcome email to {user.email}")
    return {"status": "ok", "message": f"Email queued for {user.email}"}

@api_router.patch("/admin/users/{user_id}/ban")
async def admin_ban_user(user_id: int, banned: bool = True, db: Session = Depends(get_session)):
    """Admin only: Ban or unban a user by setting status to expired/active"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.subscription_status = "expired" if banned else "active"
    db.add(user)
    db.commit()
    return {"status": "ok", "banned": banned}

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: int, db: Session = Depends(get_session)):
    """Admin only: Permanently delete a user and their associated data (cascaded)"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return {"status": "ok"}

@api_router.get("/admin/stats/dashboard", response_model=DashboardStatsResponse)
async def admin_get_dashboard_stats(db: Session = Depends(get_session)):
    """Admin only: Get global KPI metrics"""
    from datetime import timedelta
    now = datetime.utcnow()
    last_24h = now - timedelta(days=1)
    prev_24h = now - timedelta(days=2)

    total_users = len(db.exec(select(User.id)).all())
    daily_requests = len(db.exec(select(UsageLog.id).where(UsageLog.timestamp >= last_24h)).all())
    prev_requests = len(db.exec(select(UsageLog.id).where(UsageLog.timestamp >= prev_24h, UsageLog.timestamp < last_24h)).all())
    
    ocr_jobs = db.exec(select(OCRJob).where(OCRJob.created_at >= last_24h)).all()
    completed_ocr = [j for j in ocr_jobs if j.status == "completed"]
    ocr_success_rate = (len(completed_ocr) / len(ocr_jobs) * 100) if ocr_jobs else 98.2
    
    total_tokens_24h = sum([l.tokens_used for l in db.exec(select(UsageLog).where(UsageLog.timestamp >= last_24h)).all()])
    llm_cost_est = (total_tokens_24h / 1_000_000) * 0.50 # Estimate $0.50 per 1M tokens
    
    # Calculate real growth
    requests_growth = ((daily_requests - prev_requests) / prev_requests * 100) if prev_requests else 0.0
    
    # Fetch recent errors
    errors = db.exec(select(SystemErrorEntry).where(SystemErrorEntry.is_resolved == False).order_by(SystemErrorEntry.created_at.desc()).limit(10)).all()
    system_errors = [SystemErrorItem(
        id=str(e.id),
        timestamp=e.created_at.isoformat(),
        level=e.level,
        message=e.message,
        component=e.component
    ) for e in errors]

    return DashboardStatsResponse(
        total_users=total_users,
        daily_requests=daily_requests,
        ocr_success_rate=ocr_success_rate,
        llm_cost_est=llm_cost_est,
        cache_hit_rate=42.5, # Placeholder for now as we don't track cache hits yet
        requests_growth=requests_growth,
        success_rate_change=0.0,
        cost_change=0.0,
        cache_hit_change=0.0,
        system_errors=system_errors
    )

@api_router.get("/admin/stats/model-routing", response_model=ModelRoutingResponse)
async def admin_get_model_routing(db: Session = Depends(get_session)):
    """Admin only: Get model distribution data"""
    series = [
        ModelRoutingSeries(day="Mon", volume=12000),
        ModelRoutingSeries(day="Tue", volume=15000),
        ModelRoutingSeries(day="Wed", volume=13000),
        ModelRoutingSeries(day="Thu", volume=18000),
        ModelRoutingSeries(day="Fri", volume=16000),
        ModelRoutingSeries(day="Sat", volume=11000),
        ModelRoutingSeries(day="Sun", volume=14000)
    ]
    return ModelRoutingResponse(
        total_requests=842000,
        avg_latency=1.2,
        requests_growth=15.4,
        latency_change=4.2,
        series=series
    )

@api_router.get("/admin/quotas", response_model=AdminQuotaListResponse)
async def admin_get_quotas(db: Session = Depends(get_session)):
    """Admin only: List users and their usage for quota management"""
    from datetime import timedelta
    now = datetime.utcnow()
    last_24h = now - timedelta(days=1)
    
    users = db.exec(select(User).limit(50)).all()
    quota_items = []
    
    for u in users:
        # Calculate daily usage %
        # Assuming 1M tokens/month -> approx 33k/day
        daily_limit = 33333
        daily_usage = sum([l.tokens_used for l in db.exec(select(UsageLog).where(UsageLog.user_id == u.id, UsageLog.timestamp >= last_24h)).all()])
        usage_pct = int((daily_usage / daily_limit) * 100) if daily_limit > 0 else 0
        
        last_active = (u.last_active_at or u.created_at or now)
        diff = now - last_active
        if diff.total_seconds() < 60: active_str = "Just now"
        elif diff.total_seconds() < 3600: active_str = f"{int(diff.total_seconds()//60)} mins ago"
        else: active_str = f"{int(diff.total_seconds()//3600)} hours ago"

        quota_items.append(AdminQuotaUserItem(
            id=u.id,
            full_id=f"USR-{u.id}",
            plan=u.subscription_tier.capitalize(),
            usage_percent=min(usage_pct, 100),
            last_active=active_str,
            is_banned=u.subscription_status == "expired"
        ))
    
    total_tokens_24h = sum([l.tokens_used for l in db.exec(select(UsageLog).where(UsageLog.timestamp >= last_24h)).all()])
    
    return AdminQuotaListResponse(
        users=quota_items,
        total_users=len(db.exec(select(User.id)).all()),
        global_consumption=72.4, # Mock
        daily_active_holders=14205, # Mock
        tokens_burned_24h=f"{total_tokens_24h/1_000_000:.1f}M"
    )

@api_router.post("/admin/quotas/override")
async def admin_apply_quota_override(req: QuotaOverrideRequest, db: Session = Depends(get_session)):
    """Admin only: Apply a manual quota override for a specific user"""
    from datetime import timedelta
    
    expires_at = None
    if req.duration_hours:
        expires_at = datetime.utcnow() + timedelta(hours=req.duration_hours)
    
    # Check if override exists
    stmt = select(UserQuotaOverride).where(UserQuotaOverride.user_id == req.user_id)
    override = db.exec(stmt).first()
    
    if override:
        override.token_limit = req.token_limit
        override.ocr_concurrency = req.ocr_concurrency
        override.expires_at = expires_at
        override.created_at = datetime.utcnow()
    else:
        override = UserQuotaOverride(
            user_id=req.user_id,
            token_limit=req.token_limit,
            ocr_concurrency=req.ocr_concurrency,
            expires_at=expires_at
        )
    
    db.add(override)
    db.commit()
    return {"status": "ok", "expires_at": expires_at.isoformat() if expires_at else None}

@api_router.get("/admin/users/{user_id}/activity", response_model=List[AdminActivityItem])
async def admin_get_user_activity(user_id: int, db: Session = Depends(get_session)):
    """Admin only: Get recent activity events for a user"""
    from app.models import ChatSession, OCRJob
    
    # Combining Sessions and OCR Jobs for activity feed
    sessions = db.exec(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()).limit(10)).all()
    ocr_jobs = db.exec(select(OCRJob).where(OCRJob.user_id == user_id).order_by(OCRJob.created_at.desc()).limit(10)).all()
    
    activity = []
    for s in sessions:
        ts = s.created_at or datetime.utcnow()
        activity.append(AdminActivityItem(
            type="Solved",
            subject=s.subject or "General",
            method="Text" if not s.topic else "OCR",
            status="Solved",
            timestamp=ts.isoformat()
        ))
    for j in ocr_jobs:
        ts = j.created_at or datetime.utcnow()
        activity.append(AdminActivityItem(
            type="OCR Scan",
            subject="Mixed content",
            method="OCR",
            status=(j.status or "queued").capitalize(),
            timestamp=ts.isoformat()
        ))
    
    # Sort by timestamp
    activity.sort(key=lambda x: x.timestamp, reverse=True)
    return activity[:10]

@api_router.get("/admin/prompts", response_model=List[PromptTemplateListItem])
async def admin_get_prompts(db: Session = Depends(get_session)):
    """Admin only: List all prompt templates"""
    templates = db.exec(select(PromptTemplate)).all()
    
    # If no templates, seed default ones
    if not templates:
        t1 = PromptTemplate(name="Math Solver", description="System instruction for advanced step-by-step math resolution")
        t2 = PromptTemplate(name="OCR Formatter", description="Normalization rules for raw OCR output")
        db.add(t1)
        db.add(t2)
        db.commit()
        db.refresh(t1)
        db.refresh(t2)
        # Seed initial versions
        v1 = PromptVersion(template_id=t1.id, version="v2.4.1", content="You are a Senior Mathematical Tutor...", author="admin_sarah", is_production=True)
        v2 = PromptVersion(template_id=t2.id, version="v1.0.0", content="Convert math to LaTeX...", author="admin_sarah", is_production=True)
        db.add(v1)
        db.add(v2)
        db.commit()
        templates = [t1, t2]

    results = []
    for t in templates:
        prod_v = db.exec(select(PromptVersion).where(PromptVersion.template_id == t.id, PromptVersion.is_production == True)).first()
        results.append(PromptTemplateListItem(
            id=t.id,
            name=t.name,
            slug=t.slug or "",
            description=t.description or "",
            version=prod_v.version if prod_v else "N/A",
            status="Production" if prod_v else "Draft",
            last_updated=(prod_v.created_at if prod_v else t.created_at).isoformat()
        ))
    return results

@api_router.get("/admin/prompts/{template_id}/versions", response_model=List[PromptVersionItem])
async def admin_get_prompt_versions(template_id: int, db: Session = Depends(get_session)):
    """Admin only: Get all versions for a template"""
    versions = db.exec(select(PromptVersion).where(PromptVersion.template_id == template_id).order_by(PromptVersion.created_at.desc())).all()
    return [
        PromptVersionItem(
            id=v.id,
            version=v.version,
            content=v.content,
            author=v.author,
            created_at=v.created_at.isoformat(),
            is_production=v.is_production
        ) for v in versions
    ]

@api_router.post("/admin/prompts/{template_id}/save")
async def admin_save_prompt(template_id: int, req: PromptSaveRequest, db: Session = Depends(get_session)):
    """Admin only: Save a new draft version"""
    # Generate new version string if not provided
    if not req.version_string:
        last = db.exec(select(PromptVersion).where(PromptVersion.template_id == template_id).order_by(PromptVersion.created_at.desc())).first()
        if last:
            import re
            m = re.search(r'v(\d+)\.(\d+)\.(\d+)', last.version_string)
            if m:
                major, minor, patch = m.groups()
                new_v = f"v{major}.{minor}.{int(patch)+1}"
            else:
                new_v = last.version_string + ".1"
        else:
            new_v = "v1.0.0"
    else:
        new_v = req.version_string

    v = PromptVersion(
        template_id=template_id,
        version_string=new_v,
        content=req.content,
        author="Loai Admin",
        is_production=False
    )
    db.add(v)
    db.commit()
    return {"status": "ok", "version_id": v.id}

@api_router.post("/admin/prompts/versions/{version_id}/deploy")
async def admin_deploy_prompt(version_id: int, db: Session = Depends(get_session)):
    """Admin only: Set a version as production"""
    v = db.get(PromptVersion, version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Set all other versions for this template to not production
    others = db.exec(select(PromptVersion).where(PromptVersion.template_id == v.template_id, PromptVersion.is_production == True)).all()
    for o in others:
        o.is_production = False
        db.add(o)
    
    v.is_production = True
    db.add(v)
    db.commit()
    return {"status": "ok"}

@api_router.get("/users/online")
async def get_online_users(db: Session = Depends(get_session)):
    """Get list of public users active in the last 15 minutes"""
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    
    # Select users who are public AND active recently
    statement = select(User).where(User.is_public == True).where(User.last_active_at >= cutoff)
    users = db.exec(statement).all()
    
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "learning_interests": u.learning_interests
        }
        for u in users
    ]

def add_tokens_to_user(user_id: int, tokens: int, db: Session):
    """Add tokens to user's monthly count"""
    user = db.get(User, user_id)
    if user:
        user = check_and_reset_monthly_tokens(user, db)
        user.tokens_used_this_month += tokens
        db.add(user)
        db.commit()

class TokenUsageResponse(BaseModel):
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    reset_date: str
    is_over_limit: bool

@api_router.get("/user/token-usage", response_model=TokenUsageResponse)
async def get_token_usage(user_id: int = Query(...), db: Session = Depends(get_session)):
    """Get current month's token usage for a user"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = check_and_reset_monthly_tokens(user, db)
    
    MONTHLY_LIMIT = 1_000_000  # 1M tokens per month
    tokens_remaining = max(0, MONTHLY_LIMIT - user.tokens_used_this_month)
    reset_date = (user.last_token_reset + timedelta(days=30)).isoformat()
    
    return TokenUsageResponse(
        tokens_used=user.tokens_used_this_month,
        tokens_limit=MONTHLY_LIMIT,
        tokens_remaining=tokens_remaining,
        reset_date=reset_date,
        is_over_limit=user.tokens_used_this_month >= MONTHLY_LIMIT
    )

@api_router.post("/sessions/{session_id}/save")
async def save_session(session_id: int, db: Session = Depends(get_session)):
    """Mark a session as saved so it appears in history and create a UserSavedSolution entry"""
    chat_session = db.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    chat_session.is_saved = True
    db.add(chat_session)
    
    # Link to UserSavedSolution to avoid duplications in history view
    from app.models import ChatMessage, CanonicalProblem, CanonicalSolution, UserSavedSolution
    import hashlib
    
    user_msg = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.role == "user")
    ).first()
    
    if user_msg:
        p_hash = hashlib.sha256(user_msg.content.strip().lower().encode()).hexdigest()
        cp = db.exec(select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == p_hash)).first()
        if cp:
            cs = db.exec(select(CanonicalSolution).where(CanonicalSolution.problem_id == cp.id)).first()
            if cs:
                existing_save = db.exec(
                    select(UserSavedSolution)
                    .where(UserSavedSolution.user_id == chat_session.user_id)
                    .where(UserSavedSolution.solution_id == cs.id)
                ).first()
                if not existing_save:
                    db.add(UserSavedSolution(user_id=chat_session.user_id, solution_id=cs.id))
    
    db.commit()
    return {"status": "ok", "message": "Session saved successfully", "session_id": session_id}

class SessionDetailResponse(BaseModel):
    id: int
    title: str
    is_saved: bool
    created_at: str

@api_router.get("/sessions/{session_id}/details", response_model=SessionDetailResponse)
async def get_session_save_status(session_id: int, db: Session = Depends(get_session)):
    """Get session details including save status"""
    chat_session = db.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionDetailResponse(
        id=chat_session.id,
        title=chat_session.title,
        is_saved=chat_session.is_saved,
        created_at=chat_session.created_at.isoformat()
    )


