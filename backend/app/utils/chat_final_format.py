from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


def _safe_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    return None


def parse_response_raw(response_raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse a raw Ollama JSON payload string safely.
    """
    if not response_raw:
        return None
    try:
        parsed = json.loads(response_raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    try:
        unescaped = response_raw.encode("utf-8").decode("unicode_escape")
        parsed = json.loads(unescaped)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def extract_assistant_text_from_ollama_obj(ollama_obj: Dict[str, Any]) -> Optional[str]:
    """
    /api/chat shape:
      {"message": {"role": "assistant", "content": "..."}}
    /api/generate shape:
      {"response": "..."}
    """
    msg = ollama_obj.get("message")
    if isinstance(msg, dict):
        content = _safe_str(msg.get("content"))
        if content is not None:
            return content

    response = _safe_str(ollama_obj.get("response"))
    if response is not None:
        return response
    return None


def _deep_find_tier(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        if isinstance(obj.get("tier"), str):
            return obj["tier"]
        for value in obj.values():
            found = _deep_find_tier(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _deep_find_tier(value)
            if found:
                return found
    return None


def _tier_from_item(item: Dict[str, Any]) -> Optional[str]:
    # Primary: top-level extracted tier, then legacy request-path fallback.
    top = item.get("tier")
    if isinstance(top, str):
        return top
    req = item.get("request")
    if isinstance(req, dict):
        if isinstance(req.get("tier"), str):
            return req["tier"]
        runtime = req.get("runtime")
        if isinstance(runtime, dict) and isinstance(runtime.get("tier"), str):
            return runtime["tier"]
        meta = req.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("tier"), str):
            return meta["tier"]
        deep = _deep_find_tier(req)
        if isinstance(deep, str):
            return deep
    return None


def _allowed_tier(item: Dict[str, Any]) -> bool:
    tier = _tier_from_item(item)
    if not isinstance(tier, str):
        return False
    return tier.strip().upper() in {"SHORT", "FINAL"}


def build_chat_final_message(extracted_item: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Build one UI-ready assistant message from one extracted item.
    Rules:
    - Primary: item.response.message.content
    - Fallback: item.response.response
    - Last resort: parse item.response_raw and extract the same way
    """
    if not _allowed_tier(extracted_item):
        return None, "excluded_tier"

    response = extracted_item.get("response")
    if isinstance(response, dict):
        msg = response.get("message")
        if isinstance(msg, dict):
            content = _safe_str(msg.get("content"))
            if content is not None:
                return {
                    "role": "assistant",
                    "content_markdown": content,
                    "render": "markdown+math",
                }, None

        fallback_response = _safe_str(response.get("response"))
        if fallback_response is not None:
            return {
                "role": "assistant",
                "content_markdown": fallback_response,
                "render": "markdown+math",
            }, None

    response_raw = extracted_item.get("response_raw")
    if isinstance(response_raw, str):
        parsed = parse_response_raw(response_raw)
        if isinstance(parsed, dict):
            content = extract_assistant_text_from_ollama_obj(parsed)
            if content is not None:
                return {
                    "role": "assistant",
                    "content_markdown": content,
                    "render": "markdown+math",
                }, None
        return None, "response_raw_parse_failed"

    return None, "no_assistant_content"

