import json
import os
import time
import uuid

import pytest
import requests


def _truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@pytest.mark.integration
def test_solve_stream_perf_sanity_live():
    """
    Lightweight live sanity check (opt-in):
    - first delta arrives quickly
    - attempt_count defaults to 1
    - no timeout retry loop
    """
    if not _truthy("RUN_PERF_SANITY"):
        pytest.skip("Set RUN_PERF_SANITY=1 to run live perf sanity check")

    base_url = os.getenv("PERF_SANITY_BASE_URL", "http://localhost:8000").rstrip("/")
    user_id = int(os.getenv("PERF_SANITY_USER_ID", "2"))
    first_delta_budget_ms = float(os.getenv("PERF_SANITY_FIRST_DELTA_BUDGET_MS", "5000"))
    total_budget_ms = float(os.getenv("PERF_SANITY_TOTAL_BUDGET_MS", "90000"))
    connect_timeout_s = float(os.getenv("PERF_SANITY_CONNECT_TIMEOUT_S", "10"))
    read_timeout_s = float(os.getenv("PERF_SANITY_READ_TIMEOUT_S", "20"))

    url = f"{base_url}/api/v1/solve_v3_stream"
    payload = {
        "text_query": "2x + 3 = 11",
        "confirmed_text": "2x + 3 = 11",
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

    started = time.perf_counter()
    first_delta_ms = None
    attempt_count = None
    timeout_hits = 0
    done_seen = False

    event_name = None
    data_lines = []

    def handle_event(name: str, data: str) -> None:
        nonlocal first_delta_ms, attempt_count, timeout_hits, done_seen
        if not data:
            return
        try:
            obj = json.loads(data)
        except Exception:
            return

        if name == "delta":
            text = str(obj.get("text") or "")
            if text and first_delta_ms is None:
                first_delta_ms = (time.perf_counter() - started) * 1000.0

        if name == "telemetry":
            telem = obj.get("telemetry") if isinstance(obj.get("telemetry"), dict) else obj
            if isinstance(telem, dict):
                val = telem.get("attempt_count")
                if isinstance(val, int):
                    attempt_count = val
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

        if name == "done":
            done_seen = bool(obj.get("ok"))

    with requests.post(
        url,
        params={"user_id": user_id},
        json=payload,
        headers=headers,
        stream=True,
        timeout=(connect_timeout_s, read_timeout_s),
    ) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines(decode_unicode=True):
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if elapsed_ms > total_budget_ms:
                break
            if raw_line is None:
                continue
            line = raw_line.strip("\r")
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
            elif line == "":
                handle_event(event_name, "\n".join(data_lines).strip())
                event_name = None
                data_lines = []
                if done_seen:
                    break

    total_ms = (time.perf_counter() - started) * 1000.0
    assert done_seen, "solve stream did not finish successfully"
    assert first_delta_ms is not None, "no delta was emitted"
    assert first_delta_ms <= first_delta_budget_ms, f"first_delta_ms={first_delta_ms:.1f} exceeded budget={first_delta_budget_ms:.1f}"
    assert attempt_count == 1, f"expected attempt_count=1, got {attempt_count}"
    assert timeout_hits == 0, f"expected timeout_hits=0, got {timeout_hits}"
    assert total_ms <= total_budget_ms, f"total_ms={total_ms:.1f} exceeded budget={total_budget_ms:.1f}"
