import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

TRACE_LOG_PATH = Path(__file__).resolve().parents[2] / "storage" / "logs" / "solve_trace.jsonl"


def log_solve_trace(payload: Dict[str, Any]) -> None:
    TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    enriched = dict(payload)
    enriched["logged_at"] = datetime.utcnow().isoformat() + "Z"
    with TRACE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched, ensure_ascii=False) + "\n")
