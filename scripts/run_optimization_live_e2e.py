from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests


API_BASE = os.environ.get("API_BASE", "http://localhost:9000").rstrip("/")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@uask.ai")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "admin1234")
INPUT_FILE = os.environ.get("OPTIMIZATION_FILE", "static_design/Optimization.txt")
OUTPUT_FILE = os.environ.get("OPTIMIZATION_REPORT", "reports/optimization_live_e2e_report.json")
ATTEMPT_POLL_TIMEOUT_SEC = int(os.environ.get("ATTEMPT_POLL_TIMEOUT_SEC", "900"))
ATTEMPT_POLL_INTERVAL_SEC = float(os.environ.get("ATTEMPT_POLL_INTERVAL_SEC", "2"))
MAX_RETRIES_PER_QUESTION = int(os.environ.get("MAX_RETRIES_PER_QUESTION", "3"))


TERMINAL_STATUSES = {"success", "failure", "ambiguous", "canceled", "timed_out"}


@dataclass
class LoginPayload:
    access_token: str
    user_id: int


def parse_questions(path: str) -> list[dict[str, Any]]:
    raw = open(path, "r", encoding="utf-8", errors="replace").read()
    starts = list(re.finditer(r"(?m)^Q(\d+)\)\s", raw))
    if not starts:
        raise RuntimeError(f"No questions found in {path}")
    out: list[dict[str, Any]] = []
    for i, m in enumerate(starts):
        q_num = int(m.group(1))
        start = m.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(raw)
        chunk = raw[start:end].strip()
        out.append({"question_number": q_num, "question_text": chunk})
    return out


def api_login() -> LoginPayload:
    resp = requests.post(
        f"{API_BASE}/api/v1/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    return LoginPayload(access_token=data["access_token"], user_id=int(data["user_id"]))


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_credits_balance(token: str) -> dict[str, Any]:
    resp = requests.get(
        f"{API_BASE}/api/v1/credits/balance",
        headers=auth_headers(token),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Credits balance failed ({resp.status_code}): {resp.text[:500]}")
    return resp.json()


def parse_sse_and_wait_done(
    token: str,
    user_id: int,
    question_text: str,
    idempotency_key: str,
) -> dict[str, Any]:
    body = {
        "question_text": question_text,
        "tier": "standard",
        "mode": "general",
        "requested_mode": "detailed",
        "graph_mode": "on",
        "trusted_context": {
            "preferred_response_language": "English",
            "domain_mode": "reals",
        },
        "idempotency_key": idempotency_key,
    }
    url = f"{API_BASE}/api/v1/solve_v3_stream_detached?user_id={user_id}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream", "Content-Type": "application/json"}
    attempt_id: str | None = None
    request_id: str | None = None
    last_seq: int | None = None
    done_payload: dict[str, Any] | None = None
    events_seen = 0

    with requests.post(url, json=body, headers=headers, stream=True, timeout=(30, ATTEMPT_POLL_TIMEOUT_SEC)) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"Solve stream failed ({resp.status_code}): {resp.text[:1200]}")

        event_type = "message"
        data_lines: list[str] = []
        event_id: str | None = None

        def flush_event() -> None:
            nonlocal event_type, data_lines, event_id, attempt_id, request_id, done_payload, events_seen, last_seq
            if not data_lines:
                event_type = "message"
                event_id = None
                return
            events_seen += 1
            raw_data = "\n".join(data_lines).strip()
            payload: dict[str, Any] = {}
            if raw_data:
                try:
                    payload = json.loads(raw_data)
                except Exception:
                    payload = {"raw": raw_data}
            if event_id is not None:
                try:
                    last_seq = int(event_id)
                except Exception:
                    pass
            if isinstance(payload, dict):
                if not attempt_id:
                    attempt_id = payload.get("attempt_id") or attempt_id
                if not request_id:
                    request_id = payload.get("request_id") or request_id
            if event_type == "done":
                done_payload = payload if isinstance(payload, dict) else {"raw": raw_data}
            event_type = "message"
            data_lines = []
            event_id = None

        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.rstrip("\r")
            if line == "":
                flush_event()
                if done_payload is not None:
                    break
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
                continue
            if line.startswith("id:"):
                event_id = line[len("id:") :].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
                continue

    return {
        "attempt_id": attempt_id,
        "request_id": request_id,
        "done_payload": done_payload,
        "events_seen": events_seen,
        "last_seq": last_seq,
    }


def wait_for_terminal_attempt(attempt_id: str, timeout_sec: int = ATTEMPT_POLL_TIMEOUT_SEC) -> dict[str, Any]:
    started = time.time()
    last: dict[str, Any] | None = None
    while time.time() - started < timeout_sec:
        resp = requests.get(f"{API_BASE}/api/v1/attempt/{attempt_id}", timeout=30)
        if resp.status_code == 404:
            raise RuntimeError(f"Attempt {attempt_id} not found (404)")
        if resp.status_code != 200:
            raise RuntimeError(f"Attempt poll failed ({resp.status_code}): {resp.text[:500]}")
        last = resp.json()
        st = str(last.get("status", "")).lower()
        if st in TERMINAL_STATUSES:
            return last
        time.sleep(ATTEMPT_POLL_INTERVAL_SEC)
    raise TimeoutError(f"Attempt {attempt_id} did not reach terminal in {timeout_sec}s; last={last}")


def verify_attempt_saved_in_db(attempt_id: str) -> dict[str, Any]:
    sql = (
        "SELECT attempt_id, status, session_id, message_id, created_at, updated_at "
        "FROM solveroutputattempt WHERE attempt_id = %s;"
    )
    cmd = [
        "docker",
        "exec",
        "uask_postgres",
        "psql",
        "-U",
        "uask_user",
        "-d",
        "uask_db",
        "-t",
        "-A",
        "-F",
        "|",
        "-c",
        sql.replace("%s", f"'{attempt_id}'"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"DB verify failed: {proc.stderr.strip() or proc.stdout.strip()}")
    row = proc.stdout.strip()
    if not row:
        raise RuntimeError(f"Attempt {attempt_id} missing in DB table solveroutputattempt")
    parts = row.split("|")
    return {
        "attempt_id": parts[0] if len(parts) > 0 else None,
        "status": parts[1] if len(parts) > 1 else None,
        "session_id": parts[2] if len(parts) > 2 else None,
        "message_id": parts[3] if len(parts) > 3 else None,
        "created_at": parts[4] if len(parts) > 4 else None,
        "updated_at": parts[5] if len(parts) > 5 else None,
    }


def run_one_question_once(token: str, user_id: int, q_num: int, question_text: str) -> dict[str, Any]:
    before = get_credits_balance(token)
    idem = f"opt-live-q{q_num}-{uuid.uuid4()}"
    stream = parse_sse_and_wait_done(token=token, user_id=user_id, question_text=question_text, idempotency_key=idem)
    attempt_id = stream.get("attempt_id")
    if not attempt_id:
        raise RuntimeError(f"Q{q_num}: stream did not provide attempt_id")
    attempt = wait_for_terminal_attempt(attempt_id)
    if str(attempt.get("status", "")).lower() != "success":
        raise RuntimeError(f"Q{q_num}: attempt terminal status is {attempt.get('status')} error={attempt.get('error_message')}")
    if not attempt.get("session_id") or not attempt.get("message_id"):
        raise RuntimeError(f"Q{q_num}: attempt success but missing session/message linkage")
    db_row = verify_attempt_saved_in_db(attempt_id)
    after = get_credits_balance(token)
    delta = float(before.get("available_credits", 0.0)) - float(after.get("available_credits", 0.0))
    return {
        "question_number": q_num,
        "attempt_id": attempt_id,
        "request_id": stream.get("request_id") or attempt.get("request_id"),
        "status": attempt.get("status"),
        "session_id": attempt.get("session_id"),
        "message_id": attempt.get("message_id"),
        "events_seen": stream.get("events_seen"),
        "last_seq": stream.get("last_seq"),
        "done_payload": stream.get("done_payload"),
        "billing": attempt.get("billing"),
        "credits_before": before,
        "credits_after": after,
        "available_credits_delta": delta,
        "db_row": db_row,
    }


def run_one_question(token: str, user_id: int, q_num: int, question_text: str) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt_no in range(1, MAX_RETRIES_PER_QUESTION + 1):
        try:
            row = run_one_question_once(token, user_id, q_num, question_text)
            row["retry_count"] = attempt_no - 1
            return row
        except Exception as exc:
            last_exc = exc
            print(f"Q{q_num}: attempt #{attempt_no} failed: {exc}")
            if attempt_no < MAX_RETRIES_PER_QUESTION:
                time.sleep(2.5)
                continue
            raise RuntimeError(f"Q{q_num}: failed after {MAX_RETRIES_PER_QUESTION} attempts: {last_exc}") from exc
    raise RuntimeError(f"Q{q_num}: unexpected retry loop termination: {last_exc}")


def main() -> None:
    questions = parse_questions(INPUT_FILE)
    login = api_login()
    results: list[dict[str, Any]] = []
    started = time.time()
    print(f"Running {len(questions)} live STANDARD solves for {EMAIL} on {API_BASE} ...")
    for q in questions:
        q_num = int(q["question_number"])
        q_text = str(q["question_text"])
        print(f"Q{q_num}: start")
        row = run_one_question(login.access_token, login.user_id, q_num, q_text)
        results.append(row)
        print(
            f"Q{q_num}: success "
            f"attempt={row['attempt_id']} session={row['session_id']} "
            f"delta={row['available_credits_delta']:.4f}"
        )

    report = {
        "ok": True,
        "api_base": API_BASE,
        "email": EMAIL,
        "user_id": login.user_id,
        "questions_run": len(results),
        "elapsed_sec": round(time.time() - started, 3),
        "results": results,
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
