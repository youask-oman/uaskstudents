import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


ENDPOINT = "http://localhost:8000/api/v1/solve_v3_stream"
PROBLEM_FREE = "√(x+3) = x − 3"
PROBLEM_RESEARCH = "Evaluate ∫(x^2 e^x) dx and simplify the result."
USER_ID = 1
MAX_TOTAL_MS = 120_000
FIRST_DELTA_BUDGET_MS = 2_000


@dataclass
class SmokeResult:
    tier: str
    problem: str
    request_id: Optional[str]
    selected_prompt_id: Optional[str]
    selected_prompt_name: Optional[str]
    first_delta_ms: Optional[float]
    total_ms: float
    attempt_count: Optional[int]
    validated: Optional[bool]
    validation_score: Optional[str]
    validation_failed_checks: List[str]
    contains_plotly_block: bool
    pass_first_delta: bool
    pass_attempt_count: bool
    pass_prompt_selection: bool
    pass_tier_shape: bool
    ok: bool
    error: Optional[str]


def run_case(tier: str, problem: str, expected_prompt_id: str) -> SmokeResult:
    payload = {
        "text_query": problem,
        "confirmed_text": problem,
        "subject": "Mathematics",
        "requested_mode": "minimal",
        "mode": "general",
        "tier": tier.lower(),
        "features_used": {"ocr_used": False, "voice_used": False},
        "input_modality": "text",
        "trusted_context": {"learning_mode": "solve"},
    }
    headers = {
        "Accept": "text/event-stream",
        "X-Request-ID": str(uuid.uuid4()),
    }

    started = time.perf_counter()
    request_id: Optional[str] = None
    selected_prompt_id: Optional[str] = None
    first_delta_ms: Optional[float] = None
    attempt_count: Optional[int] = None
    validated: Optional[bool] = None
    validation_score: Optional[str] = None
    validation_failed_checks: List[str] = []
    done_ok = False
    err: Optional[str] = None
    delta_text_parts: List[str] = []

    cur_event: Optional[str] = None
    cur_data: List[str] = []

    def handle_event(event_name: Optional[str], data_lines: List[str]) -> None:
        nonlocal request_id, selected_prompt_id, first_delta_ms, attempt_count, validated, validation_score
        nonlocal validation_failed_checks, done_ok, err
        if not event_name:
            return
        raw = "\n".join(data_lines).strip()
        if not raw:
            return
        try:
            obj: Any = json.loads(raw)
        except Exception:
            return

        if event_name == "meta" and isinstance(obj, dict):
            request_id = request_id or obj.get("request_id")
            selected_prompt_id = obj.get("developer_prompt_id")
        elif event_name == "delta" and isinstance(obj, dict):
            text = str(obj.get("text") or "")
            if text:
                delta_text_parts.append(text)
                if first_delta_ms is None:
                    first_delta_ms = (time.perf_counter() - started) * 1000.0
        elif event_name == "telemetry" and isinstance(obj, dict):
            telemetry = obj.get("telemetry") if isinstance(obj.get("telemetry"), dict) else obj
            if isinstance(telemetry, dict):
                request_id = request_id or telemetry.get("request_id")
                selected_prompt_id = selected_prompt_id or telemetry.get("prompt_id")
                attempt_count = telemetry.get("attempt_count")
                validated = telemetry.get("validated")
                validation_score = telemetry.get("validation_score")
                failed = telemetry.get("validation_failed_checks")
                if isinstance(failed, list):
                    validation_failed_checks = [str(item) for item in failed]
        elif event_name == "done" and isinstance(obj, dict):
            done_ok = bool(obj.get("ok"))
            if not done_ok:
                eobj = obj.get("error")
                if isinstance(eobj, dict):
                    err = str(eobj.get("message") or eobj.get("code") or "done_error")
                else:
                    err = "done_error"

    try:
        timeout = httpx.Timeout(connect=10.0, read=15.0, write=20.0, pool=10.0)
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", ENDPOINT, params={"user_id": USER_ID}, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                buf = b""
                for chunk in resp.iter_raw():
                    elapsed_ms = (time.perf_counter() - started) * 1000.0
                    if elapsed_ms > MAX_TOTAL_MS:
                        raise RuntimeError(f"total_ms_exceeded:{elapsed_ms:.1f}")
                    if not chunk:
                        continue
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.rstrip(b"\r")
                        if line.startswith(b"event:"):
                            cur_event = line[len(b"event:") :].decode("utf-8", "replace").strip()
                        elif line.startswith(b"data:"):
                            cur_data.append(line[len(b"data:") :].decode("utf-8", "replace").strip())
                        elif line == b"":
                            handle_event(cur_event, cur_data)
                            cur_event = None
                            cur_data = []
                            if done_ok:
                                break
                    if done_ok:
                        break
    except Exception as exc:
        err = str(exc)

    total_ms = (time.perf_counter() - started) * 1000.0
    full_text = "".join(delta_text_parts)
    contains_plotly_block = "```json" in full_text.lower()
    pass_first_delta = first_delta_ms is not None and first_delta_ms < FIRST_DELTA_BUDGET_MS
    pass_attempt_count = attempt_count == 1
    pass_prompt_selection = selected_prompt_id == expected_prompt_id
    if tier.upper() == "FREE":
        pass_tier_shape = not contains_plotly_block
    else:
        pass_tier_shape = contains_plotly_block

    return SmokeResult(
        tier=tier.upper(),
        problem=problem,
        request_id=request_id,
        selected_prompt_id=selected_prompt_id,
        selected_prompt_name=selected_prompt_id,
        first_delta_ms=first_delta_ms,
        total_ms=total_ms,
        attempt_count=attempt_count,
        validated=validated,
        validation_score=validation_score,
        validation_failed_checks=validation_failed_checks,
        contains_plotly_block=contains_plotly_block,
        pass_first_delta=pass_first_delta,
        pass_attempt_count=pass_attempt_count,
        pass_prompt_selection=pass_prompt_selection,
        pass_tier_shape=pass_tier_shape,
        ok=done_ok and pass_first_delta and pass_attempt_count and pass_prompt_selection and pass_tier_shape,
        error=err,
    )


def warm_up_model() -> None:
    payload = {
        "text_query": "Solve x + 1 = 2",
        "confirmed_text": "Solve x + 1 = 2",
        "subject": "Mathematics",
        "requested_mode": "minimal",
        "mode": "general",
        "tier": "free",
        "features_used": {"ocr_used": False, "voice_used": False},
        "input_modality": "text",
        "trusted_context": {"learning_mode": "solve"},
    }
    headers = {
        "Accept": "text/event-stream",
        "X-Request-ID": str(uuid.uuid4()),
    }
    timeout = httpx.Timeout(connect=10.0, read=15.0, write=20.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", ENDPOINT, params={"user_id": USER_ID}, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8", "replace") if isinstance(line, (bytes, bytearray)) else str(line)
                if text.startswith("event: done"):
                    break


def write_report(results: List[SmokeResult], output_path: Path) -> None:
    lines: List[str] = []
    lines.append("Prompt Selection Smoke Test")
    lines.append("===========================")
    lines.append("")
    lines.append(f"Endpoint: {ENDPOINT}")
    lines.append(f"User ID: {USER_ID}")
    lines.append(f"first_delta_budget_ms: {FIRST_DELTA_BUDGET_MS}")
    lines.append(f"max_total_ms: {MAX_TOTAL_MS}")
    lines.append("")
    lines.append(
        "request_id | tier | selected_prompt_id | selected_prompt_name | first_delta_ms | total_ms | attempt_count | validated | validation_score | validation_failed_checks | contains_plotly_block | pass_first_delta | pass_attempt_count | pass_prompt_selection | pass_tier_shape | ok | error"
    )
    for res in results:
        lines.append(
            " | ".join(
                [
                    res.request_id or "",
                    res.tier,
                    res.selected_prompt_id or "",
                    res.selected_prompt_name or "",
                    f"{res.first_delta_ms:.1f}" if res.first_delta_ms is not None else "",
                    f"{res.total_ms:.1f}",
                    str(res.attempt_count) if res.attempt_count is not None else "",
                    str(res.validated) if res.validated is not None else "",
                    res.validation_score or "",
                    ",".join(res.validation_failed_checks),
                    str(res.contains_plotly_block),
                    str(res.pass_first_delta),
                    str(res.pass_attempt_count),
                    str(res.pass_prompt_selection),
                    str(res.pass_tier_shape),
                    str(res.ok),
                    (res.error or "").replace("\n", " ")[:240],
                ]
            )
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    warm_up_model()
    results = [
        run_case("FREE", PROBLEM_FREE, "free_form_math_free_fast_v1"),
        run_case("RESEARCH", PROBLEM_RESEARCH, "free_form_math_research_rigorous_v1"),
    ]
    out_path = Path("prompt_selection_smoke_test.txt")
    write_report(results, out_path)
    print(f"Wrote {out_path}")
    if not all(r.ok for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
