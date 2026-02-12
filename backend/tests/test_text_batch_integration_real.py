from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.models import User


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV)


SET_A: List[str] = [
    "Solve for x: sqrt(3x + 4) = 2",
    "Solve for x: x = 2*sqrt(x - 1)",
    "Solve for x: (5x - 2)^(1/3) = 2",
    "Simplify: (2x^3 y^2) / (4 x y)",
    "Factor completely: x^2 - 5x + 6",
    "Solve the system: { 2x + y = 7, x - y = 1 }",
    "Find the derivative: d/dx (x^3 * ln(x))",
]

SET_B: List[str] = [
    *SET_A,
    "Solve: |2x - 3| = 7",
    "Solve for x: ln(x - 2) = 1",
    "Solve the inequality: x^2 - 4x + 3 <= 0",
    "Compute: integral from 0 to 1 of 3x^2 dx",
]


def _questions(texts: List[str], start: int = 1) -> List[Dict[str, str]]:
    return [{"question_id": f"q{i}", "text": text} for i, text in enumerate(texts, start=start)]


def _extract_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return detail
    error = payload.get("error")
    if isinstance(error, dict):
        details = error.get("details")
        if isinstance(details, dict):
            return details
    return {}


def _summary(label: str, mode: str, count: int, status_code: int, payload: Dict[str, Any]) -> None:
    telemetry = payload.get("telemetry") if isinstance(payload.get("telemetry"), dict) else {}
    latency = telemetry.get("latency_ms")
    tokens = telemetry.get("tokens") if isinstance(telemetry.get("tokens"), dict) else {}
    token_total = tokens.get("total")
    error_code = None
    detail = _extract_detail(payload)
    if isinstance(detail.get("code"), str):
        error_code = detail.get("code")
    print(
        f"[batch-it] {label} mode={mode} count={count} status={status_code} "
        f"latency_ms={latency} tokens_total={token_total} error_code={error_code}"
    )


def _is_transient_provider_failure(status_code: int, payload: Dict[str, Any]) -> bool:
    if status_code not in {502, 504}:
        return False
    detail = _extract_detail(payload)
    code = str(detail.get("code") or payload.get("code") or "").upper()
    return code in {"PROVIDER_TIMEOUT", "TEXT_SOLVE_FAILED", "SCHEMA_INVALID"}


def _post_with_retry(
    client: TestClient,
    *,
    url: str,
    body: Dict[str, Any],
    label: str,
    mode: str,
    count: int,
    max_attempts: int = 3,
) -> Tuple[int, Dict[str, Any]]:
    last_status = 0
    last_payload: Dict[str, Any] = {}
    for attempt in range(1, max_attempts + 1):
        res = client.post(url, json=body)
        payload = res.json()
        _summary(f"{label}#attempt{attempt}", mode, count, res.status_code, payload)
        last_status = res.status_code
        last_payload = payload
        if not _is_transient_provider_failure(res.status_code, payload):
            return last_status, last_payload
    return last_status, last_payload


def _assert_question_id_mapping(sent: List[Dict[str, str]], payload: Dict[str, Any]) -> None:
    solutions = payload.get("solutions")
    assert isinstance(solutions, list)
    sent_ids = [q["question_id"] for q in sent]
    got_ids = [str((s or {}).get("question_id") or "") for s in solutions]
    assert got_ids == sent_ids


def _create_user(preferred_language: str) -> User:
    create_kwargs: Dict[str, Any] = {
        "email": f"batch_it_{preferred_language}_{os.urandom(6).hex()}@uask.local",
        "full_name": f"Batch IT {preferred_language}",
        "password_hash": "integration-test",
        "subscription_tier": "research",
        "subscription_status": "active",
    }
    if hasattr(User, "default_language"):
        create_kwargs["default_language"] = preferred_language
    else:
        create_kwargs["preferred_language"] = preferred_language

    with Session(engine) as db:
        user = User(**create_kwargs)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not configured for real integration")
def test_text_batch_endpoint_real_integration() -> None:
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)

    user_en = _create_user("en")
    user_fr = _create_user("fr")

    # 1) Free Minimal cap test
    free_a = _questions(SET_A)
    status_code, payload = _post_with_retry(
        client,
        url=f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        body={"requested_mode": "free_minimal", "tier": "FREE", "questions": free_a},
        label="free_set_a",
        mode="free_minimal",
        count=len(free_a),
    )
    assert status_code == 200
    assert payload.get("ok") is True
    assert len(payload.get("solutions") or []) == 7
    assert payload.get("response_language") == "en"
    _assert_question_id_mapping(free_a, payload)

    free_b = _questions(SET_B)
    res = client.post(
        f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        json={"requested_mode": "free_minimal", "tier": "FREE", "questions": free_b},
    )
    payload = res.json()
    _summary("free_set_b", "free_minimal", len(free_b), res.status_code, payload)
    assert res.status_code == 422
    detail = _extract_detail(payload)
    assert detail.get("code") == "TOO_MANY_QUESTIONS"
    assert detail.get("max_allowed") == 10
    assert detail.get("received") == 11

    # 2) FinalOnly cap + no-steps invariant
    final_a = _questions(SET_A)
    status_code, payload = _post_with_retry(
        client,
        url=f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        body={"requested_mode": "final_only", "tier": "FREE", "questions": final_a},
        label="final_set_a",
        mode="final_only",
        count=len(final_a),
    )
    assert status_code == 200
    solutions = payload.get("solutions") or []
    assert len(solutions) == 7
    for item in solutions:
        steps = (item or {}).get("steps")
        assert isinstance(steps, list)
        assert len(steps) == 0
    _assert_question_id_mapping(final_a, payload)

    final_b = _questions(SET_B)
    res = client.post(
        f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        json={"requested_mode": "final_only", "tier": "FREE", "questions": final_b},
    )
    payload = res.json()
    _summary("final_set_b", "final_only", len(final_b), res.status_code, payload)
    assert res.status_code == 422
    detail = _extract_detail(payload)
    assert detail.get("code") == "TOO_MANY_QUESTIONS"
    assert detail.get("max_allowed") == 10
    assert detail.get("received") == 11

    # 3) Standard Detailed cap test
    std_3 = _questions(SET_A[:3])
    status_code, payload = _post_with_retry(
        client,
        url=f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        body={"requested_mode": "standard_detailed", "tier": "STANDARD", "questions": std_3},
        label="standard_3",
        mode="standard_detailed",
        count=len(std_3),
    )
    assert status_code == 200
    assert len(payload.get("solutions") or []) == 3
    _assert_question_id_mapping(std_3, payload)

    std_4 = _questions(SET_A[:4])
    res = client.post(
        f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        json={"requested_mode": "standard_detailed", "tier": "STANDARD", "questions": std_4},
    )
    payload = res.json()
    _summary("standard_4", "standard_detailed", len(std_4), res.status_code, payload)
    assert res.status_code == 422
    detail = _extract_detail(payload)
    assert detail.get("code") == "TOO_MANY_QUESTIONS"
    assert detail.get("max_allowed") == 3
    assert detail.get("received") == 4

    # 4) Research Detailed single-only
    research_1 = _questions([SET_A[6]])
    status_code, payload = _post_with_retry(
        client,
        url=f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        body={"requested_mode": "research_detailed", "tier": "RESEARCH", "questions": research_1},
        label="research_1",
        mode="research_detailed",
        count=len(research_1),
    )
    assert status_code == 200
    assert len(payload.get("solutions") or []) == 1
    _assert_question_id_mapping(research_1, payload)

    research_2 = _questions([SET_A[0], SET_A[1]])
    res = client.post(
        f"/api/v1/math/solve_text_batch?user_id={user_en.id}",
        json={"requested_mode": "research_detailed", "tier": "RESEARCH", "questions": research_2},
    )
    payload = res.json()
    _summary("research_2", "research_detailed", len(research_2), res.status_code, payload)
    assert res.status_code == 422
    detail = _extract_detail(payload)
    assert detail.get("code") == "TOO_MANY_QUESTIONS"
    assert detail.get("max_allowed") == 1

    # 5 + 6) language propagation with non-English user
    lang_questions = _questions(["Resous en francais: derivee de x^3 * ln(x)"])
    status_code, payload = _post_with_retry(
        client,
        url=f"/api/v1/math/solve_text_batch?user_id={user_fr.id}",
        body={"requested_mode": "standard_detailed", "tier": "STANDARD", "questions": lang_questions},
        label="language_fr",
        mode="standard_detailed",
        count=len(lang_questions),
    )
    assert status_code == 200
    assert payload.get("response_language") == "fr"
    _assert_question_id_mapping(lang_questions, payload)

    solution = (payload.get("solutions") or [{}])[0]
    prose_fields: List[str] = []
    final_answer = solution.get("final_answer") if isinstance(solution.get("final_answer"), dict) else {}
    if isinstance(final_answer.get("answer_text"), str):
        prose_fields.append(final_answer.get("answer_text") or "")
    steps = solution.get("steps") if isinstance(solution.get("steps"), list) else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        for key in ("title", "explanation"):
            value = step.get(key)
            if isinstance(value, str):
                prose_fields.append(value)

    prose_blob = " ".join(prose_fields).lower()
    french_signal = re.search(r"\b(le|la|les|des|et|donc|solution|etape|derivee)\b", prose_blob)
    assert french_signal, f"Expected French prose signal, got: {prose_blob[:250]}"
