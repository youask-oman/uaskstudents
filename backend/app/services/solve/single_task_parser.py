from __future__ import annotations

import re
from typing import Any, Dict, List


TASK_HEADER_RE = re.compile(
    r"(?:^|\n)\s*(Tasks|Instructions|Steps|Do the following|Part)\s*:\s*",
    flags=re.IGNORECASE,
)
TASK_LINE_RE = re.compile(r"^\s*(\d+[.)]|[-*\u2022])\s+(.*)$")


def parse_single_question_tasks(text: str, max_tasks: int = 15) -> Dict[str, Any]:
    src = str(text or "")
    m = TASK_HEADER_RE.search(src)
    if not m:
        return {
            "has_tasks_header": False,
            "detected_task_count_raw": 0,
            "task_count_capped": 0,
            "tasks": [],
            "omitted": 0,
            "omitted_count": 0,
        }

    body = src[m.end() :]
    tasks: List[str] = []
    current: List[str] = []
    for line in body.splitlines():
        ml = TASK_LINE_RE.match(line)
        if ml:
            if current:
                merged = " ".join(part.strip() for part in current if part.strip()).strip()
                if merged:
                    tasks.append(merged)
            current = [ml.group(2).strip()]
        else:
            stripped = line.strip()
            if stripped and current:
                current.append(stripped)
    if current:
        merged = " ".join(part.strip() for part in current if part.strip()).strip()
        if merged:
            tasks.append(merged)

    raw_count = len(tasks)
    capped = tasks[: max(0, int(max_tasks))]
    task_objs = [
        {"task_id": f"t{i+1}", "task_text": t, "order_index": i + 1}
        for i, t in enumerate(capped)
    ]
    omitted = max(0, raw_count - len(capped))
    return {
        "has_tasks_header": True,
        "detected_task_count_raw": raw_count,
        "task_count_capped": len(capped),
        "tasks": task_objs,
        "omitted": omitted,
        "omitted_count": omitted,
    }


def unicode_integrity_probe(text: str) -> Dict[str, Any]:
    src = str(text or "")
    for idx, ch in enumerate(src):
        if ch == "\ufffd":
            return {
                "unicode_integrity_check": False,
                "first_offending_codepoint": f"U+{ord(ch):04X}",
                "offset": idx,
            }
    return {
        "unicode_integrity_check": True,
        "first_offending_codepoint": None,
        "offset": None,
    }

