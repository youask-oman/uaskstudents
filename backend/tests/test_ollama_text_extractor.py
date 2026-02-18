from app.services.solve.batch_tier_runtime import (
    _extract_boxed_answer,
    _extract_final_line_answer,
    _extract_ollama_text_payload,
)


def test_extract_boxed_answer_nested() -> None:
    text = r"steps ... \boxed{\left(\frac{5}{2}, \text{A}\right)}"
    assert _extract_boxed_answer(text) == r"\left(\frac{5}{2}, \text{A}\right)"


def test_extract_final_line_answer_prefers_final_phrase() -> None:
    text = "\n".join(
        [
            "Compute x from ...",
            "x = 7",
            "Therefore, final answer: 14 m",
        ]
    )
    assert _extract_final_line_answer(text) == "14 m"


def test_extract_payload_marks_refusal_when_no_answer() -> None:
    payload = _extract_ollama_text_payload(
        raw_text="Step 1: use formula. Step 2: compute.",
        questions=[{"question_id": "q1", "mode": "SOLVE", "question_text": "Find value"}],
        tier="FINAL",
        runtime_request_id="r1",
        runtime_attempt_id="a1",
        runtime_lang="English",
        runtime_allow_auto_split=False,
        max_questions_allowed=15,
        runtime_max_tasks_per_question=6,
    )
    item = payload["items"][0]
    assert item["refusal"]["is_refusal"] is True
    assert item["final_answer"]["answer_text"]


def test_extract_payload_short_has_single_step_block() -> None:
    payload = _extract_ollama_text_payload(
        raw_text=r"Therefore, \boxed{42}.",
        questions=[{"question_id": "q1", "mode": "SOLVE", "question_text": "Compute"}],
        tier="SHORT_STEPS",
        runtime_request_id="r1",
        runtime_attempt_id="a1",
        runtime_lang="English",
        runtime_allow_auto_split=False,
        max_questions_allowed=15,
        runtime_max_tasks_per_question=6,
    )
    item = payload["items"][0]
    assert item["refusal"]["is_refusal"] is False
    assert item["final_answer"]["answer_text"] == "42"
    assert isinstance(item["steps"], list) and len(item["steps"]) == 1
