from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Form
from fastapi.responses import StreamingResponse, JSONResponse
from sqlmodel import Session, SQLModel, select
from sqlalchemy import text as sql_text, or_
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
import uuid
import re
import requests
import httpx
import hashlib
import base64
import filetype
import json
import os
import time
import logging
import asyncio
import io
import aiofiles
from datetime import datetime, timedelta
from jsonschema import Draft202012Validator, ValidationError
from PIL import Image, ImageEnhance, ImageFilter, ImageStat
from openai import AsyncOpenAI, BadRequestError

from app.database import get_session
from app.services.solve.normalizer_service import problem_normalizer_service
from app.models import (
    User, ChatSession, ChatMessage, UsageLog, OCRJob,
    Upload, Crop, OCRArtifact, OCRConfirmation,
    CanonicalProblem, CanonicalSolution, UserSavedSolution, Payment, PromoCode,
    OCRQuestion, OCRChoice, OCRFigure, OCRAuditEvent,
    VoiceSession, VoiceAudio, VoiceJob, VoiceArtifact, VoiceConfirmation,
    AdminNote, SystemConfig, UserQuotaOverride, SystemErrorEntry,
    School, Plan, Subscription, UsageLedger,
    RequestEvent, DeviceSignupLog, OcrCache,
    OcrExtractionCache, CreditHold, SolverOutputAttempt,
    PromptTemplateEntry, JsonSchemaEntry, PromptBinding,
    PromptTierEnum, PromptModeEnum, PromptRoleEnum
)
from app.services.plot_sampling import process_visuals
from app.services.rag import rag_service
from app.services.ocr.upload_service import upload_service
from app.services.ocr.crop_service import crop_service
from app.services.ocr.ocr_router_service import ocr_router_service
from app.services.ocr.audit_log_service import audit_log_service
from app.services.ocr.ocr_service import ocr_service
from app.services.ocr.vision_routing import (
    VisionInput,
    VisionOptions,
    VisionOcrProvider,
    VisionProviderAttempt,
    VisionExtractionResult,
    VisionRoutingConfig,
    build_provider_plan,
    get_openai_ocr_model,
)
from app.services.solve.canonicalization_service import canonicalization_service
from app.services.admin.analytics_service import record_request_event, _calc_cost
from app.services.whatsapp import whatsapp_service
from app.services.whatsapp.whatsapp_state import (
    mark_dedupe,
    get_ocr_state,
    clear_ocr_state,
    set_upload_meta,
    create_upload_id,
    get_upload_meta,
    log_whatsapp_event,
    get_whatsapp_events,
)
from app.services.prompt_registry_service import prompt_registry_service, PromptRegistryError
from app.services.tier_utils import get_user_effective_tier_slug
from app.services.mode_execution_service import mode_execution_service, ModeExecutionError
from app.services.llm import get_llm_manager, LLMProviderError
from app.services.whatsapp.whatsapp_state import get_redis
from app.services.whatsapp.whatsapp_send import send_whatsapp_logo
from app.services.whatsapp.step_delivery import handle_navigation
from app.worker import celery_app
from app.services.solve.cache_service import cache_service
from app.services.solve.freeform_solver import (
    FREEFORM_OUTPUT_MODE,
    FREEFORM_PROMPT_ID,
    FREEFORM_PROMPT_VERSION,
    archive_freeform_output,
    generate_freeform_solution,
    resolve_num_predict,
    resolve_timeout_seconds,
    should_use_freeform_output,
)
from app.services.token_policy import get_token_policy, serialize_token_policy
from app.config import get_settings
from app.services.school_import_service import normalize_country_code
from app.utils.perf_timer import perf_emit, perf_enabled



from app.auth import verify_password, create_access_token, Token, get_password_hash
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.bg_routers.voice_router import router as voice_router
from app.bg_routers.local_router import router as local_router
from app.bg_routers.snap_solve_pdf import router as snap_solve_pdf_router
from app.bg_routers.credits_router import router as credits_router

limiter = Limiter(key_func=get_remote_address)
api_router = APIRouter()

api_router.include_router(voice_router, tags=["voice"])
api_router.include_router(local_router, tags=["local_math"])
api_router.include_router(snap_solve_pdf_router, tags=["snap_solve_pdf"])
api_router.include_router(credits_router, tags=["credits"])

OCR_OPENAI_SYSTEM_PROMPT_ID = os.environ.get(
    "OCR_OPENAI_SYSTEM_PROMPT_ID",
    prompt_registry_service.OCR_EXTRACT_OPENAI_SYSTEM_PROMPT_ID,
)
OCR_OPENAI_SCHEMA_ID = os.environ.get(
    "OCR_OPENAI_SCHEMA_ID",
    prompt_registry_service.OCR_EXTRACT_OPENAI_SCHEMA_ID,
)


@api_router.get("/health/llm")
async def health_llm():
    """
    Check availability of the active LLM provider.
    """
    try:
        mgr = get_llm_manager()
        # Assume mgr has check_health or we try a simple generation?
        # Or check if URL reachable?
        # Simple check:
        # If manager exposes provider name.
        status = "ok"
        detail = "reachable"
        
        # We can try a ping if manager supports it, or just return basic info
        return {
            "status": status,
            "provider": mgr.provider if hasattr(mgr, "provider") else "unknown",
            "detail": detail
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# --- Helper Functions ---
def _resolve_runtime_tier_slug(user: Optional[User]) -> str:
    """
    Runtime tier source of truth:
    subscription -> plan.slug, with legacy fallback for migration safety.
    """
    return get_user_effective_tier_slug(user)


_TIER_ORDER = {"FREE": 0, "STANDARD": 1, "RESEARCH": 2}


def _normalize_tier_for_prompt_binding(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    if raw in {"research", "enterprise", "family", "family_standard"}:
        return "RESEARCH"
    if raw in {"standard", "student_standard", "pro", "premium"}:
        return "STANDARD"
    return "FREE"


def _clamp_requested_tier(requested_tier: Optional[str], entitled_tier_slug: str) -> Dict[str, str]:
    entitled = _normalize_tier_for_prompt_binding(entitled_tier_slug)
    requested = _normalize_tier_for_prompt_binding(requested_tier) if requested_tier else entitled
    effective = requested if _TIER_ORDER[requested] <= _TIER_ORDER[entitled] else entitled
    return {
        "tier_requested": requested,
        "tier_effective": effective,
    }


def _schema_object_for_validation(schema_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(schema_config, dict):
        return {}
    inner = schema_config.get("schema")
    if isinstance(inner, dict):
        return inner
    return schema_config


def _format_json_schema_errors(errors: List[ValidationError]) -> List[str]:
    formatted: List[str] = []
    for err in errors[:10]:
        path = "$"
        for part in err.absolute_path:
            if isinstance(part, int):
                path += f"[{part}]"
            else:
                path += f".{part}"
        formatted.append(f"{path}: {err.message}")
    return formatted


def _collect_stream_business_rule_errors(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    solution = payload.get("solution")
    if isinstance(solution, dict):
        status = str(solution.get("status") or "").strip().lower()
        steps = solution.get("steps")
        step_count = len(steps) if isinstance(steps, list) else 0
        if status == "ok" and step_count < 4:
            errors.append("business_rule: solution.status='ok' requires at least 4 steps.")
        if status == "needs_clarification" and step_count != 0:
            errors.append("business_rule: solution.status='needs_clarification' requires steps=[].")

    plot = payload.get("plot")
    if isinstance(plot, dict):
        plot_needed = plot.get("plot_needed")
        plot_specs = plot.get("plot_specs")
        if plot_needed is True:
            if not isinstance(plot_specs, list) or len(plot_specs) < 1:
                errors.append("business_rule: plot.plot_needed=true requires at least one plot spec.")
        if plot_needed is False and isinstance(plot_specs, list) and len(plot_specs) > 0:
            errors.append("business_rule: plot.plot_needed=false requires plot_specs to be empty or null.")

    verification = payload.get("verification")
    if isinstance(verification, dict):
        requested = verification.get("requested")
        checks = verification.get("checks")
        check_count = len(checks) if isinstance(checks, list) else 0
        if requested is True and check_count < 3:
            errors.append("business_rule: verification.requested=true requires at least 3 checks.")
        if requested is False and check_count > 0:
            errors.append("business_rule: verification.checks must be empty when verification.requested=false.")

    return errors


def _validate_stream_payload(payload: Dict[str, Any], schema_config: Optional[Dict[str, Any]]) -> List[str]:
    schema = _schema_object_for_validation(schema_config)
    if not schema:
        return ["schema_error: missing schema configuration for stream validation."]

    try:
        validator = Draft202012Validator(schema)
    except Exception as exc:
        return [f"schema_error: invalid JSON schema: {exc}"]

    schema_errors = _format_json_schema_errors(list(validator.iter_errors(payload)))
    return schema_errors + _collect_stream_business_rule_errors(payload)


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _preview_text(value: str, limit: int = 60) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2):]
    return f"{head}...{tail}"


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_freeform_max_attempts(
    *,
    effective_tier: str,
    trusted_context: Optional[Dict[str, Any]],
    is_make_it_right: bool,
) -> int:
    tier_norm = (effective_tier or "FREE").strip().upper()
    learning_mode = str((trusted_context or {}).get("learning_mode") or "").strip().lower()
    improve_requested = (
        is_make_it_right
        or learning_mode == "improve"
        or _is_truthy((trusted_context or {}).get("improve"))
        or _is_truthy((trusted_context or {}).get("improve_requested"))
    )
    if tier_norm == "RESEARCH" and improve_requested:
        default_attempts = int(os.environ.get("FREEFORM_MAX_ATTEMPTS_RESEARCH_IMPROVE", "3"))
    elif tier_norm == "STANDARD" and improve_requested:
        default_attempts = int(os.environ.get("FREEFORM_MAX_ATTEMPTS_STANDARD_IMPROVE", "2"))
    else:
        default_attempts = 1
    configured_cap = int(os.environ.get("FREEFORM_MAX_ATTEMPTS", str(default_attempts)))
    return max(1, min(3, min(default_attempts, configured_cap)))


def _build_schema_valid_stream_error_payload(
    *,
    problem_text: str,
    provider: str,
    model: str,
    tier: str,
    mode: str,
    prompt_id: Optional[str],
    validation_errors: List[str],
    schema_config: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    message = "Unable to generate a valid structured solution. Please try again."
    errors_top = [str(err) for err in (validation_errors or [])[:10]]
    evidence = [r"\text{validation failed}"]
    schema_obj = _schema_object_for_validation(schema_config)
    schema_version = "v1"
    response_type = "standard_solve_extreme"
    prompt_const = prompt_id or "solve_standard_extreme_detailed_v1"
    if isinstance(schema_obj, dict):
        schema_version = (
            (schema_obj.get("properties") or {}).get("schema_version", {}).get("const")
            or schema_version
        )
        response_type = (
            (schema_obj.get("properties") or {}).get("response_type", {}).get("const")
            or response_type
        )
        prompt_const = (
            (
                ((schema_obj.get("properties") or {}).get("meta", {}).get("properties") or {})
                .get("debug", {})
                .get("properties", {})
                .get("prompt_id", {})
            ).get("const")
            or prompt_const
        )
    return {
        "schema_version": schema_version,
        "response_type": response_type,
        "question_id": None,
        "tier": (tier or "STANDARD").upper(),
        "mode": (mode or "SOLVE").upper(),
        "language": {
            "response_language": "en",
            "english_only_enforced": True,
            "input_language_hint": "en",
        },
        "question": {
            "raw_text": (problem_text or "N/A").strip() or "N/A",
            "normalized_text": (problem_text or "N/A").strip() or "N/A",
            "assumptions": [],
            "constraints": [],
        },
        "solution": {
            "status": "error",
            "steps": [],
            "final_answer": {
                "value": message,
                "latex": r"\text{Unable to generate a valid structured solution. Please try again.}",
                "units": None,
            },
            "key_idea": None,
            "notes": ["Automatic schema repair failed."],
        },
        "plot": {
            "plot_needed": True,
            "plot_reason": "Validation fallback placeholder plot.",
            "plot_specs": [
                {
                    "plot_id": "fallback_plot",
                    "library": "plotly",
                    "spec": {
                        "data": [{"type": "scatter", "mode": "lines", "x": [0, 1], "y": [0, 0]}],
                        "layout": {"title": "Fallback plot"},
                    },
                    "attach_to_step_id": None,
                }
            ],
        },
        "verification": {
            "requested": True,
            "status": "error",
            "checks": [
                {
                    "check_id": "domain_check",
                    "verdict": "warn",
                    "message": "Domain check unavailable because schema validation failed.",
                    "related_step_id": None,
                    "evidence_math": evidence,
                },
                {
                    "check_id": "algebra_check",
                    "verdict": "warn",
                    "message": "Algebraic transformation check unavailable because schema validation failed.",
                    "related_step_id": None,
                    "evidence_math": evidence,
                },
                {
                    "check_id": "substitution_check",
                    "verdict": "warn",
                    "message": "Substitution check unavailable because schema validation failed.",
                    "related_step_id": None,
                    "evidence_math": evidence,
                },
            ],
        },
        "meta": {
            "provider": provider or "openai",
            "model": model or "unknown",
            "timestamps": {
                "started_at": None,
                "completed_at": datetime.utcnow().isoformat() + "Z",
            },
            "latency_ms": None,
            "fingerprint": {"normalized_sha256": ""},
            "cache": {"hit": False, "type": "none", "source_question_id": None},
            "debug": {
                "prompt_id": prompt_const,
                "schema_valid": False,
                "fallback_used": True,
                "validation_errors": errors_top,
            },
        },
    }


def _persist_freeform_attempt(
    *,
    session: Session,
    request_id: str,
    user_id: int,
    session_id: Optional[int],
    message_id: Optional[int],
    attempt_number: int,
    provider: str,
    model: str,
    prompt_id: str,
    prompt_version: str,
    raw_solution_text: str,
    extracted_answer: Optional[str],
    validation_json: Optional[Dict[str, Any]],
    latency_ms: Optional[int],
    archive_path: Optional[str],
    status: str,
    error_message: Optional[str] = None,
) -> SolverOutputAttempt:
    entry = SolverOutputAttempt(
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        output_format=FREEFORM_OUTPUT_MODE.lower(),
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        attempt_number=attempt_number,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        char_count=len(raw_solution_text or ""),
        extracted_answer=extracted_answer,
        raw_solution_text=raw_solution_text or "",
        validation_json=validation_json or {},
        archive_path=archive_path,
        status=status,
        error_message=error_message,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def _detect_image_kind(raw: bytes) -> Optional[str]:
    guessed = filetype.guess(raw)
    if not guessed:
        return None

    ext = (getattr(guessed, "extension", None) or "").lower()
    if ext in ("jpg", "jpeg"):
        return "jpeg"
    if ext == "png":
        return "png"
    if ext == "webp":
        return "webp"
    return None


def _normalize_whatsapp_number(value: str) -> str:
    if not value:
        return ""
    digits = re.sub(r"\\D+", "", value)
    return digits or value


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

        # Verification removed in v1.1
        # transformed["verification"] = {"methods": methods_v1}
        
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
    tier: Optional[str] = Field(None, description="Requested tier from frontend: free|standard|research")
    trusted_context: Optional[Dict[str, Any]] = None
    requested_mode: Optional[str] = "minimal"
    features_used: Optional[Dict[str, Any]] = None
    input_modality: Optional[str] = Field(None, description="one of 'text', 'ocr_image', 'ocr_pdf', 'voice'")
    token_policy: Optional[str] = Field(None, description="policy key applied for this request, for auditing")
    verification_level: Optional[str] = Field(None, description="expected verification rigor: light|moderate|strict")

from app.models import Plan, Subscription, UsageLedger
from app.services.subscription_service import subscription_service

class SolveResponse(BaseModel):
    session_id: int
    solution: Dict[str, Any]
    concepts: Optional[List[Any]] = []
    visuals: Optional[List[Any]] = []
    # verification removed in v1.1
    model_used: Optional[str] = None
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

    # Frontend handles math-likeness with mode/template data; keep backend permissive.


def _estimate_input_tokens(text: str) -> int:
    from app.utils.token_estimator import estimate_tokens
    return estimate_tokens(text or "")


VALID_MODALITIES = {"text", "ocr_image", "ocr_pdf", "voice"}


def _resolve_modality_flags(
    body: SolveRequest,
    features_used: Optional[Dict[str, Any]],
    has_image: bool,
    has_voice_flag: bool
) -> str:
    requested = body.input_modality
    if requested in VALID_MODALITIES:
        return requested

    ocr_used = bool(features_used.get("ocr_used")) if features_used else False
    voice_used = bool(features_used.get("voice_used")) if features_used else False
    has_ocr = bool(has_image or ocr_used)
    has_voice = bool(has_voice_flag or voice_used)

    if has_ocr and has_voice:
        raise HTTPException(status_code=400, detail="Mixed modality is not supported. Use OCR or voice, not both.")

    if has_voice:
        return "voice"

    if has_ocr:
        ocr_source = (features_used or {}).get("ocr_source")
        if ocr_source == "pdf":
            return "ocr_pdf"
        return "ocr_image"

    return "text"


def _get_verification_level(body: SolveRequest, modality: str) -> str:
    if body.verification_level:
        return body.verification_level
    if modality == "text":
        return "light"
    return "moderate"


def _extract_ocr_confidence(features_used: Optional[Dict[str, Any]]) -> Optional[float]:
    if not features_used:
        return None
    raw = features_used.get("ocr_confidence")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _enforce_ocr_confidence(confidence: Optional[float]) -> None:
    if confidence is not None and confidence < OCR_CONFIDENCE_THRESHOLD:
        raise HTTPException(
            status_code=400,
            detail=f"OCR confidence too low ({confidence:.2f}). Please re-run extraction."
        )


def _collect_ocr_metadata(features_used: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not features_used:
        return {}
    return {
        "ocr_engine": features_used.get("ocr_engine"),
        "ocr_source": features_used.get("ocr_source"),
        "ocr_warnings": features_used.get("ocr_warnings"),
        "ocr_confidence": _extract_ocr_confidence(features_used),
    }


def _ensure_voice_confirmed(features_used: Optional[Dict[str, Any]]) -> None:
    if features_used and features_used.get("voice_used") and not features_used.get("voice_confirmed"):
        raise HTTPException(status_code=400, detail="Voice confirmation required before solving.")


def _collect_voice_metadata(features_used: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not features_used:
        return {}
    return {
        "voice_confirmed": bool(features_used.get("voice_confirmed")),
        "voice_ambiguity_flags": features_used.get("voice_ambiguity_flags"),
        "voice_clarifier_question": features_used.get("voice_clarifier_question"),
        "voice_stt_provider": features_used.get("voice_stt_provider"),
        "voice_transcript_confidence": features_used.get("voice_transcript_confidence"),
    }


def _apply_modality_metadata(payload: Dict[str, Any], modality: str, ocr_metadata: Dict[str, Any], voice_metadata: Dict[str, Any], verification_level: str, token_policy_key: str) -> None:
    payload.update({
        "input_modality": modality,
        "verification_level": verification_level,
        "token_policy_key": token_policy_key,
        "ocr_engine": ocr_metadata.get("ocr_engine"),
        "ocr_source": ocr_metadata.get("ocr_source"),
        "ocr_warnings": ocr_metadata.get("ocr_warnings"),
        "ocr_confidence": ocr_metadata.get("ocr_confidence"),
        "voice_confirmed": voice_metadata.get("voice_confirmed"),
        "voice_ambiguity_flags": voice_metadata.get("voice_ambiguity_flags"),
        "voice_clarifier_question": voice_metadata.get("voice_clarifier_question"),
        "voice_stt_provider": voice_metadata.get("voice_stt_provider"),
        "voice_transcript_confidence": voice_metadata.get("voice_transcript_confidence"),
    })


def _log_trace_with_modality(payload: Dict[str, Any], modality: str, ocr_metadata: Dict[str, Any], voice_metadata: Dict[str, Any], verification_level: str, token_policy_key: str) -> None:
    _apply_modality_metadata(payload, modality, ocr_metadata, voice_metadata, verification_level, token_policy_key)
    log_solve_trace(payload)


def _record_event_with_modality(session: Session, payload: Dict[str, Any], modality: str, ocr_metadata: Dict[str, Any], voice_metadata: Dict[str, Any], verification_level: str, token_policy_key: str) -> None:
    _apply_modality_metadata(payload, modality, ocr_metadata, voice_metadata, verification_level, token_policy_key)
    record_request_event(session, payload)


def _enforce_input_token_limit(text: str, max_tokens: int, modality: str) -> None:
    estimated = _estimate_input_tokens(text)
    if estimated > max_tokens:
        raise HTTPException(
            status_code=413,
            detail=f"Input exceeds {modality} token limit ({estimated} > {max_tokens})"
        )

# _verification_passed removed in v1.1


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
    grade_level: Optional[str] = None
    difficulty: Optional[str] = None
    topics: Optional[List[str]] = None
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
    subscription_status: Optional[str] = None
    subscription_id: Optional[int] = None
    role: str
    questions_count: int
    scans_count: int
    last_active_at: str
    plan_id: Optional[int] = None
    plan_slug: Optional[str] = None
    plan_name: Optional[str] = None
    plan_credits_per_month: Optional[int] = None
    plan_price_monthly_cents: Optional[int] = None

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
    subscription_id: Optional[int] = None
    plan_id: Optional[int] = None
    plan_slug: Optional[str] = None
    plan_name: Optional[str] = None
    plan_credits_per_month: Optional[int] = None
    plan_price_monthly_cents: Optional[int] = None
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
    multipliers: Dict[str, Any]
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
    school_id: Optional[int] = None
    school_name: Optional[str] = None
    display_name: str

class SubscriptionResponse(BaseModel):
    plan: SubscriptionPlanInfo
    usage: SubscriptionUsage
    profile: SubscriptionProfile
    allow_detailed: bool
    allow_ocr: bool
    allow_voice: bool


class TokenPolicyResponse(BaseModel):
    ok: bool
    policy: Dict[str, Any]
    source: str

class SystemConfigEntry(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class SystemConfigUpdateRequest(BaseModel):
    entries: List[SystemConfigEntry]

class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    academic_level: Optional[str] = None
    timezone: Optional[str] = None
    profile_country: Optional[str] = None
    profile_province_state: Optional[str] = None
    grade_level: Optional[str] = None
    school_id: Optional[int] = None
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
    ocr_confidence: Optional[float] = None
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
    tokens_burned_24h: Optional[str] = ""

class QuotaOverrideRequest(BaseModel):
    user_id: int
    token_limit: Optional[int] = None
    ocr_concurrency: Optional[int] = None
    duration_hours: Optional[int] = None # null for permanent

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


class OcrV5Response(BaseModel):
    ok: bool = True
    extracted_text: str
    extracted_markdown: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    cache_hit: bool = False
    latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None

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
    school_name: Optional[str] = None
    
    # WhatsApp Integration
    whatsapp_secret: Optional[str] = None
    whatsapp_enabled: bool = True

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
    import secrets
    import string
    whatsapp_secret = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    
    new_user = User(
        email=form_data.email,
        full_name=form_data.full_name,
        password_hash=get_password_hash(form_data.password),
        academic_level=form_data.academic_level,
        whatsapp_secret=whatsapp_secret,
        whatsapp_enabled=True,
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
def _sync_subscription_balance(subscription: Subscription, plan: Plan, session: Session) -> float:
    expected_remaining = max(float(plan.credits_per_month) - float(subscription.credits_used_this_period or 0), 0.0)
    if subscription.credits_balance != expected_remaining:
        subscription.credits_balance = expected_remaining
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
    return expected_remaining


def build_subscription_response(
    user: User,
    subscription: Subscription,
    plan: Plan,
    credits_remaining: Optional[float] = None,
    school_name: Optional[str] = None,
) -> SubscriptionResponse:
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
    ocr_used = feature_usage.get("ocr_used", feature_usage.get("ocr", 0))
    voice_used = feature_usage.get("voice_used", feature_usage.get("voice", 0))
    usage_info = SubscriptionUsage(
        credits_used=subscription.credits_used_this_period,
        credits_remaining=credits_remaining if credits_remaining is not None else subscription.credits_balance,
        ocr_used=ocr_used,
        ocr_limit=features.get("ocr_monthly_cap", 100),
        voice_used=voice_used,
        voice_limit=features.get("voice_monthly_cap", 50)
    )

    profile_info = SubscriptionProfile(
        grade_level=user.grade_level,
        region_country=user.profile_country,
        region_state_province=user.profile_province_state,
        school_id=user.school_id,
        school_name=school_name if school_name is not None else (user.school.school_name if user.school else None),
        display_name=user.full_name
    )

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
    
    subscription = subscription_service.get_or_create_subscription(session, user)
    if not subscription:
        raise HTTPException(status_code=500, detail="Subscription not available")

    plan = session.get(Plan, subscription.plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="Plan not available for subscription")

    credits_remaining = _sync_subscription_balance(subscription, plan, session)
    school_name = None
    if user.school_id:
        school = session.get(School, user.school_id)
        school_name = school.school_name if school else None
    return build_subscription_response(user, subscription, plan, credits_remaining, school_name=school_name)


@api_router.get("/config/token-policy", response_model=TokenPolicyResponse)
async def get_token_policy_endpoint(session: Session = Depends(get_session)):
    policy = get_token_policy(session)
    return TokenPolicyResponse(ok=True, policy=serialize_token_policy(policy), source="system_config")



class LatexResponse(BaseModel):
    latex: str

# ------------------------------------------------------------------
# OCR Subsystem Endpoints
# ------------------------------------------------------------------

OCR_V5_MODEL = os.getenv("OCR_V5_MODEL") or os.environ.get("OPENAI_MODEL_DEFAULT")
OCR_V5_MAX_MB = int(os.getenv("OCR_V5_MAX_MB", "10"))

OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.65"))

OCR_V5_SYSTEM_PROMPT = (
    "You are an OCR extraction engine. Extract EXACT text and math as seen. "
    "Do not solve or explain. Return only JSON with fields extracted_text, "
    "extracted_markdown, questions."
)

OCR_V5_USER_PROMPT = (
    "Return STRICT JSON ONLY in this shape: "
    "{\"extracted_text\":\"...\",\"extracted_markdown\":\"...\",\"questions\":[\"...\"]}. "
    "Preserve math. If unreadable, say: "
    "\"Could not read text. Try cropping tighter or increasing zoom.\""
)

OCR_V5_SCHEMA = {
    "name": "ocr_v5_response",
    "schema": {
        "type": "object",
        "properties": {
            "extracted_text": {"type": "string"},
            "extracted_markdown": {"type": ["string", "null"]},
            "questions": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["extracted_text", "questions"],
        "additionalProperties": False
    }
}

# ------------------------------------------------------------------
# Snap & Solve v2 - Extract Questions
# ------------------------------------------------------------------

EXTRACT_MODEL = os.getenv("EXTRACT_MODEL") or os.environ.get("OPENAI_MODEL_DEFAULT")
EXTRACT_MAX_MB = int(os.getenv("EXTRACT_MAX_MB", "10"))
EXTRACT_CACHE_REV = os.getenv("EXTRACT_CACHE_REV", "2026-02-03-pix2txt-latex-normalize-v3")

EXTRACT_SYSTEM_PROMPT = (
    "You are a robust Math JSON OCR EXTRACTOR.\n\n"
    "Your task is to extract mathematical questions and expressions from the image and return them as JSON.\n"
    "Convert ALL mathematical formulas to perfect LaTeX format.\n\n"
    "ABSOLUTE RULES:\n"
    "- Use LaTeX for all math content where appropriate ($...$ for inline, $$...$$ for blocks).\n"
    "- Even if the image is a SMALL CROP or ONLY ONE LINE, extract it as a question if it contains math.\n"
    "- Match the provided JSON schema in text.format.\n"
    "- DO NOT explain or add commentary.\n"
    "- If the image is truly blank or completely unreadable, return:\n"
    "  {\"ok\": false, \"error\": \"Unreadable image\"}\n"
    "- Otherwise, TRY YOUR BEST to extract any visible mathematical text."
)

EXTRACT_USER_PROMPT = (
    "Extract all math questions from the image. If only one line is present, treat it as a single question.\n"
    "Ensure all math is in perfect LaTeX. Return ONLY valid JSON matching the schema exactly.\n\n"
    "If unreadable, return: {\"ok\": false, \"error\": \"Unreadable\"}"
)

EXTRACT_SCHEMA = {
    "name": "extract_questions_v1",
    "schema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ExtractQuestionsResponse",
        "type": "object",
        "additionalProperties": False,
        "required": ["ok", "error", "is_math_page", "notes", "questions"],
        "properties": {
            "ok": {"type": "boolean"},
            "error": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["code", "message"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                ],
            },
            "is_math_page": {"type": "boolean"},
            "notes": {"type": "array", "items": {"type": "string"}},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "page", "text", "latex", "type"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "page": {"type": "integer", "minimum": 0},
                        "type": {
                            "type": "string",
                            "enum": [
                                "word_problem",
                                "equation",
                                "multiple_choice",
                                "graph",
                                "table",
                                "geometry",
                                "other",
                            ],
                        },
                        "text": {"type": "string", "minLength": 1},
                        "latex": {
                            "anyOf": [
                                {"type": "null"},
                                {"type": "string", "minLength": 1},
                            ],
                        },
                        "confidence": {
                            "anyOf": [
                                {"type": "null"},
                                {"type": "number", "minimum": 0, "maximum": 1},
                            ],
                        },
                    },
                },
            },
        },
    },
}


EXTRACT_SCHEMA_RUNTIME = EXTRACT_SCHEMA["schema"]
EXTRACT_SCHEMA_VALIDATOR = Draft202012Validator(EXTRACT_SCHEMA_RUNTIME)
INVALID_EXTRACT_PAYLOAD = {
    "ok": False,
    "error": {"code": "INVALID_SCHEMA", "message": "invalid schema from model"},
    "is_math_page": False,
    "notes": [],
    "questions": [],
}

CODE_FENCE_PATTERN = re.compile(r"```(?:[^\n]*\n)?([\s\S]*?)```", re.MULTILINE)


def _truncate_text(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...(truncated)"


def _serialize_response_for_log(response: Any) -> str:
    try:
        dumped = json.dumps(response, default=str)
    except Exception:
        dumped = repr(response)
    return _truncate_text(dumped)


def _normalize_response_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        for element in value:
            candidate = _normalize_response_text(element)
            if candidate:
                return candidate
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if isinstance(value, dict):
        for key in ("text", "output_text"):
            candidate = _normalize_response_text(value.get(key))
            if candidate:
                return candidate
        for key in ("content", "items"):
            contents = value.get(key)
            if isinstance(contents, (list, tuple)):
                for element in contents:
                    candidate = _normalize_response_text(element)
                    if candidate:
                        return candidate
        for val in value.values():
            candidate = _normalize_response_text(val)
            if candidate:
                return candidate
        return None
    text_attr = getattr(value, "text", None)
    if text_attr:
        return _normalize_response_text(text_attr)
    output_text = getattr(value, "output_text", None)
    if output_text:
        return _normalize_response_text(output_text)
    contents = getattr(value, "content", None) or getattr(value, "items", None)
    if isinstance(contents, (list, tuple)):
        for element in contents:
            candidate = _normalize_response_text(element)
            if candidate:
                return candidate
    return None


def _extract_openai_text(response: Any) -> str:
    if not response:
        return ""
    output_text = None
    if isinstance(response, dict):
        output_text = response.get("output_text")
    else:
        output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    response_text = _extract_responses_message_text(response)
    if response_text:
        return response_text
    choices = getattr(response, "choices", None)
    if isinstance(choices, (list, tuple)) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message")
        else:
            message = getattr(choice, "message", None)
        contents = None
        if isinstance(message, dict):
            contents = message.get("content")
        else:
            contents = getattr(message, "content", None)
        if contents:
            for entry in contents:
                candidate = _normalize_response_text(entry)
                if candidate:
                    return candidate
    logging.warning(
        "OpenAI extract response missing text; type=%s payload=%s",
        type(response).__name__,
        _serialize_response_for_log(response),
    )
    return ""


def _extract_responses_message_text(response: Any) -> str:
    output = getattr(response, "output", None) or getattr(response, "result", None)
    if not isinstance(output, (list, tuple)):
        return ""
    chunks: List[str] = []
    for item in output:
        item_type = getattr(item, "type", None) if not isinstance(item, dict) else item.get("type")
        if item_type and item_type != "message":
            continue
        content_list = getattr(item, "content", None) if not isinstance(item, dict) else item.get("content")
        if not isinstance(content_list, (list, tuple)):
            continue
        for part in content_list:
            if isinstance(part, dict):
                text_value = part.get("text")
            else:
                text_value = getattr(part, "text", None)
            if isinstance(text_value, str) and text_value:
                chunks.append(text_value)
    if chunks:
        return "".join(chunks).strip()
    fallback_text = getattr(response, "output_text", None)
    if isinstance(fallback_text, str):
        return fallback_text
    return ""


def _sanitize_trimmed_keys(value: Any) -> Tuple[Any, bool]:
    if isinstance(value, dict):
        changed = False
        out: Dict[str, Any] = {}
        for key, val in value.items():
            new_key = key.strip() if isinstance(key, str) else key
            cleaned_val, child_changed = _sanitize_trimmed_keys(val)
            if new_key != key:
                changed = True
            if child_changed:
                changed = True
            out[new_key] = cleaned_val
        return out, changed
    if isinstance(value, list):
        changed = False
        out_list = []
        for item in value:
            cleaned_item, child_changed = _sanitize_trimmed_keys(item)
            if child_changed:
                changed = True
            out_list.append(cleaned_item)
        return out_list, changed
    return value, False


_CJK_CHAR_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF]")
_CJK_RUN_RE = re.compile(r"(?:(?<=\s)|^)([\u3400-\u4DBF\u4E00-\u9FFF]{1,3})(?=(?:\s|[0-9A-Za-z\\(\\[\\{]|$))")
_LATEX_STYLE_MACRO_RE = re.compile(r"\\(boldsymbol|mathbf|mathbb)\s*\{([^{}]+)\}")


def _strip_likely_cjk_ocr_noise(text: str) -> str:
    """
    Remove short accidental CJK runs from predominantly Latin OCR outputs.
    Keeps genuine CJK content intact by only applying when the text is mostly Latin.
    """
    if not text:
        return text
    cjk_count = len(_CJK_CHAR_RE.findall(text))
    if cjk_count == 0:
        return text
    latin_count = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    digit_count = sum(1 for ch in text if ch.isdigit())
    if cjk_count <= 3 and digit_count >= 2:
        cleaned = _CJK_RUN_RE.sub("", text)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return cleaned.strip()
    if (latin_count + digit_count) < 16:
        return text
    if cjk_count > max(6, (latin_count + digit_count) // 6):
        return text
    cleaned = _CJK_RUN_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _repair_root_notation_ocr_noise(text: str) -> str:
    s = text
    # Common Pix2Text corruption for indexed roots: "oot4 \of{...}" / "root4 of {...}".
    s = re.sub(r"(?i)\b(?:root|oot)\s*(\d+)\s*\\of\s*\{", r"\\sqrt[\1]{", s)
    s = re.sub(r"(?i)\b(?:root|oot)\s*(\d+)\s*of\s*\{", r"\\sqrt[\1]{", s)
    s = re.sub(r"(?i)\\root\s*(\d+)\s*\\of\s*\{", r"\\sqrt[\1]{", s)
    s = re.sub(r"(?i)(\\sqrt(?:\[[^\]]+\])?)\s*\\of\s*\{", r"\1{", s)
    # Last-resort cleanup for stray "\of{...}" fragments.
    s = re.sub(r"\\of\s*\{", "{", s)
    return s


def _unwrap_latex_style_macros(text: str) -> str:
    s = text
    for _ in range(4):
        replaced = False

        def _replace(match: re.Match[str]) -> str:
            nonlocal replaced
            replaced = True
            macro = match.group(1)
            inner = (match.group(2) or "").strip()
            if macro == "mathbb" and inner in {"R", "N", "Z", "Q", "C"}:
                return f"\\mathbb{{{inner}}}"
            return inner

        next_s = _LATEX_STYLE_MACRO_RE.sub(_replace, s)
        s = next_s
        if not replaced:
            break
    return s


def _normalize_math_ocr_text(text: str) -> str:
    if not text:
        return ""
    s = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("âˆ’", "-")
        .replace("−", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("÷", "\\div ")
        .replace("×", "\\times ")
        .replace("∗", "*")
    )
    s = _repair_root_notation_ocr_noise(s)
    s = _unwrap_latex_style_macros(s)
    s = re.sub(r"\\bf\s+([A-Za-z0-9])", r"\\mathbf{\1}", s)
    s = re.sub(r"\\\s+([A-Za-z])", r"\\\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _looks_like_latex_math(text: str) -> bool:
    if not text:
        return False
    if any(token in text for token in ("\\[", "\\]", "\\(", "\\)", "$$", "$")):
        return True
    return bool(re.search(r"\\[A-Za-z]+|[=+\-*/^_]", text))


def _normalize_extract_payload_shape(payload: Dict[str, Any], page_hint: int = 0) -> Dict[str, Any]:
    """
    Normalize legacy extract payload variants into ExtractQuestionsResponse schema shape.
    """
    out = dict(payload or {})
    questions = out.get("questions")
    if not isinstance(questions, list):
        questions = []
    normalized_questions = []
    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id") or f"p{page_hint}-q{idx+1}")
        qtype = str(q.get("type") or "other")
        if qtype not in {"word_problem", "equation", "multiple_choice", "graph", "table", "geometry", "other"}:
            qtype = "other"
        text = _strip_likely_cjk_ocr_noise(str(q.get("text") or "").strip())
        text = _normalize_math_ocr_text(text)
        if not text:
            continue
        page = q.get("page")
        if not isinstance(page, int) or page < 0:
            page = page_hint
        latex = q.get("latex")
        if isinstance(latex, str):
            latex = _normalize_math_ocr_text(_strip_likely_cjk_ocr_noise(latex.strip())) or None
        else:
            latex = None
        if latex is None and _looks_like_latex_math(text):
            latex = text
        confidence = q.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence = max(0.0, min(1.0, float(confidence)))
        else:
            confidence = None
        normalized_questions.append(
            {
                "id": qid,
                "page": page,
                "text": text,
                "latex": latex,
                "type": qtype,
                "confidence": confidence,
            }
        )
    out["questions"] = normalized_questions
    out["is_math_page"] = bool(out.get("is_math_page", bool(normalized_questions)))
    notes = out.get("notes")
    out["notes"] = notes if isinstance(notes, list) else ([] if notes is None else [str(notes)])
    error_obj = out.get("error")
    if isinstance(error_obj, str):
        out["error"] = {"code": "EXTRACT_ERROR", "message": error_obj}
    elif isinstance(error_obj, dict):
        code = str(error_obj.get("code") or "EXTRACT_ERROR")
        msg = str(error_obj.get("message") or "Extraction error")
        out["error"] = {"code": code, "message": msg}
    else:
        out["error"] = None
    out["ok"] = bool(out.get("ok", True))
    return out


def _extract_error_message(error_value: Any) -> Optional[str]:
    if error_value is None:
        return None
    if isinstance(error_value, str):
        return error_value
    if isinstance(error_value, dict):
        message = error_value.get("message")
        if isinstance(message, str):
            return message
    return str(error_value)


def _validate_extract_payload(payload: Dict[str, Any], page_hint: int = 0) -> Dict[str, Any]:
    sanitized_payload, keys_changed = _sanitize_trimmed_keys(payload)
    normalized_payload = _normalize_extract_payload_shape(sanitized_payload, page_hint=page_hint)
    if keys_changed:
        notes = normalized_payload.get("notes")
        if not isinstance(notes, list):
            notes = []
        notes.append("Sanitized whitespace in JSON keys before validation.")
        normalized_payload["notes"] = notes
    errors = list(EXTRACT_SCHEMA_VALIDATOR.iter_errors(normalized_payload))
    if not errors:
        return normalized_payload
    details = "; ".join(
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in errors[:5]
    )
    logging.warning("Extract schema validation failed: %s", details)
    return INVALID_EXTRACT_PAYLOAD


def _clean_content_for_json(content: str) -> str:
    return CODE_FENCE_PATTERN.sub(r"\1", content)


def _try_recover_json(content: str) -> Optional[str]:
    cleaned = _clean_content_for_json(content)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return None


class ExtractQuestionItem(BaseModel):
    id: str
    page: int
    text: str
    latex: Optional[str] = None
    type: str
    confidence: Optional[float] = None


class ExtractErrorItem(BaseModel):
    code: str
    message: str


class ExtractTelemetry(BaseModel):
    request_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    latency_ms_openai: Optional[int] = None
    latency_ms_total: Optional[int] = None


class ExtractQuestionsResponse(BaseModel):
    ok: bool
    is_math_page: bool
    notes: List[str]
    questions: List[ExtractQuestionItem]
    error: Optional[ExtractErrorItem] = None
    ocr_provider_used: Optional[str] = None
    ocr_model_used: Optional[str] = None
    ocr_fallback_attempts: Optional[List[Dict[str, Any]]] = None


class SolveBatchItem(BaseModel):
    question_id: str
    text: str
    requested_mode: Optional[str] = "minimal"
    requires_figure: Optional[bool] = False
    figure_image_base64: Optional[str] = None


class SolveBatchRequest(BaseModel):
    items: List[SolveBatchItem]
    features_used: Optional[Dict[str, Any]] = None
    input_modality: Optional[str] = None
    verification_level: Optional[str] = None
    token_policy: Optional[str] = None
    image_url: Optional[str] = None
    artifact_id: Optional[int] = None
    has_voice: Optional[bool] = False


class SolveBatchItemResult(BaseModel):
    question_id: str
    ok: bool
    solve_response_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    telemetry: Optional[Dict[str, Any]] = None
    credits_reserved: Optional[float] = None
    credits_final: Optional[float] = None
    credits_refunded: Optional[float] = None


class SolveBatchResponse(BaseModel):
    ok: bool
    results: List[SolveBatchItemResult]


TOKENS_PER_CREDIT = float(os.getenv("TOKENS_PER_CREDIT", "2000"))
SOLVE_BATCH_CONCURRENCY = int(os.getenv("SOLVE_BATCH_CONCURRENCY", "3"))


def _estimate_credits(
    plan: Plan,
    requested_mode: str,
    text: str,
    has_ocr: bool,
    has_voice: bool
) -> float:
    mode_key = "detailed" if requested_mode == "detailed" else "concise"
    base_cost = subscription_service.calculate_cost(plan, mode_key, has_ocr, has_voice)
    token_est = max(len(text) / 4.0, 1.0)
    extra_cost = token_est / TOKENS_PER_CREDIT
    return float(base_cost + extra_cost)


async def _call_extract_questions(
    session: Session,
    image_bytes: bytes, 
    max_output_tokens: int, 
    engine_choice: str = "auto",
    crop_meta: Optional[Dict[str, Any]] = None,
    debug: bool = False
) -> Dict[str, Any]:
    def _load_openai_ocr_assets() -> Tuple[str, Dict[str, Any]]:
        system_entry = prompt_registry_service.get_active_prompt(session, OCR_OPENAI_SYSTEM_PROMPT_ID)
        schema_entry = prompt_registry_service.get_active_schema(session, OCR_OPENAI_SCHEMA_ID)
        if not system_entry or not schema_entry:
            raise PromptRegistryError(
                "Missing OpenAI OCR prompt/schema in registry. "
                f"Expected prompt_id={OCR_OPENAI_SYSTEM_PROMPT_ID} schema_id={OCR_OPENAI_SCHEMA_ID}"
            )
        return system_entry.content, schema_entry.content

    def _normalize_openai_ocr_payload(raw_payload: Dict[str, Any], model: str) -> Dict[str, Any]:
        warnings = raw_payload.get("warnings") if isinstance(raw_payload.get("warnings"), list) else []
        questions = raw_payload.get("questions") if isinstance(raw_payload.get("questions"), list) else []
        normalized_questions: List[Dict[str, Any]] = []
        for idx, item in enumerate(questions):
            if not isinstance(item, dict):
                continue
            qid = str(item.get("question_id") or f"p{page_num}-q{idx+1}")
            page = item.get("page_index")
            if not isinstance(page, int) or page < 0:
                page = page_num
            q_text = str(item.get("question_text") or "").strip()
            q_latex = item.get("question_latex")
            if not q_text and isinstance(q_latex, str):
                q_text = q_latex.strip()
            if not q_text:
                continue
            choices = item.get("answer_choices") if isinstance(item.get("answer_choices"), list) else []
            q_type = "multiple_choice" if len(choices) > 0 else "other"
            conf = item.get("confidence")
            if not isinstance(conf, (int, float)):
                conf = None
            normalized_questions.append(
                {
                    "id": qid,
                    "page": page,
                    "text": q_text,
                    "latex": str(q_latex).strip() if isinstance(q_latex, str) and q_latex.strip() else None,
                    "type": q_type,
                    "confidence": conf,
                }
            )
        notes = [str(w) for w in warnings if isinstance(w, str)]
        if not normalized_questions and not notes:
            notes = ["No math questions detected."]
        return {
            "ok": True,
            "error": None,
            "is_math_page": bool(normalized_questions),
            "notes": notes,
            "questions": normalized_questions,
        }

    def _looks_like_garbled_pix2text(markdown: str) -> bool:
        text = (markdown or "").strip()
        if not text:
            return True
        if len(text) < 16:
            return True
        if re.search(r"(?i)\boot\s*\d+\s*\\?of\s*\{", text):
            return True
        if text.count("\\of{") >= 1:
            return True
        if text.count("\\boldsymbol{") >= 3:
            return True
        brace_pairs = text.count("{}")
        slash_count = text.count("\\")
        amp_count = text.count("&")
        alpha_count = sum(1 for ch in text if ch.isalpha())
        if brace_pairs >= 8:
            return True
        if slash_count >= 24 and alpha_count < max(20, len(text) // 12):
            return True
        if amp_count >= 10 and alpha_count < max(20, len(text) // 14):
            return True
        return False

    def _pix2text_extract_payload(
        markdown: str,
        confidence: float,
        page_number: int,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "payload": {
                "ok": True,
                "error": None,
                "is_math_page": True,
                "notes": notes or ["Extracted using Pix2Text (Local)"],
                "questions": [{
                    "id": f"p{page_number}-q1",
                    "page": page_number,
                    "text": markdown,
                    "latex": markdown if ("\\" in markdown or "$" in markdown) else None,
                    "confidence": confidence,
                    "type": "equation",
                }]
            },
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0
        }

    def _is_incomplete(resp: Any) -> bool:
        status = getattr(resp, "status", None)
        if status and status != "completed":
            return True
        details = getattr(resp, "incomplete_details", None)
        reason = getattr(details, "reason", None) if details else None
        return reason == "max_output_tokens"

    page_num = 0
    if isinstance(crop_meta, dict):
        page_raw = crop_meta.get("page_number")
        if isinstance(page_raw, int) and page_raw >= 0:
            page_num = page_raw

    class Pix2TextProvider(VisionOcrProvider):
        name = "pix2txt"
        supports_pdf = True
        supports_image = True

        async def extract(self, vision_input: VisionInput, options: VisionOptions) -> VisionExtractionResult:
            import tempfile

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(vision_input.images[0])
                    tmp_path = f.name
                result = ocr_service.process_job(
                    tmp_path,
                    engine_name="local",
                    crop_meta=options.crop_meta,
                    debug=options.debug,
                )
                markdown = str(result.get("markdown", "") or "").strip()
                if not markdown:
                    raise RuntimeError("empty_extraction")
                confidence = float(result.get("confidence", 0.8) or 0.8)
                payload_bundle = _pix2text_extract_payload(markdown, confidence, page_num)
                return VisionExtractionResult(
                    provider="pix2txt",
                    model="pix2text-local",
                    extracted_text=markdown,
                    payload=payload_bundle["payload"],
                    blocks=payload_bundle["payload"].get("questions") or [],
                    confidence=confidence,
                    diagnostics={"telemetry": result.get("telemetry")},
                    token_usage={"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0},
                )
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    class OpenAIVisionProvider(VisionOcrProvider):
        name = "openai"
        supports_pdf = True
        supports_image = True

        async def extract(self, vision_input: VisionInput, options: VisionOptions) -> VisionExtractionResult:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
            if len(vision_input.images) > 4:
                raise RuntimeError("unsupported_too_many_images")

            model = get_openai_ocr_model()
            client = AsyncOpenAI(api_key=api_key)
            b64 = base64.b64encode(vision_input.images[0]).decode("utf-8")
            system_prompt, openai_schema = _load_openai_ocr_assets()
            validator = Draft202012Validator(openai_schema)
            user_prompt = "Extract math content from this input image. Return JSON only."

            async def _responses_call(max_tokens: int, repair: bool = False):
                prompt_text = user_prompt
                if repair:
                    prompt_text = "Return ONLY valid JSON that matches schema; no extra text."
                return await client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                        {"role": "user", "content": [
                            {"type": "input_text", "text": prompt_text},
                            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"},
                        ]},
                    ],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": OCR_OPENAI_SCHEMA_ID,
                            "schema": openai_schema,
                            "strict": True,
                        }
                    },
                    reasoning={"effort": "low"},
                    max_output_tokens=max_tokens,
                    timeout=float(os.environ.get("OPENAI_OCR_TIMEOUT_SECONDS", "60")),
                )

            response = await _responses_call(options.max_output_tokens)
            content = _extract_openai_text(response)
            if _is_incomplete(response) or not content.strip():
                response = await _responses_call(int(options.max_output_tokens * 2), repair=True)
                content = _extract_openai_text(response)
            if not content.strip():
                raise RuntimeError("empty_extraction")

            try:
                parsed = _parse_json_response(content)
            except Exception:
                response = await _responses_call(int(options.max_output_tokens * 2), repair=True)
                content = _extract_openai_text(response)
                parsed = _parse_json_response(content)
            errors = list(validator.iter_errors(parsed))
            if errors:
                response = await _responses_call(int(options.max_output_tokens * 2), repair=True)
                content = _extract_openai_text(response)
                parsed = _parse_json_response(content)
                errors = list(validator.iter_errors(parsed))
                if errors:
                    raise RuntimeError("schema_validation_failed")

            usage = getattr(response, "usage", None)
            payload = _validate_extract_payload(_normalize_openai_ocr_payload(parsed, model), page_hint=page_num)
            input_tokens = None
            output_tokens = None
            cached_tokens = None
            usage_payload = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
            if usage:
                input_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
                if hasattr(usage, "input_token_details"):
                    cached_tokens = getattr(usage.input_token_details, "cached_tokens", None)
                elif hasattr(usage, "prompt_tokens_details"):
                    cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", None)
            if usage_payload.get("tokens_in") is not None:
                input_tokens = usage_payload.get("tokens_in")
            if usage_payload.get("tokens_out") is not None:
                output_tokens = usage_payload.get("tokens_out")
            return VisionExtractionResult(
                provider="openai",
                model=model,
                extracted_text="\n".join((q.get("text") or "") for q in (payload.get("questions") or [])).strip(),
                payload=payload,
                blocks=payload.get("questions") or [],
                token_usage={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_tokens": cached_tokens,
                },
            )

    providers: Dict[str, VisionOcrProvider] = {
        "pix2txt": Pix2TextProvider(),
        "openai": OpenAIVisionProvider(),
    }
    routing_cfg = VisionRoutingConfig.from_env()
    plan = build_provider_plan(engine_choice, routing_cfg)
    if not plan:
        raise RuntimeError("No OCR providers enabled")

    attempts: List[VisionProviderAttempt] = []
    last_error: Optional[str] = None
    for idx, provider_name in enumerate(plan):
        provider = providers.get(provider_name)
        if not provider:
            continue
        start_attempt = time.perf_counter()
        request_id = (crop_meta or {}).get("request_id") if isinstance(crop_meta, dict) else None
        try:
            result = await provider.extract(
                VisionInput(images=[image_bytes], request_id=request_id, source=(crop_meta or {}).get("source")),
                VisionOptions(max_output_tokens=max_output_tokens, crop_meta=crop_meta, debug=debug),
            )
            duration_ms = int((time.perf_counter() - start_attempt) * 1000)
            logging.info(
                "ocr_attempt request_id=%s provider=%s model=%s duration_ms=%s validation_passed=%s fail_reason=%s",
                request_id,
                provider_name,
                result.model,
                duration_ms,
                True,
                None,
            )
            attempts.append(
                VisionProviderAttempt(
                    provider=provider_name,
                    model=result.model,
                    duration_ms=duration_ms,
                    success=True,
                )
            )
            token_usage = result.token_usage or {}
            return {
                "payload": result.payload,
                "input_tokens": token_usage.get("input_tokens"),
                "output_tokens": token_usage.get("output_tokens"),
                "cached_tokens": token_usage.get("cached_tokens"),
                "ocr_provider_used": result.provider,
                "ocr_model_used": result.model,
                "ocr_fallback_attempts": [a.__dict__ for a in attempts],
            }
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_attempt) * 1000)
            reason = str(exc)
            last_error = reason
            attempts.append(
                VisionProviderAttempt(
                    provider=provider_name,
                    model=(get_openai_ocr_model() if provider_name == "openai" else provider_name),
                    duration_ms=duration_ms,
                    success=False,
                    reason=reason,
                )
            )
            logging.warning(
                "ocr_attempt request_id=%s provider=%s model=%s duration_ms=%s validation_passed=%s fail_reason=%s",
                request_id,
                provider_name,
                (get_openai_ocr_model() if provider_name == "openai" else provider_name),
                duration_ms,
                False,
                reason[:200],
            )
            if idx == len(plan) - 1:
                break

    raise RuntimeError(last_error or "All OCR providers failed")


def _parse_json_response(content: str) -> Dict[str, Any]:
    normalized = content.strip()
    if not normalized:
        raise ValueError("Empty content received from extract model")
    try:
        logging.debug("Attempting to parse OCR JSON payload: %s", normalized)
        return json.loads(normalized)
    except json.JSONDecodeError as exc:
        logging.exception("extract_questions failed while parsing OCR json", exc_info=True)
        candidate = _try_recover_json(normalized)
        if candidate:
            try:
                logging.warning("Retrying parse on substring: %s", _truncate_text(candidate, limit=200))
                return json.loads(candidate)
            except json.JSONDecodeError:
                logging.warning("Best-effort JSON parsing failed; substring=%s", _truncate_text(candidate, limit=200))
        snippet = _truncate_text(normalized, limit=400)
        raise ValueError(f"Invalid JSON response from Extract engine: {snippet}") from exc


def _normalize_crop_ratios(
    crop_x: Optional[float],
    crop_y: Optional[float],
    crop_w: Optional[float],
    crop_h: Optional[float],
    preview_w: Optional[float],
    preview_h: Optional[float],
    image_w: int,
    image_h: int
) -> Optional[Dict[str, float]]:
    if crop_x is None or crop_y is None or crop_w is None or crop_h is None:
        return None
    if any(value <= 0 for value in (crop_w, crop_h)):
        return None
    if max(crop_x, crop_y, crop_w, crop_h) <= 1:
        return {
            "x": float(crop_x),
            "y": float(crop_y),
            "w": float(crop_w),
            "h": float(crop_h),
        }
    base_w = preview_w or image_w
    base_h = preview_h or image_h
    if not base_w or not base_h:
        return None
    return {
        "x": float(crop_x) / float(base_w),
        "y": float(crop_y) / float(base_h),
        "w": float(crop_w) / float(base_w),
        "h": float(crop_h) / float(base_h),
    }


def _ratios_to_pixels(crop: Dict[str, float], width: int, height: int) -> tuple[int, int, int, int]:
    x = int(round(crop["x"] * width))
    y = int(round(crop["y"] * height))
    w = int(round(crop["w"] * width))
    h = int(round(crop["h"] * height))
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return x, y, w, h


def _crop_quality_metrics(img: Image.Image) -> Dict[str, float]:
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    mean = float(stat.mean[0]) if stat.mean else 0.0
    stddev = float(stat.stddev[0]) if stat.stddev else 0.0
    histogram = gray.histogram()
    total = float(sum(histogram)) or 1.0
    white = float(sum(histogram[245:256]))
    white_pct = white / total
    return {
        "mean": mean,
        "stddev": stddev,
        "white_pct": white_pct,
        "width": float(gray.width),
        "height": float(gray.height),
    }


def _is_low_text_crop(metrics: Dict[str, float]) -> bool:
    if metrics["white_pct"] >= 0.98:
        return True
    if metrics["stddev"] <= 6.0:
        return True
    return False


def _encode_image_jpeg(img: Image.Image, quality: int = 85) -> bytes:
    output = io.BytesIO()
    rgb = img.convert("RGB")
    rgb.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()


def _should_cache_extract_result(result: Dict[str, Any]) -> bool:
    if not result.get("ok", True):
        return False
    questions = result.get("questions") or []
    return len(questions) > 0


async def _call_ocr_v5(image_bytes: bytes, max_output_tokens: int) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    client = AsyncOpenAI(api_key=api_key)
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    if "gpt-5" in OCR_V5_MODEL.lower():
        response = await client.responses.create(
            model=OCR_V5_MODEL,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": OCR_V5_SYSTEM_PROMPT}]},
                {"role": "user", "content": [
                    {"type": "input_text", "text": OCR_V5_USER_PROMPT},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"}
                ]}
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "json_schema": OCR_V5_SCHEMA
                }
            },
            max_output_tokens=max_output_tokens
        )
        content = None
        if getattr(response, "output", None):
            for item in response.output:
                if getattr(item, "content", None):
                    content = item.content[0].text
                    break
        if not content:
            raise ValueError("Empty OCR response")
        usage = getattr(response, "usage", None)
        cached_tokens = None
        if usage and hasattr(usage, "input_token_details"):
            cached_tokens = getattr(usage.input_token_details, "cached_tokens", None)
        return {
            "payload": _parse_json_response(content),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "cached_tokens": cached_tokens
        }

    response = await client.chat.completions.create(
        model=OCR_V5_MODEL,
        messages=[
            {"role": "system", "content": OCR_V5_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": OCR_V5_USER_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}}
            ]}
        ],
        response_format={"type": "json_schema", "json_schema": OCR_V5_SCHEMA},
        max_completion_tokens=max_output_tokens
    )
    content = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    cached_tokens = None
    if usage and hasattr(usage, "prompt_tokens_details"):
        cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", None)
    return {
        "payload": _parse_json_response(content),
        "input_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "output_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "cached_tokens": cached_tokens
    }


@api_router.post("/ocr_v5", response_model=OcrV5Response)
@limiter.limit("10/minute")
async def ocr_v5(
    request: Request,
    file: UploadFile = File(...),
    page_number: int = Form(1),
    file_hash: Optional[str] = Form(None),
    crop_x: Optional[int] = Form(None),
    crop_y: Optional[int] = Form(None),
    crop_w: Optional[int] = Form(None),
    crop_h: Optional[int] = Form(None),
    session: Session = Depends(get_session)
):
    if not file:
        raise HTTPException(status_code=400, detail="File is required")
    token_policy = get_token_policy(session)

    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set on server")

    raw = await file.read()
    if len(raw) > OCR_V5_MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds size limit")

    if raw.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="PDF uploads are not accepted")
    image_kind = _detect_image_kind(raw)
    content_type = file.content_type or ""
    if not content_type.startswith("image/") and image_kind not in ("jpeg", "png", "webp"):
        raise HTTPException(status_code=415, detail="Only image uploads are accepted")
    if image_kind not in ("jpeg", "png", "webp"):
        raise HTTPException(status_code=415, detail="Unsupported image type")

    crop_meta = {
        "page_number": page_number,
        "file_hash": file_hash,
        "crop_x": crop_x,
        "crop_y": crop_y,
        "crop_w": crop_w,
        "crop_h": crop_h,
    }
    hash_input = raw + json.dumps(crop_meta, sort_keys=True).encode("utf-8")
    cache_key = hashlib.sha256(hash_input).hexdigest()

    cached = session.exec(select(OcrCache).where(OcrCache.cache_key == cache_key)).first()
    if cached:
        cached.hit_count += 1
        cached.last_hit_at = datetime.utcnow()
        session.add(cached)
        session.commit()
        return OcrV5Response(
            extracted_text=cached.extracted_text,
            extracted_markdown=cached.extracted_markdown,
            questions=cached.questions or [],
            cache_hit=True,
            latency_ms=0
        )

    start = time.time()
    try:
        if token_policy.ocr_v5_output_max <= 0:
            raise HTTPException(status_code=500, detail="OCR token policy misconfigured")
        ocr_data = await _call_ocr_v5(raw, token_policy.ocr_v5_output_max)
    except Exception as exc:
        logging.exception("OCR v5 failed")
        raise HTTPException(status_code=502, detail=f"OCR engine error: {str(exc)}") from exc
    payload = ocr_data.get("payload", {})
    extracted_text = payload.get("extracted_text") or ""
    extracted_markdown = payload.get("extracted_markdown")
    questions = payload.get("questions") or []
    latency_ms = int((time.time() - start) * 1000)

    if not extracted_text:
        extracted_text = "Could not read text. Try cropping tighter or increasing zoom."

    cache_entry = OcrCache(
        cache_key=cache_key,
        extracted_text=extracted_text,
        extracted_markdown=extracted_markdown,
        questions=questions,
        hit_count=1,
        created_at=datetime.utcnow(),
        last_hit_at=datetime.utcnow()
    )
    session.add(cache_entry)
    session.commit()

    return OcrV5Response(
        extracted_text=extracted_text,
        extracted_markdown=extracted_markdown,
        questions=questions,
        cache_hit=False,
        latency_ms=latency_ms,
        input_tokens=ocr_data.get("input_tokens"),
        output_tokens=ocr_data.get("output_tokens"),
        cached_tokens=ocr_data.get("cached_tokens")
    )


@api_router.post("/extract_questions", response_model=ExtractQuestionsResponse)
@limiter.limit("10/minute")
async def extract_questions(
    request: Request,
    file: UploadFile = File(...),
    file_hash: Optional[str] = Form(None),
    page_number: Optional[int] = Form(None),
    crop_x: Optional[float] = Form(None),
    crop_y: Optional[float] = Form(None),
    crop_w: Optional[float] = Form(None),
    crop_h: Optional[float] = Form(None),
    preview_w: Optional[float] = Form(None),
    preview_h: Optional[float] = Form(None),
    viewport_w: Optional[float] = Form(None),
    viewport_h: Optional[float] = Form(None),
    rotation: Optional[float] = Form(None),
    render_scale: Optional[float] = Form(None),
    source: str = Form("image"),
    user_selection: str = Form("crop"),
    ocr_engine_choice: str = Form("auto"),
    debug: bool = Form(False),
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not file:
        raise HTTPException(status_code=400, detail="File is required")

    token_policy = get_token_policy(session)

    raw = await file.read()
    if len(raw) > EXTRACT_MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds size limit")

    if raw.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="PDF uploads are not accepted")
    image_kind = _detect_image_kind(raw)
    content_type = file.content_type or ""
    if not content_type.startswith("image/") and image_kind not in ("jpeg", "png", "webp"):
        raise HTTPException(status_code=415, detail="Only image uploads are accepted")
    if image_kind not in ("jpeg", "png", "webp"):
        raise HTTPException(status_code=415, detail="Unsupported image type")

    meta = {
        "extract_cache_rev": EXTRACT_CACHE_REV,
        "file_hash": file_hash,
        "page_number": page_number,
        "crop_x": crop_x,
        "crop_y": crop_y,
        "crop_w": crop_w,
        "crop_h": crop_h,
        "preview_w": preview_w,
        "preview_h": preview_h,
        "viewport_w": viewport_w,
        "viewport_h": viewport_h,
        "rotation": rotation,
        "render_scale": render_scale,
        "source": source,
        "user_selection": user_selection,
        "ocr_engine_choice": ocr_engine_choice,
    }
    hash_input = raw + json.dumps(meta, sort_keys=True).encode("utf-8")
    cache_key = hashlib.sha256(hash_input).hexdigest()

    cached = session.exec(select(OcrExtractionCache).where(OcrExtractionCache.cache_key == cache_key)).first()
    if cached:
        cached.hit_count += 1
        cached.last_hit_at = datetime.utcnow()
        session.add(cached)
        session.commit()
        page_hint = page_number if isinstance(page_number, int) and page_number >= 0 else 0
        cached_result = cached.result_json or {}
        payload = _validate_extract_payload(
            {
                "ok": cached_result.get("ok"),
                "error": cached_result.get("error"),
                "is_math_page": cached_result.get("is_math_page"),
                "notes": cached_result.get("notes"),
                "questions": cached_result.get("questions"),
            },
            page_hint=page_hint,
        )
        ok = payload.get("ok", True)
        error = payload.get("error")
        error_msg = _extract_error_message(error)
        return ExtractQuestionsResponse(
            ok=bool(ok),
            is_math_page=bool(payload.get("is_math_page", False)),
            notes=payload.get("notes") or ([error_msg] if error_msg else []),
            questions=payload.get("questions") or [],
            error=error,
            ocr_provider_used=cached_result.get("ocr_provider_used"),
            ocr_model_used=cached_result.get("ocr_model_used"),
            ocr_fallback_attempts=cached_result.get("ocr_fallback_attempts"),
        )

    request_id = str(uuid.uuid4())
    start = time.time()
    image_bytes = raw
    crop_ratios = None

    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        crop_ratios = _normalize_crop_ratios(
            crop_x, crop_y, crop_w, crop_h, preview_w, preview_h, img.width, img.height
        )
        if user_selection != "whole_page" and crop_ratios:
            x_px, y_px, w_px, h_px = _ratios_to_pixels(crop_ratios, img.width, img.height)
            logging.info(
                "extract_questions applying crop: x=%s y=%s w=%s h=%s image=%sx%s",
                x_px,
                y_px,
                w_px,
                h_px,
                img.width,
                img.height,
            )
            img = img.crop((x_px, y_px, x_px + w_px, y_px + h_px))
        metrics = _crop_quality_metrics(img)
        logging.info(
            "extract_questions input metrics: size=%sx%s stddev=%.2f white=%.3f",
            int(metrics["width"]),
            int(metrics["height"]),
            metrics["stddev"],
            metrics["white_pct"]
        )
        if _is_low_text_crop(metrics):
            scale = 1.5
            upscaled = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS
            )
            retry_crop = ImageEnhance.Contrast(upscaled).enhance(1.4)
            retry_crop = retry_crop.filter(ImageFilter.SHARPEN)
            retry_metrics = _crop_quality_metrics(retry_crop)
            logging.info(
                "extract_questions retry metrics: size=%sx%s stddev=%.2f white=%.3f",
                int(retry_metrics["width"]),
                int(retry_metrics["height"]),
                retry_metrics["stddev"],
                retry_metrics["white_pct"]
            )
            if not _is_low_text_crop(retry_metrics):
                img = retry_crop
        image_bytes = _encode_image_jpeg(img, quality=85)
    except Exception as exc:
        logging.warning("extract_questions pre-processing failed: %s", exc)
        image_bytes = raw
    try:
        is_pdf_source = source in ("pdf", "pdf_page")
        max_extract_tokens = token_policy.ocr_pdf_extract_max if is_pdf_source else token_policy.ocr_image_extract_max
        if max_extract_tokens <= 0:
            raise HTTPException(status_code=500, detail="Extract token policy misconfigured")
        crop_meta = {
            "request_id": request_id,
            "rotation": rotation,
            "fullPage": user_selection == "whole_page",
            "user_selection": user_selection,
            "source": source,
            "page_number": page_number,
            "crop_norm": {
                "x": crop_x, "y": crop_y, "w": crop_w, "h": crop_h
            } if crop_x is not None else None,
            "viewport": {
                "vw": viewport_w, "vh": viewport_h, "pw": preview_w, "ph": preview_h
            }
        }
        extract_data = await _call_extract_questions(
            session=session,
            image_bytes=image_bytes,
            max_output_tokens=max_extract_tokens,
            engine_choice=ocr_engine_choice,
            crop_meta=crop_meta,
            debug=debug
        )
    except BadRequestError as exc:
        logging.exception("extract_questions OpenAI request failed")
        raise HTTPException(status_code=400, detail=f"Extract engine error: {str(exc)}") from exc
    except Exception as exc:
        logging.exception("extract_questions failed")
        raise HTTPException(status_code=502, detail=f"Extract engine error: {str(exc)}") from exc

    page_hint = page_number if isinstance(page_number, int) and page_number >= 0 else 0
    payload = _validate_extract_payload(extract_data.get("payload") or {}, page_hint=page_hint)
    latency_ms = int((time.time() - start) * 1000)
    telemetry = ExtractTelemetry(
        request_id=request_id,
        input_tokens=extract_data.get("input_tokens"),
        output_tokens=extract_data.get("output_tokens"),
        cached_tokens=extract_data.get("cached_tokens"),
        latency_ms_openai=latency_ms,
        latency_ms_total=latency_ms
    )

    ok_value = payload.get("ok", True)
    error_value = payload.get("error")
    error_msg = _extract_error_message(error_value)
    result = {
        "ok": bool(ok_value),
        "error": error_value,
        "is_math_page": bool(payload.get("is_math_page", False)),
        "notes": payload.get("notes") or ([error_msg] if error_msg else []),
        "questions": payload.get("questions") or [],
        "ocr_provider_used": extract_data.get("ocr_provider_used"),
        "ocr_model_used": extract_data.get("ocr_model_used"),
        "ocr_fallback_attempts": extract_data.get("ocr_fallback_attempts") or [],
    }

    should_cache = _should_cache_extract_result(result)
    if should_cache:
        cache_entry = OcrExtractionCache(
            cache_key=cache_key,
            user_id=user_id,
            result_json=result,
            meta=meta,
            hit_count=1,
            created_at=datetime.utcnow(),
            last_hit_at=datetime.utcnow()
        )
        session.add(cache_entry)

    total_tokens = None
    if telemetry.input_tokens is not None and telemetry.output_tokens is not None:
        total_tokens = telemetry.input_tokens + telemetry.output_tokens
    record_request_event(session, {
        "request_id": request_id,
        "user_id": user_id,
        "mode": "extract",
        "learning_mode": None,
        "subject": None,
        "grade_level": user.grade_level if user else None,
        "model": result.get("ocr_model_used") or EXTRACT_MODEL,
        "provider": result.get("ocr_provider_used") or "openai",
        "route": "extract_questions",
        "tokens_in": telemetry.input_tokens,
        "tokens_out": telemetry.output_tokens,
        "tokens_total": total_tokens,
        "cost_usd": _calc_cost(total_tokens, EXTRACT_MODEL, telemetry.input_tokens, telemetry.output_tokens),
        "latency_ms": latency_ms,
        "status": "ok",
        "error_type": None,
        "schema_valid": True,
        "verification_pass": None,
        "is_stream": False,
        "is_cached": False,
        "credit_deducted": False,
        "credit_amount": None,
        "ocr_used": True,
        "voice_used": False,
        "response_truncated": False
    })
    session.add(UsageLog(
        user_id=user_id,
        action_type="extract_questions",
        tokens_used=total_tokens or 0,
        timestamp=datetime.utcnow()
    ))
    session.commit()

    return ExtractQuestionsResponse(
        ok=bool(result["ok"]),
        is_math_page=result["is_math_page"],
        notes=result["notes"],
        questions=result["questions"],
        error=result.get("error"),
        ocr_provider_used=result.get("ocr_provider_used"),
        ocr_model_used=result.get("ocr_model_used"),
        ocr_fallback_attempts=result.get("ocr_fallback_attempts"),
    )


@api_router.post("/solve_questions_batch", response_model=SolveBatchResponse)
@limiter.limit("5/minute")
async def solve_questions_batch(
    request: Request,
    body: SolveBatchRequest,
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    from app.services.admin.analytics_service import record_request_event, _calc_cost
    if not body.items:
        raise HTTPException(status_code=400, detail="No items provided")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token_policy = get_token_policy(session)
    subscription = subscription_service.get_or_create_subscription(session, user)
    if not subscription:
        raise HTTPException(status_code=500, detail="Subscription not available")

    plan = session.get(Plan, subscription.plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="Plan not available for subscription")

    features_used = body.features_used or {}
    token_policy = get_token_policy(session)
    ocr_metadata = _collect_ocr_metadata(features_used)
    voice_metadata = _collect_voice_metadata(features_used)
    ocr_confidence = ocr_metadata.get("ocr_confidence")
    modality = _resolve_modality_flags(body, features_used, bool(body.image_url or body.artifact_id), bool(body.has_voice))
    verification_level = _get_verification_level(body, modality)
    token_policy_key = body.token_policy or "system_config"
    has_ocr = bool(features_used.get("ocr_used", True))
    has_voice = bool(features_used.get("voice_used", False))
    if has_voice:
        raise HTTPException(status_code=400, detail="Voice modality is not supported in OCR batch solves")
    if modality in ("ocr_image", "ocr_pdf"):
        _enforce_ocr_confidence(ocr_confidence)

    reserve_map: Dict[str, float] = {}
    total_reserve = 0.0
    for item in body.items:
        reserve = _estimate_credits(plan, item.requested_mode or "minimal", item.text, has_ocr, has_voice)
        reserve_map[item.question_id] = reserve
        total_reserve += reserve

    if subscription.credits_balance < total_reserve:
        raise HTTPException(status_code=402, detail="Insufficient credits for batch solve")

    request_id = str(uuid.uuid4())
    holds: Dict[str, CreditHold] = {}
    for item in body.items:
        reserve = reserve_map[item.question_id]
        subscription.credits_balance -= reserve
        subscription.credits_used_this_period += reserve
        hold = CreditHold(
            user_id=user.id,
            subscription_id=subscription.id,
            request_id=request_id,
            question_id=item.question_id,
            reserved_credits=reserve,
            status="held",
            metadata={
                "requested_mode": item.requested_mode,
                "has_ocr": has_ocr,
                "has_voice": has_voice,
                "text_length": len(item.text)
            }
        )
        holds[item.question_id] = hold
        session.add(hold)
        session.add(UsageLedger(
            subscription_id=subscription.id,
            transaction_type="HOLD",
            amount=reserve,
            balance_after=subscription.credits_balance,
            reference_id=request_id,
            meta={"question_id": item.question_id}
        ))

    session.add(subscription)
    session.commit()

    semaphore = asyncio.Semaphore(SOLVE_BATCH_CONCURRENCY)
    from app.services.solver_v3 import get_solver_v3
    from app.database import engine

    async def solve_one(item: SolveBatchItem) -> SolveBatchItemResult:
        async with semaphore:
            if item.requires_figure and not item.figure_image_base64:
                return SolveBatchItemResult(
                    question_id=item.question_id,
                    ok=False,
                    error="Figure required. Please crop the figure region."
                )
            token_estimate = _estimate_input_tokens(item.text)
            max_input = token_policy.ocr_image_input_max + token_policy.ocr_image_input_overhead
            if token_estimate > max_input:
                return SolveBatchItemResult(
                    question_id=item.question_id,
                    ok=False,
                    error=f"OCR input exceeds token limit ({token_estimate} > {max_input})"
                )

            image_url = None
            if item.figure_image_base64:
                data = item.figure_image_base64
                if data.startswith("data:image"):
                    image_url = data
                else:
                    image_url = f"data:image/jpeg;base64,{data}"

            local_session = Session(engine)
            try:
                solver = get_solver_v3()
                from app.utils.token_limits import get_effective_max_tokens
                effective_max_tokens = get_effective_max_tokens(item.requested_mode or "minimal", "solve", token_policy)
                result = await solver.solve(
                    problem_text=item.text,
                    context="",
                    request_id=request_id,
                    user_id=user_id,
                    db_session=local_session,
                    requested_mode=item.requested_mode or "minimal",
                    trusted_context=None,
                    learning_mode="solve",
                    image_url=image_url,
                    max_output_tokens=effective_max_tokens
                )
                telemetry = result.get("telemetry") or result.get("_telemetry") or {}
                return SolveBatchItemResult(
                    question_id=item.question_id,
                    ok=not result.get("error", False),
                    solve_response_json=result,
                    telemetry=telemetry
                )
            except Exception as exc:
                logging.exception("solve_questions_batch item failed")
                return SolveBatchItemResult(
                    question_id=item.question_id,
                    ok=False,
                    error=str(exc)
                )
            finally:
                local_session.close()

    results = await asyncio.gather(*[solve_one(item) for item in body.items])

    for item_result in results:
        hold = holds.get(item_result.question_id)
        reserved = hold.reserved_credits if hold else 0.0

        if not item_result.ok or not item_result.solve_response_json:
            subscription_service.refund_credits(
                session,
                subscription.id,
                reserved,
                "Solve failed",
                request_id
            )
            item_result.credits_reserved = reserved
            item_result.credits_final = 0.0
            item_result.credits_refunded = reserved
            if hold:
                hold.status = "released"
                hold.finalized_at = datetime.utcnow()
                session.add(hold)
            event_payload = {
                "request_id": request_id,
                "user_id": user_id,
                "mode": hold.meta.get("requested_mode") if hold and hold.meta else None,
                "learning_mode": "solve",
                "subject": None,
                "grade_level": user.grade_level if user else None,
                "model": None,
                "provider": "openai",
                "route": "solve_question",
                "tokens_in": None,
                "tokens_out": None,
                "tokens_total": None,
                "cost_usd": 0.0,
                "latency_ms": None,
                "status": "error",
                "error_type": item_result.error or "solve_failed",
                "schema_valid": None,
                "verification_pass": None,
                "is_stream": False,
                "is_cached": False,
                "credit_deducted": False,
                "credit_amount": 0.0,
                "ocr_used": has_ocr,
                "voice_used": has_voice,
                "response_truncated": False
            }
            _record_event_with_modality(session, event_payload, modality, ocr_metadata, voice_metadata, verification_level, token_policy_key)
            session.commit()
            continue

        telemetry = item_result.telemetry or {}
        total_tokens = telemetry.get("total_tokens")
        if total_tokens is None:
            total_tokens = (telemetry.get("input_tokens") or 0) + (telemetry.get("output_tokens") or 0)

        base_cost = subscription_service.calculate_cost(
            plan,
            "detailed" if (hold.meta or {}).get("requested_mode") == "detailed" else "concise",
            has_ocr,
            has_voice
        )
        actual_cost = float(base_cost + (float(total_tokens or 0) / TOKENS_PER_CREDIT))

        refund_amount = 0.0
        if actual_cost <= reserved:
            refund_amount = reserved - actual_cost
            if refund_amount > 0:
                subscription_service.refund_credits(
                    session,
                    subscription.id,
                    refund_amount,
                    "Solve refund",
                    request_id
                )
        else:
            extra = actual_cost - reserved
            if subscription.credits_balance >= extra:
                subscription_service.execute_debit(
                    session,
                    subscription,
                    extra,
                    {"action": "solve_batch_extra", "question_id": item_result.question_id},
                    request_id
                )
                session.commit()
            else:
                actual_cost = reserved

        item_result.credits_reserved = reserved
        item_result.credits_final = actual_cost
        item_result.credits_refunded = refund_amount

        session.add(UsageLog(
            user_id=user_id,
            action_type="solve_question",
            tokens_used=int(total_tokens or 0),
            timestamp=datetime.utcnow()
        ))
        record_request_event(session, {
            "request_id": request_id,
            "user_id": user_id,
                "mode": hold.meta.get("requested_mode") if hold and hold.meta else None,
            "learning_mode": "solve",
            "subject": None,
            "grade_level": user.grade_level if user else None,
            "model": telemetry.get("model") if isinstance(telemetry, dict) else None,
            "provider": "openai",
            "route": "solve_question",
            "tokens_in": telemetry.get("input_tokens") if isinstance(telemetry, dict) else None,
            "tokens_out": telemetry.get("output_tokens") if isinstance(telemetry, dict) else None,
            "tokens_total": total_tokens,
            "cost_usd": _calc_cost(total_tokens, telemetry.get("model") if isinstance(telemetry, dict) else None, telemetry.get("input_tokens") if isinstance(telemetry, dict) else None, telemetry.get("output_tokens") if isinstance(telemetry, dict) else None),
            "latency_ms": telemetry.get("latency_ms_total") if isinstance(telemetry, dict) else None,
            "status": "ok" if item_result.ok else "error",
            "error_type": item_result.error if not item_result.ok else None,
            "schema_valid": telemetry.get("validated") if isinstance(telemetry, dict) else None,
            "verification_pass": None,
            "is_stream": False,
            "is_cached": False,
            "credit_deducted": item_result.ok,
            "credit_amount": actual_cost if item_result.ok else None,
            "ocr_used": has_ocr,
            "voice_used": has_voice,
            "response_truncated": bool(telemetry.get("truncated")) if isinstance(telemetry, dict) else False
            ,
            "ocr_engine": ocr_metadata.get("ocr_engine"),
            "ocr_source": ocr_metadata.get("ocr_source"),
            "ocr_warnings": ocr_metadata.get("ocr_warnings"),
            "ocr_confidence": ocr_confidence,
            "voice_confirmed": voice_metadata.get("voice_confirmed"),
            "voice_ambiguity_flags": voice_metadata.get("voice_ambiguity_flags"),
            "voice_clarifier_question": voice_metadata.get("voice_clarifier_question"),
            "voice_stt_provider": voice_metadata.get("voice_stt_provider"),
            "voice_transcript_confidence": voice_metadata.get("voice_transcript_confidence"),
            "verification_level": verification_level,
            "token_policy_key": token_policy_key
        })

        if hold:
            hold.status = "finalized"
            hold.finalized_at = datetime.utcnow()
            hold.meta = {
                **(hold.meta or {}),
                "total_tokens": total_tokens,
                "credits_final": actual_cost,
                "credits_refunded": refund_amount
            }
            session.add(hold)
        session.commit()

    return SolveBatchResponse(ok=True, results=results)

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

        token_policy = get_token_policy(session)
        
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
    features_used = body.features_used or {}
    modality = _resolve_modality_flags(body, features_used, bool(body.image_url or body.artifact_id), bool(body.has_voice))
    if modality == "voice":
        _enforce_input_token_limit(base_query, token_policy.voice_input_max, modality)
    elif modality.startswith("ocr"):
        _enforce_input_token_limit(base_query, token_policy.ocr_image_input_max + token_policy.ocr_image_input_overhead, modality)
    else:
        _enforce_input_token_limit(base_query, token_policy.text_input_max, modality)
    
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
    model_name_fallback = "YouAsk AI (Multimodal)" if (body.image_url or body.artifact_id) else (os.environ.get("OPENAI_MODEL_DEFAULT") or "unknown_model")
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
    from app.utils.token_limits import get_effective_max_tokens
    requested_mode = body.requested_mode or ("detailed" if body.mode == "detailed" else "minimal")
    effective_max_tokens = get_effective_max_tokens(
        requested_mode,
        (body.trusted_context or {}).get("learning_mode", "solve"),
        token_policy
    )
    try:
        print(f"[API] Using Solver V3 for: {final_prompt[:50]}...")
        solution_data = await solver.solve(
            problem_text=final_prompt,
            context=context,
            trace=body.mode == "debug",
            user_tier=_resolve_runtime_tier_slug(user),
            user_id=user_id,
            db_session=session,
            requested_mode=requested_mode,
            trusted_context=body.trusted_context,
            max_output_tokens=effective_max_tokens
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
        solve_tier=_resolve_runtime_tier_slug(user)
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
    
    assistant_msg = ChatMessage(
        session_id=new_chat.id,
        role="assistant",
        content=assistant_content or "",
        structured_data=solution_data,
        model_used=model_name,
        tokens_used=telemetry_data.get("total_tokens", 0),
        telemetry=telemetry_data
    )
    session.add(assistant_msg)
    
    # 6. Finalize Analytics Event
    from app.services.admin.analytics_service import record_request_event
    
    # Commit session and messages
    session.commit()
    
    # Record telemetry for admin dashboard
    event_payload = {
        "request_id": request_id,
        "user_id": user_id,
        "mode": requested_mode,
        "learning_mode": new_chat.learning_mode,
        "subject": body.subject,
        "grade_level": user.grade_level if user else None,
        "model": model_name,
        "provider": "openai",
        "route": "solve_question",
        "tokens_in": telemetry_data.get("input_tokens"),
        "tokens_out": telemetry_data.get("output_tokens"),
        "tokens_total": telemetry_data.get("total_tokens"),
        "cost_usd": 0.0, # Will be calc'd inside record_request_event or legacy helper
        "latency_ms": telemetry_data.get("latency_ms_total"),
        "status": "success"
    }
    record_request_event(session, event_payload)
    session.commit()

    # Transformation complete, visuals handled at runtime in frontend
    return SolveResponse(
        session_id=new_chat.id,
        solution=solution_data,
        concepts=solution_data.get("concepts") or [],
        model_used=model_name,
        tokens_used=telemetry_data.get("total_tokens", 0),
        telemetry=telemetry_data,
        has_image=is_image
    )

# --- Legacy Prompt Endpoints (Removed) ---

LEGACY_PROMPT_TABLES_REMOVED_DETAIL = (
    "Legacy prompt tables were removed. Use /api/v1/admin/prompt-registry/* endpoints."
)

@api_router.get("/admin/prompt-assets")
async def list_prompt_assets_removed():
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.put("/admin/plans/{plan_id}/prompt-links")
async def update_plan_links_removed(plan_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.get("/admin/plans/{plan_id}/prompt-links")
async def get_plan_links_removed(plan_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

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

@api_router.get("/solve_v3_runtime_meta")
async def solve_v3_runtime_meta(
    user_id: int = Query(...),
    tier: Optional[str] = Query(None),
    mode_family: str = Query("SOLVE"),
    requested_mode: str = Query("minimal"),
    session: Session = Depends(get_session),
):
    from app.llm_profiles.profile_resolver import ProfileResolver, ProfileResolutionError
    from app.services.llm.manager import get_configured_openai_model

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    request_id = str(uuid.uuid4())
    provider = "openai"
    model = get_configured_openai_model()
    entitled_tier_slug = _resolve_runtime_tier_slug(user)
    tier_policy = _clamp_requested_tier(tier, entitled_tier_slug)
    tier_requested = tier_policy["tier_requested"]
    tier_effective = tier_policy["tier_effective"]
    mode_label = (mode_family or "SOLVE").strip().upper()
    output_format = (
        FREEFORM_OUTPUT_MODE.lower()
        if should_use_freeform_output(provider, model) and mode_label == "SOLVE"
        else "json_schema"
    )

    try:
        profile = ProfileResolver.resolve_profile(
            session=session,
            user=user,
            requested_mode=requested_mode,
            learning_mode="solve",
            force_tier=tier_effective,
            mode_family=mode_label,
            provider=provider,
        )
    except ProfileResolutionError as profile_err:
        raise HTTPException(
            status_code=500,
            detail={
                "code": getattr(profile_err, "code", "PROFILE_RESOLUTION_FAILED"),
                "message": str(profile_err),
                "request_id": request_id,
                "tier": tier_effective,
                "mode": mode_label,
                "provider": provider,
                "details": getattr(profile_err, "details", {}),
            },
        )

    binding_meta = getattr(profile, "prompt_binding_meta", {}) or {}
    return {
        "request_id": request_id,
        "provider": provider,
        "model": model,
        "tier_requested": tier_requested,
        "tier_effective": tier_effective,
        "mode": mode_label,
        "output_format": output_format,
        "prompt_binding_id": binding_meta.get("binding_id"),
        "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
        "developer_prompt_id": binding_meta.get("developer_prompt_id"),
        "output_schema_id": binding_meta.get("output_schema_id"),
        "prompt_versions": {
            "system": binding_meta.get("global_system_prompt_version"),
            "developer": binding_meta.get("developer_prompt_version"),
            "schema": binding_meta.get("output_schema_version"),
        },
    }


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
    token_policy = get_token_policy(session)

    
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
    modality = _resolve_modality_flags(body, features_used, bool(body.image_url or body.artifact_id), bool(body.has_voice))
    if modality == "voice":
        _enforce_input_token_limit(problem_text, token_policy.voice_input_max, modality)
    elif modality.startswith("ocr"):
        _enforce_input_token_limit(problem_text, token_policy.ocr_image_input_max + token_policy.ocr_image_input_overhead, modality)
    else:
        _enforce_input_token_limit(problem_text, token_policy.text_input_max, modality)
    
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
    from app.llm_profiles.profile_resolver import ProfileResolutionError
    from app.services.llm.manager import get_configured_openai_model
    entitled_tier_slug = _resolve_runtime_tier_slug(user)
    tier_policy = _clamp_requested_tier(body.tier, entitled_tier_slug)
    requested_tier = tier_policy["tier_requested"]
    effective_tier = tier_policy["tier_effective"]
    solve_provider = "openai"
    configured_model = get_configured_openai_model()
    try:
        resolved_profile = ProfileResolver.resolve_profile(
            session,
            user,
            requested_mode=requested_mode,
            learning_mode=learning_mode,
            force_tier=effective_tier,
            mode_family="SOLVE",
            provider=solve_provider,
        )
    except ProfileResolutionError as profile_err:
        raise HTTPException(
            status_code=500,
            detail={
                "code": getattr(profile_err, "code", "PROFILE_RESOLUTION_FAILED"),
                "message": str(profile_err),
                "request_id": request_id,
                "tier": effective_tier,
                "mode": "SOLVE",
                "provider": solve_provider,
                "details": getattr(profile_err, "details", {}),
            },
        )
    effective_max_tokens = None
    if resolved_profile:
        from app.utils.token_limits import get_effective_max_tokens
        effective_max_tokens = get_effective_max_tokens(resolved_profile.mode, learning_mode, token_policy)
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
            # --- BILLING: STAGE 1 (ESTIMATE & HOLD) ---
            action_type = "solve_tutor" if requested_mode == "detailed" else "solve_quick"
            if bool(body.has_voice or features_used.get("voice_used")):
                 action_type = "voice_solve"

            # Estimate Tokens (Heuristics)
            # Input: ~ len(text)/4
            # Output: minimal=1000, detailed=4000 (roughly)
            # This is just for holding credits; reconciliation fixes it.
            est_input = len(problem_text) // 3 + 100
            est_output = 4000 if requested_mode == "detailed" else 1500
            
            op_id_raw = f"{user_id}_{action_type}_{question_key}_{requested_mode}_{request_id}"
            op_id = hashlib.sha256(op_id_raw.encode()).hexdigest()

            ledger = billing_service.create_pending_transaction(
                 session,
                 user_id,
                 action_type,
                 estimated_input_tokens=est_input,
                 estimated_output_tokens=est_output,
                 request_id=request_id, # Using request_id as key for simplicity in logs
                 question_id=question_key or str(hash(problem_text))
            )
            
            if not ledger.ok:
                raise HTTPException(status_code=402, detail=f"Insufficient credits for estimate. Status: {ledger.status}")
                 
            deduct_committed = True # Flag implies we have an open ledger to settle
            ledger_id = ledger.id
            
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
                    learning_mode=learning_mode,
                    image_url=body.image_url,
                    max_output_tokens=effective_max_tokens
                )
                
                # --- BILLING: STAGE 2 (SETTLE) ---
                # Extract actual usage from result
                telemetry = result.get("telemetry", {})
                act_in = telemetry.get("input_tokens", 0)
                act_out = telemetry.get("output_tokens", 0)
                
                # If telemetry missing (rare error), fallback to estimate or 0? 
                # Let's fallback to estimate to avoid free usage exploit if backend glitch.
                if act_in == 0 and act_out == 0:
                     act_in, act_out = est_input, est_output
                
                billing_service.settle_transaction(
                    session,
                    ledger_id,
                    actual_input_tokens=act_in,
                    actual_output_tokens=act_out
                )

            except Exception as e:
                # --- BILLING: STAGE 3 (FAIL) ---
                billing_service.fail_transaction(session, ledger_id, f"System Error: {str(e)}")
                raise e
            

        
        # Check if it's an error response
        if result.get("error", False):
            # FAIL ON SOLVER ERROR
            if not was_cached and 'ledger_id' in locals():
                 billing_service.fail_transaction(session, ledger_id, f"Solver Error: {result.get('error_type')}")

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
                "model": (result.get("telemetry") or {}).get("model") or configured_model,
                "provider": (result.get("telemetry") or {}).get("provider") or solve_provider,
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
                "validation_errors": result.get("validation_errors", []),
                "solve_meta": {
                    "request_id": request_id,
                    "provider": (result.get("telemetry") or {}).get("provider") or solve_provider,
                    "model": (result.get("telemetry") or {}).get("model") or configured_model,
                    "tier_requested": requested_tier,
                    "tier_effective": effective_tier,
                    "mode": "SOLVE",
                    "prompt_binding_id": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("binding_id"),
                    "global_system_prompt_id": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("global_system_prompt_id"),
                    "developer_prompt_id": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("developer_prompt_id"),
                    "output_schema_id": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("output_schema_id"),
                    "prompt_versions": {
                        "system": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("global_system_prompt_version"),
                        "developer": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("developer_prompt_version"),
                        "schema": ((result.get("telemetry") or {}).get("prompt_binding") or {}).get("output_schema_version"),
                    },
                },
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
            model_used=result.get("_model", os.environ.get("OPENAI_MODEL_DEFAULT") or "unknown_model"),
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
        binding_meta = (telemetry.get("prompt_binding") or (getattr(resolved_profile, "prompt_binding_meta", {}) or {}))
        result["solve_meta"] = {
            "request_id": request_id,
            "provider": telemetry.get("provider") or solve_provider,
            "model": telemetry.get("model") or configured_model,
            "tier_requested": requested_tier,
            "tier_effective": effective_tier,
            "mode": "SOLVE",
            "prompt_binding_id": binding_meta.get("binding_id"),
            "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
            "developer_prompt_id": binding_meta.get("developer_prompt_id"),
            "output_schema_id": binding_meta.get("output_schema_id"),
            "prompt_versions": {
                "system": binding_meta.get("global_system_prompt_version"),
                "developer": binding_meta.get("developer_prompt_version"),
                "schema": binding_meta.get("output_schema_version"),
            },
        }
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
            from app.utils.token_limits import get_effective_max_tokens
            effective_max_tokens = get_effective_max_tokens(requested_mode, learning_mode, token_policy)
        trace_payload = {
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
            "model_sent": telemetry.get("model") or os.environ.get("OPENAI_MODEL_DEFAULT"),
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
        }
        _log_trace_with_modality(trace_payload, modality, ocr_metadata, voice_metadata, verification_level, token_policy_key)

        record_request_event(session, {
            "request_id": request_id,
            "user_id": user_id,
            "mode": requested_mode,
            "learning_mode": learning_mode,
            "subject": body.subject,
            "grade_level": user.grade_level if user else None,
            "model": telemetry.get("model") or result.get("_model") or configured_model,
            "provider": telemetry.get("provider") or solve_provider,
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
            ,
            "input_modality": modality,
            "verification_level": verification_level,
            "token_policy": token_policy_key
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
                "model_sent": os.environ.get("OPENAI_MODEL_DEFAULT"),
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
                "error": str(e),
                "input_modality": modality,
                "verification_level": verification_level,
                "token_policy_key": token_policy_key,
                "ocr_confidence": ocr_confidence
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
                "model": configured_model,
                "provider": solve_provider,
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
                "response_truncated": False,
                "input_modality": modality,
                "verification_level": verification_level,
                "token_policy": token_policy_key
            })
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Solver V3 failed: {str(e)}"
        )
    
@api_router.get("/solve_v3_stream")
async def solve_v3_stream_info():
    """Helper for developers testing the URL in browser."""
    return {
        "status": "online", 
        "message": "This endpoint is active but requires a POST request with a JSON body. Please use the 'Solve' button in the application."
    }

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
    from app.utils.token_limits import get_effective_max_tokens
    from pathlib import Path

    from app.services.subscription_service import subscription_service
    from app.services.tier_utils import get_user_effective_tier_slug
    from app.services.llm.manager import get_configured_openai_model
    from app.llm_profiles.profile_resolver import ProfileResolutionError

    # 0. Phase 3: Idempotency & Debit (Audit/Billing)
    # Generate request_id early to use as idempotency key or reference
    request_id = str(uuid.uuid4())

    # Resolve checks
    user_obj = session.get(User, user_id)
    effective_tier_slug = get_user_effective_tier_slug(user_obj)
    tier_policy = _clamp_requested_tier(body.tier, effective_tier_slug)
    requested_tier = tier_policy["tier_requested"]
    effective_tier = tier_policy["tier_effective"]
    stream_provider = "openai"
    stream_model = get_configured_openai_model()
    effective_billing_tier = effective_tier.lower()

    action_req = {
        "tier": effective_billing_tier,
        "mode": body.requested_mode,
        "has_ocr": body.features_used.get("ocr_used", False) if body.features_used else False,
        "has_voice": body.features_used.get("voice_used", False) if body.features_used else False,
        "reference_id": request_id, 
        "source_type": None
    }
    
    entitlement = subscription_service.check_entitlement_and_debit(session, user_id, action_req)
    if not entitlement["allowed"]:
         # Strict HTTP Status Mapping (Phase 4)
         err_code = entitlement.get("error_code")
         detail_msg = entitlement.get("reason", "Credit check failed")
         
         if err_code == "TIER_NOT_ALLOWED":
             raise HTTPException(status_code=403, detail=detail_msg)
         elif err_code == "CAP_EXCEEDED":
             raise HTTPException(status_code=429, detail=detail_msg)
         elif err_code == "INSUFFICIENT_CREDITS":
             raise HTTPException(status_code=402, detail=detail_msg)
         else:
             raise HTTPException(status_code=402, detail=detail_msg) # Fallback
         
    # Execute Debit if not already processed
    subscription = entitlement["subscription"]
    cost = entitlement["cost"]
    debit_meta = entitlement["meta"]
    should_refund = (entitlement.get("status") != "already_processed" and cost > 0)
    
    if entitlement.get("status") != "already_processed":
        subscription_service.execute_debit(session, subscription, cost, debit_meta, request_id)

    async def _inner_generate():
        start_total = time.perf_counter()
        # request_id already defined in outer scope
        
        requested_mode = body.requested_mode or "minimal"
        learning_mode = (body.trusted_context or {}).get("learning_mode", "solve")
        deduct_attempted = {"credits": False, "ocr": False, "voice": False}
        deduct_committed = False
        features_used = body.features_used or {}
        raw_problem_text = (
            body.confirmed_text or
            body.confirmed_markdown or
            body.text_query or
            "No problem provided"
        )
        if perf_enabled():
            perf_emit(
                label="solve_input_received",
                file_function="backend/app/api.py:solve_v3_stream_endpoint._inner_generate",
                elapsed_ms=0.0,
                request_id=request_id,
                extra=(
                    f"confirmed_text_len={len(body.confirmed_text or '')}"
                    f"|confirmed_markdown_len={len(body.confirmed_markdown or '')}"
                    f"|text_query_len={len(body.text_query or '')}"
                    f"|raw_hash={_sha256_text(raw_problem_text or '')}"
                    f"|raw_preview={_preview_text(raw_problem_text or '').replace(chr(10), ' ')}"
                ),
            )
        problem_text = (raw_problem_text or "").strip()
        if perf_enabled():
            perf_emit(
                label="solve_input_selected",
                file_function="backend/app/api.py:solve_v3_stream_endpoint._inner_generate",
                elapsed_ms=0.0,
                request_id=request_id,
                extra=(
                    f"len={len(problem_text)}"
                    f"|hash={_sha256_text(problem_text)}"
                    f"|preview={_preview_text(problem_text).replace(chr(10), ' ')}"
                ),
            )
        print(f"[API] Solve Request Body: {body.model_dump_json(indent=2)}")
        token_policy = get_token_policy(session)
        print(f"[API] Loaded TokenPolicy: {json.dumps(serialize_token_policy(token_policy), indent=2)}")

        # Resolve profile for correct prompt/schema/tokens
        from app.llm_profiles.profile_resolver import ProfileResolver
        plan_key = None
        if user_obj and user_obj.subscription and user_obj.subscription.plan:
            plan_key = user_obj.subscription.plan.slug
        else:
            plan_key = effective_tier_slug
        try:
            profile = ProfileResolver.resolve_profile(
                session,
                user_obj,
                requested_mode=requested_mode,
                learning_mode=learning_mode,
                force_tier=effective_tier,
                mode_family="SOLVE",
                provider=stream_provider,
            )
        except ProfileResolutionError as profile_err:
            error_code = getattr(profile_err, "code", "PROFILE_RESOLUTION_FAILED")
            error_details = getattr(profile_err, "details", {})
            log_solve_trace({
                "request_id": request_id,
                "user_id": user_id,
                "seat_id": None,
                "plan_key": plan_key,
                "ui_goal": learning_mode,
                "ui_style": requested_mode,
                "resolved_profile_key": None,
                "resolved_system_file_path": None,
                "resolved_schema_file_path": None,
                "schema_name": None,
                "max_output_tokens_sent": None,
                "model_sent": stream_model,
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
                "error": f"{error_code}: {profile_err}",
            })
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': {'code': error_code, 'message': str(profile_err), 'request_id': request_id, 'tier': effective_tier, 'mode': 'SOLVE', 'provider': stream_provider, 'details': error_details}})}\n\n"
            return
        print(f"[SOLVER_V3_STREAM] Resolved Profile: Tier={profile.tier}, Mode={profile.mode}, MaxTokens={profile.max_output_tokens}")
        profile_key = f"{profile.tier.upper().replace('-', '_')}_{profile.mode.upper()}"
        binding_meta = getattr(profile, "prompt_binding_meta", {}) or {}
        if user_obj and user_obj.subscription and user_obj.subscription.plan:
            plan_key = user_obj.subscription.plan.slug
        else:
            plan_key = profile.tier

        effective_max_tokens = get_effective_max_tokens(requested_mode, learning_mode, token_policy)

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
                "model_sent": stream_model,
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
                "model": os.environ.get("OPENAI_MODEL_DEFAULT"),
                "provider": stream_provider,
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

        modality = _resolve_modality_flags(body, features_used, bool(body.image_url or body.artifact_id), bool(body.has_voice))
        verification_level = _get_verification_level(body, modality)
        policy_key = body.token_policy or "system_config"
        if modality == "voice":
            _enforce_input_token_limit(problem_text, token_policy.voice_input_max, modality)
        elif modality in ("ocr_image", "ocr_pdf"):
            overhead = token_policy.ocr_image_input_overhead if modality == "ocr_image" else token_policy.ocr_pdf_input_overhead
            limit = (token_policy.ocr_image_input_max if modality == "ocr_image" else token_policy.ocr_pdf_input_max) + overhead
            _enforce_input_token_limit(problem_text, limit, modality)
        else:
            _enforce_input_token_limit(problem_text, token_policy.text_input_max, modality)

        # Entitlement check + debit (credits/OCR/voice)
        action_mode = "detailed" if requested_mode == "detailed" else "concise"
        action_req = {
            "tier": effective_billing_tier,
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
                "model_sent": stream_model,
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
                "model": os.environ.get("OPENAI_MODEL_DEFAULT"),
                "provider": stream_provider,
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

        output_format = (
            FREEFORM_OUTPUT_MODE.lower()
            if should_use_freeform_output(stream_provider, stream_model)
            else "json_schema"
        )
        freeform_prompt_template: Optional[str] = None
        freeform_prompt_id = FREEFORM_PROMPT_ID
        freeform_prompt_version = FREEFORM_PROMPT_VERSION
        if output_format == FREEFORM_OUTPUT_MODE.lower():
            tier_enum = PromptTierEnum((effective_tier or "FREE").upper())
            freeform_prompt_entry = prompt_registry_service.get_active_freeform_prompt_for_tier(
                session=session,
                tier=tier_enum,
                provider=stream_provider,
                model=stream_model,
                mode=PromptModeEnum.SOLVE,
            )
            if not freeform_prompt_entry or not (freeform_prompt_entry.content or "").strip():
                if deduct_committed and debit_cost > 0:
                    subscription_service.refund_credits(
                        session,
                        sub_id,
                        debit_cost,
                        "Free-form solve failed: prompt not configured",
                        request_id,
                    )
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': 'freeform_prompt_not_found', 'message': f'Missing active tiered free-form prompt in prompt_templates for tier={effective_tier}', 'request_id': request_id}})}\n\n"
                return
            freeform_prompt_template = freeform_prompt_entry.content
            freeform_prompt_id = freeform_prompt_entry.prompt_id
            freeform_prompt_version = str(freeform_prompt_entry.version)
            logging.getLogger(__name__).debug(
                "request_id=%s freeform_prompt_selected tier=%s provider=%s model=%s prompt_id=%s prompt_row_id=%s version=%s",
                request_id,
                effective_tier,
                stream_provider,
                stream_model,
                freeform_prompt_entry.prompt_id,
                freeform_prompt_entry.id,
                freeform_prompt_entry.version,
            )

        # Meta Event (Part A1)
        meta_data = {
            "request_id": request_id,
            "session_id": None, # Will be set after creation
            "message_id": None,
            "provider": stream_provider,
            "model": stream_model,
            "max_output_tokens": effective_max_tokens,
            "mode": requested_mode,
            "mode_family": "SOLVE",
            "tier_requested": requested_tier,
            "effective_tier": effective_tier,
            "prompt_binding_id": binding_meta.get("binding_id"),
            "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
            "developer_prompt_id": freeform_prompt_id if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("developer_prompt_id"),
            "output_schema_id": None if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("output_schema_id"),
            "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
            "developer_prompt_version": freeform_prompt_version if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("developer_prompt_version"),
            "output_schema_version": None if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("output_schema_version"),
            "output_format": output_format,
        }
        meta_data["input_modality"] = modality
        meta_data["verification_level"] = verification_level
        meta_data["token_policy_key"] = policy_key
        meta_data["solve_meta"] = {
            "request_id": request_id,
            "provider": stream_provider,
            "model": stream_model,
            "tier_requested": requested_tier,
            "tier_effective": effective_tier,
            "mode": "SOLVE",
            "prompt_binding_id": binding_meta.get("binding_id"),
            "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
            "developer_prompt_id": freeform_prompt_id if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("developer_prompt_id"),
            "output_schema_id": None if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("output_schema_id"),
            "output_format": output_format,
            "prompt_versions": {
                "system": binding_meta.get("global_system_prompt_version"),
                "developer": freeform_prompt_version if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("developer_prompt_version"),
                "schema": None if output_format == FREEFORM_OUTPUT_MODE.lower() else binding_meta.get("output_schema_version"),
            },
        }
        
        max_output_tokens = effective_max_tokens
        meta_data["type"] = "meta"
        yield f"event: meta\ndata: {json.dumps(meta_data)}\n\n"

        # Stage: Preparing request... (Part A2)
        yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Preparing request...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

        print(
            f"[SOLVER_V3_STREAM] Recv: {problem_text[:50]}... "
            f"(RequestedMode: {requested_mode}, output_format: {output_format}, tokens: {max_output_tokens})"
        )

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
                "model_sent": stream_model,
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
                "model": os.environ.get("OPENAI_MODEL_DEFAULT"),
                "provider": stream_provider,
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
        
        context_user = user_obj or session.get(User, user_id)
        if context_user:
            country = context_user.profile_country or 'Canada'
            province = context_user.profile_province_state or 'ON'
            context += f"\n\n[STUDENT CONTEXT]\nCountry: {country}\nProvince: {province}\nGrade: {context_user.grade_level or 'Unknown'}"

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

        # Stage: Waiting for model...
        yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Waiting for model...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

        if output_format == FREEFORM_OUTPUT_MODE.lower():
            if not os.environ.get("OPENAI_API_KEY"):
                if deduct_committed and debit_cost > 0:
                    subscription_service.refund_credits(
                        session,
                        sub_id,
                        debit_cost,
                        "Free-form solve failed: OPENAI_API_KEY missing",
                        request_id,
                    )
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': 'openai_not_configured', 'message': 'OPENAI_API_KEY is not configured', 'request_id': request_id}})}\n\n"
                return

            max_attempts = _resolve_freeform_max_attempts(
                effective_tier=effective_tier,
                trusted_context=body.trusted_context,
                is_make_it_right=bool(getattr(body, "is_make_it_right", False)),
            )
            freeform_requested_mode = requested_mode
            if (
                (effective_tier or "").strip().upper() == "RESEARCH"
                and requested_mode.strip().lower() in {"", "minimal", "concise"}
                and os.environ.get("FREEFORM_RESEARCH_FORCE_IMPROVE_MODE", "1").strip().lower() in {"1", "true", "yes", "on"}
            ):
                freeform_requested_mode = "improve"
            base_num_predict = int(os.environ.get("FREEFORM_NUM_PREDICT", "2500"))
            num_predict = resolve_num_predict(
                tier=effective_tier,
                difficulty=body.difficulty,
                requested_mode=freeform_requested_mode,
                env_default=base_num_predict,
            )
            timeout_seconds = resolve_timeout_seconds(
                tier=effective_tier,
                env_default=int(os.environ.get("FREEFORM_TIMEOUT_SECONDS", "120")),
            )

            attempt_summaries: List[Dict[str, Any]] = []
            selected_result = None
            latest_nonempty_result = None
            first_delta_emitted = False
            for attempt_number in range(1, max_attempts + 1):
                yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': f'Free-form attempt {attempt_number}/{max_attempts}...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"
                try:
                    attempt_result = None
                    streamed_parts: List[str] = []
                    async for stream_event in generate_freeform_solution(
                        problem_text=problem_text,
                        prompt_template=freeform_prompt_template or "",
                        model=stream_model,
                        num_predict=num_predict,
                        timeout_seconds=timeout_seconds,
                        prompt_id=freeform_prompt_id,
                        prompt_version=freeform_prompt_version,
                        tier=effective_tier,
                        requested_mode=freeform_requested_mode,
                        system_prompt=(os.environ.get("FREEFORM_SYSTEM_PROMPT") or "").strip() or None,
                    ):
                        event_type = stream_event.get("type")
                        if event_type == "delta":
                            chunk_text = str(stream_event.get("text") or "")
                            if chunk_text:
                                streamed_parts.append(chunk_text)
                                yield f"event: delta\ndata: {json.dumps({'type': 'delta', 'text': chunk_text})}\n\n"
                                if not first_delta_emitted:
                                    first_delta_emitted = True
                                    if perf_enabled():
                                        perf_emit(
                                            label="sse_first_delta",
                                            file_function="backend/app/api.py:solve_v3_stream_endpoint._inner_generate",
                                            elapsed_ms=(time.perf_counter() - start_total) * 1000.0,
                                            request_id=request_id,
                                            extra=f"attempt={attempt_number}",
                                        )
                        elif event_type == "result":
                            attempt_result = stream_event.get("result")
                    if attempt_result is None:
                        raise RuntimeError("freeform_stream_missing_result")
                    streamed_text = "".join(streamed_parts)
                    if attempt_result.output_text and attempt_result.output_text != streamed_text:
                        if attempt_result.output_text.startswith(streamed_text):
                            tail = attempt_result.output_text[len(streamed_text) :]
                            if tail:
                                yield f"event: delta\ndata: {json.dumps({'type': 'delta', 'text': tail})}\n\n"
                                if not first_delta_emitted:
                                    first_delta_emitted = True
                                    if perf_enabled():
                                        perf_emit(
                                            label="sse_first_delta",
                                            file_function="backend/app/api.py:solve_v3_stream_endpoint._inner_generate",
                                            elapsed_ms=(time.perf_counter() - start_total) * 1000.0,
                                            request_id=request_id,
                                            extra=f"attempt={attempt_number}|postprocess_tail=1",
                                        )
                    if attempt_result.validation.get("is_valid"):
                        status = "ok"
                    elif attempt_result.validation.get("is_usable"):
                        status = "usable"
                    else:
                        status = "invalid"
                    attempt_summaries.append(
                        {
                            "attempt_number": attempt_number,
                            "status": status,
                            "latency_ms": attempt_result.latency_ms,
                            "time_to_first_token_ms": attempt_result.time_to_first_token_ms,
                            "truncated": attempt_result.truncated,
                            "char_count": len(attempt_result.output_text or ""),
                            "validation_score": attempt_result.validation.get("score"),
                            "failed_checks": attempt_result.validation.get("failed_checks", []),
                        }
                    )
                    if attempt_result.output_text and attempt_result.validation.get("is_usable"):
                        latest_nonempty_result = (attempt_number, attempt_result)
                    if attempt_result.validation.get("is_valid"):
                        selected_result = (attempt_number, attempt_result)
                        break
                    if attempt_result.validation.get("is_usable") and attempt_result.extracted_answer:
                        selected_result = (attempt_number, attempt_result)
                        break
                    if attempt_result.validation.get("is_usable"):
                        selected_result = (attempt_number, attempt_result)
                        break
                except Exception as attempt_error:
                    error_text = str(attempt_error)
                    attempt_summaries.append(
                        {
                            "attempt_number": attempt_number,
                            "status": "error",
                            "latency_ms": None,
                            "char_count": 0,
                            "validation_score": "0/0",
                            "failed_checks": ["generation_error"],
                            "error": error_text,
                        }
                    )
                if attempt_number >= max_attempts:
                    break

            final_choice = selected_result or latest_nonempty_result
            if final_choice is None:
                if deduct_committed and debit_cost > 0:
                    subscription_service.refund_credits(
                        session,
                        sub_id,
                        debit_cost,
                        "Free-form solve failed after retries",
                        request_id,
                    )
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': 'freeform_generation_failed', 'message': 'Unable to generate free-form solution.', 'request_id': request_id}})}\n\n"
                return

            final_attempt_number, final_result = final_choice
            output_text = final_result.output_text
            extracted_answer = final_result.extracted_answer or ""
            archive_path = None
            try:
                archive_path = archive_freeform_output(
                    request_id=request_id,
                    provider=stream_provider,
                    model=stream_model,
                    attempt_number=final_attempt_number,
                    output_text=output_text,
                )
            except Exception as archive_exc:
                logging.getLogger(__name__).warning(
                    "request_id=%s freeform_archive_failed error=%s",
                    request_id,
                    archive_exc,
                )
            final_status = "ok" if final_result.validation.get("is_valid") else "invalid"
            _persist_freeform_attempt(
                session=session,
                request_id=request_id,
                user_id=user_id,
                session_id=new_chat.id,
                message_id=placeholder_msg.id,
                attempt_number=final_attempt_number,
                provider=stream_provider,
                model=stream_model,
                prompt_id=final_result.prompt_id,
                prompt_version=final_result.prompt_version,
                raw_solution_text=output_text,
                extracted_answer=extracted_answer,
                validation_json=final_result.validation,
                latency_ms=final_result.latency_ms,
                archive_path=archive_path,
                status=final_status,
            )
            if output_text and not first_delta_emitted:
                yield f"event: delta\ndata: {json.dumps({'type': 'delta', 'text': output_text})}\n\n"
                if perf_enabled():
                    perf_emit(
                        label="sse_first_delta",
                        file_function="backend/app/api.py:solve_v3_stream_endpoint._inner_generate",
                        elapsed_ms=(time.perf_counter() - start_total) * 1000.0,
                        request_id=request_id,
                        extra=f"attempt={final_attempt_number}|fallback=1",
                    )
                first_delta_emitted = True

            yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Finalizing...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

            freeform_telemetry = {
                "provider": stream_provider,
                "model": stream_model,
                "output_format": FREEFORM_OUTPUT_MODE.lower(),
                "request_id": request_id,
                "latency_ms_total": int((time.perf_counter() - start_total) * 1000),
                "latency_ms_generation": final_result.latency_ms,
                "char_count": len(output_text),
                "attempts": attempt_summaries,
                "attempt_count": len(attempt_summaries),
                "final_attempt_number": final_attempt_number,
                "archive_path": archive_path,
                "prompt_id": freeform_prompt_id,
                "prompt_version": freeform_prompt_version,
                "requested_mode_model": freeform_requested_mode,
                "validated": final_result.validation.get("is_valid", False),
                "is_usable": final_result.validation.get("is_usable", False),
                "validation_score": final_result.validation.get("score"),
                "validation_quality_score": final_result.validation.get("quality_score"),
                "validation_failed_checks": final_result.validation.get("failed_checks", []),
                "validation_missing_items": final_result.validation.get("missing_items", []),
                "autocorrect_applied": bool((final_result.solution_doc or {}).get("autocorrect", {}).get("applied")),
                "schema_valid": None,
                "hide_from_tutor": True,
                "channel": "canvas_primary",
            }

            placeholder_msg.content = output_text
            placeholder_msg.structured_data = {
                "output_format": FREEFORM_OUTPUT_MODE.lower(),
                "raw_solution_text": output_text,
                "extracted_answer": extracted_answer,
                "validation_json": final_result.validation,
                "solution_doc": final_result.solution_doc,
                "attempts": attempt_summaries,
                "archive_path": archive_path,
                "prompt_id": freeform_prompt_id,
                "prompt_version": freeform_prompt_version,
                "request_id": request_id,
                "solve_meta": meta_data.get("solve_meta"),
                "hide_from_tutor": True,
            }
            placeholder_msg.telemetry = freeform_telemetry
            placeholder_msg.tokens_used = max(len(output_text) // 4, 1)
            placeholder_msg.subject = body.subject or "General"
            placeholder_msg.grade_level = context_user.grade_level if context_user else None
            placeholder_msg.difficulty = body.difficulty

            tokens_estimate = max(len(output_text) // 4, 1)
            add_tokens_to_user(user_id, tokens_estimate, session)
            session.add(UsageLog(user_id=user_id, action_type="solve_v3_stream", tokens_used=tokens_estimate))
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
                "schema_name": None,
                "max_output_tokens_sent": effective_max_tokens,
                "model_sent": stream_model,
                "cache_hit": False,
                "openai_calls_count": 0,
                "repair_attempted": False,
                "prompt_tokens_estimate": None,
                "input_tokens": 0,
                "output_tokens": tokens_estimate,
                "cached_tokens": None,
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": None,
                "problem_text": problem_text,
                "input_modality": modality,
                "verification_level": verification_level,
                "token_policy_key": policy_key,
                "prompt_binding_id": binding_meta.get("binding_id"),
                "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
                "developer_prompt_id": freeform_prompt_id,
                "output_schema_id": None,
                "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
                "developer_prompt_version": freeform_prompt_version,
                "output_schema_version": None,
                "output_format": FREEFORM_OUTPUT_MODE.lower(),
            })
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_obj.grade_level if user_obj else None,
                "model": stream_model,
                "provider": stream_provider,
                "route": "solve_v3_stream",
                "tokens_in": 0,
                "tokens_out": tokens_estimate,
                "tokens_total": tokens_estimate,
                "cost_usd": _calc_cost(tokens_estimate, stream_model, 0, tokens_estimate),
                "latency_ms": freeform_telemetry["latency_ms_total"],
                "status": "ok",
                "error_type": None,
                "schema_valid": None,
                "verification_pass": bool(final_result.validation.get("checks", {}).get("verification_checks_min_3")),
                "is_stream": True,
                "is_cached": False,
                "credit_deducted": deduct_committed,
                "credit_amount": debit_cost if deduct_committed else None,
                "ocr_used": action_req["has_ocr"],
                "voice_used": action_req["has_voice"],
                "response_truncated": False,
            })
            yield f"event: telemetry\ndata: {json.dumps({'type': 'telemetry', 'telemetry': freeform_telemetry})}\n\n"
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': True, 'session_id': new_chat.id, 'message_id': placeholder_msg.id})}\n\n"
            return

        solver = get_solver_v3()
        full_content = ""
        openai_telemetry = {}
        repair_attempted = False

        try:
            async for chunk in solver.solve_stream(
                problem_text,
                context,
                trace=True,
                request_id=request_id,
                max_output_tokens=max_output_tokens,
                system_prompt=profile.system_prompt_content,
                developer_prompt=getattr(profile, "developer_prompt_content", None),
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
                    truncated_meta = dict(meta_data)
                    truncated_meta["truncated"] = True
                    truncated_meta["type"] = "meta"
                    yield f"event: meta\ndata: {json.dumps(truncated_meta)}\n\n"
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
                        "model_sent": openai_telemetry.get("model") or stream_model,
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
                        "error": str(chunk.get("error")),
                        "prompt_binding_id": binding_meta.get("binding_id"),
                        "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
                        "developer_prompt_id": binding_meta.get("developer_prompt_id"),
                        "output_schema_id": binding_meta.get("output_schema_id"),
                        "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
                        "developer_prompt_version": binding_meta.get("developer_prompt_version"),
                        "output_schema_version": binding_meta.get("output_schema_version"),
                    })
                    record_request_event(session, {
                        "request_id": request_id,
                        "user_id": user_id,
                        "mode": requested_mode,
                        "learning_mode": learning_mode,
                        "subject": body.subject,
                        "grade_level": user_obj.grade_level if user_obj else None,
                        "model": openai_telemetry.get("model") or stream_model,
                        "provider": openai_telemetry.get("provider") or stream_provider,
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
            final_data: Dict[str, Any] = {}
            is_truncated = openai_telemetry.get("truncated", False)
            raw_llm_output = full_content or ""
            validation_errors: List[str] = []
            schema_valid = False
            repair_attempted = False

            print(f"[SOLVER_V3_STREAM] Stream finished. Content length: {len(raw_llm_output)} chars, truncated: {is_truncated}")

            if not raw_llm_output.strip():
                validation_errors.append("parse_error: empty content received from LLM")
            else:
                try:
                    final_data = json.loads(raw_llm_output)
                except json.JSONDecodeError as parse_err:
                    validation_errors.append(
                        f"parse_error: invalid JSON at line {parse_err.lineno}, col {parse_err.colno}: {parse_err.msg}"
                    )

            if final_data and not validation_errors:
                validation_errors = _validate_stream_payload(final_data, profile.json_schema_content)
                schema_valid = len(validation_errors) == 0

            if validation_errors:
                repair_attempted = True
                openai_telemetry["repair_attempted"] = True
                openai_telemetry["repair_attempts"] = 1
                try:
                    repaired_data, repaired_text = await solver._repair_response(
                        problem=problem_text,
                        context=context,
                        system_prompt=profile.system_prompt_content,
                        invalid_data=final_data if final_data else raw_llm_output,
                        validation_error="schema_validation_failed",
                        error_list=validation_errors,
                        json_schema_config={"schema": _schema_object_for_validation(profile.json_schema_content)},
                        max_output_tokens=min(1200, max_output_tokens or 1200),
                        requested_mode=requested_mode,
                        trace=True,
                        provider=stream_provider,
                        model=stream_model,
                    )
                    if isinstance(repaired_text, str) and repaired_text.strip():
                        raw_llm_output = repaired_text
                    final_data = repaired_data if isinstance(repaired_data, dict) else {}
                    validation_errors = (
                        _validate_stream_payload(final_data, profile.json_schema_content)
                        if final_data
                        else ["repair_error: repair output was not a JSON object"]
                    )
                    schema_valid = len(validation_errors) == 0
                    if schema_valid:
                        openai_telemetry["repaired"] = True
                except Exception as repair_err:
                    validation_errors.append(f"repair_error: {repair_err}")
                    schema_valid = False

            if not schema_valid:
                error_message = "Unable to generate a valid structured solution. Please try again."
                error_payload = _build_schema_valid_stream_error_payload(
                    problem_text=problem_text,
                    provider=openai_telemetry.get("provider") or stream_provider,
                    model=openai_telemetry.get("model") or stream_model,
                    tier=effective_tier,
                    mode="SOLVE",
                    prompt_id=binding_meta.get("developer_prompt_id"),
                    validation_errors=validation_errors,
                    schema_config=profile.json_schema_content,
                )
                error_payload["_raw_llm_output"] = raw_llm_output[:20000]
                placeholder_msg.content = error_message
                placeholder_msg.structured_data = error_payload
                openai_telemetry["schema_valid"] = False
                openai_telemetry["validation_errors"] = validation_errors[:10]
                openai_telemetry["raw_llm_output"] = raw_llm_output[:20000]
                placeholder_msg.telemetry = openai_telemetry
                placeholder_msg.tokens_used = openai_telemetry.get("total_tokens", 0)
                session.commit()

                if deduct_committed and debit_cost > 0:
                    subscription_service.refund_credits(
                        session,
                        sub_id,
                        debit_cost,
                        "Stream schema validation failed",
                        request_id,
                    )

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
                    "model_sent": openai_telemetry.get("model") or stream_model,
                    "cache_hit": False,
                    "openai_calls_count": openai_telemetry.get("openai_calls_count", 0),
                    "repair_attempted": repair_attempted,
                    "prompt_tokens_estimate": None,
                    "input_tokens": openai_telemetry.get("input_tokens"),
                    "output_tokens": openai_telemetry.get("output_tokens"),
                    "cached_tokens": openai_telemetry.get("cached_tokens"),
                    "deduct_attempted": deduct_attempted,
                    "deduct_committed": deduct_committed,
                    "openai_payload": openai_telemetry.get("openai_payload"),
                    "problem_text": problem_text,
                    "error": "schema_validation_failed",
                    "validation_errors": validation_errors[:10],
                    "prompt_binding_id": binding_meta.get("binding_id"),
                    "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
                    "developer_prompt_id": binding_meta.get("developer_prompt_id"),
                    "output_schema_id": binding_meta.get("output_schema_id"),
                    "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
                    "developer_prompt_version": binding_meta.get("developer_prompt_version"),
                    "output_schema_version": binding_meta.get("output_schema_version"),
                })
                record_request_event(session, {
                    "request_id": request_id,
                    "user_id": user_id,
                    "mode": requested_mode,
                    "learning_mode": learning_mode,
                    "subject": body.subject,
                    "grade_level": user_obj.grade_level if user_obj else None,
                    "model": openai_telemetry.get("model") or stream_model,
                    "provider": openai_telemetry.get("provider") or stream_provider,
                    "route": "solve_v3_stream",
                    "tokens_in": openai_telemetry.get("input_tokens"),
                    "tokens_out": openai_telemetry.get("output_tokens"),
                    "tokens_total": openai_telemetry.get("total_tokens"),
                    "cost_usd": _calc_cost(
                        openai_telemetry.get("total_tokens"),
                        openai_telemetry.get("model"),
                        openai_telemetry.get("input_tokens"),
                        openai_telemetry.get("output_tokens"),
                    ),
                    "latency_ms": openai_telemetry.get("latency_ms_total") or openai_telemetry.get("latency_ms_openai"),
                    "status": "error",
                    "error_type": "schema_validation_failed",
                    "schema_valid": False,
                    "verification_pass": False,
                    "is_stream": True,
                    "is_cached": False,
                    "credit_deducted": deduct_committed,
                    "credit_amount": debit_cost if deduct_committed else None,
                    "ocr_used": action_req["has_ocr"],
                    "voice_used": action_req["has_voice"],
                    "response_truncated": bool(openai_telemetry.get("truncated") or is_truncated),
                })
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': 'schema_validation_failed', 'message': error_message, 'validation_errors': validation_errors[:10], 'request_id': request_id}})}\n\n"
                return

            if profile.mode == "minimal" and "solution" not in final_data:
                from app.services.response_mapper import map_minimal_to_canonical
                try:
                    final_data = map_minimal_to_canonical(final_data, problem_text)
                except Exception as e:
                    print(f"[SOLVER_V3_STREAM] Warning: Mapping failed: {e}")

            if isinstance(final_data.get("meta"), dict):
                debug_meta = final_data["meta"].get("debug")
                if not isinstance(debug_meta, dict):
                    debug_meta = {}
                debug_meta["schema_valid"] = True
                debug_meta["validation_errors"] = []
                final_data["meta"]["debug"] = debug_meta

            # Normalize only legacy payload shapes; v2 structured payloads are already strict-schema validated.
            if "solution" not in final_data:
                final_data = solver.normalize_solver_response(final_data)

            if is_truncated:
                final_data["_truncated"] = True
                final_data["_truncation_warning"] = "Response was truncated due to output token limit"
            final_data["_raw_llm_output"] = raw_llm_output[:20000]
            steps_count = 0
            if isinstance(final_data.get("solution"), dict) and isinstance(final_data["solution"].get("steps"), list):
                steps_count = len(final_data["solution"].get("steps") or [])
            elif isinstance(final_data.get("steps"), list):
                steps_count = len(final_data.get("steps") or [])
            print(f"[SOLVER_V3_STREAM] Validated response. Steps: {steps_count}")

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
                # Safe extraction of answer_text (supports both legacy and v2 payload shapes)
                final_answer_obj = final_data.get("final_answer", {})
                if not final_answer_obj and isinstance(final_data.get("solution"), dict):
                    final_answer_obj = final_data.get("solution", {}).get("final_answer", {})
                if isinstance(final_answer_obj, dict):
                    answer_text = (
                        final_answer_obj.get("answer_text")
                        or final_answer_obj.get("value")
                        or ""
                    ).strip()
                    if not answer_text and (final_answer_obj.get("answer_latex") or final_answer_obj.get("latex")):
                        answer_text = str(
                            final_answer_obj.get("answer_latex") or final_answer_obj.get("latex") or ""
                        ).strip()
                else:
                    answer_text = str(final_answer_obj).strip() if final_answer_obj else ""

                # Defensive fallback: never persist an empty assistant content.
                if not answer_text:
                    hints = final_data.get("hints") or final_data.get(" hints")
                    if isinstance(hints, list):
                        for hint in reversed(hints):
                            if isinstance(hint, dict):
                                hint_value = str(hint.get("value", "")).strip()
                                if hint_value:
                                    answer_text = hint_value
                                    break
                if not answer_text:
                    answer_text = (raw_llm_output or "").strip()
                if not answer_text:
                    answer_text = "Solution complete"

                # Keep structured payload consistent with fallback answer text.
                if isinstance(final_data.get("final_answer"), dict) and not final_data["final_answer"].get("answer_text"):
                    final_data["final_answer"]["answer_text"] = answer_text
                if (
                    isinstance(final_data.get("solution"), dict)
                    and isinstance(final_data["solution"].get("final_answer"), dict)
                    and not final_data["solution"]["final_answer"].get("value")
                ):
                    final_data["solution"]["final_answer"]["value"] = answer_text

                placeholder_msg.content = answer_text
                placeholder_msg.structured_data = final_data
                openai_telemetry["schema_valid"] = schema_valid
                placeholder_msg.telemetry = openai_telemetry
                placeholder_msg.tokens_used = openai_telemetry.get("total_tokens", 0)
                
                # Populate Metadata Columns (New)
                classification = final_data.get("classification", {})
                placeholder_msg.subject = classification.get("subject") or classification.get("topic") or body.subject
                placeholder_msg.grade_level = classification.get("grade_level") or (user_obj.grade_level if user_obj else None)
                placeholder_msg.difficulty = classification.get("difficulty")
                # Normalize tags/topics
                raw_tags = classification.get("tags") or classification.get("topics")
                if isinstance(raw_tags, list):
                     placeholder_msg.topics = [str(t) for t in raw_tags]
                elif isinstance(raw_tags, str):
                     placeholder_msg.topics = [raw_tags]
                
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
                "model_sent": openai_telemetry.get("model") or stream_model,
                "cache_hit": False,
                "openai_calls_count": openai_telemetry.get("openai_calls_count", 0),
                "repair_attempted": repair_attempted,
                "prompt_tokens_estimate": None,
                "input_tokens": openai_telemetry.get("input_tokens"),
                "output_tokens": openai_telemetry.get("output_tokens"),
                "cached_tokens": openai_telemetry.get("cached_tokens"),
                "deduct_attempted": deduct_attempted,
                "deduct_committed": deduct_committed,
                "openai_payload": openai_telemetry.get("openai_payload"),
                "problem_text": problem_text
                ,
                "input_modality": modality,
                "verification_level": verification_level,
                "token_policy_key": policy_key,
                "prompt_binding_id": binding_meta.get("binding_id"),
                "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
                "developer_prompt_id": binding_meta.get("developer_prompt_id"),
                "output_schema_id": binding_meta.get("output_schema_id"),
                "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
                "developer_prompt_version": binding_meta.get("developer_prompt_version"),
                "output_schema_version": binding_meta.get("output_schema_version"),
            })
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_obj.grade_level if user_obj else None,
                "model": openai_telemetry.get("model") or stream_model,
                "provider": openai_telemetry.get("provider") or stream_provider,
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
                "schema_valid": schema_valid,
                "verification_pass": None,
                "is_stream": True,
                "is_cached": False,
                "credit_deducted": deduct_committed,
                "credit_amount": debit_cost if deduct_committed else None,
                "ocr_used": action_req["has_ocr"],
                "voice_used": action_req["has_voice"],
                "response_truncated": bool(openai_telemetry.get("truncated") or final_data.get("_truncated"))
                ,
                "input_modality": modality,
                "verification_level": verification_level,
                "token_policy": policy_key
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
                "model_sent": openai_telemetry.get("model") or stream_model,
                "cache_hit": False,
                "openai_calls_count": openai_telemetry.get("openai_calls_count", 0),
                "repair_attempted": repair_attempted,
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
                    "model": openai_telemetry.get("model") or stream_model,
                    "provider": openai_telemetry.get("provider") or stream_provider,
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

    async def generate():
        try:
            async for chunk in _inner_generate():
                # Check for explicit application error yield logic
                if should_refund and "event: done" in chunk:
                    # Check for failure in the done event
                    # We look for simple string match to avoid parsing every chunk
                    # The DONE event looks like: data: {"ok": false, ...}
                    if '"ok": false' in chunk or '"ok":false' in chunk:
                         try:
                             subscription_service.refund_credits(session, subscription.id, cost, "System Error during solve", request_id)
                         except Exception as idx:
                             print(f"Refund failed: {idx}")
                yield chunk
        except Exception as e:
            if should_refund:
                try:
                    subscription_service.refund_credits(session, subscription.id, cost, "System Error during solve", request_id)
                except Exception as ex:
                    print(f"Refund failed: {ex}")
            raise e

    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@api_router.post("/solve/batch", response_model=SolveBatchResponse)
async def solve_batch_endpoint(
    body: SolveBatchRequest,
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    """
    Batch solve items with per-item tier application and credit deduction.
    """
    from app.services.solver_v3 import get_solver_v3
    from app.services.subscription_service import subscription_service
    
    results = []
    
    for item in body.items:
        # Unique ID for idempotency and tracing
        ref_id = f"batch_{uuid.uuid4()}_{item.question_id}"
        
        # 1. Check Entitlement
        action_req = {
            # Use requested_mode to derive tier if not explicit
            # Batch request logic usually similar to stream
            "mode": item.requested_mode or "minimal",
            "has_ocr": body.features_used.get("ocr_used", False) if body.features_used else False,
            "has_voice": body.features_used.get("voice_used", False) if body.features_used else False,
            "reference_id": ref_id,
            "source_type": None
        }
        
        entitlement = subscription_service.check_entitlement_and_debit(session, user_id, action_req)
        
        if not entitlement["allowed"]:
            # Strict error mapping for batch items?
            # Usually batch 200 OK with per-item error details.
            # But let's check code.
            err_code = entitlement.get("error_code")
            reason = entitlement.get("reason", "Credit check failed")
            
            results.append(SolveBatchItemResult(
                question_id=item.question_id,
                ok=False,
                error=f"[{err_code}] {reason}" if err_code else reason
            ))
            continue
            
        # 2. Execute Debit (if not already processed)
        status = entitlement.get("status")
        subscription = entitlement.get("subscription")
        cost = entitlement.get("cost", 0.0)
        
        if status != "already_processed" and subscription:
            subscription_service.execute_debit(session, subscription, cost, entitlement["meta"], ref_id)
            
        # 3. Solve
        try:
            solver = get_solver_v3()
            resolved_tier = entitlement["meta"].get("tier", "free")
            
            solve_res = await solver.solve(
                problem_text=item.text,
                context="",
                request_id=ref_id,
                user_tier=resolved_tier,
                requested_mode=item.requested_mode or "minimal",
                db_session=session,
                features_used=body.features_used,
                # Force non-streaming response
            )
            
            results.append(SolveBatchItemResult(
                question_id=item.question_id,
                ok=True,
                solve_response_json=solve_res if isinstance(solve_res, dict) else solve_res.dict(),
                credits_final=cost,
                credits_reserved=cost
            ))
            
        except Exception as e:
            # Refund if we charged
            if status != "already_processed" and cost > 0 and subscription:
                subscription_service.refund_credits(
                    session, subscription.id, cost, 
                    f"Batch error: {str(e)}", ref_id
                )
                
            results.append(SolveBatchItemResult(
                question_id=item.question_id,
                ok=False,
                error=str(e),
                credits_refunded=cost if (status != "already_processed" and cost > 0) else 0.0
            ))

    return SolveBatchResponse(ok=True, results=results)



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
VALID_COUNTRY_INPUTS = ['USA', 'Canada', 'US', 'CA']
COUNTRY_DISPLAY = {"US": "USA", "CA": "Canada"}

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

VALID_GRADE_LEVELS = [f"Grade {i}" for i in range(4, 13)] + ["College", "University"]


@api_router.get("/locations/countries")
async def get_countries():
    """Get list of supported countries for student profiles."""
    return {"countries": ["USA", "Canada"], "canonical_codes": ["US", "CA"]}


@api_router.get("/locations/provinces")
async def get_provinces(country: str = Query(..., description="Country code (USA or Canada)")):
    """Get list of provinces/states for a country."""
    canonical_country = normalize_country_code(country)
    if canonical_country not in {"US", "CA"}:
        raise HTTPException(status_code=400, detail=f"Invalid country. Must be one of: {VALID_COUNTRY_INPUTS}")

    if canonical_country == "US":
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


class SchoolDetailResult(BaseModel):
    id: int
    school_name: str
    country: str
    province_state: str
    city: Optional[str] = None


@api_router.get("/schools/search", response_model=List[SchoolSearchResult])
async def search_schools(
    country: str = Query(..., description="Country (USA/US or Canada/CA)"),
    province_state: str = Query(..., description="State or Province abbreviation"),
    q: str = Query("", description="Search query for school name"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    session: Session = Depends(get_session)
):
    """
    Search schools by country, province/state, and optional name query.
    Returns minimal fields for dropdown display.
    """
    canonical_country = normalize_country_code(country)
    if canonical_country not in {"US", "CA"}:
        raise HTTPException(status_code=400, detail=f"Invalid country. Must be one of: {VALID_COUNTRY_INPUTS}")

    province_state = province_state.strip().upper()
    # Validate province_state
    valid_provinces = US_STATES if canonical_country == "US" else CA_PROVINCES
    if province_state not in valid_provinces:
        raise HTTPException(status_code=400, detail=f"Invalid province/state for {COUNTRY_DISPLAY[canonical_country]}")

    # Dual-read compatibility while profile country strings transition.
    country_values = [canonical_country, COUNTRY_DISPLAY[canonical_country]]
    # Build query
    stmt = select(School).where(
        School.country.in_(country_values),
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


@api_router.get("/schools/{school_id}", response_model=SchoolDetailResult)
async def get_school_by_id(
    school_id: int,
    session: Session = Depends(get_session),
):
    school = session.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return SchoolDetailResult(
        id=school.id,
        school_name=school.school_name,
        country=school.country,
        province_state=school.province_state,
        city=school.city,
    )


class ProfileLocationUpdateRequest(BaseModel):
    """Request body for updating profile location fields."""
    profile_country: str  # Required: USA/US or Canada/CA
    profile_province_state: str  # Required: State or Province abbreviation
    grade_level: str  # Required: Grade 4-12, College, or University
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
    canonical_country = normalize_country_code(body.profile_country)
    if canonical_country not in {"US", "CA"}:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid country. Must be one of: {VALID_COUNTRY_INPUTS}"
        )
    
    # Validate province/state for country
    canonical_province = body.profile_province_state.strip().upper()
    valid_provinces = US_STATES if canonical_country == "US" else CA_PROVINCES
    if canonical_province not in valid_provinces:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid province/state for {COUNTRY_DISPLAY[canonical_country]}"
        )
    
    # Validate grade level
    if body.grade_level not in VALID_GRADE_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid grade level. Must be one of: {VALID_GRADE_LEVELS}"
        )
    
    selected_school_name: Optional[str] = None
    # Validate school_id if provided
    if body.school_id is not None:
        school = session.get(School, body.school_id)
        if not school:
            raise HTTPException(status_code=400, detail="School not found")
        
        # Ensure school matches the country and province
        school_country = normalize_country_code(school.country)
        if school_country != canonical_country or school.province_state != canonical_province:
            raise HTTPException(
                status_code=400,
                detail="School must be in the same country and province/state as user profile"
            )
        selected_school_name = school.school_name
    
    # Update user profile
    user.profile_country = body.profile_country
    user.profile_province_state = canonical_province
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
        "school_id": user.school_id,
        "school_name": selected_school_name
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
        user_input = None
        for msg in chat.messages:
            if msg.role == "user" and not user_input:
                user_input = msg.content
                break
        
        # Extract metadata from any assistant message (prefer most recent)
        telemetry = None
        grade_level = None
        difficulty = None
        topics_list = []
        msg_subject = None

        for msg in reversed(chat.messages):
            if msg.role == "assistant":
                # Telemetry
                if msg.telemetry:
                    telemetry = msg.telemetry
                elif msg.structured_data and isinstance(msg.structured_data, dict):
                    telemetry = msg.structured_data.get("telemetry") or msg.structured_data.get("_telemetry")
                
                # Metadata (New fields)
                if getattr(msg, "grade_level", None):
                    grade_level = msg.grade_level
                if getattr(msg, "difficulty", None):
                    difficulty = msg.difficulty
                if getattr(msg, "subject", None):
                    msg_subject = msg.subject
                
                # Topics parsing
                raw_topics = getattr(msg, "topics", None)
                if raw_topics:
                    try:
                        # Try JSON first
                        if raw_topics.startswith("["):
                            import json
                            topics_list = json.loads(raw_topics)
                        else:
                            # Comma separated
                            topics_list = [t.strip() for t in raw_topics.split(",") if t.strip()]
                    except:
                        topics_list = [raw_topics]
                
                if telemetry: 
                    break
        
        history_items.append(ChatHistoryItem(
            id=chat.id, 
            title=chat.title, 
            created_at=chat.created_at.isoformat(),
            subject=msg_subject or chat.subject or "Math",
            topic=chat.topic,
            grade_level=grade_level,
            difficulty=difficulty,
            topics=topics_list,
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


class PaperVersionSaveRequest(BaseModel):
    title: Optional[str] = None
    pages: List[Dict[str, Any]]


class PaperVersionSaveResponse(BaseModel):
    ok: bool
    session_id: int
    message_id: int
    version: int
    title: str
    saved_at: str

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
                media_url=getattr(msg, "media_url", None),
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


def _pick_primary_solve_message(messages: List[ChatMessage]) -> Optional[ChatMessage]:
    for msg in messages:
        if msg.role != "assistant":
            continue
        telemetry = msg.telemetry if isinstance(msg.telemetry, dict) else {}
        structured = msg.structured_data if isinstance(msg.structured_data, dict) else {}
        if telemetry.get("channel") == "canvas_primary" or telemetry.get("hide_from_tutor") is True:
            return msg
        if structured.get("hide_from_tutor") is True or structured.get("solve_meta"):
            return msg
        if str(structured.get("output_format") or "").lower() in {"freeform", "json_schema"}:
            return msg
    for msg in messages:
        if msg.role == "assistant":
            return msg
    return None


@api_router.post("/sessions/{session_id}/paper-versions", response_model=PaperVersionSaveResponse)
async def save_paper_version(
    session_id: int,
    request: PaperVersionSaveRequest,
    db: Session = Depends(get_session),
):
    chat_session = db.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not request.pages:
        raise HTTPException(status_code=400, detail="pages is required")

    assistant_messages = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc())
    ).all()
    target = _pick_primary_solve_message(assistant_messages)
    if not target:
        raise HTTPException(status_code=404, detail="No assistant solve output found")

    structured = target.structured_data.copy() if isinstance(target.structured_data, dict) else {}
    existing = structured.get("paper_versions")
    versions = existing if isinstance(existing, list) else []
    next_version = len(versions) + 1
    saved_at = datetime.utcnow().isoformat() + "Z"
    entry = {
        "version": next_version,
        "title": (request.title or f"Version {next_version}").strip() or f"Version {next_version}",
        "saved_at": saved_at,
        "pages": request.pages,
    }
    versions.append(entry)
    # Keep last 25 versions to avoid unbounded growth.
    structured["paper_versions"] = versions[-25:]
    structured["paper_latest_version"] = next_version
    target.structured_data = structured
    target.content = target.content or "Updated paper version."

    db.add(target)
    db.commit()
    db.refresh(target)

    return PaperVersionSaveResponse(
        ok=True,
        session_id=session_id,
        message_id=int(target.id or 0),
        version=next_version,
        title=entry["title"],
        saved_at=saved_at,
    )

class QuestionRequest(BaseModel):
    session_id: int
    user_id: int
    query: str
    context: Optional[dict] = None

@api_router.post("/ask-question")
async def ask_question(request: QuestionRequest, db: Session = Depends(get_session)):
    # 1. Fetch Context
    chat_session = db.get(ChatSession, request.session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get the last assistant message structure for fallback context
    last_assistant_msg = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == request.session_id)
        .where(ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc())
    ).first()
    
    # Merge or prioritize request context
    context = request.context or {}
    if not context and last_assistant_msg:
         context = last_assistant_msg.structured_data or {}
    
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
        model_used=os.environ.get("OPENAI_MODEL_DEFAULT") or "unknown_model",
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


# Session-scoped chat endpoint (for ContextualChatPanel)
class SessionChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


@api_router.post("/sessions/{session_id}/chat")
async def session_chat(
    session_id: int,
    request: SessionChatRequest,
    db: Session = Depends(get_session)
):
    """
    Chat endpoint for contextual questions about a specific session/solution.
    Used by the ContextualChatPanel in the frontend.
    """
    # 1. Fetch session
    chat_session = db.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. Build context from request or last assistant message
    context = request.context or {}
    
    # If no context provided, try to get from last assistant message with solution
    if not context or not context.get('original_problem'):
        last_assistant_msg = db.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.role == "assistant")
            .order_by(ChatMessage.created_at.desc())
        ).first()
        if last_assistant_msg and last_assistant_msg.structured_data:
            # Merge with existing context
            full_context = last_assistant_msg.structured_data.copy()
            full_context.update(context)
            context = full_context
    
    # 3. Get AI response
    result = await solver_service.get_chat_response(request.message, context, db)
    
    # 4. Save user message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.message
    )
    db.add(user_msg)
    
    # 5. Save AI response
    ai_content = result.get("content", "I'm sorry, I couldn't process that request.")
    ai_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=ai_content,
        model_used=os.environ.get("OPENAI_MODEL_DEFAULT") or "unknown_model",
        tokens_used=100  # Flat rate for chat
    )
    db.add(ai_msg)
    
    # 6. Charge tokens to user
    if chat_session.user_id:
        add_tokens_to_user(chat_session.user_id, 100, db)
    
    db.commit()
    db.refresh(ai_msg)
    
    return {
        "response": ai_content,
        "relevant": result.get("relevant", True),
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
        school_name=(user.school.school_name if user.school else None),
        
        # WhatsApp Integration
        whatsapp_secret=user.whatsapp_secret,
        whatsapp_enabled=user.whatsapp_enabled,
        
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

    user_ids = [u.id for u in users]
    subs = []
    if user_ids:
        subs = db.exec(select(Subscription).where(Subscription.user_id.in_(user_ids))).all()
    subscription_map = {sub.user_id: sub for sub in subs}
    plan_ids = {sub.plan_id for sub in subs if sub.plan_id}
    plan_map = {}
    if plan_ids:
        plans = db.exec(select(Plan).where(Plan.id.in_(plan_ids))).all()
        plan_map = {plan.id: plan for plan in plans}

    user_list = []
    for u in users:
        # Robust counts
        q_count = len(db.exec(select(ChatSession.id).where(ChatSession.user_id == u.id)).all())
        s_count = len(db.exec(select(OCRJob.id).where(OCRJob.user_id == u.id)).all())
        
        # Robust date handling
        last_active = u.last_active_at or u.created_at or datetime.utcnow()
        sub = subscription_map.get(u.id)
        plan = plan_map.get(sub.plan_id) if sub else None
        
        user_list.append(AdminUserListItem(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            subscription_tier=u.subscription_tier,
            subscription_status=sub.status if sub else u.subscription_status,
            subscription_id=sub.id if sub else None,
            role=u.role,
            questions_count=q_count,
            scans_count=s_count,
            last_active_at=last_active.isoformat(),
            plan_id=plan.id if plan else None,
            plan_slug=plan.slug if plan else u.subscription_tier,
            plan_name=plan.name if plan else None,
            plan_credits_per_month=plan.credits_per_month if plan else None,
            plan_price_monthly_cents=plan.price_monthly_cents if plan else None
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
    subscription = db.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    plan = db.get(Plan, subscription.plan_id) if subscription else None

    return AdminUserDetailResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        subscription_id=subscription.id if subscription else None,
        plan_id=plan.id if plan else None,
        plan_slug=plan.slug if plan else None,
        plan_name=plan.name if plan else None,
        plan_credits_per_month=plan.credits_per_month if plan else None,
        plan_price_monthly_cents=plan.price_monthly_cents if plan else None,
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
    if req.full_name is not None:
        user.full_name = req.full_name
    if req.email is not None:
        user.email = req.email
    if req.academic_level is not None:
        user.academic_level = req.academic_level
    if req.timezone is not None:
        user.timezone = req.timezone
    if req.profile_country is not None:
        user.profile_country = req.profile_country
    if req.profile_province_state is not None:
        user.profile_province_state = req.profile_province_state
    if req.grade_level is not None:
        user.grade_level = req.grade_level
    if req.school_id is not None:
        user.school_id = req.school_id
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


class SolverOutputAttemptListItem(BaseModel):
    id: int
    request_id: str
    user_id: Optional[int] = None
    session_id: Optional[int] = None
    message_id: Optional[int] = None
    output_format: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    attempt_number: int
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    char_count: int
    status: str
    archive_path: Optional[str] = None
    created_at: str
    output_preview: str


class SolverOutputAttemptDetail(SolverOutputAttemptListItem):
    extracted_answer: Optional[str] = None
    validation_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    raw_solution_text: str


def _serialize_solver_output_attempt(
    row: SolverOutputAttempt,
    include_full_output: bool = False,
) -> Dict[str, Any]:
    preview = (row.raw_solution_text or "")[:400]
    payload: Dict[str, Any] = {
        "id": int(row.id or 0),
        "request_id": row.request_id,
        "user_id": row.user_id,
        "session_id": row.session_id,
        "message_id": row.message_id,
        "output_format": row.output_format,
        "prompt_id": row.prompt_id,
        "prompt_version": row.prompt_version,
        "attempt_number": row.attempt_number,
        "provider": row.provider,
        "model": row.model,
        "latency_ms": row.latency_ms,
        "char_count": row.char_count,
        "status": row.status,
        "archive_path": row.archive_path,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "output_preview": preview,
    }
    if include_full_output:
        payload.update(
            {
                "extracted_answer": row.extracted_answer,
                "validation_json": row.validation_json,
                "error_message": row.error_message,
                "raw_solution_text": row.raw_solution_text or "",
            }
        )
    return payload


@api_router.get("/admin/solver-output-attempts", response_model=List[SolverOutputAttemptListItem])
async def admin_list_solver_output_attempts(
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    request_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    output_format: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    query = select(SolverOutputAttempt)
    if request_id:
        query = query.where(SolverOutputAttempt.request_id.contains(request_id.strip()))
    if user_id is not None:
        query = query.where(SolverOutputAttempt.user_id == user_id)
    if status:
        query = query.where(SolverOutputAttempt.status == status.strip().lower())
    if output_format:
        query = query.where(SolverOutputAttempt.output_format == output_format.strip().lower())
    rows = db.exec(
        query.order_by(SolverOutputAttempt.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return [_serialize_solver_output_attempt(row) for row in rows]


@api_router.get("/admin/solver-output-attempts/{attempt_id}", response_model=SolverOutputAttemptDetail)
async def admin_get_solver_output_attempt(
    attempt_id: int,
    db: Session = Depends(get_session),
):
    row = db.get(SolverOutputAttempt, attempt_id)
    if not row:
        raise HTTPException(status_code=404, detail="Solver output attempt not found")
    return _serialize_solver_output_attempt(row, include_full_output=True)


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
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_session)
):
    if table_name not in SQLModel.metadata.tables:
        raise HTTPException(status_code=404, detail="Table not found")
    table = SQLModel.metadata.tables[table_name]
    if table.schema:
        qualified_name = f"\"{table.schema}\".\"{table.name}\""
    else:
        qualified_name = f"\"{table.name}\""
    try:
        # Prefer deterministic ordering by id when available so admins see newest rows first.
        if "id" in table.c:
            query = sql_text(
                f"SELECT * FROM {qualified_name} ORDER BY \"id\" {order.upper()} LIMIT :limit OFFSET :offset"
            )
        else:
            query = sql_text(f"SELECT * FROM {qualified_name} LIMIT :limit OFFSET :offset")
        result = db.execute(query, {"limit": limit, "offset": offset})
        rows = result.mappings().all()
        return [dict(row) for row in rows]
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


@api_router.get("/admin/system-config", response_model=List[SystemConfigEntry])
async def admin_list_system_config(session: Session = Depends(get_session)):
    """Admin only: fetch the entire system configuration table."""
    rows = session.exec(select(SystemConfig)).all()
    return [SystemConfigEntry(key=row.key, value=row.value, description=row.description) for row in rows]


@api_router.post("/admin/system-config")
async def admin_update_system_config(req: SystemConfigUpdateRequest, session: Session = Depends(get_session)):
    """Admin only: persist updated system configuration entries."""
    updated = 0
    for entry in req.entries:
        row = session.get(SystemConfig, entry.key)
        if row:
            row.value = entry.value
            if entry.description is not None:
                row.description = entry.description
        else:
            row = SystemConfig(key=entry.key, value=entry.value, description=entry.description)
            session.add(row)
        updated += 1
    session.commit()
    return {"ok": True, "updated": updated}

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

@api_router.get("/admin/prompts")
async def admin_get_prompts_removed():
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.get("/admin/prompts/{template_id}/versions")
async def admin_get_prompt_versions_removed(template_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.post("/admin/prompts/{template_id}/save")
async def admin_save_prompt_removed(template_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.post("/admin/prompts/versions/{version_id}/deploy")
async def admin_deploy_prompt_removed(version_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

# --- Prompt Registry (DB-backed) ---

class RegistryPromptItem(BaseModel):
    prompt_id: str
    tier: Optional[str]
    mode: str
    role: str
    version: int
    is_active: bool
    content: Optional[str] = None
    updated_at: str
    updated_by: Optional[str]

class RegistrySchemaItem(BaseModel):
    schema_id: str
    version: int
    is_active: bool
    content: Optional[Dict[str, Any]] = None
    updated_at: str
    updated_by: Optional[str]

class RegistryBindingItem(BaseModel):
    id: str
    tier: str
    mode: str
    global_system_prompt_id: str
    developer_prompt_id: str
    output_schema_id: str
    is_active: bool
    updated_at: str
    updated_by: Optional[str]

class RegistryBindingAuditIssue(BaseModel):
    type: str
    tier: Optional[str] = None
    mode: Optional[str] = None
    binding_id: Optional[str] = None
    prompt_id: Optional[str] = None
    schema_id: Optional[str] = None

class RegistryBindingAuditReport(BaseModel):
    ok: bool
    active_bindings: int
    active_binding_pairs: int
    issues: List[RegistryBindingAuditIssue]

class PromptRegistryUpdateRequest(BaseModel):
    content: str
    tier: Optional[str] = None
    mode: str
    role: str
    updated_by: Optional[str] = None

class SchemaRegistryUpdateRequest(BaseModel):
    content: Dict[str, Any]
    updated_by: Optional[str] = None

class RegistryRollbackRequest(BaseModel):
    version: int
    updated_by: Optional[str] = None

class BindingActivateRequest(BaseModel):
    tier: str
    mode: str
    global_system_prompt_id: str
    developer_prompt_id: str
    output_schema_id: str
    updated_by: Optional[str] = None

class PromptRegistryTestRequest(BaseModel):
    tier: str
    mode: str
    question_payload: Dict[str, Any]
    context_payload: Dict[str, Any] = Field(default_factory=dict)
    runtime_hints: Dict[str, Any] = Field(default_factory=dict)

def _parse_tier(value: Optional[str]) -> Optional[PromptTierEnum]:
    if value is None:
        return None
    return PromptTierEnum(value.upper())

def _parse_mode(value: str) -> PromptModeEnum:
    return PromptModeEnum(value.upper())

def _parse_role(value: str) -> PromptRoleEnum:
    return PromptRoleEnum(value.upper())

@api_router.get("/admin/prompt-registry/prompts", response_model=List[RegistryPromptItem])
async def admin_list_prompt_registry_prompts(db: Session = Depends(get_session)):
    rows = db.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.is_active == True)
        .order_by(PromptTemplateEntry.prompt_id.asc())
    ).all()
    return [
        RegistryPromptItem(
            prompt_id=row.prompt_id,
            tier=row.tier.value if row.tier else None,
            mode=row.mode.value,
            role=row.role.value,
            version=row.version,
            is_active=row.is_active,
            content=None,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in rows
    ]

@api_router.get("/admin/prompt-registry/prompts/{prompt_id}/versions", response_model=List[RegistryPromptItem])
async def admin_list_prompt_registry_versions(prompt_id: str, db: Session = Depends(get_session)):
    rows = prompt_registry_service.get_prompt_versions(db, prompt_id)
    return [
        RegistryPromptItem(
            prompt_id=row.prompt_id,
            tier=row.tier.value if row.tier else None,
            mode=row.mode.value,
            role=row.role.value,
            version=row.version,
            is_active=row.is_active,
            content=row.content,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in rows
    ]

@api_router.post("/admin/prompt-registry/prompts/{prompt_id}/update", response_model=RegistryPromptItem)
async def admin_update_prompt_registry_prompt(prompt_id: str, req: PromptRegistryUpdateRequest, db: Session = Depends(get_session)):
    entry = prompt_registry_service.update_prompt(
        session=db,
        prompt_id=prompt_id,
        content=req.content,
        tier=_parse_tier(req.tier),
        mode=_parse_mode(req.mode),
        role=_parse_role(req.role),
        updated_by=req.updated_by,
    )
    return RegistryPromptItem(
        prompt_id=entry.prompt_id,
        tier=entry.tier.value if entry.tier else None,
        mode=entry.mode.value,
        role=entry.role.value,
        version=entry.version,
        is_active=entry.is_active,
        content=entry.content,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.post("/admin/prompt-registry/prompts/{prompt_id}/rollback", response_model=RegistryPromptItem)
async def admin_rollback_prompt_registry_prompt(prompt_id: str, req: RegistryRollbackRequest, db: Session = Depends(get_session)):
    entry = prompt_registry_service.rollback_prompt(db, prompt_id, req.version, req.updated_by)
    return RegistryPromptItem(
        prompt_id=entry.prompt_id,
        tier=entry.tier.value if entry.tier else None,
        mode=entry.mode.value,
        role=entry.role.value,
        version=entry.version,
        is_active=entry.is_active,
        content=entry.content,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.get("/admin/prompt-registry/schemas", response_model=List[RegistrySchemaItem])
async def admin_list_prompt_registry_schemas(db: Session = Depends(get_session)):
    rows = db.exec(
        select(JsonSchemaEntry)
        .where(JsonSchemaEntry.is_active == True)
        .order_by(JsonSchemaEntry.schema_id.asc())
    ).all()
    return [
        RegistrySchemaItem(
            schema_id=row.schema_id,
            version=row.version,
            is_active=row.is_active,
            content=None,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in rows
    ]

@api_router.get("/admin/prompt-registry/schemas/{schema_id}/versions", response_model=List[RegistrySchemaItem])
async def admin_list_prompt_registry_schema_versions(schema_id: str, db: Session = Depends(get_session)):
    rows = prompt_registry_service.get_schema_versions(db, schema_id)
    return [
        RegistrySchemaItem(
            schema_id=row.schema_id,
            version=row.version,
            is_active=row.is_active,
            content=row.content,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in rows
    ]

@api_router.post("/admin/prompt-registry/schemas/{schema_id}/update", response_model=RegistrySchemaItem)
async def admin_update_prompt_registry_schema(schema_id: str, req: SchemaRegistryUpdateRequest, db: Session = Depends(get_session)):
    error = prompt_registry_service.validate_schema(req.content)
    if error:
        raise HTTPException(status_code=400, detail=f"Invalid schema: {error}")
    entry = prompt_registry_service.update_schema(db, schema_id, req.content, req.updated_by)
    return RegistrySchemaItem(
        schema_id=entry.schema_id,
        version=entry.version,
        is_active=entry.is_active,
        content=entry.content,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.post("/admin/prompt-registry/schemas/{schema_id}/rollback", response_model=RegistrySchemaItem)
async def admin_rollback_prompt_registry_schema(schema_id: str, req: RegistryRollbackRequest, db: Session = Depends(get_session)):
    entry = prompt_registry_service.rollback_schema(db, schema_id, req.version, req.updated_by)
    return RegistrySchemaItem(
        schema_id=entry.schema_id,
        version=entry.version,
        is_active=entry.is_active,
        content=entry.content,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.get("/admin/prompt-registry/bindings", response_model=List[RegistryBindingItem])
async def admin_list_prompt_registry_bindings(db: Session = Depends(get_session)):
    rows = db.exec(select(PromptBinding).order_by(PromptBinding.updated_at.desc())).all()
    return [
        RegistryBindingItem(
            id=row.id,
            tier=row.tier.value,
            mode=row.mode.value,
            global_system_prompt_id=row.global_system_prompt_id,
            developer_prompt_id=row.developer_prompt_id,
            output_schema_id=row.output_schema_id,
            is_active=row.is_active,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in rows
    ]

@api_router.get("/admin/prompt-registry/audit", response_model=RegistryBindingAuditReport)
async def admin_prompt_registry_audit(db: Session = Depends(get_session)):
    report = prompt_registry_service.audit_active_bindings(db)
    return RegistryBindingAuditReport(
        ok=report.get("ok", False),
        active_bindings=report.get("active_bindings", 0),
        active_binding_pairs=report.get("active_binding_pairs", 0),
        issues=[RegistryBindingAuditIssue(**issue) for issue in report.get("issues", [])],
    )

@api_router.post("/admin/prompt-registry/bindings/activate", response_model=RegistryBindingItem)
async def admin_activate_prompt_registry_binding(req: BindingActivateRequest, db: Session = Depends(get_session)):
    entry = prompt_registry_service.activate_binding(
        session=db,
        tier=_parse_tier(req.tier),
        mode=_parse_mode(req.mode),
        global_system_prompt_id=req.global_system_prompt_id,
        developer_prompt_id=req.developer_prompt_id,
        output_schema_id=req.output_schema_id,
        updated_by=req.updated_by,
    )
    return RegistryBindingItem(
        id=entry.id,
        tier=entry.tier.value,
        mode=entry.mode.value,
        global_system_prompt_id=entry.global_system_prompt_id,
        developer_prompt_id=entry.developer_prompt_id,
        output_schema_id=entry.output_schema_id,
        is_active=entry.is_active,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.post("/admin/prompt-registry/test")
async def admin_prompt_registry_test(req: PromptRegistryTestRequest, db: Session = Depends(get_session)):
    try:
        result = await mode_execution_service.run(
            session=db,
            tier=PromptTierEnum(req.tier.upper()),
            mode=PromptModeEnum(req.mode.upper()),
            question_payload=req.question_payload,
            context_payload=req.context_payload,
            runtime_hints=req.runtime_hints,
            request_id=str(uuid.uuid4()),
        )
        return result
    except (ValueError, PromptRegistryError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModeExecutionError as e:
        return JSONResponse(status_code=e.status_code, content=e.payload)


@api_router.post("/admin/llm/circuit-breaker/reset")
async def admin_reset_llm_circuit_breaker(provider: str = Query("openai")):
    manager = get_llm_manager()
    try:
        result = manager.reset_circuit_breaker(provider)
        return result
    except LLMProviderError as e:
        detail = {
            "code": "LLM_PROVIDER_ERROR",
            "provider": e.provider,
            "details": str(e).strip() or repr(e),
        }
        if e.details:
            detail.update(e.details)
        raise HTTPException(status_code=400, detail=detail)

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

@api_router.get('/users/me/subscription', response_model=SubscriptionResponse)
async def get_my_subscription_v2(user_id: int = Query(...), session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail="User not found")
    subscription = subscription_service.get_or_create_subscription(session, user)
    if not subscription:
        raise HTTPException(status_code=500, detail="Subscription not available")
    plan = session.get(Plan, subscription.plan_id)
    if not plan:
        raise HTTPException(status_code=500, detail="Plan not available for subscription")

    credits_remaining = _sync_subscription_balance(subscription, plan, session)
    school_name = None
    if user.school_id:
        school = session.get(School, user.school_id)
        school_name = school.school_name if school else None
    return build_subscription_response(user, subscription, plan, credits_remaining, school_name=school_name)


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


# ========================================================================
# LOCAL FIND ERROR ENDPOINT (NO LLM)
# ========================================================================

@api_router.post("/find_error_local")
@limiter.limit("20/minute")
async def find_error_local(
    request: Request,
    file: UploadFile = File(...),
    selection_bbox_json: str = Form(...),
    max_lines: int = Form(6),
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    """
    Local error detection using Pix2Text + SymPy (NO OpenAI).
    
    Feature flag: FEATURE_LOCAL_FIND_ERROR (default: false)
    """
    from app.schemas.find_error_local_schemas import (
        FindErrorLocalResponse, SelectionBBox, OCRResult, AnalysisResult, TimingsMs
    )
    from app.services.math.error_localizer import analyze_error
    
    request_id = str(uuid.uuid4())
    start_time = time.time()
    timings = {"crop": 0, "ocr": 0, "parse": 0, "check": 0, "total": 0}
    
    # Feature flag check
    if not os.getenv("FEATURE_LOCAL_FIND_ERROR", "false").lower() == "true":
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            error={"code": "DISABLED", "message": "Local find error feature is disabled"},
            timings_ms=TimingsMs(**timings)
        )
    
    try:
        # Parse selection bbox
        selection_bbox = SelectionBBox(**json.loads(selection_bbox_json))
        
        # Read image
        t0 = time.time()
        image_bytes = await file.read()
        
        # Validate size
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                error={"code": "FILE_TOO_LARGE", "message": "Image exceeds 10MB"},
                timings_ms=TimingsMs(**timings)
            )
        
        # Load image and crop to selection
        img = Image.open(io.BytesIO(image_bytes))
        img_width, img_height = img.size
        
        # Convert normalized bbox to pixels
        x_px = int(selection_bbox.x * img_width)
        y_px = int(selection_bbox.y * img_height)
        w_px = int(selection_bbox.w * img_width)
        h_px = int(selection_bbox.h * img_height)
        
        # Clamp to image bounds
        x_px = max(0, min(x_px, img_width))
        y_px = max(0, min(y_px, img_height))
        w_px = max(1, min(w_px, img_width - x_px))
        h_px = max(1, min(h_px, img_height - y_px))
        
        # Check minimum size
        if w_px < 25 or h_px < 25:
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=selection_bbox,
                error={"code": "BBOX_TOO_SMALL", "message": "Selection too small (min 25x25 pixels)"},
                timings_ms=TimingsMs(**timings)
            )
        
        # Crop region
        cropped = img.crop((x_px, y_px, x_px + w_px, y_px + h_px))
        
        # Convert to bytes
        crop_buffer = io.BytesIO()
        cropped.save(crop_buffer, format='PNG')
        crop_bytes = crop_buffer.getvalue()
        
        timings["crop"] = int((time.time() - t0) * 1000)
        
        # OCR
        t1 = time.time()
        ocr_result = ocr_service.recognize_region(crop_bytes, engine_name="local")
        timings["ocr"] = int((time.time() - t1) * 1000)
        
        if not ocr_result.get("text"):
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=selection_bbox,
                ocr=OCRResult(**ocr_result),
                error={"code": "NO_TEXT", "message": "No text detected in selection"},
                timings_ms=TimingsMs(**timings)
            )
        
        # Analyze
        t2 = time.time()
        analysis = analyze_error(ocr_result["text"], max_lines=max_lines)
        timings["check"] = int((time.time() - t2) * 1000)
        timings["total"] = int((time.time() - start_time) * 1000)
        
        # Check confidence threshold
        if analysis["confidence"] < 0.3:
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=selection_bbox,
                ocr=OCRResult(**ocr_result),
                error={
                    "code": "LOW_CONFIDENCE",
                    "message": "Could not reliably parse the selection. Try re-selecting or typing manually."
                },
                timings_ms=TimingsMs(**timings)
            )
        
        return FindErrorLocalResponse(
            ok=True,
            request_id=request_id,
            selection_bbox=selection_bbox,
            ocr=OCRResult(**ocr_result),
            analysis=AnalysisResult(**analysis),
            timings_ms=TimingsMs(**timings)
        )
        
    except json.JSONDecodeError:
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            error={"code": "INVALID_BBOX", "message": "Invalid selection_bbox JSON"},
            timings_ms=TimingsMs(**timings)
        )
    except Exception as e:
        logging.exception("Local find error failed")
        timings["total"] = int((time.time() - start_time) * 1000)
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
            timings_ms=TimingsMs(**timings)
        )


# ------------------------------------------------------------------
# Production Billing Endpoints
# ------------------------------------------------------------------

class ImportRequest(BaseModel):
    asset_id: int
    source_type: str = "image" # image | pdf

class SolveSelectedRequest(BaseModel):
    extraction_id: Optional[int] = None # OCRArtifact ID
    selected_items: List[SolveBatchItem] # Reuse SolveBatchItem
    requested_mode: str = "minimal"
    
@api_router.post("/import", response_model=Dict[str, Any])
async def import_asset(
    req: ImportRequest,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_session)
):
    """
    Import an asset (Image/PDF), charge import credits, and run OCR.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    upload = session.get(Upload, req.asset_id)
    if not upload or upload.user_id != user.id:
        raise HTTPException(status_code=404, detail="Upload not found or access denied")
        
    # 1. Charge Credits
    action_type = "image_import" if req.source_type == "image" else "pdf_import"
    
    # Process transaction (deducts credits)
    ledger = billing_service.process_transaction(
        session, 
        user_id, 
        action_type, 
        source_asset_id=str(req.asset_id)
    )
    
    if not ledger.ok:
        raise HTTPException(
            status_code=402, 
            detail=f"Insufficient credits for {req.source_type} import. Cost: {ledger.credits_charged}"
        )
        
    # 2. Run OCR (Optimistic: Refund if fails)
    try:
        if not os.path.exists(upload.storage_url):
             raise ValueError("File not found on disk")
             
        # Read file bytes
        async with aiofiles.open(upload.storage_url, "rb") as f:
            content = await f.read()
            
        # Call extraction
        result = await _call_extract_questions(
            session=session,
            image_bytes=content,
            max_output_tokens=4000, 
            engine_choice="lmm" 
        )
        
        # 3. Persist Artifact (Using Cache for now as per plan)
        extraction_cache = OcrExtractionCache(
            cache_key=f"import_{user_id}_{req.asset_id}_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            result_json=result,
            meta={"source": "billing_import", "ledger_id": ledger.id}
        )
        session.add(extraction_cache)
        session.commit()
        session.refresh(extraction_cache)
        
        return {
            "extraction_id": extraction_cache.id,
            "blocks": result.get("payload", {}).get("questions", []),
            "cost": ledger.credits_charged,
            "ledger_id": ledger.id
        }

    except Exception as e:
        # Refund on failure
        billing_service.refund_transaction(session, ledger.id, reason=f"Import failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@api_router.post("/solve_selected", response_model=Dict[str, Any])
async def solve_selected(
    req: SolveSelectedRequest,
    user_id: int = Query(..., description="User ID"),
    session: Session = Depends(get_session)
):
    """
    Solve specific selected questions, charging per question.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    results = []
    
    # Iterate and charge
    for item in req.selected_items:
        mode = item.requested_mode or req.requested_mode
        action_type = "solve_tutor" if mode == "detailed" else "solve_quick"
        
        # Idempotency Key
        op_id_raw = f"{user_id}_{req.extraction_id}_{item.question_id}_{mode}"
        op_id = hashlib.sha256(op_id_raw.encode()).hexdigest()
        
        # 1. Charge
        ledger = billing_service.process_transaction(
            session,
            user_id,
            action_type,
            question_id=item.question_id,
            request_id=op_id
        )
        
        if not ledger.ok:
            results.append({
                "question_id": item.question_id,
                "ok": False,
                "error": "Insufficient credits"
            })
            continue
            
        # 2. Solve (Call internal solver)
        try:
             # Construct minimal context request
             solve_req = SolveRequest(
                 text_query=item.text,
                 requested_mode=mode,
                 user_id=user_id,
                 mode="solve"
             )
             
             solve_resp = await solver_service.solve(solve_req, session=session)
             
             results.append({
                 "question_id": item.question_id,
                 "ok": True,
                 "solution": solve_resp.solution,
                 "cost": ledger.credits_charged
             })
             
        except Exception as e:
            # Refund
            billing_service.refund_transaction(session, ledger.id, reason=f"Solve failed: {str(e)}")
            results.append({
                "question_id": item.question_id,
                "ok": False,
                "error": str(e)
            })
            
    return {
        "ok": True,
        "results": results,
        "total_charged": sum(r.get("cost", 0) for r in results if r.get("ok"))
    }


# ============================================================================
# WHATSAPP BOT ENDPOINTS
# ============================================================================

class WhatsAppMessageRequest(BaseModel):
    from_number: str = Field(..., alias="from")
    text: str = ""
    hasImage: bool = False
    timestamp: str
    message_id: Optional[str] = None
    upload_id: Optional[str] = None

@api_router.get("/admin/whatsapp/status")
async def get_whatsapp_status():
    """Get current WhatsApp bot status"""
    return whatsapp_service.get_status()

@api_router.post("/admin/whatsapp/initialize")
async def initialize_whatsapp_bot():
    """Initialize WhatsApp bot and generate QR code"""
    return await whatsapp_service.initialize()

@api_router.post("/admin/whatsapp/disconnect")
async def disconnect_whatsapp_bot():
    """Disconnect WhatsApp bot"""
    return await whatsapp_service.disconnect()

@api_router.get("/admin/whatsapp/ocr-state")
async def get_whatsapp_ocr_state(
    request: Request,
    phone: Optional[str] = None,
    upload_id: Optional[str] = None,
):
    """
    Internal-only diagnostics endpoint for WhatsApp OCR state.
    """
    expected_key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")
    provided_key = request.headers.get("X-UASK-INTERNAL-KEY", "")
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    state = get_ocr_state(phone) if phone else None
    upload = get_upload_meta(upload_id) if upload_id else None
    return {
        "ocr_state": state,
        "upload_meta": upload,
        "whatsapp_ocr_enabled": os.getenv("WHATSAPP_OCR_ENABLED", "false"),
        "whatsapp_solver_v3_enabled": os.getenv("WHATSAPP_SOLVER_V3_ENABLED", "false"),
    }

@api_router.get("/admin/whatsapp/diag")
async def whatsapp_diag(request: Request):
    """
    Internal diagnostics for WhatsApp OCR flow.
    """
    expected_key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")
    provided_key = request.headers.get("X-UASK-INTERNAL-KEY", "")
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    send_url = os.environ.get("WHATSAPP_INTERNAL_SEND_URL", "http://orchestrator:8791/send")
    send_ok = False
    send_status = None
    try:
        resp = requests.get(send_url, timeout=2)
        send_status = resp.status_code
        send_ok = resp.status_code in (400, 404, 405)
    except Exception as e:
        send_status = str(e)

    return {
        "bot_status": whatsapp_service.get_status(),
        "send_url": send_url,
        "send_reachable": send_ok,
        "send_status": send_status,
        "whatsapp_ocr_enabled": os.getenv("WHATSAPP_OCR_ENABLED", "false"),
        "whatsapp_solver_v3_enabled": os.getenv("WHATSAPP_SOLVER_V3_ENABLED", "false"),
    }

@api_router.get("/admin/whatsapp/monitor")
async def whatsapp_monitor(request: Request, limit: int = 50, phone: Optional[str] = None, direction: Optional[str] = None):
    """
    Admin monitor: recent WhatsApp events + Celery queue length.
    """
    expected_key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")
    provided_key = request.headers.get("X-UASK-INTERNAL-KEY", "")
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    queue_len = None
    queue_len_whatsapp = None
    try:
        queue_len = get_redis().llen("celery")
        queue_len_whatsapp = get_redis().llen("whatsapp")
    except Exception:
        queue_len = None
        queue_len_whatsapp = None

    return {
        "bot_status": whatsapp_service.get_status(),
        "queue_length": queue_len,
        "queue_length_whatsapp": queue_len_whatsapp,
        "events": get_whatsapp_events(limit=limit, phone=phone, direction=direction),
        "server_time": datetime.utcnow().isoformat() + "Z",
    }

@api_router.get("/admin/whatsapp/monitor/export")
async def whatsapp_monitor_export(request: Request, limit: int = 200, phone: Optional[str] = None, direction: Optional[str] = None):
    expected_key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")
    provided_key = request.headers.get("X-UASK-INTERNAL-KEY", "")
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    events = get_whatsapp_events(limit=limit, phone=phone, direction=direction)
    rows = ["timestamp,direction,type,from,to,message_id,upload_id,ok,text,error"]
    for e in events:
        row = [
            str(e.get("timestamp", "")),
            str(e.get("direction", "")),
            str(e.get("type", "")),
            str(e.get("from", "")),
            str(e.get("to", "")),
            str(e.get("message_id", "")),
            str(e.get("upload_id", "")),
            str(e.get("ok", "")),
            str(e.get("text", "")).replace("\\n", " ").replace(",", " "),
            str(e.get("error", "")).replace("\\n", " ").replace(",", " "),
        ]
        rows.append(",".join(row))

    content = "\n".join(rows)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=whatsapp_monitor.csv"},
    )

@api_router.get("/admin/whatsapp/monitor/stream")
async def whatsapp_monitor_stream(request: Request):
    expected_key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")
    provided_key = request.headers.get("X-UASK-INTERNAL-KEY", "")
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async def event_generator():
        pubsub = get_redis().pubsub()
        pubsub.subscribe("whatsapp:events:stream")
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"
                await asyncio.sleep(0.1)
        finally:
            try:
                pubsub.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@api_router.post("/whatsapp/media")
async def upload_whatsapp_media(
    request: Request,
    file: UploadFile = File(...),
    from_number: str = Form(..., alias="from"),
    message_id: Optional[str] = Form(None),
    timestamp: Optional[str] = Form(None),
    mime_type: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
):
    """
    Internal-only media upload for WhatsApp image OCR.
    Stores bytes to disk and returns an upload_id.
    """
    expected_key = os.environ.get("WHATSAPP_INTERNAL_KEY", "")
    provided_key = request.headers.get("X-UASK-INTERNAL-KEY", "")
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Limit to 10MB
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")

    storage_dir = os.path.join("storage", "whatsapp_uploads")
    os.makedirs(storage_dir, exist_ok=True)

    upload_id = create_upload_id()
    ext = os.path.splitext(file.filename or "")[1].lower() if file.filename else ""
    if not ext:
        if mime_type and "jpeg" in mime_type:
            ext = ".jpg"
        elif mime_type and "png" in mime_type:
            ext = ".png"
        elif mime_type and "webp" in mime_type:
            ext = ".webp"
        else:
            ext = ".png"

    file_path = os.path.join(storage_dir, f"{upload_id}{ext}")
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    set_upload_meta(
        upload_id,
        {
            "path": file_path,
            "from": from_number,
            "message_id": message_id,
            "timestamp": timestamp,
            "mime_type": mime_type or file.content_type or "image/png",
            "caption": caption or "",
        },
    )

    return {"upload_id": upload_id}

@api_router.post("/whatsapp/message")
async def handle_whatsapp_message(
    request: WhatsAppMessageRequest,
    db: Session = Depends(get_session)
):
    """
    Handle incoming WhatsApp message
    Verify user, process math problem, and return solution
    """
    from_number = request.from_number
    normalized_number = _normalize_whatsapp_number(from_number)
    text = request.text.strip()
    has_image = request.hasImage
    message_id = request.message_id
    upload_id = request.upload_id
    whatsapp_ocr_enabled = os.getenv("WHATSAPP_OCR_ENABLED", "false").lower() == "true"
    whatsapp_latex_enabled = os.getenv("WHATSAPP_LATEX_RENDER_ENABLED", "false").lower() == "true"

    log_whatsapp_event({
        "direction": "in",
        "type": "image" if has_image else "text",
        "from": from_number,
        "text": text,
        "message_id": message_id,
        "upload_id": upload_id,
    })

    # Dedupe by message_id to avoid double-processing
    if not mark_dedupe(message_id):
        return {"reply": ""}
    
    # Check if this is a verification code (handle this first, before checking user)
    if text.upper().startswith("CODE "):
        code = text[5:].strip().upper()
        # Find user by verification code
        user = db.exec(
            select(User).where(User.whatsapp_secret == code)
        ).first()
        
        if user:
            # Link the phone number to this user
            user.whatsapp_number = normalized_number
            db.add(user)
            db.commit()
            return {
                "reply": "✅ Verification successful!\n\nYou can now send me your math problems, and I'll help you solve them step by step.\n\nYou can:\n• Send text problems\n• Send photos of math problems\n• Ask follow-up questions"
            }
        else:
            return {
                "reply": "❌ Invalid verification code. Please check your code in Settings → Preferences and try again."
            }
    
    # Check if user is already verified for this number
    user = db.exec(
        select(User).where(
            or_(
                User.whatsapp_number == from_number,
                User.whatsapp_number == normalized_number,
            )
        )
    ).first()
    
    if not user:
        # User not linked - ask for verification code
        return {
            "reply": "👋 Welcome to uask.ai Math Tutor!\n\nTo use this service, please send me your WhatsApp verification code.\n\nYou can find your code in:\nSettings → Preferences → WhatsApp Code\n\nFormat: CODE your-code-here"
        }
    
    # Check if user has active subscription status
    if user.subscription_status != "active":
        return {
            "reply": "⚠️ Your account is not active. Please check your subscription at uask.ai"
        }
    
    # Get or create subscription for the user
    try:
        subscription = subscription_service.get_or_create_subscription(db, user)
    except Exception as e:
        print(f"[WhatsApp] Error getting subscription: {e}")
        return {
            "reply": "⚠️ There was an error checking your subscription. Please try again or visit uask.ai"
        }
    
    # Handle OCR confirmation state if present
    ocr_state = get_ocr_state(from_number)
    if ocr_state and ocr_state.get("state") == "OCR_PENDING_CONFIRMATION":
        normalized = text.strip()
        upper = normalized.upper()

        if upper == "1":
            clear_ocr_state(from_number)
            extracted = ocr_state.get("extracted_text", "")
            celery_app.send_task("whatsapp_solve", args=[user.id, from_number, extracted, ocr_state.get("upload_id"), message_id])
            return {"reply": "Got it! Solving now..."}
        if upper == "2":
            clear_ocr_state(from_number)
            return {"reply": "Okay - please resend a clearer photo (crop to the question)."}
        if upper.startswith("EDIT:"):
            edited = normalized[5:].strip()
            if not edited:
                return {"reply": "Please provide your correction after `EDIT:`."}
            clear_ocr_state(from_number)
            celery_app.send_task("whatsapp_solve", args=[user.id, from_number, edited, ocr_state.get("upload_id"), message_id])
            return {"reply": "Thanks! Solving your corrected question now..."}
        if upper == "CANCEL":
            clear_ocr_state(from_number)
            return {"reply": "Cancelled. Send a new photo any time."}

        return {
            "reply": "Please reply with:\n1 = Correct\n2 = Not correct (resend photo)\nEDIT: <corrected question>\nCANCEL"
        }

    if whatsapp_latex_enabled and text and handle_navigation(from_number, text):
        return {"reply": ""}

    # If image upload_id is provided and OCR is enabled, enqueue OCR extraction
    if upload_id and whatsapp_ocr_enabled:
        celery_app.send_task("whatsapp_ocr_extract", args=[upload_id, user.id, from_number, message_id])
        return {"reply": "Received your image. Reading it now..."}

    # If message has an image, we need to process it with OCR
    problem_text = text
    if has_image:
        # In a real implementation, we would:
        # 1. Download the image from WhatsApp
        # 2. Process it with OCR service
        # 3. Extract the math problem
        # For now, we'll acknowledge the image and ask for text
        if not text:
            return {
                "reply": "📸 I see you sent an image! Unfortunately, I'm still learning to read images from WhatsApp.\n\nFor now, please:\n1. Type out your math problem, or\n2. Use the web app at uask.ai for full photo support\n\nI'll be able to read photos soon! 🔜"
            }
        problem_text = f"[Image received] {text}"
    
    # Process the math problem
    try:
        # Get WhatsApp-specific prompt
        from app.utils import get_active_prompt
        system_prompt = get_active_prompt("whatsapp-solver", db)
        
        if not system_prompt:
            # Fallback prompt
            system_prompt = """You are a WhatsApp math tutor. Solve the problem step-by-step.
Keep responses concise and mobile-friendly. Use simple formatting.
Format: Problem → Steps → Final Answer"""
        
        # Use solver service
        result = await solver_service.solve_problem(problem_text, "", db)
        
        # Format response for WhatsApp
        reply = "*Problem:* " + text + "\n\n"
        
        # Extract solution data (solver returns nested structure)
        solution = result.get("solution", {})
        steps = solution.get("steps", [])
        final_answer = solution.get("final_answer", "")
        
        if steps:
            reply += "*Solution:*\n"
            for i, step in enumerate(steps, 1):
                title = step.get("title", f"Step {i}")
                reply += f"\n*{i}. {title}*\n"
                explanation = step.get("explanation", "")
                if explanation:
                    # Truncate long explanations for WhatsApp
                    if len(explanation) > 200:
                        explanation = explanation[:197] + "..."
                    reply += explanation + "\n"
        
        if final_answer:
            reply += f"\n✅ *Answer:* {final_answer}"
        
        # Add helpful footer
        reply += "\n\n💡 _Need more help? Visit uask.ai_"
        
        # Log usage
        usage_log = UsageLog(
            user_id=user.id,
            action_type="whatsapp_solve",
            tokens_used=len(problem_text.split()) + len(reply.split())
        )
        db.add(usage_log)
        db.commit()
        
        send_whatsapp_logo(from_number)
        return {"reply": reply}
        
    except Exception as e:
        print(f"[WhatsApp] Error processing message: {e}")
        return {
            "reply": "❌ Sorry, I encountered an error processing your problem. Please try again or contact support at uask.ai"
        }
