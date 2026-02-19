from __future__ import annotations

from typing import Any, Dict, List

from app.utils.chat_final_format import build_chat_final_message


def build_chat_final_payload(extracted_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert full extracted payload into chat_final UI payload.
    """
    raw_items = extracted_json.get("items")
    items = raw_items if isinstance(raw_items, list) else []

    included: List[Dict[str, Any]] = []
    excluded = 0
    excluded_reasons: Dict[str, int] = {}

    for item in items:
        if not isinstance(item, dict):
            excluded += 1
            excluded_reasons["invalid_item"] = excluded_reasons.get("invalid_item", 0) + 1
            continue

        msg, err = build_chat_final_message(item)
        if msg is None:
            excluded += 1
            reason = err or "excluded_unknown"
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            continue

        included.append(
            {
                "question_number": item.get("question_number"),
                "item_number": item.get("item_number"),
                "message": msg,
            }
        )

    return {
        "items": included,
        "counts": {
            "included": len(included),
            "excluded": excluded,
            "excluded_reasons": excluded_reasons,
        },
    }

