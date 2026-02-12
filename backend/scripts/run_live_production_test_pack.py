from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests
from jsonschema import Draft202012Validator
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import engine
from app.models import JsonSchemaEntry


BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:9000")
USER_ID = int(os.getenv("LIVE_TEST_USER_ID", "166"))
ORCHESTRATOR_CONTAINER = os.getenv("ORCHESTRATOR_CONTAINER", "uask_orchestrator")
SCHEMA_ID = "solve_superset_v2.schema.json"

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "reports" / "evidence"


@dataclass
class LiveCase:
    index: int
    tier: str
    min_steps: int
    prompt: str


CASES: List[LiveCase] = [
    LiveCase(
        index=1,
        tier="standard",
        min_steps=6,
        prompt="Solve the equation $$x^2 - 5x + 6 = 0$$ and include a plot of $$y=x^2-5x+6$$ showing the x-intercepts.",
    ),
    LiveCase(
        index=2,
        tier="standard",
        min_steps=6,
        prompt="Find the intersection points of $$y=2x+1$$ and $$y=x^2$$. Include a plot of both curves and mark the intersection points.",
    ),
    LiveCase(
        index=3,
        tier="standard",
        min_steps=6,
        prompt="Let f(x) = (x^2 - 4)/(x - 2). Simplify the function, state the domain restriction, identify the hole coordinate, and include a plot.",
    ),
    LiveCase(
        index=4,
        tier="standard",
        min_steps=6,
        prompt="Given f(x)=x^3-3x+1, find all critical points, classify each as local max/min using derivative tests, and include a plot.",
    ),
    LiveCase(
        index=5,
        tier="research",
        min_steps=10,
        prompt="Let f(x)=x^5-5x+1. Determine the number of real roots using critical points, approximate all real roots to 4 decimals with Newton-style iterations, and include a plot showing roots and critical points.",
    ),
    LiveCase(
        index=6,
        tier="research",
        min_steps=10,
        prompt="Find intersections of the system x^2+y^2=4 and y=e^x-1, report intersection points to 4 decimals, and include a plot of both curves with intersections marked.",
    ),
]


def _load_schema_validator() -> Draft202012Validator:
    with Session(engine) as session:
        row = session.exec(
            select(JsonSchemaEntry)
            .where(JsonSchemaEntry.schema_id == SCHEMA_ID)
            .where(JsonSchemaEntry.is_active == True)
            .order_by(JsonSchemaEntry.version.desc(), JsonSchemaEntry.id.desc())
        ).first()
    if not row:
        raise RuntimeError(f"Schema not found in DB: {SCHEMA_ID}")
    content = row.content if isinstance(row.content, dict) else {}
    schema = content.get("schema") if isinstance(content.get("schema"), dict) else content
    if not isinstance(schema, dict):
        raise RuntimeError(f"Invalid schema content for {SCHEMA_ID}")
    return Draft202012Validator(schema)


def _docker_logs_since(since_iso_utc: str) -> str:
    # Keep a bounded tail to avoid huge payloads and codec crashes on Windows cp1252.
    cmd = ["docker", "logs", ORCHESTRATOR_CONTAINER, "--tail", "6000"]
    proc = subprocess.run(cmd, capture_output=True, text=False, check=False)
    merged = (proc.stdout or b"") + b"\n" + (proc.stderr or b"")
    decoded = merged.decode("utf-8", errors="ignore")
    # Try to retain only lines newer than since marker when possible (best-effort).
    _ = since_iso_utc
    merged = decoded
    return merged


def _request_with_retry(method: str, url: str, retries: int = 8, pause_sec: float = 1.5, **kwargs) -> requests.Response:
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            return requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(pause_sec)
    if last_exc:
        raise last_exc
    raise RuntimeError("request failed without explicit exception")


def _extract_request_logs(full_logs: str, request_id: str) -> List[str]:
    lines = [line for line in full_logs.splitlines() if request_id in line]
    return lines


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _assert_openai_proof(runtime_meta: Dict[str, Any], case_idx: int) -> None:
    if str(runtime_meta.get("provider") or "").lower() != "openai":
        raise AssertionError(f"case {case_idx}: provider is not openai")
    if not runtime_meta.get("model"):
        raise AssertionError(f"case {case_idx}: model missing")
    if int(runtime_meta.get("input_tokens") or 0) <= 0:
        raise AssertionError(f"case {case_idx}: input_tokens not positive")
    if int(runtime_meta.get("output_tokens") or 0) <= 0:
        raise AssertionError(f"case {case_idx}: output_tokens not positive")
    if int(runtime_meta.get("latency_ms_openai") or 0) <= 0:
        raise AssertionError(f"case {case_idx}: latency_ms_openai not positive")
    if not runtime_meta.get("request_id"):
        raise AssertionError(f"case {case_idx}: request_id missing in runtime_meta")


def _assert_sympy_proof(log_lines: List[str], case_idx: int) -> None:
    canonical_hit = any(
        ("solve_v3_stage_canonicalize" in line or "sympy_canonicalization" in line)
        and ("\"sympy_used\": true" in line or "\"sympy_used\":true" in line)
        for line in log_lines
    )
    verify_hit = any(
        ("solve_v3_stage_verify" in line or "sympy_verification_gate" in line or "verification_gate" in line)
        and ("\"sympy_used\": true" in line or "\"sympy_used\":true" in line)
        for line in log_lines
    )
    if not canonical_hit:
        raise AssertionError(f"case {case_idx}: missing canonicalization sympy proof in logs")
    if not verify_hit:
        raise AssertionError(f"case {case_idx}: missing verification sympy proof in logs")


def _assert_contract(response_json: Dict[str, Any], min_steps: int, case_idx: int, validator: Draft202012Validator) -> None:
    schema_payload = dict(response_json)
    for extra_key in [
        "request_id",
        "attempt_id",
        "verified",
        "verification_method",
        "assumptions_used",
        "dropped_candidates",
        "final_solutions",
        "timing_ms",
    ]:
        schema_payload.pop(extra_key, None)

    errors = list(validator.iter_errors(schema_payload))
    if errors:
        first = errors[0]
        raise AssertionError(f"case {case_idx}: schema invalid: {first.message}")

    steps = response_json.get("steps") if isinstance(response_json.get("steps"), list) else []
    if len(steps) < min_steps:
        raise AssertionError(f"case {case_idx}: steps below minimum ({len(steps)} < {min_steps})")

    visuals = response_json.get("visuals") if isinstance(response_json.get("visuals"), dict) else {}
    if visuals.get("should_visualize") is not True:
        raise AssertionError(f"case {case_idx}: visuals.should_visualize must be true")
    plots = visuals.get("plots") if isinstance(visuals.get("plots"), list) else []
    if not plots:
        raise AssertionError(f"case {case_idx}: plot payload missing")


def run_case(case: LiveCase, validator: Draft202012Validator) -> Dict[str, Any]:
    since = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "text_query": case.prompt,
        "requested_mode": "detailed",
        "graph_mode": "on",
        "tier": case.tier,
        "mode": "SOLVE",
        "trusted_context": {
            "domain_mode": "reals",
            "preferred_response_language": "English",
        },
        "idempotency_key": f"live-case-{case.index}-{int(time.time())}",
    }
    req_path = EVIDENCE_DIR / f"live_case_{case.index}_request.json"
    _write_json(req_path, body)

    resp = _request_with_retry(
        "POST",
        f"{BASE_URL}/api/v1/solve_v3",
        params={"user_id": USER_ID},
        json=body,
        timeout=300,
    )
    resp_payload: Dict[str, Any]
    try:
        resp_payload = resp.json()
    except Exception:
        resp_payload = {"raw": resp.text[:2000]}
    resp_path = EVIDENCE_DIR / f"live_case_{case.index}_response.json"
    _write_json(resp_path, resp_payload)

    if resp.status_code != 200:
        raise AssertionError(f"case {case.index}: non-200 response: {resp.status_code}")

    attempt_id = str(resp_payload.get("attempt_id") or "").strip()
    request_id = str(resp_payload.get("request_id") or "").strip()
    if not attempt_id or not request_id:
        raise AssertionError(f"case {case.index}: missing attempt_id/request_id in response")

    meta_resp = _request_with_retry(
        "GET",
        f"{BASE_URL}/api/v1/solve_v3_runtime_meta",
        params={"attempt_id": attempt_id},
        timeout=60,
    )
    try:
        runtime_meta = meta_resp.json()
    except Exception:
        runtime_meta = {"raw": meta_resp.text[:2000]}
    meta_path = EVIDENCE_DIR / f"live_case_{case.index}_runtime_meta.json"
    _write_json(meta_path, runtime_meta)
    if meta_resp.status_code != 200:
        raise AssertionError(f"case {case.index}: runtime_meta non-200: {meta_resp.status_code}")

    _assert_openai_proof(runtime_meta, case.index)
    _assert_contract(resp_payload, case.min_steps, case.index, validator)

    time.sleep(1.0)
    full_logs = _docker_logs_since(since)
    req_lines = _extract_request_logs(full_logs, request_id)
    if not req_lines:
        raise AssertionError(f"case {case.index}: no logs found for request_id={request_id}")
    _assert_sympy_proof(req_lines, case.index)
    log_path = EVIDENCE_DIR / f"live_case_{case.index}_logs.log"
    _write_text(log_path, "\n".join(req_lines) + "\n")

    return {
        "case": case.index,
        "attempt_id": attempt_id,
        "request_id": request_id,
        "steps": len(resp_payload.get("steps") or []),
        "verified": bool((resp_payload.get("verification") or {}).get("verified")),
        "verification_method": (resp_payload.get("verification") or {}).get("verification_method"),
        "provider": runtime_meta.get("provider"),
        "model": runtime_meta.get("model"),
        "input_tokens": runtime_meta.get("input_tokens"),
        "output_tokens": runtime_meta.get("output_tokens"),
        "latency_ms_openai": runtime_meta.get("latency_ms_openai"),
    }


def main() -> None:
    validator = _load_schema_validator()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    selected = os.getenv("LIVE_CASES", "").strip()
    if selected:
        wanted = {int(x.strip()) for x in selected.split(",") if x.strip().isdigit()}
        run_cases = [c for c in CASES if c.index in wanted]
    else:
        run_cases = CASES
    if not run_cases:
        raise RuntimeError("No cases selected. Set LIVE_CASES to comma-separated indices, e.g. LIVE_CASES=1,2")
    summary: List[Dict[str, Any]] = []
    for case in run_cases:
        summary.append(run_case(case, validator))

    out = EVIDENCE_DIR / "live_production_test_pack_summary.json"
    _write_json(out, {"base_url": BASE_URL, "user_id": USER_ID, "cases": summary, "ok": True})
    print(json.dumps({"ok": True, "cases": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
