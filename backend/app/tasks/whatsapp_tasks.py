import os
import asyncio
import re
import logging
import uuid
from typing import Optional

from sqlmodel import Session, create_engine

from app.worker import celery_app
from app.services.whatsapp.whatsapp_state import (
    get_upload_meta,
    clear_ocr_state,
    set_step_pack,
)
from app.services.whatsapp.whatsapp_send import send_whatsapp_message, send_whatsapp_logo
from app.services.whatsapp.step_delivery import build_step_pack, send_step_pack
from app.models import UsageLog, User, ChatSession, ChatMessage
from app.services.whatsapp.ingress_security import increment_metric
from app.services.glmocr_direct import parse_image_with_ollama_generate
from app.services.solve_text_pipeline import SolveTextPipelineError, solve_text_questions
from app.services.subscription_service import subscription_service

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)

def _clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r", "").strip()
    if cleaned.startswith("$$") and cleaned.endswith("$$") and len(cleaned) > 4:
        cleaned = cleaned[2:-2].strip()
    cleaned = cleaned.replace("\\n", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > 800:
        cleaned = cleaned[:797] + "..."
    return cleaned

def _save_whatsapp_history(session: Session, user: User, problem_text: str, answer_text: str) -> None:
    try:
        chat = ChatSession(
            user_id=user.id,
            title="WhatsApp Solve",
            subject="Math",
            is_saved=True,
            learning_mode="solve",
            requested_mode="minimal",
            solve_tier="final",
        )
        session.add(chat)
        session.flush()
        session.add(ChatMessage(session_id=chat.id, role="user", content=problem_text))
        session.add(ChatMessage(
            session_id=chat.id,
            role="assistant",
            content=answer_text,
            structured_data={"channel": "whatsapp"},
        ))
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[WhatsApp] Failed to save history: {e}")


def _format_steps_for_history(steps, final_text: str = "") -> str:
    lines = ["Solution:"]
    for i, step in enumerate(steps, 1):
        title = step.get("title") or f"Step {i}"
        explanation = step.get("explanation") or ""
        lines.append(f"{i}. {title}")
        if explanation:
            lines.append(explanation)
    if final_text:
        lines.append(f"Answer: {final_text}")
    return "\n".join(lines)


def _has_meaningful_steps(steps: list) -> bool:
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        title = str(step.get("title") or "").strip()
        explanation = str(step.get("explanation") or "").strip()
        math = step.get("math")
        if title or explanation:
            return True
        if isinstance(math, dict) and any(str(v).strip() for v in math.values() if v is not None):
            return True
    return False


def _normalize_whatsapp_tier(raw: Optional[str]) -> str:
    token = str(raw or "").strip().lower()
    if token in {"final", "final_only"}:
        return "final"
    return "short_steps"


def _resolve_whatsapp_tier(user: User) -> str:
    env_tier = os.getenv("WHATSAPP_SOLVE_TIER", "").strip()
    if env_tier:
        return _normalize_whatsapp_tier(env_tier)
    return _normalize_whatsapp_tier(getattr(user, "subscription_tier", "short_steps"))


def _log_whatsapp_billing_event(event: str, **fields) -> None:
    payload = " ".join(f"{k}={fields[k]}" for k in sorted(fields.keys()))
    logger.info("wa_billing_%s %s", event, payload)


def _deduct_whatsapp_final_shot_credits(
    session: Session,
    *,
    user: User,
    requested_tier: str,
    requested_mode: str,
    source_type: str,
    reference_id: str,
):
    tier_key = _normalize_whatsapp_tier(requested_tier)
    mode_key = "minimal" if str(requested_mode or "").strip().lower() == "minimal" else "detailed"
    _log_whatsapp_billing_event(
        "debit_attempt",
        user_id=user.id,
        reference_id=reference_id,
        tier=tier_key,
        mode=mode_key,
        source_type=source_type,
    )
    entitlement = subscription_service.check_entitlement_and_debit(
        session,
        user.id,
        {
            "tier": tier_key,
            "mode": mode_key,
            "source_type": source_type,
            "has_ocr": source_type in {"snap_image", "snap_pdf"},
            "has_voice": False,
            "reference_id": reference_id,
        },
    )
    if not entitlement.get("allowed"):
        reason = str(entitlement.get("reason") or "Action not allowed")
        error_code = str(entitlement.get("error_code") or "")
        _log_whatsapp_billing_event(
            "debit_denied",
            user_id=user.id,
            reference_id=reference_id,
            tier=tier_key,
            mode=mode_key,
            source_type=source_type,
            error_code=error_code or "UNKNOWN",
            reason=reason,
        )
        if error_code == "INSUFFICIENT_CREDITS":
            return False, None, 0.0, "Insufficient credits. Please top up or use the app."
        if error_code == "CAP_EXCEEDED":
            return False, None, 0.0, "Daily WhatsApp limit reached. Please try again later."
        return False, None, 0.0, reason

    cost = float(entitlement.get("cost") or 0.0)
    subscription = entitlement.get("subscription")
    meta = dict(entitlement.get("meta") or {})
    meta.update(
        {
            "channel": "whatsapp",
            "requested_tier": tier_key,
            "requested_mode": mode_key,
            "source_type": source_type,
            "has_ocr": source_type in {"snap_image", "snap_pdf"},
        }
    )
    subscription_service.execute_debit(session, subscription, cost, meta, reference_id)
    session.commit()
    _log_whatsapp_billing_event(
        "debit_success",
        user_id=user.id,
        subscription_id=getattr(subscription, "id", None),
        reference_id=reference_id,
        amount=cost,
        tier=tier_key,
        mode=mode_key,
        source_type=source_type,
    )
    return True, subscription, cost, ""

@celery_app.task(
    name="whatsapp_ocr_extract",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=120,
    hard_time_limit=150,
)
def whatsapp_ocr_extract(
    self,
    upload_id: str,
    user_id: int,
    phone: str,
    message_id: Optional[str] = None,
    request_id: Optional[str] = None,
):
    logger.info(
        "wa_worker_ocr_start request_id=%s user_id=%s phone=%s upload_id=%s message_id=%s",
        request_id,
        user_id,
        phone,
        upload_id,
        message_id,
    )
    meta = get_upload_meta(upload_id)
    if not meta:
        send_whatsapp_message(phone, "I couldn't find that image. Please resend a clearer photo.")
        increment_metric("worker_failure")
        return "missing_upload"

    image_path = meta.get("path")
    if not image_path:
        send_whatsapp_message(phone, "I couldn't read that image. Please resend a clearer photo.")
        increment_metric("worker_failure")
        return "missing_path"

    try:
        with open(image_path, "rb") as fh:
            image_bytes = fh.read()
        parsed = _run_async(
            parse_image_with_ollama_generate(
                image_bytes,
                request_id=request_id or str(uuid.uuid4()),
                mime_type=str(meta.get("mime_type") or "image/png"),
                filename=os.path.basename(image_path),
            )
        )
        extracted = _clean_extracted_text(
            str(parsed.get("markdown_result") or "")
            or str((parsed.get("json_result") or {}).get("raw_text") or "")
        )
    except Exception as e:
        logger.exception("wa_worker_ocr_failed request_id=%s error=%s", request_id, str(e))
        send_whatsapp_message(phone, "I couldn't read that clearly. Please resend a sharper photo (crop to the question).")
        clear_ocr_state(phone)
        increment_metric("worker_failure")
        return "ocr_failed"

    if not extracted or len(extracted) < 3:
        send_whatsapp_message(phone, "I couldn't read that clearly. Please resend a sharper photo (crop to the question).")
        clear_ocr_state(phone)
        increment_metric("worker_failure")
        return "ocr_empty"

    try:
        celery_app.send_task(
            "whatsapp_solve",
            args=[user_id, phone, extracted, upload_id, message_id, request_id],
            queue="whatsapp",
        )
    except Exception as exc:
        logger.exception("wa_worker_enqueue_after_ocr_failed request_id=%s error=%s", request_id, str(exc))
        send_whatsapp_message(phone, "I read your image but couldn't queue the solve. Please try again.")
        increment_metric("worker_failure")
        return "enqueue_failed"

    send_whatsapp_message(phone, "Image extracted. Solving now...")
    increment_metric("worker_success")
    return "ok"


@celery_app.task(
    name="whatsapp_solve",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=180,
    hard_time_limit=240,
)
def whatsapp_solve(
    self,
    user_id: int,
    phone: str,
    text: str,
    upload_id: Optional[str] = None,
    message_id: Optional[str] = None,
    request_id: Optional[str] = None,
):
    logger.info(
        "wa_worker_solve_start request_id=%s user_id=%s phone=%s upload_id=%s message_id=%s",
        request_id,
        user_id,
        phone,
        upload_id,
        message_id,
    )
    if not text:
        send_whatsapp_message(phone, "I didn't receive any text to solve. Please try again.")
        increment_metric("worker_failure")
        return "no_text"

    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(DATABASE_URL)

    use_latex = os.getenv("WHATSAPP_LATEX_RENDER_ENABLED", "false").lower() == "true"
    deliver_steps = os.getenv("WHATSAPP_DELIVER_STEPS", "false").lower() == "true"

    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            send_whatsapp_message(phone, "I couldn't verify your account. Please try again.")
            increment_metric("worker_failure")
            return "no_user"
        effective_tier = _resolve_whatsapp_tier(user)
        pipeline_mode = "final_only" if effective_tier == "final" else "free_minimal"
        solver_tier = "FINAL" if effective_tier == "final" else "SHORT_STEPS"
        source_type = "snap_image" if upload_id else "text"
        reference_id = request_id or f"wa:{user.id}:{message_id or uuid.uuid4()}"
        allowed, subscription, charged_cost, deny_message = _deduct_whatsapp_final_shot_credits(
            session,
            user=user,
            requested_tier=effective_tier,
            requested_mode="minimal",
            source_type=source_type,
            reference_id=reference_id,
        )
        if not allowed:
            send_whatsapp_message(phone, deny_message or "Unable to process your request right now.")
            increment_metric("worker_failure")
            return "billing_denied"

        try:
            batch_result = _run_async(
                solve_text_questions(
                    session=session,
                    user_id=user.id,
                    requested_mode=pipeline_mode,
                    tier=solver_tier,
                    questions=[{"question_id": request_id or str(uuid.uuid4()), "text": text}],
                )
            )
        except SolveTextPipelineError as e:
            logger.exception("wa_worker_solve_pipeline_failed request_id=%s error=%s", request_id, str(e))
            if subscription and charged_cost > 0:
                try:
                    subscription_service.refund_credits(
                        session,
                        subscription.id,
                        charged_cost,
                        "WhatsApp short-tier solve failed",
                        reference_id,
                    )
                    session.commit()
                    _log_whatsapp_billing_event(
                        "refund_success",
                        user_id=user.id,
                        subscription_id=getattr(subscription, "id", None),
                        reference_id=reference_id,
                        amount=charged_cost,
                        reason="solve_pipeline_failed",
                    )
                except Exception:
                    session.rollback()
                    _log_whatsapp_billing_event(
                        "refund_failed",
                        user_id=user.id,
                        subscription_id=getattr(subscription, "id", None),
                        reference_id=reference_id,
                        amount=charged_cost,
                        reason="solve_pipeline_failed",
                    )
            send_whatsapp_message(phone, "Sorry, I hit an error solving that. Please try again.")
            increment_metric("worker_failure")
            return "solve_pipeline_failed"
        except Exception as e:
            logger.exception("wa_worker_solve_failed request_id=%s error=%s", request_id, str(e))
            if subscription and charged_cost > 0:
                try:
                    subscription_service.refund_credits(
                        session,
                        subscription.id,
                        charged_cost,
                        "WhatsApp short-tier solve failed",
                        reference_id,
                    )
                    session.commit()
                    _log_whatsapp_billing_event(
                        "refund_success",
                        user_id=user.id,
                        subscription_id=getattr(subscription, "id", None),
                        reference_id=reference_id,
                        amount=charged_cost,
                        reason="solve_failed",
                    )
                except Exception:
                    session.rollback()
                    _log_whatsapp_billing_event(
                        "refund_failed",
                        user_id=user.id,
                        subscription_id=getattr(subscription, "id", None),
                        reference_id=reference_id,
                        amount=charged_cost,
                        reason="solve_failed",
                    )
            send_whatsapp_message(phone, "Sorry, I encountered an error processing your problem. Please try again.")
            increment_metric("worker_failure")
            return "solve_failed"

        first_solution = ((batch_result.get("solutions") or [{}])[0]) if isinstance(batch_result, dict) else {}
        if not isinstance(first_solution, dict):
            first_solution = {}
        final_obj = first_solution.get("final_answer")
        if isinstance(final_obj, dict):
            final_answer = str(final_obj.get("answer_text") or final_obj.get("answer_latex") or "").strip()
        else:
            final_answer = str(final_obj or "").strip()
        steps = first_solution.get("steps") if isinstance(first_solution.get("steps"), list) else []

        # Tier-based delivery:
        # - final: final-answer-only
        # - short_steps: optional step navigation pack
        if effective_tier == "short_steps" and deliver_steps and use_latex and _has_meaningful_steps(steps):
            normalized_steps = []
            for i, step in enumerate(steps, 1):
                math = step.get("math") or {}
                math_latex = step.get("math_latex")
                if math_latex and not math:
                    math = {"latex_lines": [math_latex]}
                normalized_steps.append({
                    "title": step.get("title") or f"Step {i}",
                    "explanation": step.get("explanation") or "",
                    "math": math,
                })
            if final_answer:
                normalized_steps.append({
                    "title": "Final Answer",
                    "explanation": final_answer,
                    "math": {},
                })

            pack = build_step_pack(phone, normalized_steps)
            set_step_pack(phone, pack)
            send_step_pack(phone, pack, 1)
            send_whatsapp_message(phone, "Reply NEXT/PREV/ALL or a step number to navigate.")
            history_text = _format_steps_for_history(steps, final_answer)
            _save_whatsapp_history(session, user, text, history_text)
            session.add(UsageLog(user_id=user.id, action_type="whatsapp_solve_short_steps", tokens_used=len(text.split())))
            session.commit()
            increment_metric("worker_success")
            return "ok"

        reply = "*Final Answer:*\n"
        if final_answer:
            reply += final_answer
        elif steps:
            fallback_bits = []
            for step in steps[:2]:
                explanation = str(step.get("explanation") or "").strip()
                if explanation:
                    fallback_bits.append(explanation[:240])
            reply += ("\n\n".join(fallback_bits) if fallback_bits else "I couldn't generate a stable final answer. Please resend the question.")
        else:
            reply += "I couldn't generate a stable final answer. Please resend the question."

        reply += "\n\n_Need more help? Visit uask.ai_"

        action_type = "whatsapp_solve_final" if effective_tier == "final" else "whatsapp_solve_short_steps"
        session.add(UsageLog(user_id=user.id, action_type=action_type, tokens_used=len(text.split()) + len(reply.split())))
        session.commit()

        send_brand_image = os.getenv("WHATSAPP_SEND_BRAND_IMAGE", "false").lower() == "true"
        if send_brand_image:
            send_whatsapp_logo(phone)
        send_whatsapp_message(phone, reply)
        _save_whatsapp_history(session, user, text, reply)
        increment_metric("worker_success")
        return "ok"
