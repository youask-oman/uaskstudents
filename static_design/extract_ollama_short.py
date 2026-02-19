#!/usr/bin/env python3
"""
Extract all Ollama "----- RESPONSE RAW TEXT -----" JSON blobs from a QA log file
and export them into ONE normalized JSON file.

Supports BOTH Ollama shapes:
- /api/chat non-stream: {"message": {"role": "...", "content": "..."}, ...}
- /api/generate non-stream: {"response": "...", ...}

If a field is missing, it is emitted as null.
If a response block is missing or unparseable, it is still emitted with nulls + parse_error.

Usage:
  python extract_ollama_raw_responses.py --input INPUT.txt --output OUTPUT.json --self-test 20
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RE_Q_HEADER = re.compile(r"^===== QUESTION (\d+) \(Item (\d+)\) =====\s*$")
MARK_REQUEST = "----- REQUEST JSON -----"
MARK_RESPONSE = "----- RESPONSE RAW TEXT -----"


def _parse_json_object_from_lines(lines: List[str], start_index: int) -> Tuple[Optional[dict], int, Optional[str], Optional[str]]:
    """
    Robustly parse a JSON object that may span multiple lines.
    Returns: (obj, end_index, raw_json_text, error)
    """
    buf = ""
    depth = 0
    in_str = False
    esc = False
    started = False

    i = start_index
    while i < len(lines):
        if buf:
            buf += "\n"
        buf += lines[i]

        for ch in lines[i]:
            if not started:
                if ch == "{":
                    started = True
                    depth = 1
                    in_str = False
                    esc = False
                continue

            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1

        if started and depth == 0:
            # Trim anything after the last closing brace.
            last_brace = buf.rfind("}")
            candidate = buf[: last_brace + 1]
            # Also trim anything before first '{' (rare but happens in messy logs).
            first_brace = candidate.find("{")
            if first_brace > 0:
                candidate = candidate[first_brace:]

            try:
                return json.loads(candidate), i, candidate, None
            except Exception as e:
                return None, i, candidate, f"json_decode_error: {e}"

        i += 1

    return None, start_index, None, "json_incomplete_or_missing"


def _extract_header_kv(lines: List[str]) -> Dict[str, Any]:
    """Parse simple key=value lines at the top of the file until first QUESTION header."""
    meta: Dict[str, Any] = {}
    for line in lines:
        if RE_Q_HEADER.match(line):
            break
        if "=" in line and not line.strip().startswith("====="):
            k, v = line.split("=", 1)
            meta[k.strip()] = v.strip()
    return meta


def extract_log(input_path: Path) -> Dict[str, Any]:
    """
    Extract ALL questions + request/response blobs from the log.
    Normalizes the response shape so every item has the same response keys (nulls for missing).
    """
    raw_text = input_path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()

    meta = _extract_header_kv(lines)

    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    question_block_lines: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        m = RE_Q_HEADER.match(line)
        if m:
            # flush previous
            if current is not None:
                current["question_block_text"] = "\n".join(question_block_lines).strip() or None
                records.append(current)

            current = {
                "question_number": int(m.group(1)),
                "item_number": int(m.group(2)),
                "question_block_text": None,
                "request": None,
                "response_raw": None,
                "response_parsed": None,
                "parse_error": None,
            }
            question_block_lines = []
            i += 1
            continue

        if current is not None:
            if line.strip() == MARK_REQUEST:
                if i + 1 < len(lines):
                    obj, end_i, raw, err = _parse_json_object_from_lines(lines, i + 1)
                    current["request"] = obj
                    if err:
                        current["parse_error"] = (current["parse_error"] or "") + f" request_{err}"
                    i = end_i
                else:
                    current["parse_error"] = (current["parse_error"] or "") + " missing_request_json"

            elif line.strip() == MARK_RESPONSE:
                if i + 1 < len(lines):
                    obj, end_i, raw, err = _parse_json_object_from_lines(lines, i + 1)
                    current["response_parsed"] = obj
                    current["response_raw"] = raw
                    if err:
                        current["parse_error"] = (current["parse_error"] or "") + f" response_{err}"
                    i = end_i
                else:
                    current["parse_error"] = (current["parse_error"] or "") + " missing_response_json"

            else:
                question_block_lines.append(line)

        i += 1

    if current is not None:
        current["question_block_text"] = "\n".join(question_block_lines).strip() or None
        records.append(current)

    # Fixed schema across BOTH /api/chat and /api/generate shapes
    response_keys = [
        "model",
        "created_at",
        "message",      # /api/chat
        "response",     # /api/generate
        "done",
        "done_reason",
        "context",
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    ]
    message_keys = ["role", "content"]

    def normalize_response(obj: Optional[dict]) -> Dict[str, Any]:
        norm: Dict[str, Any] = {k: None for k in response_keys}
        norm["message"] = {k: None for k in message_keys}

        if not isinstance(obj, dict):
            norm["extra"] = None
            return norm

        extra = {}
        for k, v in obj.items():
            if k in response_keys and k != "message":
                norm[k] = v
            elif k != "message":
                extra[k] = v

        msg = obj.get("message")
        if isinstance(msg, dict):
            for mk in message_keys:
                if mk in msg:
                    norm["message"][mk] = msg.get(mk)

        # Mirror /api/generate "response" into message.content
        if norm["message"]["content"] is None and isinstance(obj.get("response"), str):
            norm["response"] = obj.get("response")
            norm["message"]["role"] = "assistant"
            norm["message"]["content"] = obj.get("response")

        norm["extra"] = extra or None
        return norm

    for r in records:
        r["response"] = normalize_response(r.get("response_parsed"))
        r.pop("response_parsed", None)

    return {
        "meta": meta,
        "input_path": str(input_path),
        "exported_at_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "questions_total": len(records),
        "items": records,
    }


def self_test(payload: Dict[str, Any], n: int = 20, seed: int = 42) -> Dict[str, Any]:
    items = payload.get("items") or []
    ok = [it for it in items if not it.get("parse_error") and it.get("response", {}).get("model")]
    rng = random.Random(seed)

    if len(ok) == 0:
        return {"tested": 0, "passed": 0, "failed": 0, "notes": "No valid responses found to test."}

    sample = ok if len(ok) <= n else rng.sample(ok, n)

    failed = []
    for it in sample:
        try:
            resp = it["response"]
            assert resp["model"] is not None
            assert resp["created_at"] is not None
            assert isinstance(resp["message"], dict)
            assert isinstance(resp["message"]["content"], str)
        except Exception as e:
            failed.append({"question_number": it.get("question_number"), "error": str(e)})

    return {
        "tested": len(sample),
        "passed": len(sample) - len(failed),
        "failed": len(failed),
        "failed_cases": failed or None,
        "seed": seed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract Ollama RESPONSE RAW TEXT blocks into one JSON file.")
    ap.add_argument("--input", required=True, help="Path to the .txt log file")
    ap.add_argument("--output", required=True, help="Path to write the output JSON")
    ap.add_argument("--self-test", type=int, default=0, help="Run a quick self-test on N random items (e.g., 20)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for self-test sampling")
    args = ap.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = extract_log(input_path)

    if args.self_test and args.self_test > 0:
        payload["self_test"] = self_test(payload, n=args.self_test, seed=args.seed)

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    parsed_ok = sum(1 for it in payload["items"] if not it.get("parse_error") and it.get("response", {}).get("model"))
    parsed_bad = payload["questions_total"] - parsed_ok
    print(f"Wrote: {output_path}")
    print(f"Questions: {payload['questions_total']} | Parsed OK: {parsed_ok} | Missing/failed: {parsed_bad}")
    if payload.get("self_test"):
        tr = payload["self_test"]
        print(f"Self-test: tested={tr['tested']} passed={tr['passed']} failed={tr['failed']} seed={tr['seed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
