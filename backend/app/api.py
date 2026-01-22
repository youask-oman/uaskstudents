from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, SQLModel, select
from sqlalchemy import text as sql_text
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
import re
import requests
import hashlib
import json
import os
import time
import logging
from datetime import datetime, timedelta

from app.database import get_session
from app.services.solve.normalizer_service import problem_normalizer_service
from app.models import (
    User, ChatSession, ChatMessage, UsageLog, OCRJob,
    Upload, Crop, OCRArtifact, OCRConfirmation,
    CanonicalProblem, CanonicalSolution, UserSavedSolution, Payment, PromoCode,
    OCRQuestion, OCRChoice, OCRFigure, OCRAuditEvent,
    VoiceSession, VoiceAudio, VoiceJob, VoiceArtifact, VoiceConfirmation,
    AdminNote, SystemConfig, PromptTemplate, PromptVersion, UserQuotaOverride, SystemErrorEntry,
    School, Plan, Subscription, UsageLedger,
    PromptAsset, PlanPromptLink, RequestEvent, DeviceSignupLog
)
from app.services.subscription_service import subscription_service
from app.services.vision import VisionService, vision_service
from app.services.solver import solver_service
from app.services.intent import should_require_visual
from app.services.plot_sampling import process_visuals
from app.services.rag import rag_service
from app.services.ocr.upload_service import upload_service
from app.services.ocr.crop_service import crop_service
from app.services.ocr.ocr_router_service import ocr_router_service
from app.services.ocr.audit_log_service import audit_log_service
from app.services.ocr.ocr_service import ocr_service
from app.services.solve.canonicalization_service import canonicalization_service
from app.services.solve.cache_service import cache_service
from app.config import get_settings



from app.auth import verify_password, create_access_token, Token, get_password_hash
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
api_router = APIRouter()


# --- Helper Functions ---
def _transform_v3_to_v1_format(v3_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform Solver V3 response format to V1 format for frontend compatibility.
    
    V3 Format:
    - verification: {method, work_latex, conclusion, alternative_method}
    - No concepts array (derived from rules/steps)
    
    V1 Format:
    - verification.methods[]: {name, math: {latex_lines: []}, result, steps}
    - concepts[]: {name, description, applies_here}
    """
    try:
        # print(f"[TRANSFORM] Starting V3 to V1 transformation") # Debug logging
        transformed = v3_data.copy()
        
        # Transform V3 verification -> V1 verification.methods
        methods_v1 = []
        if "verification" in transformed and isinstance(transformed["verification"], dict):
            verif_v3 = transformed["verification"]
            
            # Primary Method
            if "method" in verif_v3:
                methods_v1.append({
                    "name": verif_v3.get("method", "Verification"),
                    "math": {
                        "latex_lines": [line.strip() for line in verif_v3.get("work_latex", "").split("\n") if line.strip()]
                    },
                    "result": verif_v3.get("conclusion", "Verified"),
                    "steps": []
                })
            
            # Alternative Method
            if "alternative_method" in verif_v3 and verif_v3["alternative_method"]:
                alt = verif_v3["alternative_method"]
                methods_v1.append({
                    "name": alt.get("name", "Alternative"),
                    "math": {
                        "latex_lines": [] # V3 alt method is just summary usually?
                    },
                    "result": alt.get("summary", ""),
                    "steps": []
                })
                
                
        # If no methods extracted but verification exists (maybe V2 style fallback?), try methods_used
        if not methods_v1 and "verification" in transformed and "methods_used" in transformed["verification"]:
             # Fallback for V2 inputs
             for method in transformed["verification"]["methods_used"]:
                steps_text = method.get("steps", [])
                latex_lines = steps_text if isinstance(steps_text, list) else [steps_text]
                methods_v1.append({
                    "name": method.get("name", ""),
                    "math": {"latex_lines": latex_lines},
                    "result": method.get("result", ""),
                    "steps": steps_text
                })

        transformed["verification"] = {"methods": methods_v1}
        
        # Transform V3 visuals (object) -> V1 visuals (list of plots)
        if "visuals" in transformed and isinstance(transformed["visuals"], dict):
            visuals_v3 = transformed["visuals"]
            # Extract plots list
            plots = visuals_v3.get("plots") or []
            # Check for alternative visual if no plots?
            # V1 expects list of plot specs.
            transformed["visuals"] = plots
            
            # V3 doesn't typically separate 'visuals_suggested', it has 'alternative_visual' in the object.
            # We can map 'alternative_visual' to 'visuals_suggested' list if needed?
            # For now, just extracting plots is crucial.

        
        # Ensure concepts array exists
        if "concepts" not in transformed or not transformed["concepts"]:
            transformed["concepts"] = [
                {
                    "name": "Problem Solving",
                    "description": "Systematic approach",
                    "applies_here": "Applied logical steps to find the solution."
                }
            ]
            
        # Ensure solution object exists (V1 expects top level solution dict sometimes, or flattened?)
        # V1: solution_data.get("solution", solution_data) in return.
        
        # GENERATE _content (Markdown) for ChatMessage if missing
        if "_content" not in transformed:
            md_lines = []
            
            # Problem Goal
            if "problem" in transformed and "original_text" in transformed["problem"]:
                 md_lines.append(f"**Problem:** {transformed['problem']['original_text']}\n")
            
            # Steps
            if "steps" in transformed and isinstance(transformed["steps"], list):
                md_lines.append("**Solution Steps:**\n")
                for step in transformed["steps"]:
                    title = step.get("title", f"Step {step.get('index', '')}")
                    explanation = step.get("explanation", "")
                    latex = step.get("math_latex", "")
                    
                    md_lines.append(f"**{title}**")
                    md_lines.append(explanation)
                    if latex:
                        md_lines.append(f"$$ {latex} $$")
                    md_lines.append("") # Spacer
            
            # Final Answer
            if "final_answer" in transformed:
                fa = transformed["final_answer"]
                ans_text = fa.get("answer_text", "")
                ans_latex = fa.get("answer_latex", "")
                
                md_lines.append("**Final Answer:**")
                md_lines.append(ans_text)
                if ans_latex:
                    md_lines.append(f"$$ {ans_latex} $$")
            
            transformed["_content"] = "\n".join(md_lines)
            
        print(f"[TRANSFORM] Success! Transformed keys: {list(transformed.keys())}")
        return transformed
        
    except Exception as e:
        print(f"[TRANSFORM_ERROR] Failed to transform V2 to V1: {e}")
        import traceback
        traceback.print_exc()
        # Return original if transformation fails
        return v2_data



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
    
    # Entitlement flags
    is_make_it_right: Optional[bool] = False
    previous_request_id: Optional[str] = None
    has_voice: Optional[bool] = False
    
    # Tier-Aware & Trusted Context
    trusted_context: Optional[Dict[str, Any]] = None
    requested_mode: Optional[str] = "minimal"
    features_used: Optional[Dict[str, Any]] = None

from app.models import Plan, Subscription, UsageLedger
from app.services.subscription_service import subscription_service

class SolveResponse(BaseModel):
    session_id: int
    solution: Dict[str, Any]
    concepts: Optional[List[Any]] = []
    visuals: Optional[List[Any]] = []
    verification: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = "OpenAI GPT-4o Mini"
    tokens_used: Optional[int] = 500
    has_image: Optional[bool] = False
    telemetry: Optional[Dict[str, Any]] = None # Added telemetry


def validate_math_query(text: str) -> None:
    normalized = (text or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Please enter a math question.")

    bad_words = [
        "fuck",
        "fucking",
        "shit",
        "shitty",
        "bitch",
        "asshole",
        "bastard",
        "dick",
        "cock",
        "pussy",
        "cunt",
        "nigger",
        "faggot",
        "slut",
        "whore",
        "motherfucker",
        "sex",
        "sexual",
        "porn",
        "porno",
        "pornography",
        "rape",
        "rapist",
        "cum",
        "ejaculate",
        "orgasm",
        "blowjob",
        "handjob",
        "anal",
        "penis",
        "vagina",
        "boobs",
        "tits",
        "nude",
        "nudes",
        "naked"
    ]
    if any(re.search(rf"\\b{re.escape(word)}\\b", normalized) for word in bad_words):
        raise HTTPException(status_code=400, detail="Inappropriate language detected. Please rephrase.")

    forbidden_patterns = [
        r"<script",
        r"</",
        r"\bimport\s+\w+",
        r"\bfrom\s+[\w\.]+\s+import\b",
        r"require\(",
        r"eval\(",
        r"exec\(",
        r"subprocess",
        r"system\(",
        r"\bcat\s",
        r"\bls\s",
        r"\bdir\s",
        r"\bchmod\s",
        r"\bchown\s",
        r"curl\s",
        r"wget\s",
        r"powershell",
        r"cmd\.exe",
        r"rm\s",
        r"del\s",
        r"drop\s+table",
        r"insert\s+into",
        r"update\s+\w+",
        r"delete\s+from",
        r"\bselect\s+.*\bfrom\b",
        r"union\s+select",
        r"http://",
        r"https://",
        r"\$\{",
        r"\{\{",
    ]
    if any(re.search(pattern, normalized) for pattern in forbidden_patterns):
        raise HTTPException(status_code=400, detail="Input blocked. Please enter a valid math question.")

    math_hints = [
        r"\d",
        r"[=<>+\-*/^]",
        r"\\(frac|sqrt|int|sum|lim|log|sin|cos|tan|theta|pi|alpha|beta|gamma|cdot|times)",
        r"\b(solve|simplify|factor|expand|evaluate|derivative|integral|integrate|limit|graph|plot|domain|range|root|roots|intercept|slope|equation|function|probability|matrix|vector|geometry|algebra|calculus)\b",
    ]
    if not any(re.search(pattern, normalized) for pattern in math_hints):
        raise HTTPException(status_code=400, detail="Input must be a math question.")


def _verification_passed(result: Dict[str, Any]) -> bool:
    verification = result.get("verification")
    if not isinstance(verification, dict):
        return False
    conclusion = (verification.get("conclusion") or "").lower()
    if "verified" in conclusion or "valid" in conclusion:
        return True
    return False


def _sqlmodel_to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "dict"):
        data = obj.dict()
    else:
        data = dict(getattr(obj, "__dict__", {}))
    data.pop("_sa_instance_state", None)
    return data


def _sqlmodel_list(items: List[Any]) -> List[Dict[str, Any]]:
    return [_sqlmodel_to_dict(item) for item in items]

class ChatHistoryItem(BaseModel):
    id: int
    title: str
    created_at: str
    subject: Optional[str] = None
    topic: Optional[str] = None
    input: Optional[str] = None
    is_saved: Optional[bool] = None
    telemetry: Optional[Dict[str, Any]] = None



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
    # Location Profile (for curriculum context)
    profile_country: Optional[str] = None  # 'USA' or 'Canada'
    profile_province_state: Optional[str] = None  # State or Province abbreviation
    grade_level: Optional[str] = None  # 'Grade 1' to 'Grade 12'
    school_id: Optional[int] = None  # Optional FK to School

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

# --- Subscription Endpoint Schemas (for tier-aware solve UX) ---
class SubscriptionPlanInfo(BaseModel):
    id: int
    slug: str
    display_name: str
    credits_monthly: int
    seats: int
    multipliers: Dict[str, float]
    features: Dict[str, Any]

class SubscriptionUsage(BaseModel):
    credits_used: float
    credits_remaining: float
    ocr_used: int
    ocr_limit: int
    voice_used: int
    voice_limit: int

class SubscriptionProfile(BaseModel):
    grade_level: Optional[str] = None
    region_country: Optional[str] = None
    region_state_province: Optional[str] = None
    display_name: str

class SubscriptionResponse(BaseModel):
    plan: SubscriptionPlanInfo
    usage: SubscriptionUsage
    profile: SubscriptionProfile
    allow_detailed: bool
    allow_ocr: bool
    allow_voice: bool

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

class SolveTraceEntry(BaseModel):
    request_id: Optional[str] = None
    user_id: Optional[int] = None
    seat_id: Optional[int] = None
    plan_key: Optional[str] = None
    ui_goal: Optional[str] = None
    ui_style: Optional[str] = None
    resolved_profile_key: Optional[str] = None
    resolved_system_file_path: Optional[str] = None
    resolved_schema_file_path: Optional[str] = None
    schema_name: Optional[str] = None
    max_output_tokens_sent: Optional[int] = None
    model_sent: Optional[str] = None
    cache_hit: Optional[bool] = None
    openai_calls_count: Optional[int] = None
    repair_attempted: Optional[bool] = None
    prompt_tokens_estimate: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    deduct_attempted: Optional[Dict[str, bool]] = None
    deduct_committed: Optional[bool] = None
    openai_payload: Optional[Dict[str, Any]] = None
    problem_text: Optional[str] = None
    error: Optional[str] = None
    logged_at: Optional[str] = None

class DashboardStatsResponse(BaseModel):
    total_users: int
    daily_requests: int
    ocr_success_rate: float
    llm_cost_est: float
    llm_cost_est_daily: float
    llm_cost_est_monthly: float
    llm_total_requests_daily: int
    llm_total_requests_monthly: int
    llm_total_spend_daily: float
    llm_total_spend_monthly: float
    llm_tokens_in_daily: int
    llm_tokens_out_daily: int
    llm_tokens_in_monthly: int
    llm_tokens_out_monthly: int
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
    full_name: str
    email: str
    plan: str
    usage_percent: int
    last_active: str
    is_banned: bool
    credits_balance: Optional[float] = None
    credits_used_this_period: Optional[float] = None
    daily_credits_used: Optional[float] = None
    daily_credit_cap: Optional[float] = None
    daily_tokens_used: Optional[int] = None
    override_token_limit: Optional[int] = None
    override_ocr_concurrency: Optional[int] = None
    override_expires_at: Optional[str] = None

class AdminQuotaListResponse(BaseModel):
    users: List[AdminQuotaUserItem]
    total_users: int
    global_consumption: float
    daily_active_holders: int


class AdminQuestionHistoryItem(BaseModel):
    request_id: Optional[str] = None
    created_at: str
    session_id: Optional[int] = None
    session_title: Optional[str] = None
    prompt: Optional[str] = None
    response: Optional[str] = None
    model: Optional[str] = None
    route: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    tokens_total: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    status: Optional[str] = None
    error_type: Optional[str] = None
    schema_valid: Optional[bool] = None
    verification_pass: Optional[bool] = None
    is_stream: Optional[bool] = None
    is_cached: Optional[bool] = None
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

    # Location Profile
    profile_country: Optional[str] = None
    profile_province_state: Optional[str] = None
    grade_level: Optional[str] = None
    school_id: Optional[int] = None

    usage: UserUsageStats

@api_router.post("/signup")
async def signup(form_data: SignupRequest, session: Session = Depends(get_session)):
    # P2: Password Complexity Check
    if len(form_data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    
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
    
    # Anti-Abuse
    if hasattr(form_data, "device_fingerprint") and form_data.device_fingerprint:
        # Check last signup from this device
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_signups = session.exec(select(DeviceSignupLog).where(
            DeviceSignupLog.device_hash == form_data.device_fingerprint,
            DeviceSignupLog.created_at > cutoff
        )).all()
        
        # Limit to 3 signups per device per 30 days
        if len(recent_signups) >= 3:
             raise HTTPException(status_code=400, detail="Device limit exceeded. Too many accounts created from this device.")
             
        # Log this signup
        session.add(DeviceSignupLog(device_hash=form_data.device_fingerprint))
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


# --- User Subscription Endpoint (for tier-aware solve UX) ---
@api_router.get("/me/subscription", response_model=SubscriptionResponse)
async def get_my_subscription(
    user_id: int = Query(..., description="User ID"), 
    session: Session = Depends(get_session)
):
    """
    Returns subscription details, usage, and profile for the current user.
    Used by the Solve page for tier-aware UX (cost preview, feature gating).
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get subscription and plan
    subscription = session.exec(
        select(Subscription).where(Subscription.user_id == user_id)
    ).first()
    
    if not subscription:
        # Return default Free plan info
        free_plan = session.exec(select(Plan).where(Plan.slug == "free")).first()
        plan_info = SubscriptionPlanInfo(
            id=free_plan.id if free_plan else 0,
            slug="free",
            display_name="Free",
            credits_monthly=50,
            seats=1,
            multipliers={"text_concise": 1, "text_detailed": 1000, "ocr_add": 1, "voice_add": 1},
            features={"allow_detailed": False, "allow_ocr": True, "allow_voice": True}
        )
        usage_info = SubscriptionUsage(
            credits_used=0,
            credits_remaining=50,
            ocr_used=0,
            ocr_limit=3,
            voice_used=0,
            voice_limit=3
        )
    else:
        plan = session.get(Plan, subscription.plan_id)
        features = plan.features or {}
        multipliers = plan.multipliers or {"text_concise": 1, "text_detailed": 2, "ocr_add": 1, "voice_add": 1}
        
        plan_info = SubscriptionPlanInfo(
            id=plan.id,
            slug=plan.slug,
            display_name=plan.name,
            credits_monthly=plan.credits_per_month,
            seats=plan.seats or 1,
            multipliers=multipliers,
            features=features
        )
        
        feature_usage = subscription.feature_usage or {}
        usage_info = SubscriptionUsage(
            credits_used=subscription.credits_used_this_period,
            credits_remaining=subscription.credits_balance,
            ocr_used=feature_usage.get("ocr_used", 0),
            ocr_limit=features.get("ocr_monthly_cap", 100),
            voice_used=feature_usage.get("voice_used", 0),
            voice_limit=features.get("voice_monthly_cap", 50)
        )
    
    # Profile info
    profile_info = SubscriptionProfile(
        grade_level=user.grade_level,
        region_country=user.profile_country,
        region_state_province=user.profile_province_state,
        display_name=user.full_name
    )
    
    # Feature allowance flags
    allow_detailed = plan_info.slug != "free"
    allow_ocr = usage_info.ocr_used < usage_info.ocr_limit
    allow_voice = usage_info.voice_used < usage_info.voice_limit
    
    return SubscriptionResponse(
        plan=plan_info,
        usage=usage_info,
        profile=profile_info,
        allow_detailed=allow_detailed,
        allow_ocr=allow_ocr,
        allow_voice=allow_voice
    )



class LatexResponse(BaseModel):
    latex: str

# ------------------------------------------------------------------
# OCR Subsystem Endpoints
# ------------------------------------------------------------------

@api_router.post("/uploads")
@limiter.limit("5/minute")
async def upload_file(
    request: Request,
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
    
    # Nested choices (Optimized: single query for all choices)
    q_ids = [q.id for q in questions]
    all_choices = session.exec(select(OCRChoice).where(OCRChoice.question_id.in_(q_ids))).all() if q_ids else []
    
    # Group choices by question_id
    from collections import defaultdict
    choices_by_q = defaultdict(list)
    for c in all_choices:
        choices_by_q[c.question_id].append(c.dict())

    questions_data = []
    for q in questions:
        q_dict = q.dict()
        q_dict["choices"] = choices_by_q[q.id]
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

    validate_math_query(request.confirmed_text)
    validate_math_query(request.confirmed_markdown)

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
    validate_math_query(request.confirmed_transcript_text)
    validate_math_query(confirmed_math)
    
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
@limiter.limit("10/minute")
async def solve_problem(
    request: Request,
    body: SolveRequest, 
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
        user_id = body.user_id or 1
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
        try:
            with open("/app/storage/solve_debug.log", "w") as f:
                f.write(f"Error: {str(e)}\n")
                traceback.print_exc(file=f)
        except:
            print("Failed to write to debug log")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    base_query = f"{body.text_query or ''}".strip()
    
    # --- STRUCTURED DATA ENHANCEMENT ---
    context_info = ""
    # Frontend can send confirmed_text (old) or confirmed_markdown (new)
    if body.confirmed_markdown:
        base_query = body.confirmed_markdown
    elif body.confirmed_text:
        base_query = body.confirmed_text

    validate_math_query(base_query)
    
    if body.artifact_id and body.question_id:
        # Fetch detailed entities to provide "Hallucination Protection"
        from app.models import OCRQuestion, OCRFigure, OCRChoice
        question_ent = session.get(OCRQuestion, body.question_id)
        if question_ent:
            # Reconstruct the problem from entities
            choices_ent = session.exec(select(OCRChoice).where(OCRChoice.question_id == question_ent.id)).all()
            choice_str = "\n".join([f"{c.label}: {c.text}" for c in choices_ent])
            base_query = f"{question_ent.prompt}\n\nChoices:\n{choice_str}"
            
            # Fetch linked figures
            figures_ent = session.exec(select(OCRFigure).where(OCRFigure.artifact_id == body.artifact_id)).all()
            if figures_ent:
                context_info += "\n[VISUAL CONTEXT DETECTED]\n"
                for fig in figures_ent:
                    fig_desc = f"Figure {fig.external_id} ({fig.type}): {fig.description}\n"
                    if fig.data_json:
                        fig_desc += f"Detailed Data: {json.dumps(fig.data_json)}\n"
                    context_info += fig_desc
    elif body.confirmed_latex_blocks:
        # Fallback to provided blocks from review screen
        choice_str = "\n".join([f"{b.get('key')}: {b.get('value')}" for b in body.confirmed_latex_blocks if b.get('type') == 'choice'])
        if choice_str:
            base_query += f"\n\nChoices:\n{choice_str}"
    
    # --- VISUAL INTENT DETECTION ---
    visual_required, visual_reason = should_require_visual(base_query)
    if visual_required:
        context_info += f"\n[SYSTEM REQUIREMENT]: A visual graph/plot is REQUIRED for this problem. {visual_reason}"

    final_prompt = base_query
    if context_info:
        final_prompt = f"{base_query}\n\n{context_info}"
    
    # 2. Deduplication (Canonical Solution Lookup)
    problem_hash = body.problem_hash
    if not problem_hash and base_query:
        problem_hash = hashlib.sha256(base_query.strip().lower().encode()).hexdigest()
    
    cached_solution = None
    if problem_hash:
        cached_solution = get_canonical_solution(problem_hash, session)

    # Determine metadata (will be overridden by actual model from OpenAI response)
    model_name_fallback = "YouAsk AI (Multimodal)" if (body.image_url or body.artifact_id) else "gpt-5-mini"
    is_image = bool(body.image_url or body.artifact_id)
    extra_images = 0
    if body.artifact_id:
        from app.models import OCRFigure
        extra_images = len(session.exec(select(OCRFigure).where(OCRFigure.artifact_id == body.artifact_id)).all())
    
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
        model_name = cached_solution.get("_model", model_name_fallback)
        
        new_chat = ChatSession(
            user_id=user_id,
            title=cached_solution.get("problem", {}).get("goal", "Resolved Problem")[:50],
            subject=body.subject or "General",
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

        # --- PROCESS VISUALS (CACHE) ---
        if "visuals" in cached_solution:
            cached_solution["visuals"] = process_visuals(cached_solution["visuals"])

        return SolveResponse(
            session_id=new_chat.id,
            solution=cached_solution,
            concepts=cached_solution.get("concepts") or [],
            model_used=cached_solution.get("_model", model_name_fallback),
            tokens_used=100,
            has_image=is_image
        )

    # 3. Retrieval
    # Prepend Mode Context
    if body.mode and body.mode != "general":
        base_query_for_retrieval = f"[MODE: {body.mode.upper()}] {base_query}"
    else:
        base_query_for_retrieval = base_query
    
    if not base_query.strip():
        raise HTTPException(status_code=400, detail="No input provided")

    concepts = await rag_service.search_related_concepts(base_query_for_retrieval)

    # 4. Solve (Using Solver V3 exclusively)
    from app.services.solver_v3 import get_solver_v3
    from app.services.admin.analytics_service import record_request_event, _calc_cost
    
    # Build Context
    context = f"Subject: {body.subject or 'General'}"
    if body.difficulty:
        context += f", Difficulty: {body.difficulty}"
    if body.mode:
        context += f", Mode: {body.mode}"
    
    # Student Location & Curriculum Context
    user = session.get(User, user_id)
    if user:
         country = user.profile_country or 'Canada'
         province = user.profile_province_state or 'ON'
         # context += f"\nCountry: {country}, Province: {province}"
         # Use implied curriculum hints if needed, but for now location is key
         if user.grade_level:
             context += f", Grade: {user.grade_level}"

    if concepts:
         context += f"\nRelated Concepts: {', '.join([c.get('title') for c in concepts])}"

    solver = get_solver_v3()
    try:
        print(f"[API] Using Solver V3 for: {final_prompt[:50]}...")
        solution_data = await solver.solve(
            problem_text=final_prompt,
            context=context,
            trace=body.mode == "debug",
            user_tier=user.subscription_tier if user else "free",
            user_id=user_id,
            db_session=session,
            requested_mode=body.requested_mode or ("detailed" if body.mode == "detailed" else "minimal"),
            trusted_context=body.trusted_context
        )
        print(f"[API] Solver V3 returned successfully")
        
        # Transform V3 format (SolveResponseV3) to V1 format (SolveResponse)
        print(f"[API] Transforming V3 response to V1 format...")
        solution_data = _transform_v3_to_v1_format(solution_data)
        print(f"[API] Transformation complete")
        
    except Exception as e:
        print(f"[API_ERROR] Solver V3 failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Solver V3 failed: {str(e)}")
    
    # DEBUG LOGGING
    print(f"DEBUG: LLM Response Visuals: {json.dumps(solution_data.get('visuals', []), indent=2)}")
    
    # Extract actual model name from OpenAI response
    model_name = solution_data.get("_model", model_name_fallback)
    
    # --- PROCESS VISUALS ---
    # V2 has both visuals and visuals_suggested
    if "visuals" in solution_data:
        solution_data["visuals"] = process_visuals(solution_data["visuals"])
    
    if "visuals_suggested" in solution_data:
        solution_data["visuals_suggested"] = process_visuals(solution_data["visuals_suggested"])

    # 5. Persistence
    # Create Session (NOT SAVED by default)
    new_chat = ChatSession(
        user_id=user_id,
        title=solution_data.get("problem", {}).get("goal", "New Problem")[:50],
        subject=body.subject or "General",
        is_saved=False,
        learning_mode=(body.trusted_context or {}).get("learning_mode", "solve"),
        requested_mode=body.requested_mode or "minimal",
        solve_tier=user.subscription_tier if user else "free"
    )
    session.add(new_chat)
    session.commit()
    session.refresh(new_chat)

    # Save User Query
    user_msg = ChatMessage(
        session_id=new_chat.id,
        role="user",
        content=base_query,
        media_url=body.image_url
    )
    session.add(user_msg)

    # Save Assistant Response
    # V2 provides _content (markdown), V1 uses final_answer
    assistant_content = solution_data.get("_content") or solution_data.get("solution", {}).get("final_answer", "")
    
    # Calculate final tokens (prefer telemetry)
    telemetry_data = solution_data.get("_telemetry") or solution_data.get("telemetry") or {}
    telemetry_data["learning_mode"] = new_chat.learning_mode
    telemetry_data["requested_mode"] = new_chat.requested_mode
    telemetry_data["solve_tier"] = new_chat.solve_tier
# --- Admin Prompt Asset & Link Management ---

class PromptAssetResponse(BaseModel):
    id: int
    key: str
    kind: str
    checksum: Optional[str]

class PlanLinkUpdateRequest(BaseModel):
    # Nested dict structure { mode: { system_id, schema_id } }
    # Or flattened list?
    # Request body: { "minimal": {"system_asset_id": 1, ...}, "detailed": ... }
    minimal: Optional[Dict[str, int]] = None
    detailed: Optional[Dict[str, int]] = None

@api_router.get("/admin/prompt-assets", response_model=List[PromptAssetResponse])
async def list_prompt_assets(
    kind: Optional[str] = None,
    session: Session = Depends(get_session)
):
    query = select(PromptAsset)
    if kind:
        query = query.where(PromptAsset.kind == kind)
    assets = session.exec(query).all()
    return assets

@api_router.put("/admin/plans/{plan_id}/prompt-links")
async def update_plan_links(
    plan_id: int,
    body: PlanLinkUpdateRequest,
    session: Session = Depends(get_session)
):
    plan = session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    from app.models import PlanPromptLink

    # Helper to update or create link
    def _update_link(mode: str, data: Dict[str, int]):
        if not data: return
        
        link = session.exec(select(PlanPromptLink).where(PlanPromptLink.plan_id == plan_id, PlanPromptLink.mode == mode)).first()
        if not link:
            link = PlanPromptLink(plan_id=plan_id, mode=mode)
            session.add(link)
        
        if "system_asset_id" in data:
            link.system_prompt_asset_id = data["system_asset_id"]
        if "schema_asset_id" in data:
            link.schema_prompt_asset_id = data["schema_asset_id"]
        session.add(link)

    if body.minimal:
        _update_link("minimal", body.minimal)
    
    if body.detailed:
        _update_link("detailed", body.detailed)
        
    session.commit()
    return {"status": "ok", "message": "Links updated"}

@api_router.get("/admin/plans/{plan_id}/prompt-links")
async def get_plan_links(
    plan_id: int,
    session: Session = Depends(get_session)
):
    from app.models import PlanPromptLink
    links = session.exec(select(PlanPromptLink).where(PlanPromptLink.plan_id == plan_id)).all()
    
    # Reshape for frontend
    response = {"minimal": {}, "detailed": {}}
    for link in links:
        if link.mode in response:
            response[link.mode] = {
                "system_asset_id": link.system_prompt_asset_id,
                "schema_asset_id": link.schema_prompt_asset_id
            }
    return response

    final_tokens_count = real_tokens if real_tokens > 0 else estimated_tokens

    ai_msg = ChatMessage(
        session_id=new_chat.id,
        role="assistant",
        content=assistant_content,
        structured_data=solution_data,
        model_used=model_name,
        tokens_used=final_tokens_count,
        telemetry=telemetry_data
    )
    session.add(ai_msg)
    
    # Store in Canonical (Simplified: In production we'd verify first)
    if problem_hash:
        try:
            # Check if problem exists
            cp = session.exec(select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == problem_hash)).first()
            if not cp:
                cp = CanonicalProblem(
                    normalized_problem_hash=problem_hash,
                    normalized_text=base_query,
                    subject=body.subject or "General"
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

    # Update User Tokens
    if user:
        add_tokens_to_user(user_id, final_tokens_count, session)
        
        # Log Solve Usage
        session.add(UsageLog(user_id=user_id, action_type="solve_request", tokens_used=final_tokens_count))
        
        # Deduct Credits (1 per solve for now)
        if user.subscription:
            # We assume active subscription if they are here (or free tier)
            # Free tier usually has no credits_balance logic unless we give them free credits?
            # Or maybe we just track usage.
            # Plan says: "For the Free tier, deduct 1 credit per solve".
            # If they have a subscription object (even free), we deduct.
            user.subscription.credits_balance -= 1 
            user.subscription.credits_used_this_period += 1
            session.add(user.subscription)
    
    session.commit()

    return SolveResponse(
        session_id=new_chat.id,
        solution=solution_data.get("solution", solution_data),
        concepts=solution_data.get("concepts") or [],
        visuals=solution_data.get("visuals") or [],
        verification=solution_data.get("verification"),
        model_used=model_name,
        tokens_used=estimated_tokens,
        has_image=is_image,
        telemetry=solution_data.get("telemetry") or solution_data.get("_telemetry")
    )
    
    # ------------------------------------------------------------------
# Solver V3 Endpoint - Production-Grade with Schema Validation
# ------------------------------------------------------------------

@api_router.post("/solve_v3")
# @limiter.limit("10/minute")
async def solve_v3_endpoint(
    request: Request,
    body: SolveRequest,
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    """
    Math Solver V3 - Production-grade endpoint.
    
    Features:
    - Strict JSON Schema Draft 2020-12 validation
    - Automatic repair loop (max 1 retry)
    - Always-visualize policy (plots generated when applicable)
    - 2+ verification methods
    - Tutor-grade explanations with concepts, rules, and checkpoints
    
    Returns:
        SolveResponseV3 with complete solution, plots, and verification
    """
    from app.services.solver_v3 import get_solver_v3
    from app.services.solve.trace_logger import log_solve_trace
    import base64
    
    # Generate unique Request ID
    request_id = str(uuid.uuid4())
    requested_mode = body.requested_mode or "minimal"
    learning_mode = (body.trusted_context or {}).get("learning_mode", "solve")
    features_used = body.features_used or {}
    deduct_attempted = {"credits": False, "ocr": False, "voice": False}
    deduct_committed = False
    resolved_profile = None

    
    # Extract problem text
    problem_text = (
        body.confirmed_text or
        body.confirmed_markdown or
        body.text_query or
        "No problem provided"
    ).strip()
    
    if not problem_text:
        raise HTTPException(status_code=400, detail="No input provided")

    validate_math_query(problem_text)
    
    # --- CACHE LOGIC ---
    settings = get_settings()
    canonical_key = None
    intent = "unknown"
    math_obj = ""
    assumptions = {}
    result = None
    was_cached = False
    
    if settings.CANONICAL_CACHE_ENABLED:
        try:
            intent = canonicalization_service.get_intent(problem_text)
            math_obj, assumptions = canonicalization_service.normalize_math_object(problem_text, intent)
            canonical_key = canonicalization_service.compute_canonical_key(intent, math_obj, assumptions)
            
            result = cache_service.get_cached_solution(session, canonical_key)
            if result:
                print(f"[CACHE] Hit: {canonical_key}")
                was_cached = True
        except Exception as e:
            print(f"[CACHE] Error: {e}")
    
    # Context assembly
    context = f"Subject: {body.subject or 'General'}"
    if body.difficulty:
        context += f", Difficulty: {body.difficulty}"
    if body.mode:
        context += f", Mode: {body.mode}"
    
    # --- STUDENT LOCATION CONTEXT INJECTION ---
    # Fetch user to get profile location for curriculum adaptation
    user = session.get(User, user_id)
    from app.llm_profiles.profile_resolver import ProfileResolver
    resolved_profile = ProfileResolver.resolve_profile(
        session,
        user,
        requested_mode=requested_mode,
        learning_mode=learning_mode
    )
    if user:
        student_context_parts = []
        
        # Country
        country = user.profile_country or 'Canada'  # Default to Canada
        student_context_parts.append(f"Country: {country}")
        
        # Province/State (default to Ontario if not set)
        province = user.profile_province_state or 'ON'
        student_context_parts.append(f"Province/State: {province}")
        
        # Grade Level
        if user.grade_level:
            student_context_parts.append(f"Grade Level: {user.grade_level}")
        
        # Comprehensive curriculum hint mapping
        curriculum_map = {
            # Canada - All Provinces and Territories
            ('Canada', 'ON'): 'Ontario curriculum (Ontario Ministry of Education)',
            ('Canada', 'BC'): 'BC curriculum (British Columbia Ministry of Education)',
            ('Canada', 'AB'): 'Alberta curriculum (Alberta Education)',
            ('Canada', 'QC'): 'Quebec Education Program (Ministère de l\'Éducation du Québec)',
            ('Canada', 'SK'): 'Saskatchewan curriculum (Saskatchewan Ministry of Education)',
            ('Canada', 'MB'): 'Manitoba curriculum (Manitoba Education)',
            ('Canada', 'NB'): 'New Brunswick curriculum',
            ('Canada', 'NS'): 'Nova Scotia curriculum (Nova Scotia EECD)',
            ('Canada', 'PE'): 'Prince Edward Island curriculum',
            ('Canada', 'NL'): 'Newfoundland and Labrador curriculum',
            ('Canada', 'YT'): 'Yukon curriculum (based on BC curriculum)',
            ('Canada', 'NT'): 'Northwest Territories curriculum (based on Alberta curriculum)',
            ('Canada', 'NU'): 'Nunavut curriculum (based on Alberta curriculum)',
            
            # USA - All States with specific standards
            ('USA', 'AL'): 'Alabama Course of Study',
            ('USA', 'AK'): 'Alaska Content Standards',
            ('USA', 'AZ'): 'Arizona Academic Standards',
            ('USA', 'AR'): 'Arkansas Academic Standards',
            ('USA', 'CA'): 'California Common Core State Standards',
            ('USA', 'CO'): 'Colorado Academic Standards',
            ('USA', 'CT'): 'Connecticut Core Standards',
            ('USA', 'DE'): 'Delaware Content Standards',
            ('USA', 'FL'): 'Florida B.E.S.T. Standards',
            ('USA', 'GA'): 'Georgia Standards of Excellence',
            ('USA', 'HI'): 'Hawaii Common Core Standards',
            ('USA', 'ID'): 'Idaho Content Standards',
            ('USA', 'IL'): 'Illinois Learning Standards',
            ('USA', 'IN'): 'Indiana Academic Standards',
            ('USA', 'IA'): 'Iowa Core Standards',
            ('USA', 'KS'): 'Kansas College and Career Ready Standards',
            ('USA', 'KY'): 'Kentucky Academic Standards',
            ('USA', 'LA'): 'Louisiana Student Standards',
            ('USA', 'ME'): 'Maine Learning Results',
            ('USA', 'MD'): 'Maryland College and Career-Ready Standards',
            ('USA', 'MA'): 'Massachusetts Curriculum Frameworks',
            ('USA', 'MI'): 'Michigan Academic Standards',
            ('USA', 'MN'): 'Minnesota Academic Standards',
            ('USA', 'MS'): 'Mississippi College and Career Readiness Standards',
            ('USA', 'MO'): 'Missouri Learning Standards',
            ('USA', 'MT'): 'Montana Content Standards',
            ('USA', 'NE'): 'Nebraska College and Career Ready Standards',
            ('USA', 'NV'): 'Nevada Academic Content Standards',
            ('USA', 'NH'): 'New Hampshire College and Career Ready Standards',
            ('USA', 'NJ'): 'New Jersey Student Learning Standards',
            ('USA', 'NM'): 'New Mexico Common Core State Standards',
            ('USA', 'NY'): 'New York State Next Generation Learning Standards',
            ('USA', 'NC'): 'North Carolina Standard Course of Study',
            ('USA', 'ND'): 'North Dakota Content Standards',
            ('USA', 'OH'): 'Ohio Learning Standards',
            ('USA', 'OK'): 'Oklahoma Academic Standards',
            ('USA', 'OR'): 'Oregon Academic Content Standards',
            ('USA', 'PA'): 'Pennsylvania Academic Standards',
            ('USA', 'RI'): 'Rhode Island Common Core State Standards',
            ('USA', 'SC'): 'South Carolina College and Career Ready Standards',
            ('USA', 'SD'): 'South Dakota Content Standards',
            ('USA', 'TN'): 'Tennessee Academic Standards',
            ('USA', 'TX'): 'Texas Essential Knowledge and Skills (TEKS)',
            ('USA', 'UT'): 'Utah Core Standards',
            ('USA', 'VT'): 'Vermont Common Core State Standards',
            ('USA', 'VA'): 'Virginia Standards of Learning',
            ('USA', 'WA'): 'Washington State Learning Standards',
            ('USA', 'WV'): 'West Virginia College and Career Readiness Standards',
            ('USA', 'WI'): 'Wisconsin Academic Standards',
            ('USA', 'WY'): 'Wyoming Content and Performance Standards',
            ('USA', 'DC'): 'District of Columbia Common Core State Standards',
        }
        
        curriculum_hint = curriculum_map.get((country, province), f"{country} curriculum standards")
        student_context_parts.append(f"Curriculum: {curriculum_hint}")

        
        # Build student context block
        context += f"\n\n[STUDENT CONTEXT - Trusted metadata, adapt to local conventions]\n"
        context += "\n".join(student_context_parts)
        context += "\n\nNOTE: Use appropriate units (metric for Canada, customary for USA), spelling conventions, and grade-appropriate terminology."
    
    # Enable trace mode for debugging
    trace = body.mode == "debug"

    # --- QUESTION IDENTITY CACHE (OCR-proof) ---
    # This is checked BEFORE the canonical cache as it's more robust for OCR text
    from app.services.solve.question_identity_service import question_identity_service
    
    question_fingerprint = None
    question_key = None
    question_cache_hit = False
    
    try:
        question_fingerprint = question_identity_service.compute_question_fingerprint(problem_text)
        question_key = question_identity_service.compute_question_key(question_fingerprint)
        
        # Check question identity cache first
        cached_result = question_identity_service.get_cached_question(session, question_key)
        if cached_result:
            result = cached_result
            was_cached = True
            question_cache_hit = True
            print(f"[QUESTION_CACHE] HIT - skipping OpenAI call")
    except Exception as e:
        print(f"[QUESTION_CACHE] Fingerprint error: {e}")
    
    try:
        # Call Solver V3 (Logic: Only if not cached)
        if not result:
            # --- ENTITLEMENT CHECK & DEBIT ---
            action_mode = "detailed" if requested_mode == "detailed" else "concise"
            action_req = {
                "mode": action_mode,
                "has_ocr": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
                "has_voice": bool(body.has_voice or features_used.get("voice_used")),
                "question_hash": question_key or str(hash(problem_text)),
                "is_make_it_right": getattr(body, "is_make_it_right", False)
            }
            deduct_attempted = {
                "credits": True,
                "ocr": action_req["has_ocr"],
                "voice": action_req["has_voice"]
            }
            
            check_result = subscription_service.check_entitlement_and_debit(session, user_id, action_req)
            if not check_result["allowed"]:
                log_solve_trace({
                    "request_id": request_id,
                    "user_id": user_id,
                    "seat_id": None,
                    "plan_key": resolved_profile.tier if resolved_profile else None,
                    "ui_goal": learning_mode,
                    "ui_style": requested_mode,
                    "resolved_profile_key": f"{resolved_profile.tier.upper().replace('-', '_')}_{resolved_profile.mode.upper()}" if resolved_profile else None,
                    "resolved_system_file_path": (resolved_profile.system_asset_path if resolved_profile else None) or (resolved_profile.system_relative_path if resolved_profile else None),
                    "resolved_schema_file_path": (resolved_profile.schema_asset_path if resolved_profile else None) or (resolved_profile.schema_relative_path if resolved_profile else None),
                    "schema_name": None,
                    "max_output_tokens_sent": resolved_profile.max_output_tokens if resolved_profile else None,
                    "model_sent": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                    "cache_hit": bool(was_cached or question_cache_hit),
                    "openai_calls_count": 0,
                    "repair_attempted": False,
                    "prompt_tokens_estimate": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "cached_tokens": None,
                    "deduct_attempted": deduct_attempted,
                    "deduct_committed": False,
                    "openai_payload": None,
                    "problem_text": problem_text,
                    "error": f"entitlement_denied: {check_result.get('reason')}"
                })
                record_request_event(session, {
                    "request_id": request_id,
                    "user_id": user_id,
                    "mode": requested_mode,
                    "learning_mode": learning_mode,
                    "subject": body.subject,
                    "grade_level": user.grade_level if user else None,
                    "model": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                    "provider": "openai",
                    "route": "solve_v3",
                    "tokens_in": None,
                    "tokens_out": None,
                    "tokens_total": None,
                    "cost_usd": 0.0,
                    "latency_ms": None,
                    "status": "error",
                    "error_type": "entitlement_denied",
                    "schema_valid": None,
                    "verification_pass": None,
                    "is_stream": False,
                    "is_cached": bool(was_cached or question_cache_hit),
                    "credit_deducted": False,
                    "credit_amount": None,
                    "ocr_used": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
                    "voice_used": bool(body.has_voice or features_used.get("voice_used")),
                    "response_truncated": False
                })
                raise HTTPException(status_code=402, detail=f"Entitlement Check Failed: {check_result['reason']}")
                 
            # Execute Debit
            sub_id = check_result["subscription"].id
            debit_cost = check_result["cost"]
            subscription_service.execute_debit(
                session, 
                check_result["subscription"], 
                debit_cost, 
                {"action": "solve_v3", **action_req}, 
                request_id
            )
            session.commit()
            deduct_committed = True
            
            try:
                solver = get_solver_v3()
                result = await solver.solve(
                    problem_text=problem_text,
                    context=context,
                    trace=trace,
                    request_id=request_id,
                    user_id=user_id,
                    db_session=session,
                    requested_mode=requested_mode,
                    trusted_context=body.trusted_context,
                    learning_mode=learning_mode
                )
            except Exception as e:
                # REFUND ON EXCEPTION
                subscription_service.refund_credits(session, sub_id, debit_cost, f"System Error: {str(e)}", request_id)
                raise e
        
        # Check if it's an error response - fallback to V2 if V3 fails
        # Check if it's an error response
        if result.get("error", False):
            # REFUND ON SOLVER ERROR (Policy: refund on technical failures)
            if not was_cached and 'debit_cost' in locals():
                 subscription_service.refund_credits(session, sub_id, debit_cost, f"Solver Error: {result.get('error_type')}", request_id)

            print(f"[API_V3] Solver V3 returned error: {result.get('error_type')}")
            
            # Record error in a chat session for visibility
            new_chat = ChatSession(
                user_id=user_id,
                title="Error: " + problem_text[:40],
                subject=body.subject or "General",
                is_saved=False
            )
            session.add(new_chat)
            session.commit()
            session.refresh(new_chat)
            
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user.grade_level if user else None,
                "model": (result.get("telemetry") or {}).get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "provider": "openai",
                "route": "solve_v3",
                "tokens_in": (result.get("telemetry") or {}).get("input_tokens"),
                "tokens_out": (result.get("telemetry") or {}).get("output_tokens"),
                "tokens_total": (result.get("telemetry") or {}).get("total_tokens"),
                "cost_usd": _calc_cost(
                    (result.get("telemetry") or {}).get("total_tokens"),
                    (result.get("telemetry") or {}).get("model"),
                    (result.get("telemetry") or {}).get("input_tokens"),
                    (result.get("telemetry") or {}).get("output_tokens")
                ),
                "latency_ms": (result.get("telemetry") or {}).get("latency_ms_total"),
                "status": "error",
                "error_type": result.get("error_type") or "solver_error",
                "schema_valid": (result.get("telemetry") or {}).get("validated"),
                "verification_pass": False,
                "is_stream": False,
                "is_cached": bool(was_cached or question_cache_hit),
                "credit_deducted": deduct_committed,
                "credit_amount": debit_cost if deduct_committed and 'debit_cost' in locals() else None,
                "ocr_used": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
                "voice_used": bool(body.has_voice or features_used.get("voice_used")),
                "response_truncated": bool(result.get("_truncated"))
            })
            return {
                "session_id": new_chat.id,
                "error": True,
                "error_type": result.get("error_type"),
                "message": result.get("message"),
                "validation_errors": result.get("validation_errors", [])
            }
        
        # Success - process plot if available
        plot_url = None
        if "_plot_image" in result:
            # Save plot image to storage
            try:
                plot_image_b64 = result["_plot_image"]
                plot_bytes = base64.b64decode(plot_image_b64)
                
                # Save to backend/storage/plots/
                import os
                from pathlib import Path
                plots_dir = Path(__file__).parent.parent / "storage" / "plots"
                plots_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate unique filename
                from datetime import datetime
                filename = f"plot_{user_id}_{datetime.utcnow().timestamp()}.png"
                filepath = plots_dir / filename
                
                with open(filepath, "wb") as f:
                    f.write(plot_bytes)
                
                plot_url = f"/storage/plots/{filename}"
                print(f"[API_V3] Saved plot: {plot_url}")
            
            except Exception as e:
                print(f"[API_V3] Failed to save plot: {e}")
                # Continue without plot - non-critical

        # --- CACHE STORE --- (Only if fresh solve and successful)
        if not was_cached and canonical_key and settings.CACHE_WRITE_ENABLED and not result.get("error"):
            try:
                # Store processed result (with plot_url if any? No, we store raw usually, but here result has plot info)
                # Ideally we store the result as is
                cache_service.store_solution(
                    session, canonical_key, problem_text, intent, math_obj, [], assumptions, result
                )
                print(f"[CACHE] Stored: {canonical_key}")
            except Exception as e:
                print(f"[CACHE] Store failed: {e}")
        
        # --- QUESTION IDENTITY CACHE STORE --- (OCR-proof cache)
        if not question_cache_hit and question_key and question_fingerprint and not result.get("error"):
            try:
                question_identity_service.store_question_result(
                    session, question_key, question_fingerprint, result, problem_text
                )
            except Exception as e:
                print(f"[QUESTION_CACHE] Store failed: {e}")
        
        # Create chat session
        new_chat = ChatSession(
            user_id=user_id,
            title=result.get("problem", {}).get("goal", problem_text[:50]),
            subject=result.get("problem", {}).get("input", body.subject or "General")[:50],
            is_saved=False
        )
        session.add(new_chat)
        session.commit()
        session.refresh(new_chat)
        
        # Save messages
        session.add(ChatMessage(
            session_id=new_chat.id,
            role="user",
            content=problem_text,
            media_url=body.image_url
        ))
        
        # Generate summary for chat display
        # Generate summary for chat display
        # V3.1 Schema: final_answer is a top-level object
        final_ans_obj = result.get("final_answer", {})
        if isinstance(final_ans_obj, dict):
             final_answer = final_ans_obj.get("answer_text", "See full solution")
        else:
             final_answer = str(final_ans_obj)
        
        # Token tracking (Part D4)
        tokens_actual = result.get("total_tokens") or result.get("telemetry", {}).get("total_tokens", 3000)
        add_tokens_to_user(user_id, tokens_actual, session)
        session.add(UsageLog(user_id=user_id, action_type="solve_v3_request", tokens_used=tokens_actual))
        
        session.add(ChatMessage(
            session_id=new_chat.id,
            role="assistant",
            content=final_answer,
            structured_data=result,
            model_used=result.get("_model", "gpt-5-mini"),
            tokens_used=tokens_actual,
            telemetry=result.get("telemetry")
        ))
        
        session.commit()
        
        # Return V3 response
        # Merge session info into the result
        result["session_id"] = new_chat.id
        result["plot_url"] = plot_url
        result["tokens_used"] = tokens_actual
        result["request_id"] = request_id

        telemetry = result.get("telemetry") or result.get("_telemetry") or {}
        openai_payload = telemetry.get("openai_payload") or {}
        profile_key = None
        if resolved_profile:
            profile_key = f"{resolved_profile.tier.upper().replace('-', '_')}_{resolved_profile.mode.upper()}"
        plan_key = None
        if user and user.subscription and user.subscription.plan:
            plan_key = user.subscription.plan.slug
        elif resolved_profile:
            plan_key = resolved_profile.tier
        effective_max_tokens = None
        if resolved_profile:
            effective_max_tokens = min(
                resolved_profile.max_output_tokens,
                4000 if learning_mode == "study" else 3000
            )
        log_solve_trace({
            "request_id": request_id,
            "user_id": user_id,
            "seat_id": None,
            "plan_key": plan_key,
            "ui_goal": learning_mode,
            "ui_style": requested_mode,
            "resolved_profile_key": profile_key,
            "resolved_system_file_path": (resolved_profile.system_asset_path if resolved_profile else None) or (resolved_profile.system_relative_path if resolved_profile else None),
            "resolved_schema_file_path": (resolved_profile.schema_asset_path if resolved_profile else None) or (resolved_profile.schema_relative_path if resolved_profile else None),
            "schema_name": openai_payload.get("response_format_schema_name"),
            "max_output_tokens_sent": effective_max_tokens,
            "model_sent": telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
            "cache_hit": bool(was_cached or question_cache_hit),
            "openai_calls_count": telemetry.get("openai_calls_count", 0),
            "repair_attempted": telemetry.get("repair_attempted", False),
            "prompt_tokens_estimate": None,
            "input_tokens": telemetry.get("input_tokens"),
            "output_tokens": telemetry.get("output_tokens"),
            "cached_tokens": telemetry.get("cached_tokens"),
            "deduct_attempted": deduct_attempted,
            "deduct_committed": deduct_committed,
            "openai_payload": openai_payload,
            "problem_text": problem_text
        })

        record_request_event(session, {
            "request_id": request_id,
            "user_id": user_id,
            "mode": requested_mode,
            "learning_mode": learning_mode,
            "subject": body.subject,
            "grade_level": user.grade_level if user else None,
            "model": telemetry.get("model") or result.get("_model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
            "provider": "openai",
            "route": "solve_v3",
            "tokens_in": telemetry.get("input_tokens"),
            "tokens_out": telemetry.get("output_tokens"),
            "tokens_total": telemetry.get("total_tokens") or tokens_actual,
            "cost_usd": _calc_cost(
                telemetry.get("total_tokens") or tokens_actual,
                telemetry.get("model"),
                telemetry.get("input_tokens"),
                telemetry.get("output_tokens")
            ),
            "latency_ms": telemetry.get("latency_ms_total") or telemetry.get("latency_ms_openai"),
            "status": "ok",
            "error_type": None,
            "schema_valid": telemetry.get("validated"),
            "verification_pass": _verification_passed(result),
            "is_stream": False,
            "is_cached": bool(was_cached or question_cache_hit),
            "credit_deducted": deduct_committed,
            "credit_amount": debit_cost if deduct_committed and 'debit_cost' in locals() else None,
            "ocr_used": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
            "voice_used": bool(body.has_voice or features_used.get("voice_used")),
            "response_truncated": bool(result.get("_truncated") or telemetry.get("truncated"))
        })

        return result
    
    except Exception as e:
        print(f"[API_V3_ERROR] Solver V3 failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        try:
            profile_key = None
            if resolved_profile:
                profile_key = f"{resolved_profile.tier.upper().replace('-', '_')}_{resolved_profile.mode.upper()}"
            plan_key = None
            if user and user.subscription and user.subscription.plan:
                plan_key = user.subscription.plan.slug
            elif resolved_profile:
                plan_key = resolved_profile.tier
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": profile_key,
                "resolved_system_file_path": (resolved_profile.system_asset_path if resolved_profile else None) or (resolved_profile.system_relative_path if resolved_profile else None),
                "resolved_schema_file_path": (resolved_profile.schema_asset_path if resolved_profile else None) or (resolved_profile.schema_relative_path if resolved_profile else None),
                "schema_name": None,
                "max_output_tokens_sent": None,
                "model_sent": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "cache_hit": bool(was_cached or question_cache_hit),
                "openai_calls_count": 0,
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": None,
                "output_tokens": None,
                "cached_tokens": None,
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": None,
                "problem_text": problem_text,
                "error": str(e)
            })
        except Exception:
            pass
        try:
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user.grade_level if user else None,
                "model": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "provider": "openai",
                "route": "solve_v3",
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "cost_usd": 0.0,
                "latency_ms": None,
                "status": "error",
                "error_type": type(e).__name__,
                "schema_valid": None,
                "verification_pass": False,
                "is_stream": False,
                "is_cached": bool(was_cached or question_cache_hit),
                "credit_deducted": deduct_committed,
                "credit_amount": debit_cost if deduct_committed and 'debit_cost' in locals() else None,
                "ocr_used": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
                "voice_used": bool(body.has_voice or features_used.get("voice_used")),
                "response_truncated": False
            })
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Solver V3 failed: {str(e)}"
        )
    
@api_router.post("/solve_v3_stream")
async def solve_v3_stream_endpoint(
    request: Request,
    body: SolveRequest,
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    """
    Streaming Math Solver V3 (Part A1).
    SSE Sequence: meta -> stage -> delta -> telemetry -> done
    """
    from app.services.solver_v3 import get_solver_v3
    from app.services.solve.question_identity_service import question_identity_service
    from app.services.solve.trace_logger import log_solve_trace
    from app.services.admin.analytics_service import record_request_event, _calc_cost
    import base64
    from pathlib import Path

    async def generate():
        start_total = time.perf_counter()
        request_id = str(uuid.uuid4())
        
        requested_mode = body.requested_mode or "minimal"
        learning_mode = (body.trusted_context or {}).get("learning_mode", "solve")
        deduct_attempted = {"credits": False, "ocr": False, "voice": False}
        deduct_committed = False
        features_used = body.features_used or {}

        # Resolve profile for correct prompt/schema/tokens
        from app.llm_profiles.profile_resolver import ProfileResolver
        user_obj = session.get(User, user_id)
        profile = ProfileResolver.resolve_profile(
            session,
            user_obj,
            requested_mode=requested_mode,
            learning_mode=learning_mode
        )
        print(f"[SOLVER_V3_STREAM] Resolved Profile: Tier={profile.tier}, Mode={profile.mode}, MaxTokens={profile.max_output_tokens}")
        profile_key = f"{profile.tier.upper().replace('-', '_')}_{profile.mode.upper()}"
        plan_key = None
        if user_obj and user_obj.subscription and user_obj.subscription.plan:
            plan_key = user_obj.subscription.plan.slug
        else:
            plan_key = profile.tier

        effective_max_tokens = min(
            profile.max_output_tokens,
            4000 if learning_mode == "study" else 3000
        )

        problem_text = (
            body.confirmed_text or
            body.confirmed_markdown or
            body.text_query or
            "No problem provided"
        ).strip()

        if not problem_text:
            print("[SOLVER_V3_STREAM] No problem text found in request body")
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": profile_key,
                "resolved_system_file_path": profile.system_asset_path or profile.system_relative_path,
                "resolved_schema_file_path": profile.schema_asset_path or profile.schema_relative_path,
                "schema_name": None,
                "max_output_tokens_sent": effective_max_tokens,
                "model_sent": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "cache_hit": False,
                "openai_calls_count": 0,
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": None,
                "output_tokens": None,
                "cached_tokens": None,
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": None,
                "problem_text": problem_text,
                "error": "no_input"
            })
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_obj.grade_level if user_obj else None,
                "model": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "provider": "openai",
                "route": "solve_v3_stream",
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "cost_usd": 0.0,
                "latency_ms": None,
                "status": "error",
                "error_type": "no_input",
                "schema_valid": None,
                "verification_pass": False,
                "is_stream": True,
                "is_cached": False,
                "credit_deducted": False,
                "credit_amount": None,
                "ocr_used": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
                "voice_used": bool(body.has_voice or features_used.get("voice_used")),
                "response_truncated": False
            })
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': {'code': 'no_input', 'message': 'No input provided'}})}\n\n"
            return

        # Entitlement check + debit (credits/OCR/voice)
        action_mode = "detailed" if requested_mode == "detailed" else "concise"
        action_req = {
            "mode": action_mode,
            "has_ocr": bool(body.image_url or body.artifact_id or features_used.get("ocr_used")),
            "has_voice": bool(body.has_voice or features_used.get("voice_used")),
            "question_hash": str(hash(problem_text)),
            "is_make_it_right": getattr(body, "is_make_it_right", False)
        }
        deduct_attempted = {
            "credits": True,
            "ocr": action_req["has_ocr"],
            "voice": action_req["has_voice"]
        }

        check_result = subscription_service.check_entitlement_and_debit(session, user_id, action_req)
        if not check_result["allowed"]:
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": profile_key,
                "resolved_system_file_path": profile.system_asset_path or profile.system_relative_path,
                "resolved_schema_file_path": profile.schema_asset_path or profile.schema_relative_path,
                "schema_name": None,
                "max_output_tokens_sent": effective_max_tokens,
                "model_sent": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "cache_hit": False,
                "openai_calls_count": 0,
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": None,
                "output_tokens": None,
                "cached_tokens": None,
                "deduct_attempted": deduct_attempted,
                "deduct_committed": False,
                "openai_payload": None,
                "problem_text": problem_text,
                "error": f"entitlement_denied: {check_result.get('reason')}"
            })
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_obj.grade_level if user_obj else None,
                "model": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "provider": "openai",
                "route": "solve_v3_stream",
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "cost_usd": 0.0,
                "latency_ms": None,
                "status": "error",
                "error_type": "entitlement_denied",
                "schema_valid": None,
                "verification_pass": False,
                "is_stream": True,
                "is_cached": False,
                "credit_deducted": False,
                "credit_amount": None,
                "ocr_used": action_req["has_ocr"],
                "voice_used": action_req["has_voice"],
                "response_truncated": False
            })
            raise HTTPException(status_code=402, detail=f"Entitlement Check Failed: {check_result['reason']}")

        sub_id = check_result["subscription"].id
        debit_cost = check_result["cost"]
        subscription_service.execute_debit(
            session,
            check_result["subscription"],
            debit_cost,
            {"action": "solve_v3_stream", **action_req},
            request_id
        )
        session.commit()
        deduct_committed = True

        # Meta Event (Part A1)
        meta_data = {
            "request_id": request_id,
            "session_id": None, # Will be set after creation
            "message_id": None,
            "model": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-4o"),
            "max_output_tokens": effective_max_tokens,
            "mode": requested_mode
        }
        
        max_output_tokens = effective_max_tokens
        meta_data["type"] = "meta"
        yield f"event: meta\ndata: {json.dumps(meta_data)}\n\n"

        # Stage: Preparing request... (Part A2)
        yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Preparing request...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

        print(f"[SOLVER_V3_STREAM] Recv: {problem_text[:50]}... (Mode: {body.mode}, tokens: {max_output_tokens})")

        try:
            validate_math_query(problem_text)
        except HTTPException as e:
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": profile_key,
                "resolved_system_file_path": profile.system_asset_path or profile.system_relative_path,
                "resolved_schema_file_path": profile.schema_asset_path or profile.schema_relative_path,
                "schema_name": None,
                "max_output_tokens_sent": effective_max_tokens,
                "model_sent": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "cache_hit": False,
                "openai_calls_count": 0,
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": None,
                "output_tokens": None,
                "cached_tokens": None,
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": None,
                "problem_text": problem_text,
                "error": f"validation_error: {e.detail}"
            })
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_obj.grade_level if user_obj else None,
                "model": os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "provider": "openai",
                "route": "solve_v3_stream",
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "cost_usd": 0.0,
                "latency_ms": None,
                "status": "error",
                "error_type": "validation_error",
                "schema_valid": False,
                "verification_pass": False,
                "is_stream": True,
                "is_cached": False,
                "credit_deducted": deduct_committed,
                "credit_amount": None,
                "ocr_used": action_req["has_ocr"],
                "voice_used": action_req["has_voice"],
                "response_truncated": False
            })
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': {'code': 'validation_error', 'message': e.detail}})}\n\n"
            return

        # Context Assembly (Matches existing logic)
        context = f"Subject: {body.subject or 'General'}"
        if body.difficulty: context += f", Difficulty: {body.difficulty}"
        if body.mode: context += f", Mode: {body.mode}"
        
        user_obj = session.get(User, user_id)
        if user_obj:
            country = user_obj.profile_country or 'Canada'
            province = user_obj.profile_province_state or 'ON'
            context += f"\n\n[STUDENT CONTEXT]\nCountry: {country}\nProvince: {province}\nGrade: {user_obj.grade_level or 'Unknown'}"

        # Part E1: Create placeholder assistant message row
        new_chat = ChatSession(
            user_id=user_id,
            title=problem_text[:50],
            subject=body.subject or "General",
            is_saved=False
        )
        session.add(new_chat)
        session.commit()
        session.refresh(new_chat)

        placeholder_msg = ChatMessage(
            session_id=new_chat.id,
            role="assistant",
            content="",
            model_used=meta_data["model"]
        )
        session.add(ChatMessage(session_id=new_chat.id, role="user", content=problem_text, media_url=body.image_url))
        session.add(placeholder_msg)
        session.commit()
        session.refresh(placeholder_msg)

        # Update meta with IDs
        meta_data["session_id"] = new_chat.id
        meta_data["message_id"] = placeholder_msg.id
        # Re-send meta with IDs
        yield f"event: meta\ndata: {json.dumps(meta_data)}\n\n"

        # Stage: Calling AI model...
        yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Calling AI model...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

        solver = get_solver_v3()
        full_content = ""
        openai_telemetry = {}
        
        # Stage: Waiting for model...
        yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Waiting for model...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

        try:
            async for chunk in solver.solve_stream(
                problem_text,
                context,
                trace=True,
                request_id=request_id,
                max_output_tokens=max_output_tokens,
                system_prompt=profile.system_prompt_content,
                json_schema_config=profile.json_schema_content,
                trusted_context=body.trusted_context,
                requested_mode=requested_mode
            ):
                if chunk["type"] == "delta":
                    full_content += chunk["text"]
                    yield f"event: delta\ndata: {json.dumps({'type': 'delta', 'text': chunk['text']})}\n\n"
                elif chunk["type"] == "telemetry":
                    openai_telemetry = chunk["telemetry"]
                elif chunk["type"] == "meta" and chunk.get("truncated"):
                    yield f"event: meta\ndata: {json.dumps({'type': 'meta', 'truncated': True})}\n\n"
                elif chunk["type"] == "error":
                    subscription_service.refund_credits(session, sub_id, debit_cost, f"Stream Error: {chunk['error']}", request_id)
                    log_solve_trace({
                        "request_id": request_id,
                        "user_id": user_id,
                        "seat_id": None,
                        "plan_key": plan_key,
                        "ui_goal": learning_mode,
                        "ui_style": requested_mode,
                        "resolved_profile_key": profile_key,
                        "resolved_system_file_path": profile.system_asset_path or profile.system_relative_path,
                        "resolved_schema_file_path": profile.schema_asset_path or profile.schema_relative_path,
                        "schema_name": (openai_telemetry.get("openai_payload") or {}).get("response_format_schema_name"),
                        "max_output_tokens_sent": effective_max_tokens,
                        "model_sent": openai_telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                        "cache_hit": False,
                        "openai_calls_count": openai_telemetry.get("openai_calls_count", 0),
                        "repair_attempted": False,
                        "prompt_tokens_estimate": None,
                        "input_tokens": openai_telemetry.get("input_tokens"),
                        "output_tokens": openai_telemetry.get("output_tokens"),
                        "cached_tokens": openai_telemetry.get("cached_tokens"),
                        "deduct_attempted": deduct_attempted,
                        "deduct_committed": deduct_committed,
                        "openai_payload": openai_telemetry.get("openai_payload"),
                        "problem_text": problem_text,
                        "error": str(chunk.get("error"))
                    })
                    record_request_event(session, {
                        "request_id": request_id,
                        "user_id": user_id,
                        "mode": requested_mode,
                        "learning_mode": learning_mode,
                        "subject": body.subject,
                        "grade_level": user_obj.grade_level if user_obj else None,
                        "model": openai_telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                        "provider": "openai",
                        "route": "solve_v3_stream",
                        "tokens_in": openai_telemetry.get("input_tokens"),
                        "tokens_out": openai_telemetry.get("output_tokens"),
                        "tokens_total": openai_telemetry.get("total_tokens"),
                        "cost_usd": _calc_cost(
                            openai_telemetry.get("total_tokens"),
                            openai_telemetry.get("model"),
                            openai_telemetry.get("input_tokens"),
                            openai_telemetry.get("output_tokens")
                        ),
                        "latency_ms": openai_telemetry.get("latency_ms_total") or openai_telemetry.get("latency_ms_openai"),
                        "status": "error",
                        "error_type": "stream_error",
                        "schema_valid": False,
                        "verification_pass": False,
                        "is_stream": True,
                        "is_cached": False,
                        "credit_deducted": deduct_committed,
                        "credit_amount": debit_cost if deduct_committed else None,
                        "ocr_used": action_req["has_ocr"],
                        "voice_used": action_req["has_voice"],
                        "response_truncated": bool(openai_telemetry.get("truncated"))
                    })
                    yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': chunk['error']})}\n\n"
                    return

            # Stage: Validating response...
            yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Validating response...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"
            
            # Post-stream persistence and validation (Part E1)
            final_data = {}
            is_truncated = openai_telemetry.get("truncated", False)
            print(f"[SOLVER_V3_STREAM] Stream finished. Content length: {len(full_content)} chars, truncated: {is_truncated}")
            
            def try_recover_json(content: str) -> dict:
                """Attempt to recover truncated JSON by removing incomplete elements and closing brackets."""
                import re
                
                # Step 1: Find the last complete key-value pair by removing trailing incomplete string
                # Remove incomplete string at end (e.g., `"key": "incomplete text` without closing quote)
                content = re.sub(r':\s*"[^"]*$', ': ""', content)  # Close incomplete string values
                content = re.sub(r',\s*"[^"]*$', '', content)  # Remove trailing incomplete keys
                content = re.sub(r',\s*$', '', content)  # Remove trailing comma
                
                # Step 2: Close all open brackets/braces
                open_braces = content.count('{') - content.count('}')
                open_brackets = content.count('[') - content.count(']')
                content += '""' * (content.count('"') % 2)  # Close open quote if odd
                content += ']' * max(0, open_brackets)
                content += '}' * max(0, open_braces)
                
                return json.loads(content)
            
            try:
                if not full_content.strip():
                    raise ValueError("Empty content received from LLM")
                
                # Attempt direct parse first
                try:
                    final_data = json.loads(full_content)
                    print(f"[SOLVER_V3_STREAM] ✅ JSON parsed directly")
                except json.JSONDecodeError as parse_err:
                    print(f"[SOLVER_V3_STREAM] ⚠️ Direct parse failed: {parse_err}. Attempting recovery...")
                    try:
                        final_data = try_recover_json(full_content)
                        print(f"[SOLVER_V3_STREAM] ✅ JSON recovered successfully")
                        is_truncated = True  # Mark as truncated since we had to recover
                    except Exception as recovery_err:
                        print(f"[SOLVER_V3_STREAM] ⚠️ Recovery failed: {recovery_err}")
                        raise parse_err
                
                final_data = solver.normalize_solver_response(final_data)
                if is_truncated:
                    final_data["_truncated"] = True
                    final_data["_truncation_warning"] = "Response was truncated due to output token limit"
                print(f"[SOLVER_V3_STREAM] ✅ Normalized. Steps: {len(final_data.get('steps', []))}")
            except Exception as e:
                # Refund on failure
                subscription_service.refund_credits(session, sub_id, debit_cost, f"Stream Error: {str(e)}", request_id)
                print(f"[SOLVER_V3_STREAM] ❌ All parsing failed. Error: {e}")
                print(f"[SOLVER_V3_STREAM] Partial content (first 500 chars): {full_content[:500]}")
                # Create minimal valid structure even on complete failure
                final_data = {
                    "problem": {"original_text": problem_text, "normalized_text": problem_text},
                    "classification": {"topic": "Unknown", "difficulty": "Unknown"},
                    "steps": [],
                    "final_answer": {"answer_text": "Solution generation failed - response was truncated or malformed", "answer_latex": "\\text{Error}"},
                    "verification": {"method": "N/A", "work_latex": "", "conclusion": "Unable to verify"},
                    "visuals": {"should_visualize": False, "plots": []},
                    "quality": {"confidence": 0.0, "common_mistakes": [], "next_practice": []},
                    "assumptions": [],
                    "refusal": {"is_refusal": False, "reason": "", "safe_alternative": ""},
                    "_truncated": True,
                    "_parse_error": str(e),
                    "_raw_partial": full_content[:1000] if len(full_content) > 1000 else full_content
                }

            if True: # Always attempt to save what we have
                # Stage: Rendering plot...
                plot_url = None
                if final_data.get("visuals", {}).get("should_visualize"):
                    yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Rendering plot...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"
                    if "_plot_image" in final_data:
                        try:
                            plot_bytes = base64.b64decode(final_data["_plot_image"])
                            plots_dir = Path(__file__).parent.parent / "storage" / "plots"
                            plots_dir.mkdir(parents=True, exist_ok=True)
                            filename = f"plot_{user_id}_{datetime.utcnow().timestamp()}.png"
                            filepath = plots_dir / filename
                            with open(filepath, "wb") as f: f.write(plot_bytes)
                            plot_url = f"/storage/plots/{filename}"
                            final_data["visuals"]["plot_url"] = plot_url
                        except: pass

                # Stage: Finalizing...
                yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Finalizing...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

                # Update DB (Part E1)
                placeholder_msg.content = str(final_data.get("final_answer", {}).get("answer_text", "Solution complete"))
                placeholder_msg.structured_data = final_data
                placeholder_msg.telemetry = openai_telemetry
                placeholder_msg.tokens_used = openai_telemetry.get("total_tokens", 0)
                
                # Token Tracking (Part D3)
                tokens = openai_telemetry.get("total_tokens", 0)
                if tokens > 0:
                    add_tokens_to_user(user_id, tokens, session)
                    session.add(UsageLog(user_id=user_id, action_type="solve_v3_stream", tokens_used=tokens))
                
                # Cache store
                try:
                    question_fingerprint = question_identity_service.compute_question_fingerprint(problem_text)
                    question_key = question_identity_service.compute_question_key(question_fingerprint)
                    question_identity_service.store_question_result(session, question_key, question_fingerprint, final_data, problem_text)
                except: pass

                session.commit()
                print(f"[SOLVER_V3_STREAM] ✅ Successfully persisted results for session {new_chat.id}")

            # Final Telemetry Event
            openai_telemetry["type"] = "telemetry"
            openai_telemetry["latency_ms_total"] = int((time.perf_counter() - start_total) * 1000)
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": profile_key,
                "resolved_system_file_path": profile.system_asset_path or profile.system_relative_path,
                "resolved_schema_file_path": profile.schema_asset_path or profile.schema_relative_path,
                "schema_name": (openai_telemetry.get("openai_payload") or {}).get("response_format_schema_name"),
                "max_output_tokens_sent": effective_max_tokens,
                "model_sent": openai_telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "cache_hit": False,
                "openai_calls_count": openai_telemetry.get("openai_calls_count", 0),
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": openai_telemetry.get("input_tokens"),
                "output_tokens": openai_telemetry.get("output_tokens"),
                "cached_tokens": openai_telemetry.get("cached_tokens"),
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": openai_telemetry.get("openai_payload"),
                "problem_text": problem_text
            })
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_obj.grade_level if user_obj else None,
                "model": openai_telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "provider": "openai",
                "route": "solve_v3_stream",
                "tokens_in": openai_telemetry.get("input_tokens"),
                "tokens_out": openai_telemetry.get("output_tokens"),
                "tokens_total": openai_telemetry.get("total_tokens"),
                "cost_usd": _calc_cost(
                    openai_telemetry.get("total_tokens"),
                    openai_telemetry.get("model"),
                    openai_telemetry.get("input_tokens"),
                    openai_telemetry.get("output_tokens")
                ),
                "latency_ms": openai_telemetry.get("latency_ms_total") or openai_telemetry.get("latency_ms_openai"),
                "status": "ok",
                "error_type": None,
                "schema_valid": not final_data.get("_parse_error"),
                "verification_pass": _verification_passed(final_data),
                "is_stream": True,
                "is_cached": False,
                "credit_deducted": deduct_committed,
                "credit_amount": debit_cost if deduct_committed else None,
                "ocr_used": action_req["has_ocr"],
                "voice_used": action_req["has_voice"],
                "response_truncated": bool(openai_telemetry.get("truncated") or final_data.get("_truncated"))
            })
            yield f"event: telemetry\ndata: {json.dumps(openai_telemetry)}\n\n"

            # Done Event
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': True, 'session_id': new_chat.id, 'message_id': placeholder_msg.id})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[SOLVER_V3_STREAM] ❌ FATAL ERROR: {str(e)}")
            session.commit()
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": profile_key,
                "resolved_system_file_path": profile.system_asset_path or profile.system_relative_path,
                "resolved_schema_file_path": profile.schema_asset_path or profile.schema_relative_path,
                "schema_name": (openai_telemetry.get("openai_payload") or {}).get("response_format_schema_name"),
                "max_output_tokens_sent": effective_max_tokens,
                "model_sent": openai_telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                "cache_hit": False,
                "openai_calls_count": openai_telemetry.get("openai_calls_count", 0),
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": openai_telemetry.get("input_tokens"),
                "output_tokens": openai_telemetry.get("output_tokens"),
                "cached_tokens": openai_telemetry.get("cached_tokens"),
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": openai_telemetry.get("openai_payload"),
                "problem_text": problem_text,
                "error": str(e)
            })
            try:
                record_request_event(session, {
                    "request_id": request_id,
                    "user_id": user_id,
                    "mode": requested_mode,
                    "learning_mode": learning_mode,
                    "subject": body.subject,
                    "grade_level": user_obj.grade_level if user_obj else None,
                    "model": openai_telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini"),
                    "provider": "openai",
                    "route": "solve_v3_stream",
                    "tokens_in": openai_telemetry.get("input_tokens"),
                    "tokens_out": openai_telemetry.get("output_tokens"),
                    "tokens_total": openai_telemetry.get("total_tokens"),
                    "cost_usd": _calc_cost(
                        openai_telemetry.get("total_tokens"),
                        openai_telemetry.get("model"),
                        openai_telemetry.get("input_tokens"),
                        openai_telemetry.get("output_tokens")
                    ),
                    "latency_ms": openai_telemetry.get("latency_ms_total") or openai_telemetry.get("latency_ms_openai"),
                    "status": "error",
                    "error_type": type(e).__name__,
                    "schema_valid": False,
                    "verification_pass": False,
                    "is_stream": True,
                    "is_cached": False,
                    "credit_deducted": deduct_committed,
                    "credit_amount": debit_cost if deduct_committed else None,
                    "ocr_used": action_req["has_ocr"],
                    "voice_used": action_req["has_voice"],
                    "response_truncated": bool(openai_telemetry.get("truncated"))
                })
            except Exception:
                pass
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': {'code': 'internal_error', 'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
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
# Location & School Directory Endpoints
# ------------------------------------------------------------------

# Valid countries and provinces/states
VALID_COUNTRIES = ['USA', 'Canada']

US_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
]

CA_PROVINCES = [
    'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'
]

VALID_GRADE_LEVELS = [f"Grade {i}" for i in range(1, 13)]


@api_router.get("/locations/countries")
async def get_countries():
    """Get list of supported countries for student profiles."""
    return {"countries": VALID_COUNTRIES}


@api_router.get("/locations/provinces")
async def get_provinces(country: str = Query(..., description="Country code (USA or Canada)")):
    """Get list of provinces/states for a country."""
    if country not in VALID_COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Invalid country. Must be one of: {VALID_COUNTRIES}")
    
    if country == 'USA':
        return {"provinces": US_STATES, "label": "State"}
    else:
        return {"provinces": CA_PROVINCES, "label": "Province/Territory"}


@api_router.get("/locations/grades")
async def get_grade_levels():
    """Get list of valid grade levels."""
    return {"grades": VALID_GRADE_LEVELS}


class SchoolSearchResult(BaseModel):
    id: int
    school_name: str
    city: Optional[str]
    district: Optional[str]


@api_router.get("/schools/search", response_model=List[SchoolSearchResult])
async def search_schools(
    country: str = Query(..., description="Country (USA or Canada)"),
    province_state: str = Query(..., description="State or Province abbreviation"),
    q: str = Query("", description="Search query for school name"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    session: Session = Depends(get_session)
):
    """
    Search schools by country, province/state, and optional name query.
    Returns minimal fields for dropdown display.
    """
    if country not in VALID_COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Invalid country. Must be one of: {VALID_COUNTRIES}")
    
    # Validate province_state
    valid_provinces = US_STATES if country == 'USA' else CA_PROVINCES
    if province_state not in valid_provinces:
        raise HTTPException(status_code=400, detail=f"Invalid province/state for {country}")
    
    # Build query
    stmt = select(School).where(
        School.country == country,
        School.province_state == province_state
    )
    
    # Add name filter if query provided
    if q and len(q) >= 2:
        # Use ILIKE for case-insensitive search
        stmt = stmt.where(School.school_name.ilike(f"%{q}%"))
    
    # Order by name and limit
    stmt = stmt.order_by(School.school_name).limit(limit)
    
    schools = session.exec(stmt).all()
    
    return [
        SchoolSearchResult(
            id=s.id,
            school_name=s.school_name,
            city=s.city,
            district=s.district
        )
        for s in schools
    ]


class ProfileLocationUpdateRequest(BaseModel):
    """Request body for updating profile location fields."""
    profile_country: str  # Required: 'USA' or 'Canada'
    profile_province_state: str  # Required: State or Province abbreviation
    grade_level: str  # Required: 'Grade 1' to 'Grade 12'
    school_id: Optional[int] = None  # Optional FK to School


@api_router.patch("/user/profile-location")
async def update_profile_location(
    user_id: int = Query(...),
    body: ProfileLocationUpdateRequest = ...,
    session: Session = Depends(get_session)
):
    """
    Update user's location profile for curriculum context.
    Validates all fields and checks school_id consistency.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate country
    if body.profile_country not in VALID_COUNTRIES:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid country. Must be one of: {VALID_COUNTRIES}"
        )
    
    # Validate province/state for country
    valid_provinces = US_STATES if body.profile_country == 'USA' else CA_PROVINCES
    if body.profile_province_state not in valid_provinces:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid province/state for {body.profile_country}"
        )
    
    # Validate grade level
    if body.grade_level not in VALID_GRADE_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid grade level. Must be one of: {VALID_GRADE_LEVELS}"
        )
    
    # Validate school_id if provided
    if body.school_id is not None:
        school = session.get(School, body.school_id)
        if not school:
            raise HTTPException(status_code=400, detail="School not found")
        
        # Ensure school matches the country and province
        if school.country != body.profile_country or school.province_state != body.profile_province_state:
            raise HTTPException(
                status_code=400,
                detail="School must be in the same country and province/state as user profile"
            )
    
    # Update user profile
    user.profile_country = body.profile_country
    user.profile_province_state = body.profile_province_state
    user.grade_level = body.grade_level
    user.school_id = body.school_id
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {
        "status": "updated",
        "profile_country": user.profile_country,
        "profile_province_state": user.profile_province_state,
        "grade_level": user.grade_level,
        "school_id": user.school_id
    }


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
    
    history_items = []
    for chat in results:
        # Extract user input
        user_input = next((msg.content for msg in chat.messages if msg.role == "user"), None)
        
        # Extract telemetry from any assistant message (prefer most recent)
        telemetry = None
        for msg in reversed(chat.messages):
            if msg.role == "assistant":
                if msg.telemetry:
                    telemetry = msg.telemetry
                    break
                # Fallback to structured_data telemetry (legacy/migration support)
                elif msg.structured_data and isinstance(msg.structured_data, dict):
                    telemetry = msg.structured_data.get("telemetry") or msg.structured_data.get("_telemetry")
                    if telemetry: 
                        break
        
        history_items.append(ChatHistoryItem(
            id=chat.id, 
            title=chat.title, 
            created_at=chat.created_at.isoformat(),
            subject=chat.subject or "Math",
            topic=chat.topic,
            input=user_input,
            is_saved=chat.is_saved,
            telemetry=telemetry
        ))
        
    return history_items

class ChatMessageSchema(BaseModel):
    role: str
    content: str
    media_url: Optional[str] = None
    structured_data: Optional[dict] = None
    created_at: str
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    telemetry: Optional[dict] = None # Added telemetry

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
                tokens_used=getattr(msg, "tokens_used", None),
                # Fallback logic for telemetry
                telemetry=(
                    msg.telemetry if hasattr(msg, "telemetry") and msg.telemetry else
                    (msg.structured_data.get("telemetry") or msg.structured_data.get("_telemetry")) if msg.structured_data and isinstance(msg.structured_data, dict) else None
                )
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

        # Location Profile
        profile_country=user.profile_country,
        profile_province_state=user.profile_province_state,
        grade_level=user.grade_level,
        school_id=user.school_id,
        
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

def add_tokens_to_user(user_id: int, tokens: int, db: Session):
    """Adds tokens to user's monthly usage"""
    user = db.get(User, user_id)
    if user:
        user = check_and_reset_monthly_tokens(user, db)
        user.tokens_used_this_month += tokens
        db.add(user)
        # We don't commit here, caller should commit

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


@api_router.get("/admin/users/{user_id}/full", response_model=Dict[str, Any])
async def admin_get_user_full(
    user_id: int,
    sessions_limit: int = Query(50, ge=1, le=500),
    messages_limit: int = Query(200, ge=1, le=2000),
    ledger_limit: int = Query(100, ge=1, le=2000),
    ocr_limit: int = Query(200, ge=1, le=2000),
    voice_limit: int = Query(200, ge=1, le=2000),
    request_limit: int = Query(200, ge=1, le=2000),
    device_limit: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_session)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subscription = db.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    plan = subscription.plan if subscription else None

    notes = db.exec(select(AdminNote).where(AdminNote.user_id == user_id).order_by(AdminNote.created_at.desc())).all()
    request_events = db.exec(
        select(RequestEvent)
        .where(RequestEvent.user_id == user_id)
        .order_by(RequestEvent.created_at.desc())
        .limit(request_limit)
    ).all()
    device_signups = db.exec(
        select(DeviceSignupLog)
        .where(DeviceSignupLog.user_id == user_id)
        .order_by(DeviceSignupLog.created_at.desc())
        .limit(device_limit)
    ).all()
    usage_logs = db.exec(select(UsageLog).where(UsageLog.user_id == user_id).order_by(UsageLog.timestamp.desc()).limit(ledger_limit)).all()
    payments = db.exec(select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc()).limit(ledger_limit)).all()
    overrides = db.exec(select(UserQuotaOverride).where(UserQuotaOverride.user_id == user_id).order_by(UserQuotaOverride.created_at.desc())).all()

    ledger_entries = []
    if subscription:
        ledger_entries = db.exec(
            select(UsageLedger)
            .where(UsageLedger.subscription_id == subscription.id)
            .order_by(UsageLedger.created_at.desc())
            .limit(ledger_limit)
        ).all()

    sessions = db.exec(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(sessions_limit)
    ).all()
    session_ids = [s.id for s in sessions]
    messages = []
    if session_ids:
        messages = db.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id.in_(session_ids))
            .order_by(ChatMessage.created_at.desc())
            .limit(messages_limit)
        ).all()

    uploads = db.exec(select(Upload).where(Upload.user_id == user_id).order_by(Upload.created_at.desc()).limit(ocr_limit)).all()
    upload_ids = [u.id for u in uploads]
    crops = []
    if upload_ids:
        crops = db.exec(select(Crop).where(Crop.upload_id.in_(upload_ids)).limit(ocr_limit)).all()
    crop_ids = [c.id for c in crops]
    ocr_jobs = db.exec(select(OCRJob).where(OCRJob.user_id == user_id).order_by(OCRJob.created_at.desc()).limit(ocr_limit)).all()
    artifacts = []
    if crop_ids:
        artifacts = db.exec(select(OCRArtifact).where(OCRArtifact.crop_id.in_(crop_ids)).limit(ocr_limit)).all()
    artifact_ids = [a.id for a in artifacts]
    questions = []
    figures = []
    confirmations = db.exec(select(OCRConfirmation).where(OCRConfirmation.user_id == user_id).order_by(OCRConfirmation.created_at.desc()).limit(ocr_limit)).all()
    audit_events = db.exec(select(OCRAuditEvent).where(OCRAuditEvent.user_id == user_id).order_by(OCRAuditEvent.created_at.desc()).limit(ocr_limit)).all()
    if artifact_ids:
        questions = db.exec(select(OCRQuestion).where(OCRQuestion.artifact_id.in_(artifact_ids)).limit(ocr_limit)).all()
        figures = db.exec(select(OCRFigure).where(OCRFigure.artifact_id.in_(artifact_ids)).limit(ocr_limit)).all()
    question_ids = [q.id for q in questions]
    choices = []
    if question_ids:
        choices = db.exec(select(OCRChoice).where(OCRChoice.question_id.in_(question_ids)).limit(ocr_limit)).all()

    voice_sessions = db.exec(select(VoiceSession).where(VoiceSession.user_id == user_id).order_by(VoiceSession.created_at.desc()).limit(voice_limit)).all()
    voice_session_ids = [s.id for s in voice_sessions]
    voice_audios = []
    voice_jobs = []
    voice_artifacts = []
    voice_confirmations = []
    if voice_session_ids:
        voice_audios = db.exec(select(VoiceAudio).where(VoiceAudio.voice_session_id.in_(voice_session_ids)).limit(voice_limit)).all()
        voice_jobs = db.exec(select(VoiceJob).where(VoiceJob.voice_session_id.in_(voice_session_ids)).limit(voice_limit)).all()
    voice_job_ids = [j.id for j in voice_jobs]
    if voice_job_ids:
        voice_artifacts = db.exec(select(VoiceArtifact).where(VoiceArtifact.job_id.in_(voice_job_ids)).limit(voice_limit)).all()
    voice_artifact_ids = [a.id for a in voice_artifacts]
    if voice_artifact_ids:
        voice_confirmations = db.exec(select(VoiceConfirmation).where(VoiceConfirmation.artifact_id.in_(voice_artifact_ids)).limit(voice_limit)).all()

    saved_solutions = db.exec(select(UserSavedSolution).where(UserSavedSolution.user_id == user_id)).all()

    return {
        "user": _sqlmodel_to_dict(user),
        "subscription": _sqlmodel_to_dict(subscription),
        "plan": _sqlmodel_to_dict(plan),
        "usage_ledger": _sqlmodel_list(ledger_entries),
        "usage_logs": _sqlmodel_list(usage_logs),
        "payments": _sqlmodel_list(payments),
        "quota_overrides": _sqlmodel_list(overrides),
        "admin_notes": _sqlmodel_list(notes),
        "request_events": _sqlmodel_list(request_events),
        "device_signup_logs": _sqlmodel_list(device_signups),
        "sessions": _sqlmodel_list(sessions),
        "messages": _sqlmodel_list(messages),
        "uploads": _sqlmodel_list(uploads),
        "crops": _sqlmodel_list(crops),
        "ocr_jobs": _sqlmodel_list(ocr_jobs),
        "ocr_artifacts": _sqlmodel_list(artifacts),
        "ocr_questions": _sqlmodel_list(questions),
        "ocr_choices": _sqlmodel_list(choices),
        "ocr_figures": _sqlmodel_list(figures),
        "ocr_confirmations": _sqlmodel_list(confirmations),
        "ocr_audit_events": _sqlmodel_list(audit_events),
        "voice_sessions": _sqlmodel_list(voice_sessions),
        "voice_audios": _sqlmodel_list(voice_audios),
        "voice_jobs": _sqlmodel_list(voice_jobs),
        "voice_artifacts": _sqlmodel_list(voice_artifacts),
        "voice_confirmations": _sqlmodel_list(voice_confirmations),
        "saved_solutions": _sqlmodel_list(saved_solutions)
    }

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
    # P2: Password Complexity Check
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    
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
    return {"status": "ok", "message": "Password reset to default successfully."}

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
    fallback_cost_per_million = float(os.getenv("OPENAI_COST_PER_1M_TOKENS", "0.50"))
    llm_cost_est_fallback = (total_tokens_24h / 1_000_000) * fallback_cost_per_million

    openai_key = os.getenv("OPENAI_API_KEY")
    def fetch_openai_usage(start_date: str, end_date: str):
        if not openai_key:
            return None
        try:
            resp = requests.get(
                "https://api.openai.com/v1/usage",
                headers={"Authorization": f"Bearer {openai_key}"},
                params={"start_date": start_date, "end_date": end_date},
                timeout=15
            )
            resp.raise_for_status()
            payload = resp.json()
            tokens_in = 0
            tokens_out = 0
            total_requests = 0
            total_spend = 0.0
            for item in payload.get("data", []):
                tokens_in += item.get("n_context_tokens_total") or item.get("prompt_tokens") or item.get("input_tokens") or 0
                tokens_out += item.get("n_generated_tokens_total") or item.get("completion_tokens") or item.get("output_tokens") or 0
                total_requests += item.get("n_requests") or item.get("requests") or 0
                total_spend += item.get("total_cost") or item.get("amount") or 0.0
            return {
                "input": tokens_in,
                "output": tokens_out,
                "requests": total_requests,
                "spend": total_spend
            }
        except Exception as e:
            logging.error(f"OpenAI usage fetch failed: {e}")
            return None

    today = now.date()
    daily_usage = fetch_openai_usage(today.isoformat(), today.isoformat())
    month_start = now.replace(day=1).date().isoformat()
    monthly_usage = fetch_openai_usage(month_start, today.isoformat())

    if daily_usage and monthly_usage:
        daily_total = daily_usage["input"] + daily_usage["output"]
        monthly_total = monthly_usage["input"] + monthly_usage["output"]
        llm_cost_est_daily = (daily_total / 1_000_000) * fallback_cost_per_million
        llm_cost_est_monthly = (monthly_total / 1_000_000) * fallback_cost_per_million
        llm_tokens_in_daily = daily_usage["input"]
        llm_tokens_out_daily = daily_usage["output"]
        llm_tokens_in_monthly = monthly_usage["input"]
        llm_tokens_out_monthly = monthly_usage["output"]
        llm_total_requests_daily = daily_usage.get("requests", 0)
        llm_total_requests_monthly = monthly_usage.get("requests", 0)
        llm_total_spend_daily = float(daily_usage.get("spend", 0.0))
        llm_total_spend_monthly = float(monthly_usage.get("spend", 0.0))
    else:
        llm_cost_est_daily = llm_cost_est_fallback
        llm_cost_est_monthly = llm_cost_est_fallback
        llm_tokens_in_daily = total_tokens_24h
        llm_tokens_out_daily = 0
        llm_tokens_in_monthly = total_tokens_24h
        llm_tokens_out_monthly = 0
        llm_total_requests_daily = daily_requests
        llm_total_requests_monthly = daily_requests
        llm_total_spend_daily = llm_cost_est_fallback
        llm_total_spend_monthly = llm_cost_est_fallback
    
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
        llm_cost_est=llm_cost_est_monthly,
        llm_cost_est_daily=llm_cost_est_daily,
        llm_cost_est_monthly=llm_cost_est_monthly,
        llm_total_requests_daily=llm_total_requests_daily,
        llm_total_requests_monthly=llm_total_requests_monthly,
        llm_total_spend_daily=llm_total_spend_daily,
        llm_total_spend_monthly=llm_total_spend_monthly,
        llm_tokens_in_daily=llm_tokens_in_daily,
        llm_tokens_out_daily=llm_tokens_out_daily,
        llm_tokens_in_monthly=llm_tokens_in_monthly,
        llm_tokens_out_monthly=llm_tokens_out_monthly,
        cache_hit_rate=42.5, # Placeholder for now as we don't track cache hits yet
        requests_growth=requests_growth,
        success_rate_change=0.0,
        cost_change=0.0,
        cache_hit_change=0.0,
        system_errors=system_errors
    )


@api_router.get("/admin/analytics/overview")
async def admin_analytics_overview(
    range: str = Query("7d"),
    mode: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    route: Optional[str] = Query(None),
    db: Session = Depends(get_session)
):
    from app.services.admin.analytics_service import get_overview
    filters = {
        "mode": mode,
        "model": model,
        "provider": provider,
        "route": route
    }
    return get_overview(db, range, filters)


@api_router.get("/admin/analytics/errors")
async def admin_analytics_errors(
    range: str = Query("1d"),
    severity: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    route: Optional[str] = Query(None),
    db: Session = Depends(get_session)
):
    from app.services.admin.analytics_service import get_errors
    filters = {
        "mode": mode,
        "model": model,
        "provider": provider,
        "route": route
    }
    return get_errors(db, range, severity, filters)


@api_router.get("/admin/analytics/anomalies")
async def admin_analytics_anomalies(
    range: str = Query("1d"),
    mode: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    route: Optional[str] = Query(None),
    db: Session = Depends(get_session)
):
    from app.services.admin.analytics_service import get_anomalies
    filters = {
        "mode": mode,
        "model": model,
        "provider": provider,
        "route": route
    }
    return get_anomalies(db, range, filters)

@api_router.get("/admin/solve-traces", response_model=List[SolveTraceEntry])
async def admin_get_solve_traces(
    limit: int = Query(100, ge=1, le=1000)
):
    from app.services.solve.trace_logger import TRACE_LOG_PATH
    if not TRACE_LOG_PATH.exists():
        return []
    try:
        lines = TRACE_LOG_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    trimmed = lines[-limit:]
    entries: List[Dict[str, Any]] = []
    for line in trimmed:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


@api_router.get("/admin/db/tables", response_model=List[str])
async def admin_list_db_tables():
    return sorted(list(SQLModel.metadata.tables.keys()))


@api_router.get("/admin/db/table/{table_name}", response_model=List[Dict[str, Any]])
async def admin_get_db_table(
    table_name: str,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session)
):
    table = SQLModel.metadata.tables.get(table_name)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    if table.schema:
        qualified_name = f"\"{table.schema}\".\"{table.name}\""
    else:
        qualified_name = f"\"{table.name}\""
    try:
        query = sql_text(f"SELECT * FROM {qualified_name} LIMIT :limit OFFSET :offset")
        rows = db.exec(query, {"limit": limit, "offset": offset}).all()
        return [dict(row._mapping) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read table {table_name}: {exc}")

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
    daily_active_holders = 0
    total_daily_tokens = 0
    total_daily_credits_used = 0.0
    total_daily_credit_cap = 0.0
    
    for u in users:
        subscription = db.exec(select(Subscription).where(Subscription.user_id == u.id)).first()
        plan = subscription.plan if subscription else None
        plan_features = plan.features or {} if plan else {}
        daily_credit_cap = float(plan_features.get("daily_credit_cap", 0)) if plan_features else 0.0

        daily_usage_logs = db.exec(
            select(UsageLog).where(UsageLog.user_id == u.id, UsageLog.timestamp >= last_24h)
        ).all()
        daily_tokens = sum([l.tokens_used for l in daily_usage_logs])
        total_daily_tokens += daily_tokens

        if daily_usage_logs:
            daily_active_holders += 1

        if subscription:
            daily_ledger = db.exec(
                select(UsageLedger)
                .where(UsageLedger.subscription_id == subscription.id)
                .where(UsageLedger.transaction_type == "DEBIT")
                .where(UsageLedger.created_at >= last_24h)
            ).all()
            daily_credits_used = sum([l.amount for l in daily_ledger])
        else:
            daily_credits_used = 0.0

        total_daily_credits_used += daily_credits_used
        if daily_credit_cap > 0:
            total_daily_credit_cap += daily_credit_cap

        override = db.exec(select(UserQuotaOverride).where(UserQuotaOverride.user_id == u.id)).first()
        override_token_limit = override.token_limit if override else None
        override_ocr_concurrency = override.ocr_concurrency if override else None
        override_expires_at = override.expires_at.isoformat() if override and override.expires_at else None

        usage_pct = 0
        if override_token_limit and override_token_limit > 0:
            usage_pct = int((daily_tokens / override_token_limit) * 100)
        elif daily_credit_cap > 0:
            usage_pct = int((daily_credits_used / daily_credit_cap) * 100)
        
        last_active = (u.last_active_at or u.created_at or now)
        diff = now - last_active
        if diff.total_seconds() < 60: active_str = "Just now"
        elif diff.total_seconds() < 3600: active_str = f"{int(diff.total_seconds()//60)} mins ago"
        else: active_str = f"{int(diff.total_seconds()//3600)} hours ago"

        quota_items.append(AdminQuotaUserItem(
            id=u.id,
            full_id=f"USR-{u.id}",
            full_name=u.full_name,
            email=u.email,
            plan=u.subscription_tier.capitalize(),
            usage_percent=min(usage_pct, 100) if usage_pct > 0 else 0,
            last_active=active_str,
            is_banned=u.subscription_status == "expired",
            credits_balance=subscription.credits_balance if subscription else None,
            credits_used_this_period=subscription.credits_used_this_period if subscription else None,
            daily_credits_used=daily_credits_used,
            daily_credit_cap=daily_credit_cap or None,
            daily_tokens_used=daily_tokens,
            override_token_limit=override_token_limit,
            override_ocr_concurrency=override_ocr_concurrency,
            override_expires_at=override_expires_at
        ))
    
    total_tokens_24h = total_daily_tokens
    global_consumption = 0.0
    if total_daily_credit_cap > 0:
        global_consumption = min((total_daily_credits_used / total_daily_credit_cap) * 100, 100.0)
    
    return AdminQuotaListResponse(
        users=quota_items,
        total_users=len(db.exec(select(User.id)).all()),
        global_consumption=round(global_consumption, 1),
        daily_active_holders=daily_active_holders,
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


@api_router.get("/admin/users/{user_id}/question-history", response_model=List[AdminQuestionHistoryItem])
async def admin_get_user_question_history(
    user_id: int,
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_session)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = db.exec(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(200)
    ).all()
    session_ids = [s.id for s in sessions]
    if not session_ids:
        return []

    messages = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id.in_(session_ids))
        .order_by(ChatMessage.created_at.asc())
    ).all()

    session_title_map = {s.id: s.title for s in sessions}
    last_user_by_session: Dict[int, ChatMessage] = {}
    assistant_items: List[Dict[str, Any]] = []

    for msg in messages:
        if msg.role == "user":
            last_user_by_session[msg.session_id] = msg
            continue
        if msg.role != "assistant":
            continue
        request_id = None
        if msg.structured_data and isinstance(msg.structured_data, dict):
            request_id = msg.structured_data.get("request_id")
        if not request_id and msg.telemetry and isinstance(msg.telemetry, dict):
            request_id = msg.telemetry.get("request_id")

        assistant_items.append({
            "request_id": request_id,
            "created_at": msg.created_at,
            "session_id": msg.session_id,
            "session_title": session_title_map.get(msg.session_id),
            "prompt": last_user_by_session.get(msg.session_id).content if last_user_by_session.get(msg.session_id) else None,
            "response": msg.content,
            "model": (msg.telemetry or {}).get("model") if msg.telemetry else msg.model_used,
            "tokens_total": msg.tokens_used
        })

    assistant_items = sorted(assistant_items, key=lambda item: item["created_at"], reverse=True)
    assistant_items = assistant_items[:limit]
    request_ids = [item["request_id"] for item in assistant_items if item.get("request_id")]
    event_map: Dict[str, RequestEvent] = {}
    if request_ids:
        events = db.exec(
            select(RequestEvent)
            .where(RequestEvent.user_id == user_id, RequestEvent.request_id.in_(request_ids))
        ).all()
        event_map = {event.request_id: event for event in events if event.request_id}

    response_items: List[AdminQuestionHistoryItem] = []
    for item in assistant_items:
        event = event_map.get(item.get("request_id"))
        response_items.append(AdminQuestionHistoryItem(
            request_id=item.get("request_id"),
            created_at=item["created_at"].isoformat() if hasattr(item["created_at"], "isoformat") else str(item["created_at"]),
            session_id=item.get("session_id"),
            session_title=item.get("session_title"),
            prompt=item.get("prompt"),
            response=item.get("response"),
            model=(event.model if event else item.get("model")),
            route=(event.route if event else None),
            tokens_in=(event.tokens_in if event else None),
            tokens_out=(event.tokens_out if event else None),
            tokens_total=(event.tokens_total if event else item.get("tokens_total")),
            cost_usd=(event.cost_usd if event else None),
            latency_ms=(event.latency_ms if event else None),
            status=(event.status if event else None),
            error_type=(event.error_type if event else None),
            schema_valid=(event.schema_valid if event else None),
            verification_pass=(event.verification_pass if event else None),
            is_stream=(event.is_stream if event else None),
            is_cached=(event.is_cached if event else None)
        ))

    return response_items

@api_router.get("/admin/prompts", response_model=List[PromptTemplateListItem])
async def admin_get_prompts(db: Session = Depends(get_session)):
    """Admin only: List all prompt templates"""
    templates = db.exec(select(PromptTemplate)).all()
    
    # If no templates, seed default ones
    if not templates:
        t1 = PromptTemplate(name="Math Solver", slug="math-solver", description="System instruction for advanced step-by-step math resolution")
        t2 = PromptTemplate(name="OCR Formatter", slug="ocr-formatter", description="Normalization rules for raw OCR output")
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



# ------------------------------------------------------------------
# Admin & Subscription Endpoints
# ------------------------------------------------------------------

class PlanCreate(BaseModel):
    name: str
    slug: str
    credits_per_month: int
    price_monthly_cents: int
    price_yearly_cents: int
    seats: int = 1
    features: Dict[str, Any] = {}
    multipliers: Dict[str, Any] = {}
    system_prompt_template_id: Optional[int] = None
    schema_prompt_template_id: Optional[int] = None
    is_active: bool = True

@api_router.get('/admin/plans')
async def list_plans(session: Session = Depends(get_session)):
    return session.exec(select(Plan)).all()

@api_router.post('/admin/plans')
async def create_or_update_plan(plan_data: PlanCreate, session: Session = Depends(get_session)):
    # Check if slug exists
    existing = session.exec(select(Plan).where(Plan.slug == plan_data.slug)).first()
    if existing:
        for key, value in plan_data.dict().items():
            setattr(existing, key, value)
        existing.version += 1
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    else:
        new_plan = Plan(**plan_data.dict())
        session.add(new_plan)
        session.commit()
        session.refresh(new_plan)
        return new_plan

@api_router.get('/users/me/subscription')
async def get_my_subscription(user_id: int = Query(...), session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user: raise HTTPException(404, detail='User not found')
    sub = subscription_service.get_or_create_subscription(session, user)
    return sub


@api_router.get('/admin/plans-with-prompts')
async def list_plans_with_prompts(session: Session = Depends(get_session)):
    plans = session.exec(select(Plan)).all()
    # Eager loading prompts would be better, but for now just returning IDs is fine
    # Frontend can fetch prompts separately
    return plans


@api_router.get('/public/plans')
async def list_public_plans(session: Session = Depends(get_session)):
    """Public endpoint to list active subscription plans for the pricing page"""
    return session.exec(select(Plan).where(Plan.is_active == True)).all()

