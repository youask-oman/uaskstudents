import argparse
import json
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

PROBLEM_A = "√(x+3) = x − 3"
PROBLEM_B = "Evaluate ∫(x^2 e^x) dx and simplify the result."


@dataclass
class RunRecord:
    phase: str
    problem_key: str
    problem_text: str
    run_kind: str
    run_index: int
    request_id: Optional[str]
    http_status: int
    ok: bool
    total_ms: float
    first_byte_ms: Optional[float]
    first_delta_ms: Optional[float]
    done_ms: Optional[float]
    delta_events_count: int
    attempt_count: Optional[int]
    timeout_hits: int
    validator_fail_reasons: List[str]
    final_validated: Optional[bool]
    last_stage: Optional[str]
    stop_trigger: Optional[str]
    error: Optional[str]
    input_hash_match: Optional[bool]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pct(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    values = sorted(values)
    k = (len(values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] * (c - k) + values[c] * (k - f)


def _run_cmd(command: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, text=True, capture_output=True)


def wait_healthy(timeout_s: int = 180) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            health = httpx.get("http://localhost:8000/health", timeout=2.0)
            ollama = httpx.get("http://localhost:8000/api/v1/health/ollama", timeout=2.0)
            if health.status_code == 200 and ollama.status_code == 200 and bool(ollama.json().get("reachable")):
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("services_not_ready")


def restart_for_cold_run() -> None:
    print("[perf] cold-run restart: ollama + backend", flush=True)
    _run_cmd(
        [
            "wsl.exe",
            "-d",
            "Ubuntu",
            "--",
            "bash",
            "-lc",
            "sudo service ollama restart || (pkill -f \"ollama serve\" || true; nohup ollama serve >/tmp/ollama.log 2>&1 &)",
        ],
        check=False,
    )
    _run_cmd(["docker", "compose", "restart", "orchestrator", "worker", "worker_whatsapp"], check=False)
    wait_healthy()


def _phase_matrix(phase: str) -> List[Tuple[str, str, int]]:
    if phase == "phase0_baseline":
        return [
            ("A", "cold", 1),
            ("A", "warm", 1),
            ("B", "cold", 1),
            ("B", "warm", 1),
        ]
    return [
        ("A", "warm", 1),
        ("B", "warm", 1),
    ]


def _filter_matrix(
    matrix: List[Tuple[str, str, int]],
    *,
    problem: str,
    run_kind: str,
) -> List[Tuple[str, str, int]]:
    problem_norm = (problem or "both").strip().upper()
    run_kind_norm = (run_kind or "both").strip().lower()
    filtered: List[Tuple[str, str, int]] = []
    for p, k, i in matrix:
        if problem_norm in {"A", "B"} and p != problem_norm:
            continue
        if run_kind_norm in {"cold", "warm"} and k != run_kind_norm:
            continue
        filtered.append((p, k, i))
    return filtered


def _phase_limits(phase: str) -> Dict[str, Any]:
    if phase == "phase0_baseline":
        return {"max_total_ms": 180_000}
    if phase == "phase1_streaming":
        return {
            "max_total_ms": 110_000,
            "max_first_delta_ms": 5_000,
            "max_no_delta_after_first_byte_ms": 10_000,
            "max_attempt_count": 1,
        }
    if phase == "phase2_retries":
        return {
            "max_total_ms": 90_000,
            "max_attempt_count": 1,
            "max_timeout_hits": 0,
        }
    if phase == "phase3_validator":
        return {
            "max_attempt_count": 1,
            "stop_on_cosmetic_rejection": True,
        }
    if phase == "post_fix_minimal":
        return {
            "max_total_ms": 60_000,
            "max_first_delta_ms": 5_000,
            "max_no_delta_after_first_byte_ms": 10_000,
            "max_attempt_count": 1,
            "max_timeout_hits": 0,
        }
    return {}


def run_single_solve(problem_text: str, user_id: int, limits: Dict[str, Any], timeout_s: int = 900) -> RunRecord:
    url = "http://localhost:8000/api/v1/solve_v3_stream"
    payload = {
        "text_query": problem_text,
        "confirmed_text": problem_text,
        "subject": "Mathematics",
        "requested_mode": "minimal",
        "mode": "general",
        "tier": "free",
        "features_used": {"ocr_used": False, "voice_used": False},
        "input_modality": "text",
        "trusted_context": {"learning_mode": "solve"},
    }

    start = time.perf_counter()
    first_byte_ms: Optional[float] = None
    first_delta_ms: Optional[float] = None
    done_ms: Optional[float] = None
    request_id: Optional[str] = None
    attempt_count: Optional[int] = None
    timeout_hits = 0
    validator_fail_reasons: List[str] = []
    final_validated: Optional[bool] = None
    last_stage: Optional[str] = None
    stop_trigger: Optional[str] = None
    ok = False
    err: Optional[str] = None
    delta_events_count = 0

    headers = {
        "Accept": "text/event-stream",
        "X-Request-ID": str(uuid.uuid4()),
    }

    cur_event: Optional[str] = None
    cur_data: List[str] = []

    def maybe_stop(reason: str) -> None:
        nonlocal stop_trigger
        if not stop_trigger:
            stop_trigger = reason
        raise RuntimeError(reason)

    def process_event(event_name: Optional[str], data_lines: List[str]) -> None:
        nonlocal request_id, first_delta_ms, done_ms, attempt_count, timeout_hits, validator_fail_reasons, final_validated, ok, err, delta_events_count, last_stage
        if not event_name:
            return
        raw = "\n".join(data_lines).strip()
        if not raw:
            return
        try:
            data_obj: Any = json.loads(raw)
        except Exception:
            data_obj = None

        if event_name == "meta" and isinstance(data_obj, dict) and not request_id:
            rid = data_obj.get("request_id")
            if isinstance(rid, str) and rid:
                request_id = rid

        if event_name == "stage" and isinstance(data_obj, dict):
            last_stage = str(data_obj.get("name") or "")

        if event_name == "delta" and isinstance(data_obj, dict):
            text = str(data_obj.get("text") or "")
            if text:
                delta_events_count += 1
                if first_delta_ms is None:
                    first_delta_ms = (time.perf_counter() - start) * 1000.0
                    max_fd = limits.get("max_first_delta_ms")
                    if isinstance(max_fd, (int, float)) and first_delta_ms > float(max_fd):
                        maybe_stop(f"first_delta_ms_exceeded:{first_delta_ms:.1f}")

        if event_name == "telemetry" and isinstance(data_obj, dict):
            telem = data_obj.get("telemetry") if isinstance(data_obj.get("telemetry"), dict) else data_obj
            if isinstance(telem, dict):
                if request_id is None and isinstance(telem.get("request_id"), str):
                    request_id = telem.get("request_id")
                if isinstance(telem.get("attempt_count"), int):
                    attempt_count = telem.get("attempt_count")
                if isinstance(telem.get("validated"), bool):
                    final_validated = telem.get("validated")
                if isinstance(telem.get("validation_failed_checks"), list):
                    validator_fail_reasons = [str(x) for x in telem.get("validation_failed_checks")]
                attempts = telem.get("attempts")
                if isinstance(attempts, list):
                    timeout_hits = sum(
                        1
                        for a in attempts
                        if isinstance(a, dict)
                        and (
                            "timeout" in str(a.get("error") or "").lower()
                            or "timed out" in str(a.get("error") or "").lower()
                        )
                    )

        if event_name == "done":
            done_ms = (time.perf_counter() - start) * 1000.0
            if isinstance(data_obj, dict):
                ok = bool(data_obj.get("ok"))
                if not ok:
                    err_obj = data_obj.get("error")
                    if isinstance(err_obj, dict):
                        err = str(err_obj.get("message") or err_obj.get("code") or "done_error")
                    else:
                        err = "done_error"

    status = 0
    try:
        timeout = httpx.Timeout(connect=10.0, read=12.0, write=20.0, pool=10.0)
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, params={"user_id": user_id}, headers=headers, json=payload) as resp:
                status = resp.status_code
                resp.raise_for_status()
                buf = b""
                for chunk in resp.iter_raw():
                    now_ms = (time.perf_counter() - start) * 1000.0
                    if first_byte_ms is None:
                        first_byte_ms = now_ms
                    max_total = limits.get("max_total_ms")
                    if isinstance(max_total, (int, float)) and now_ms > float(max_total):
                        maybe_stop(f"total_ms_exceeded:{now_ms:.1f}")
                    max_no_delta = limits.get("max_no_delta_after_first_byte_ms")
                    if (
                        first_byte_ms is not None
                        and first_delta_ms is None
                        and isinstance(max_no_delta, (int, float))
                        and (now_ms - first_byte_ms) > float(max_no_delta)
                    ):
                        maybe_stop(f"no_delta_within_ms:{max_no_delta}")

                    if not chunk:
                        continue
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.rstrip(b"\r")
                        if line.startswith(b"event:"):
                            cur_event = line[len(b"event:"):].decode("utf-8", "replace").strip()
                        elif line.startswith(b"data:"):
                            cur_data.append(line[len(b"data:"):].decode("utf-8", "replace").strip())
                        elif line == b"":
                            process_event(cur_event, cur_data)
                            cur_event = None
                            cur_data = []

                            max_attempt = limits.get("max_attempt_count")
                            if isinstance(max_attempt, int) and attempt_count is not None and attempt_count > max_attempt:
                                maybe_stop(f"attempt_count_exceeded:{attempt_count}")
                            max_timeout_hits = limits.get("max_timeout_hits")
                            if isinstance(max_timeout_hits, int) and timeout_hits > max_timeout_hits:
                                maybe_stop(f"timeout_hits_exceeded:{timeout_hits}")

                            if done_ms is not None:
                                break
                    if done_ms is not None:
                        break
    except Exception as exc:
        err = str(exc)

    total_ms = (time.perf_counter() - start) * 1000.0

    return RunRecord(
        phase="",
        problem_key="",
        problem_text=problem_text,
        run_kind="",
        run_index=0,
        request_id=request_id,
        http_status=status,
        ok=ok,
        total_ms=total_ms,
        first_byte_ms=first_byte_ms,
        first_delta_ms=first_delta_ms,
        done_ms=done_ms,
        delta_events_count=delta_events_count,
        attempt_count=attempt_count,
        timeout_hits=timeout_hits,
        validator_fail_reasons=validator_fail_reasons,
        final_validated=final_validated,
        last_stage=last_stage,
        stop_trigger=stop_trigger,
        error=err,
        input_hash_match=None,
    )


def _parse_perf_log_for_hash(log_path: Path, request_id: str) -> Optional[bool]:
    if not log_path.exists():
        return None
    selected_hash: Optional[str] = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if f"| {request_id} |" not in line:
            continue
        if "| solve_input_selected |" in line and "| hash=" in line:
            try:
                extra = line.split("|", 5)[-1].strip()
                parts = dict(part.split("=", 1) for part in extra.split("|") if "=" in part)
                selected_hash = parts.get("hash")
            except Exception:
                continue
    return bool(selected_hash)


def _is_cosmetic_only_failures(fails: List[str]) -> bool:
    if not fails:
        return False
    cosmetic = {
        "starts_with_step_1",
        "char_count_min_1800",
        "char_count_target_max_2500",
        "steps_min_12",
        "has_plotly_json_block",
        "has_domain_constraints",
        "has_verification_section",
        "verification_checks_min_3",
    }
    return all(f in cosmetic for f in fails)


def evaluate_stop_after_run(phase: str, rec: RunRecord) -> Optional[str]:
    if rec.stop_trigger:
        return rec.stop_trigger
    if phase == "phase0_baseline" and rec.total_ms > 180_000:
        return f"baseline_total_exceeded:{rec.total_ms:.1f}"
    if phase == "phase1_streaming":
        if rec.first_delta_ms is None:
            return "missing_first_delta"
        if rec.first_delta_ms > 5_000:
            return f"first_delta_ms_exceeded:{rec.first_delta_ms:.1f}"
        if rec.total_ms > 120_000:
            return f"total_ms_exceeded:{rec.total_ms:.1f}"
        if (rec.attempt_count or 1) > 1:
            return f"attempt_count_exceeded:{rec.attempt_count}"
    if phase == "phase2_retries":
        if (rec.attempt_count or 1) > 1:
            return f"attempt_count_exceeded:{rec.attempt_count}"
        if rec.timeout_hits > 0:
            return f"timeout_hits_exceeded:{rec.timeout_hits}"
        if rec.total_ms > 90_000:
            return f"total_ms_exceeded:{rec.total_ms:.1f}"
    if phase == "phase3_validator":
        if (rec.attempt_count or 1) > 1:
            return f"attempt_count_exceeded:{rec.attempt_count}"
        if rec.final_validated is False and _is_cosmetic_only_failures(rec.validator_fail_reasons):
            return "validator_cosmetic_rejection"
    if phase == "post_fix_minimal":
        if rec.first_delta_ms is None:
            return "missing_first_delta"
        if rec.first_delta_ms > 5_000:
            return f"first_delta_ms_exceeded:{rec.first_delta_ms:.1f}"
        if (rec.attempt_count or 1) > 1:
            return f"attempt_count_exceeded:{rec.attempt_count}"
        if rec.timeout_hits > 0:
            return f"timeout_hits_exceeded:{rec.timeout_hits}"
        if rec.total_ms > 60_000:
            return f"total_ms_exceeded:{rec.total_ms:.1f}"
    return None


def render_report(phase: str, records: List[RunRecord], output_path: Path, aborted_reason: Optional[str]) -> None:
    def fmt(vals: List[float]) -> str:
        if not vals:
            return "n/a"
        return f"avg={statistics.fmean(vals):.1f} p50={_pct(vals, 0.5):.1f} p95={_pct(vals, 0.95):.1f}"

    totals = [r.total_ms for r in records]
    first_bytes = [r.first_byte_ms for r in records if r.first_byte_ms is not None]
    first_deltas = [r.first_delta_ms for r in records if r.first_delta_ms is not None]

    lines: List[str] = []
    lines.append(f"{phase} Performance Report")
    lines.append("=" * len(lines[-1]))
    lines.append("")
    lines.append(f"Generated at: {_now_iso()}")
    lines.append("Endpoint: /api/v1/solve_v3_stream")
    lines.append("Problems: A=√(x+3)=x−3 ; B=Evaluate ∫(x^2 e^x) dx and simplify the result.")
    if aborted_reason:
        lines.append(f"Run aborted early: {aborted_reason}")
    lines.append("")
    lines.append("Overall (ms):")
    lines.append(f"- total_ms: {fmt(totals)}")
    lines.append(f"- first_byte_ms: {fmt(first_bytes)}")
    lines.append(f"- first_delta_ms: {fmt(first_deltas)}")
    lines.append("")

    lines.append("Per-run:")
    lines.append("problem | run_kind | idx | request_id | ok | total_ms | first_byte_ms | first_delta_ms | delta_events | done_ms | attempt_count | timeout_hits | validated | last_stage | stop_trigger | validator_fail_reasons | error")
    for r in records:
        lines.append(
            " | ".join(
                [
                    r.problem_key,
                    r.run_kind,
                    str(r.run_index),
                    r.request_id or "",
                    str(r.ok),
                    f"{r.total_ms:.1f}",
                    f"{r.first_byte_ms:.1f}" if r.first_byte_ms is not None else "",
                    f"{r.first_delta_ms:.1f}" if r.first_delta_ms is not None else "",
                    str(r.delta_events_count),
                    f"{r.done_ms:.1f}" if r.done_ms is not None else "",
                    str(r.attempt_count) if r.attempt_count is not None else "",
                    str(r.timeout_hits),
                    str(r.final_validated) if r.final_validated is not None else "",
                    r.last_stage or "",
                    r.stop_trigger or "",
                    ",".join(r.validator_fail_reasons),
                    (r.error or "").replace("\n", " ")[:240],
                ]
            )
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output_path.with_suffix(output_path.suffix + ".jsonl")).open("w", encoding="utf-8") as jf:
        for r in records:
            jf.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def run_phase(
    phase: str,
    output_path: Path,
    user_id: int,
    perf_log_path: Optional[Path],
    *,
    problem: str = "both",
    run_kind: str = "both",
) -> int:
    matrix = _filter_matrix(_phase_matrix(phase), problem=problem, run_kind=run_kind)
    if not matrix:
        raise RuntimeError("empty_run_matrix")
    limits = _phase_limits(phase)
    records: List[RunRecord] = []
    aborted_reason: Optional[str] = None

    for problem_key, run_kind, run_idx in matrix:
        text = PROBLEM_A if problem_key == "A" else PROBLEM_B
        if run_kind == "cold":
            restart_for_cold_run()
        print(f"[perf] {phase} {problem_key} {run_kind}#{run_idx} start", flush=True)
        rec = run_single_solve(text, user_id=user_id, limits=limits)
        rec.phase = phase
        rec.problem_key = problem_key
        rec.run_kind = run_kind
        rec.run_index = run_idx

        if phase == "phase5_input_integrity" and rec.request_id and perf_log_path:
            rec.input_hash_match = _parse_perf_log_for_hash(perf_log_path, rec.request_id)

        records.append(rec)
        print(
            f"[perf] {phase} {problem_key} {run_kind}#{run_idx} done total_ms={rec.total_ms:.1f} first_delta_ms={rec.first_delta_ms} attempts={rec.attempt_count} stop={rec.stop_trigger}",
            flush=True,
        )

        stop_reason = evaluate_stop_after_run(phase, rec)
        if stop_reason:
            aborted_reason = f"{stop_reason} request_id={rec.request_id} stage={rec.last_stage}"
            print(f"[perf] EARLY STOP: {aborted_reason}", flush=True)
            break

    render_report(phase, records, output_path, aborted_reason)

    if phase == "phase1_streaming" and not aborted_reason:
        warm = [r for r in records if r.run_kind == "warm"]
        for r in warm:
            if r.first_delta_ms is None or r.first_delta_ms >= 2000:
                print(f"[perf] phase1 pass criteria failed on request_id={r.request_id}", flush=True)
                return 2
            if r.delta_events_count <= 1:
                print(f"[perf] phase1 continuous delta failed on request_id={r.request_id}", flush=True)
                return 3

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded phase perf tests with early-stop")
    parser.add_argument("--phase", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--user-id", type=int, default=2)
    parser.add_argument("--perf-log-path", default="backend/backend/perf_profile.log")
    parser.add_argument("--problem", default="both", choices=["A", "B", "both"])
    parser.add_argument("--run-kind", default="both", choices=["cold", "warm", "both"])
    args = parser.parse_args()

    phase = args.phase.strip()
    output = Path(args.output)
    perf_log = Path(args.perf_log_path)

    try:
        wait_healthy()
        rc = run_phase(
            phase=phase,
            output_path=output,
            user_id=args.user_id,
            perf_log_path=perf_log,
            problem=args.problem,
            run_kind=args.run_kind,
        )
        print(f"Wrote {output}", flush=True)
        return rc
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
