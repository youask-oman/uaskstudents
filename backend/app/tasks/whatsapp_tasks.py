import os
import asyncio
import re
from typing import Optional

from sqlmodel import Session, create_engine

from app.worker import celery_app
from app.services.ocr import ocr_service
from app.services.whatsapp.whatsapp_state import (
    get_upload_meta,
    set_ocr_state,
    clear_ocr_state,
)
from app.services.whatsapp.whatsapp_send import send_whatsapp_message
from app.models import UsageLog, User
from app.services.solver import solver_service


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

@celery_app.task(
    name="whatsapp_ocr_extract",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=120,
    hard_time_limit=150,
)
def whatsapp_ocr_extract(self, upload_id: str, user_id: int, phone: str, message_id: Optional[str] = None):
    meta = get_upload_meta(upload_id)
    if not meta:
        send_whatsapp_message(phone, "I couldn't find that image. Please resend a clearer photo.")
        return "missing_upload"

    image_path = meta.get("path")
    if not image_path:
        send_whatsapp_message(phone, "I couldn't read that image. Please resend a clearer photo.")
        return "missing_path"

    try:
        result = ocr_service.process_job(image_path, engine_name="local")
        extracted = _clean_extracted_text(result.get("plain_text") or result.get("markdown") or "")
    except Exception as e:
        print(f"[WhatsApp OCR] Failed: {e}")
        send_whatsapp_message(phone, "I couldn't read that clearly. Please resend a sharper photo (crop to the question).")
        clear_ocr_state(phone)
        return "ocr_failed"

        if not extracted or len(extracted) < 3:
            send_whatsapp_message(phone, "I couldn't read that clearly. Please resend a sharper photo (crop to the question).")
            clear_ocr_state(phone)
            return "ocr_empty"

    set_ocr_state(
        phone,
        {
            "state": "OCR_PENDING_CONFIRMATION",
            "extracted_text": extracted,
            "upload_id": upload_id,
            "message_id": message_id,
            "user_id": user_id,
        },
    )

    confirmation_msg = (
        "I read:\n"
        f"{extracted}\n\n"
        "Reply:\n"
        "1 = Correct\n"
        "2 = Not correct (resend photo)\n"
        "EDIT: <corrected question>\n"
        "CANCEL"
    )
    send_whatsapp_message(phone, confirmation_msg)
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
def whatsapp_solve(self, user_id: int, phone: str, text: str, upload_id: Optional[str] = None, message_id: Optional[str] = None):
    if not text:
        send_whatsapp_message(phone, "I didn't receive any text to solve. Please try again.")
        return "no_text"

    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://uask_user:uask_password@localhost:5432/uask_db")
    engine = create_engine(DATABASE_URL)

    use_v3 = os.getenv("WHATSAPP_SOLVER_V3_ENABLED", "false").lower() == "true"

    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            send_whatsapp_message(phone, "I couldn't verify your account. Please try again.")
            return "no_user"

        if use_v3:
            from app.services.solver_v3 import get_solver_v3
            solver = get_solver_v3()
            try:
                v3_result = _run_async(
                    solver.solve(
                        problem_text=text,
                        user_id=user.id,
                        db_session=session,
                        requested_mode="minimal",
                    )
                )
            except Exception as e:
                print(f"[WhatsApp Solve V3] Failed: {e}")
                send_whatsapp_message(phone, "Sorry, I hit an error solving that. Please try again.")
                return "solve_v3_failed"

            steps = v3_result.get("steps", [])
            final = v3_result.get("final_answer", {})
            final_text = final.get("answer_text") or final.get("answer_latex") or ""

            reply = "📝 *Problem:* " + text + "\n\n"
            if steps:
                reply += "*Solution:*\n"
                for i, step in enumerate(steps, 1):
                    title = step.get("title") or f"Step {i}"
                    explanation = step.get("explanation") or ""
                    reply += f"\n*{i}. {title}*\n"
                    if explanation:
                        if len(explanation) > 200:
                            explanation = explanation[:197] + "..."
                        reply += explanation + "\n"
            if final_text:
                reply += f"\n✅ *Answer:* {final_text}"
            reply += "\n\n💡 _Need more help? Visit uask.ai_"

            session.add(UsageLog(user_id=user.id, action_type="whatsapp_solve_v3", tokens_used=len(text.split()) + len(reply.split())))
            session.commit()

            send_whatsapp_message(phone, reply)
            return "ok"

        # Legacy solver (current WhatsApp text behavior)
        try:
            result = _run_async(solver_service.solve_problem(text, "", session))
        except Exception as e:
            print(f"[WhatsApp Solve] Failed: {e}")
            send_whatsapp_message(phone, "Sorry, I encountered an error processing your problem. Please try again.")
            return "solve_failed"

        reply = "📝 *Problem:* " + text + "\n\n"
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
                    if len(explanation) > 200:
                        explanation = explanation[:197] + "..."
                    reply += explanation + "\n"

        if final_answer:
            reply += f"\n✅ *Answer:* {final_answer}"

        reply += "\n\n💡 _Need more help? Visit uask.ai_"

        session.add(UsageLog(user_id=user.id, action_type="whatsapp_solve", tokens_used=len(text.split()) + len(reply.split())))
        session.commit()

        send_whatsapp_message(phone, reply)
        return "ok"
