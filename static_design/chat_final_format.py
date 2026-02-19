from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


def _safe_str(x: Any) -> Optional[str]:
    if isinstance(x, str) and x.strip():
        return x
    return None


def parse_response_raw(response_raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    response_raw is a JSON object stored as a string.
    Try normal json.loads first, then a unicode-escape fallback for double-escaped cases.
    """
    if not response_raw:
        return None

    try:
        return json.loads(response_raw)
    except json.JSONDecodeError:
        pass

    # Fallback for cases where the JSON string is double-escaped
    try:
        unescaped = response_raw.encode("utf-8").decode("unicode_escape")
        return json.loads(unescaped)
    except Exception:
        return None


def extract_assistant_text_from_ollama_obj(ollama_obj: Dict[str, Any]) -> Optional[str]:
    """
    Supports both Ollama response shapes:
      - /api/chat: {"message": {"role":"assistant","content":"..."}}
      - /api/generate: {"response":"..."}
    """
    msg = ollama_obj.get("message")
    if isinstance(msg, dict):
        c = _safe_str(msg.get("content"))
        if c:
            return c

    r = _safe_str(ollama_obj.get("response"))
    if r:
        return r

    return None


def deep_find_tier(obj: Any) -> Optional[str]:
    """
    Tier discovery (STRICT):
      1) request["tier"]
      2) request["runtime"]["tier"]
      3) request["meta"]["tier"]
      4) deep search for any "tier"
    """
    if not isinstance(obj, dict):
        return None

    # 1
    t = obj.get("tier")
    if isinstance(t, str):
        return t

    # 2
    rt = obj.get("runtime")
    if isinstance(rt, dict) and isinstance(rt.get("tier"), str):
        return rt["tier"]

    # 3
    mt = obj.get("meta")
    if isinstance(mt, dict) and isinstance(mt.get("tier"), str):
        return mt["tier"]

    # 4 deep search
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if isinstance(cur.get("tier"), str):
                return cur["tier"]
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)

    return None


def is_allowed_tier(request_obj: Optional[Dict[str, Any]]) -> bool:
    if not request_obj:
        return False
    t = deep_find_tier(request_obj)
    if not isinstance(t, str):
        return False
    return t.strip().upper() in {"SHORT", "FINAL"}


def build_chat_final_message(extracted_item: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Input: one extracted item (from your existing extractor output).
    Output: (ui_message, error_string)

    ui_message shape:
      {
        "role": "assistant",
        "render": "markdown+math",
        "content_markdown": "<assistant text>"
      }
    """
    request_obj = extracted_item.get("request")
    if not is_allowed_tier(request_obj):
        return None, "excluded_tier"

    # Primary: normalized response object already created by your extractor
    response_norm = extracted_item.get("response")
    if isinstance(response_norm, dict):
        # Preferred: message.content
        msg = response_norm.get("message")
        if isinstance(msg, dict):
            c = _safe_str(msg.get("content"))
            if c:
                return {
                    "role": "assistant",
                    "render": "markdown+math",
                    "content_markdown": c,
                }, None

        # Fallback: response string (generate shape)
        r = _safe_str(response_norm.get("response"))
        if r:
            return {
                "role": "assistant",
                "render": "markdown+math",
                "content_markdown": r,
            }, None

    # Last resort: parse response_raw then extract message.content/response
    response_raw = extracted_item.get("response_raw")
    if isinstance(response_raw, str) and response_raw.strip():
        parsed = parse_response_raw(response_raw)
        if isinstance(parsed, dict):
            c = extract_assistant_text_from_ollama_obj(parsed)
            if c:
                return {
                    "role": "assistant",
                    "render": "markdown+math",
                    "content_markdown": c,
                }, None
        return None, "response_raw_parse_failed"

    return None, "no_assistant_content"
