import json
import re
from typing import Any, Dict, Tuple


FORBIDDEN_KEYS = {"OPENAI_API_KEY", "WHATSAPP_INTERNAL_KEY"}
SK_TOKEN_RE = re.compile(r"sk-[A-Za-z0-9]{10,}")
PEM_RE = re.compile(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", re.DOTALL)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        if PEM_RE.search(value):
            return "[REDACTED_PEM]"
        if SK_TOKEN_RE.search(value):
            return SK_TOKEN_RE.sub("[REDACTED]", value)
        return value
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, dict):
        return _sanitize_payload(value)
    return value


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in payload.items():
        if key.upper() in FORBIDDEN_KEYS:
            continue
        cleaned[key] = _sanitize_value(value)
    return cleaned


def _truncate_context_payload(context_payload: Dict[str, Any], max_chars: int) -> Tuple[Dict[str, Any], bool, list]:
    serialized = json.dumps(context_payload, sort_keys=True, separators=(",", ":"))
    if len(serialized) <= max_chars:
        return context_payload, False, []

    truncated = {}
    for key in sorted(context_payload.keys()):
        value = context_payload[key]
        if isinstance(value, str) and len(value) > 200:
            truncated[key] = value[:200] + "...[truncated]"
        else:
            truncated[key] = value

    serialized = json.dumps(truncated, sort_keys=True, separators=(",", ":"))
    if len(serialized) <= max_chars:
        return truncated, True, []

    removed = []
    for key in sorted(truncated.keys(), reverse=True):
        removed.append(key)
        truncated.pop(key, None)
        serialized = json.dumps(truncated, sort_keys=True, separators=(",", ":"))
        if len(serialized) <= max_chars:
            break

    return truncated, True, removed


def build_user_message(
    question_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
    runtime_hints: Dict[str, Any],
    max_context_chars: int = 4000,
) -> str:
    question_payload = _sanitize_payload(question_payload or {})
    context_payload = _sanitize_payload(context_payload or {})
    runtime_hints = _sanitize_payload(runtime_hints or {})

    truncated_context, did_truncate, removed_keys = _truncate_context_payload(context_payload, max_context_chars)
    if did_truncate:
        runtime_hints["context_truncated"] = True
        if removed_keys:
            runtime_hints["context_removed_keys"] = removed_keys

    question_json = json.dumps(question_payload, sort_keys=True, separators=(",", ":"))
    context_json = json.dumps(truncated_context, sort_keys=True, separators=(",", ":"))
    hints_json = json.dumps(runtime_hints, sort_keys=True, separators=(",", ":"))

    return (
        "question_payload:\n"
        f"{question_json}\n\n"
        "context_payload:\n"
        f"{context_json}\n\n"
        "runtime_hints:\n"
        f"{hints_json}"
    )
