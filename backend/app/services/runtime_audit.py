from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional


def runtime_audit_enabled() -> bool:
    return os.getenv("RUNTIME_AUDIT_LOGGING", "false").strip().lower() == "true"


def emit_runtime_audit(
    *,
    component: str,
    started_at: float,
    request_id: Optional[str] = None,
    route: Optional[str] = None,
    sympy_used: bool = False,
    numpy_used: bool = False,
    result: str = "ok",
    error_class: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    if not runtime_audit_enabled():
        return

    payload: Dict[str, Any] = {
        "component": component,
        "request_id": request_id,
        "route": route,
        "sympy_used": bool(sympy_used),
        "numpy_used": bool(numpy_used),
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
        "result": result,
        "error_class": error_class,
    }
    if extra:
        payload.update(extra)

    target = logger or logging.getLogger("runtime_audit")
    target.debug("[RUNTIME_AUDIT] %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))
