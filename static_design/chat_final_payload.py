from __future__ import annotations

from typing import Any, Dict, List, Optional

from .chat_final_format import build_chat_final_message


def build_chat_final_payload(extracted_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input: the full extracted JSON (the output from your existing extractor)
    Output: UI-ready payload for chat_final page

    Output shape:
      {
        "items": [
           {"question_number":..., "item_number":..., "message": {...}}
        ],
        "counts": {"included": X, "excluded": Y, "excluded_reasons": {...}}
      }
    """
    items = extracted_json.get("items")
    if not isinstance(items, list):
        items = []

    included: List[Dict[str, Any]] = []
    excluded_reasons: Dict[str, int] = {}
    excluded = 0

    for it in items:
        if not isinstance(it, dict):
            excluded += 1
            excluded_reasons["invalid_item"] = excluded_reasons.get("invalid_item", 0) + 1
            continue

        msg, err = build_chat_final_message(it)
        if msg:
            included.append({
                "question_number": it.get("question_number"),
                "item_number": it.get("item_number"),
                "message": msg,
            })
        else:
            excluded += 1
            k = err or "excluded_unknown"
            excluded_reasons[k] = excluded_reasons.get(k, 0) + 1

    return {
        "items": included,
        "counts": {
            "included": len(included),
            "excluded": excluded,
            "excluded_reasons": excluded_reasons,
        }
    }
