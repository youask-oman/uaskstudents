from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from app.database import engine
from app.models import ChatMessage, ChatSession


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "ollama_short_live_diffeq_extracted_usercode_newparser_20260218.json"
    if not source_path.exists():
        raise FileNotFoundError(f"Missing source payload file: {source_path}")

    raw_source = json.loads(source_path.read_text(encoding="utf-8"))
    question_text = (
        "Differential equation with forcing + initial condition + long-run behavior\n"
        "A mass-spring-damper system satisfies:\n"
        "m x'' + c x' + k x = F0 cos(omega t),\n"
        "with m = 2, c = 6, k = 18, F0 = 10, and omega = 3. The system starts from rest at equilibrium:\n"
        "x(0) = 0, x'(0) = 0."
    )

    structured_data = {
        "mode": "short_source_test",
        "tier_requested": "SHORT_STEPS",
        "tier_effective": "SHORT_STEPS",
        "question": {"text": question_text},
        "problem": {"original_text": question_text},
        "raw_user_extraction": raw_source,
    }
    telemetry = {
        "tier": "SHORT_STEPS",
        "tier_requested": "SHORT_STEPS",
        "tier_effective": "SHORT_STEPS",
        "channel": "canvas_primary",
    }

    with Session(engine) as session:
        chat_session = ChatSession(
            user_id=None,
            title="Short Source Test Session",
            subject="Math",
            is_saved=True,
            solve_tier="short_steps",
        )
        session.add(chat_session)
        session.flush()

        user_msg = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=question_text,
        )
        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="Short source payload test",
            structured_data=structured_data,
            telemetry=telemetry,
            model_used="Qwen2.5-Math-7B-Instruct-Q4_K_M:latest",
            tokens_used=0,
        )
        session.add(user_msg)
        session.add(assistant_msg)
        session.commit()
        session.refresh(chat_session)

        session_id = int(chat_session.id)
        print(f"created_session_id={session_id}")
        print(f"chat_final_url=http://localhost:3000/chat_final/{session_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

