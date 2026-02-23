from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Tuple

from app.schemas.render_events import RenderEvent, RenderProfile
from app.plot.python_codegen import generate_python_code_from_recipe


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _seed_to_rng(seed: str) -> random.Random:
    digest = hashlib.sha256((seed or "").encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big", signed=False))


def _default_profile(seed: str) -> RenderProfile:
    return RenderProfile(seed=seed)


def _extract_items(solution_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [x for x in _as_list(solution_json.get("items")) if isinstance(x, dict)]
    if items:
        return items
    # Backward compatibility for older payload shape.
    legacy = [x for x in _as_list(solution_json.get("solutions")) if isinstance(x, dict)]
    return legacy


def _extract_question_text(solution_json: Dict[str, Any], item: Dict[str, Any]) -> str:
    question = _as_dict(solution_json.get("question"))
    if _as_text(question.get("text")).strip():
        return _as_text(question.get("text")).strip()
    if _as_text(item.get("question_summary")).strip():
        return _as_text(item.get("question_summary")).strip()
    problem = _as_dict(item.get("problem"))
    if _as_text(problem.get("normalized_text")).strip():
        return _as_text(problem.get("normalized_text")).strip()
    if _as_text(problem.get("original_text")).strip():
        return _as_text(problem.get("original_text")).strip()
    if _as_text(item.get("question_text")).strip():
        return _as_text(item.get("question_text")).strip()
    qid = _as_text(item.get("question_id")).strip() or "q1"
    return f"Question {qid}"


def _extract_steps(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps = [x for x in _as_list(item.get("steps")) if isinstance(x, dict)]
    if steps:
        return steps
    # Legacy short format.
    legacy_steps = []
    for idx, raw in enumerate(_as_list(item.get("steps")), start=1):
        if not isinstance(raw, dict):
            continue
        legacy_steps.append(
            {
                "index": raw.get("index", idx),
                "title": raw.get("title") or f"Step {idx}",
                "blocks": [
                    {"kind": "text", "content": _as_text(raw.get("explanation"))},
                    {"kind": "math", "content": _as_text(raw.get("math_latex")), "display": True},
                ],
            }
        )
    return legacy_steps


def _extract_blocks(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = [x for x in _as_list(step.get("blocks")) if isinstance(x, dict)]
    if blocks:
        return blocks
    # Backward compatibility for step.explanation/math_latex.
    out: List[Dict[str, Any]] = []
    explanation = _as_text(step.get("explanation")).strip()
    if explanation:
        out.append({"kind": "text", "content": explanation})
    math_latex = step.get("math_latex")
    if isinstance(math_latex, list):
        for raw in math_latex:
            text = _as_text(raw).strip()
            if text:
                out.append({"kind": "math", "content": text, "display": True})
    else:
        text = _as_text(math_latex).strip()
        if text:
            out.append({"kind": "math", "content": text, "display": True})
    return out


def _text_chunks(text: str, chunk_size: int) -> List[str]:
    source = text or ""
    if not source:
        return []
    chunks: List[str] = []
    cursor = 0
    while cursor < len(source):
        chunks.append(source[cursor : cursor + chunk_size])
        cursor += chunk_size
    return chunks


def build_render_events(
    solution_json: Dict[str, Any],
    *,
    profile: RenderProfile | None = None,
    seed: str,
) -> Tuple[List[RenderEvent], RenderProfile]:
    used_profile = profile or _default_profile(seed)
    rng = _seed_to_rng(seed)
    items = _extract_items(solution_json)

    events: List[RenderEvent] = []
    t_ms = 0
    event_index = 0

    def emit(event_type: str, payload: Dict[str, Any]) -> None:
        nonlocal event_index
        event_index += 1
        events.append(
            RenderEvent(
                id=f"evt_{event_index:05d}",
                at_ms=max(0, int(t_ms)),
                type=event_type,  # type: ignore[arg-type]
                payload=payload,
            )
        )

    emit("MESSAGE_START", {"items_count": len(items)})
    attempt_id = _as_text(solution_json.get("attempt_id")).strip()

    for item_index, item in enumerate(items, start=1):
        question_id = _as_text(item.get("question_id")).strip() or f"q{item_index}"
        question_text = _extract_question_text(solution_json, item)
        emit(
            "QUESTION_SET",
            {
                "item_index": item_index,
                "question_id": question_id,
                "text": question_text,
            },
        )

        for step_index, step in enumerate(_extract_steps(item), start=1):
            step_title = _as_text(step.get("title")).strip() or f"Step {step_index}"
            emit(
                "STEP_START",
                {
                    "item_index": item_index,
                    "question_id": question_id,
                    "step_index": step_index,
                    "title": step_title,
                },
            )

            for block_index, block in enumerate(_extract_blocks(step), start=1):
                kind = _as_text(block.get("kind")).strip().lower() or "text"
                content = _as_text(block.get("content"))
                block_id = f"{question_id}_s{step_index}_b{block_index}"
                if kind == "math":
                    t_ms += int(used_profile.math_drop_delay_ms)
                    emit(
                        "BLOCK_SET_MATH",
                        {
                            "item_index": item_index,
                            "question_id": question_id,
                            "step_index": step_index,
                            "block_id": block_id,
                            "latex": content,
                            "display": bool(block.get("display")),
                        },
                    )
                    continue

                for chunk in _text_chunks(content, int(used_profile.chunk_size_chars)):
                    emit(
                        "BLOCK_APPEND_TEXT",
                        {
                            "item_index": item_index,
                            "question_id": question_id,
                            "step_index": step_index,
                            "block_id": block_id,
                            "chunk": chunk,
                        },
                    )
                    base = max(1, int(round((len(chunk) / max(1, used_profile.text_cps)) * 1000)))
                    jitter = rng.randint(0, int(used_profile.jitter_ms))
                    t_ms += base + jitter

            emit(
                "STEP_END",
                {
                    "item_index": item_index,
                    "question_id": question_id,
                    "step_index": step_index,
                },
            )
            t_ms += int(used_profile.step_pause_ms)

        final_answer = _as_dict(item.get("final_answer"))
        final_payload = {
            "item_index": item_index,
            "question_id": question_id,
            "answer_text": _as_text(final_answer.get("answer_text")),
            "answer_latex": _as_text(final_answer.get("answer_latex")),
            "values": _as_list(final_answer.get("values")),
        }
        emit("FINAL_ANSWER_SET", final_payload)

        plot = _as_dict(item.get("plot"))
        if bool(plot.get("should_visualize")) and isinstance(plot.get("recipe"), dict):
            t_ms += int(used_profile.plot_delay_ms)
            emit(
                "PLOT_SET",
                {
                    "item_index": item_index,
                    "question_id": question_id,
                    "attempt_id": attempt_id or None,
                    "recipe": _as_dict(plot.get("recipe")),
                    "notes": _as_text(plot.get("notes")),
                },
            )

        python_code = _as_text(plot.get("python_code")).strip()
        if not python_code and bool(plot.get("should_visualize")) and isinstance(plot.get("recipe"), dict):
            try:
                python_code = generate_python_code_from_recipe(_as_dict(plot.get("recipe")))
            except Exception:
                python_code = ""
        if python_code:
            t_ms += int(used_profile.code_delay_ms)
            emit(
                "PYTHON_CODE_SET",
                {
                    "item_index": item_index,
                    "question_id": question_id,
                    "code": python_code,
                    "language": "python",
                },
            )

    emit("MESSAGE_END", {"items_count": len(items)})
    return events, used_profile
