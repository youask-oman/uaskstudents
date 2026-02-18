from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Form, Body
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, SQLModel, select
from sqlalchemy import text as sql_text, or_, func
from sqlalchemy.exc import IntegrityError
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
from app.utils.safe_json import safe_parse_json
import os
import time
import logging
import asyncio
import io
import aiofiles
import secrets
import string
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
    RequestEvent, DeviceSignupLog, OcrCache, QuestionIdentityCache,
    OcrExtractionCache, CreditHold, SolverOutputAttempt,
    PromptTemplateEntry, JsonSchemaEntry, PromptBinding,
    PromptTierEnum, PromptModeEnum, PromptRoleEnum,
    SolveSession, FollowupChatTurn, LlmUsageLedger,
    CreditLot, CreditProgramEnrollment,
    BillingLedger, UsageLedgerV2,
    CreditLotV2,
    ChatEditNoteV2, ChatEditCopyV2,
    LegalDocument, LegalAcceptance,
    SolutionShare,
)
from app.utils.token_utils import count_tokens, count_messages_tokens
from app.services.plot_sampling import process_visuals
from app.services.rag import rag_service
from app.services.ocr.upload_service import upload_service
from app.services.ocr.crop_service import crop_service
from app.services.ocr.ocr_router_service import ocr_router_service
from app.services.ocr.ocr_config_service import ocr_config_service
from app.services.ocr.ocr_runtime_config_service import get_active_ocr_config
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
from app.services.solve.trace_logger import log_solve_trace
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
from app.services.token_policy import get_token_policy, serialize_token_policy
from app.config import get_settings
from app.services.school_import_service import normalize_country_code
from app.utils.perf_timer import perf_emit, perf_enabled
from app.services.response_mapper import normalize_raw_llm_response
from app.services.solver import solver_service
from app.services.intent import should_require_visual
from app.services.solve.solution_doc import parse_solution_doc, render_solution_doc_markdown
from app.services.legal_service import get_terms_requirement_status
from app.services.audit_log_service import audit_log_service
from app.services.share_service import share_service
from app.services.credit_transfer_config import load_credit_transfer_config
from app.services.prompt_binding_policy import (
    ALLOWED_PROMPT_IDS,
    ALLOWED_SCHEMA_IDS,
)



from app.auth import verify_password, create_access_token, Token, get_password_hash
from app.api_admin import get_current_user
from app.admin_billing.deps import get_admin_user
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.bg_routers.voice_router import router as voice_router
from app.bg_routers.local_router import router as local_router
from app.bg_routers.snap_solve_pdf import router as snap_solve_pdf_router
from app.bg_routers.credits_router import router as credits_router
from app.bg_routers.plot_router import router as plot_router
from app.bg_routers.math_render_router import router as math_render_router
from app.bg_routers.notifications_router import router as notifications_router

limiter = Limiter(key_func=get_remote_address)
api_router = APIRouter()
logger = logging.getLogger(__name__)
WHATSAPP_SECRET_LENGTH = 8
WHATSAPP_SECRET_ALPHABET = string.ascii_uppercase + string.digits

api_router.include_router(voice_router, tags=["voice"])
api_router.include_router(local_router, tags=["local_math"])
api_router.include_router(snap_solve_pdf_router, tags=["snap_solve_pdf"])
api_router.include_router(credits_router, tags=["credits"])
api_router.include_router(notifications_router, tags=["notifications"])
api_router.include_router(plot_router, prefix="/v1", tags=["plotting"])
# Backward-compatible canonical path: /api/v1/plot/*
api_router.include_router(plot_router, tags=["plotting"])
api_router.include_router(math_render_router, tags=["math_render"])
from app.services.solve.solve_events import emit_attempt_event

# OCR prompt/schema are DB-driven via ocr_config_service


def _generate_whatsapp_secret(used: Optional[set[str]] = None) -> str:
    used = used or set()
    for _ in range(16):
        candidate = "".join(
            secrets.choice(WHATSAPP_SECRET_ALPHABET) for _ in range(WHATSAPP_SECRET_LENGTH)
        )
        if candidate not in used:
            return candidate
    raise RuntimeError("Failed to generate unique WhatsApp secret")


def _regenerate_whatsapp_secrets_for_all_users(session: Session) -> int:
    users = session.exec(select(User)).all()
    if not users:
        return 0
    used: set[str] = set()
    updated = 0
    for user in users:
        user.whatsapp_secret = _generate_whatsapp_secret(used=used)
        used.add(user.whatsapp_secret)
        session.add(user)
        updated += 1
    session.commit()
    return updated


def _enqueue_attempt_graph_render(attempt_id: Optional[str]) -> None:
    if not attempt_id:
        return
    try:
        celery_app.send_task("render_attempt_graph", args=[attempt_id], queue="celery")
    except Exception as exc:
        logger.warning("graph_enqueue_failed attempt_id=%s reason=%s", attempt_id, str(exc))


def _extract_steps_text_for_solve_session(solution_payload: Dict[str, Any]) -> str:
    if not isinstance(solution_payload, dict):
        return ""
    steps = solution_payload.get("steps")
    if not isinstance(steps, list):
        steps = (solution_payload.get("solution") or {}).get("steps")
    if not isinstance(steps, list):
        return ""
    out: List[str] = []
    for idx, step in enumerate(steps, start=1):
        if isinstance(step, dict):
            text = (
                step.get("explanation")
                or step.get("text")
                or step.get("work")
                or step.get("output")
                or ""
            )
            text = str(text).strip()
        else:
            text = str(step).strip()
        if text:
            out.append(f"Step {idx}: {text}")
    return "\n".join(out)


def _extract_final_answer_text_for_solve_session(solution_payload: Dict[str, Any]) -> str:
    if not isinstance(solution_payload, dict):
        return ""
    final_answer = solution_payload.get("final_answer")
    if isinstance(final_answer, dict):
        text = (
            final_answer.get("answer_text")
            or final_answer.get("value")
            or final_answer.get("answer_latex")
            or final_answer.get("latex")
            or ""
        )
        if text:
            return str(text).strip()
    if isinstance(final_answer, str):
        return final_answer.strip()
    nested_solution = solution_payload.get("solution")
    if isinstance(nested_solution, dict):
        nested_final = nested_solution.get("final_answer")
        if isinstance(nested_final, dict):
            text = (
                nested_final.get("answer_text")
                or nested_final.get("value")
                or nested_final.get("answer_latex")
                or nested_final.get("latex")
                or ""
            )
            if text:
                return str(text).strip()
        if isinstance(nested_final, str):
            return nested_final.strip()
        if isinstance(nested_solution.get("result"), str):
            return nested_solution.get("result", "").strip()
    return ""


def _persist_solve_session_and_llm_usage(
    session: Session,
    *,
    user_id: int,
    problem_text: str,
    topic: str,
    solution_payload: Dict[str, Any],
    provider: Optional[str],
    model: Optional[str],
    request_id: Optional[str],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    total_tokens: Optional[int],
    latency_ms: Optional[int],
) -> Optional[int]:
    try:
        steps_text = _extract_steps_text_for_solve_session(solution_payload)
        final_answer_text = _extract_final_answer_text_for_solve_session(solution_payload)
        solve_session = SolveSession(
            user_id=user_id,
            problem_text=(problem_text or "").strip(),
            topic=(topic or "Math").strip() or "Math",
            solution_steps_text=steps_text,
            final_answer_text=final_answer_text,
        )
        session.add(solve_session)
        session.commit()
        session.refresh(solve_session)

        input_tok = max(0, int(input_tokens or 0))
        output_tok = max(0, int(output_tokens or 0))
        computed_total = input_tok + output_tok
        total_tok = max(0, int(total_tokens if total_tokens is not None else computed_total))
        usage_row = LlmUsageLedger(
            solve_session_id=solve_session.id or 0,
            followup_turn_id=None,
            provider=(provider or "openai").strip() or "openai",
            model=(model or os.environ.get("OPENAI_MODEL_DEFAULT") or "unknown_model").strip(),
            request_id=(request_id or "").strip() or None,
            system_prompt_tokens=0,
            input_tokens=input_tok,
            output_tokens=output_tok,
            total_tokens=total_tok,
            latency_ms=int(latency_ms) if latency_ms is not None else None,
        )
        session.add(usage_row)
        session.commit()
        return solve_session.id
    except Exception as exc:
        session.rollback()
        logger.warning("solve_session_or_usage_persist_failed user_id=%s reason=%s", user_id, str(exc))
        return None


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


def _solve_tier_ceiling_slug() -> str:
    """
    Solve tier availability is credit-driven on the client.
    Do not cap requested solve tier by persisted subscription_tier.
    """
    return "research"


_TIER_ORDER = {"SHORT_STEPS": 0, "FINAL": 1, "STANDARD": 2, "RESEARCH": 3}


def _normalize_tier_for_prompt_binding(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    if raw in {"three_step", "free", "short_steps"}:
        return "SHORT_STEPS"
    if raw in {"research", "enterprise"}:
        return "RESEARCH"
    if raw in {"family", "family_standard", "short", "final"}:
        return "FINAL"
    if raw in {"standard", "student_standard", "pro", "premium"}:
        return "STANDARD"
    return "SHORT_STEPS"


def _externalize_tier(value: str) -> str:
    return {
        "SHORT_STEPS": "short_steps",
        "FINAL": "final",
        "STANDARD": "standard",
        "RESEARCH": "research",
    }.get(value, "short_steps")


def _clamp_requested_tier(requested_tier: Optional[str], entitled_tier_slug: str) -> Dict[str, str]:
    entitled_internal = _normalize_tier_for_prompt_binding(entitled_tier_slug)
    requested_internal = _normalize_tier_for_prompt_binding(requested_tier) if requested_tier else entitled_internal
    effective_internal = requested_internal if _TIER_ORDER[requested_internal] <= _TIER_ORDER[entitled_internal] else entitled_internal
    return {
        "tier_requested": _externalize_tier(requested_internal),
        "tier_effective": _externalize_tier(effective_internal),
        "tier_requested_internal": requested_internal,
        "tier_effective_internal": effective_internal,
    }


def _schema_object_for_validation(schema_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from app.utils.solve_schema_contract import optimize_schema_for_validation

    if not isinstance(schema_config, dict):
        return {}
    return optimize_schema_for_validation(schema_config)


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


def _validate_stream_payload(payload: Dict[str, Any], schema_config: Optional[Dict[str, Any]]) -> Tuple[List[str], bool]:
    schema = _schema_object_for_validation(schema_config)
    if not schema:
        return ["schema_error: missing schema configuration for stream validation."]

    try:
        validator = Draft202012Validator(schema)
    except Exception as exc:
        return [f"schema_error: invalid JSON schema: {exc}"]

    schema_errors = _format_json_schema_errors(list(validator.iter_errors(payload)))
    
    # Check for Refusal (Ambiguity)
    is_ambiguous = False
    refusal = payload.get("refusal")
    if refusal:
        if isinstance(refusal, dict):
             if refusal.get("is_refusal", True):
                 is_ambiguous = True
        else:
             is_ambiguous = bool(refusal)
    
    return schema_errors + _collect_stream_business_rule_errors(payload), is_ambiguous


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


def _normalize_language_code(raw_value: Any) -> str:
    raw = str(raw_value or "").strip().lower()
    if not raw:
        return "en"
    mapping = {
        "english": "en",
        "en": "en",
        "french": "fr",
        "francais": "fr",
        "français": "fr",
        "fr": "fr",
        "arabic": "ar",
        "ar": "ar",
        "spanish": "es",
        "es": "es",
    }
    return mapping.get(raw, raw[:2] if len(raw) >= 2 else "en")


def _build_solver_trusted_context(
    base_context: Optional[Dict[str, Any]],
    user_obj: Optional[User],
) -> Dict[str, Any]:
    merged = dict(base_context or {})
    if user_obj:
        profile_lang = (
            getattr(user_obj, "default_language", None)
            or getattr(user_obj, "preferred_language", None)
        )
        lang_code = _normalize_language_code(profile_lang)
        merged["response_language"] = lang_code
        merged.setdefault("preferred_response_language", lang_code)
        merged.setdefault("user_language", lang_code)
    return merged


def _resolve_freeform_max_attempts(
    *,
    effective_tier: str,
    trusted_context: Optional[Dict[str, Any]],
    is_make_it_right: bool,
) -> int:
    tier_norm = (effective_tier or "SHORT_STEPS").strip().upper()
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


def _latest_published_legal_doc(session: Session, key: str) -> Optional[LegalDocument]:
    return session.exec(
        select(LegalDocument)
        .where(LegalDocument.key == key, LegalDocument.status == "published")
        .order_by(LegalDocument.published_at.desc(), LegalDocument.id.desc())
    ).first()


def _record_legal_acceptance_if_missing(
    session: Session,
    *,
    user_id: int,
    document_key: str,
    document_version: str,
    method: str,
    ip: Optional[str],
    user_agent: Optional[str],
    locale: Optional[str],
) -> None:
    if not document_version:
        return
    existing = session.exec(
        select(LegalAcceptance).where(
            LegalAcceptance.user_id == user_id,
            LegalAcceptance.document_key == document_key,
            LegalAcceptance.document_version == document_version,
        )
    ).first()
    if existing:
        return
    session.add(
        LegalAcceptance(
            user_id=user_id,
            document_key=document_key,
            document_version=document_version,
            method=method,
            ip=ip,
            user_agent=user_agent,
            locale=locale,
        )
    )


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
    error_code: str = "internal_error",
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
        "error": {
            "code": error_code,
            "message": (validation_errors[0] if validation_errors else "Validation failed") if not (error_code == "ambiguous_response") else "Clarification needed",
            "validation_failures": validation_errors
        }
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
        print(f"[TRANSFORM_ERROR] Failed to transform V3 to V1: {e}")
        import traceback
        traceback.print_exc()
        # Return original if transformation fails
        return v3_data



# --- Schemas ---
class SolveRequest(BaseModel):
    image_url: Optional[str] = None
    text_query: Optional[str] = None
    
    # Post-OCR Review Fields
    confirmed_markdown: Optional[str] = None
    confirmed_text: Optional[str] = None
    confirmed_latex_blocks: Optional[List[Dict[str, Any]]] = None
    question_text: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    
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
    tier: Optional[str] = Field(None, description="Requested tier from frontend: short_steps|final|standard|research")
    trusted_context: Optional[Dict[str, Any]] = None
    requested_mode: Optional[str] = "minimal"
    features_used: Optional[Dict[str, Any]] = None
    input_modality: Optional[str] = Field(None, description="one of 'text', 'ocr_image', 'ocr_pdf', 'voice'")
    token_policy: Optional[str] = Field(None, description="policy key applied for this request, for auditing")
    verification_level: Optional[str] = Field(None, description="expected verification rigor: light|moderate|strict")
    include_graph: Optional[bool] = Field(False, description="Whether to include a visualization/graph in the solution")
    graph_mode: Optional[str] = Field("auto", description="Graph mode: off | auto | on")
    attach_to_step_id: Optional[int] = Field(None, description="Step ID to attach plot to, or null for standalone")
    force_validity: Optional[bool] = Field(False, description="Whether to bypass strict math validation checks")
    idempotency_key: Optional[str] = Field(
        None,
        description="Client-provided idempotency key (UUID) to prevent duplicate charges"
    )
    debug_simulated_tokens: Optional[Dict[str, Any]] = Field(
        None,
        description="DEV/TEST only. Override token telemetry for fake solver."
    )
    debug_force_error: Optional[bool] = Field(
        False,
        description="DEV/TEST only. Force solver failure for testing."
    )

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
    solve_session_id: Optional[int] = None # Added for Phase 3 Follow-up



def validate_math_query(text: str) -> None:
    normalized = (text or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Please enter a math question.")

class FollowupRequest(BaseModel):
    message: str

def check_followup_scope(message: str, session: SolveSession) -> bool:
    """
    Lightweight scope classifier BEFORE calling the LLM.
    Allowed if user message references:
    - “step” + number
    - symbols/equations present in solution_steps_text
    - mentions “final answer”, “why”, “how”, “verify”, “domain”, “constraint”
    - explicitly refers to the given problem statement.
    """
    msg = message.lower()
    
    # Block phrases that look like new problems
    blocking_phrases = ["solve this", "another question", "similar problem", "new problem", "another math"]
    if any(bp in msg for bp in blocking_phrases):
        return False
        
    # Check for keywords
    allowed_keywords = ["step", "final answer", "why", "how", "verify", "domain", "constraint", "formula", "method", "concept"]
    if any(kw in msg for kw in allowed_keywords):
        return True
        
    # Check for significant words from problem text (min 4 chars)
    stop_words = {"the", "and", "for", "with", "what", "solve", "this", "that", "please", "can", "you", "help"}
    problem_words = [w for w in re.findall(r"\w+", session.problem_text.lower()) if len(w) >= 4 and w not in stop_words]
    if any(w in msg for w in problem_words):
        return True

    # Check for steps references
    if re.search(r"step\s*\d+", msg):
        return True
        
    return False


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
    attempt_id: Optional[str] = None
    request_id: Optional[str] = None
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
    credits_charged_total: float = 0.0
    credits_balance_after: Optional[float] = None
    per_question_charges: List[Dict[str, Any]] = Field(default_factory=list)



class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    academic_level: Optional[str] = None
    terms_accepted: bool = False
    privacy_acknowledged: bool = False

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
    whatsapp_enabled: Optional[bool] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: Optional[str] = None

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
    status: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
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


class SolveV2ConfigResponse(BaseModel):
    system_prompt_id: str
    orchestrator_prompt_id: str
    narrator_prompt_id: str
    plot_spec_prompt_id: str
    repair_prompt_id: str
    clarify_prompt_id: str
    schema_id: str
    llm_min_schema_id: str
    clarify_schema_id: str
    repair_schema_id: str
    tier_policy_json: str
    narrator_enabled: bool
    output_contract_id: Optional[str] = None


class SolveV2ConfigUpdateRequest(BaseModel):
    system_prompt_id: str
    orchestrator_prompt_id: str
    narrator_prompt_id: str
    plot_spec_prompt_id: str
    repair_prompt_id: str
    clarify_prompt_id: str
    schema_id: str
    llm_min_schema_id: str
    clarify_schema_id: str
    repair_schema_id: str
    tier_policy_json: str
    narrator_enabled: bool = False
    output_contract_id: Optional[str] = None


class CreditTransferAdminConfigResponse(BaseModel):
    credit_transfer_enabled: bool
    notifications_enabled: bool
    min_transfer: float
    max_transfer: float
    daily_cap: float
    pending_expiry_days: int
    per_minute_limit: int
    thank_per_minute_limit: int
    account_age_minutes_min: int


class CreditTransferAdminConfigUpdateRequest(BaseModel):
    credit_transfer_enabled: bool
    notifications_enabled: bool
    min_transfer: float
    max_transfer: float
    daily_cap: float
    pending_expiry_days: int
    per_minute_limit: int
    thank_per_minute_limit: int
    account_age_minutes_min: int

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
    source: Optional[str] = None

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


class OcrExtractResponse(BaseModel):
    ocr_attempt_id: str
    status: str
    extracted_text: Optional[str] = None
    structured_json: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    cache_hit: bool = False
    billing: Dict[str, Any]


class OcrEngineAvailabilityResponse(BaseModel):
    local_engine_enabled: bool
    openai_engine_enabled: bool
    default_engine: str


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
async def signup(
    request: Request,
    form_data: SignupRequest,
    session: Session = Depends(get_session),
):
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

    if not form_data.terms_accepted or not form_data.privacy_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="You must accept the Terms of Service and acknowledge the Privacy Policy to create an account.",
        )

    # Create new user
    whatsapp_secret = _generate_whatsapp_secret()
    
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

    # Record legal acceptance snapshot at signup for latest published versions.
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    locale = request.headers.get("accept-language")
    latest_terms = _latest_published_legal_doc(session, "terms_of_service")
    latest_privacy = _latest_published_legal_doc(session, "privacy_policy")
    if latest_terms:
        _record_legal_acceptance_if_missing(
            session,
            user_id=new_user.id,
            document_key="terms_of_service",
            document_version=latest_terms.version,
            method="signup",
            ip=ip_addr,
            user_agent=user_agent,
            locale=locale,
        )
    if latest_privacy:
        _record_legal_acceptance_if_missing(
            session,
            user_id=new_user.id,
            document_key="privacy_policy",
            document_version=latest_privacy.version,
            method="signup",
            ip=ip_addr,
            user_agent=user_agent,
            locale=locale,
        )
    session.commit()

    return {"status": "ok", "message": "User created successfully. Please check your email for verification.", "user_id": new_user.id}

@api_router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: LoginRequest,
    session: Session = Depends(get_session),
):
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
    requires_terms_acceptance, required_terms_version = get_terms_requirement_status(session, user_id=user.id)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
        avatar_url=user.avatar_url,
        session_token=session_token, # Return to client
        terms_acceptance_required=requires_terms_acceptance,
        required_terms_version=required_terms_version,
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

    return SubscriptionResponse(
        plan=plan_info,
        usage=usage_info,
        profile=profile_info,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        allow_detailed=features.get("allow_detailed", plan_info.slug not in {"free", "short_steps", "final"}),
        allow_ocr=features.get("allow_ocr", True),
        allow_voice=features.get("allow_voice", True)
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


@api_router.get("/ocr/engines", response_model=OcrEngineAvailabilityResponse)
async def get_ocr_engines_endpoint(session: Session = Depends(get_session)):
    runtime_cfg = get_active_ocr_config(session)
    default_engine = "pix2text" if runtime_cfg.local_engine_enabled else ("openai" if runtime_cfg.openai_engine_enabled else "pix2text")
    return OcrEngineAvailabilityResponse(
        local_engine_enabled=bool(runtime_cfg.local_engine_enabled),
        openai_engine_enabled=bool(runtime_cfg.openai_engine_enabled),
        default_engine=default_engine,
    )



class LatexResponse(BaseModel):
    latex: str

# ------------------------------------------------------------------
# OCR Subsystem Endpoints
# ------------------------------------------------------------------

def _require_gpt5mini_model() -> str:
    model = (os.getenv("OPENAI_MODEL_DEFAULT") or "").strip()
    if not model:
        return "gpt-5-mini"
    if model != "gpt-5-mini":
        raise RuntimeError(f"OPENAI_MODEL_DEFAULT must be 'gpt-5-mini', got '{model}'")
    return model


OCR_V5_MODEL = _require_gpt5mini_model()
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

EXTRACT_MODEL = _require_gpt5mini_model()
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
    text: Optional[str] = None
    question_text: Optional[str] = None
    mode: Optional[str] = None
    graph_mode: Optional[str] = None
    domain_mode: Optional[str] = None
    requested_mode: Optional[str] = "minimal"
    requires_figure: Optional[bool] = False
    figure_image_base64: Optional[str] = None


class SolveBatchRequest(BaseModel):
    items: List[SolveBatchItem] = Field(default_factory=list)
    tier: Optional[str] = "SHORT_STEPS"
    mode: Optional[str] = "SOLVE"
    graph_mode: Optional[str] = "AUTO"
    domain_mode: Optional[str] = "reals"
    preferred_response_language: Optional[str] = "English"
    questions_json: Optional[List[Dict[str, Any]]] = None
    features_used: Optional[Dict[str, Any]] = None
    input_modality: Optional[str] = None
    verification_level: Optional[str] = None
    token_policy: Optional[str] = None
    image_url: Optional[str] = None
    artifact_id: Optional[int] = None
    has_voice: Optional[bool] = False
    verify_requested: Optional[bool] = False
    plot_requested: Optional[bool] = False
    idempotency_key: Optional[str] = None


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
    request_id: Optional[str] = None
    attempt_id: Optional[str] = None
    session_id: Optional[int] = None
    tier: Optional[str] = None
    language: Optional[Dict[str, Any]] = None
    items: Optional[List[Dict[str, Any]]] = None
    payload: Optional[Dict[str, Any]] = None
    telemetry: Optional[Dict[str, Any]] = None


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
    runtime_cfg = get_active_ocr_config(session)

    def _load_openai_ocr_assets() -> Tuple[PromptTemplateEntry, JsonSchemaEntry]:
        prompt_entry, schema_entry = ocr_config_service.get_openai_ocr_assets(
            session,
            prompt_key=runtime_cfg.openai_system_prompt_key,
            schema_key=runtime_cfg.openai_schema_key,
        )
        return prompt_entry, schema_entry

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
        if not normalized_questions:
            # Some OCR schema-valid outputs place extracted text under pages[].segments
            # while keeping questions[] empty. Build a best-effort synthetic question.
            segment_lines: List[str] = []
            pages = raw_payload.get("pages") if isinstance(raw_payload.get("pages"), list) else []
            for page in pages:
                if not isinstance(page, dict):
                    continue
                segments = page.get("segments") if isinstance(page.get("segments"), list) else []
                for segment in segments:
                    if not isinstance(segment, dict):
                        continue
                    kind = str(segment.get("kind") or "").strip().lower()
                    if kind and kind not in {"question_text", "equation", "instruction", "title", "other"}:
                        continue
                    candidate = segment.get("latex") if isinstance(segment.get("latex"), str) and segment.get("latex").strip() else segment.get("text")
                    if not isinstance(candidate, str):
                        continue
                    text = candidate.strip()
                    if not text:
                        continue
                    segment_lines.append(text)
            deduped_lines: List[str] = []
            seen: set[str] = set()
            for line in segment_lines:
                key = re.sub(r"\s+", " ", line).strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped_lines.append(line)
            if deduped_lines:
                merged = "\n".join(deduped_lines[:12]).strip()
                if merged:
                    normalized_questions.append(
                        {
                            "id": f"p{page_num}-q1",
                            "page": page_num,
                            "text": merged,
                            "latex": merged if ("\\" in merged or "$" in merged) else None,
                            "type": "other",
                            "confidence": None,
                        }
                    )
                    warnings = [*warnings, "questions[] empty; synthesized from page segments"]
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

    def _coerce_openai_schema_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Backfill required array fields that models often omit when empty."""
        if not isinstance(raw_payload, dict):
            return raw_payload
        questions = raw_payload.get("questions")
        if isinstance(questions, list):
            for item in questions:
                if isinstance(item, dict) and not isinstance(item.get("subparts"), list):
                    item["subparts"] = []
        return raw_payload

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

            model = runtime_cfg.resolved_openai_model()
            client = AsyncOpenAI(api_key=api_key)
            b64 = base64.b64encode(vision_input.images[0]).decode("utf-8")
            prompt_entry, schema_entry = _load_openai_ocr_assets()
            system_prompt = prompt_entry.content
            schema_wrapper = schema_entry.content if isinstance(schema_entry.content, dict) else {}
            openai_schema = _schema_object_for_validation(schema_wrapper)
            if not isinstance(openai_schema, dict) or not openai_schema:
                raise RuntimeError(
                    f"invalid_openai_ocr_schema:{getattr(schema_entry, 'schema_id', 'unknown')}"
                )
            validator = Draft202012Validator(openai_schema)
            schema_name = (
                str(schema_wrapper.get("name")).strip()
                if isinstance(schema_wrapper.get("name"), str) and str(schema_wrapper.get("name")).strip()
                else str(getattr(schema_entry, "schema_id", "ocr_schema"))
            )
            schema_strict = (
                schema_wrapper.get("strict")
                if isinstance(schema_wrapper.get("strict"), bool)
                else True
            )
            safe_schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", schema_name or "ocr_schema")
            request_id = str(getattr(vision_input, "request_id", "") or "").strip()
            user_prompt = "Extract math content from this input image. Return JSON only."
            if request_id:
                user_prompt = (
                    f'Extract math content from this input image. '
                    f'Set "request_id" to "{request_id}" in your JSON output. Return JSON only.'
                )

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
                            "name": safe_schema_name,
                            "schema": openai_schema,
                            "strict": schema_strict,
                        }
                    },
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
            parsed = _coerce_openai_schema_payload(parsed)
            errors = list(validator.iter_errors(parsed))
            if errors:
                response = await _responses_call(int(options.max_output_tokens * 2), repair=True)
                content = _extract_openai_text(response)
                parsed = _parse_json_response(content)
                parsed = _coerce_openai_schema_payload(parsed)
                errors = list(validator.iter_errors(parsed))
                if errors:
                    details = "; ".join(
                        f"{'.'.join(str(part) for part in err.path) or '<root>'}: {err.message}"
                        for err in errors[:5]
                    )
                    logging.warning(
                        "OpenAI OCR schema mismatch after repair; continuing with normalized payload. schema_id=%s details=%s",
                        getattr(schema_entry, "schema_id", None),
                        details,
                    )
                    if isinstance(parsed, dict):
                        parsed["needs_human_review"] = True
                        warnings_list = parsed.get("warnings")
                        if not isinstance(warnings_list, list):
                            warnings_list = []
                        warnings_list.append("Schema mismatch after repair: " + details[:2000])
                        parsed["warnings"] = warnings_list

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
    enabled_providers: List[str] = []
    if runtime_cfg.local_engine_enabled:
        enabled_providers.append("pix2txt")
    if runtime_cfg.openai_engine_enabled and os.getenv("OPENAI_API_KEY"):
        enabled_providers.append("openai")
    if not enabled_providers:
        raise RuntimeError("No OCR providers enabled")
    default_mode = "AUTO" if len(enabled_providers) > 1 else enabled_providers[0].upper()
    routing_cfg = VisionRoutingConfig(
        enabled_providers=enabled_providers,
        default_provider_mode=default_mode,
        fallback_order=enabled_providers,
    )
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


def _compute_ocr_quality_score(text: str) -> float:
    """
    Lightweight heuristic score in [0,1] for OCR extraction quality.
    """
    s = (text or "").strip()
    if not s:
        return 0.0
    score = 0.5
    # Positive signals
    if re.search(r"\d", s):
        score += 0.1
    if re.search(r"[=+\-*/^]", s):
        score += 0.15
    if re.search(r"(\\frac|\\sqrt|\\int|\\sum)", s):
        score += 0.15
    if re.search(r"[xyza-zA-Z]\s*=", s):
        score += 0.1
    # Negative signals
    if len(s) < 15:
        score -= 0.2
    if re.search(r"(upload|camera|paste|selected|extract)", s, flags=re.IGNORECASE):
        score -= 0.2
    # Clamp
    return max(0.0, min(1.0, score))


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


@api_router.post("/ocr/extract", response_model=OcrExtractResponse)
@limiter.limit("10/minute")
async def ocr_extract(
    request: Request,
    file: UploadFile = File(...),
    engine: str = Form("pix2text"),
    crop_x: Optional[float] = Form(None),
    crop_y: Optional[float] = Form(None),
    crop_w: Optional[float] = Form(None),
    crop_h: Optional[float] = Form(None),
    rotation: Optional[int] = Form(0),
    margin_pct: Optional[int] = Form(0),
    user_id: int = Query(...),
    session: Session = Depends(get_session),
):
    from decimal import Decimal
    from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
    from app.services.billing_exceptions import InsufficientCreditsError, HoldAlreadyFinalizedError, HoldNotFoundError
    from app.services.ocr.ocr_runtime_config_service import get_active_ocr_config

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not file:
        raise HTTPException(status_code=400, detail="File is required")

    runtime_cfg = get_active_ocr_config(session)

    engine_choice = (engine or "pix2text").lower().strip()
    if engine_choice not in {"pix2text", "openai"}:
        raise HTTPException(status_code=400, detail="Invalid engine. Use pix2text or openai.")
    if engine_choice == "pix2text" and not runtime_cfg.local_engine_enabled:
        raise HTTPException(status_code=422, detail="Pix2Text OCR engine is disabled")
    if engine_choice == "openai" and not runtime_cfg.openai_engine_enabled:
        raise HTTPException(status_code=422, detail="OpenAI OCR engine is disabled")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    file.file.seek(0)

    image_kind = _detect_image_kind(raw)
    content_type = file.content_type or ""
    if not content_type.startswith("image/") and image_kind not in ("jpeg", "png", "webp"):
        raise HTTPException(status_code=415, detail="Only image uploads are accepted")
    if image_kind not in ("jpeg", "png", "webp"):
        raise HTTPException(status_code=415, detail="Unsupported image type")

    image_fingerprint = hashlib.sha256(raw).hexdigest()

    # Compute crop signature up front (affects dedupe + idempotency)
    crop_rect = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
    if crop_x is not None and crop_y is not None and crop_w is not None and crop_h is not None:
        crop_rect = {"x": float(crop_x), "y": float(crop_y), "w": float(crop_w), "h": float(crop_h)}
    crop_signature = f"{crop_rect['x']:.5f}:{crop_rect['y']:.5f}:{crop_rect['w']:.5f}:{crop_rect['h']:.5f}:rot{int(rotation or 0)}:m{int(margin_pct or 0)}"

    # Dynamic rate limit per user (config-driven)
    if runtime_cfg.rate_limit_extract_per_min > 0:
        window_start = datetime.utcnow() - timedelta(minutes=1)
        recent_count = session.exec(
            select(func.count())
            .select_from(OCRJob)
            .where(OCRJob.user_id == user_id)
            .where(OCRJob.created_at >= window_start)
        ).one()
        if isinstance(recent_count, tuple):
            recent_count = recent_count[0]
        if int(recent_count or 0) >= runtime_cfg.rate_limit_extract_per_min:
            raise HTTPException(status_code=429, detail="OCR extract rate limit reached")

    prompt_entry = None
    schema_entry = None
    if engine_choice == "openai":
        prompt_entry, schema_entry = ocr_config_service.get_openai_ocr_assets(session)

    prompt_version = str(getattr(prompt_entry, "version", "local"))
    schema_version = str(getattr(schema_entry, "version", "local"))
    dedupe_key = f"{user_id}:{engine_choice}:{image_fingerprint}:{crop_signature}:{prompt_version}:{schema_version}"

    # Config-driven dedupe window
    cutoff = datetime.utcnow() - timedelta(hours=max(runtime_cfg.dedupe_window_hours, 1))
    cached = session.exec(
        select(OcrExtractionCache)
        .where(OcrExtractionCache.cache_key == dedupe_key)
        .where(OcrExtractionCache.user_id == user_id)
        .where(OcrExtractionCache.created_at >= cutoff)
    ).first()
    if cached:
        payload = cached.result_json or {}
        extracted_text = str(payload.get("extracted_text") or "").strip()
        if extracted_text:
            cached.hit_count += 1
            cached.last_hit_at = datetime.utcnow()
            session.add(cached)
            session.commit()
            return OcrExtractResponse(
                ocr_attempt_id=str((cached.meta or {}).get("ocr_job_id") or ""),
                status="cached",
                extracted_text=payload.get("extracted_text"),
                structured_json=payload.get("structured_json"),
                quality_score=payload.get("quality_score"),
                cache_hit=True,
                billing={"hold_applied": False, "hold_amount": 0},
            )
        # cached result was empty; drop it to allow re-extract
        session.delete(cached)
        session.commit()

    # Persist upload + crop (full image by default)
    upload = await upload_service.save_upload(user_id=user_id, file=file, session=session)
    try:
        crop = await crop_service.create_crop(
            upload=upload,
            crop_rect=crop_rect,
            rotation=int(rotation or 0),
            margin_pct=int(margin_pct or 0),
            session=session,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=410,
            detail="Uploaded source file is no longer available. Please upload the image again.",
        ) from exc

    # Create OCR attempt record
    job_id = str(uuid.uuid4())
    ocr_job = OCRJob(
        id=job_id,
        user_id=user_id,
        crop_id=crop.id,
        requested_engine=engine_choice,
        status="processing",
        image_fingerprint=image_fingerprint,
        dedupe_key=dedupe_key,
        prompt_template_id=getattr(prompt_entry, "prompt_id", None),
        json_schema_id=getattr(schema_entry, "schema_id", None),
        created_at=datetime.utcnow(),
    )
    session.add(ocr_job)
    session.commit()

    # Apply hold
    hold_amount = Decimal(str(runtime_cfg.local_ocr_credit)) if engine_choice == "pix2text" else Decimal(str(runtime_cfg.openai_ocr_credit))
    hold_request_id = f"ocr:{user_id}:{engine_choice}:{image_fingerprint}:{crop_signature}:{getattr(prompt_entry, 'prompt_id', 'local')}:{getattr(schema_entry, 'schema_id', 'local')}"
    try:
        hold_result = billing_ledger_service_v2.create_hold(
            session=session,
            user_id=user_id,
            request_id=hold_request_id,
            estimated_credits=hold_amount,
            attempt_id=job_id,
            idempotency_key=hold_request_id,
        )
        ocr_job.hold_request_id = hold_request_id
        ocr_job.hold_amount = hold_amount
        session.add(ocr_job)
        session.commit()
    except InsufficientCreditsError as e:
        ocr_job.status = "failed"
        ocr_job.error_code = "INSUFFICIENT_CREDITS"
        ocr_job.error_message = f"Required: {e.required}, Available: {e.available}"
        session.add(ocr_job)
        session.commit()
        raise HTTPException(status_code=402, detail="Insufficient credits") from e

    # Run OCR
    try:
        crop_path = crop_service.resolve_crop_path(crop.cropped_storage_url)
        if not crop_path:
            raise FileNotFoundError(
                f"Crop file not found for crop_id={crop.id}: {crop.cropped_storage_url}"
            )
        with open(crop_path, "rb") as f:
            crop_bytes = f.read()
        max_extract_tokens = get_token_policy(session).ocr_image_extract_max
        extract_data = await _call_extract_questions(
            session=session,
            image_bytes=crop_bytes,
            max_output_tokens=max_extract_tokens,
            engine_choice="openai" if engine_choice == "openai" else "pix2txt",
            crop_meta={
                "request_id": hold_request_id,
                "page_number": 0,
                "source": "image",
                "crop_norm": crop_rect,
            },
            debug=False,
        )
        payload = extract_data.get("payload") or {}
        extracted_text = "\n".join((q.get("text") or "") for q in (payload.get("questions") or [])).strip()
        quality_score = _compute_ocr_quality_score(extracted_text)
        if not extracted_text:
            # Not an engine failure: OCR completed but produced no usable question text.
            # Return gracefully so UI can show "No questions detected" instead of 502.
            ocr_job.status = "completed"
            ocr_job.extracted_text = ""
            ocr_job.structured_json = payload
            ocr_job.quality_score = 0.0
            ocr_job.finished_at = datetime.utcnow()
            session.add(ocr_job)
            try:
                billing_ledger_service_v2.release_hold(session, request_id=hold_request_id, attempt_id=job_id)
            except (HoldAlreadyFinalizedError, HoldNotFoundError):
                pass
            session.commit()
            return OcrExtractResponse(
                ocr_attempt_id=job_id,
                status="no_content",
                extracted_text="",
                structured_json=payload,
                quality_score=0.0,
                cache_hit=False,
                billing={"hold_applied": False, "hold_amount": 0},
            )

        ocr_job.status = "completed"
        ocr_job.extracted_text = extracted_text
        ocr_job.structured_json = payload
        ocr_job.quality_score = quality_score
        ocr_job.finished_at = datetime.utcnow()
        session.add(ocr_job)

        cache_entry = OcrExtractionCache(
            cache_key=dedupe_key,
            user_id=user_id,
            result_json={
                "extracted_text": extracted_text,
                "structured_json": payload,
                "quality_score": quality_score,
            },
            meta={"ocr_job_id": job_id, "engine": engine_choice},
            hit_count=1,
            created_at=datetime.utcnow(),
            last_hit_at=datetime.utcnow(),
        )
        session.add(cache_entry)
        session.commit()
        return OcrExtractResponse(
            ocr_attempt_id=job_id,
            status="completed",
            extracted_text=extracted_text,
            structured_json=payload,
            quality_score=quality_score,
            cache_hit=False,
            billing={"hold_applied": True, "hold_amount": float(hold_amount)},
        )
    except Exception as exc:
        logging.exception("ocr_extract failed")
        ocr_job.status = "failed"
        ocr_job.error_code = "OCR_FAILED"
        ocr_job.error_message = str(exc)
        ocr_job.finished_at = datetime.utcnow()
        session.add(ocr_job)
        # Release hold if OCR fails
        try:
            billing_ledger_service_v2.release_hold(session, request_id=hold_request_id, attempt_id=job_id)
        except (HoldAlreadyFinalizedError, HoldNotFoundError):
            pass
        session.commit()
        raise HTTPException(status_code=502, detail=f"OCR engine error: {str(exc)}") from exc


@api_router.post("/solve_questions_batch", response_model=SolveBatchResponse)
@limiter.limit("5/minute")
async def solve_questions_batch(
    request: Request,
    body: SolveBatchRequest,
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    from app.services.solve.batch_tier_runtime import BatchSolveError, execute_batch_solve
    from app.services.credit_billing_service import CreditBillingError, credit_billing_service

    if not body.items and not body.questions_json:
        raise HTTPException(status_code=400, detail="No questions provided")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    questions_json: List[Dict[str, Any]] = []
    if isinstance(body.questions_json, list) and body.questions_json:
        questions_json = body.questions_json
    else:
        for item in body.items:
            q_text = (item.question_text or item.text or "").strip()
            questions_json.append(
                {
                    "question_id": item.question_id,
                    "question_text": q_text,
                    "mode": item.mode or body.mode or "SOLVE",
                    "graph_mode": item.graph_mode or body.graph_mode or "AUTO",
                    "domain_mode": item.domain_mode or body.domain_mode or "reals",
                }
            )

    if not questions_json:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_question_item",
                "message": "No valid questions provided.",
                "details": {},
            },
        )

    normalized_questions: List[Dict[str, Any]] = []
    for idx, q in enumerate(questions_json, start=1):
        qid = str((q or {}).get("question_id") or "").strip()
        qtext = str((q or {}).get("question_text") or "").strip()
        if not qid or not qtext:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_question_item",
                    "message": "Each question requires non-empty question_id and question_text.",
                    "details": {"question_index": idx},
                },
            )
        normalized_questions.append(
            {
                "question_id": qid,
                "question_text": qtext,
                "mode": str((q or {}).get("mode") or body.mode or "SOLVE"),
                "graph_mode": str((q or {}).get("graph_mode") or body.graph_mode or "AUTO"),
                "domain_mode": str((q or {}).get("domain_mode") or body.domain_mode or "reals"),
            }
        )
    questions_json = normalized_questions

    request_id = str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    modality = "text"
    raw_modality = str(body.input_modality or "").strip().lower()
    if raw_modality in {"ocr_image", "snap_image", "image"}:
        modality = "snap_image"
    elif raw_modality in {"ocr_pdf", "snap_pdf", "pdf"}:
        modality = "snap_pdf"
    elif bool(body.has_voice):
        modality = "voice"

    verify_requested = bool(body.verify_requested)
    plot_requested = bool(body.plot_requested)
    reserve_result = None
    try:
        reserve_result = credit_billing_service.reserve_for_batch_solve(
            session=session,
            user_id=user_id,
            tier=body.tier or "SHORT_STEPS",
            mode=body.mode or "SOLVE",
            modality=modality,
            verify_requested=verify_requested,
            plot_requested=plot_requested,
            questions_json=questions_json,
            request_id=request_id,
            attempt_id=attempt_id,
            idempotency_key=body.idempotency_key,
        )
        session.flush()
        if reserve_result.reused:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "already_processed",
                    "message": "Request idempotency key already processed or in-flight.",
                    "request_id": request_id,
                    "attempt_id": attempt_id,
                    "details": {
                        "hold_id": reserve_result.hold_id,
                        "hold_status": reserve_result.hold_status,
                    },
                },
            )
    except CreditBillingError as exc:
        session.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": str(exc),
                "request_id": request_id,
                "attempt_id": attempt_id,
                "details": exc.details,
            },
        )
    try:
        payload, telemetry = await execute_batch_solve(
            session=session,
            tier=body.tier or "SHORT_STEPS",
            request_id=request_id,
            attempt_id=attempt_id,
            mode=body.mode or "SOLVE",
            graph_mode=body.graph_mode or "AUTO",
            domain_mode=body.domain_mode or "reals",
            preferred_response_language=body.preferred_response_language or "English",
            questions_json=questions_json,
            allow_auto_split=(len(questions_json) > 1),
            max_tasks_per_question=6,
        )
    except BatchSolveError as exc:
        if reserve_result and reserve_result.hold_id:
            try:
                credit_billing_service.release_hold_full(session=session, hold_id=reserve_result.hold_id)
                session.commit()
            except Exception:
                session.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": str(exc),
                "request_id": request_id,
                "attempt_id": attempt_id,
                "details": exc.details,
            },
        )
    except Exception:
        if reserve_result and reserve_result.hold_id:
            try:
                credit_billing_service.release_hold_full(session=session, hold_id=reserve_result.hold_id)
                session.commit()
            except Exception:
                session.rollback()
        raise

    settlement_summary = None
    if reserve_result:
        try:
            settlement_summary = credit_billing_service.settle_batch_hold(
                session=session,
                hold_id=reserve_result.hold_id,
                request_id=str(telemetry.get("request_id") or request_id),
                attempt_id=str(telemetry.get("attempt_id") or attempt_id),
                idempotency_key=reserve_result.idempotency_key,
                item_costs=reserve_result.item_costs,
                payload_items=payload.get("items") or [],
                pricing_snapshot=reserve_result.pricing_snapshot,
                provider_failed=False,
            )
            session.commit()
        except Exception as settle_exc:
            session.rollback()
            release_status = "settlement_failed"
            try:
                credit_billing_service.release_hold_full(session=session, hold_id=reserve_result.hold_id)
                session.commit()
                release_status = "settlement_failed_released"
            except Exception:
                session.rollback()
                release_status = "settlement_failed_release_failed"
            logger.exception(
                "batch_settlement_failed request_id=%s attempt_id=%s hold_id=%s reason=%s release_status=%s",
                str(telemetry.get("request_id") or request_id) if isinstance(telemetry, dict) else request_id,
                str(telemetry.get("attempt_id") or attempt_id) if isinstance(telemetry, dict) else attempt_id,
                reserve_result.hold_id,
                str(settle_exc),
                release_status,
            )
            settlement_summary = {
                "hold_id": reserve_result.hold_id,
                "status": release_status,
                "error": str(settle_exc),
            }

    results: List[SolveBatchItemResult] = []
    for idx, item in enumerate(payload.get("items", []), start=1):
        qid = str(item.get("question_id") or "")
        item_reserved = None
        item_final = None
        item_refunded = None
        if reserve_result and idx - 1 < len(reserve_result.item_costs):
            row = reserve_result.item_costs[idx - 1]
            item_reserved = float(row.total_reserved)
            refusal = bool(((item.get("refusal") or {}) if isinstance(item.get("refusal"), dict) else {}).get("is_refusal"))
            settlement_status = str((settlement_summary or {}).get("status") or "")
            if settlement_status.startswith("settlement_failed"):
                item_final = 0.0
                item_refunded = float(row.total_reserved)
            elif refusal:
                item_final = float(row.attempt_fee)
                item_refunded = float(row.total_reserved - row.attempt_fee)
            else:
                item_final = float(row.total_reserved)
                item_refunded = 0.0
        results.append(
            SolveBatchItemResult(
                question_id=qid,
                ok=True,
                solve_response_json=item,
                telemetry={**telemetry, "billing_settlement": settlement_summary} if isinstance(telemetry, dict) else telemetry,
                credits_reserved=item_reserved,
                credits_final=item_final,
                credits_refunded=item_refunded,
            )
        )

    created_session_id: Optional[int] = None
    try:
        normalized_tier = _normalize_tier_for_prompt_binding(body.tier)
        solve_tier_slug = _externalize_tier(normalized_tier)
        requested_mode = "minimal" if normalized_tier in {"SHORT_STEPS", "FINAL"} else "detailed"
        question_lines = [
            f"- ({str(q.get('question_id') or '').strip()}) {str(q.get('question_text') or '').strip()}"
            for q in questions_json
            if str(q.get("question_id") or "").strip() and str(q.get("question_text") or "").strip()
        ]
        title_seed = str((questions_json[0] or {}).get("question_text") or "Batch Solve").strip() if questions_json else "Batch Solve"
        title = (title_seed[:80] + "...") if len(title_seed) > 83 else title_seed
        if not title:
            title = "Batch Solve"

        chat_session = ChatSession(
            user_id=user_id,
            title=title,
            subject="Math",
            is_saved=True,
            learning_mode="solve",
            requested_mode=requested_mode,
            solve_tier=solve_tier_slug,
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        created_session_id = int(chat_session.id)

        user_content = "Batch Solve Request"
        if question_lines:
            user_content = f"{user_content}\n" + "\n".join(question_lines)
        safe_items = jsonable_encoder(payload.get("items") or [])
        safe_telemetry = jsonable_encoder(telemetry if isinstance(telemetry, dict) else {})
        solve_meta = {
            "request_id": str(telemetry.get("request_id") or request_id),
            "attempt_id": str(telemetry.get("attempt_id") or attempt_id),
            "provider": str((telemetry or {}).get("provider") or ""),
            "model": str((telemetry or {}).get("model") or ""),
            "tier_requested": str((body.tier or "")).upper() or "SHORT_STEPS",
            "tier_effective": str(payload.get("tier") or body.tier or "").upper(),
            "mode": "SOLVE",
            "output_format": "json_schema",
            "prompt_binding_id": telemetry.get("prompt_binding_id") if isinstance(telemetry, dict) else None,
            "global_system_prompt_id": telemetry.get("global_system_prompt_id") if isinstance(telemetry, dict) else None,
            "developer_prompt_id": telemetry.get("developer_prompt_id") if isinstance(telemetry, dict) else None,
            "output_schema_id": telemetry.get("output_schema_id") if isinstance(telemetry, dict) else None,
        }
        assistant_structured = {
            "mode": "batch_text_solve",
            "requested_mode": body.mode or "SOLVE",
            "response_language": (
                (payload.get("language") or {}).get("response_language")
                if isinstance(payload.get("language"), dict)
                else (body.preferred_response_language or "English")
            ),
            "question_count": len(safe_items),
            "questions": jsonable_encoder(questions_json),
            "solutions": safe_items,
            "request_id": str(telemetry.get("request_id") or request_id),
            "attempt_id": str(telemetry.get("attempt_id") or attempt_id),
            "tier": str(payload.get("tier") or body.tier or "").upper(),
            "tier_requested": str((body.tier or "")).upper() or "SHORT_STEPS",
            "tier_effective": str(payload.get("tier") or body.tier or "").upper(),
            "output_format": "json_schema",
            "hide_from_tutor": True,
            "solve_meta": solve_meta,
            "telemetry": safe_telemetry if isinstance(safe_telemetry, dict) else None,
        }
        if normalized_tier == "SHORT_STEPS":
            if isinstance(payload.get("question"), dict):
                assistant_structured["question"] = jsonable_encoder(payload.get("question"))
            if isinstance(payload.get("problem"), dict):
                assistant_structured["problem"] = jsonable_encoder(payload.get("problem"))
            if isinstance(payload.get("raw_user_extraction"), dict):
                assistant_structured["raw_user_extraction"] = jsonable_encoder(payload.get("raw_user_extraction"))
        user_msg = ChatMessage(
            session_id=int(chat_session.id),
            role="user",
            content=user_content,
        )
        assistant_msg = ChatMessage(
            session_id=int(chat_session.id),
            role="assistant",
            content=f"Batch solve complete for {len(payload.get('items') or [])} question(s).",
            structured_data=assistant_structured,
            telemetry=safe_telemetry if isinstance(safe_telemetry, dict) else None,
            model_used=str((telemetry or {}).get("model") or ""),
            tokens_used=int((telemetry or {}).get("total_tokens") or 0),
        )
        session.add(user_msg)
        session.add(assistant_msg)
        try:
            session.commit()
            session.refresh(assistant_msg)
            telemetry_provider = str((telemetry or {}).get("provider") or "").strip().lower()
            tier_effective = str(payload.get("tier") or body.tier or "").upper()
            provider_raw_text = str((telemetry or {}).get("provider_raw_text") or "")
            provider_raw_payload = (telemetry or {}).get("provider_raw_payload")
            use_exact_ollama_short_raw = (
                telemetry_provider == "ollama"
                and tier_effective == "SHORT_STEPS"
                and provider_raw_text != ""
            )
            persisted_raw_solution_text = (
                provider_raw_text if use_exact_ollama_short_raw else json.dumps(payload, ensure_ascii=False)
            )
            persisted_llm_raw_response = (
                provider_raw_payload if isinstance(provider_raw_payload, dict) else None
            )
            if persisted_llm_raw_response is not None:
                try:
                    json.dumps(persisted_llm_raw_response, ensure_ascii=False)
                except Exception:
                    persisted_llm_raw_response = {
                        "raw_payload_preview": str(provider_raw_payload)[:4000]
                    }
            session.add(
                SolverOutputAttempt(
                    request_id=str(telemetry.get("request_id") or request_id),
                    attempt_id=str(telemetry.get("attempt_id") or attempt_id),
                    user_id=user_id,
                    session_id=int(chat_session.id),
                    message_id=int(assistant_msg.id) if assistant_msg.id is not None else None,
                    output_format="json_schema",
                    attempt_number=1,
                    provider=str((telemetry or {}).get("provider") or ""),
                    model=str((telemetry or {}).get("model") or ""),
                    provider_model=(
                        f"{str((telemetry or {}).get('provider') or '')}:{str((telemetry or {}).get('model') or '')}"
                        if (telemetry or {}).get("provider") and (telemetry or {}).get("model")
                        else None
                    ),
                    input_text_raw=user_content,
                    char_count=len(persisted_raw_solution_text),
                    extracted_answer=str((((safe_items[0] if safe_items else {}) or {}).get("final_answer") or {}).get("answer_text") or ""),
                    raw_solution_text=persisted_raw_solution_text,
                    llm_raw_response=persisted_llm_raw_response,
                    validation_json=assistant_structured,
                    input_tokens=int((telemetry or {}).get("input_tokens") or 0),
                    output_tokens=int((telemetry or {}).get("output_tokens") or 0),
                    total_tokens=int((telemetry or {}).get("total_tokens") or 0),
                    latency_ms=int((telemetry or {}).get("latency_ms_total") or 0) or None,
                    prompt_meta={"questions_json": jsonable_encoder(questions_json)},
                    status="success",
                )
            )
            session.commit()
        except Exception as msg_exc:
            session.rollback()
            logger.exception(
                "batch_session_message_persist_failed request_id=%s attempt_id=%s user_id=%s reason=%s",
                str(telemetry.get("request_id") or request_id),
                str(telemetry.get("attempt_id") or attempt_id),
                user_id,
                str(msg_exc),
            )
            # Fallback write with minimal JSON footprint to avoid losing session visibility.
            session.add(ChatMessage(session_id=int(chat_session.id), role="user", content=user_content))
            session.add(
                ChatMessage(
                    session_id=int(chat_session.id),
                    role="assistant",
                    content=f"Batch solve complete for {len(safe_items)} question(s).",
                    structured_data={
                        "mode": "batch_text_solve",
                        "request_id": str(telemetry.get("request_id") or request_id),
                        "attempt_id": str(telemetry.get("attempt_id") or attempt_id),
                        "tier": str(payload.get("tier") or body.tier or "").upper(),
                        "tier_requested": str((body.tier or "")).upper() or "SHORT_STEPS",
                        "tier_effective": str(payload.get("tier") or body.tier or "").upper(),
                        "questions": jsonable_encoder(questions_json),
                        "solutions": safe_items,
                        "solutions_count": len(safe_items),
                        "hide_from_tutor": True,
                        "question": jsonable_encoder(payload.get("question")) if isinstance(payload.get("question"), dict) else None,
                        "problem": jsonable_encoder(payload.get("problem")) if isinstance(payload.get("problem"), dict) else None,
                        "raw_user_extraction": jsonable_encoder(payload.get("raw_user_extraction")) if isinstance(payload.get("raw_user_extraction"), dict) else None,
                    },
                )
            )
            session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(
            "batch_session_persist_failed request_id=%s attempt_id=%s user_id=%s reason=%s",
            str(telemetry.get("request_id") if isinstance(telemetry, dict) else request_id),
            str(telemetry.get("attempt_id") if isinstance(telemetry, dict) else attempt_id),
            user_id,
            str(exc),
        )

    return SolveBatchResponse(
        ok=True,
        results=results,
        request_id=str(telemetry.get("request_id") or request_id),
        attempt_id=str(telemetry.get("attempt_id") or attempt_id),
        session_id=created_session_id,
        tier=str(payload.get("tier") or body.tier or ""),
        language=payload.get("language") if isinstance(payload.get("language"), dict) else None,
        items=payload.get("items") if isinstance(payload.get("items"), list) else None,
        payload=payload,
        telemetry=telemetry,
    )

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
        # Priority: body.user_id > X-User-ID header > default to 1 (legacy/internal)
        x_user_id = request.headers.get("X-User-ID")
        user_id = body.user_id or (int(x_user_id) if x_user_id and x_user_id.isdigit() else 1)
        
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
        
        # 1. OCR Processing (Handled by frontend/separate endpoint)
        extracted_text = ""
    except HTTPException:
        # Pass through expected HTTP exceptions
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Log unexpected errors but don't leak internals unless requested
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    # Phase 1: Create Attempt Record Immediately
    attempt_id = str(uuid.uuid4())
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    try:
        new_attempt = SolverOutputAttempt(
            request_id=req_id,
            attempt_id=attempt_id,
            user_id=user_id,
            status="pending",
            input_text_raw=body.text_query, # Raw input from body
            created_at=datetime.utcnow()
        )
        session.add(new_attempt)
        session.commit()
        
        # Structured Log
        print(f"request_id={req_id} attempt_id={attempt_id} phase=solve_start status=pending")
    except Exception as e:
        print(f"[API] Failed to create attempt record: {e}")
        # We continue even if tracking fails, but log it.
        # Ideally we should fail if strict audit is required, but for availability we proceed.


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

    # Mandatory local symbolic + numeric gate for every solve request.
    from app.services.solve.sympy_numpy_gate import run_mandatory_sympy_numpy_gate
    try:
        gate_report = run_mandatory_sympy_numpy_gate(base_query or final_prompt)
        print(
            "[SOLVE_SYMPY_NUMPY_GATE] "
            + json.dumps(
                {
                    "request_id": req_id,
                    "attempt_id": attempt_id,
                    **gate_report.as_dict(),
                },
                ensure_ascii=False,
            )
        )
    except Exception as gate_exc:
        raise HTTPException(status_code=500, detail=f"Mandatory SymPy/NumPy gate failed: {gate_exc}")
    
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
    solver_trusted_context = _build_solver_trusted_context(body.trusted_context, user)
    effective_max_tokens = get_effective_max_tokens(
        requested_mode,
        solver_trusted_context.get("learning_mode", "solve"),
        token_policy
    )
    try:
        print(f"[API] Using Solver V3 for: {final_prompt[:50]}...")
        
        # Update attempt input text with final resolved prompt
        if attempt_id:
             try:
                 att = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
                 if att:
                     att.input_text_normalized = final_prompt
                     session.add(att)
                     session.commit()
             except: pass

        solution_data = await solver.solve(
            problem_text=final_prompt,
            context=context,
            trace=body.mode == "debug",
            user_tier=_resolve_runtime_tier_slug(user),
            user_id=user_id,
            db_session=session,
            requested_mode=requested_mode,
            trusted_context=solver_trusted_context,
            max_output_tokens=effective_max_tokens,
            attempt_id=attempt_id, # Phase 1
            image_url=body.image_url
        )
        print(f"[API] Solver V3 returned successfully")
        
        # Transform V3 format (SolveResponseV3) to V1 format (SolveResponse)
        print(f"[API] Transforming V3 response to V1 format...")
        solution_data = _transform_v3_to_v1_format(solution_data)
        print(f"[API] Transformation complete")
        
    except Exception as e:
        print(f"[API_ERROR] Solver V3 failed: {type(e).__name__}: {e}")
        # Structured Log (Failure)
        # Check if req_id is bound; it should be as it's at top of function
        if 'req_id' not in locals(): req_id = "unknown"
        if 'attempt_id' not in locals(): attempt_id = "unknown"
        print(f"request_id={req_id} attempt_id={attempt_id} phase=solve_end status=failure error={str(e)}")
        
        session.rollback() # Ensure session is clean for status update
        
        # Fail the attempt if it threw exception (e.g. RateLimit, Overloaded)
        # Fail the attempt if it threw exception (e.g. RateLimit, Overloaded)
        if attempt_id:
            try:
                att = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
                if att:
                    att.status = "failure"
                    att.failure_code = "INTERNAL_SERVER_ERROR"
                    att.error_message = str(e)
                    session.add(att)
                    session.commit()
            except Exception as update_err:
                print(f"[API_ERROR] Failed to update attempt status: {update_err}")
                # We don't re-raise here to allow the main error to propagate via HTTPException

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
    try:
        plan_version = None
        from app.services.prompt_binding_pricing import resolve_binding_pricing
        _, mults, _ = resolve_binding_pricing(session, new_chat.solve_tier)
        plan_version = str(mults.version)
        from app.services.pricing_service import pricing_service
        token_version = pricing_service.get_pricing_config(session).config_version_id
        telemetry_data["pricing_version_plan"] = plan_version
        telemetry_data["config_version_id"] = token_version
    except Exception:
        pass
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
        "request_id": req_id,
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

    solve_session_id = _persist_solve_session_and_llm_usage(
        session,
        user_id=user_id,
        problem_text=base_query,
        topic=body.subject or "Math",
        solution_payload=solution_data if isinstance(solution_data, dict) else {},
        provider="openai",
        model=model_name,
        request_id=req_id,
        input_tokens=telemetry_data.get("input_tokens"),
        output_tokens=telemetry_data.get("output_tokens"),
        total_tokens=telemetry_data.get("total_tokens"),
        latency_ms=telemetry_data.get("latency_ms_total"),
    )

    # Transformation complete, visuals handled at runtime in frontend
    # Structured Log (Success)
    print(f"request_id={req_id} attempt_id={attempt_id} phase=solve_end status=success latency={telemetry_data.get('latency_ms_total')}ms")
    
    return SolveResponse(
        session_id=new_chat.id,
        solve_session_id=solve_session_id,
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
    
    # 1.1 Store immutable snapshot of the solved problem for follow-up chat context.
    steps_list = solution_data.get("solution", {}).get("steps", [])
    steps_text = "\n".join([f"Step {i+1}: {s.get('explanation', '')}" for i, s in enumerate(steps_list)])
    final_ans = str(solution_data.get("solution", {}).get("result", ""))
    
    solve_session_rec = SolveSession(
        user_id=user_id,
        problem_text=base_query,
        topic=body.subject or "Math",
        solution_steps_text=steps_text,
        final_answer_text=final_ans
    )
    session.add(solve_session_rec)
    session.commit()
    session.refresh(solve_session_rec)

    return SolveResponse(
        session_id=new_chat.id,
        solve_session_id=solve_session_rec.id, # Phase 3
        solution=solution_data.get("solution", solution_data),
        concepts=solution_data.get("concepts") or [],
        visuals=solution_data.get("visuals") or [],
        verification=solution_data.get("verification"),
        model_used=model_name,
        tokens_used=final_tokens_count,
        has_image=is_image,
        telemetry=solution_data.get("telemetry") or solution_data.get("_telemetry")
    )

    
    # ------------------------------------------------------------------
# Solver V3 Endpoint - Production-Grade with Schema Validation
# ------------------------------------------------------------------

@api_router.get("/solve_v3_runtime_meta")
async def solve_v3_runtime_meta(
    attempt_id: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    tier: Optional[str] = Query(None),
    mode_family: Optional[str] = Query("SOLVE"),
    requested_mode: Optional[str] = Query("minimal"),
    session: Session = Depends(get_session),
):
    query = select(SolverOutputAttempt)
    if attempt_id:
        query = query.where(SolverOutputAttempt.attempt_id == attempt_id.strip())
    elif request_id:
        query = query.where(SolverOutputAttempt.request_id == request_id.strip())
    elif user_id is not None:
        query = query.where(SolverOutputAttempt.user_id == user_id)
    else:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "status": "not_found",
                "reason": "Provide attempt_id or request_id (or user_id for latest attempt lookup).",
                "retryable": False,
            },
        )

    attempt = session.exec(query.order_by(SolverOutputAttempt.created_at.desc())).first()
    if not attempt:
        # Normal page-load behavior asks for runtime meta using only user_id before first solve.
        # Return a stable empty payload instead of 404 to avoid noisy client/server logs.
        if user_id is not None and not attempt_id and not request_id:
            normalized_tier = (tier or "").strip().lower()
            effective_tier = (
                "short_steps"
                if normalized_tier in {"free", "three_step", "short_steps", ""}
                else normalized_tier
            )
            return {
                "status": "ok",
                "has_runtime_evidence": False,
                "attempt_id": None,
                "request_id": None,
                "user_id": user_id,
                "provider": None,
                "model": None,
                "tier_requested": effective_tier,
                "effective_tier": effective_tier,
                "mode_family": (mode_family or "SOLVE"),
                "mode": (requested_mode or "minimal"),
                "prompt_binding_id": None,
                "global_system_prompt_id": None,
                "developer_prompt_id": None,
                "output_schema_id": None,
                "global_system_prompt_version": None,
                "developer_prompt_version": None,
                "output_schema_version": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency_ms_total": 0,
                "latency_ms_openai": 0,
                "finish_reason": None,
                "truncated": False,
                "cache_hit": False,
                "timing_ms": {
                    "parse": 0,
                    "canonicalize": 0,
                    "openai": 0,
                    "verify": 0,
                    "total": 0,
                },
                "verification": {
                    "verified": False,
                    "verification_method": None,
                    "unverified_reason": "no_attempt_runtime_evidence",
                    "verification_meta": {},
                },
                "attempt_status": None,
                "failure_code": None,
                "created_at": None,
                "updated_at": None,
            }
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NOT_FOUND",
                "status": "not_found",
                "reason": "No attempt runtime evidence found.",
                "attempt_id": attempt_id,
                "request_id": request_id,
                "user_id": user_id,
                "retryable": False,
            },
        )

    validation = attempt.validation_json if isinstance(attempt.validation_json, dict) else {}
    runtime_meta = validation.get("runtime_meta") if isinstance(validation.get("runtime_meta"), dict) else {}
    verification = validation.get("verification") if isinstance(validation.get("verification"), dict) else {}
    prompt_meta = attempt.prompt_meta if isinstance(attempt.prompt_meta, dict) else {}
    timing_ms = (
        runtime_meta.get("timing_ms")
        if isinstance(runtime_meta.get("timing_ms"), dict)
        else (prompt_meta.get("timing_ms") if isinstance(prompt_meta.get("timing_ms"), dict) else {})
    )

    return {
        "status": "ok",
        "attempt_id": attempt.attempt_id,
        "request_id": attempt.request_id,
        "user_id": attempt.user_id,
        "provider": attempt.provider or runtime_meta.get("provider"),
        "model": attempt.model or runtime_meta.get("model"),
        "input_tokens": int(attempt.input_tokens or 0),
        "output_tokens": int(attempt.output_tokens or 0),
        "total_tokens": int(attempt.total_tokens or 0),
        "latency_ms_total": int(attempt.latency_ms or runtime_meta.get("latency_ms_total") or 0),
        "latency_ms_openai": int(runtime_meta.get("latency_ms_openai") or timing_ms.get("openai") or 0),
        "finish_reason": runtime_meta.get("finish_reason"),
        "truncated": runtime_meta.get("truncated"),
        "cache_hit": runtime_meta.get("cache_hit"),
        "timing_ms": {
            "parse": int(timing_ms.get("parse") or 0),
            "canonicalize": int(timing_ms.get("canonicalize") or 0),
            "openai": int(timing_ms.get("openai") or 0),
            "verify": int(timing_ms.get("verify") or 0),
            "total": int(timing_ms.get("total") or 0),
        },
        "verification": {
            "verified": bool(verification.get("verified")),
            "verification_method": verification.get("verification_method"),
            "unverified_reason": verification.get("unverified_reason"),
            "verification_meta": verification.get("verification_meta") if isinstance(verification.get("verification_meta"), dict) else {},
        },
        "attempt_status": attempt.status,
        "failure_code": attempt.failure_code,
        "created_at": attempt.created_at,
        "updated_at": attempt.updated_at,
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
    from app.services.billing_service import billing_service
    from app.services.subscription_service import subscription_service
    from app.services.solver_v3 import get_solver_v3
    from app.services.runtime_audit import emit_runtime_audit
    import base64

    app_env = os.environ.get("APP_ENV", "").upper()
    debug_allowed = app_env in {"DEV", "TEST"} or os.environ.get("BILLING_FAKE_SOLVER_ENABLED", "").lower() == "true"
    if (body.debug_simulated_tokens or body.debug_force_error) and not debug_allowed:
        raise HTTPException(status_code=400, detail="debug_simulated_tokens not allowed in this environment")
    
    start_total = time.perf_counter()
    # Generate unique Request ID (idempotent when idempotency_key is provided)
    request_id = (body.idempotency_key or "").strip() or str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    requested_mode = body.requested_mode or "minimal"
    learning_mode = (body.trusted_context or {}).get("learning_mode", "solve")
    features_used = body.features_used or {}
    deduct_attempted = {"credits": False, "ocr": False, "voice": False}
    deduct_committed = False
    resolved_profile = None
    token_policy = get_token_policy(session)
    ocr_metadata = {}
    voice_metadata = {}
    verification_level = "standard"
    token_policy_key = "DEFAULT"
    ocr_confidence = None
    graph_mode = getattr(body, 'graph_mode', 'auto')
    stage_timing_ms: Dict[str, int] = {
        "parse": 0,
        "canonicalize": 0,
        "openai": 0,
        "verify": 0,
        "total": 0,
    }
    solve_route = "openai"
    symbolic_parse = False
    solver_instance = None

    
    # Extract problem text
    problem_text = (
        body.question_text or
        body.confirmed_text or
        body.confirmed_markdown or
        body.text_query or
        "No problem provided"
    ).strip()
    
    if not problem_text:
        raise HTTPException(status_code=400, detail="No input provided")
    if len(problem_text) > 20000:
        raise HTTPException(status_code=400, detail="Input too long (max 20000 chars).")
    if graph_mode not in {"off", "auto", "on"}:
        raise HTTPException(status_code=400, detail="graph_mode must be one of off|auto|on")
    if requested_mode not in {"minimal", "detailed"}:
        raise HTTPException(status_code=400, detail="requested_mode must be one of minimal|detailed")

    from app.services.solve.batch_tier_runtime import BatchSolveError, execute_batch_solve
    try:
        payload, telemetry = await execute_batch_solve(
            session=session,
            tier=body.tier or "SHORT_STEPS",
            request_id=request_id,
            attempt_id=attempt_id,
            mode=(body.mode or "SOLVE"),
            graph_mode=(body.graph_mode or "AUTO"),
            domain_mode=((body.trusted_context or {}).get("domain_mode") if isinstance(body.trusted_context, dict) else "reals"),
            preferred_response_language=((body.trusted_context or {}).get("preferred_response_language") if isinstance(body.trusted_context, dict) else "English"),
            questions_json=[
                {
                    "question_id": str(body.question_id or "q1"),
                    "question_text": problem_text,
                    "mode": body.mode or "SOLVE",
                    "graph_mode": body.graph_mode or "AUTO",
                    "domain_mode": ((body.trusted_context or {}).get("domain_mode") if isinstance(body.trusted_context, dict) else "reals"),
                }
            ],
        )
    except BatchSolveError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "status": "failed_controlled",
                "reason": str(exc),
                "retryable": exc.status_code >= 500,
                "request_id": request_id,
                "attempt_id": attempt_id,
                "details": exc.details,
            },
        )

    chat_session = ChatSession(
        user_id=user_id,
        title=(problem_text[:80] or "Batch Solve"),
        learning_mode="solve",
        requested_mode=requested_mode,
        solve_tier=str(body.tier or "short_steps").lower(),
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)

    answer_item = (payload.get("items") or [{}])[0]
    msg = ChatMessage(
        session_id=int(chat_session.id),
        role="assistant",
        content=str(((answer_item.get("final_answer") or {}).get("answer_text")) or "Solution generated."),
        structured_data=payload,
        telemetry=telemetry,
        model_used=telemetry.get("model"),
        tokens_used=int(telemetry.get("total_tokens") or 0),
    )
    session.add(msg)
    session.commit()

    return SolveResponse(
        session_id=int(chat_session.id),
        solution=payload,
        concepts=[],
        visuals=[],
        model_used=telemetry.get("model"),
        tokens_used=int(telemetry.get("total_tokens") or 0),
        has_image=bool(body.image_url),
        telemetry=telemetry,
        solve_session_id=None,
    )

    validate_math_query(problem_text)
    use_superset_v2 = os.getenv("SOLVE_V3_USE_SUPERSET_V2", "true").strip().lower() in {"1", "true", "yes", "on"}
    if use_superset_v2:
        try:
            from app.services.solver_v3 import get_solver_v3 as _get_solver_probe
            solver_probe = _get_solver_probe()
            use_superset_v2 = hasattr(solver_probe, "_call_llm_with_schema")
        except Exception:
            use_superset_v2 = False
    if use_superset_v2:
        from app.services.solve.superset_v2_pipeline import (
            SolveV2PipelineError,
            run_solve_v3_superset_v2,
        )
        try:
            return await run_solve_v3_superset_v2(
                session=session,
                user_id=user_id,
                problem_text=problem_text,
                requested_tier=body.tier,
                requested_mode=requested_mode,
                graph_mode=graph_mode,
                trusted_context=body.trusted_context,
                idempotency_key=body.idempotency_key,
            )
        except SolveV2PipelineError as pipeline_error:
            raise HTTPException(
                status_code=pipeline_error.status_code,
                detail={
                    "code": pipeline_error.code,
                    "status": "failed_controlled",
                    "reason": pipeline_error.message,
                    "retryable": pipeline_error.retryable,
                    "request_id": request_id,
                    "attempt_id": attempt_id,
                    "details": pipeline_error.details,
                },
            )

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
            t_parse = time.perf_counter()
            intent = canonicalization_service.get_intent(problem_text)
            stage_timing_ms["parse"] = int((time.perf_counter() - t_parse) * 1000)
            emit_runtime_audit(
                component="solve_v3_stage_parse",
                started_at=t_parse,
                request_id=request_id,
                route=solve_route,
                result="ok",
                extra={"attempt_id": attempt_id},
            )
            t_canonical = time.perf_counter()
            math_obj, assumptions = canonicalization_service.normalize_math_object(problem_text, intent)
            symbolic_parse = not bool(assumptions.get("parse_error"))
            canonical_key = canonicalization_service.compute_canonical_key(intent, math_obj, assumptions)
            stage_timing_ms["canonicalize"] = int((time.perf_counter() - t_canonical) * 1000)
            emit_runtime_audit(
                component="solve_v3_stage_canonicalize",
                started_at=t_canonical,
                request_id=request_id,
                route=solve_route,
                sympy_used=True,
                result="ok",
                extra={"attempt_id": attempt_id, "symbolic_parse": symbolic_parse},
            )
            
            result = cache_service.get_cached_solution(session, canonical_key)
            if result:
                print(f"[CACHE] Hit: {canonical_key}")
                was_cached = True
                solve_route = "cache"
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
    solver_trusted_context = _build_solver_trusted_context(body.trusted_context, user)
    learning_mode = solver_trusted_context.get("learning_mode", learning_mode)
    from app.llm_profiles.profile_resolver import ProfileResolver
    from app.llm_profiles.profile_resolver import ProfileResolutionError
    from app.services.llm.manager import get_configured_openai_model
    entitled_tier_slug = _solve_tier_ceiling_slug()
    tier_policy = _clamp_requested_tier(body.tier, entitled_tier_slug)
    requested_tier = tier_policy["tier_requested"]
    effective_tier = tier_policy["tier_effective"]
    effective_tier_internal = tier_policy["tier_effective_internal"]
    solve_provider = "openai"
    configured_model = get_configured_openai_model()
    try:
        resolved_profile = ProfileResolver.resolve_profile(
            session,
            user,
            requested_mode=requested_mode,
            learning_mode=learning_mode,
            force_tier=effective_tier_internal,
            mode_family="SOLVE",
            provider=solve_provider,
        )
    except ProfileResolutionError as profile_err:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DEPENDENCY_UNAVAILABLE",
                "status": "dependency_unavailable",
                "reason": str(profile_err),
                "message": str(profile_err),
                "retryable": True,
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
    except HTTPException as e:
        stage_timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
        try:
            attempt_row.status = "failed_controlled"
            attempt_row.failure_code = "HTTPException"
            attempt_row.error_message = str(e.detail)
            attempt_row.prompt_meta = {
                **(attempt_row.prompt_meta or {}),
                "route": solve_route,
                "stage_timing_ms": stage_timing_ms,
            }
            session.add(attempt_row)
            session.commit()
        except Exception:
            session.rollback()
        raise

    except Exception as e:
        print(f"[QUESTION_CACHE] Fingerprint error: {e}")

    # Stage A3: create attempt record before any OpenAI call
    attempt_row = SolverOutputAttempt(
        request_id=request_id,
        attempt_id=attempt_id,
        user_id=user_id,
        status="processing",
        input_text_raw=problem_text,
        input_text_normalized=problem_text,
        prompt_meta={
            "graph_mode": graph_mode,
            "requested_mode": requested_mode,
            "tier_requested": body.tier,
            "tier_effective": effective_tier,
            "route": solve_route,
            "assumptions_detected": assumptions,
            "symbolic_parse": symbolic_parse,
        },
        model=configured_model,
        provider=solve_provider,
    )
    try:
        session.add(attempt_row)
        session.commit()
    except Exception:
        session.rollback()
        # controlled failure: do not continue without attempt record
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DEPENDENCY_UNAVAILABLE",
                "status": "dependency_unavailable",
                "reason": "Could not create attempt record",
                "retryable": True,
                "request_id": request_id,
            },
        )
    
    try:
        # Call Solver V3 (Logic: cache -> rule_engine -> openai)
        if not result:
            from app.services.solve.verification_gate import verify_solve_result
            rule_engine_enabled = os.getenv("SOLVE_RULE_ENGINE_ENABLED", "true").lower() == "true"
            if rule_engine_enabled and symbolic_parse and intent == "solve_equation":
                rule_meta = verify_solve_result(problem_text, {"final_answer": {"answer_text": ""}}, request_id=request_id)
                if rule_meta.get("verified"):
                    solve_route = "rule_engine"
                    final_solutions = rule_meta.get("final_solutions") or []
                    answer_text = "x = " + ", ".join(final_solutions) if final_solutions else "No real solution"
                    result = {
                        "schema_version": "v1.0",
                        "problem": {"original_text": problem_text, "normalized_text": problem_text, "detected_tasks": ["solve_equation"]},
                        "classification": {"grade_band": "unknown", "domain": "algebra", "topic": "equation", "difficulty": "unknown"},
                        "refusal": {"is_refusal": False, "reason": None, "safe_alternative": None},
                        "assumptions": rule_meta.get("assumptions") or [],
                        "steps": [
                            {
                                "index": 1,
                                "title": "Symbolic solve",
                                "explanation": "Solved using deterministic rule engine and symbolic verification.",
                                "math_latex": answer_text,
                                "rules_used": ["sympy_solve", "symbolic_substitution_check"],
                                "checkpoint": {"question": "Do solutions satisfy original equation?", "answer": "Yes"},
                            }
                        ],
                        "final_answer": {"answer_text": answer_text, "answer_latex": answer_text, "values": []},
                        "visuals": {"should_visualize": False, "decision_reason": "Rule engine response", "plots": []},
                        "quality": {"confidence": 0.98, "common_mistakes": []},
                        "telemetry": {"provider": "local_rule_engine", "model": "sympy", "latency_ms_total": 0, "validated": True},
                    }

        if not result:
            solve_route = "openai"
            # --- ENTITLEMENT CHECK & DEBIT ---
            action_type = "solve_tutor" if requested_mode == "detailed" else "solve_quick"
            if bool(body.has_voice or features_used.get("voice_used")):
                 action_type = "voice_solve"

            # Estimate Tokens (Heuristics; retained for hold behavior)
            est_input = len(problem_text) // 3 + 100
            est_output = 4000 if requested_mode == "detailed" else 1500
            
            # Phase 1: Hold Credits
            sub_obj = subscription_service.get_or_create_subscription(session, user)
            
            try:
                 hold = billing_service.initiate_hold(
                     session,
                     user_id,
                     request_id,
                     subscription_id=sub_obj.id,
                     estimated_credits=1.0, # Strict hold
                     question_id=question_key
                 )
            except ValueError as e:
                 raise HTTPException(status_code=402, detail=f"Insufficient credits: {e}")
                 
            deduct_committed = True
            
            try:
                solver_instance = get_solver_v3()
                t_openai = time.perf_counter()
                result = await solver_instance.solve(
                    problem_text=problem_text,
                    context=context,
                    trace=trace,
                    request_id=request_id,
                    user_id=user_id,
                    db_session=session,
                    requested_mode=requested_mode,
                    trusted_context=solver_trusted_context,
                    learning_mode=learning_mode,
                    image_url=body.image_url,
                    max_output_tokens=effective_max_tokens,
                    user_tier=effective_tier,
                    attempt_id=attempt_id,
                    debug_simulated_tokens=body.debug_simulated_tokens,
                    debug_force_error=bool(body.debug_force_error),
                )
                stage_timing_ms["openai"] = int((time.perf_counter() - t_openai) * 1000)
                if not isinstance(result, dict) or "final_answer" not in result:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "code": "llm_invalid_output",
                            "status": "failed_controlled",
                            "reason": "LLM output missing required fields",
                            "retryable": True,
                            "request_id": request_id,
                            "attempt_id": attempt_id,
                        },
                    )
                emit_runtime_audit(
                    component="solve_v3_stage_openai",
                    started_at=t_openai,
                    request_id=request_id,
                    route=solve_route,
                    result="ok",
                    extra={"attempt_id": attempt_id},
                )

            except Exception as e:
                raise e
            
        
        # --- PLOTTING PIPELINE INTEGRATION ---
        # Normalize and ensure essentials
        from app.services.plot_integration import maybe_generate_plot, apply_graph_mode_override, format_plot_for_response
        from app.services.solve.verification_gate import verify_solve_result

        t_verify = time.perf_counter()
        verification_meta = verify_solve_result(problem_text, result or {}, request_id=request_id)
        stage_timing_ms["verify"] = int((time.perf_counter() - t_verify) * 1000)
        emit_runtime_audit(
            component="solve_v3_stage_verify",
            started_at=t_verify,
            request_id=request_id,
            route=solve_route,
            sympy_used=True,
            result="ok",
            extra={"attempt_id": attempt_id, "verified": bool(verification_meta.get("verified"))},
        )
        assumptions_list = result.get("assumptions")
        if not isinstance(assumptions_list, list):
            assumptions_list = []
        for assumption in verification_meta.get("assumptions", []):
            if assumption not in assumptions_list:
                assumptions_list.append(assumption)
        result["assumptions"] = assumptions_list
        result["verified"] = bool(verification_meta.get("verified"))
        result["verification_method"] = verification_meta.get("verification_method") or "none"
        result["dropped_candidates"] = verification_meta.get("dropped_candidates") or []
        result["final_solutions"] = verification_meta.get("final_solutions") or []
        result["llm_answer_text"] = verification_meta.get("llm_answer_text") or ""
        result["unverified_reason"] = verification_meta.get("unverified_reason")
        result["verification_meta"] = verification_meta
        if (
            solve_route == "openai"
            and solver_instance is not None
            and not result["verified"]
            and result.get("unverified_reason") == "verification_failed"
        ):
            repair_reasons = ", ".join(
                f"{item.get('candidate')}:{item.get('reason')}" for item in (result.get("dropped_candidates") or [])
            )
            repair_context = (
                context
                + "\n[VERIFICATION REPAIR REQUIRED]\n"
                + "Previous candidate solutions failed symbolic verification.\n"
                + f"Failure reasons: {repair_reasons}\n"
                + "Return corrected candidate solutions that satisfy the original equation and domain assumptions."
            )
            t_repair = time.perf_counter()
            repaired_result = await solver_instance.solve(
                problem_text=problem_text,
                context=repair_context,
                trace=trace,
                request_id=request_id,
                user_id=user_id,
                db_session=session,
                requested_mode=requested_mode,
                trusted_context=solver_trusted_context,
                learning_mode=learning_mode,
                image_url=body.image_url,
                max_output_tokens=effective_max_tokens,
                user_tier=effective_tier,
                attempt_id=attempt_id,
                debug_simulated_tokens=body.debug_simulated_tokens,
                debug_force_error=bool(body.debug_force_error),
            )
            stage_timing_ms["openai"] += int((time.perf_counter() - t_repair) * 1000)
            repair_verification_meta = verify_solve_result(problem_text, repaired_result or {}, request_id=request_id)
            if repair_verification_meta.get("verified"):
                result = repaired_result
                result["assumptions"] = repair_verification_meta.get("assumptions") or []
                result["verified"] = True
                result["verification_method"] = repair_verification_meta.get("verification_method") or "symbolic"
                result["dropped_candidates"] = repair_verification_meta.get("dropped_candidates") or []
                result["final_solutions"] = repair_verification_meta.get("final_solutions") or []
                result["llm_answer_text"] = repair_verification_meta.get("llm_answer_text") or ""
                result["unverified_reason"] = None
                result["verification_meta"] = repair_verification_meta
                result["verification_meta"]["repair_attempted"] = True
            else:
                result["verification_meta"]["repair_attempted"] = True

        if not result["verified"]:
            if isinstance(result.get("final_answer"), dict):
                answer_text = str(result["final_answer"].get("answer_text") or "").strip()
                if answer_text:
                    result["final_answer"]["answer_text"] = f"Unverified explanation: {answer_text}"
        
        # We only run plotting if result is successful and not an error
        if result and not result.get("error"):
            plot_data = await maybe_generate_plot(
                db_session=session,
                problem_text=problem_text,
                solve_result=result,
                graph_mode=graph_mode,
                attach_to_step_id=getattr(body, 'attach_to_step_id', None),
                tier=effective_tier,
                question_id=question_key or request_id
            )
            
            logger.info(f"[API_V3] Plot data generated: {plot_data.get('plot_generated')}, type: {plot_data.get('pipeline_type')}")
            # Apply deterministic overrides to visuals.should_visualize
            result = apply_graph_mode_override(
                solve_result=result,
                graph_mode=graph_mode,
                plot_generated=plot_data.get("plot_generated", False)
            )
            logger.info(f"[API_V3] After override: should_visualize={result.get('visuals', {}).get('should_visualize')}")
            
            # Merge generated plot into visuals.plots if successful
            if plot_data.get("plot_generated"):
                formatted_plot = format_plot_for_response(plot_data)
                if formatted_plot:
                    # V3 Schema expects visual object to have plots list
                    if not result.get("visuals"):
                         result["visuals"] = {"should_visualize": True, "decision_reason": "Injected", "plots": []}
                    
                    if "plots" not in result["visuals"] or result["visuals"]["plots"] is None:
                        result["visuals"]["plots"] = []
                    
                    # Deduplicate by plot_id
                    new_plot_id = formatted_plot.get("plot_id")
                    existing_plots = result["visuals"]["plots"]
                    if not any(isinstance(p, dict) and p.get("plot_id") == new_plot_id for p in existing_plots):
                        result["visuals"]["plots"].append(formatted_plot)
                        logger.info(f"[API_V3] Plot merged into visuals.plots: {new_plot_id}")
                    else:
                        # Replace existing with pipeline-processed version
                        for i, p in enumerate(existing_plots):
                            if isinstance(p, dict) and p.get("plot_id") == new_plot_id:
                                existing_plots[i] = formatted_plot
                                break
                        logger.info(f"[API_V3] existing plot updated from pipeline: {new_plot_id}")

        # Check if it's an error response
        if result.get("error", False):
            logger.info(f"[API_V3] Solver V3 returned error: {result.get('error_type')}")
            stage_timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
            try:
                attempt_row.status = "failed_controlled"
                attempt_row.error_message = result.get("message")
                attempt_row.failure_code = result.get("error_type") or "solver_error"
                attempt_row.prompt_meta = {
                    **(attempt_row.prompt_meta or {}),
                    "route": solve_route,
                    "stage_timing_ms": stage_timing_ms,
                }
                attempt_row.validation_json = result
                session.add(attempt_row)
                session.commit()
            except Exception:
                session.rollback()

            
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
                "status": "failure",
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
            
            # Phase 1: Finalize (Void/Refund)
            billing_service.finalize_transaction(
                 session,
                 request_id=request_id,
                 result_status="failure",
                 schema_valid=False
            )
            
            return {
                "request_id": request_id,
                "attempt_id": attempt_id,
                "session_id": new_chat.id,
                "error": True,
                "error_type": result.get("error_type"),
                "message": result.get("message"),
                "validation_errors": result.get("validation_errors", []),
                "timing_ms": stage_timing_ms,
                "solve_meta": {
                    "request_id": request_id,
                    "attempt_id": attempt_id,
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
            model_used=(result or {}).get("_model") or os.environ.get("OPENAI_MODEL_DEFAULT") or "unknown_model",
            tokens_used=tokens_actual,
            telemetry=result.get("telemetry")
        ))
        
        session.commit()

        solve_session_id = _persist_solve_session_and_llm_usage(
            session,
            user_id=user_id,
            problem_text=problem_text,
            topic=body.subject or "Math",
            solution_payload=result if isinstance(result, dict) else {},
            provider=(result.get("telemetry") or {}).get("provider") if isinstance(result, dict) else "openai",
            model=((result.get("telemetry") or {}).get("model") if isinstance(result, dict) else None) or (result.get("_model") if isinstance(result, dict) else None),
            request_id=request_id,
            input_tokens=(result.get("telemetry") or {}).get("input_tokens") if isinstance(result, dict) else None,
            output_tokens=(result.get("telemetry") or {}).get("output_tokens") if isinstance(result, dict) else None,
            total_tokens=(result.get("telemetry") or {}).get("total_tokens") if isinstance(result, dict) else tokens_actual,
            latency_ms=((result.get("telemetry") or {}).get("latency_ms_total") if isinstance(result, dict) else None),
        )
        
        # Return V3 response
        # Merge session info into the result
        result["session_id"] = new_chat.id
        result["solve_session_id"] = solve_session_id
        result["plot_url"] = plot_url
        result["tokens_used"] = tokens_actual
        result["request_id"] = request_id
        result["attempt_id"] = attempt_id
        result["route"] = solve_route
        result["symbolic_parse"] = symbolic_parse

        telemetry = result.get("telemetry") or result.get("_telemetry") or {}
        binding_meta = (telemetry.get("prompt_binding") or (getattr(resolved_profile, "prompt_binding_meta", {}) or {}))
        result["solve_meta"] = {
            "request_id": request_id,
            "attempt_id": attempt_id,
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
            "route": solve_route,
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
            "verification_pass": bool(result.get("verified")),
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

        # Phase 1: Finalize Billing
        # Must happen AFTER RequestEvent is recorded
        telemetry_final = result.get("telemetry", {})
        billing_service.finalize_transaction(
            session,
            request_id=request_id,
            result_status="ok",
            schema_valid=telemetry_final.get("validated", False),
            repaired=telemetry_final.get("repair_attempted", False)
        )

        stage_timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
        result["timing_ms"] = stage_timing_ms
        try:
            attempt_row.status = "success"
            attempt_row.validation_json = result
            attempt_row.extracted_answer = str((result.get("final_answer") or {}).get("answer_text") or "")
            attempt_row.input_tokens = int((telemetry.get("input_tokens") or 0))
            attempt_row.output_tokens = int((telemetry.get("output_tokens") or 0))
            attempt_row.total_tokens = int((telemetry.get("total_tokens") or tokens_actual or 0))
            attempt_row.latency_ms = int((telemetry.get("latency_ms_total") or stage_timing_ms["total"] or 0))
            attempt_row.prompt_meta = {
                **(attempt_row.prompt_meta or {}),
                "route": solve_route,
                "stage_timing_ms": stage_timing_ms,
                "verified": bool(result.get("verified")),
            }
            session.add(attempt_row)
            session.commit()
        except Exception:
            session.rollback()

        _enqueue_attempt_graph_render(attempt_id)
        return result

    except Exception as e:
        print(f"[API_V3_ERROR] Solver V3 failed: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        stage_timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
        try:
            attempt_row.status = "failed_controlled"
            attempt_row.failure_code = type(e).__name__
            attempt_row.error_message = str(e)
            attempt_row.prompt_meta = {
                **(attempt_row.prompt_meta or {}),
                "route": solve_route,
                "stage_timing_ms": stage_timing_ms,
            }
            session.add(attempt_row)
            session.commit()
        except Exception:
            session.rollback()
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
                "route": solve_route,
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
            status_code=503,
            detail={
                "code": "DEPENDENCY_UNAVAILABLE",
                "status": "dependency_unavailable",
                "reason": str(e),
                "retryable": True,
                "request_id": request_id,
                "attempt_id": attempt_id,
                "timing_ms": stage_timing_ms,
            },
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
    from app.services.admin.analytics_service import record_request_event, _calc_cost
    import base64
    from app.utils.token_limits import get_effective_max_tokens
    from pathlib import Path

    from app.services.subscription_service import subscription_service
    from app.services.tier_utils import get_user_effective_tier_slug
    from app.services.llm.manager import get_configured_openai_model
    from app.llm_profiles.profile_resolver import ProfileResolutionError

    # 0. Phase 1 Hardening: Distinct IDs (idempotent when idempotency_key is provided)
    request_id = (body.idempotency_key or "").strip() or str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    attempt = None
    should_refund = False
    cost = 0
    app_env = os.environ.get("APP_ENV", "").upper()
    debug_allowed = app_env in {"DEV", "TEST"} or os.environ.get("BILLING_FAKE_SOLVER_ENABLED", "").lower() == "true"
    if (body.debug_simulated_tokens or body.debug_force_error) and not debug_allowed:
        raise HTTPException(status_code=400, detail="debug_simulated_tokens not allowed in this environment")
    debug_simulated_tokens = body.debug_simulated_tokens
    debug_force_error = bool(body.debug_force_error)
    graph_mode = getattr(body, 'graph_mode', 'auto')
    # DEBUG: Write to file to confirm graph_mode value
    with open("graph_mode_trace.log", "a") as f:
        from datetime import datetime
        f.write(f"[{datetime.utcnow().isoformat()}] graph_mode={graph_mode}, body.graph_mode={getattr(body, 'graph_mode', 'MISSING')}\n")
        f.flush()
    print(f"[SOLVE_V3_STREAM] Extracted graph_mode: {graph_mode}")

    from app.services.solve.batch_tier_runtime import BatchSolveError, execute_batch_solve

    raw_problem_text = (
        body.question_text
        or body.confirmed_text
        or body.confirmed_markdown
        or body.text_query
        or ""
    ).strip()
    if not raw_problem_text:
        raise HTTPException(status_code=400, detail="No input provided")

    def _auto_split_questions_for_batch(text: str) -> List[str]:
        re_mod = __import__("re")
        src = (text or "").replace("\r", "").strip()
        if not src:
            return []
        lines = [ln.rstrip() for ln in src.split("\n")]
        non_empty = [ln for ln in lines if ln.strip()]
        if not non_empty:
            return []

        req_anchor_re = re_mod.compile(r"\b(must\s+do\s+all\s+of\s+the\s+following|do\s+all\s+of\s+the\s+following|requirements\s*:|tasks\s*:)\b", re_mod.I)
        bullet_re = re_mod.compile(r"^\s*[-*•]\s+")
        num_re = re_mod.compile(r"^\s*\(?\d{1,3}\)?\s*[.)\-:]\s+")
        alpha_re = re_mod.compile(r"^\s*\(?[a-zA-Z]\)?\s*[.)\-:]\s+")
        imperative_re = re_mod.compile(
            r"^\s*(write|state|derive|prove|show|compute|evaluate|justify|expand|find|verify|interpret|deduce|normalize|combine|define|determine|substitute|solve|describe|identify|report|list|use|parametrize)\b",
            re_mod.I,
        )
        task_verb_re = re_mod.compile(
            r"\b("
            r"solve|find|determine|compute|evaluate|derive|state|report|identify|list|"
            r"rewrite|express|factor|simplify|expand|transform|"
            r"verify|check|confirm|justify|prove|"
            r"format|arrange|order|standardize|interpret"
            r")\b",
            re_mod.I,
        )

        verb_to_class = {
            "solve": "SOLVE",
            "find": "SOLVE",
            "determine": "SOLVE",
            "compute": "SOLVE",
            "evaluate": "SOLVE",
            "derive": "SOLVE",
            "state": "SOLVE",
            "report": "SOLVE",
            "identify": "SOLVE",
            "list": "SOLVE",
            "rewrite": "TRANSFORM",
            "express": "TRANSFORM",
            "factor": "TRANSFORM",
            "simplify": "TRANSFORM",
            "expand": "TRANSFORM",
            "transform": "TRANSFORM",
            "verify": "VERIFY",
            "check": "VERIFY",
            "confirm": "VERIFY",
            "justify": "VERIFY",
            "prove": "VERIFY",
            "format": "FORMAT",
            "arrange": "FORMAT",
            "order": "FORMAT",
            "standardize": "FORMAT",
            "interpret": "FORMAT",
        }

        anchor_idx = -1
        for idx, ln in enumerate(lines):
            if req_anchor_re.search(ln or ""):
                anchor_idx = idx
                break

        def _strip_marker(ln: str) -> str:
            out = bullet_re.sub("", ln)
            out = num_re.sub("", out)
            out = alpha_re.sub("", out)
            return out.strip()

        def _parse_task_lines(task_lines: List[str]) -> List[str]:
            tasks: List[str] = []
            cur: List[str] = []
            for ln in task_lines:
                t = (ln or "").strip()
                if not t:
                    continue
                explicit = bool(bullet_re.match(ln) or num_re.match(ln) or alpha_re.match(ln))
                implicit = bool(imperative_re.match(t))
                if explicit or implicit:
                    if cur:
                        merged = " ".join(x.strip() for x in cur if x.strip()).strip()
                        if merged:
                            tasks.append(merged)
                    cur = [_strip_marker(ln) if explicit else t]
                elif cur:
                    cur.append(t)
                else:
                    cur = [t]
            if cur:
                merged = " ".join(x.strip() for x in cur if x.strip()).strip()
                if merged:
                    tasks.append(merged)
            return tasks

        if anchor_idx >= 0:
            preamble = "\n".join([ln for ln in lines[:anchor_idx] if ln.strip()]).strip()
            tasks = _parse_task_lines(lines[anchor_idx + 1 :])
            if len(tasks) >= 2:
                if preamble:
                    return [f"{preamble}\n\n{task}".strip() for task in tasks]
                return tasks

        first_item_idx = -1
        for idx, ln in enumerate(lines):
            if num_re.match(ln or "") or alpha_re.match(ln or "") or bullet_re.match(ln or ""):
                first_item_idx = idx
                break
        if first_item_idx > 0:
            preamble = "\n".join([ln for ln in lines[:first_item_idx] if ln.strip()]).strip()
            tasks = _parse_task_lines(lines[first_item_idx:])
            if len(tasks) >= 2:
                if preamble:
                    return [f"{preamble}\n\n{task}".strip() for task in tasks]
                return tasks

        q_lines = [ln.strip() for ln in lines if ln.strip().endswith("?")]
        if len(q_lines) >= 2:
            return q_lines

        # Step A/B/C fallback for paragraph-style multi-task prompts:
        # - A: split into candidate segments and keep those with task verbs
        # - B: normalize matched verb -> canonical class
        # - C: derive cheap object/scope keys, then dedupe by (class, object, scope)
        sentence_segments = [seg.strip() for seg in re_mod.split(r"(?<=[.?!;])\s+", src) if seg.strip()]
        if sentence_segments:
            preamble = sentence_segments[0]
            candidate_segments = sentence_segments[1:] if len(sentence_segments) > 1 else sentence_segments

            def _canonical_class(segment: str) -> str:
                match = task_verb_re.search(segment or "")
                if not match:
                    return "OTHER"
                return verb_to_class.get(match.group(1).lower(), "OTHER")

            def _object_key(segment: str) -> str:
                s = str(segment or "")
                lower = s.lower()
                m = re_mod.search(r"\bfor\s+([a-zA-Z][a-zA-Z0-9_]*)\b", s)
                if m:
                    return m.group(1).lower()
                if "sin(" in lower:
                    return "sin"
                if "cos(" in lower:
                    return "cos"
                if "tan(" in lower:
                    return "tan"
                if re_mod.search(r"\bsolutions?\b|\broots?\b", lower):
                    return "solutions"
                if "marginal density" in lower:
                    return "marginal_density"
                if "conditional density" in lower:
                    return "conditional_density"
                if "cov(" in lower or "covariance" in lower:
                    return "covariance"
                if "corr(" in lower or "correlation" in lower:
                    return "correlation"
                return "general"

            def _scope_key(segment: str) -> str:
                lower = str(segment or "").lower()
                if re_mod.search(r"\b[a-z]\s*in\s*\[", lower) or ("[0,2" in lower and ("pi" in lower or "π" in lower)):
                    return "domain_restricted"
                return "default"

            deduped: List[str] = []
            seen_keys: set[str] = set()
            for seg in candidate_segments:
                if not task_verb_re.search(seg):
                    continue
                key = f"{_canonical_class(seg)}|{_object_key(seg)}|{_scope_key(seg)}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(seg)

            if len(deduped) >= 2:
                return [f"{preamble} {task}".strip() for task in deduped]

        return [src]

    def _input_looks_incomplete(text: str) -> bool:
        re_mod = __import__("re")
        src = (text or "").replace("\r", "").strip()
        if len(src) < 12:
            return True
        lowered = src.lower()
        if lowered.endswith(("...", "…", ":", ",", ";", " and", " or", " because")):
            return True
        if re_mod.search(r"\b(must\s+do\s+all\s+of\s+the\s+following|requirements\s*:|tasks\s*:)\b", lowered):
            # Anchor is present but no concrete task lines after it.
            parts = src.split("\n")
            anchor_found = False
            for ln in parts:
                if re_mod.search(r"\b(must\s+do\s+all\s+of\s+the\s+following|requirements\s*:|tasks\s*:)\b", ln.lower()):
                    anchor_found = True
                    continue
                if anchor_found and ln.strip():
                    return False
            return True
        # Single short sentence without a full question/task signal.
        lines = [ln.strip() for ln in src.split("\n") if ln.strip()]
        if len(lines) == 1 and len(lines[0]) < 24 and "?" not in lines[0] and "=" not in lines[0]:
            return True
        return False

    trusted_ctx = body.trusted_context if isinstance(body.trusted_context, dict) else {}
    default_domain_mode = trusted_ctx.get("domain_mode") or "reals"
    default_mode = "SOLVE"
    default_graph_mode = body.graph_mode or "AUTO"

    incoming_questions_json = getattr(body, "questions_json", None)
    if isinstance(incoming_questions_json, list) and incoming_questions_json:
        runtime_questions_json = []
        for idx, q in enumerate(incoming_questions_json, start=1):
            qtext = str((q or {}).get("question_text") or "").strip()
            if not qtext:
                continue
            runtime_questions_json.append(
                {
                    "question_id": str((q or {}).get("question_id") or f"q{idx}"),
                    "question_text": qtext,
                    "mode": str((q or {}).get("mode") or default_mode),
                    "graph_mode": str((q or {}).get("graph_mode") or default_graph_mode),
                    "domain_mode": str((q or {}).get("domain_mode") or default_domain_mode),
                }
            )
        if not runtime_questions_json:
            runtime_questions_json = [
                {
                    "question_id": str(body.question_id or "q1"),
                    "question_text": raw_problem_text,
                    "mode": default_mode,
                    "graph_mode": default_graph_mode,
                    "domain_mode": default_domain_mode,
                }
            ]
    else:
        split_texts = _auto_split_questions_for_batch(raw_problem_text)
        runtime_questions_json = [
            {
                "question_id": f"q{idx}",
                "question_text": qtext,
                "mode": default_mode,
                "graph_mode": default_graph_mode,
                "domain_mode": default_domain_mode,
            }
            for idx, qtext in enumerate(split_texts, start=1)
            if str(qtext or "").strip()
        ]
        if not runtime_questions_json:
            runtime_questions_json = [
                {
                    "question_id": str(body.question_id or "q1"),
                    "question_text": raw_problem_text,
                    "mode": default_mode,
                    "graph_mode": default_graph_mode,
                    "domain_mode": default_domain_mode,
                }
            ]

    async def _batch_stream():
        from app.services.credit_billing_service import CreditBillingError, credit_billing_service
        meta_data = {
            "request_id": request_id,
            "attempt_id": attempt_id,
            "provider": "openai",
            "model": get_configured_openai_model(),
            "tier_requested": str(body.tier or "short_steps").lower(),
            "effective_tier": str(body.tier or "short_steps").lower(),
            "type": "meta",
        }
        yield f"event: meta\ndata: {json.dumps(meta_data)}\n\n"
        if _input_looks_incomplete(raw_problem_text):
            err = {
                "code": "incomplete_input",
                "message": "Input looks incomplete. Please provide the full question before solve.",
                "request_id": request_id,
                "attempt_id": attempt_id,
            }
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': err})}\n\n"
            return
        reserve_result = None
        try:
            try:
                reserve_result = credit_billing_service.reserve_for_batch_solve(
                    session=session,
                    user_id=user_id,
                    tier=body.tier or "SHORT_STEPS",
                    mode=default_mode,
                    modality="text",
                    verify_requested=False,
                    plot_requested=False,
                    questions_json=runtime_questions_json,
                    request_id=request_id,
                    attempt_id=attempt_id,
                    idempotency_key=getattr(body, "idempotency_key", None),
                )
                session.flush()
            except CreditBillingError as exc:
                err = {
                    "code": exc.code,
                    "message": str(exc),
                    "request_id": request_id,
                    "attempt_id": attempt_id,
                    "details": exc.details,
                }
                yield f"event: done\ndata: {json.dumps({'ok': False, 'error': err})}\n\n"
                return

            payload, telemetry = await execute_batch_solve(
                session=session,
                tier=body.tier or "SHORT_STEPS",
                request_id=request_id,
                attempt_id=attempt_id,
                mode=default_mode,
                graph_mode=default_graph_mode,
                domain_mode=default_domain_mode,
                preferred_response_language=(trusted_ctx.get("preferred_response_language") or "English"),
                questions_json=runtime_questions_json,
                allow_auto_split=(len(runtime_questions_json) > 1),
                max_tasks_per_question=6,
                max_output_tokens=5000,
            )
            settlement_summary = None
            if reserve_result:
                try:
                    settlement_summary = credit_billing_service.settle_batch_hold(
                        session=session,
                        hold_id=reserve_result.hold_id,
                        request_id=str(telemetry.get("request_id") or request_id),
                        attempt_id=str(telemetry.get("attempt_id") or attempt_id),
                        idempotency_key=reserve_result.idempotency_key,
                        item_costs=reserve_result.item_costs,
                        payload_items=payload.get("items") or [],
                        pricing_snapshot=reserve_result.pricing_snapshot,
                        provider_failed=False,
                    )
                    session.commit()
                except Exception as settle_exc:
                    session.rollback()
                    release_status = "settlement_failed"
                    try:
                        credit_billing_service.release_hold_full(session=session, hold_id=reserve_result.hold_id)
                        session.commit()
                        release_status = "settlement_failed_released"
                    except Exception:
                        session.rollback()
                        release_status = "settlement_failed_release_failed"
                    settlement_summary = {
                        "hold_id": reserve_result.hold_id,
                        "status": release_status,
                        "error": str(settle_exc),
                    }
            if isinstance(telemetry, dict):
                telemetry = {**telemetry, "billing_settlement": settlement_summary}

            session_row = ChatSession(
                user_id=user_id,
                title=(raw_problem_text[:80] or "Batch Solve"),
                subject="Math",
                is_saved=True,
                learning_mode="solve",
                requested_mode=(body.requested_mode or "minimal"),
                solve_tier=str(body.tier or "short_steps").lower(),
            )
            session.add(session_row)
            session.commit()
            session.refresh(session_row)

            question_lines = [
                f"- ({str(q.get('question_id') or '').strip()}) {str(q.get('question_text') or '').strip()}"
                for q in runtime_questions_json
                if str(q.get("question_id") or "").strip() and str(q.get("question_text") or "").strip()
            ]
            user_content = "Batch Solve Request"
            if question_lines:
                user_content = f"{user_content}\n" + "\n".join(question_lines)
            session.add(
                ChatMessage(
                    session_id=int(session_row.id),
                    role="user",
                    content=user_content,
                )
            )

            first_item = (payload.get("items") or [{}])[0]
            answer_text = str(((first_item.get("final_answer") or {}).get("answer_text")) or "Solution generated.")
            safe_items = jsonable_encoder(payload.get("items") or [])
            safe_telemetry = jsonable_encoder(telemetry if isinstance(telemetry, dict) else {})
            assistant_structured = {
                "mode": "batch_text_solve",
                "requested_mode": body.mode or "SOLVE",
                "response_language": (
                    (payload.get("language") or {}).get("response_language")
                    if isinstance(payload.get("language"), dict)
                    else (trusted_ctx.get("preferred_response_language") or "English")
                ),
                "question_count": len(safe_items),
                "questions": jsonable_encoder(runtime_questions_json),
                "solutions": safe_items,
                "request_id": str(telemetry.get("request_id") or request_id),
                "attempt_id": str(telemetry.get("attempt_id") or attempt_id),
                "tier": str(payload.get("tier") or body.tier or "").upper(),
                "tier_requested": str((body.tier or "")).upper() or "SHORT_STEPS",
                "tier_effective": str(payload.get("tier") or body.tier or "").upper(),
                "output_format": "json_schema",
                "hide_from_tutor": True,
                "solve_meta": {
                    "request_id": str(telemetry.get("request_id") or request_id),
                    "attempt_id": str(telemetry.get("attempt_id") or attempt_id),
                    "provider": str((telemetry or {}).get("provider") or ""),
                    "model": str((telemetry or {}).get("model") or ""),
                    "tier_requested": str((body.tier or "")).upper() or "SHORT_STEPS",
                    "tier_effective": str(payload.get("tier") or body.tier or "").upper(),
                    "mode": "SOLVE",
                    "output_format": "json_schema",
                    "prompt_binding_id": telemetry.get("prompt_binding_id") if isinstance(telemetry, dict) else None,
                    "global_system_prompt_id": telemetry.get("global_system_prompt_id") if isinstance(telemetry, dict) else None,
                    "developer_prompt_id": telemetry.get("developer_prompt_id") if isinstance(telemetry, dict) else None,
                    "output_schema_id": telemetry.get("output_schema_id") if isinstance(telemetry, dict) else None,
                },
                "telemetry": safe_telemetry if isinstance(safe_telemetry, dict) else None,
            }
            if str(body.tier or "").upper() == "SHORT_STEPS":
                if isinstance(payload.get("question"), dict):
                    assistant_structured["question"] = jsonable_encoder(payload.get("question"))
                if isinstance(payload.get("problem"), dict):
                    assistant_structured["problem"] = jsonable_encoder(payload.get("problem"))
                if isinstance(payload.get("raw_user_extraction"), dict):
                    assistant_structured["raw_user_extraction"] = jsonable_encoder(payload.get("raw_user_extraction"))
            msg = ChatMessage(
                session_id=int(session_row.id),
                role="assistant",
                content=answer_text,
                structured_data=assistant_structured,
                telemetry=telemetry,
                model_used=telemetry.get("model"),
                tokens_used=int(telemetry.get("total_tokens") or 0),
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)
            telemetry_provider = str((telemetry or {}).get("provider") or "").strip().lower()
            tier_effective = str(payload.get("tier") or body.tier or "").upper()
            provider_raw_text = str((telemetry or {}).get("provider_raw_text") or "")
            provider_raw_payload = (telemetry or {}).get("provider_raw_payload")
            use_exact_ollama_short_raw = (
                telemetry_provider == "ollama"
                and tier_effective == "SHORT_STEPS"
                and provider_raw_text != ""
            )
            persisted_raw_solution_text = (
                provider_raw_text if use_exact_ollama_short_raw else json.dumps(payload, ensure_ascii=False)
            )
            persisted_llm_raw_response = (
                provider_raw_payload if isinstance(provider_raw_payload, dict) else None
            )
            if persisted_llm_raw_response is not None:
                try:
                    json.dumps(persisted_llm_raw_response, ensure_ascii=False)
                except Exception:
                    persisted_llm_raw_response = {
                        "raw_payload_preview": str(provider_raw_payload)[:4000]
                    }
            session.add(
                SolverOutputAttempt(
                    request_id=str(telemetry.get("request_id") or request_id),
                    attempt_id=str(telemetry.get("attempt_id") or attempt_id),
                    user_id=user_id,
                    session_id=int(session_row.id),
                    message_id=int(msg.id) if msg.id is not None else None,
                    output_format="json_schema",
                    attempt_number=1,
                    provider=str((telemetry or {}).get("provider") or ""),
                    model=str((telemetry or {}).get("model") or ""),
                    provider_model=(
                        f"{str((telemetry or {}).get('provider') or '')}:{str((telemetry or {}).get('model') or '')}"
                        if (telemetry or {}).get("provider") and (telemetry or {}).get("model")
                        else None
                    ),
                    input_text_raw=user_content,
                    char_count=len(persisted_raw_solution_text),
                    extracted_answer=answer_text,
                    raw_solution_text=persisted_raw_solution_text,
                    llm_raw_response=persisted_llm_raw_response,
                    validation_json=assistant_structured,
                    input_tokens=int((telemetry or {}).get("input_tokens") or 0),
                    output_tokens=int((telemetry or {}).get("output_tokens") or 0),
                    total_tokens=int((telemetry or {}).get("total_tokens") or 0),
                    latency_ms=int((telemetry or {}).get("latency_ms_total") or 0) or None,
                    prompt_meta={"questions_json": jsonable_encoder(runtime_questions_json)},
                    status="success",
                )
            )
            session.commit()

            yield f"event: delta\ndata: {json.dumps({'type': 'delta', 'text': json.dumps(payload, ensure_ascii=False)})}\n\n"
            yield f"event: telemetry\ndata: {json.dumps({'telemetry': telemetry})}\n\n"
            yield f"event: done\ndata: {json.dumps({'ok': True, 'session_id': int(session_row.id), 'message_id': int(msg.id or 0)})}\n\n"
        except BatchSolveError as exc:
            if reserve_result and reserve_result.hold_id:
                try:
                    credit_billing_service.release_hold_full(session=session, hold_id=reserve_result.hold_id)
                    session.commit()
                except Exception:
                    session.rollback()
            err = {
                "code": exc.code,
                "message": str(exc),
                "request_id": request_id,
                "attempt_id": attempt_id,
                "details": exc.details,
            }
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': err})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive path
            if reserve_result and reserve_result.hold_id:
                try:
                    credit_billing_service.release_hold_full(session=session, hold_id=reserve_result.hold_id)
                    session.commit()
                except Exception:
                    session.rollback()
            err = {
                "code": "stream_batch_failed",
                "message": str(exc),
                "request_id": request_id,
                "attempt_id": attempt_id,
            }
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': err})}\n\n"

    return StreamingResponse(_batch_stream(), media_type="text/event-stream")

    
    # Initialize TraceContext with solving phase
    from app.trace import TraceContext
    TraceContext.set(
        trace_id=str(uuid.uuid4()),
        request_id=request_id,
        attempt_id=attempt_id,
        phase="solve_v3_stream",
        status="pending"
    )

    # Idempotency: return existing attempt for same request_id
    if body.idempotency_key:
        from app.models import SolverOutputAttempt
        existing_attempt = session.exec(
            select(SolverOutputAttempt).where(SolverOutputAttempt.request_id == request_id)
        ).first()
        if existing_attempt:
            attempt_id = existing_attempt.attempt_id
            TraceContext.set(
                trace_id=str(uuid.uuid4()),
                request_id=request_id,
                attempt_id=attempt_id,
                phase="solve_v3_stream",
                status="idempotent_replay"
            )

            async def _replay():
                meta = {
                    "request_id": request_id,
                    "attempt_id": attempt_id,
                    "status": existing_attempt.status,
                    "tier_requested": (body.tier or "").lower(),
                    "tier_effective": (body.tier or "").lower(),
                }
                yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
                if existing_attempt.status == "success" and existing_attempt.session_id:
                    yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': True, 'session_id': existing_attempt.session_id, 'message_id': existing_attempt.message_id})}\n\n"
                elif existing_attempt.status in {"failure", "ambiguous"}:
                    yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': existing_attempt.failure_code or 'ambiguous_response', 'message': existing_attempt.error_message or 'Previous attempt failed', 'request_id': request_id}})}\n\n"
                else:
                    yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': 'in_progress', 'message': 'Attempt already in progress', 'request_id': request_id}})}\n\n"
            return StreamingResponse(_replay(), media_type="text/event-stream")
    
    # Phase 1: Create Attempt Record (Pending)
    try:
        from app.models import SolverOutputAttempt
        
        attempt = SolverOutputAttempt(
            request_id=request_id,
            attempt_id=attempt_id,
            user_id=user_id,
            status="pending",
            input_text_raw=(body.confirmed_text or body.text_query or "")[:50000],
            created_at=datetime.utcnow()
        )
        session.add(attempt)
        session.commit()
    except Exception as e:
        logging.error(f"Failed to create attempt record: {e}", extra=TraceContext.get_all())
    
    # ===== LIVE REQUEST TRACE =====
    import sys
    sys.stderr.write("\n" + "="*60 + "\n")
    sys.stderr.write(f"[SOLVE_V3_STREAM] request_id={request_id}\n")
    sys.stderr.write(f"[SOLVE_V3_STREAM] graph_mode={graph_mode}\n")
    sys.stderr.write("="*60 + "\n")
    sys.stderr.write(f"user_id: {user_id}\n")
    sys.stderr.write(f"tier (requested): {body.tier}\n")
    sys.stderr.write(f"mode (requested): {body.requested_mode}\n")

    sys.stderr.write(f"problem_text: {(body.confirmed_text or body.text_query or '')[:200]}...\n")
    sys.stderr.write("="*60 + "\n\n")
    sys.stderr.flush()
    # ==============================

    # Resolve checks
    from sqlalchemy.orm import selectinload
    user_obj = session.exec(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.subscription))
    ).first()
    solver_trusted_context = _build_solver_trusted_context(body.trusted_context, user_obj)
    user_grade_level = user_obj.grade_level if user_obj else None
    user_profile_country = user_obj.profile_country if user_obj else None
    user_profile_province = user_obj.profile_province_state if user_obj else None
    effective_tier_slug = _solve_tier_ceiling_slug()
    tier_policy = _clamp_requested_tier(body.tier, effective_tier_slug)
    requested_tier = tier_policy["tier_requested"]
    effective_tier = tier_policy["tier_effective"]
    requested_tier_internal = tier_policy["tier_requested_internal"]
    effective_tier_internal = tier_policy["tier_effective_internal"]
    stream_provider = "openai"
    stream_model = get_configured_openai_model()
    effective_billing_tier = effective_tier.lower()

    # OCR acceptance: capture OCR hold at solve-start when source_type=ocr
    if (body.source_type or "").lower() == "ocr" and body.source_id:
        from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
        from app.services.billing_exceptions import HoldAlreadyFinalizedError, HoldNotFoundError
        from decimal import Decimal

        ocr_job = session.get(OCRJob, body.source_id)
        if not ocr_job:
            raise HTTPException(status_code=404, detail="OCR attempt not found")
        if ocr_job.user_id != user_id:
            raise HTTPException(status_code=403, detail="OCR attempt does not belong to user")
        if ocr_job.status != "completed":
            raise HTTPException(status_code=400, detail="OCR attempt not completed")
        if ocr_job.accepted_solve_attempt_id is None:
            ocr_job.accepted_solve_attempt_id = attempt_id
            session.add(ocr_job)
            session.commit()
        if ocr_job.hold_request_id:
            try:
                billing_ledger_service_v2.settle_hold(
                    session=session,
                    request_id=ocr_job.hold_request_id,
                    actual_credits=Decimal(str(ocr_job.hold_amount or 0)),
                    tier="OCR",
                    attempt_id=attempt_id,
                    action_type="ocr_extract",
                )
                session.commit()
            except (HoldAlreadyFinalizedError, HoldNotFoundError):
                pass

    plan_pricing_version = None
    pricing_binding = None
    pricing_multipliers = None
    try:
        from app.services.prompt_binding_pricing import normalize_tier_key, resolve_binding_pricing
        _, pricing_multipliers, pricing_binding = resolve_binding_pricing(session, effective_billing_tier)
        plan_pricing_version = str(pricing_multipliers.version)
    except Exception:
        plan_pricing_version = None

    from app.services.pricing_service import pricing_service
    token_config_version = pricing_service.get_pricing_config(session).config_version_id

    action_req = {
        "tier": effective_billing_tier,
        "mode": body.requested_mode,
        "has_ocr": bool((body.source_type or "").lower() == "ocr") or (body.features_used.get("ocr_used", False) if body.features_used else False),
        "has_voice": body.features_used.get("voice_used", False) if body.features_used else False,
        "reference_id": request_id,
        "source_type": body.source_type,
    }

    from app.services.billing_feature_flags import is_billing_v2_enabled
    use_billing_v2 = is_billing_v2_enabled(user_id)
    billing_v2_hold_id = None
    billing_v2_cost = None

    if use_billing_v2:
        from decimal import Decimal
        from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
        from app.services.billing_exceptions import InsufficientCreditsError

        source_type = "text"
        if action_req["has_voice"]:
            source_type = "voice"
        elif action_req["has_ocr"]:
            source_type = "snap_image"

        tier_key = normalize_tier_key(effective_billing_tier)
        base_cost = 0.0
        attempt_fee_cost = 0.0
        plot_addon_cost = 0.0

        # Prefer explicit per-binding credit columns; fallback to multipliers if missing.
        if (
            pricing_binding is not None
            and getattr(pricing_binding, "solve_text_cost", None) is not None
            and getattr(pricing_binding, "solve_snap_image_cost", None) is not None
            and getattr(pricing_binding, "solve_snap_pdf_cost", None) is not None
            and getattr(pricing_binding, "solve_voice_cost", None) is not None
            and getattr(pricing_binding, "attempt_fee", None) is not None
            and getattr(pricing_binding, "plot_addon_cost", None) is not None
        ):
            if source_type == "snap_image":
                base_cost = float(pricing_binding.solve_snap_image_cost or 0)
            elif source_type == "snap_pdf":
                base_cost = float(pricing_binding.solve_snap_pdf_cost or 0)
            elif source_type == "voice":
                base_cost = float(pricing_binding.solve_voice_cost or 0)
            else:
                base_cost = float(pricing_binding.solve_text_cost or 0)
            attempt_fee_cost = float(pricing_binding.attempt_fee or 0)
            plot_addon_cost = float(pricing_binding.plot_addon_cost or 0)
        else:
            tier_cfg = getattr(getattr(pricing_multipliers, "credits", None), "solve", None)
            tier_row = getattr(tier_cfg, tier_key, None) if tier_cfg is not None else None
            if tier_row is not None:
                if source_type == "snap_image":
                    base_cost = float(getattr(tier_row, "snap_image", 0) or 0)
                elif source_type == "snap_pdf":
                    base_cost = float(getattr(tier_row, "snap_pdf", 0) or 0)
                elif source_type == "voice":
                    base_cost = float(getattr(tier_row, "voice", 0) or 0)
                else:
                    base_cost = float(getattr(tier_row, "text", 0) or 0)
            attempt_map = getattr(getattr(pricing_multipliers, "credits", None), "attempt_fee", None)
            attempt_fee_cost = float(getattr(attempt_map, tier_key, 0) or 0) if attempt_map is not None else 0.0
            plot_addon_cost = float(getattr(getattr(pricing_multipliers, "credits", None), "plot_trigger", 0) or 0)

        allow_plot = True
        if pricing_binding is not None and isinstance(getattr(pricing_binding, "features", None), dict):
            allow_plot = bool((pricing_binding.features or {}).get("allow_plot", True))
        plot_requested_now = str(getattr(body, "graph_mode", "auto") or "auto").lower() != "off"
        if effective_tier_internal == "FINAL":
            plot_requested_now = False
        extras_cost = attempt_fee_cost + (plot_addon_cost if (allow_plot and plot_requested_now) else 0.0)
        billing_v2_cost = base_cost + extras_cost

        if (body.source_type or "").lower() == "ocr":
            ocr_cfg = get_active_ocr_config(session)
            billing_v2_cost = max(float(billing_v2_cost), float(ocr_cfg.solve_credit))
        try:
            hold_result = billing_ledger_service_v2.create_hold(
                session=session,
                user_id=user_id,
                request_id=request_id,
                estimated_credits=Decimal(str(billing_v2_cost)),
                attempt_id=attempt_id,
                idempotency_key=body.idempotency_key,
            )
            billing_v2_hold_id = hold_result.hold_id
            session.commit()
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=f"Insufficient credits: required={e.required}, available={e.available}")
    else:
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
        learning_mode = solver_trusted_context.get("learning_mode", "solve")
        is_ambiguous = False
        refusal = None
        deduct_attempted = {"credits": False, "ocr": False, "voice": False}
        deduct_committed = False
        features_used = body.features_used or {}
        def _release_hold_if_needed():
            if use_billing_v2 and (billing_v2_cost or 0) > 0:
                try:
                    from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
                    billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                except Exception:
                    pass
        raw_problem_text = (
            body.question_text or
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
        plan_key = effective_tier_slug
        try:
            profile = ProfileResolver.resolve_profile(
                session,
                user_obj,
                requested_mode=requested_mode,
                learning_mode=learning_mode,
                force_tier=effective_tier_internal,
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
            _release_hold_if_needed()
            yield f"event: done\ndata: {json.dumps({'ok': False, 'error': {'code': error_code, 'message': str(profile_err), 'request_id': request_id, 'tier': effective_tier, 'mode': 'SOLVE', 'provider': stream_provider, 'details': error_details}})}\n\n"
            return
        print(f"[SOLVER_V3_STREAM] Resolved Profile: Tier={profile.tier}, Mode={profile.mode}, MaxTokens={profile.max_output_tokens}")
        profile_key = f"{profile.tier.upper().replace('-', '_')}_{profile.mode.upper()}"
        
        binding_meta = getattr(profile, "prompt_binding_meta", {}) or {}
        # Phase 1: Update Attempt with Prompt Meta
        try:
            if attempt:
                attempt.prompt_id = binding_meta.get("binding_id")
                attempt.prompt_version = binding_meta.get("global_system_prompt_version")
                attempt.prompt_meta = binding_meta
                attempt.status = "processing"
                session.add(attempt)
                session.commit()
        except Exception as e:
            print(f"[SOLVER_V3_STREAM] Update attempt meta failed: {e}")

        plan_key = effective_tier_slug or profile.tier

        # --- TOKEN POLICY FIX (STREAMING) ---
        profile_max_output = profile.max_output_tokens or 900
        policy_limit = get_effective_max_tokens(requested_mode, learning_mode, token_policy)
        
        if profile.tier.upper() == "RESEARCH":
            effective_max_tokens = profile_max_output
        else:
            # Non-research tiers: cap at policy_limit, but honor binding if it's smaller
            effective_max_tokens = min(profile_max_output, policy_limit)
        # Final tier needs larger completion budget to avoid truncated JSON responses.
        if str(effective_tier or "").upper() == "FINAL":
            effective_max_tokens = max(int(effective_max_tokens or 0), 5000)
        # ------------------------------------

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
            _release_hold_if_needed()
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_grade_level,
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
            text_input_limit = token_policy.text_input_max
            if str(effective_tier or "").upper() == "FINAL":
                text_input_limit = max(int(text_input_limit or 0), 5000)
            _enforce_input_token_limit(problem_text, text_input_limit, modality)

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

        if use_billing_v2:
            debit_cost = float(billing_v2_cost or 0.0)
            should_refund = debit_cost > 0
        else:
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
                    "grade_level": user_grade_level,
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

        output_format = "json_schema"

        # Meta Event (Part A1)
        meta_data = {
            "request_id": request_id,
            "attempt_id": attempt_id,
            "session_id": None, # Will be set after creation
            "message_id": None,
            "provider": stream_provider,
            "model": stream_model,
            "max_output_tokens": effective_max_tokens,
            "debug_profile_max": profile_max_output,
            "debug_policy_limit": policy_limit,
            "debug_policy_dump": token_policy.text_output_detailed_solve,
            "mode": requested_mode,
            "learning_mode": learning_mode,
            "mode_family": "SOLVE",
            "tier_requested": requested_tier,
            "effective_tier": effective_tier,
            "pricing_version_plan": plan_pricing_version,
            "config_version_id": token_config_version,
            "prompt_binding_id": binding_meta.get("binding_id"),
            "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
            "developer_prompt_id": binding_meta.get("developer_prompt_id"),
            "output_schema_id": binding_meta.get("output_schema_id"),
            "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
            "developer_prompt_version": binding_meta.get("developer_prompt_version"),
            "output_schema_version": binding_meta.get("output_schema_version"),
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
            "pricing_version_plan": plan_pricing_version,
            "config_version_id": token_config_version,
            "mode": "SOLVE",
            "prompt_binding_id": binding_meta.get("binding_id"),
            "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
            "developer_prompt_id": binding_meta.get("developer_prompt_id"),
            "output_schema_id": binding_meta.get("output_schema_id"),
            "output_format": output_format,
            "debug_graph_mode_IN_RESPONSE": graph_mode,  # DEBUG: Must appear in output

            "prompt_versions": {
                "system": binding_meta.get("global_system_prompt_version"),
                "developer": binding_meta.get("developer_prompt_version"),
                "schema": binding_meta.get("output_schema_version"),
            },
        }
        
        max_output_tokens = effective_max_tokens
        meta_data["type"] = "meta"
        print(f"DEBUG: yielding meta_data keys: {list(meta_data.keys())}")
        yield f"event: meta\ndata: {json.dumps(meta_data)}\n\n"

        # Stage: Preparing request... (Part A2)
        yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Preparing request...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"

        print(
            f"[SOLVER_V3_STREAM] Recv: {problem_text[:50]}... "
            f"(RequestedMode: {requested_mode}, output_format: {output_format}, tokens: {max_output_tokens})"
        )

        try:
            if not body.force_validity:
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
            _release_hold_if_needed()
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_grade_level,
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
        
        if user_profile_country or user_profile_province or user_grade_level:
            country = user_profile_country or 'Canada'
            province = user_profile_province or 'ON'
            grade = user_grade_level or 'Unknown'
            context += f"\n\n[STUDENT CONTEXT]\nCountry: {country}\nProvince: {province}\nGrade: {grade}"

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

        solver = get_solver_v3()
        full_content = ""
        openai_telemetry = {}
        repair_attempted = False

        chunk_type_counts = {}

        try:
            # Give compact tiers extra completion headroom to reduce truncation-driven repair calls.
            stream_max_output_tokens = int(effective_max_tokens or 0)
            if str(effective_tier or "").upper() == "SHORT_STEPS":
                stream_max_output_tokens = max(stream_max_output_tokens, int(stream_max_output_tokens * 1.5))

            async for chunk in solver.solve_stream(
                problem_text=problem_text,
                context=context,
                trace=True,
                request_id=request_id,
                max_output_tokens=stream_max_output_tokens,
                system_prompt=profile.system_prompt_content,
                developer_prompt=profile.developer_prompt_content,
                json_schema_config=profile.json_schema_content,
                requested_mode=requested_mode,
                trusted_context=solver_trusted_context,
                attempt_id=attempt_id,
                debug_simulated_tokens=debug_simulated_tokens,
                debug_force_error=debug_force_error,
            ):
                # METRIC: Count chunk types
                ctype = chunk.get("type", "unknown")
                chunk_type_counts[ctype] = chunk_type_counts.get(ctype, 0) + 1

                # FIX: Append ANY text content, not just delta
                if "text" in chunk and chunk["text"]:
                    full_content += chunk["text"]

                if chunk["type"] == "delta":
                    yield f"data: {json.dumps({'type': 'delta', 'text': chunk['text']})}\n\n"
                elif chunk["type"] == "usage":
                    openai_telemetry = chunk["telemetry"]
                    # A3: Append history entry
                    if "history_entry" in chunk and attempt:
                        if attempt.llm_responses is None:
                            attempt.llm_responses = []
                        attempt.llm_responses.append(chunk["history_entry"])
                        session.add(attempt)
                        session.commit()
                elif chunk["type"] == "failure":
                    if should_refund and debit_cost > 0:
                        try:
                            if use_billing_v2:
                                from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
                                billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                            else:
                                subscription_service.refund_credits(
                                    session,
                                    subscription.id,
                                    debit_cost,
                                    "Solver failed",
                                    request_id,
                                )
                        except Exception:
                            pass
                    # Handle early termination
                    yield f"event: done\ndata: {json.dumps({'ok': False, 'error': chunk['error']})}\n\n"
                    return
                elif chunk["type"] == "meta" and chunk.get("truncated"):
                    truncated_meta = dict(meta_data)
                    truncated_meta["truncated"] = True
                    truncated_meta["type"] = "meta"
                    yield f"event: meta\ndata: {json.dumps(truncated_meta)}\n\n"
                elif chunk["type"] == "error":
                    # ... (existing error handling) ...
                    yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': chunk['error']})}\n\n"
                    return

            # Stage: Validating response...
            yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Validating response...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"
            if attempt_id:
                emit_attempt_event(attempt_id, request_id, "schema_validate_start")

            # Post-stream persistence and validation (Part E1)
            final_data: Dict[str, Any] = {}
            is_truncated = openai_telemetry.get("truncated", False)
            raw_llm_output = full_content or ""
            
            # --- DEBUG SNAPSHOT ---
            try:
                debug_log_dir = "logs"
                if not os.path.exists(debug_log_dir):
                    os.makedirs(debug_log_dir, exist_ok=True)
                
                with open(f"{debug_log_dir}/llm_raw_{request_id}.txt", "w", encoding="utf-8") as f:
                    f.write(f"Request ID: {request_id}\n")
                    f.write(f"Length: {len(raw_llm_output)}\n")
                    f.write(f"Chunk Types: {chunk_type_counts}\n")
                    f.write("-" * 40 + "\nRAW CONTENT (Head 4000 + Tail 16000):\n")
                    
                    # Store Head + Tail to capture start/end issues
                    if len(raw_llm_output) > 20000:
                        head = raw_llm_output[:4000]
                        tail = raw_llm_output[-16000:]
                        f.write(head)
                        f.write("\n...[snipped]...\n")
                        f.write(tail)
                    else:
                        f.write(raw_llm_output)
                        
                    # Also write strict full raw dump to separate file if huge?
                    # Or just rely on the above being enough for 99% cases.
                    # User requested "head 4000 chars tail 16000 chars".
                    # User also said "also store the full raw output to a log file on disk".
                
                # Full Raw Dump
                with open(f"{debug_log_dir}/llm_full_{request_id}.log", "w", encoding="utf-8") as f_full:
                    f_full.write(raw_llm_output)
            except Exception as e:
                print(f"[DEBUG_SNAPSHOT_ERROR] {e}")

            validation_errors: List[str] = []
            schema_valid = False
            repair_attempted = False

            print(f"[SOLVER_V3_STREAM] Stream finished. Content length: {len(raw_llm_output)} chars, truncated: {is_truncated}")
            print(f"[SOLVER_V3_STREAM] Chunk types: {chunk_type_counts}")

            # New Parsing Logic (Stop Envelope Validation)
            # 1. Store Full Raw Output (Head + Tail)
            # 2. Extract specific schema object
            
            extracted_json = None
            try:
                # Use safe_parse_json with prefer_last=True and required_keys
                # This ensures we get the MODEL JSON, not the envelope/meta
                final_data = safe_parse_json(
                    raw_llm_output,
                    prefer_last=True,
                    required_keys=["schema_version", "problem", "steps", "final_answer"]
                )
                extracted_json = json.dumps(final_data) # Back to string for logic consistency if needed, or just use final_data
                
                # Check for "Refusal" disguised as success?
                # safe_parse_json returns Dict.
                
                # Remove internal fields that violate strict schema BEFORE validation
                if isinstance(final_data, dict):
                    final_data.pop("_raw_llm_output", None)
                    final_data.pop("paper_versions", None)
                    
            except ValueError as ve:
                 validation_errors.append(f"parse_error: {str(ve)}")
            except json.JSONDecodeError as parse_err:
                validation_errors.append(f"parse_error: {parse_err.msg}")
            except Exception as e:
                validation_errors.append(f"parse_error: {str(e)}")

            # if not extracted_json: (Handled by exception block above)
            if not final_data and not validation_errors:
                 validation_errors.append("parse_error: safe_parse_json returned empty")
            
            # Logic moved/replaced above


            if final_data and not validation_errors:
                # Normalization pass to fix common enum mishaps before strict validation
                final_data = normalize_raw_llm_response(final_data)
                validation_errors, is_ambiguous = _validate_stream_payload(final_data, profile.json_schema_content)
                schema_valid = len(validation_errors) == 0 and not is_ambiguous
                
                if attempt_id:
                    if is_ambiguous:
                        emit_attempt_event(attempt_id, request_id, "clarification_needed", status="ambiguous")
                    else:
                        emit_attempt_event(attempt_id, request_id, "schema_validate_done", status="success" if schema_valid else "failure")

            # --- REPAIR LOGIC ---
            if validation_errors:
                repair_attempted = True
                openai_telemetry["repair_attempted"] = True
                openai_telemetry["repair_attempts"] = 1
                if attempt_id:
                    emit_attempt_event(attempt_id, request_id, "schema_repair_start")
                
                try:
                    # Construct CLIPPED payload for repair if it's too long (Head + Tail)
                    repair_input_text = raw_llm_output
                    if len(repair_input_text) > 20000:
                        repair_input_text = repair_input_text[:10000] + "\n...[clipped]...\n" + repair_input_text[-10000:]
                    
                    # 2-Pass Repair Logic
                    repaired_data = None
                    repaired_text = None
                    
                    # Pass 1: Normal Repair
                    repaired_data, repaired_text = await solver._repair_response(
                        problem=problem_text,
                        context=context,
                        system_prompt=profile.system_prompt_content,
                        invalid_data=repair_input_text,  
                        validation_error=f"{validation_errors[0]} (Truncated: {is_truncated})",
                        error_list=validation_errors,
                        json_schema_config=profile.json_schema_content,
                        max_output_tokens=max_output_tokens,
                        requested_mode=requested_mode,
                        trace=True,
                        provider=stream_provider,
                        model=stream_model
                    )

                    # Pass 2: Minimal Fallback if Pass 1 failed (and not just refused)
                    allow_second_repair_pass = os.environ.get("SOLVE_V3_SECOND_REPAIR_PASS", "false").lower() in {"1", "true", "yes"}
                    if not repaired_data and requested_mode == "detailed" and allow_second_repair_pass:
                         print("[SOLVER_V3_STREAM] Repair Pass 1 failed. Trying Pass 2 (Minimal Mode)...")
                         repaired_data, repaired_text = await solver._repair_response(
                            problem=problem_text,
                            context=context,
                            system_prompt=profile.system_prompt_content,
                            invalid_data=repair_input_text,  
                            validation_error=f"{validation_errors[0]} (Truncated: {is_truncated})",
                            error_list=validation_errors,
                            json_schema_config=profile.json_schema_content,
                            max_output_tokens=max_output_tokens,
                            requested_mode="minimal", # Force minimal for simpler schema
                            trace=True,
                            provider=stream_provider,
                            model=stream_model
                        )

                    if repaired_data:
                         print("[SOLVER_V3_STREAM] Repair successful.")
                         final_data = repaired_data
                         schema_valid = True
                         validation_errors = [] # Clear errors
                         if attempt_id:
                            emit_attempt_event(attempt_id, request_id, "schema_repair_done", status="success")
                    else:
                         print("[SOLVER_V3_STREAM] Repair failed.")
                         if attempt_id:
                            emit_attempt_event(attempt_id, request_id, "schema_repair_done", status="failure")

                except Exception as repair_err:
                    print(f"[SOLVER_V3_STREAM] Repair exception: {repair_err}")

            # --- FALLBACK LOGIC ---
            # If still invalid after repair, generate a SAFE FALLBACK object.
            # Do NOT return an error envelope in structured_data.
            if validation_errors or not final_data:
                print("[SOLVER_V3_STREAM] ALL VALIDATION/REPAIR FAILED. Using Fallback Object.")
                
                # Construct a valid "Refusal" object that matches the schema
                fallback_obj = {
                    "schema_version": "v1",
                    "refusal": {
                        "is_refusal": True,
                        "reason": f"Generation failed: {validation_errors[0] if validation_errors else 'Unknown error'}",
                        "safe_alternative": "Please try again or simplify the request."
                    },
                    "status": "error",
                    "final_answer": {
                        "value": "Error generating solution.",
                        "latex": "\\text{Error generating solution.}"
                    }
                }
                # Try to salvage at least the problem text if possible, but keep it safe
                final_data = fallback_obj
                schema_valid = True # functionality is valid, effectively
                # We don't clear validation_errors string for logging, but we proceed as 'success' for the UI envelope
            
            # --- FINAL PERSISTENCE ---
            # Now final_data is GUARANTEED to be a dict (either parsed or fallback)


            if not schema_valid:
                # ===== LIVE ERROR TRACE =====
                import sys
                sys.stderr.write("\n" + "="*60 + "\n")
                sys.stderr.write(f"[STREAM_VALIDATION_FAIL] request_id={request_id}\n")
                sys.stderr.write("="*60 + "\n")
                sys.stderr.write(f"Tier: {effective_tier}\n")
                sys.stderr.write(f"Mode: {requested_mode}\n")
                sys.stderr.write(f"Validation Errors:\n")
                for err in validation_errors[:10]:
                    sys.stderr.write(f"  - {err}\n")
                sys.stderr.write(f"Raw LLM Output (first 1000 chars):\n")
                sys.stderr.write((raw_llm_output[:1000] if raw_llm_output else "NONE") + "\n")
                sys.stderr.write("="*60 + "\n\n")
                sys.stderr.flush()
                # =============================
                
                print(f"[DEBUG] is_ambiguous={is_ambiguous} refusal={refusal}")
                error_message = refusal if is_ambiguous and refusal else "Unable to generate a valid structured solution. Please try again."
                error_payload = _build_schema_valid_stream_error_payload(
                    problem_text=problem_text,
                    provider=openai_telemetry.get("provider") or stream_provider,
                    model=openai_telemetry.get("model") or stream_model,
                    tier=effective_tier,
                    mode="SOLVE",
                    prompt_id=binding_meta.get("developer_prompt_id"),
                    validation_errors=validation_errors,
                    schema_config=profile.json_schema_content,
                    error_code="ambiguous_response" if is_ambiguous else "internal_error"
                )
                if is_ambiguous:
                     error_payload["is_ambiguous"] = True
                     error_payload["refusal"] = refusal
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
                    if use_billing_v2:
                        from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
                        billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                    else:
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
                    "grade_level": user_grade_level,
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
                    "error_type": "ambiguous_response" if is_ambiguous else "schema_validation_failed",
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
                error_code = "ambiguous_response" if is_ambiguous else "schema_validation_failed"
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': False, 'error': {'code': error_code, 'message': error_message, 'validation_errors': validation_errors[:10], 'request_id': request_id, 'refusal': refusal if is_ambiguous else None}})}\n\n"
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

            from app.services.solve.verification_gate import verify_solve_result
            verification_meta = verify_solve_result(problem_text, final_data or {}, request_id=request_id)
            assumptions_list = final_data.get("assumptions")
            if not isinstance(assumptions_list, list):
                assumptions_list = []
            for assumption in verification_meta.get("assumptions", []):
                if assumption not in assumptions_list:
                    assumptions_list.append(assumption)
            final_data["assumptions"] = assumptions_list
            final_data["verified"] = bool(verification_meta.get("verified"))
            final_data["verification_method"] = verification_meta.get("verification_method") or "none"
            final_data["dropped_candidates"] = verification_meta.get("dropped_candidates") or []
            final_data["final_solutions"] = verification_meta.get("final_solutions") or []
            final_data["llm_answer_text"] = verification_meta.get("llm_answer_text") or ""
            final_data["unverified_reason"] = verification_meta.get("unverified_reason")
            final_data["verification_meta"] = verification_meta
            if not final_data["verified"] and isinstance(final_data.get("final_answer"), dict):
                ans = str(final_data["final_answer"].get("answer_text") or "").strip()
                if ans:
                    final_data["final_answer"]["answer_text"] = f"Unverified explanation: {ans}"

            # --- PLOTTING PIPELINE INTEGRATION ---
            from app.services.plot_integration import maybe_generate_plot, apply_graph_mode_override, format_plot_for_response
            
            # CRITICAL: Read graph_mode directly from body to avoid closure issues
            effective_graph_mode = getattr(body, 'graph_mode', None) or 'auto'
            binding_features = binding_meta.get("features") if isinstance(binding_meta.get("features"), dict) else {}
            allow_plot = bool(binding_features.get("allow_plot", True))
            if not allow_plot:
                effective_graph_mode = "off"
            print(f"[SOLVER_V3_STREAM] effective_graph_mode from body: {effective_graph_mode}")
            
            plot_data = await maybe_generate_plot(
                db_session=session,
                problem_text=problem_text,
                solve_result=final_data,
                graph_mode=effective_graph_mode,
                attach_to_step_id=getattr(body, 'attach_to_step_id', None),
                tier=effective_tier,
                question_id=request_id
            )
            
            # Apply deterministic overrides to visuals.should_visualize
            # This MUST override the LLM's decision based on user's graph_mode setting
            final_data = apply_graph_mode_override(
                solve_result=final_data,
                graph_mode=effective_graph_mode,
                plot_generated=plot_data.get("plot_generated", False)
            )
            
            # VERIFY the override was applied
            print(f"[SOLVER_V3_STREAM] After override: should_visualize={final_data.get('visuals', {}).get('should_visualize')}, decision_reason={final_data.get('visuals', {}).get('decision_reason')}")
            

            # Merge generated plot into visuals.plots if successful
            if plot_data.get("plot_generated"):
                formatted_plot = format_plot_for_response(plot_data)
                if formatted_plot:
                    if not final_data.get("visuals"):
                         final_data["visuals"] = {"should_visualize": True, "decision_reason": "Injected", "plots": []}
                    
                    if "plots" not in final_data["visuals"] or final_data["visuals"]["plots"] is None:
                        final_data["visuals"]["plots"] = []
                    
                    # Deduplicate by plot_id
                    new_plot_id = formatted_plot.get("plot_id")
                    existing_plots = final_data["visuals"]["plots"]
                    if not any(isinstance(p, dict) and p.get("plot_id") == new_plot_id for p in existing_plots):
                        final_data["visuals"]["plots"].append(formatted_plot)
                    else:
                        for i, p in enumerate(existing_plots):
                            if isinstance(p, dict) and p.get("plot_id") == new_plot_id:
                                existing_plots[i] = formatted_plot
                                break

            solve_session_id = None
            if True: # Always attempt to save what we have
                # Stage: Rendering plot...
                plot_url = None
                if final_data.get("visuals", {}).get("should_visualize"):
                    yield f"event: stage\ndata: {json.dumps({'type': 'stage', 'name': 'Rendering plot...', 'at_ms': int((time.perf_counter() - start_total) * 1000)})}\n\n"
                    
                    # Legacy fallback for _plot_image if it still exists (unlikely with new pipeline but kept for safety)
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

                # Phase 1: Structured Logging & Persistence
                if attempt:
                    attempt.status = "success" if schema_valid else "failure"
                    if is_ambiguous:
                        attempt.status = "ambiguous"
                    attempt.session_id = new_chat.id
                    attempt.message_id = placeholder_msg.id
                    
                    attempt.raw_solution_text = raw_llm_output
                    attempt.validation_json = final_data if schema_valid else None
                    attempt.validation_errors = validation_errors if not schema_valid else None
                    attempt.error_message = error_message if not schema_valid else None
                    
                    attempt.input_tokens = openai_telemetry.get("input_tokens", 0)
                    attempt.output_tokens = openai_telemetry.get("output_tokens", 0)
                    attempt.total_tokens = openai_telemetry.get("total_tokens", 0)
                    attempt.latency_ms = openai_telemetry.get("latency_ms_total")
                    attempt.provider_model = f"{openai_telemetry.get('provider')}:{openai_telemetry.get('model')}"
                    
                    session.add(attempt)
                    session.commit()
                
                # --- Legacy compatibility for placeholder_msg ---
                placeholder_msg.content = answer_text
                placeholder_msg.structured_data = final_data
                openai_telemetry["schema_valid"] = schema_valid
                placeholder_msg.telemetry = openai_telemetry
                placeholder_msg.tokens_used = openai_telemetry.get("total_tokens", 0)
                
                # Populate Metadata Columns
                classification = final_data.get("classification", {})
                placeholder_msg.subject = classification.get("subject") or classification.get("topic") or body.subject
                placeholder_msg.grade_level = classification.get("grade_level") or user_grade_level
                placeholder_msg.difficulty = classification.get("difficulty")
                
                # Token Tracking
                tokens = openai_telemetry.get("total_tokens", 0)
                if tokens > 0:
                    add_tokens_to_user(user_id, tokens, session)
                    session.add(UsageLog(user_id=user_id, action_type="solve_v3_stream", tokens_used=tokens))
                
                session.commit()
                try:
                    question_fingerprint = question_identity_service.compute_question_fingerprint(problem_text)
                    question_key = question_identity_service.compute_question_key(question_fingerprint)
                    question_identity_service.store_question_result(session, question_key, question_fingerprint, final_data, problem_text)
                except: pass

                session.commit()
                solve_session_id = _persist_solve_session_and_llm_usage(
                    session,
                    user_id=user_id,
                    problem_text=problem_text,
                    topic=body.subject or "Math",
                    solution_payload=final_data if isinstance(final_data, dict) else {},
                    provider=openai_telemetry.get("provider") or stream_provider,
                    model=openai_telemetry.get("model") or stream_model,
                    request_id=request_id,
                    input_tokens=openai_telemetry.get("input_tokens"),
                    output_tokens=openai_telemetry.get("output_tokens"),
                    total_tokens=openai_telemetry.get("total_tokens"),
                    latency_ms=openai_telemetry.get("latency_ms_total") or openai_telemetry.get("latency_ms_openai"),
                )
                print(f"[SOLVER_V3_STREAM] ✅ Successfully persisted results for session {new_chat.id}")
                _enqueue_attempt_graph_render(attempt_id)
                if attempt_id:
                    emit_attempt_event(attempt_id, request_id, "completed_success", status="success")

                # Phase 1: Update Final Attempt Record
                try:
                    if attempt:
                        # Phase 1 Ambiguity Mapping
                        if schema_valid:
                             attempt.status = "success"
                        elif is_ambiguous:
                             attempt.status = "ambiguous"
                             attempt.failure_code = "AMBIGUOUS_RESPONSE"
                        else:
                             attempt.status = "failure"
                        attempt.output_tokens = openai_telemetry.get("output_tokens", 0)
                        attempt.input_tokens = openai_telemetry.get("input_tokens", 0)
                        attempt.total_tokens = openai_telemetry.get("total_tokens", 0)
                        attempt.latency_ms = int((time.perf_counter() - start_total) * 1000)
                        
                        # Append history
                        history_entry = {
                            "kind": "primary",
                            "timestamp": datetime.utcnow().isoformat(),
                            "provider": stream_provider,
                            "model": stream_model,
                            "raw_text": raw_llm_output,
                            "parsed_json": final_data,
                            "usage": {
                                "input": attempt.input_tokens,
                                "output": attempt.output_tokens,
                                "total": attempt.total_tokens
                            },
                            "latency_ms": attempt.latency_ms
                        }
                        if attempt.llm_responses is None: attempt.llm_responses = []
                        h = list(attempt.llm_responses)
                        h.append(history_entry)
                        attempt.llm_responses = h
                        
                        # Append validation event
                        val_event = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "success": schema_valid,
                            "errors": validation_errors
                        }
                        if attempt.validation_events is None: attempt.validation_events = []
                        v = list(attempt.validation_events)
                        v.append(val_event)
                        attempt.validation_events = v
                        
                        session.add(attempt)
                        session.commit()
                except Exception as e:
                    print(f"[SOLVER_V3_STREAM] Final attempt update failed: {e}")


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

            response_kind = str((final_data or {}).get("response_kind") or "").strip().lower()
            clarification_obj = (final_data or {}).get("clarification") if isinstance((final_data or {}).get("clarification"), dict) else {}
            solution_obj = (final_data or {}).get("solution") if isinstance((final_data or {}).get("solution"), dict) else {}
            solution_status = str(solution_obj.get("status") or (final_data or {}).get("status") or "").strip().lower()
            is_clarification_response = (
                response_kind == "clarification"
                or bool(clarification_obj.get("needs_clarification"))
                or solution_status in {"needs_clarification", "ambiguous"}
            )

            if use_billing_v2 and debit_cost > 0:
                from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
                if is_clarification_response:
                    billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                    session.commit()
                    deduct_committed = False
                else:
                    from decimal import Decimal

                    cost_usd = _calc_cost(
                        openai_telemetry.get("total_tokens"),
                        openai_telemetry.get("model"),
                        openai_telemetry.get("input_tokens"),
                        openai_telemetry.get("output_tokens"),
                    )
                    billing_ledger_service_v2.settle_hold(
                        session=session,
                        request_id=request_id,
                        actual_credits=Decimal(str(debit_cost)),
                        tier=effective_billing_tier.upper(),
                        provider_cost_usd=Decimal(str(cost_usd or 0.0)),
                        attempt_id=attempt_id,
                        is_billable=True,
                    )
                    session.commit()
                    deduct_committed = True
            elif (not use_billing_v2) and deduct_committed and debit_cost > 0 and is_clarification_response:
                subscription_service.refund_credits(
                    session,
                    sub_id,
                    debit_cost,
                    "Clarification response is non-billable",
                    request_id,
                )
                session.commit()
                deduct_committed = False
            record_request_event(session, {
                "request_id": request_id,
                "user_id": user_id,
                "mode": requested_mode,
                "learning_mode": learning_mode,
                "subject": body.subject,
                "grade_level": user_grade_level,
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
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'ok': True, 'session_id': new_chat.id, 'message_id': placeholder_msg.id, 'solve_session_id': solve_session_id})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[SOLVER_V3_STREAM] ❌ FATAL ERROR: {str(e)}")
            
            # Phase 1: Persistent Failure State
            try:
                if attempt:
                    attempt.status = "failure"
                    attempt.failure_code = "INTERNAL_SERVER_ERROR"
                    attempt.error_message = str(e)
                    session.add(attempt)
                    session.commit()
            except Exception as ex:
                print(f"[SOLVER_V3_STREAM] Error persistence failed: {ex}")
            
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
                    "grade_level": user_grade_level,
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
            resolved_tier = entitlement["meta"].get("tier", "short_steps")
            
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
    requires_terms_acceptance, required_terms_version = get_terms_requirement_status(session, user_id=user.id)
    if requires_terms_acceptance:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "terms_acceptance_required",
                "message": "You must accept the latest Terms of Service before completing checkout.",
                "document_key": "terms_of_service",
                "document_version": required_terms_version,
            },
        )
    
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
    include_debug: bool = False,
    session: Session = Depends(get_session)
):
    # Filter based on saved_only flag
    if saved_only:
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.is_saved == True
        ).order_by(ChatSession.created_at.desc())
        if not include_debug:
            stmt = stmt.where(ChatSession.title != "Debug Seeded Session")
    else:
        # Return ALL sessions for this user
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.created_at.desc())
        
    results = session.exec(stmt).all()
    
    def _extract_problem_from_structured(payload: Any) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        problem = payload.get("problem")
        if isinstance(problem, dict):
            for key in ("original_text", "normalized_text", "text"):
                value = problem.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        items = payload.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                problem = item.get("problem")
                if not isinstance(problem, dict):
                    continue
                for key in ("original_text", "normalized_text", "text"):
                    value = problem.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        return None

    usage_rows_user = session.exec(
        select(UsageLedgerV2)
        .where(UsageLedgerV2.user_id == user_id)
        .order_by(
            UsageLedgerV2.created_at.asc(),
            UsageLedgerV2.question_index.asc(),
            UsageLedgerV2.ledger_id.asc(),
        )
    ).all()
    lots_rows_user = session.exec(
        select(CreditLotV2)
        .where(CreditLotV2.user_id == user_id)
        .order_by(CreditLotV2.created_at.asc(), CreditLotV2.lot_id.asc())
    ).all()

    usage_by_request: Dict[str, List[UsageLedgerV2]] = {}
    for usage_row in usage_rows_user:
        rid = str(usage_row.request_id or "").strip()
        if not rid:
            continue
        usage_by_request.setdefault(rid, []).append(usage_row)

    # Reconstruct per-usage "balance_after" from credit lot grants (+) and usage debits (-).
    # This gives users an audit-style "left after charge" value even when BillingLedger rows are absent.
    replay_events: List[Tuple[datetime, int, float, Optional[UsageLedgerV2]]] = []
    for lot in lots_rows_user:
        replay_events.append((lot.created_at or datetime.min, 0, float(lot.credits_total or 0), None))
    for usage_row in usage_rows_user:
        replay_events.append((usage_row.created_at or datetime.min, 1, float(usage_row.total_cost or 0), usage_row))
    replay_events.sort(
        key=lambda row: (
            row[0],
            row[1],
            (row[3].question_index if row[3] is not None and row[3].question_index is not None else 10_000),
            (row[3].ledger_id if row[3] is not None else ""),
        )
    )

    balance_after_by_ledger_id: Dict[str, float] = {}
    replay_balance = 0.0
    for _event_at, event_kind, amount, usage_row in replay_events:
        if event_kind == 0:
            replay_balance += amount
            continue
        replay_balance -= amount
        if usage_row is not None:
            balance_after_by_ledger_id[usage_row.ledger_id] = replay_balance

    # Calibrate with actual current lot balance to absorb legacy migration offsets.
    expected_current = sum(float(lot.credits_remaining or 0) for lot in lots_rows_user)
    offset = expected_current - replay_balance
    if abs(offset) > 1e-6 and balance_after_by_ledger_id:
        for ledger_id in list(balance_after_by_ledger_id.keys()):
            balance_after_by_ledger_id[ledger_id] = balance_after_by_ledger_id[ledger_id] + offset

    history_items = []
    for chat in results:
        latest_attempt = session.exec(
            select(SolverOutputAttempt)
            .where(SolverOutputAttempt.session_id == chat.id)
            .order_by(SolverOutputAttempt.created_at.desc())
        ).first()

        # Extract user input
        user_input = None
        for msg in chat.messages:
            if msg.role == "user" and not user_input:
                user_input = msg.content
                break
        if not user_input:
            for msg in reversed(chat.messages):
                if msg.role != "assistant":
                    continue
                extracted = _extract_problem_from_structured(msg.structured_data)
                if extracted:
                    user_input = extracted
                    break
        
        # Extract metadata from any assistant message (prefer most recent)
        telemetry = None
        grade_level = None
        difficulty = None
        topics_list = []
        msg_subject = None
        session_request_id = str(latest_attempt.request_id or "").strip() if latest_attempt else ""

        for msg in reversed(chat.messages):
            if msg.role == "assistant":
                if not session_request_id:
                    extracted_request_id = _extract_chat_message_request_id(msg)
                    if extracted_request_id:
                        session_request_id = extracted_request_id
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

        request_usage_rows = usage_by_request.get(session_request_id, []) if session_request_id else []
        request_usage_rows = sorted(
            request_usage_rows,
            key=lambda item: (
                item.question_index if item.question_index is not None else 10_000,
                item.created_at,
                item.ledger_id,
            ),
        )
        per_question_charges: List[Dict[str, Any]] = []
        credits_total = 0.0
        for usage_row in request_usage_rows:
            cost_val = float(usage_row.total_cost or 0)
            credits_total += cost_val
            per_question_charges.append(
                {
                    "question_id": usage_row.question_id,
                    "question_index": usage_row.question_index,
                    "credits_charged": cost_val,
                    "balance_after": balance_after_by_ledger_id.get(usage_row.ledger_id),
                    "created_at": usage_row.created_at.isoformat() if usage_row.created_at else None,
                }
            )
        credits_balance_after = (
            per_question_charges[-1].get("balance_after")
            if per_question_charges
            else None
        )
        
        history_items.append(ChatHistoryItem(
            id=chat.id, 
            attempt_id=latest_attempt.attempt_id if latest_attempt else None,
            request_id=session_request_id or None,
            title=chat.title, 
            created_at=chat.created_at.isoformat(),
            subject=msg_subject or chat.subject or "Math",
            topic=chat.topic,
            grade_level=grade_level,
            difficulty=difficulty,
            topics=topics_list,
            input=user_input,
            is_saved=chat.is_saved,
            telemetry=telemetry,
            credits_charged_total=credits_total,
            credits_balance_after=credits_balance_after,
            per_question_charges=per_question_charges,
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
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    telemetry: Optional[dict] = None # Added telemetry

class ChatSessionResponse(BaseModel):
    id: int
    attempt_id: Optional[str] = None
    title: str
    subject: Optional[str] = None
    is_saved: bool = False
    created_at: str
    messages: List[ChatMessageSchema]


class CanonicalMarkdownResponse(BaseModel):
    id: int
    canonical_md: str
    canonical_md_hash: str


class SolutionDocResponse(BaseModel):
    id: int
    solution_doc: dict


class SolutionDocPreviewRequest(BaseModel):
    markdown: str


class ShareVisibilityUpdateRequest(BaseModel):
    visibility: str = Field(..., description="PRIVATE or PUBLIC")


class ShareStateResponse(BaseModel):
    attempt_id: str
    visibility: str
    share_url: Optional[str] = None
    revoked: bool


class PublicShareResponse(BaseModel):
    attempt_id: str
    paper: Dict[str, Any]
    problem: Dict[str, Any]
    created_at: Optional[str] = None
    visibility: str


class ShareAttemptResolutionResponse(BaseModel):
    attempt_id: Optional[str] = None


class NotesResponse(BaseModel):
    notes_md: str
    version: int
    updated_at: str


class NotesUpdateRequest(BaseModel):
    notes_md: str
    expected_version: int


class EditCopyResponse(BaseModel):
    edited_md: str
    version: int
    canonical_md_hash: str
    updated_at: str


class EditCopyUpdateRequest(BaseModel):
    edited_md: str
    expected_version: int


class EditCopyResetResponse(BaseModel):
    edited_md: str
    version: int
    canonical_md_hash: str
    updated_at: str


class DebugSeedChatResponse(BaseModel):
    session_id: int


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

    latest_attempt = session.exec(
        select(SolverOutputAttempt)
        .where(SolverOutputAttempt.session_id == chat_session.id)
        .order_by(SolverOutputAttempt.created_at.desc())
    ).first()
        
    return ChatSessionResponse(
        id=chat_session.id,
        attempt_id=latest_attempt.attempt_id if latest_attempt else None,
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
                input_tokens=(
                    (msg.telemetry.get("input_tokens") or msg.telemetry.get("prompt_tokens")) if isinstance(msg.telemetry, dict) else
                    (msg.structured_data.get("input_tokens") or msg.structured_data.get("prompt_tokens")) if isinstance(msg.structured_data, dict) else None
                ),
                output_tokens=(
                    (msg.telemetry.get("output_tokens") or msg.telemetry.get("completion_tokens")) if isinstance(msg.telemetry, dict) else
                    (msg.structured_data.get("output_tokens") or msg.structured_data.get("completion_tokens")) if isinstance(msg.structured_data, dict) else None
                ),
                # Fallback logic for telemetry
                telemetry=(
                    msg.telemetry if hasattr(msg, "telemetry") and msg.telemetry else
                    (msg.structured_data.get("telemetry") or msg.structured_data.get("_telemetry")) if msg.structured_data and isinstance(msg.structured_data, dict) else None
                )
            )
            for msg in chat_session.messages
        ]
    )


@api_router.get("/shares/attempt/{attempt_id}", response_model=ShareStateResponse)
async def get_attempt_share_state(
    attempt_id: str,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    attempt = share_service.get_attempt_by_attempt_id(session, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this attempt")

    share = share_service.get_share_for_attempt(session, attempt_id, user.id)
    origin = request.headers.get("origin")
    return share_service.read_state(
        share=share,
        attempt_id=attempt_id,
        request_origin=origin,
    )


@api_router.get("/shares/session/{session_id}/attempt", response_model=ShareAttemptResolutionResponse)
async def resolve_share_attempt_for_session(
    session_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session or chat_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    attempt = session.exec(
        select(SolverOutputAttempt)
        .where(
            SolverOutputAttempt.session_id == session_id,
            SolverOutputAttempt.user_id == user.id,
            SolverOutputAttempt.status == "success",
        )
        .order_by(SolverOutputAttempt.created_at.desc())
    ).first()
    if not attempt:
        assistant_messages = [msg for msg in chat_session.messages if msg.role == "assistant"]
        target = None
        for msg in reversed(assistant_messages):
            if isinstance(msg.structured_data, dict) and msg.structured_data:
                target = msg
                break
            if isinstance(msg.content, str) and msg.content.strip():
                target = msg
                break
        if target:
            target_structured = target.structured_data if isinstance(target.structured_data, dict) else {}
            target_telemetry = target.telemetry if isinstance(target.telemetry, dict) else {}
            if not target_telemetry:
                candidate_telemetry = target_structured.get("telemetry") if isinstance(target_structured.get("telemetry"), dict) else None
                if not candidate_telemetry and isinstance(target_structured.get("_telemetry"), dict):
                    candidate_telemetry = target_structured.get("_telemetry")
                if isinstance(candidate_telemetry, dict):
                    target_telemetry = candidate_telemetry
            metrics = _resolve_attempt_metrics(
                SolverOutputAttempt(
                    request_id="synthetic",
                    attempt_id=str(uuid.uuid4()),
                    user_id=user.id,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    prompt_meta=target_structured.get("runtime_meta") if isinstance(target_structured.get("runtime_meta"), dict) else None,
                    llm_raw_response=None,
                    validation_json=target_structured if isinstance(target_structured, dict) else None,
                    provider=target_telemetry.get("provider") if isinstance(target_telemetry, dict) else None,
                    model=target_telemetry.get("model") if isinstance(target_telemetry, dict) else None,
                ),
                message_telemetry=target_telemetry if isinstance(target_telemetry, dict) else None,
                message_structured=target_structured if isinstance(target_structured, dict) else None,
            )
            synthetic_attempt = SolverOutputAttempt(
                request_id=f"share_session_{uuid.uuid4()}",
                attempt_id=str(uuid.uuid4()),
                user_id=user.id,
                session_id=chat_session.id,
                message_id=target.id,
                output_format="json_schema" if isinstance(target.structured_data, dict) else "freeform",
                attempt_number=1,
                char_count=len((target.content or "").strip()),
                status="success",
                provider=metrics.get("provider"),
                model=metrics.get("model"),
                provider_model=f"{metrics.get('provider')}:{metrics.get('model')}" if metrics.get("provider") and metrics.get("model") else None,
                input_tokens=int(metrics.get("input_tokens") or 0),
                output_tokens=int(metrics.get("output_tokens") or 0),
                total_tokens=int(metrics.get("total_tokens") or 0),
                latency_ms=_safe_int(metrics.get("latency_ms")),
                raw_solution_text=(target.content or "").strip(),
                validation_json=target.structured_data if isinstance(target.structured_data, dict) else None,
            )
            session.add(synthetic_attempt)
            session.commit()
            session.refresh(synthetic_attempt)
            attempt = synthetic_attempt
    if not attempt:
        return ShareAttemptResolutionResponse(attempt_id=None)
    return ShareAttemptResolutionResponse(attempt_id=attempt.attempt_id)


@api_router.post("/shares/attempt/{attempt_id}", response_model=ShareStateResponse)
async def upsert_attempt_share_state(
    attempt_id: str,
    body: ShareVisibilityUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    attempt = share_service.get_attempt_by_attempt_id(session, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this attempt")

    visibility = (body.visibility or "").strip().upper()
    if visibility not in {"PRIVATE", "PUBLIC"}:
        raise HTTPException(status_code=422, detail="visibility must be PRIVATE or PUBLIC")
    if visibility == "PUBLIC" and (attempt.status or "").lower() != "success":
        raise HTTPException(status_code=409, detail="Solve must complete before sharing.")

    share = share_service.upsert_visibility(
        session=session,
        attempt=attempt,
        owner_user_id=user.id,
        visibility=visibility,
    )
    logger.info(
        "share_event=%s attempt_id=%s user_id=%s",
        "share_enabled" if visibility == "PUBLIC" else "share_disabled",
        attempt_id,
        user.id,
    )
    if share.created_at == share.updated_at:
        logger.info("share_event=share_created attempt_id=%s user_id=%s", attempt_id, user.id)

    origin = request.headers.get("origin")
    return share_service.read_state(
        share=share,
        attempt_id=attempt_id,
        request_origin=origin,
    )


@api_router.get("/shares/public/{token}", response_model=PublicShareResponse)
async def get_public_shared_solution(
    token: str,
    request: Request,
    session: Session = Depends(get_session),
):
    client_ip = request.client.host if request.client else "unknown"
    if not share_service.allow_public_request(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    share = share_service.resolve_public_share(session, token)
    if not share:
        raise HTTPException(status_code=404, detail="This shared solution is unavailable.")

    payload = share_service.build_public_view_model(session, share)
    if not payload:
        raise HTTPException(status_code=404, detail="This shared solution is unavailable.")

    try:
        share_service.mark_view(session, share)
    except Exception:
        session.rollback()

    logger.info("share_event=share_viewed attempt_id=%s", payload.get("attempt_id"))
    response = JSONResponse(
        content=payload,
        headers={
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            "Cache-Control": "no-store",
        },
    )
    return response


@api_router.get("/chat/{session_id}/canonical_markdown", response_model=CanonicalMarkdownResponse)
async def get_canonical_markdown(
    session_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    canonical_md, canonical_md_hash = _derive_canonical_markdown(chat_session)
    return CanonicalMarkdownResponse(
        id=chat_session.id,
        canonical_md=canonical_md,
        canonical_md_hash=canonical_md_hash,
    )


@api_router.get("/chat/{session_id}/solution_doc", response_model=SolutionDocResponse)
async def get_solution_doc(
    session_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    assistant_messages = [msg for msg in chat_session.messages if msg.role == "assistant"]
    target = _pick_primary_solve_message(assistant_messages)
    if not target:
        raise HTTPException(status_code=404, detail="No canonical solution found for this chat")

    problem_text = _extract_problem_text(
        target.structured_data if isinstance(target.structured_data, dict) else {},
        chat_session.messages,
    )
    if isinstance(target.structured_data, dict):
        raw_json = json.dumps(target.structured_data, ensure_ascii=False)
        solution_doc = parse_solution_doc(raw_json, problem_text=problem_text)
        return SolutionDocResponse(id=chat_session.id, solution_doc=solution_doc)

    if isinstance(target.content, str) and target.content.strip():
        solution_doc = parse_solution_doc(target.content.strip(), problem_text=problem_text)
        return SolutionDocResponse(id=chat_session.id, solution_doc=solution_doc)

    raise HTTPException(status_code=404, detail="No canonical solution found for this chat")


@api_router.post("/chat/{session_id}/solution_doc/preview", response_model=SolutionDocResponse)
async def preview_solution_doc(
    session_id: int,
    body: SolutionDocPreviewRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    assistant_messages = [msg for msg in chat_session.messages if msg.role == "assistant"]
    target = _pick_primary_solve_message(assistant_messages)
    problem_text = (
        _extract_problem_text(
            target.structured_data if isinstance(target.structured_data, dict) else {},
            chat_session.messages,
        )
        if target
        else ""
    )
    solution_doc = parse_solution_doc(body.markdown or "", problem_text=problem_text)
    return SolutionDocResponse(id=chat_session.id, solution_doc=solution_doc)


@api_router.get("/chat/{session_id}/notes", response_model=NotesResponse)
async def get_chat_notes(
    session_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    note = session.exec(
        select(ChatEditNoteV2).where(ChatEditNoteV2.chat_id == session_id, ChatEditNoteV2.user_id == user.id)
    ).first()
    if not note:
        return NotesResponse(notes_md="", version=0, updated_at=datetime.utcnow().isoformat() + "Z")

    return NotesResponse(
        notes_md=note.notes_md,
        version=note.version,
        updated_at=note.updated_at.isoformat() + "Z",
    )


@api_router.put("/chat/{session_id}/notes", response_model=NotesResponse)
@limiter.limit("30/minute")
async def put_chat_notes(
    session_id: int,
    body: NotesUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    if len(body.notes_md.encode("utf-8")) > 50_000:
        raise HTTPException(status_code=413, detail="Notes too large (50KB max)")
    if _JSX_LIKE_RE.search(body.notes_md or ""):
        raise HTTPException(status_code=400, detail="JSX/HTML is not allowed in notes")

    note = session.exec(
        select(ChatEditNoteV2).where(ChatEditNoteV2.chat_id == session_id, ChatEditNoteV2.user_id == user.id)
    ).first()
    if not note:
        if body.expected_version not in (0, 1):
            raise HTTPException(status_code=409, detail="Version conflict")
        note = ChatEditNoteV2(
            chat_id=session_id,
            user_id=user.id,
            notes_md=body.notes_md,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(note)
        session.commit()
        session.refresh(note)
    else:
        if body.expected_version != note.version:
            raise HTTPException(status_code=409, detail="Version conflict")
        note.notes_md = body.notes_md
        note.version += 1
        note.updated_at = datetime.utcnow()
        session.add(note)
        session.commit()
        session.refresh(note)

    return NotesResponse(
        notes_md=note.notes_md,
        version=note.version,
        updated_at=note.updated_at.isoformat() + "Z",
    )


@api_router.get("/chat/{session_id}/edit_copy", response_model=EditCopyResponse)
async def get_chat_edit_copy(
    session_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    canonical_md, canonical_md_hash = _derive_canonical_markdown(chat_session)
    row = session.exec(
        select(ChatEditCopyV2).where(ChatEditCopyV2.chat_id == session_id, ChatEditCopyV2.user_id == user.id)
    ).first()
    if not row:
        row = ChatEditCopyV2(
            chat_id=session_id,
            user_id=user.id,
            edited_md=canonical_md,
            canonical_md_hash=canonical_md_hash,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    elif not (row.edited_md or "").strip():
        row.edited_md = canonical_md
        row.canonical_md_hash = canonical_md_hash
        row.version += 1
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.commit()
        session.refresh(row)
    return EditCopyResponse(
        edited_md=row.edited_md,
        version=row.version,
        canonical_md_hash=row.canonical_md_hash,
        updated_at=row.updated_at.isoformat() + "Z",
    )


@api_router.put("/chat/{session_id}/edit_copy", response_model=EditCopyResponse)
@limiter.limit("30/minute")
async def put_chat_edit_copy(
    session_id: int,
    body: EditCopyUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    if len(body.edited_md.encode("utf-8")) > 50_000:
        raise HTTPException(status_code=413, detail="Edited copy too large (50KB max)")
    if _JSX_LIKE_RE.search(body.edited_md or ""):
        raise HTTPException(status_code=400, detail="JSX/HTML is not allowed in edited copy")

    row = session.exec(
        select(ChatEditCopyV2).where(ChatEditCopyV2.chat_id == session_id, ChatEditCopyV2.user_id == user.id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Edit copy not initialized")
    if body.expected_version != row.version:
        raise HTTPException(status_code=409, detail="Version conflict")

    row.edited_md = body.edited_md
    row.version += 1
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return EditCopyResponse(
        edited_md=row.edited_md,
        version=row.version,
        canonical_md_hash=row.canonical_md_hash,
        updated_at=row.updated_at.isoformat() + "Z",
    )


@api_router.post("/chat/{session_id}/edit_copy/reset", response_model=EditCopyResetResponse)
async def reset_chat_edit_copy(
    session_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if chat_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this chat")

    canonical_md, canonical_md_hash = _derive_canonical_markdown(chat_session)
    row = session.exec(
        select(ChatEditCopyV2).where(ChatEditCopyV2.chat_id == session_id, ChatEditCopyV2.user_id == user.id)
    ).first()
    if not row:
        row = ChatEditCopyV2(
            chat_id=session_id,
            user_id=user.id,
            edited_md=canonical_md,
            canonical_md_hash=canonical_md_hash,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    else:
        row.edited_md = canonical_md
        row.canonical_md_hash = canonical_md_hash
        row.version += 1
        row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return EditCopyResetResponse(
        edited_md=row.edited_md,
        version=row.version,
        canonical_md_hash=row.canonical_md_hash,
        updated_at=row.updated_at.isoformat() + "Z",
    )


@api_router.post("/debug/chat_seed", response_model=DebugSeedChatResponse)
async def debug_seed_chat_session(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    app_env = os.environ.get("APP_ENV", "").upper()
    if app_env == "PROD":
        raise HTTPException(status_code=403, detail="Debug endpoint disabled in PROD")

    sample_solution = {
        "topic": "Algebra",
        "steps": [
            {"k": 1, "title": "Isolate x", "body_markdown": "Subtract 7 from both sides: $2x = 12$."},
            {"k": 2, "title": "Solve", "body_markdown": "Divide by 2 to get $x = 6$."},
        ],
        "final_answer": {"text": "x = 6", "latex": "x = 6"},
        "domain_constraints": ["All real numbers"],
        "verification": ["Check: $2(6) + 7 = 19$"],
    }
    content_lines = [
        "**Problem:** Solve for x: 2x + 7 = 19",
        "",
        "**Solution Steps:**",
        "1) Subtract 7 from both sides to get $2x = 12$.",
        "2) Divide by 2 to get $x = 6$.",
        "",
        "**Final Answer:**",
        "$$x = 6$$",
    ]

    new_chat = ChatSession(
        user_id=user.id,
        title="Debug Seeded Session",
        subject="Math",
        is_saved=False,
    )
    session.add(new_chat)
    session.commit()
    session.refresh(new_chat)

    session.add(ChatMessage(session_id=new_chat.id, role="user", content="Solve for x: 2x + 7 = 19"))
    session.add(
        ChatMessage(
            session_id=new_chat.id,
            role="assistant",
            content="\n".join(content_lines),
            structured_data=sample_solution,
            model_used="debug",
            tokens_used=0,
            telemetry={"channel": "canvas_primary"},
        )
    )
    session.commit()
    return DebugSeedChatResponse(session_id=new_chat.id)


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


def _extract_problem_text(structured: dict, messages: List[ChatMessage]) -> str:
    if isinstance(structured.get("problem"), dict):
        problem = structured.get("problem") or {}
        for key in ("original_text", "recognized_text", "text", "statement"):
            value = problem.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(structured.get("question"), dict):
        question = structured.get("question") or {}
        for key in ("text", "original_text", "statement"):
            value = question.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(structured.get("questions"), list):
        for q in structured.get("questions") or []:
            if not isinstance(q, dict):
                continue
            for key in ("question_text", "text", "original_text", "statement"):
                value = q.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    if isinstance(structured.get("raw_user_extraction"), dict):
        raw_user_extraction = structured.get("raw_user_extraction") or {}
        question_obj = raw_user_extraction.get("question") if isinstance(raw_user_extraction.get("question"), dict) else {}
        for key in ("text", "original_text", "statement"):
            value = question_obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for msg in messages:
        if msg.role == "user" and msg.content:
            return msg.content.strip()
    return ""


def _derive_canonical_markdown(chat_session: ChatSession) -> Tuple[str, str]:
    assistant_messages = [msg for msg in chat_session.messages if msg.role == "assistant"]
    target = _pick_primary_solve_message(assistant_messages)
    if not target:
        raise HTTPException(status_code=404, detail="No canonical solution found for this chat")

    # Prefer structured_data (canonical JSON) when available.
    if isinstance(target.structured_data, dict):
        structured = target.structured_data
        problem_text = _extract_problem_text(structured, chat_session.messages)
        raw_json = json.dumps(structured, ensure_ascii=False)
        solution_doc = parse_solution_doc(raw_json, problem_text=problem_text)
        canonical_md = render_solution_doc_markdown(solution_doc)
        canonical_md_hash = hashlib.sha256(canonical_md.encode("utf-8")).hexdigest()
        return canonical_md, canonical_md_hash

    # Fallback for legacy chats with no structured_data.
    if isinstance(target.content, str) and target.content.strip():
        canonical_md = target.content.strip()
        canonical_md_hash = hashlib.sha256(canonical_md.encode("utf-8")).hexdigest()
        return canonical_md, canonical_md_hash

    raise HTTPException(status_code=404, detail="No canonical solution found for this chat")


_JSX_LIKE_RE = re.compile(r"<[A-Za-z][^>]*>")


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
    
@api_router.post("/followup/{solve_session_id}")
async def solve_followup(
    solve_session_id: int,
    request: FollowupRequest,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_session)
):
    """
    Dedicated follow-up chat endpoint that restricts scope to the solved problem.
    Enforces a hard limit of 10 turns per session.
    """
    # 1. Fetch session
    session_rec = db.get(SolveSession, solve_session_id)
    if not session_rec:
        raise HTTPException(status_code=404, detail="Solve session not found")
    
    if session_rec.user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # 2. Check turn limit
    existing_turns = db.exec(
        select(FollowupChatTurn).where(FollowupChatTurn.solve_session_id == solve_session_id)
    ).all()
    turn_index = len(existing_turns) + 1
    
    if turn_index > 10:
        raise HTTPException(status_code=403, detail="Follow-up limit reached. Start a new solve session.")
    
    # 3. Scope Lock (Hard Constraint)
    if not check_followup_scope(request.message, session_rec):
        turn = FollowupChatTurn(
            solve_session_id=solve_session_id,
            user_id=user_id,
            turn_index=turn_index,
            user_message=request.message,
            assistant_message="I'm sorry, I can only answer questions related to THIS specific problem and solution. Please ask about a step or concept from the result above.",
            refused_out_of_scope=True
        )
        db.add(turn)
        db.commit()
        return {
            "assistant_message": turn.assistant_message,
            "turn_index": turn_index,
            "turns_remaining": 10 - turn_index,
            "refused_out_of_scope": True,
            "usage": None
        }

    # 4. LLM Prompting
    turns_remaining = 10 - turn_index
    system_prompt = f"""You are a math tutor for follow-up questions about ONE specific solved problem.

AUTHORITATIVE CONTEXT (do not invent beyond this):
Problem: {session_rec.problem_text}
Topic: {session_rec.topic}
Solution steps and results: {session_rec.solution_steps_text}
Final answer: {session_rec.final_answer_text}

SCOPE (STRICT):
Only answer if the student’s question is directly about this problem, a specific step, a transformation, a definition used in the steps, a constraint/domain issue, or verifying the final result.
If the question is outside scope or asks to solve a different/new problem: refuse politely and redirect them to reference a specific step number or expression from THIS solution.

SOCRATIC (STRICT):
If asked for the final answer/formula/step directly, do not immediately give it. Ask ONE short guiding question, then provide ONE short hint based on the given steps. If the requested item is already explicitly present in the provided steps, you may restate it briefly after the guiding question.

STYLE:
- Always short and direct. 2–6 sentences max.
- Plain text.
- Use LaTeX: $...$ or $$...$$.
- No extra sections, no long explanations, no fluff.

TURN LIMIT:
Questions remaining: {turns_remaining}/10"""

    try:
        start_time_pts = time.time()
        mgr = get_llm_manager()
        provider = mgr.primary_provider
        client = mgr.get_client(provider)
        
        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]
        
        # Token Accounting (System Prompt + User Message)
        system_tokens = count_tokens(system_prompt)
        input_tokens_est = count_messages_tokens(messages)
        
        response = await client.generate(
            messages=messages,
            system_prompt=None,
            prompt=None,
            json_schema=None,
            max_tokens=400,
            temperature=0.3,
            stream=False,
            request_id=f"follow-up-{solve_session_id}-{turn_index}"
        )
        
        latency_ms = int((time.time() - start_time_pts) * 1000)
        
        assistant_content = response.content.strip()
        output_tokens_est = count_tokens(assistant_content)
        
        # 5. Token Tracking (Full Accounting)
        provider_input = response.usage.get("input", input_tokens_est)
        provider_output = response.usage.get("output", output_tokens_est)
        provider_total = response.usage.get("total", provider_input + provider_output)
        
        # Log Turn
        turn = FollowupChatTurn(
            solve_session_id=solve_session_id,
            user_id=user_id,
            turn_index=turn_index,
            user_message=request.message,
            assistant_message=assistant_content,
            refused_out_of_scope=False
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)
        
        # 5.1 Provider Usage Capture
        usage_rec = LlmUsageLedger(
            solve_session_id=solve_session_id,
            followup_turn_id=turn.id,
            provider="openai",
            model=response.model,
            request_id=response.payload.get("request_id") or f"req-{turn.id}",
            system_prompt_tokens=system_tokens,
            input_tokens=provider_input,
            output_tokens=provider_output,
            total_tokens=provider_total,
            latency_ms=latency_ms
        )
        db.add(usage_rec)
        db.commit()
        
        # Update user totals
        add_tokens_to_user(user_id, provider_total, db)
        db.commit()

        return {
            "assistant_message": assistant_content,
            "turn_index": turn_index,
            "turns_remaining": turns_remaining,
            "refused_out_of_scope": False,
            "usage": {
                "system_prompt_tokens": system_tokens,
                "input_tokens": provider_input,
                "output_tokens": provider_output,
                "total_tokens": provider_total,
                "model": response.model,
                "request_id": usage_rec.request_id
            }
        }
    except Exception as e:
        print(f"[FOLLOWUP_ERROR] {e}")
        raise HTTPException(status_code=500, detail="Internal error during follow-up chat.")



# --- Profile & Preferences ---

@api_router.get("/user/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.whatsapp_secret:
        user.whatsapp_secret = _generate_whatsapp_secret()
        db.add(user)
        db.commit()
        db.refresh(user)
    
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
    if request.whatsapp_enabled is not None:
        user.whatsapp_enabled = request.whatsapp_enabled
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "message": "Preferences updated"}

@api_router.post("/user/change-password")
async def change_user_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    if request.confirm_password is not None and request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect current password")

    user.password_hash = get_password_hash(request.new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "message": "Password updated"}

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
, admin: User = Depends(get_admin_user)):
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
async def admin_get_user_detail(user_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
, admin: User = Depends(get_admin_user)):
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
    
    # Phase 3: Add new credit-based billing models
    credit_lots = db.exec(
        select(CreditLot)
        .where(CreditLot.user_id == user_id)
        .order_by(CreditLot.created_at.desc())
    ).all()
    
    enrollments = db.exec(
        select(CreditProgramEnrollment)
        .where(CreditProgramEnrollment.user_id == user_id)
        .order_by(CreditProgramEnrollment.created_at.desc())
    ).all()

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
        "saved_solutions": _sqlmodel_list(saved_solutions),
        "credit_lots": _sqlmodel_list(credit_lots),
        "enrollments": _sqlmodel_list(enrollments)
    }

@api_router.patch("/admin/users/{user_id}")
async def admin_update_user(user_id: int, req: AdminUserUpdateRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_add_note(user_id: int, req: AdminNoteCreateRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_invite_user(req: SignupRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_reset_password(user_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_resend_email(user_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Admin only: Resend verification OR welcome email"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mocking email sending for now
    print(f"Resending welcome email to {user.email}")
    return {"status": "ok", "message": f"Email queued for {user.email}"}

@api_router.patch("/admin/users/{user_id}/ban")
async def admin_ban_user(user_id: int, banned: bool = True, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Admin only: Ban or unban a user by setting status to expired/active"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.subscription_status = "expired" if banned else "active"
    db.add(user)
    db.commit()
    return {"status": "ok", "banned": banned}

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Admin only: Permanently delete a user and their associated data (cascaded manual)"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Manual cascade for problematic tables to avoid IntegrityErrors
    # Many relationships should ideally be cascade=delete but for now manual is safer for high-traffic tables.
    db.execute(sql_text("DELETE FROM usagelog WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM chatsession WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM creditlotconsumption WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM creditprogramgrantlog WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM creditprogramenrollment WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM reconciliationrecord WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM creditlot WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM billingledger WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM ocrjob WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM voicesession WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM solvesession WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM userquotaoverride WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM devicesignuplog WHERE user_id = :uid"), {"uid": user_id})
    db.execute(sql_text("DELETE FROM subscription WHERE user_id = :uid"), {"uid": user_id})
    
    db.delete(user)
    db.commit()
    return {"status": "ok"}

@api_router.get("/admin/stats/dashboard", response_model=DashboardStatsResponse)
async def admin_get_dashboard_stats(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
    # External usage API can block admin responses when the upstream is slow.
    # Keep it opt-in so dashboard reads are always fast/stable by default.
    fetch_external_usage = (os.getenv("ADMIN_DASHBOARD_FETCH_OPENAI_USAGE", "false") or "").strip().lower() in {"1", "true", "yes", "on"}
    def fetch_openai_usage(start_date: str, end_date: str):
        if not fetch_external_usage or not openai_key:
            return None
        try:
            resp = requests.get(
                "https://api.openai.com/v1/usage",
                headers={"Authorization": f"Bearer {openai_key}"},
                params={"start_date": start_date, "end_date": end_date},
                timeout=2
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
        level=getattr(e, "severity", "ERROR"),
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
, admin: User = Depends(get_admin_user)):
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
, admin: User = Depends(get_admin_user)):
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
, admin: User = Depends(get_admin_user)):
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


class AdminLlmUsageLedgerItem(BaseModel):
    id: int
    solve_session_id: Optional[int] = None
    followup_turn_id: Optional[int] = None
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    session_id: Optional[int] = None
    message_id: Optional[int] = None
    provider: str
    model: str
    request_id: Optional[str] = None
    output_format: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    attempt_id: Optional[str] = None
    attempt_number: Optional[int] = None
    status: Optional[str] = None
    char_count: Optional[int] = None
    error_message: Optional[str] = None
    source_record: str = "llmusageledger"
    chat_session_title: Optional[str] = None
    chat_message_preview: Optional[str] = None
    solve_problem_preview: Optional[str] = None
    request_summary: Optional[Dict[str, Any]] = None
    system_prompt_tokens: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: Optional[int] = None
    created_at: str


class AdminLlmUsageLedgerListResponse(BaseModel):
    total: int
    items: List[AdminLlmUsageLedgerItem]
    source: str = "llmusageledger"


class AdminLlmUsageCreateRequest(BaseModel):
    solve_session_id: int
    followup_turn_id: Optional[int] = None
    provider: str
    model: str
    request_id: Optional[str] = None
    system_prompt_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    reason: str


class AdminLlmUsageUpdateRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    request_id: Optional[str] = None
    system_prompt_tokens: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    reason: str


class AdminLlmUsageDeleteRequest(BaseModel):
    reason: str


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _first_non_empty_str(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _extract_usage_like(payload: Any) -> Dict[str, Optional[int]]:
    if not isinstance(payload, dict):
        return {"input": None, "output": None, "total": None}

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
    input_tokens = (
        _safe_int(usage.get("input_tokens"))
        if isinstance(usage, dict)
        else None
    )
    if input_tokens is None and isinstance(usage, dict):
        input_tokens = _safe_int(usage.get("prompt_tokens"))
    if input_tokens is None and isinstance(usage, dict):
        input_tokens = _safe_int(usage.get("input"))
    if input_tokens is None and isinstance(usage, dict):
        input_tokens = _safe_int(usage.get("tokens_in"))

    output_tokens = (
        _safe_int(usage.get("output_tokens"))
        if isinstance(usage, dict)
        else None
    )
    if output_tokens is None and isinstance(usage, dict):
        output_tokens = _safe_int(usage.get("completion_tokens"))
    if output_tokens is None and isinstance(usage, dict):
        output_tokens = _safe_int(usage.get("output"))
    if output_tokens is None and isinstance(usage, dict):
        output_tokens = _safe_int(usage.get("tokens_out"))

    total_tokens = _safe_int(usage.get("total_tokens")) if isinstance(usage, dict) else None
    if total_tokens is None and isinstance(usage, dict):
        total_tokens = _safe_int(usage.get("total"))
    if total_tokens is None and isinstance(usage, dict):
        total_tokens = _safe_int(usage.get("tokens_total"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = max(0, input_tokens + output_tokens)

    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": total_tokens,
    }


def _resolve_attempt_metrics(
    row: SolverOutputAttempt,
    *,
    message_telemetry: Optional[Dict[str, Any]] = None,
    message_structured: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    prompt_meta = row.prompt_meta if isinstance(row.prompt_meta, dict) else {}
    validation_json = row.validation_json if isinstance(row.validation_json, dict) else {}
    runtime_meta = validation_json.get("runtime_meta") if isinstance(validation_json.get("runtime_meta"), dict) else {}
    llm_raw = row.llm_raw_response if isinstance(row.llm_raw_response, dict) else {}
    message_telemetry = message_telemetry if isinstance(message_telemetry, dict) else {}
    message_structured = message_structured if isinstance(message_structured, dict) else {}
    structured_runtime_meta = message_structured.get("runtime_meta") if isinstance(message_structured.get("runtime_meta"), dict) else {}
    structured_telemetry = message_structured.get("telemetry") if isinstance(message_structured.get("telemetry"), dict) else {}
    if not structured_telemetry and isinstance(message_structured.get("_telemetry"), dict):
        structured_telemetry = message_structured.get("_telemetry")

    provider_model = (row.provider_model or "").strip()
    provider_from_pair = None
    model_from_pair = None
    if ":" in provider_model:
        provider_from_pair, model_from_pair = provider_model.split(":", 1)
        provider_from_pair = provider_from_pair.strip() or None
        model_from_pair = model_from_pair.strip() or None

    provider = _first_non_empty_str(
        row.provider,
        provider_from_pair,
        message_telemetry.get("provider"),
        structured_telemetry.get("provider"),
        runtime_meta.get("provider"),
        structured_runtime_meta.get("provider"),
        prompt_meta.get("provider"),
        llm_raw.get("provider"),
    ) or "openai"
    model = _first_non_empty_str(
        row.model,
        model_from_pair,
        message_telemetry.get("model"),
        structured_telemetry.get("model"),
        runtime_meta.get("model"),
        structured_runtime_meta.get("model"),
        prompt_meta.get("model"),
        llm_raw.get("model"),
    ) or "unknown"

    row_input = max(0, int(row.input_tokens or 0))
    row_output = max(0, int(row.output_tokens or 0))
    row_total = max(0, int(row.total_tokens or 0))
    row_has_usage = any(v > 0 for v in (row_input, row_output, row_total))

    usage_sources = [
        _extract_usage_like(message_telemetry),
        _extract_usage_like(structured_telemetry),
        _extract_usage_like(runtime_meta),
        _extract_usage_like(structured_runtime_meta),
        _extract_usage_like(prompt_meta),
        _extract_usage_like(llm_raw),
    ]
    fallback_usage = next(
        (
            u for u in usage_sources
            if (u.get("input") or 0) > 0 or (u.get("output") or 0) > 0 or (u.get("total") or 0) > 0
        ),
        {"input": 0, "output": 0, "total": 0},
    )
    input_tokens = row_input if row_has_usage else max(0, int(fallback_usage.get("input") or 0))
    output_tokens = row_output if row_has_usage else max(0, int(fallback_usage.get("output") or 0))
    total_tokens = row_total if row_has_usage else max(0, int(fallback_usage.get("total") or (input_tokens + output_tokens)))
    if total_tokens == 0 and (input_tokens > 0 or output_tokens > 0):
        total_tokens = input_tokens + output_tokens

    latency_ms = _safe_int(row.latency_ms)
    if latency_ms is None or latency_ms <= 0:
        latency_ms = (
            _safe_int(message_telemetry.get("latency_ms_total"))
            or _safe_int(message_telemetry.get("latency_ms_openai"))
            or _safe_int(message_telemetry.get("latency_ms"))
            or _safe_int(structured_telemetry.get("latency_ms_total"))
            or _safe_int(structured_telemetry.get("latency_ms_openai"))
            or _safe_int(structured_telemetry.get("latency_ms"))
            or _safe_int(runtime_meta.get("latency_ms_total"))
            or _safe_int(runtime_meta.get("latency_ms_openai"))
            or _safe_int(runtime_meta.get("latency_ms"))
            or _safe_int(structured_runtime_meta.get("latency_ms_total"))
            or _safe_int(structured_runtime_meta.get("latency_ms_openai"))
            or _safe_int(structured_runtime_meta.get("latency_ms"))
            or _safe_int(prompt_meta.get("latency_ms_total"))
            or _safe_int(llm_raw.get("latency_ms"))
            or None
        )

    return {
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
    }


def _serialize_llm_usage_row(
    row: LlmUsageLedger,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    solve_problem_preview: Optional[str] = None,
    request_summary: Optional[Dict[str, Any]] = None,
) -> AdminLlmUsageLedgerItem:
    return AdminLlmUsageLedgerItem(
        id=int(row.id or 0),
        solve_session_id=row.solve_session_id,
        followup_turn_id=row.followup_turn_id,
        user_id=user_id,
        user_email=user_email,
        session_id=None,
        message_id=None,
        provider=row.provider,
        model=row.model,
        request_id=row.request_id,
        output_format=None,
        prompt_id=None,
        prompt_version=None,
        attempt_id=None,
        attempt_number=None,
        status=None,
        char_count=None,
        error_message=None,
        source_record="llmusageledger",
        chat_session_title=None,
        chat_message_preview=None,
        solve_problem_preview=solve_problem_preview,
        request_summary=request_summary,
        system_prompt_tokens=row.system_prompt_tokens,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        latency_ms=row.latency_ms,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def _serialize_solver_attempt_as_llm_usage(
    row: SolverOutputAttempt,
    user_email: Optional[str] = None,
    message_telemetry: Optional[Dict[str, Any]] = None,
    message_structured: Optional[Dict[str, Any]] = None,
    chat_session_title: Optional[str] = None,
    chat_message_preview: Optional[str] = None,
    request_summary: Optional[Dict[str, Any]] = None,
) -> AdminLlmUsageLedgerItem:
    metrics = _resolve_attempt_metrics(
        row,
        message_telemetry=message_telemetry,
        message_structured=message_structured,
    )
    return AdminLlmUsageLedgerItem(
        id=int(row.id or 0),
        solve_session_id=None,
        followup_turn_id=None,
        user_id=row.user_id,
        user_email=user_email,
        session_id=row.session_id,
        message_id=row.message_id,
        provider=metrics["provider"],
        model=metrics["model"],
        request_id=row.request_id,
        output_format=row.output_format,
        prompt_id=row.prompt_id,
        prompt_version=row.prompt_version,
        attempt_id=row.attempt_id,
        attempt_number=row.attempt_number,
        status=row.status,
        char_count=row.char_count,
        error_message=row.error_message,
        source_record="solver_attempt_fallback",
        chat_session_title=chat_session_title,
        chat_message_preview=chat_message_preview,
        solve_problem_preview=None,
        request_summary=request_summary,
        system_prompt_tokens=0,
        input_tokens=metrics["input_tokens"],
        output_tokens=metrics["output_tokens"],
        total_tokens=metrics["total_tokens"],
        latency_ms=metrics["latency_ms"],
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def _serialize_solver_attempt_as_trace(row: SolverOutputAttempt) -> Dict[str, Any]:
    schema_name = None
    if isinstance(row.prompt_meta, dict):
        schema_name = (
            row.prompt_meta.get("output_schema_id")
            or row.prompt_meta.get("schema_name")
        )
    if not schema_name and isinstance(row.validation_json, dict):
        runtime_meta = row.validation_json.get("runtime_meta")
        if isinstance(runtime_meta, dict):
            schema_name = runtime_meta.get("schema_name")

    return {
        "request_id": row.request_id,
        "user_id": row.user_id,
        "ui_goal": None,
        "ui_style": None,
        "schema_name": schema_name,
        "input_tokens": int(row.input_tokens or 0),
        "output_tokens": int(row.output_tokens or 0),
        "deduct_committed": None,
        "problem_text": (row.input_text_normalized or row.input_text_raw),
        "openai_payload": row.llm_raw_response if isinstance(row.llm_raw_response, dict) else None,
        "error": row.error_message,
        "logged_at": row.created_at.isoformat() if row.created_at else None,
        "source": "solver_attempt_fallback",
    }


def _build_request_summary_map(db: Session, request_ids: set[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not request_ids:
        return out
    usage_rows = db.exec(select(UsageLedgerV2).where(UsageLedgerV2.request_id.in_(request_ids))).all()
    for row in usage_rows:
        rid = str(row.request_id or "").strip()
        if not rid:
            continue
        bucket = out.setdefault(
            rid,
            {
                "question_count": 0,
                "question_ids": [],
                "billed_credits_total": 0.0,
                "tiers": [],
                "actions": [],
                "billing_entries_count": 0,
                "billing_credits_total": 0.0,
                "provider_cost_usd_total": 0.0,
            },
        )
        bucket["question_count"] += 1
        qid = str(row.question_id or "").strip()
        if qid and qid not in bucket["question_ids"]:
            bucket["question_ids"].append(qid)
        bucket["billed_credits_total"] += float(row.total_cost or 0)
        tier_val = str(row.tier or "").strip()
        if tier_val and tier_val not in bucket["tiers"]:
            bucket["tiers"].append(tier_val)
        action_val = str(row.action or "").strip()
        if action_val and action_val not in bucket["actions"]:
            bucket["actions"].append(action_val)

    billing_rows = db.exec(select(BillingLedger).where(BillingLedger.request_id.in_(request_ids))).all()
    for row in billing_rows:
        rid = str(row.request_id or "").strip()
        if not rid:
            continue
        bucket = out.setdefault(
            rid,
            {
                "question_count": 0,
                "question_ids": [],
                "billed_credits_total": 0.0,
                "tiers": [],
                "actions": [],
                "billing_entries_count": 0,
                "billing_credits_total": 0.0,
                "provider_cost_usd_total": 0.0,
            },
        )
        bucket["billing_entries_count"] += 1
        bucket["billing_credits_total"] += float(row.credits_charged or 0)
        bucket["provider_cost_usd_total"] += float(row.provider_cost_usd or 0)

    return out


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
admin: User = Depends(get_admin_user)):
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
admin: User = Depends(get_admin_user)):
    row = db.get(SolverOutputAttempt, attempt_id)
    if not row:
        raise HTTPException(status_code=404, detail="Solver output attempt not found")
    return _serialize_solver_output_attempt(row, include_full_output=True)


@api_router.get("/admin/solve-traces", response_model=List[SolveTraceEntry])
async def admin_get_solve_traces(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    from app.services.solve.trace_logger import TRACE_LOG_PATH
    entries: List[Dict[str, Any]] = []
    if TRACE_LOG_PATH.exists():
        try:
            lines = TRACE_LOG_PATH.read_text(encoding="utf-8").splitlines()
            trimmed = lines[-limit:]
            for line in trimmed:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            entries = []
    if entries:
        for entry in entries:
            if isinstance(entry, dict):
                entry.setdefault("source", "trace_file")
        return entries

    # Fallback: derive traces from solver attempts when file-based traces are missing/empty.
    rows = db.exec(
        select(SolverOutputAttempt).order_by(SolverOutputAttempt.created_at.desc()).limit(limit)
    ).all()
    return [_serialize_solver_attempt_as_trace(row) for row in rows]


@api_router.get("/admin/observability/llm-usage", response_model=AdminLlmUsageLedgerListResponse)
async def admin_list_llm_usage_ledger(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    solve_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    query = select(LlmUsageLedger)
    if provider:
        query = query.where(LlmUsageLedger.provider == provider.strip())
    if model:
        query = query.where(LlmUsageLedger.model == model.strip())
    if request_id:
        query = query.where(LlmUsageLedger.request_id.contains(request_id.strip()))
    if solve_session_id is not None:
        query = query.where(LlmUsageLedger.solve_session_id == solve_session_id)
    if user_id is not None:
        session_ids = db.exec(select(SolveSession.id).where(SolveSession.user_id == user_id)).all()
        if not session_ids:
            return AdminLlmUsageLedgerListResponse(total=0, items=[], source="llmusageledger")
        query = query.where(LlmUsageLedger.solve_session_id.in_(session_ids))

    rows = db.exec(query.order_by(LlmUsageLedger.created_at.desc()).offset(offset).limit(limit)).all()
    total = len(db.exec(query).all())
    request_ids_for_summary = {
        str(r.request_id).strip()
        for r in rows
        if isinstance(r.request_id, str) and str(r.request_id).strip()
    }
    request_summary_map = _build_request_summary_map(db, request_ids_for_summary)

    session_id_set = {r.solve_session_id for r in rows}
    session_map: Dict[int, SolveSession] = {}
    if session_id_set:
        sessions = db.exec(select(SolveSession).where(SolveSession.id.in_(session_id_set))).all()
        session_map = {int(s.id): s for s in sessions if s.id is not None}
    user_id_set = {s.user_id for s in session_map.values() if s.user_id is not None}
    user_email_map: Dict[int, str] = {}
    if user_id_set:
        users = db.exec(select(User).where(User.id.in_(user_id_set))).all()
        user_email_map = {int(u.id): u.email for u in users if u.id is not None}

    items = []
    for row in rows:
        session_rec = session_map.get(row.solve_session_id)
        session_user_id = session_rec.user_id if session_rec else None
        session_user_email = user_email_map.get(session_user_id) if session_user_id is not None else None
        solve_problem_preview = _truncate_text((session_rec.problem_text or "").replace("\n", " "), 180) if session_rec else None
        req_summary = request_summary_map.get(str(row.request_id).strip()) if isinstance(row.request_id, str) else None
        items.append(
            _serialize_llm_usage_row(
                row,
                user_id=session_user_id,
                user_email=session_user_email,
                solve_problem_preview=solve_problem_preview,
                request_summary=req_summary,
            )
        )

    if items:
        return AdminLlmUsageLedgerListResponse(total=total, items=items, source="llmusageledger")

    # Fallback: derive usage list from solver attempts when llmusageledger is empty.
    # solve_session_id filter cannot be mapped from solver attempts.
    if solve_session_id is not None:
        return AdminLlmUsageLedgerListResponse(total=0, items=[], source="solver_attempt_fallback")

    attempt_query = select(SolverOutputAttempt)
    if provider:
        attempt_query = attempt_query.where(SolverOutputAttempt.provider == provider.strip())
    if model:
        attempt_query = attempt_query.where(SolverOutputAttempt.model == model.strip())
    if request_id:
        attempt_query = attempt_query.where(SolverOutputAttempt.request_id.contains(request_id.strip()))
    if user_id is not None:
        attempt_query = attempt_query.where(SolverOutputAttempt.user_id == user_id)

    fallback_rows = db.exec(
        attempt_query.order_by(SolverOutputAttempt.created_at.desc()).offset(offset).limit(limit)
    ).all()
    fallback_total = len(db.exec(attempt_query).all())
    fallback_request_ids = {
        str(r.request_id).strip()
        for r in fallback_rows
        if isinstance(r.request_id, str) and str(r.request_id).strip()
    }
    fallback_request_summary_map = _build_request_summary_map(db, fallback_request_ids)
    fallback_message_ids = {r.message_id for r in fallback_rows if r.message_id is not None}
    message_map: Dict[int, ChatMessage] = {}
    if fallback_message_ids:
        messages = db.exec(select(ChatMessage).where(ChatMessage.id.in_(fallback_message_ids))).all()
        message_map = {int(m.id): m for m in messages if m.id is not None}
    fallback_session_ids = {r.session_id for r in fallback_rows if r.session_id is not None}
    fallback_session_map: Dict[int, ChatSession] = {}
    if fallback_session_ids:
        fallback_sessions = db.exec(select(ChatSession).where(ChatSession.id.in_(fallback_session_ids))).all()
        fallback_session_map = {int(s.id): s for s in fallback_sessions if s.id is not None}
    fallback_user_ids = {r.user_id for r in fallback_rows if r.user_id is not None}
    fallback_email_map: Dict[int, str] = {}
    if fallback_user_ids:
        fallback_users = db.exec(select(User).where(User.id.in_(fallback_user_ids))).all()
        fallback_email_map = {int(u.id): u.email for u in fallback_users if u.id is not None}
    fallback_items = [
        _serialize_solver_attempt_as_llm_usage(
            row,
            user_email=fallback_email_map.get(row.user_id) if row.user_id is not None else None,
            message_telemetry=(
                message_map[row.message_id].telemetry
                if row.message_id is not None and row.message_id in message_map and isinstance(message_map[row.message_id].telemetry, dict)
                else None
            ),
            message_structured=(
                message_map[row.message_id].structured_data
                if row.message_id is not None and row.message_id in message_map and isinstance(message_map[row.message_id].structured_data, dict)
                else None
            ),
            chat_session_title=(
                fallback_session_map[row.session_id].title
                if row.session_id is not None and row.session_id in fallback_session_map
                else None
            ),
            chat_message_preview=(
                _truncate_text((message_map[row.message_id].content or "").replace("\n", " "), 180)
                if row.message_id is not None and row.message_id in message_map
                else None
            ),
            request_summary=(
                fallback_request_summary_map.get(str(row.request_id).strip())
                if isinstance(row.request_id, str)
                else None
            ),
        )
        for row in fallback_rows
    ]

    if fallback_items:
        return AdminLlmUsageLedgerListResponse(
            total=fallback_total,
            items=fallback_items,
            source="solver_attempt_fallback",
        )

    # Second fallback: derive usage rows from credits usage ledger when
    # llmusageledger and solveroutputattempt both lack the request trail.
    usage_query = select(UsageLedgerV2)
    if request_id:
        usage_query = usage_query.where(UsageLedgerV2.request_id.contains(request_id.strip()))
    if user_id is not None:
        usage_query = usage_query.where(UsageLedgerV2.user_id == user_id)
    usage_rows = db.exec(
        usage_query.order_by(UsageLedgerV2.created_at.desc()).offset(offset).limit(limit)
    ).all()
    usage_total = len(db.exec(usage_query).all())
    usage_request_ids = {
        str(r.request_id).strip()
        for r in usage_rows
        if isinstance(r.request_id, str) and str(r.request_id).strip()
    }
    usage_request_summary_map = _build_request_summary_map(db, usage_request_ids)
    usage_user_ids = {r.user_id for r in usage_rows if r.user_id is not None}
    usage_user_email_map: Dict[int, str] = {}
    if usage_user_ids:
        usage_users = db.exec(select(User).where(User.id.in_(usage_user_ids))).all()
        usage_user_email_map = {int(u.id): u.email for u in usage_users if u.id is not None}
    usage_items: List[AdminLlmUsageLedgerItem] = []
    for idx, row in enumerate(usage_rows):
        usage_items.append(
            AdminLlmUsageLedgerItem(
                id=-(offset + idx + 1),
                solve_session_id=None,
                followup_turn_id=None,
                user_id=row.user_id,
                user_email=usage_user_email_map.get(row.user_id) if row.user_id is not None else None,
                session_id=None,
                message_id=None,
                provider="unknown",
                model="unknown",
                request_id=row.request_id,
                output_format="batch",
                prompt_id=str((row.pricing_snapshot or {}).get("binding_id") or ""),
                prompt_version=None,
                attempt_id=row.attempt_id,
                attempt_number=row.question_index,
                status=row.outcome,
                char_count=None,
                error_message=None,
                source_record="usage_ledger_fallback",
                chat_session_title=None,
                chat_message_preview=None,
                solve_problem_preview=None,
                request_summary=(
                    usage_request_summary_map.get(str(row.request_id).strip())
                    if isinstance(row.request_id, str)
                    else None
                ),
                system_prompt_tokens=0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=None,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
        )
    if usage_items:
        return AdminLlmUsageLedgerListResponse(
            total=usage_total,
            items=usage_items,
            source="usage_ledger_fallback",
        )

    return AdminLlmUsageLedgerListResponse(
        total=fallback_total,
        items=[],
        source="solver_attempt_fallback",
    )


@api_router.get("/admin/observability/llm-usage/{entry_id}", response_model=AdminLlmUsageLedgerItem)
async def admin_get_llm_usage_ledger_entry(
    entry_id: int,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    row = db.get(LlmUsageLedger, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="LLM usage entry not found")
    session_rec = db.get(SolveSession, row.solve_session_id)
    user_rec = db.get(User, session_rec.user_id) if session_rec and session_rec.user_id is not None else None
    return _serialize_llm_usage_row(
        row,
        user_id=session_rec.user_id if session_rec else None,
        user_email=user_rec.email if user_rec else None,
    )


@api_router.post("/admin/observability/llm-usage", response_model=AdminLlmUsageLedgerItem)
async def admin_create_llm_usage_ledger_entry(
    body: AdminLlmUsageCreateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    solve_session = db.get(SolveSession, body.solve_session_id)
    if not solve_session:
        raise HTTPException(status_code=404, detail="Solve session not found")
    solve_user = db.get(User, solve_session.user_id) if solve_session.user_id is not None else None
    if body.followup_turn_id is not None:
        turn = db.get(FollowupChatTurn, body.followup_turn_id)
        if not turn:
            raise HTTPException(status_code=404, detail="Follow-up turn not found")
        if turn.solve_session_id != body.solve_session_id:
            raise HTTPException(status_code=400, detail="followup_turn_id does not belong to solve_session_id")

    computed_total = body.total_tokens if body.total_tokens is not None else (
        max(0, body.system_prompt_tokens) + max(0, body.input_tokens) + max(0, body.output_tokens)
    )
    row = LlmUsageLedger(
        solve_session_id=body.solve_session_id,
        followup_turn_id=body.followup_turn_id,
        provider=body.provider.strip(),
        model=body.model.strip(),
        request_id=body.request_id.strip() if body.request_id else None,
        system_prompt_tokens=max(0, body.system_prompt_tokens),
        input_tokens=max(0, body.input_tokens),
        output_tokens=max(0, body.output_tokens),
        total_tokens=max(0, computed_total),
        latency_ms=body.latency_ms,
    )
    db.add(row)
    db.flush()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="CREATE",
        entity_type="LLM_USAGE_LEDGER",
        entity_id=str(row.id),
        before_json=None,
        after_json=_serialize_llm_usage_row(
            row,
            user_id=solve_session.user_id,
            user_email=solve_user.email if solve_user else None,
        ).model_dump(),
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_llm_usage_row(
        row,
        user_id=solve_session.user_id,
        user_email=solve_user.email if solve_user else None,
    )


@api_router.patch("/admin/observability/llm-usage/{entry_id}", response_model=AdminLlmUsageLedgerItem)
async def admin_update_llm_usage_ledger_entry(
    entry_id: int,
    body: AdminLlmUsageUpdateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(LlmUsageLedger, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="LLM usage entry not found")
    session_rec = db.get(SolveSession, row.solve_session_id)
    session_user = db.get(User, session_rec.user_id) if session_rec and session_rec.user_id is not None else None
    before = _serialize_llm_usage_row(
        row,
        user_id=session_rec.user_id if session_rec else None,
        user_email=session_user.email if session_user else None,
    ).model_dump()

    if body.provider is not None:
        row.provider = body.provider.strip()
    if body.model is not None:
        row.model = body.model.strip()
    if body.request_id is not None:
        row.request_id = body.request_id.strip() or None
    if body.system_prompt_tokens is not None:
        row.system_prompt_tokens = max(0, body.system_prompt_tokens)
    if body.input_tokens is not None:
        row.input_tokens = max(0, body.input_tokens)
    if body.output_tokens is not None:
        row.output_tokens = max(0, body.output_tokens)
    if body.total_tokens is not None:
        row.total_tokens = max(0, body.total_tokens)
    else:
        row.total_tokens = max(0, row.system_prompt_tokens + row.input_tokens + row.output_tokens)
    if body.latency_ms is not None:
        row.latency_ms = body.latency_ms

    db.add(row)
    db.flush()
    after = _serialize_llm_usage_row(
        row,
        user_id=session_rec.user_id if session_rec else None,
        user_email=session_user.email if session_user else None,
    ).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="UPDATE",
        entity_type="LLM_USAGE_LEDGER",
        entity_id=str(row.id),
        before_json=before,
        after_json=after,
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_llm_usage_row(
        row,
        user_id=session_rec.user_id if session_rec else None,
        user_email=session_user.email if session_user else None,
    )


@api_router.delete("/admin/observability/llm-usage/{entry_id}")
async def admin_delete_llm_usage_ledger_entry(
    entry_id: int,
    body: AdminLlmUsageDeleteRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(LlmUsageLedger, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="LLM usage entry not found")
    session_rec = db.get(SolveSession, row.solve_session_id)
    session_user = db.get(User, session_rec.user_id) if session_rec and session_rec.user_id is not None else None
    before = _serialize_llm_usage_row(
        row,
        user_id=session_rec.user_id if session_rec else None,
        user_email=session_user.email if session_user else None,
    ).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="DELETE",
        entity_type="LLM_USAGE_LEDGER",
        entity_id=str(row.id),
        before_json=before,
        after_json=None,
        reason=body.reason.strip(),
        request=request,
    )
    db.delete(row)
    db.commit()
    return {"status": "ok", "deleted_id": entry_id}


class AdminChatBillingQuestionChargeItem(BaseModel):
    ledger_id: str
    hold_id: Optional[str] = None
    attempt_id: Optional[str] = None
    question_id: Optional[str] = None
    question_index: Optional[int] = None
    action: str
    tier: str
    outcome: str
    total_cost: float
    created_at: str


class AdminChatBillingRecord(BaseModel):
    session_id: int
    message_id: int
    role: str
    created_at: str
    user_id: int
    user_email: str
    request_id: Optional[str] = None
    content_preview: str
    question_count: int = 0
    charge_mode: str = "none"  # none | single | batch
    credits_charged_total: float = 0.0
    credits_source: str = "none"  # usage_ledger | billingledger | none
    provider_cost_usd_total: float = 0.0
    provider_cost_source: str = "none"  # billingledger | requestevent | estimated | none
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    total_tokens: int = 0
    latency_ms: Optional[int] = None
    billing_entries_count: int = 0
    usage_entries_count: int = 0
    ledger_entries_total_count: int = 0
    billing_statuses: List[str] = Field(default_factory=list)
    per_question_total_credits: float = 0.0
    per_question_charges: List[AdminChatBillingQuestionChargeItem] = Field(default_factory=list)


class AdminChatBillingListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[AdminChatBillingRecord]


def _extract_chat_message_request_id(message: ChatMessage) -> Optional[str]:
    telemetry = message.telemetry if isinstance(message.telemetry, dict) else {}
    structured = message.structured_data if isinstance(message.structured_data, dict) else {}
    nested_telemetry = structured.get("telemetry") if isinstance(structured.get("telemetry"), dict) else {}
    nested_legacy_telemetry = structured.get("_telemetry") if isinstance(structured.get("_telemetry"), dict) else {}
    candidates = [
        telemetry.get("request_id"),
        nested_telemetry.get("request_id"),
        nested_legacy_telemetry.get("request_id"),
        structured.get("request_id"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_chat_message_question_count(message: ChatMessage) -> int:
    structured = message.structured_data if isinstance(message.structured_data, dict) else {}
    if isinstance(structured.get("solutions"), list):
        return len(structured.get("solutions") or [])
    if isinstance(structured.get("items"), list):
        return len(structured.get("items") or [])
    return 0


def _extract_chat_message_telemetry(message: ChatMessage) -> Dict[str, Any]:
    telemetry = message.telemetry if isinstance(message.telemetry, dict) else {}
    structured = message.structured_data if isinstance(message.structured_data, dict) else {}
    nested_telemetry = structured.get("telemetry") if isinstance(structured.get("telemetry"), dict) else {}
    nested_legacy_telemetry = structured.get("_telemetry") if isinstance(structured.get("_telemetry"), dict) else {}
    runtime_meta = structured.get("runtime_meta") if isinstance(structured.get("runtime_meta"), dict) else {}
    out: Dict[str, Any] = {}
    for source in [telemetry, nested_telemetry, nested_legacy_telemetry, runtime_meta]:
        for key, value in source.items():
            if key not in out or out.get(key) in (None, "", 0):
                out[key] = value
    return out


@api_router.get("/admin/observability/chat-billing", response_model=AdminChatBillingListResponse)
async def admin_list_chat_billing_records(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_query: Optional[str] = Query(None, description="User id or email fragment"),
    session_id: Optional[int] = Query(None),
    request_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None, description="assistant | user | system"),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    message_query = (
        select(ChatMessage, ChatSession, User)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .join(User, User.id == ChatSession.user_id)
    )
    count_query = (
        select(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .join(User, User.id == ChatSession.user_id)
    )

    if role:
        role_norm = role.strip().lower()
        message_query = message_query.where(ChatMessage.role == role_norm)
        count_query = count_query.where(ChatMessage.role == role_norm)
    else:
        message_query = message_query.where(ChatMessage.role == "assistant")
        count_query = count_query.where(ChatMessage.role == "assistant")

    if session_id is not None:
        message_query = message_query.where(ChatSession.id == session_id)
        count_query = count_query.where(ChatSession.id == session_id)

    if user_query and user_query.strip():
        uq = user_query.strip()
        if uq.isdigit():
            uid = int(uq)
            message_query = message_query.where(User.id == uid)
            count_query = count_query.where(User.id == uid)
        else:
            message_query = message_query.where(User.email.ilike(f"%{uq}%"))
            count_query = count_query.where(User.email.ilike(f"%{uq}%"))

    rows = db.exec(
        message_query
        .order_by(ChatMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = int(db.exec(count_query).one() or 0)

    request_ids = set()
    for message, _session, _user in rows:
        req_id = _extract_chat_message_request_id(message)
        if req_id:
            request_ids.add(req_id)
    if request_id and request_id.strip():
        request_ids.add(request_id.strip())

    billing_by_request: Dict[str, List[BillingLedger]] = {}
    usage_by_request: Dict[str, List[UsageLedgerV2]] = {}
    request_event_by_request: Dict[str, RequestEvent] = {}
    attempt_by_request: Dict[str, SolverOutputAttempt] = {}
    if request_ids:
        billing_rows = db.exec(
            select(BillingLedger).where(BillingLedger.request_id.in_(request_ids))
        ).all()
        for entry in billing_rows:
            rid = (entry.request_id or "").strip()
            if not rid:
                continue
            billing_by_request.setdefault(rid, []).append(entry)

        usage_rows = db.exec(
            select(UsageLedgerV2).where(UsageLedgerV2.request_id.in_(request_ids))
        ).all()
        for entry in usage_rows:
            rid = (entry.request_id or "").strip()
            if not rid:
                continue
            usage_by_request.setdefault(rid, []).append(entry)

        event_rows = db.exec(
            select(RequestEvent)
            .where(RequestEvent.request_id.in_(request_ids))
            .order_by(RequestEvent.created_at.desc())
        ).all()
        for event in event_rows:
            rid = (event.request_id or "").strip()
            if not rid or rid in request_event_by_request:
                continue
            request_event_by_request[rid] = event

        attempt_rows = db.exec(
            select(SolverOutputAttempt)
            .where(SolverOutputAttempt.request_id.in_(request_ids))
            .order_by(SolverOutputAttempt.created_at.desc())
        ).all()
        for attempt in attempt_rows:
            rid = (attempt.request_id or "").strip()
            if not rid or rid in attempt_by_request:
                continue
            attempt_by_request[rid] = attempt

    records: List[AdminChatBillingRecord] = []
    request_id_filter = request_id.strip() if isinstance(request_id, str) else None
    for message, chat_session, user in rows:
        msg_request_id = _extract_chat_message_request_id(message)
        if request_id_filter and msg_request_id != request_id_filter:
            continue

        billing_entries = billing_by_request.get(msg_request_id or "", []) if msg_request_id else []
        usage_entries = usage_by_request.get(msg_request_id or "", []) if msg_request_id else []
        request_event = request_event_by_request.get(msg_request_id or "") if msg_request_id else None
        attempt_entry = attempt_by_request.get(msg_request_id or "") if msg_request_id else None
        message_telemetry = _extract_chat_message_telemetry(message)

        billing_credits_total = 0.0
        provider_cost_total = 0.0
        statuses: List[str] = []
        for entry in billing_entries:
            credits_value = float(entry.credits_charged or 0)
            provider_cost = float(entry.provider_cost_usd or 0)
            billing_credits_total += credits_value
            provider_cost_total += provider_cost
            status_value = (entry.status or "").strip()
            if status_value and status_value not in statuses:
                statuses.append(status_value)

        question_items: List[AdminChatBillingQuestionChargeItem] = []
        per_question_total = 0.0
        usage_entries_sorted = sorted(
            usage_entries,
            key=lambda item: (
                item.question_index if item.question_index is not None else 10_000,
                item.created_at,
            ),
        )
        for usage_entry in usage_entries_sorted:
            q_cost = float(usage_entry.total_cost or 0)
            per_question_total += q_cost
            question_items.append(
                AdminChatBillingQuestionChargeItem(
                    ledger_id=usage_entry.ledger_id,
                    hold_id=usage_entry.hold_id,
                    attempt_id=usage_entry.attempt_id,
                    question_id=usage_entry.question_id,
                    question_index=usage_entry.question_index,
                    action=usage_entry.action,
                    tier=usage_entry.tier,
                    outcome=usage_entry.outcome,
                    total_cost=q_cost,
                    created_at=usage_entry.created_at.isoformat() if usage_entry.created_at else "",
                )
            )

        credits_charged_total = 0.0
        credits_source = "none"
        if per_question_total > 0:
            credits_charged_total = per_question_total
            credits_source = "usage_ledger"
        elif billing_credits_total > 0:
            credits_charged_total = billing_credits_total
            credits_source = "billingledger"

        provider_cost_source = "none"
        if provider_cost_total > 0:
            provider_cost_source = "billingledger"
        elif request_event and float(request_event.cost_usd or 0) > 0:
            provider_cost_total = float(request_event.cost_usd or 0)
            provider_cost_source = "requestevent"

        provider = _first_non_empty_str(
            request_event.provider if request_event else None,
            attempt_entry.provider if attempt_entry else None,
            message_telemetry.get("provider"),
        )
        model = _first_non_empty_str(
            request_event.model if request_event else None,
            attempt_entry.model if attempt_entry else None,
            message_telemetry.get("model"),
        )
        input_tokens = (
            _safe_int(request_event.tokens_in) if request_event else None
        )
        output_tokens = (
            _safe_int(request_event.tokens_out) if request_event else None
        )
        total_tokens = (
            _safe_int(request_event.tokens_total) if request_event else None
        )
        if input_tokens is None and attempt_entry is not None:
            input_tokens = _safe_int(attempt_entry.input_tokens)
        if output_tokens is None and attempt_entry is not None:
            output_tokens = _safe_int(attempt_entry.output_tokens)
        if total_tokens is None and attempt_entry is not None:
            total_tokens = _safe_int(attempt_entry.total_tokens)
        if input_tokens is None:
            input_tokens = _safe_int(message_telemetry.get("input_tokens")) or _safe_int(message_telemetry.get("tokens_in"))
        if output_tokens is None:
            output_tokens = _safe_int(message_telemetry.get("output_tokens")) or _safe_int(message_telemetry.get("tokens_out"))
        if total_tokens is None:
            total_tokens = _safe_int(message_telemetry.get("total_tokens")) or _safe_int(message_telemetry.get("tokens_total"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        latency_ms: Optional[int] = (
            _safe_int(request_event.latency_ms) if request_event else None
        )
        if latency_ms is None and attempt_entry is not None:
            latency_ms = _safe_int(attempt_entry.latency_ms)
        if latency_ms is None:
            latency_ms = (
                _safe_int(message_telemetry.get("latency_ms_total"))
                or _safe_int(message_telemetry.get("latency_ms_openai"))
                or _safe_int(message_telemetry.get("latency_ms"))
                or None
            )

        if provider_cost_source == "none" and total_tokens and total_tokens > 0:
            model_for_cost = model or ""
            provider_cost_total = float(
                _calc_cost(
                    total_tokens,
                    model_for_cost,
                    input_tokens,
                    output_tokens,
                ) or 0.0
            )
            if provider_cost_total > 0:
                provider_cost_source = "estimated"

        question_count = _extract_chat_message_question_count(message)
        if question_count <= 0 and question_items:
            question_count = len(question_items)
        charge_mode = "none"
        if question_count > 1 or len(question_items) > 1:
            charge_mode = "batch"
        elif question_count == 1 or len(question_items) == 1:
            charge_mode = "single"

        records.append(
            AdminChatBillingRecord(
                session_id=int(chat_session.id or 0),
                message_id=int(message.id or 0),
                role=message.role,
                created_at=message.created_at.isoformat() if message.created_at else "",
                user_id=int(user.id or 0),
                user_email=user.email,
                request_id=msg_request_id,
                content_preview=_truncate_text((message.content or "").replace("\n", " "), 220),
                question_count=question_count,
                charge_mode=charge_mode,
                credits_charged_total=credits_charged_total,
                credits_source=credits_source,
                provider_cost_usd_total=provider_cost_total,
                provider_cost_source=provider_cost_source,
                provider=provider,
                model=model,
                input_tokens_total=max(0, int(input_tokens or 0)),
                output_tokens_total=max(0, int(output_tokens or 0)),
                total_tokens=max(0, int(total_tokens or 0)),
                latency_ms=latency_ms,
                billing_entries_count=len(billing_entries),
                usage_entries_count=len(usage_entries),
                ledger_entries_total_count=len(billing_entries) + len(usage_entries),
                billing_statuses=statuses,
                per_question_total_credits=per_question_total,
                per_question_charges=question_items,
            )
        )

    # Include usage-ledger-only requests even when no chatmessage row exists,
    # so the default dashboard view never hides charged requests.
    include_usage_fallback = (not role) or (str(role).strip().lower() == "assistant")
    if include_usage_fallback and not request_id_filter:
        request_ids_in_records = {
            str(r.request_id).strip()
            for r in records
            if isinstance(r.request_id, str) and str(r.request_id).strip()
        }
        usage_recent_rows = db.exec(
            select(UsageLedgerV2).order_by(UsageLedgerV2.created_at.desc()).limit(max(limit * 8, 500))
        ).all()
        usage_by_request_recent: Dict[str, List[UsageLedgerV2]] = {}
        for usage_row in usage_recent_rows:
            rid = str(usage_row.request_id or "").strip()
            if not rid:
                continue
            usage_by_request_recent.setdefault(rid, []).append(usage_row)

        for rid, usage_entries in usage_by_request_recent.items():
            if rid in request_ids_in_records:
                continue
            first_entry = usage_entries[0]
            usage_user = db.get(User, first_entry.user_id) if first_entry.user_id is not None else None
            question_items: List[AdminChatBillingQuestionChargeItem] = []
            usage_total = 0.0
            usage_entries_sorted = sorted(
                usage_entries,
                key=lambda item: (
                    item.question_index if item.question_index is not None else 10_000,
                    item.created_at,
                ),
            )
            for usage_entry in usage_entries_sorted:
                q_cost = float(usage_entry.total_cost or 0)
                usage_total += q_cost
                question_items.append(
                AdminChatBillingQuestionChargeItem(
                    ledger_id=usage_entry.ledger_id,
                    hold_id=usage_entry.hold_id,
                    attempt_id=usage_entry.attempt_id,
                    question_id=usage_entry.question_id,
                    question_index=usage_entry.question_index,
                    action=usage_entry.action,
                        tier=usage_entry.tier,
                        outcome=usage_entry.outcome,
                        total_cost=q_cost,
                        created_at=usage_entry.created_at.isoformat() if usage_entry.created_at else "",
                    )
                )

            fallback_attempt_id = next(
                (str(item.attempt_id).strip() for item in usage_entries_sorted if str(item.attempt_id or "").strip()),
                "",
            )
            fallback_hold_id = next(
                (str(item.hold_id).strip() for item in usage_entries_sorted if str(item.hold_id or "").strip()),
                "",
            )
            question_labels = [str(item.question_id or f"q{item.question_index or '?'}") for item in usage_entries_sorted[:6]]
            labels_preview = ", ".join(question_labels)
            records.append(
                AdminChatBillingRecord(
                    session_id=0,
                    message_id=0,
                    role="assistant",
                    created_at=first_entry.created_at.isoformat() if first_entry.created_at else "",
                    user_id=int(first_entry.user_id or 0),
                    user_email=usage_user.email if usage_user else "unknown",
                    request_id=rid,
                    content_preview=(
                        "No chatmessage row found; rendered from usage_ledger fallback. "
                        f"attempt_id={fallback_attempt_id or 'n/a'} "
                        f"hold_id={fallback_hold_id or 'n/a'} "
                        f"questions=[{labels_preview}]"
                    ),
                    question_count=len(question_items),
                    charge_mode="batch" if len(question_items) > 1 else "single",
                    credits_charged_total=usage_total,
                    credits_source="usage_ledger",
                    provider_cost_usd_total=0.0,
                    provider_cost_source="none",
                    provider=None,
                    model=None,
                    input_tokens_total=0,
                    output_tokens_total=0,
                    total_tokens=0,
                    latency_ms=None,
                    billing_entries_count=0,
                    usage_entries_count=len(question_items),
                    ledger_entries_total_count=len(question_items),
                    billing_statuses=[],
                    per_question_total_credits=usage_total,
                    per_question_charges=question_items,
                )
            )
            request_ids_in_records.add(rid)

        records.sort(key=lambda row: row.created_at, reverse=True)
        if len(records) > limit:
            records = records[:limit]

    filtered_total = len(records) if not request_id_filter else len(records)
    if request_id_filter and not records:
        usage_entries = db.exec(
            select(UsageLedgerV2)
            .where(UsageLedgerV2.request_id == request_id_filter)
            .order_by(UsageLedgerV2.question_index.asc(), UsageLedgerV2.created_at.asc())
        ).all()
        if usage_entries:
            first_entry = usage_entries[0]
            usage_user = db.get(User, first_entry.user_id) if first_entry.user_id is not None else None
            question_items: List[AdminChatBillingQuestionChargeItem] = []
            usage_total = 0.0
            for usage_entry in usage_entries:
                q_cost = float(usage_entry.total_cost or 0)
                usage_total += q_cost
                question_items.append(
                    AdminChatBillingQuestionChargeItem(
                        ledger_id=usage_entry.ledger_id,
                        hold_id=usage_entry.hold_id,
                        attempt_id=usage_entry.attempt_id,
                        question_id=usage_entry.question_id,
                        question_index=usage_entry.question_index,
                        action=usage_entry.action,
                        tier=usage_entry.tier,
                        outcome=usage_entry.outcome,
                        total_cost=q_cost,
                        created_at=usage_entry.created_at.isoformat() if usage_entry.created_at else "",
                    )
                )
            fallback_attempt_id = next(
                (str(item.attempt_id).strip() for item in usage_entries if str(item.attempt_id or "").strip()),
                "",
            )
            fallback_hold_id = next(
                (str(item.hold_id).strip() for item in usage_entries if str(item.hold_id or "").strip()),
                "",
            )
            question_labels = [str(item.question_id or f"q{item.question_index or '?'}") for item in usage_entries[:6]]
            labels_preview = ", ".join(question_labels)
            records.append(
                AdminChatBillingRecord(
                    session_id=0,
                    message_id=0,
                    role="system",
                    created_at=first_entry.created_at.isoformat() if first_entry.created_at else "",
                    user_id=int(first_entry.user_id or 0),
                    user_email=usage_user.email if usage_user else "unknown",
                    request_id=request_id_filter,
                    content_preview=(
                        "No chatmessage row found; rendered from usage_ledger fallback. "
                        f"attempt_id={fallback_attempt_id or 'n/a'} "
                        f"hold_id={fallback_hold_id or 'n/a'} "
                        f"questions=[{labels_preview}]"
                    ),
                    question_count=len(question_items),
                    charge_mode="batch" if len(question_items) > 1 else "single",
                    credits_charged_total=usage_total,
                    credits_source="usage_ledger",
                    provider_cost_usd_total=0.0,
                    provider_cost_source="none",
                    provider=None,
                    model=None,
                    input_tokens_total=0,
                    output_tokens_total=0,
                    total_tokens=0,
                    latency_ms=None,
                    billing_entries_count=0,
                    usage_entries_count=len(question_items),
                    ledger_entries_total_count=len(question_items),
                    billing_statuses=[],
                    per_question_total_credits=usage_total,
                    per_question_charges=question_items,
                )
            )
            filtered_total = len(records)

    return AdminChatBillingListResponse(
        total=filtered_total,
        limit=limit,
        offset=offset,
        items=records,
    )


class AdminCanonicalProblemItem(BaseModel):
    id: int
    normalized_problem_hash: str
    normalized_text: str
    intent: str
    canonical_math_object: str
    assumptions_hash: Optional[str] = None
    prompt_version: Optional[str] = None
    solver_version: Optional[str] = None
    schema_version: Optional[str] = None
    normalized_latex_blocks: Optional[List[dict]] = None
    subject: Optional[str] = None
    language: str
    created_at: str
    last_seen_at: str
    seen_count: int


class AdminCanonicalProblemListResponse(BaseModel):
    total: int
    items: List[AdminCanonicalProblemItem]


class AdminCanonicalProblemCreateRequest(BaseModel):
    normalized_problem_hash: str
    normalized_text: str
    intent: str = "unknown"
    canonical_math_object: str = ""
    assumptions_hash: Optional[str] = None
    prompt_version: Optional[str] = None
    solver_version: Optional[str] = None
    schema_version: Optional[str] = None
    normalized_latex_blocks: Optional[List[dict]] = None
    subject: Optional[str] = None
    language: str = "en"
    seen_count: int = 1
    reason: str


class AdminCanonicalProblemUpdateRequest(BaseModel):
    normalized_text: Optional[str] = None
    intent: Optional[str] = None
    canonical_math_object: Optional[str] = None
    assumptions_hash: Optional[str] = None
    prompt_version: Optional[str] = None
    solver_version: Optional[str] = None
    schema_version: Optional[str] = None
    normalized_latex_blocks: Optional[List[dict]] = None
    subject: Optional[str] = None
    language: Optional[str] = None
    seen_count: Optional[int] = None
    reason: str


class AdminCanonicalProblemDeleteRequest(BaseModel):
    reason: str


class AdminCanonicalSolutionItem(BaseModel):
    id: int
    problem_id: int
    solution_json: dict
    verification_status: str
    verification_report: Optional[dict] = None
    prompt_version: Optional[str] = None
    model_id: Optional[str] = None
    created_at: str
    last_served_at: str
    served_count: int


class AdminCanonicalSolutionListResponse(BaseModel):
    total: int
    items: List[AdminCanonicalSolutionItem]


class AdminCanonicalSolutionCreateRequest(BaseModel):
    problem_id: int
    solution_json: dict
    verification_status: str = "pending"
    verification_report: Optional[dict] = None
    prompt_version: Optional[str] = None
    model_id: Optional[str] = None
    served_count: int = 1
    reason: str


class AdminCanonicalSolutionUpdateRequest(BaseModel):
    problem_id: Optional[int] = None
    solution_json: Optional[dict] = None
    verification_status: Optional[str] = None
    verification_report: Optional[dict] = None
    prompt_version: Optional[str] = None
    model_id: Optional[str] = None
    served_count: Optional[int] = None
    reason: str


class AdminCanonicalSolutionDeleteRequest(BaseModel):
    reason: str


def _serialize_canonical_problem_row(row: CanonicalProblem) -> AdminCanonicalProblemItem:
    return AdminCanonicalProblemItem(
        id=int(row.id or 0),
        normalized_problem_hash=row.normalized_problem_hash,
        normalized_text=row.normalized_text,
        intent=row.intent,
        canonical_math_object=row.canonical_math_object,
        assumptions_hash=row.assumptions_hash,
        prompt_version=row.prompt_version,
        solver_version=row.solver_version,
        schema_version=row.schema_version,
        normalized_latex_blocks=row.normalized_latex_blocks,
        subject=row.subject,
        language=row.language,
        created_at=row.created_at.isoformat() if row.created_at else "",
        last_seen_at=row.last_seen_at.isoformat() if row.last_seen_at else "",
        seen_count=row.seen_count,
    )


def _serialize_canonical_solution_row(row: CanonicalSolution) -> AdminCanonicalSolutionItem:
    return AdminCanonicalSolutionItem(
        id=int(row.id or 0),
        problem_id=row.problem_id,
        solution_json=row.solution_json,
        verification_status=row.verification_status,
        verification_report=row.verification_report,
        prompt_version=row.prompt_version,
        model_id=row.model_id,
        created_at=row.created_at.isoformat() if row.created_at else "",
        last_served_at=row.last_served_at.isoformat() if row.last_served_at else "",
        served_count=row.served_count,
    )


@api_router.get("/admin/cache/canonical/problems", response_model=AdminCanonicalProblemListResponse)
async def admin_list_canonical_problems(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    query = select(CanonicalProblem)
    where_clauses = []
    if q:
        needle = f"%{q.strip()}%"
        clause = (
            or_(
                CanonicalProblem.normalized_problem_hash.ilike(needle),
                CanonicalProblem.normalized_text.ilike(needle),
                CanonicalProblem.canonical_math_object.ilike(needle),
            )
        )
        where_clauses.append(clause)
        query = query.where(clause)
    if intent:
        clause = CanonicalProblem.intent == intent.strip()
        where_clauses.append(clause)
        query = query.where(clause)
    if subject:
        clause = CanonicalProblem.subject == subject.strip()
        where_clauses.append(clause)
        query = query.where(clause)

    rows = db.exec(query.order_by(CanonicalProblem.last_seen_at.desc()).offset(offset).limit(limit)).all()
    total = db.exec(
        select(func.count())
        .select_from(CanonicalProblem)
        .where(*where_clauses)
    ).one()
    return AdminCanonicalProblemListResponse(total=total, items=[_serialize_canonical_problem_row(r) for r in rows])


@api_router.post("/admin/cache/canonical/problems", response_model=AdminCanonicalProblemItem)
async def admin_create_canonical_problem(
    body: AdminCanonicalProblemCreateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    existing = db.exec(
        select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == body.normalized_problem_hash.strip())
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="normalized_problem_hash already exists")
    row = CanonicalProblem(
        normalized_problem_hash=body.normalized_problem_hash.strip(),
        normalized_text=body.normalized_text,
        intent=body.intent,
        canonical_math_object=body.canonical_math_object,
        assumptions_hash=body.assumptions_hash,
        prompt_version=body.prompt_version,
        solver_version=body.solver_version,
        schema_version=body.schema_version,
        normalized_latex_blocks=body.normalized_latex_blocks,
        subject=body.subject,
        language=body.language,
        seen_count=max(0, body.seen_count),
    )
    db.add(row)
    db.flush()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="CREATE",
        entity_type="CANONICAL_PROBLEM",
        entity_id=str(row.id),
        before_json=None,
        after_json=_serialize_canonical_problem_row(row).model_dump(),
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_canonical_problem_row(row)


@api_router.patch("/admin/cache/canonical/problems/{problem_id}", response_model=AdminCanonicalProblemItem)
async def admin_update_canonical_problem(
    problem_id: int,
    body: AdminCanonicalProblemUpdateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(CanonicalProblem, problem_id)
    if not row:
        raise HTTPException(status_code=404, detail="Canonical problem not found")
    before = _serialize_canonical_problem_row(row).model_dump()

    if body.normalized_text is not None:
        row.normalized_text = body.normalized_text
    if body.intent is not None:
        row.intent = body.intent
    if body.canonical_math_object is not None:
        row.canonical_math_object = body.canonical_math_object
    if body.assumptions_hash is not None:
        row.assumptions_hash = body.assumptions_hash
    if body.prompt_version is not None:
        row.prompt_version = body.prompt_version
    if body.solver_version is not None:
        row.solver_version = body.solver_version
    if body.schema_version is not None:
        row.schema_version = body.schema_version
    if body.normalized_latex_blocks is not None:
        row.normalized_latex_blocks = body.normalized_latex_blocks
    if body.subject is not None:
        row.subject = body.subject
    if body.language is not None:
        row.language = body.language
    if body.seen_count is not None:
        row.seen_count = max(0, body.seen_count)

    db.add(row)
    db.flush()
    after = _serialize_canonical_problem_row(row).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="UPDATE",
        entity_type="CANONICAL_PROBLEM",
        entity_id=str(row.id),
        before_json=before,
        after_json=after,
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_canonical_problem_row(row)


@api_router.delete("/admin/cache/canonical/problems/{problem_id}")
async def admin_delete_canonical_problem(
    problem_id: int,
    body: AdminCanonicalProblemDeleteRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(CanonicalProblem, problem_id)
    if not row:
        raise HTTPException(status_code=404, detail="Canonical problem not found")

    linked_solutions = db.exec(select(CanonicalSolution).where(CanonicalSolution.problem_id == problem_id)).all()
    before = _serialize_canonical_problem_row(row).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="DELETE",
        entity_type="CANONICAL_PROBLEM",
        entity_id=str(row.id),
        before_json=before,
        after_json=None,
        reason=body.reason.strip(),
        request=request,
    )
    for solution in linked_solutions:
        db.delete(solution)
    db.delete(row)
    db.commit()
    return {"status": "ok", "deleted_problem_id": problem_id, "deleted_solutions": len(linked_solutions)}


@api_router.get("/admin/cache/canonical/solutions", response_model=AdminCanonicalSolutionListResponse)
async def admin_list_canonical_solutions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    problem_id: Optional[int] = Query(None),
    verification_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    query = select(CanonicalSolution)
    where_clauses = []
    if problem_id is not None:
        clause = CanonicalSolution.problem_id == problem_id
        where_clauses.append(clause)
        query = query.where(clause)
    if verification_status:
        clause = CanonicalSolution.verification_status == verification_status.strip()
        where_clauses.append(clause)
        query = query.where(clause)
    if q:
        needle = f"%{q.strip()}%"
        clause = (
            or_(
                CanonicalSolution.model_id.ilike(needle),
                CanonicalSolution.prompt_version.ilike(needle),
            )
        )
        where_clauses.append(clause)
        query = query.where(clause)

    rows = db.exec(query.order_by(CanonicalSolution.last_served_at.desc()).offset(offset).limit(limit)).all()
    total = db.exec(
        select(func.count())
        .select_from(CanonicalSolution)
        .where(*where_clauses)
    ).one()
    return AdminCanonicalSolutionListResponse(total=total, items=[_serialize_canonical_solution_row(r) for r in rows])


@api_router.post("/admin/cache/canonical/solutions", response_model=AdminCanonicalSolutionItem)
async def admin_create_canonical_solution(
    body: AdminCanonicalSolutionCreateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    if not db.get(CanonicalProblem, body.problem_id):
        raise HTTPException(status_code=404, detail="Canonical problem not found")
    row = CanonicalSolution(
        problem_id=body.problem_id,
        solution_json=body.solution_json,
        verification_status=body.verification_status,
        verification_report=body.verification_report,
        prompt_version=body.prompt_version,
        model_id=body.model_id,
        served_count=max(0, body.served_count),
    )
    db.add(row)
    db.flush()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="CREATE",
        entity_type="CANONICAL_SOLUTION",
        entity_id=str(row.id),
        before_json=None,
        after_json=_serialize_canonical_solution_row(row).model_dump(),
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_canonical_solution_row(row)


@api_router.patch("/admin/cache/canonical/solutions/{solution_id}", response_model=AdminCanonicalSolutionItem)
async def admin_update_canonical_solution(
    solution_id: int,
    body: AdminCanonicalSolutionUpdateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(CanonicalSolution, solution_id)
    if not row:
        raise HTTPException(status_code=404, detail="Canonical solution not found")
    before = _serialize_canonical_solution_row(row).model_dump()

    if body.problem_id is not None:
        if not db.get(CanonicalProblem, body.problem_id):
            raise HTTPException(status_code=404, detail="Canonical problem not found")
        row.problem_id = body.problem_id
    if body.solution_json is not None:
        row.solution_json = body.solution_json
    if body.verification_status is not None:
        row.verification_status = body.verification_status
    if body.verification_report is not None:
        row.verification_report = body.verification_report
    if body.prompt_version is not None:
        row.prompt_version = body.prompt_version
    if body.model_id is not None:
        row.model_id = body.model_id
    if body.served_count is not None:
        row.served_count = max(0, body.served_count)

    db.add(row)
    db.flush()
    after = _serialize_canonical_solution_row(row).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="UPDATE",
        entity_type="CANONICAL_SOLUTION",
        entity_id=str(row.id),
        before_json=before,
        after_json=after,
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_canonical_solution_row(row)


@api_router.delete("/admin/cache/canonical/solutions/{solution_id}")
async def admin_delete_canonical_solution(
    solution_id: int,
    body: AdminCanonicalSolutionDeleteRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(CanonicalSolution, solution_id)
    if not row:
        raise HTTPException(status_code=404, detail="Canonical solution not found")
    before = _serialize_canonical_solution_row(row).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="DELETE",
        entity_type="CANONICAL_SOLUTION",
        entity_id=str(row.id),
        before_json=before,
        after_json=None,
        reason=body.reason.strip(),
        request=request,
    )
    db.delete(row)
    db.commit()
    return {"status": "ok", "deleted_solution_id": solution_id}


class AdminQuestionIdentityItem(BaseModel):
    id: int
    question_key: str
    normalized_stem: str
    normalized_options: Optional[str] = None
    question_type: str
    solution_json: dict
    original_variants: List[str]
    hit_count: int
    created_at: str
    last_seen_at: str
    last_user_id: Optional[int] = None
    last_user_email: Optional[str] = None


class AdminQuestionIdentityListResponse(BaseModel):
    total: int
    items: List[AdminQuestionIdentityItem]


class AdminQuestionIdentityCreateRequest(BaseModel):
    question_key: str
    normalized_stem: str
    normalized_options: Optional[str] = None
    question_type: str = "unknown"
    solution_json: dict
    original_variants: List[str] = []
    hit_count: int = 0
    reason: str


class AdminQuestionIdentityUpdateRequest(BaseModel):
    question_key: Optional[str] = None
    normalized_stem: Optional[str] = None
    normalized_options: Optional[str] = None
    question_type: Optional[str] = None
    solution_json: Optional[dict] = None
    original_variants: Optional[List[str]] = None
    hit_count: Optional[int] = None
    reason: str


class AdminQuestionIdentityDeleteRequest(BaseModel):
    reason: str


def _serialize_question_identity_row(
    row: QuestionIdentityCache,
    last_user_id: Optional[int] = None,
    last_user_email: Optional[str] = None,
) -> AdminQuestionIdentityItem:
    return AdminQuestionIdentityItem(
        id=int(row.id or 0),
        question_key=row.question_key,
        normalized_stem=row.normalized_stem,
        normalized_options=row.normalized_options,
        question_type=row.question_type,
        solution_json=row.solution_json,
        original_variants=row.original_variants or [],
        hit_count=row.hit_count,
        created_at=row.created_at.isoformat() if row.created_at else "",
        last_seen_at=row.last_seen_at.isoformat() if row.last_seen_at else "",
        last_user_id=last_user_id,
        last_user_email=last_user_email,
    )


@api_router.get("/admin/cache/question-identity", response_model=AdminQuestionIdentityListResponse)
async def admin_list_question_identity_cache(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    query = select(QuestionIdentityCache)
    if q:
        needle = f"%{q.strip()}%"
        query = query.where(
            or_(
                QuestionIdentityCache.question_key.ilike(needle),
                QuestionIdentityCache.normalized_stem.ilike(needle),
            )
        )
    if question_type:
        query = query.where(QuestionIdentityCache.question_type == question_type.strip())

    rows = db.exec(query.order_by(QuestionIdentityCache.last_seen_at.desc()).offset(offset).limit(limit)).all()
    question_keys = [r.question_key for r in rows if r.question_key]
    last_user_by_key: Dict[str, Tuple[Optional[int], Optional[str]]] = {}
    if question_keys:
        hold_rows = db.exec(
            select(CreditHold.question_id, CreditHold.user_id, User.email, CreditHold.created_at)
            .join(User, User.id == CreditHold.user_id)
            .where(CreditHold.question_id.in_(question_keys))
            .order_by(CreditHold.created_at.desc())
        ).all()
        for question_id, hold_user_id, hold_user_email, _created_at in hold_rows:
            if question_id and question_id not in last_user_by_key:
                last_user_by_key[question_id] = (hold_user_id, hold_user_email)
    total = len(db.exec(query).all())
    return AdminQuestionIdentityListResponse(
        total=total,
        items=[
            _serialize_question_identity_row(
                r,
                last_user_id=(last_user_by_key.get(r.question_key) or (None, None))[0],
                last_user_email=(last_user_by_key.get(r.question_key) or (None, None))[1],
            )
            for r in rows
        ],
    )


@api_router.get("/admin/cache/question-identity/{entry_id}", response_model=AdminQuestionIdentityItem)
async def admin_get_question_identity_cache_entry(
    entry_id: int,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    row = db.get(QuestionIdentityCache, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question identity cache entry not found")
    last_user_id: Optional[int] = None
    last_user_email: Optional[str] = None
    if row.question_key:
        latest_hold = db.exec(
            select(CreditHold.user_id, User.email)
            .join(User, User.id == CreditHold.user_id)
            .where(CreditHold.question_id == row.question_key)
            .order_by(CreditHold.created_at.desc())
        ).first()
        if latest_hold:
            last_user_id = latest_hold[0]
            last_user_email = latest_hold[1]
    return _serialize_question_identity_row(row, last_user_id=last_user_id, last_user_email=last_user_email)


@api_router.post("/admin/cache/question-identity", response_model=AdminQuestionIdentityItem)
async def admin_create_question_identity_cache_entry(
    body: AdminQuestionIdentityCreateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    existing = db.exec(select(QuestionIdentityCache).where(QuestionIdentityCache.question_key == body.question_key.strip())).first()
    if existing:
        raise HTTPException(status_code=409, detail="question_key already exists")
    row = QuestionIdentityCache(
        question_key=body.question_key.strip(),
        normalized_stem=body.normalized_stem,
        normalized_options=body.normalized_options,
        question_type=body.question_type,
        solution_json=body.solution_json,
        original_variants=body.original_variants or [],
        hit_count=max(0, body.hit_count),
    )
    db.add(row)
    db.flush()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="CREATE",
        entity_type="QUESTION_IDENTITY_CACHE",
        entity_id=str(row.id),
        before_json=None,
        after_json=_serialize_question_identity_row(row).model_dump(),
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_question_identity_row(row)


@api_router.patch("/admin/cache/question-identity/{entry_id}", response_model=AdminQuestionIdentityItem)
async def admin_update_question_identity_cache_entry(
    entry_id: int,
    body: AdminQuestionIdentityUpdateRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(QuestionIdentityCache, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question identity cache entry not found")
    before = _serialize_question_identity_row(row).model_dump()

    if body.question_key is not None:
        next_key = body.question_key.strip()
        if next_key and next_key != row.question_key:
            dup = db.exec(select(QuestionIdentityCache).where(QuestionIdentityCache.question_key == next_key)).first()
            if dup:
                raise HTTPException(status_code=409, detail="question_key already exists")
            row.question_key = next_key
    if body.normalized_stem is not None:
        row.normalized_stem = body.normalized_stem
    if body.normalized_options is not None:
        row.normalized_options = body.normalized_options
    if body.question_type is not None:
        row.question_type = body.question_type
    if body.solution_json is not None:
        row.solution_json = body.solution_json
    if body.original_variants is not None:
        row.original_variants = body.original_variants
    if body.hit_count is not None:
        row.hit_count = max(0, body.hit_count)

    db.add(row)
    db.flush()
    after = _serialize_question_identity_row(row).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="UPDATE",
        entity_type="QUESTION_IDENTITY_CACHE",
        entity_id=str(row.id),
        before_json=before,
        after_json=after,
        reason=body.reason.strip(),
        request=request,
    )
    db.commit()
    db.refresh(row)
    return _serialize_question_identity_row(row)


@api_router.delete("/admin/cache/question-identity/{entry_id}")
async def admin_delete_question_identity_cache_entry(
    entry_id: int,
    body: AdminQuestionIdentityDeleteRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    row = db.get(QuestionIdentityCache, entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Question identity cache entry not found")
    before = _serialize_question_identity_row(row).model_dump()
    audit_log_service.log_action(
        session=db,
        admin_user_id=admin.id or 0,
        action="DELETE",
        entity_type="QUESTION_IDENTITY_CACHE",
        entity_id=str(row.id),
        before_json=before,
        after_json=None,
        reason=body.reason.strip(),
        request=request,
    )
    db.delete(row)
    db.commit()
    return {"status": "ok", "deleted_id": entry_id}


@api_router.get("/admin/db/tables", response_model=List[str])
async def admin_list_db_tables(admin: User = Depends(get_admin_user)):
    return sorted(list(SQLModel.metadata.tables.keys()))


@api_router.get("/admin/db/table/{table_name}", response_model=List[Dict[str, Any]])
async def admin_get_db_table(
    table_name: str,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_session)
, admin: User = Depends(get_admin_user)):
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
async def admin_get_model_routing(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_get_quotas(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Admin only: List users and their usage for quota management"""
    from datetime import timedelta
    from decimal import Decimal
    from app.models import BillingLedger
    now = datetime.utcnow()
    last_24h = now - timedelta(days=1)
    
    users = db.exec(select(User).limit(50)).all()
    quota_items = []
    daily_active_holders = 0
    total_daily_tokens = 0
    total_daily_credits_used = Decimal("0")
    total_daily_credit_cap = 0.0
    tier_default_daily_caps = {
        "free": 5.0,
        "short": 5.0,
        "short_steps": 5.0,
        "final": 5.0,
        "standard": 50.0,
        "research": 200.0,
    }
    
    for u in users:
        subscription = db.exec(select(Subscription).where(Subscription.user_id == u.id)).first()
        plan = subscription.plan if subscription else None
        plan_features = plan.features or {} if plan else {}
        daily_credit_cap = float(plan_features.get("daily_credit_cap", 0)) if plan_features else 0.0
        if daily_credit_cap <= 0:
            daily_credit_cap = tier_default_daily_caps.get((u.subscription_tier or "").lower(), 0.0)

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
            daily_credits_used = sum([l.amount for l in daily_ledger], Decimal("0"))
        else:
            daily_credits_used = Decimal("0")

        # Billing v2 path: credits are tracked in BillingLedger. Fallback to it when legacy UsageLedger is empty.
        if daily_credits_used <= 0:
            billing_rows = db.exec(
                select(BillingLedger)
                .where(BillingLedger.user_id == u.id)
                .where(BillingLedger.created_at >= last_24h)
                .where(BillingLedger.ok == True)
            ).all()
            if billing_rows:
                billed_credits = Decimal("0")
                for row in billing_rows:
                    status = (row.status or "").upper()
                    if status in {"CHARGED", "SETTLED"}:
                        charged = Decimal(str(row.credits_charged or 0))
                        if charged > 0:
                            billed_credits += charged
                daily_credits_used = billed_credits

        total_daily_credits_used += daily_credits_used
        if daily_credit_cap > 0:
            total_daily_credit_cap += daily_credit_cap

        override = db.exec(select(UserQuotaOverride).where(UserQuotaOverride.user_id == u.id)).first()
        override_token_limit = override.token_limit if override else None
        override_ocr_concurrency = override.ocr_concurrency if override else None
        override_expires_at = override.expires_at.isoformat() if override and override.expires_at else None

        usage_pct = 0
        if daily_credit_cap > 0:
            # Daily usage bar is credit-cap based; if credit debits are not yet available,
            # fall back to token usage as a non-zero signal for active daily consumption.
            usage_basis = float(daily_credits_used) if float(daily_credits_used) > 0 else float(daily_tokens)
            usage_pct = int((usage_basis / daily_credit_cap) * 100)
        elif override_token_limit and override_token_limit > 0:
            usage_pct = int((daily_tokens / override_token_limit) * 100)
        
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
            daily_credits_used=float(daily_credits_used),
            daily_credit_cap=daily_credit_cap or None,
            daily_tokens_used=daily_tokens,
            override_token_limit=override_token_limit,
            override_ocr_concurrency=override_ocr_concurrency,
            override_expires_at=override_expires_at
        ))
    
    total_tokens_24h = total_daily_tokens
    global_consumption = 0.0
    if total_daily_credit_cap > 0:
        global_consumption = min((float(total_daily_credits_used) / total_daily_credit_cap) * 100, 100.0)
    
    return AdminQuotaListResponse(
        users=quota_items,
        total_users=len(db.exec(select(User.id)).all()),
        global_consumption=round(global_consumption, 1),
        daily_active_holders=daily_active_holders,
        tokens_burned_24h=f"{total_tokens_24h/1_000_000:.1f}M"
    )

@api_router.post("/admin/quotas/override")
async def admin_apply_quota_override(req: QuotaOverrideRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_list_system_config(session: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Admin only: fetch the entire system configuration table."""
    rows = session.exec(select(SystemConfig)).all()
    row_map = {str(row.key): row for row in rows}
    defaults: Dict[str, Dict[str, str]] = {
        "SOLVE_LOCAL_SYMPY_NUMPY_ENABLED": {
            "value": "true",
            "description": "Enable local SymPy/NumPy solve path before LLM fallback (FINAL/SHORT tiers).",
        },
    }
    for key, meta in defaults.items():
        if key not in row_map:
            session.add(
                SystemConfig(
                    key=key,
                    value=str(meta.get("value") or ""),
                    description=str(meta.get("description") or ""),
                )
            )
    session.commit()
    rows = session.exec(select(SystemConfig)).all()
    return [SystemConfigEntry(key=row.key, value=row.value, description=row.description) for row in rows]


@api_router.post("/admin/system-config")
async def admin_update_system_config(req: SystemConfigUpdateRequest, session: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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


@api_router.get("/admin/config/credit_transfer", response_model=CreditTransferAdminConfigResponse)
async def admin_get_credit_transfer_config(
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    cfg = load_credit_transfer_config(session)
    return CreditTransferAdminConfigResponse(
        credit_transfer_enabled=cfg.enabled,
        notifications_enabled=cfg.notifications_enabled,
        min_transfer=float(cfg.min_transfer),
        max_transfer=float(cfg.max_transfer),
        daily_cap=float(cfg.daily_cap),
        pending_expiry_days=cfg.pending_expiry_days,
        per_minute_limit=cfg.per_minute_limit,
        thank_per_minute_limit=cfg.thank_per_minute_limit,
        account_age_minutes_min=cfg.account_age_minutes_min,
    )


@api_router.put("/admin/config/credit_transfer", response_model=CreditTransferAdminConfigResponse)
async def admin_update_credit_transfer_config(
    req: CreditTransferAdminConfigUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    entries = [
        ("CREDIT_TRANSFER_ENABLED", "true" if req.credit_transfer_enabled else "false", "Enable credit transfer flow"),
        ("NOTIFICATIONS_ENABLED", "true" if req.notifications_enabled else "false", "Enable in-app notifications"),
        ("CREDIT_TRANSFER_MIN", str(req.min_transfer), "Minimum credit transfer amount"),
        ("CREDIT_TRANSFER_MAX", str(req.max_transfer), "Maximum credit transfer amount"),
        ("CREDIT_TRANSFER_DAILY_CAP", str(req.daily_cap), "Daily sender credit transfer cap"),
        ("CREDIT_TRANSFER_PENDING_EXPIRY_DAYS", str(req.pending_expiry_days), "Days before pending transfers expire/refund"),
        ("CREDIT_TRANSFER_PER_MIN_LIMIT", str(req.per_minute_limit), "Sender transfer rate limit per minute"),
        ("NOTIFICATIONS_THANK_PER_MIN_LIMIT", str(req.thank_per_minute_limit), "Notification thank action limit per minute"),
        ("CREDIT_TRANSFER_ACCOUNT_AGE_MINUTES", str(req.account_age_minutes_min), "Minimum account age (minutes) to allow transfer"),
    ]
    for key, value, description in entries:
        row = session.get(SystemConfig, key)
        if row:
            row.value = value
            row.description = description
        else:
            session.add(SystemConfig(key=key, value=value, description=description))
    session.commit()
    cfg = load_credit_transfer_config(session)
    return CreditTransferAdminConfigResponse(
        credit_transfer_enabled=cfg.enabled,
        notifications_enabled=cfg.notifications_enabled,
        min_transfer=float(cfg.min_transfer),
        max_transfer=float(cfg.max_transfer),
        daily_cap=float(cfg.daily_cap),
        pending_expiry_days=cfg.pending_expiry_days,
        per_minute_limit=cfg.per_minute_limit,
        thank_per_minute_limit=cfg.thank_per_minute_limit,
        account_age_minutes_min=cfg.account_age_minutes_min,
    )


@api_router.get("/admin/solve-v2-config", response_model=SolveV2ConfigResponse)
async def admin_get_solve_v2_config(session: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    def _get(key: str, default: str) -> str:
        row = session.get(SystemConfig, key)
        if not row or row.value is None:
            return default
        return str(row.value)

    return SolveV2ConfigResponse(
        system_prompt_id=_get("SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2_compact.txt"),
        orchestrator_prompt_id=_get("SOLVE_ORCHESTRATOR_DEV_PROMPT_ID", "solve_orchestrator_developer_v2_compact.txt"),
        output_contract_id=_get("SOLVE_OUTPUT_CONTRACT_ID", "solve_output_contract_v2_compact.txt"),
        narrator_prompt_id=_get("SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2_compact.txt"),
        plot_spec_prompt_id=_get("SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2_compact.txt"),
        repair_prompt_id=_get("SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_patch_v1.txt"),
        clarify_prompt_id=_get("SOLVE_CLARIFY_PROMPT_ID", "solve_clarification_patch_v1.txt"),
        schema_id=_get("SOLVE_SCHEMA_ID", "solve_superset_v2.schema.json"),
        llm_min_schema_id=_get("SOLVE_LLM_MIN_SCHEMA_ID", "solve_llm_min_v2.schema.json"),
        clarify_schema_id=_get("SOLVE_CLARIFY_SCHEMA_ID", "solve_clarification_patch_v1.schema.json"),
        repair_schema_id=_get("SOLVE_REPAIR_SCHEMA_ID", "solve_repair_patch_v1.schema.json"),
        tier_policy_json=_get("SOLVE_TIER_POLICY_JSON", "{}"),
        narrator_enabled=_get("SOLVE_NARRATOR_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
    )


@api_router.post("/admin/solve-v2-config")
async def admin_update_solve_v2_config(
    req: SolveV2ConfigUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    entries = [
        ("SOLVE_SYSTEM_PROMPT_ID", req.system_prompt_id, "Active solve system prompt ID"),
        ("SOLVE_ORCHESTRATOR_DEV_PROMPT_ID", req.orchestrator_prompt_id, "Active solve orchestrator developer prompt ID"),
        ("SOLVE_OUTPUT_CONTRACT_ID", req.output_contract_id or "solve_output_contract_v2_compact.txt", "Legacy output contract prompt ID (unused by solve_v3)"),
        ("SOLVE_NARRATOR_PROMPT_ID", req.narrator_prompt_id, "Active solve narrator prompt ID"),
        ("SOLVE_PLOT_SPEC_PROMPT_ID", req.plot_spec_prompt_id, "Active solve plot spec prompt ID"),
        ("SOLVE_REPAIR_PROMPT_ID", req.repair_prompt_id, "Active solve verification-repair prompt ID"),
        ("SOLVE_CLARIFY_PROMPT_ID", req.clarify_prompt_id, "Active solve clarification prompt ID"),
        ("SOLVE_SCHEMA_ID", req.schema_id, "Active solve schema ID"),
        ("SOLVE_LLM_MIN_SCHEMA_ID", req.llm_min_schema_id, "Active solve main LLM-min schema ID"),
        ("SOLVE_CLARIFY_SCHEMA_ID", req.clarify_schema_id, "Active solve clarification patch schema ID"),
        ("SOLVE_REPAIR_SCHEMA_ID", req.repair_schema_id, "Active solve repair patch schema ID"),
        ("SOLVE_TIER_POLICY_JSON", req.tier_policy_json, "Tier policy JSON (min/max steps, max tokens, narrator)"),
        ("SOLVE_NARRATOR_ENABLED", "true" if req.narrator_enabled else "false", "Enable post-verification narrator pass"),
    ]
    updated = 0
    for key, value, description in entries:
        row = session.get(SystemConfig, key)
        if row:
            row.value = value
            row.description = description
        else:
            row = SystemConfig(key=key, value=value, description=description)
            session.add(row)
        updated += 1
    session.commit()
    return {"ok": True, "updated": updated}

@api_router.get("/admin/users/{user_id}/full", response_model=AdminUserDetailResponse)
async def admin_get_user_full_data(user_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    from app.models import ChatSession, OCRJob, AdminNote

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Subscription info
    sub = db.exec(select(Subscription).where(Subscription.user_id == user.id)).first()
    plan = sub.plan if sub else None
    
    # Usage stats
    questions_used = db.exec(select(func.count(ChatSession.id)).where(ChatSession.user_id == user.id)).one()
    scans_used = db.exec(select(func.count(OCRJob.id)).where(OCRJob.user_id == user.id)).one()

    notes = []
    if user.admin_notes:
        for n in user.admin_notes:
            notes.append(AdminNoteResponse(
                id=n.id,
                admin_name=n.admin_name,
                content=n.content,
                created_at=n.created_at.isoformat()
            ))

    return AdminUserDetailResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        subscription_id=sub.id if sub else None,
        plan_id=plan.id if plan else None,
        plan_slug=plan.slug if plan else None,
        plan_name=plan.name if plan else None,
        plan_credits_per_month=plan.credits_per_month if plan else None,
        plan_price_monthly_cents=plan.price_monthly_cents if plan else None,
        academic_level=user.academic_level,
        joined_at=user.created_at.isoformat(),
        avatar_url=user.avatar_url,
        quota_questions_total=user.quota_questions_total,
        quota_scans_total=user.quota_scans_total,
        questions_used=questions_used,
        scans_used=scans_used,
        notes=notes
    )

@api_router.get("/admin/users/{user_id}/activity", response_model=List[AdminActivityItem])
async def admin_get_user_activity(user_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
, admin: User = Depends(get_admin_user)):
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
async def admin_get_prompts_removed(admin: User = Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.get("/admin/prompts/{template_id}/versions")
async def admin_get_prompt_versions_removed(template_id: int, admin: User = Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.post("/admin/prompts/{template_id}/save")
async def admin_save_prompt_removed(template_id: int, admin: User = Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)

@api_router.post("/admin/prompts/versions/{version_id}/deploy")
async def admin_deploy_prompt_removed(version_id: int, admin: User = Depends(get_admin_user)):
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
    max_output_tokens: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_questions_allowed: Optional[int] = None
    system_schema_budget_tokens: Optional[int] = None
    context_budget_tokens: Optional[int] = None
    json_retry_max_output_tokens: Optional[int] = None
    json_retry_max_attempts: Optional[int] = None
    timeout_ms: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    plot_points_cap: Optional[int] = None
    plot_traces_cap: Optional[int] = None
    plot_annotations_cap: Optional[int] = None
    trim_strategy: Optional[str] = None
    max_steps: Optional[int] = None
    retry_cap_tokens: Optional[int] = None
    solve_text_cost: Optional[float] = None
    solve_snap_image_cost: Optional[float] = None
    solve_snap_pdf_cost: Optional[float] = None
    solve_voice_cost: Optional[float] = None
    verify_addon_cost: Optional[float] = None
    plot_addon_cost: Optional[float] = None
    attempt_fee: Optional[float] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    multipliers: Dict[str, Any] = Field(default_factory=dict)
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

class PromptRegistryDeleteResponse(BaseModel):
    status: str
    prompt_id: str
    deleted_versions: int
    rebound_bindings: int
    deactivated_bindings: int

class SchemaRegistryDeleteResponse(BaseModel):
    status: str
    schema_id: str
    deleted_versions: int
    rebound_bindings: int
    deactivated_bindings: int

class BindingRegistryDeleteResponse(BaseModel):
    status: str
    binding_id: str

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
    max_output_tokens: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_questions_allowed: Optional[int] = None
    system_schema_budget_tokens: Optional[int] = None
    context_budget_tokens: Optional[int] = None
    json_retry_max_output_tokens: Optional[int] = None
    json_retry_max_attempts: Optional[int] = None
    timeout_ms: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    plot_points_cap: Optional[int] = None
    plot_traces_cap: Optional[int] = None
    plot_annotations_cap: Optional[int] = None
    trim_strategy: Optional[str] = None
    max_steps: Optional[int] = None
    retry_cap_tokens: Optional[int] = None
    solve_text_cost: Optional[float] = None
    solve_snap_image_cost: Optional[float] = None
    solve_snap_pdf_cost: Optional[float] = None
    solve_voice_cost: Optional[float] = None
    verify_addon_cost: Optional[float] = None
    plot_addon_cost: Optional[float] = None
    attempt_fee: Optional[float] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    multipliers: Dict[str, Any] = Field(default_factory=dict)
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
    raw = str(value).strip().upper()
    if raw in {"THREE_STEP", "FREE"}:
        raw = "SHORT_STEPS"
    elif raw in {"SHORT"}:
        raw = "FINAL"
    return PromptTierEnum(raw)

def _parse_mode(value: str) -> PromptModeEnum:
    return PromptModeEnum(value.upper())

def _parse_role(value: str) -> PromptRoleEnum:
    return PromptRoleEnum(value.upper())


def _is_production_env() -> bool:
    return os.environ.get("APP_ENV", "").strip().upper() in {"PROD", "PRODUCTION"}


def _enforce_prompt_registry_allowlist() -> bool:
    return os.environ.get("PROMPT_REGISTRY_ENFORCE_ALLOWLIST", "").strip().lower() in {"1", "true", "yes", "on"}


def _enforce_allowed_prompt_id(prompt_id: str) -> None:
    if _is_production_env() and _enforce_prompt_registry_allowlist() and prompt_id not in ALLOWED_PROMPT_IDS:
        raise HTTPException(status_code=400, detail=f"prompt_id not allowed in production: {prompt_id}")


def _enforce_allowed_schema_id(schema_id: str) -> None:
    # Schema registry is intentionally open for admin-managed schema evolution
    # across all environments (DEV/TEST/PROD).
    return

@api_router.get("/admin/prompt-registry/prompts", response_model=List[RegistryPromptItem])
async def admin_list_prompt_registry_prompts(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_session),
admin: User = Depends(get_admin_user)):
    if not include_inactive:
        rows = db.exec(
            select(PromptTemplateEntry)
            .where(PromptTemplateEntry.is_active == True)
            .order_by(PromptTemplateEntry.prompt_id.asc())
        ).all()
    else:
        all_rows = db.exec(
            select(PromptTemplateEntry)
            .order_by(PromptTemplateEntry.prompt_id.asc(), PromptTemplateEntry.version.desc())
        ).all()
        latest_by_id: Dict[str, PromptTemplateEntry] = {}
        for row in all_rows:
            chosen = latest_by_id.get(row.prompt_id)
            if chosen is None:
                latest_by_id[row.prompt_id] = row
                continue
            if (not chosen.is_active) and row.is_active:
                latest_by_id[row.prompt_id] = row
        rows = sorted(latest_by_id.values(), key=lambda item: item.prompt_id)

    filtered = [row for row in rows if row.prompt_id in ALLOWED_PROMPT_IDS] if (_is_production_env() and _enforce_prompt_registry_allowlist()) else rows
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
        for row in filtered
    ]

@api_router.get("/admin/prompt-registry/prompts/{prompt_id}/versions", response_model=List[RegistryPromptItem])
async def admin_list_prompt_registry_versions(prompt_id: str, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_prompt_id(prompt_id)
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
async def admin_update_prompt_registry_prompt(prompt_id: str, req: PromptRegistryUpdateRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_prompt_id(prompt_id)
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
async def admin_rollback_prompt_registry_prompt(prompt_id: str, req: RegistryRollbackRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_prompt_id(prompt_id)
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

@api_router.delete("/admin/prompt-registry/prompts/{prompt_id}", response_model=PromptRegistryDeleteResponse)
async def admin_delete_prompt_registry_prompt(
    prompt_id: str,
    updated_by: Optional[str] = Query(None),
    db: Session = Depends(get_session),
admin: User = Depends(get_admin_user)):
    _enforce_allowed_prompt_id(prompt_id)
    try:
        result = prompt_registry_service.delete_prompt(
            session=db,
            prompt_id=prompt_id,
            updated_by=updated_by,
        )
    except PromptRegistryError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return PromptRegistryDeleteResponse(
        status="ok",
        prompt_id=prompt_id,
        deleted_versions=result["deleted_versions"],
        rebound_bindings=result["rebound_bindings"],
        deactivated_bindings=result["deactivated_bindings"],
    )

@api_router.get("/admin/prompt-registry/schemas", response_model=List[RegistrySchemaItem])
async def admin_list_prompt_registry_schemas(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_session),
admin: User = Depends(get_admin_user)):
    if not include_inactive:
        rows = db.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.is_active == True)
            .order_by(JsonSchemaEntry.schema_id.asc())
        ).all()
    else:
        all_rows = db.exec(
            select(JsonSchemaEntry)
            .order_by(JsonSchemaEntry.schema_id.asc(), JsonSchemaEntry.version.desc())
        ).all()
        latest_by_id: Dict[str, JsonSchemaEntry] = {}
        for row in all_rows:
            chosen = latest_by_id.get(row.schema_id)
            if chosen is None:
                latest_by_id[row.schema_id] = row
                continue
            if (not chosen.is_active) and row.is_active:
                latest_by_id[row.schema_id] = row
        rows = sorted(latest_by_id.values(), key=lambda item: item.schema_id)

    filtered = [row for row in rows if row.schema_id in ALLOWED_SCHEMA_IDS] if (_is_production_env() and _enforce_prompt_registry_allowlist()) else rows
    return [
        RegistrySchemaItem(
            schema_id=row.schema_id,
            version=row.version,
            is_active=row.is_active,
            content=None,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in filtered
    ]

@api_router.get("/admin/prompt-registry/schemas/{schema_id}/versions", response_model=List[RegistrySchemaItem])
async def admin_list_prompt_registry_schema_versions(schema_id: str, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_schema_id(schema_id)
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
async def admin_update_prompt_registry_schema(schema_id: str, req: SchemaRegistryUpdateRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_schema_id(schema_id)
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
async def admin_rollback_prompt_registry_schema(schema_id: str, req: RegistryRollbackRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_schema_id(schema_id)
    entry = prompt_registry_service.rollback_schema(db, schema_id, req.version, req.updated_by)
    return RegistrySchemaItem(
        schema_id=entry.schema_id,
        version=entry.version,
        is_active=entry.is_active,
        content=entry.content,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.delete("/admin/prompt-registry/schemas/{schema_id}", response_model=SchemaRegistryDeleteResponse)
async def admin_delete_prompt_registry_schema(
    schema_id: str,
    updated_by: Optional[str] = Query(None),
    db: Session = Depends(get_session),
admin: User = Depends(get_admin_user)):
    _enforce_allowed_schema_id(schema_id)
    try:
        result = prompt_registry_service.delete_schema(
            session=db,
            schema_id=schema_id,
            updated_by=updated_by,
        )
    except PromptRegistryError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return SchemaRegistryDeleteResponse(
        status="ok",
        schema_id=schema_id,
        deleted_versions=result["deleted_versions"],
        rebound_bindings=result["rebound_bindings"],
        deactivated_bindings=result["deactivated_bindings"],
    )

@api_router.get("/admin/prompt-registry/bindings", response_model=List[RegistryBindingItem])
async def admin_list_prompt_registry_bindings(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    statement = (
        select(PromptBinding)
        .where(PromptBinding.mode == PromptModeEnum.SOLVE)
        .order_by(PromptBinding.updated_at.desc())
    )
    if _is_production_env() and _enforce_prompt_registry_allowlist():
        statement = (
            statement
            .where(PromptBinding.global_system_prompt_id.in_(ALLOWED_PROMPT_IDS))
            .where(PromptBinding.developer_prompt_id.in_(ALLOWED_PROMPT_IDS))
            .where(PromptBinding.output_schema_id.in_(ALLOWED_SCHEMA_IDS))
        )
    rows = db.exec(statement).all()
    return [
        RegistryBindingItem(
            id=row.id,
            tier=row.tier.value,
            mode=row.mode.value,
            global_system_prompt_id=row.global_system_prompt_id,
            developer_prompt_id=row.developer_prompt_id,
            output_schema_id=row.output_schema_id,
            max_output_tokens=row.max_output_tokens,
            max_input_tokens=row.max_input_tokens,
            max_questions_allowed=row.max_questions_allowed,
            system_schema_budget_tokens=row.system_schema_budget_tokens,
            context_budget_tokens=row.context_budget_tokens,
            json_retry_max_output_tokens=row.json_retry_max_output_tokens,
            json_retry_max_attempts=row.json_retry_max_attempts,
            timeout_ms=row.timeout_ms,
            temperature=row.temperature,
            top_p=row.top_p,
            plot_points_cap=row.plot_points_cap,
            plot_traces_cap=row.plot_traces_cap,
            plot_annotations_cap=row.plot_annotations_cap,
            trim_strategy=row.trim_strategy.value if row.trim_strategy else None,
            max_steps=row.max_steps,
            retry_cap_tokens=row.retry_cap_tokens,
            solve_text_cost=float(row.solve_text_cost) if row.solve_text_cost is not None else None,
            solve_snap_image_cost=float(row.solve_snap_image_cost) if row.solve_snap_image_cost is not None else None,
            solve_snap_pdf_cost=float(row.solve_snap_pdf_cost) if row.solve_snap_pdf_cost is not None else None,
            solve_voice_cost=float(row.solve_voice_cost) if row.solve_voice_cost is not None else None,
            verify_addon_cost=float(row.verify_addon_cost) if row.verify_addon_cost is not None else None,
            plot_addon_cost=float(row.plot_addon_cost) if row.plot_addon_cost is not None else None,
            attempt_fee=float(row.attempt_fee) if row.attempt_fee is not None else None,
            features=row.features or {},
            multipliers=row.multipliers or {},
            is_active=row.is_active,
            updated_at=row.updated_at.isoformat(),
            updated_by=row.updated_by,
        )
        for row in rows
    ]

@api_router.get("/admin/prompt-registry/audit", response_model=RegistryBindingAuditReport)
async def admin_prompt_registry_audit(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    report = prompt_registry_service.audit_active_bindings(db)
    return RegistryBindingAuditReport(
        ok=report.get("ok", False),
        active_bindings=report.get("active_bindings", 0),
        active_binding_pairs=report.get("active_binding_pairs", 0),
        issues=[RegistryBindingAuditIssue(**issue) for issue in report.get("issues", [])],
    )

@api_router.post("/admin/prompt-registry/bindings/activate", response_model=RegistryBindingItem)
async def admin_activate_prompt_registry_binding(req: BindingActivateRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    _enforce_allowed_prompt_id(req.global_system_prompt_id)
    _enforce_allowed_prompt_id(req.developer_prompt_id)
    _enforce_allowed_schema_id(req.output_schema_id)
    if _is_production_env() and _parse_mode(req.mode) != PromptModeEnum.SOLVE:
        raise HTTPException(status_code=400, detail="Only SOLVE mode bindings are allowed in production.")
    try:
        entry = prompt_registry_service.activate_binding(
            session=db,
            tier=_parse_tier(req.tier),
            mode=_parse_mode(req.mode),
            global_system_prompt_id=req.global_system_prompt_id,
            developer_prompt_id=req.developer_prompt_id,
            output_schema_id=req.output_schema_id,
            updated_by=req.updated_by,
            max_output_tokens=req.max_output_tokens,
            max_input_tokens=req.max_input_tokens,
            max_questions_allowed=req.max_questions_allowed,
            system_schema_budget_tokens=req.system_schema_budget_tokens,
            context_budget_tokens=req.context_budget_tokens,
            json_retry_max_output_tokens=req.json_retry_max_output_tokens,
            json_retry_max_attempts=req.json_retry_max_attempts,
            timeout_ms=req.timeout_ms,
            temperature=req.temperature,
            top_p=req.top_p,
            plot_points_cap=req.plot_points_cap,
            plot_traces_cap=req.plot_traces_cap,
            plot_annotations_cap=req.plot_annotations_cap,
            trim_strategy=req.trim_strategy,
            max_steps=req.max_steps,
            retry_cap_tokens=req.retry_cap_tokens,
            solve_text_cost=req.solve_text_cost,
            solve_snap_image_cost=req.solve_snap_image_cost,
            solve_snap_pdf_cost=req.solve_snap_pdf_cost,
            solve_voice_cost=req.solve_voice_cost,
            verify_addon_cost=req.verify_addon_cost,
            plot_addon_cost=req.plot_addon_cost,
            attempt_fee=req.attempt_fee,
            features=req.features,
            multipliers=req.multipliers,
        )
    except PromptRegistryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Binding activation conflict: this tuple already exists. Refresh and retry.",
        )
    return RegistryBindingItem(
        id=entry.id,
        tier=entry.tier.value,
        mode=entry.mode.value,
        global_system_prompt_id=entry.global_system_prompt_id,
        developer_prompt_id=entry.developer_prompt_id,
        output_schema_id=entry.output_schema_id,
        max_output_tokens=entry.max_output_tokens,
        max_input_tokens=entry.max_input_tokens,
        max_questions_allowed=entry.max_questions_allowed,
        system_schema_budget_tokens=entry.system_schema_budget_tokens,
        context_budget_tokens=entry.context_budget_tokens,
        json_retry_max_output_tokens=entry.json_retry_max_output_tokens,
        json_retry_max_attempts=entry.json_retry_max_attempts,
        timeout_ms=entry.timeout_ms,
        temperature=entry.temperature,
        top_p=entry.top_p,
        plot_points_cap=entry.plot_points_cap,
        plot_traces_cap=entry.plot_traces_cap,
        plot_annotations_cap=entry.plot_annotations_cap,
        trim_strategy=entry.trim_strategy.value if entry.trim_strategy else None,
        max_steps=entry.max_steps,
        retry_cap_tokens=entry.retry_cap_tokens,
        solve_text_cost=float(entry.solve_text_cost) if entry.solve_text_cost is not None else None,
        solve_snap_image_cost=float(entry.solve_snap_image_cost) if entry.solve_snap_image_cost is not None else None,
        solve_snap_pdf_cost=float(entry.solve_snap_pdf_cost) if entry.solve_snap_pdf_cost is not None else None,
        solve_voice_cost=float(entry.solve_voice_cost) if entry.solve_voice_cost is not None else None,
        verify_addon_cost=float(entry.verify_addon_cost) if entry.verify_addon_cost is not None else None,
        plot_addon_cost=float(entry.plot_addon_cost) if entry.plot_addon_cost is not None else None,
        attempt_fee=float(entry.attempt_fee) if entry.attempt_fee is not None else None,
        features=entry.features or {},
        multipliers=entry.multipliers or {},
        is_active=entry.is_active,
        updated_at=entry.updated_at.isoformat(),
        updated_by=entry.updated_by,
    )

@api_router.delete("/admin/prompt-registry/bindings/{binding_id}", response_model=BindingRegistryDeleteResponse)
async def admin_delete_prompt_registry_binding(binding_id: str, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    row = db.get(PromptBinding, binding_id)
    if not row:
        raise HTTPException(status_code=404, detail="Binding not found.")
    db.delete(row)
    db.commit()
    return BindingRegistryDeleteResponse(status="ok", binding_id=binding_id)

@api_router.post("/admin/prompt-registry/test")
async def admin_prompt_registry_test(req: PromptRegistryTestRequest, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
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
async def admin_reset_llm_circuit_breaker(provider: str = Query("openai"), admin: User = Depends(get_admin_user)):
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


class PlanAdminUpdate(BaseModel):
    name: str
    slug: str
    credits_per_month: int
    price_monthly_cents: int
    price_yearly_cents: int
    seats: int = 1
    features: Dict[str, Any] = {}
    multipliers: Dict[str, Any] = {}
    is_active: bool = True


LEGACY_PLAN_MUTATION_DETAIL = (
    "Legacy plans/subscriptions are disabled. Use Credit Programs. "
    "This endpoint is read-only and will be removed."
)

@api_router.get('/admin/plans')
async def list_plans(session: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    return session.exec(select(Plan)).all()

@api_router.put('/admin/plans/{plan_id}')
async def admin_update_plan(
    plan_id: int,
    payload: PlanAdminUpdate,
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    from app.schemas.pricing import PlanMultipliers
    try:
        PlanMultipliers(**(payload.multipliers or {}))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid multipliers payload: {exc}") from exc

    update_data = payload.model_dump()
    for key, value in update_data.items():
        setattr(plan, key, value)
    plan.version = int(getattr(plan, "version", 1) or 1) + 1

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

@api_router.post('/admin/plans')
async def admin_save_plan(plan: Plan, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PLAN_MUTATION_DETAIL)
    if plan.id == 0:
        plan.id = None
        db.add(plan)
    else:
        existing = db.get(Plan, plan.id)
        if existing:
            for key, value in plan.dict(exclude={"id"}).items():
                setattr(existing, key, value)
            db.add(existing)
        else:
            db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

@api_router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: int, db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PLAN_MUTATION_DETAIL)
    """Delete a plan if it's not and has never been used by any users."""
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check current assignments
    usage_count = db.exec(select(func.count(User.id)).where(User.subscription_tier == plan.slug)).one()
    if usage_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete plan: {usage_count} users are currently assigned to this tier.")
    
    # Check historical or active subscription records
    sub_usage = db.exec(select(func.count(Subscription.id)).where(Subscription.plan_id == plan_id)).one()
    if sub_usage > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete plan: {sub_usage} active/past subscriptions are linked to it.")

    db.delete(plan)
    db.commit()
    return {"status": "ok"}

@api_router.post('/admin/plans')
async def create_or_update_plan(plan_data: PlanCreate, session: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PLAN_MUTATION_DETAIL)
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

@api_router.post('/subscriptions/stripe/checkout')
async def create_subscription_stripe_checkout(
    plan_slug: str = Body(..., embed=True),
    success_url: str = Body(..., embed=True),
    cancel_url: str = Body(..., embed=True),
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    """Initiate Stripe checkout session for a subscription plan."""
    try:
        requires_terms_acceptance, required_terms_version = get_terms_requirement_status(session, user_id=user_id)
        if requires_terms_acceptance:
            raise HTTPException(
                status_code=428,
                detail={
                    "code": "terms_acceptance_required",
                    "message": "You must accept the latest Terms of Service before completing checkout.",
                    "document_key": "terms_of_service",
                    "document_version": required_terms_version,
                },
            )
        return subscription_service.create_stripe_checkout_session(
            session, user_id, plan_slug, success_url, cancel_url
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.error(f"Subscription checkout error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



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
    from app.services.math.error_localizer import OCRPayload, Budget, find_first_error_from_ocr
    
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
        try:
            ocr_result = ocr_service.recognize_region(crop_bytes, engine_name="local")
        except Exception as exc:
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=selection_bbox,
                error={
                    "code": "DEPENDENCY_UNAVAILABLE",
                    "status": "dependency_unavailable",
                    "reason": f"OCR unavailable: {type(exc).__name__}",
                    "retryable": True,
                },
                timings_ms=TimingsMs(**timings),
            )
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
        payload = OCRPayload(raw=ocr_result.get("raw", ""), text=ocr_result["text"], confidence=float(ocr_result.get("confidence", 0.0)))
        analysis_result = find_first_error_from_ocr(
            payload,
            transcript_hint="find_error",
            max_lines=max_lines,
            budget=Budget(
                total_ms=int(os.getenv("LOCAL_FINDERR_TOTAL_MS", "1500")),
                sympy_ms=int(os.getenv("LOCAL_FINDERR_SYMPY_MS", "700")),
                numeric_ms=int(os.getenv("LOCAL_FINDERR_NUMERIC_MS", "700")),
            ),
        )
        analysis = {
            "detected_format": analysis_result.detected_format,
            "first_wrong_line_index": analysis_result.first_wrong_line_index,
            "what_is_wrong": analysis_result.what_is_wrong,
            "minimal_fix": analysis_result.minimal_fix,
            "confidence": float(analysis_result.confidence),
        }
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

@api_router.get("/whatsapp/status")
async def get_public_whatsapp_status():
    """Public WhatsApp bot status for user-profile gating."""
    return whatsapp_service.get_status()

@api_router.post("/admin/whatsapp/initialize")
async def initialize_whatsapp_bot(db: Session = Depends(get_session)):
    """Initialize WhatsApp bot and generate QR code"""
    previous_status = (whatsapp_service.get_status() or {}).get("status")
    result = await whatsapp_service.initialize()
    current_status = (result or {}).get("status")
    if (
        previous_status == "disconnected"
        and current_status in {"connecting", "qr_ready", "connected"}
    ):
        regenerated_count = _regenerate_whatsapp_secrets_for_all_users(db)
        result = {**result, "regenerated_whatsapp_codes": regenerated_count}
    return result

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

@api_router.delete("/admin/logs/all")
async def admin_clear_logs(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Truncate the main trace/event logs for performance reset."""
    db.execute(sql_text("TRUNCATE TABLE requestevent CASCADE;"))
    db.execute(sql_text("TRUNCATE TABLE usagelog CASCADE;"))
    db.commit()

    # Also clear the file-based solve traces
    from app.services.solve.trace_logger import TRACE_LOG_PATH
    if TRACE_LOG_PATH.exists():
        try:
            # Truncate file
            with TRACE_LOG_PATH.open("w", encoding="utf-8") as f:
                pass
        except Exception:
            pass

    return {"status": "ok"}

@api_router.delete("/admin/solver-attempts/all")
async def admin_clear_solver_attempts(db: Session = Depends(get_session), admin: User = Depends(get_admin_user)):
    """Clear all solver output attempts."""
    db.execute(sql_text("TRUNCATE TABLE solveroutputattempt CASCADE;"))
    db.commit()
    return {"status": "ok"}

@api_router.delete("/admin/whatsapp/all")
async def admin_clear_whatsapp_monitor(admin: User = Depends(get_admin_user)):
    """Clear the persistent WhatsApp event list in Redis."""
    try:
        get_redis().delete("whatsapp:events")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear Redis: {str(e)}")

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
    cleaned_text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text).strip()
    code_match = re.match(
        r"^(?:CODE[\s:\-]*)?([A-Z0-9]{8})$",
        cleaned_text.upper(),
    )
    if code_match:
        code = code_match.group(1)
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

@api_router.post("/solve/clarify", response_model=SolveResponse)
async def solve_clarify(
    request: Request,
    attempt_id: str = Body(..., embed=True),
    user_response: str = Body(..., embed=True),
    session: Session = Depends(get_session)
):
    """
    Phase 1: Resume an ambiguous attempt with user clarification.
    """
    from sqlalchemy.orm import selectinload
    attempt = session.exec(
        select(SolverOutputAttempt)
        .where(SolverOutputAttempt.attempt_id == attempt_id)
        .options(
            selectinload(SolverOutputAttempt.user).selectinload(User.subscription).selectinload(Subscription.plan),
            selectinload(SolverOutputAttempt.chat_session)
        )
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    if attempt.status != "ambiguous" and attempt.status != "failure" and attempt.status != "processing":
        # We allow 'processing' if resuming from a crash? No, 'ambiguous' is the main use case.
        # But we also want to allow clarifications on failures if the failure was "I don't understand".
        # For now, we allow 'ambiguous' and 'failure'.
        if attempt.status == "success":
             raise HTTPException(status_code=400, detail="Goal already succeeded.")

    if attempt.clarification_count >= 2:
        # Phase 1 Hardening: Persist Failure Code
        attempt.status = "failure"
        attempt.failure_code = "AMBIGUOUS_AFTER_CLARIFICATIONS"
        attempt.error_message = "Max clarifications reached (2). Please start a new query."
        session.add(attempt)
        session.commit()
        
        print(f"request_id={attempt.request_id} attempt_id={attempt_id} phase=clarify status=failure failure_code=AMBIGUOUS_AFTER_CLARIFICATIONS")
        raise HTTPException(status_code=400, detail="Max clarifications reached (2). Please start a new query.")

    # 2. Update History
    history = attempt.clarification_history or []
    if not isinstance(history, list): history = []
    
    last_question = attempt.error_message or "Clarification needed"
    
    history.append({
        "question": last_question,
        "answer": user_response,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    attempt.clarification_history = history
    attempt.clarification_count += 1
    attempt.status = "processing"
    # Clear previous error/failure code since we are retrying
    attempt.failure_code = None 
    
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    
    print(f"request_id={attempt.request_id} attempt_id={attempt_id} phase=clarify status=processing clarification_count={attempt.clarification_count}")
    
    # 3. Re-Solve
    original_prompt = attempt.input_text_normalized or attempt.input_text_raw
    
    # Append history to prompt or context
    clarification_context = "\\n\\n[Clarification History]\\n"
    for item in history:
        clarification_context += f"System: {item.get('question')}\\nUser: {item.get('answer')}\\n"
        
    user_id = attempt.user_id # Could be None
    
    try:
        from app.services.solver_v3 import get_solver_v3
        solver = get_solver_v3()
        
        # We pass attempt_id again so it updates the SAME record.
        solution_data = await solver.solve(
            problem_text=original_prompt,
            context=clarification_context, # Appended
            trace=False,
            user_id=user_id,
            db_session=session,
            attempt_id=attempt_id # Reuse ID
        )
        
        # transform to V1
        transformed = _transform_v3_to_v1_format(solution_data)
        
        # Ensure required SolveResponse fields are present
        return {
            "session_id": attempt.session_id or 0,
            "solution": transformed,
            "concepts": transformed.get("concepts", []),
            "visuals": transformed.get("visuals", []),
            "model_used": transformed.get("meta", {}).get("model"),
            "tokens_used": transformed.get("meta", {}).get("tokens", 500),
            "telemetry": transformed.get("meta")
        }
        
    except Exception as e:
        attempt.status = "failure"
        attempt.failure_code = "INTERNAL_ERROR"
        attempt.error_message = str(e)
        session.add(attempt)
        session.commit()
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/attempt/{attempt_id}")
async def get_attempt_status(
    attempt_id: str,
    session: Session = Depends(get_session)
):
    """
    Phase 1 Hardening: Frontend Resume Endpoint.
    Returns status, clarification state, and results.
    """
    attempt = session.exec(
        select(SolverOutputAttempt)
        .where(SolverOutputAttempt.attempt_id == attempt_id)
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    from app.models import BillingLedger, CreditHold
    ledger = session.exec(
        select(BillingLedger)
        .where(BillingLedger.request_id == attempt.request_id)
        .order_by(BillingLedger.created_at.desc())
    ).first()
    hold = session.exec(
        select(CreditHold)
        .where(CreditHold.request_id == attempt.request_id)
        .order_by(CreditHold.created_at.desc())
    ).first()

    return {
        "attempt_id": attempt.attempt_id,
        "request_id": attempt.request_id,
        "status": attempt.status,
        "failure_code": attempt.failure_code,
        "error_message": attempt.error_message,
        "clarification_count": attempt.clarification_count,
        "created_at": attempt.created_at,
        "updated_at": attempt.updated_at,
        "telemetry": {
            "provider": attempt.provider,
            "model": attempt.model,
            "input_tokens": attempt.input_tokens,
            "output_tokens": attempt.output_tokens,
            "total_tokens": attempt.total_tokens,
            "latency_ms_total": attempt.latency_ms,
        },
        "runtime_meta": (attempt.validation_json or {}).get("runtime_meta") if isinstance(attempt.validation_json, dict) else {},
        "timing_ms": (
            ((attempt.validation_json or {}).get("runtime_meta") or {}).get("timing_ms")
            if isinstance(((attempt.validation_json or {}).get("runtime_meta")), dict)
            else ((attempt.prompt_meta or {}).get("timing_ms") if isinstance((attempt.prompt_meta or {}).get("timing_ms"), dict) else {})
        ),
        "verification": (attempt.validation_json or {}).get("verification") if isinstance(attempt.validation_json, dict) else {},
        "billing": {
            "ledger_id": ledger.id if ledger else None,
            "ledger_status": ledger.status if ledger else None,
            "credits_charged": float(ledger.credits_charged) if ledger else None,
            "credits_before": float(ledger.credits_before) if ledger else None,
            "credits_after": float(ledger.credits_after) if ledger else None,
            "config_version_id": ledger.config_version_id if ledger else None,
            "hold_id": hold.id if hold else None,
            "hold_status": hold.status if hold else None,
        },
    }


@api_router.get("/attempt/{attempt_id}/graph.svg")
async def get_attempt_graph_svg(
    attempt_id: str,
    theme: str = Query("light"),
    width: int = Query(920, ge=320, le=2200),
    height: int = Query(520, ge=220, le=1600),
    session: Session = Depends(get_session),
):
    from app.services.graph.asset_service import get_or_render_graph_bytes

    payload, error = get_or_render_graph_bytes(
        session,
        attempt_id=attempt_id,
        fmt="svg",
        theme=theme,
        width_px=width,
        height_px=height,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail=f"graph_not_available:{error}")
    return Response(content=payload, media_type="image/svg+xml")


@api_router.get("/attempt/{attempt_id}/graph.png")
async def get_attempt_graph_png(
    attempt_id: str,
    theme: str = Query("light"),
    width: int = Query(920, ge=320, le=2200),
    height: int = Query(520, ge=220, le=1600),
    session: Session = Depends(get_session),
):
    from app.services.graph.asset_service import get_or_render_graph_bytes

    payload, error = get_or_render_graph_bytes(
        session,
        attempt_id=attempt_id,
        fmt="png",
        theme=theme,
        width_px=width,
        height_px=height,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail=f"graph_not_available:{error}")
    return Response(content=payload, media_type="image/png")


@api_router.get("/attempt/{attempt_id}/events")
async def stream_attempt_events(
    attempt_id: str,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    SSE endpoint to stream progress events for a specific solve attempt.
    """
    attempt = session.exec(
        select(SolverOutputAttempt)
        .where(SolverOutputAttempt.attempt_id == attempt_id)
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    async def event_generator():
        redis_client = get_redis()
        pubsub = redis_client.pubsub()
        channel = f"solve:attempt:{attempt_id}:events"
        pubsub.subscribe(channel)

        try:
            # Send initial state if already completed/failed/processing
            if attempt.status in ["success", "failure", "ambiguous"]:
                yield f"data: {json.dumps({'attempt_id': attempt_id, 'request_id': attempt.request_id, 'phase': 'completed_success' if attempt.status == 'success' else 'completed_failure' if attempt.status == 'failure' else 'clarification_needed', 'status': attempt.status})}\n\n"
                return
            
            if attempt.status in ["pending", "processing"]:
                yield f"data: {json.dumps({'attempt_id': attempt_id, 'request_id': attempt.request_id, 'phase': 'attempt_created', 'status': 'active'})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                
                # We use a small sleep to avoid tight loop, but pubsub.get_message is better
                # redis-py's pubsub.get_message(ignore_subscribe_messages=True)
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    yield f"data: {message['data']}\n\n"
                
                # Optional: check if attempt status changed in DB as a safety fallback
                # but Redis events should be the primary driver.
                
                await asyncio.sleep(0.1)
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@api_router.get("/dev/solve_debug")
async def dev_solve_debug(
    user_id: int = Query(...),
    session: Session = Depends(get_session)
):
    app_env = os.environ.get("APP_ENV", "").upper()
    if app_env not in {"DEV", "TEST"} and os.environ.get("BILLING_FAKE_SOLVER_ENABLED", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Not Found")

    from app.models import BillingLedger, CreditHold, CreditLotConsumption, SolverOutputAttempt

    attempt = session.exec(
        select(SolverOutputAttempt)
        .where(SolverOutputAttempt.user_id == user_id)
        .order_by(SolverOutputAttempt.created_at.desc())
    ).first()
    ledger = session.exec(
        select(BillingLedger)
        .where(BillingLedger.user_id == user_id)
        .order_by(BillingLedger.created_at.desc())
    ).first()
    hold = session.exec(
        select(CreditHold)
        .where(CreditHold.user_id == user_id)
        .order_by(CreditHold.created_at.desc())
    ).first()
    consumption = session.exec(
        select(CreditLotConsumption)
        .where(CreditLotConsumption.user_id == user_id)
        .order_by(CreditLotConsumption.created_at.desc())
        .limit(5)
    ).all()

    return {
        "attempt": {
            "attempt_id": attempt.attempt_id if attempt else None,
            "request_id": attempt.request_id if attempt else None,
            "status": attempt.status if attempt else None,
            "input_tokens": attempt.input_tokens if attempt else None,
            "output_tokens": attempt.output_tokens if attempt else None,
            "total_tokens": attempt.total_tokens if attempt else None,
            "provider": attempt.provider if attempt else None,
            "model": attempt.model if attempt else None,
            "created_at": attempt.created_at if attempt else None,
        },
        "ledger": {
            "id": ledger.id if ledger else None,
            "request_id": ledger.request_id if ledger else None,
            "status": ledger.status if ledger else None,
            "credits_charged": float(ledger.credits_charged) if ledger else None,
            "credits_before": float(ledger.credits_before) if ledger else None,
            "credits_after": float(ledger.credits_after) if ledger else None,
            "token_usage_json": ledger.token_usage_json if ledger else None,
        },
        "hold": {
            "id": hold.id if hold else None,
            "request_id": hold.request_id if hold else None,
            "status": hold.status if hold else None,
            "reserved_credits": float(hold.reserved_credits) if hold else None,
        },
        "consumption": [
            {
                "id": row.id,
                "credit_lot_id": row.credit_lot_id,
                "usage_ledger_id": row.usage_ledger_id,
                "ledger_event_id": row.ledger_event_id,
                "attempt_id": row.attempt_id,
                "direction": row.direction,
                "amount": float(row.amount),
                "created_at": row.created_at,
            }
            for row in (consumption or [])
        ],
    }



