from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger("ollama_raw_capture")


_RESPONSE_KEYS = [
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
_MESSAGE_KEYS = ["role", "content"]


def _default_output_path() -> Path:
    env_path = (os.environ.get("OLLAMA_CAPTURE_OUTPUT_PATH") or "").strip()
    if env_path:
        return Path(env_path).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "reports" / "ollama_extracted_short_final.json"


def _read_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "meta": {"path": str(path)},
            "exported_at_utc": None,
            "items": [],
            "filter_summary": {
                "seen_total": 0,
                "included_total": 0,
                "excluded_missing_tier": 0,
                "excluded_non_short_final": 0,
                "parse_error_count": 0,
            },
        }
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("root_not_object")
        parsed.setdefault("meta", {"path": str(path)})
        parsed.setdefault("items", [])
        parsed.setdefault("filter_summary", {})
        fs = parsed["filter_summary"]
        fs.setdefault("seen_total", 0)
        fs.setdefault("included_total", 0)
        fs.setdefault("excluded_missing_tier", 0)
        fs.setdefault("excluded_non_short_final", 0)
        fs.setdefault("parse_error_count", 0)
        return parsed
    except Exception as exc:
        logger.error("capture: failed reading existing file=%s err=%s", str(path), str(exc))
        return {
            "meta": {"path": str(path), "recovered_after_read_error": True},
            "exported_at_utc": None,
            "items": [],
            "filter_summary": {
                "seen_total": 0,
                "included_total": 0,
                "excluded_missing_tier": 0,
                "excluded_non_short_final": 0,
                "parse_error_count": 0,
            },
        }


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass


def _extract_json_object_from_text(raw_text: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Mirrors the approved extraction behavior:
    - trim surrounding junk
    - parse first complete top-level JSON object
    """
    src = str(raw_text or "").strip()
    if not src:
        return None, "empty_response_raw_text"
    start = src.find("{")
    if start < 0:
        return None, "missing_json_start_brace"
    src = src[start:]

    depth = 0
    in_str = False
    esc = False
    end = -1
    for i, ch in enumerate(src):
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
                if depth == 0:
                    end = i
                    break
    if end < 0:
        return None, "json_incomplete_or_missing"
    candidate = src[: end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed, None
        return None, "json_root_not_object"
    except Exception as exc:
        return None, f"json_decode_error: {exc}"


def _normalize_response_obj(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Approved normalization logic (same schema behavior as static_design/extract_ollama_short.py):
    - fixed keys with null defaults
    - supports /api/chat and /api/generate shapes
    """
    norm: Dict[str, Any] = {k: None for k in _RESPONSE_KEYS}
    norm["message"] = {k: None for k in _MESSAGE_KEYS}

    if not isinstance(obj, dict):
        norm["extra"] = None
        return norm

    extra: Dict[str, Any] = {}
    for k, v in obj.items():
        if k in _RESPONSE_KEYS and k != "message":
            norm[k] = v
        elif k != "message":
            extra[k] = v

    msg = obj.get("message")
    if isinstance(msg, dict):
        for mk in _MESSAGE_KEYS:
            if mk in msg:
                norm["message"][mk] = msg.get(mk)

    if norm["message"]["content"] is None and isinstance(obj.get("response"), str):
        norm["response"] = obj.get("response")
        norm["message"]["role"] = "assistant"
        norm["message"]["content"] = obj.get("response")

    norm["extra"] = extra or None
    return norm


def _deep_find_tier(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        if "tier" in value and value.get("tier") is not None:
            return str(value.get("tier"))
        for v in value.values():
            found = _deep_find_tier(v)
            if found:
                return found
    elif isinstance(value, list):
        for v in value:
            found = _deep_find_tier(v)
            if found:
                return found
    elif isinstance(value, str):
        s = value.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                parsed = json.loads(s)
                return _deep_find_tier(parsed)
            except Exception:
                return None
    return None


def _detect_tier(request_json: Dict[str, Any]) -> Optional[str]:
    raw_tier: Optional[str] = None
    if isinstance(request_json, dict):
        if request_json.get("tier") is not None:
            raw_tier = str(request_json.get("tier"))
        elif isinstance(request_json.get("runtime"), dict) and request_json["runtime"].get("tier") is not None:
            raw_tier = str(request_json["runtime"].get("tier"))
        elif isinstance(request_json.get("meta"), dict) and request_json["meta"].get("tier") is not None:
            raw_tier = str(request_json["meta"].get("tier"))
        else:
            raw_tier = _deep_find_tier(request_json)

    if not raw_tier:
        return None
    up = str(raw_tier).strip().upper()
    if up in {"SHORT", "SHORT_STEPS", "FREE", "THREE_STEP"}:
        return "SHORT"
    if up == "FINAL":
        return "FINAL"
    return up


def capture_ollama_raw_response(
    request_json: dict,
    response_raw_text: str,
    question_number: int | None,
    item_number: int | None,
) -> None:
    try:
        output_path = _default_output_path()
        store = _read_json_if_exists(output_path)
        fs = store["filter_summary"]
        fs["seen_total"] = int(fs.get("seen_total", 0)) + 1

        detected_tier = _detect_tier(request_json if isinstance(request_json, dict) else {})
        if detected_tier is None:
            fs["excluded_missing_tier"] = int(fs.get("excluded_missing_tier", 0)) + 1
            store["exported_at_utc"] = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
            _atomic_write_json(output_path, store)
            logger.info(
                "capture excluded=missing_tier tier=%s file=%s question=%s item=%s",
                None,
                str(output_path),
                question_number,
                item_number,
            )
            return

        if detected_tier not in {"SHORT", "FINAL"}:
            fs["excluded_non_short_final"] = int(fs.get("excluded_non_short_final", 0)) + 1
            store["exported_at_utc"] = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
            _atomic_write_json(output_path, store)
            logger.info(
                "capture excluded=non_target_tier tier=%s file=%s question=%s item=%s",
                detected_tier,
                str(output_path),
                question_number,
                item_number,
            )
            return

        parsed_obj, parse_err = _extract_json_object_from_text(response_raw_text)
        norm = _normalize_response_obj(parsed_obj)
        if parse_err:
            fs["parse_error_count"] = int(fs.get("parse_error_count", 0)) + 1

        rec = {
            "tier": detected_tier,
            "question_number": question_number,
            "item_number": item_number,
            "model": norm.get("model"),
            "created_at": norm.get("created_at"),
            "message": norm.get("message"),
            "response": norm.get("response"),
            "done": norm.get("done"),
            "done_reason": norm.get("done_reason"),
            "context": norm.get("context"),
            "total_duration": norm.get("total_duration"),
            "load_duration": norm.get("load_duration"),
            "prompt_eval_count": norm.get("prompt_eval_count"),
            "prompt_eval_duration": norm.get("prompt_eval_duration"),
            "eval_count": norm.get("eval_count"),
            "eval_duration": norm.get("eval_duration"),
            "extra": norm.get("extra"),
            "response_raw": str(response_raw_text or ""),
            "parse_error": parse_err,
        }

        store["items"].append(rec)
        fs["included_total"] = int(fs.get("included_total", 0)) + 1
        store["exported_at_utc"] = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        _atomic_write_json(output_path, store)

        logger.info(
            "capture included=true tier=%s file=%s question=%s item=%s",
            detected_tier,
            str(output_path),
            question_number,
            item_number,
        )
    except Exception as exc:
        logger.error("capture failed err=%s", str(exc))
        return

