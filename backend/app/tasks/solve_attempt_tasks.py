from __future__ import annotations

import logging
import os
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import Session, select

from app.database import engine
from app.models import ChatMessage, ChatSession, CreditHold, SolverOutputAttempt, User
from app.services.attempt_event_service import append_attempt_event
from app.services.billing_feature_flags import is_billing_v2_enabled
from app.services.billing_ledger_service_v2 import billing_ledger_service_v2
from app.services.solve.batch_tier_runtime import BatchSolveError, execute_batch_solve
from app.services.solve.single_task_parser import parse_single_question_tasks
from app.worker import celery_app

logger = logging.getLogger(__name__)

SOLVE_ATTEMPT_TASK_NAME = "solve_attempt_async"
_WORKER_EVENT_LOOP: asyncio.AbstractEventLoop | None = None


def _run_in_worker_loop(coro):
    """
    Reuse a persistent event loop in the Celery worker process.
    Avoid asyncio.run(...) per task because it closes the loop and can break
    async clients that keep loop-bound transports across calls.
    """
    global _WORKER_EVENT_LOOP
    if _WORKER_EVENT_LOOP is None or _WORKER_EVENT_LOOP.is_closed():
        _WORKER_EVENT_LOOP = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(_WORKER_EVENT_LOOP)
    except Exception:
        pass
    return _WORKER_EVENT_LOOP.run_until_complete(coro)


def _is_terminal(status: str) -> bool:
    return str(status or "").lower() in {"success", "failure", "ambiguous", "canceled", "timed_out"}


def _tier_internal(raw: str) -> str:
    token = str(raw or "").strip().lower()
    if token in {"short_steps", "free", "three_step", "short"}:
        return "SHORT_STEPS"
    if token in {"final", "final_only"}:
        return "FINAL"
    if token in {"standard", "detailed"}:
        return "STANDARD"
    if token == "research":
        return "RESEARCH"
    return "SHORT_STEPS"


@celery_app.task(name=SOLVE_ATTEMPT_TASK_NAME, bind=True, soft_time_limit=1200, time_limit=1500)
def solve_attempt_async(self, attempt_id: str) -> bool:
    lock_key = f"solve:attempt:{attempt_id}:lock"
    lock = None
    started_perf = time.perf_counter()
    with Session(engine) as session:
        attempt = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
        if attempt is None:
            logger.warning("solve_attempt_async missing attempt_id=%s", attempt_id)
            return False
        if _is_terminal(attempt.status):
            return True

        try:
            redis = __import__("app.services.whatsapp.whatsapp_state", fromlist=["get_redis"]).get_redis()
            lock = redis.lock(lock_key, timeout=1800, blocking=False)
            if not lock.acquire(blocking=False):
                logger.info("solve_attempt_async skip attempt_id=%s reason=already_running", attempt_id)
                return False
        except Exception:
            lock = None

        request_id = attempt.request_id
        payload = (attempt.prompt_meta or {}).get("request_payload") if isinstance(attempt.prompt_meta, dict) else {}
        payload = payload if isinstance(payload, dict) else {}
        trusted_context = payload.get("trusted_context") if isinstance(payload.get("trusted_context"), dict) else {}
        question_text = (
            payload.get("question_text")
            or payload.get("confirmed_text")
            or payload.get("confirmed_markdown")
            or payload.get("text_query")
            or payload.get("original_input_text")
            or attempt.input_text_raw
            or ""
        )
        if not str(question_text).strip():
            attempt.status = "failure"
            attempt.failure_code = "no_input"
            attempt.error_message = "No input provided"
            attempt.error_json = {"code": "no_input", "message": "No input provided"}
            attempt.finished_at = datetime.utcnow()
            attempt.updated_at = datetime.utcnow()
            session.add(attempt)
            session.commit()
            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="done",
                payload={"ok": False, "error": {"code": "no_input", "message": "No input provided", "request_id": request_id}},
                session=session,
            )
            return False

        try:
            attempt.status = "running"
            attempt.started_at = datetime.utcnow()
            attempt.updated_at = datetime.utcnow()
            session.add(attempt)
            session.commit()

            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="stage",
                payload={"name": "Calling AI Core"},
                session=session,
            )

            # Respect explicit cancel request before provider call.
            session.refresh(attempt)
            if attempt.cancel_requested_at is not None:
                attempt.status = "canceled"
                attempt.failure_code = "cancel_requested"
                attempt.error_message = "Attempt canceled by user."
                attempt.finished_at = datetime.utcnow()
                attempt.updated_at = datetime.utcnow()
                session.add(attempt)
                session.commit()
                if is_billing_v2_enabled(int(attempt.user_id or 0)):
                    try:
                        billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                        session.commit()
                    except Exception:
                        session.rollback()
                append_attempt_event(
                    attempt_id=attempt_id,
                    request_id=request_id,
                    event_type="done",
                    payload={"ok": False, "error": {"code": "canceled", "message": "Canceled by user", "request_id": request_id}},
                    session=session,
                )
                return True

            domain_mode = str(payload.get("domain_mode") or trusted_context.get("domain_mode") or "reals")
            graph_mode = str(payload.get("graph_mode") or "auto")
            preferred_lang = str(trusted_context.get("preferred_response_language") or "English")
            tier = _tier_internal(str(payload.get("tier") or "standard"))
            max_output_tokens = 20000 if tier == "STANDARD" else None

            task_parse = parse_single_question_tasks(str(question_text), max_tasks=15)
            tasks = task_parse.get("tasks") if isinstance(task_parse.get("tasks"), list) else []

            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="stage",
                payload={"name": "Executing Solver"},
                session=session,
            )

            solve_payload, solve_telemetry = _run_in_worker_loop(
                execute_batch_solve(
                    session=session,
                    tier=tier,
                    request_id=request_id,
                    attempt_id=attempt_id,
                    mode="SOLVE",
                    graph_mode=graph_mode,
                    domain_mode=domain_mode,
                    preferred_response_language=preferred_lang,
                    questions_json=[
                        {
                            "question_id": "q1",
                            "question_text": str(question_text),
                            "mode": "SOLVE",
                            "graph_mode": graph_mode,
                            "domain_mode": domain_mode,
                            "tasks": tasks,
                        }
                    ],
                    user_id=attempt.user_id,
                    trusted_context=trusted_context,
                    max_output_tokens=max_output_tokens,
                    allow_auto_split=False,
                    max_tasks_per_question=15,
                )
            )

            user = session.get(User, int(attempt.user_id or 0))
            chat = ChatSession(
                user_id=attempt.user_id,
                title=(str(question_text).strip()[:80] or "New Solve"),
                subject=str(payload.get("subject") or "General"),
                is_saved=False,
                learning_mode=str(trusted_context.get("learning_mode") or "solve"),
                requested_mode=str(payload.get("requested_mode") or "detailed"),
                solve_tier=(str(payload.get("tier") or "standard").strip().lower() or "standard"),
            )
            session.add(chat)
            session.commit()
            session.refresh(chat)

            user_msg = ChatMessage(session_id=chat.id, role="user", content=str(question_text))
            assistant_msg = ChatMessage(
                session_id=chat.id,
                role="assistant",
                content="",
                structured_data=solve_payload if isinstance(solve_payload, dict) else {},
                telemetry=solve_telemetry if isinstance(solve_telemetry, dict) else {},
                model_used=str((solve_telemetry or {}).get("model") or os.environ.get("OPENAI_MODEL_DEFAULT") or ""),
                tokens_used=int((solve_telemetry or {}).get("total_tokens") or 0),
            )
            session.add(user_msg)
            session.add(assistant_msg)
            session.commit()
            session.refresh(assistant_msg)

            elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
            attempt.status = "success"
            attempt.finished_at = datetime.utcnow()
            attempt.updated_at = datetime.utcnow()
            attempt.session_id = chat.id
            attempt.message_id = assistant_msg.id
            attempt.result_json = solve_payload if isinstance(solve_payload, dict) else {}
            attempt.provider_meta = {
                "telemetry": solve_telemetry if isinstance(solve_telemetry, dict) else {},
                "latency_ms_total": elapsed_ms,
            }
            attempt.input_tokens = int((solve_telemetry or {}).get("input_tokens") or 0)
            attempt.output_tokens = int((solve_telemetry or {}).get("output_tokens") or 0)
            attempt.total_tokens = int((solve_telemetry or {}).get("total_tokens") or 0)
            attempt.latency_ms = elapsed_ms
            session.add(attempt)
            session.commit()

            if is_billing_v2_enabled(int(attempt.user_id or 0)):
                try:
                    hold = session.exec(
                        select(CreditHold).where(CreditHold.request_id == request_id).order_by(CreditHold.created_at.desc())
                    ).first()
                    estimated = hold.reserved_credits if hold is not None else 0
                    billing_ledger_service_v2.settle_hold(
                        session=session,
                        request_id=request_id,
                        actual_credits=estimated,
                        tier=str(payload.get("tier") or "STANDARD").upper(),
                        provider_cost_usd=0,
                        attempt_id=attempt_id,
                        is_billable=True,
                    )
                    session.commit()
                except Exception:
                    session.rollback()

            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="telemetry",
                payload={"telemetry": solve_telemetry if isinstance(solve_telemetry, dict) else {}},
                session=session,
            )
            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="done",
                payload={"ok": True, "session_id": int(chat.id), "message_id": int(assistant_msg.id or 0)},
                session=session,
            )
            return True
        except BatchSolveError as exc:
            session.rollback()
            attempt = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
            if attempt is not None:
                attempt.status = "failure"
                attempt.failure_code = exc.code
                attempt.error_message = str(exc)
                attempt.error_json = {"code": exc.code, "message": str(exc), "details": exc.details}
                attempt.finished_at = datetime.utcnow()
                attempt.updated_at = datetime.utcnow()
                session.add(attempt)
                session.commit()
            if is_billing_v2_enabled(int((attempt.user_id if attempt else 0) or 0)):
                try:
                    billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                    session.commit()
                except Exception:
                    session.rollback()
            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="done",
                payload={"ok": False, "error": {"code": exc.code, "message": str(exc), "request_id": request_id}},
                session=session,
            )
            return False
        except Exception as exc:
            session.rollback()
            attempt = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
            if attempt is not None:
                attempt.status = "failure"
                attempt.failure_code = "internal_error"
                attempt.error_message = str(exc)
                attempt.error_json = {"code": "internal_error", "message": str(exc)}
                attempt.finished_at = datetime.utcnow()
                attempt.updated_at = datetime.utcnow()
                session.add(attempt)
                session.commit()
            if is_billing_v2_enabled(int((attempt.user_id if attempt else 0) or 0)):
                try:
                    billing_ledger_service_v2.release_hold(session, request_id=request_id, attempt_id=attempt_id)
                    session.commit()
                except Exception:
                    session.rollback()
            append_attempt_event(
                attempt_id=attempt_id,
                request_id=request_id,
                event_type="done",
                payload={
                    "ok": False,
                    "error": {"code": "internal_error", "message": str(exc), "request_id": request_id},
                },
                session=session,
            )
            return False
        finally:
            if lock is not None:
                try:
                    lock.release()
                except Exception:
                    pass


@celery_app.task(name="reap_stuck_attempts")
def reap_stuck_attempts() -> int:
    now = datetime.utcnow()
    reaped = 0
    with Session(engine) as session:
        stale = session.exec(
            select(SolverOutputAttempt)
            .where(SolverOutputAttempt.status.in_(["running", "pending"]))
            .where(SolverOutputAttempt.ttl_deadline_at.is_not(None))
            .where(SolverOutputAttempt.ttl_deadline_at < now)
        ).all()
        for attempt in stale:
            attempt.status = "timed_out"
            attempt.failure_code = "ttl_expired"
            attempt.error_message = "Attempt exceeded execution deadline."
            attempt.finished_at = now
            attempt.updated_at = now
            session.add(attempt)
            if is_billing_v2_enabled(int(attempt.user_id or 0)):
                try:
                    billing_ledger_service_v2.release_hold(
                        session=session,
                        request_id=attempt.request_id,
                        attempt_id=attempt.attempt_id,
                    )
                except Exception:
                    session.rollback()
            append_attempt_event(
                attempt_id=attempt.attempt_id,
                request_id=attempt.request_id,
                event_type="done",
                payload={
                    "ok": False,
                    "error": {
                        "code": "timed_out",
                        "message": "Attempt timed out.",
                        "request_id": attempt.request_id,
                    },
                },
                session=session,
            )
            reaped += 1
        session.commit()
    return reaped
