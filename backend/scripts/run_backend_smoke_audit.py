from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path
import sys
from typing import Any, Dict, List

import requests
from PIL import Image
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import engine
from app.models import User


BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:9000")
AUDIT_EMAIL = os.getenv("AUDIT_USER_EMAIL", "audit@uask.ai")


def _blank_png_b64() -> str:
    img = Image.new("RGB", (120, 120), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _is_dependency_unavailable(payload: Dict[str, Any]) -> bool:
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict) and detail.get("status") == "dependency_unavailable":
        return True
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict) and err.get("status") == "dependency_unavailable":
        return True
    return False


def _is_legacy_meta_dependency(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    detail = payload.get("detail") if isinstance(payload.get("detail"), dict) else {}
    reason = str(detail.get("reason") or detail.get("message") or "").lower()
    if detail.get("status") == "dependency_unavailable" and "binding" in reason:
        return True
    err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    err_reason = str(err.get("reason") or err.get("message") or "").lower()
    return err.get("status") == "dependency_unavailable" and "binding" in err_reason


def _fetch_audit_user_id() -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == AUDIT_EMAIL)).first()
        if user is None or user.id is None:
            raise RuntimeError(f"Audit user not found: {AUDIT_EMAIL}. Run scripts/seed_audit_state.py first.")
        return int(user.id)


def _request_with_retry(method: str, url: str, retries: int = 10, **kwargs):
    last_exc = None
    for _ in range(retries):
        try:
            return requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(1.0)
    raise last_exc


def main() -> None:
    user_id = _fetch_audit_user_id()
    checks: List[Dict[str, Any]] = []
    runtime_meta_warned = False

    # 1) health
    r = _request_with_retry("GET", f"{BASE_URL}/health", timeout=15)
    checks.append({"name": "health", "status_code": r.status_code, "ok": r.status_code == 200})

    # 2) solve_v3 superset route
    r = _request_with_retry(
        "POST",
        f"{BASE_URL}/api/v1/solve_v3",
        params={"user_id": user_id},
        json={
            "text_query": "Solve x^2 - 4 = 0",
            "requested_mode": "detailed",
            "graph_mode": "on",
            "tier": "standard",
            "idempotency_key": f"smoke-{int(time.time())}",
        },
        timeout=120,
    )
    solve_payload = {}
    try:
        solve_payload = r.json()
    except Exception:
        solve_payload = {"raw": r.text[:500]}
    ok_solve = r.status_code in {200, 422, 503}
    if ok_solve and r.status_code != 200:
        detail = solve_payload.get("detail") if isinstance(solve_payload, dict) else None
        ok_solve = isinstance(detail, dict) and detail.get("status") in {"failed_controlled", "dependency_unavailable"}
    checks.append({"name": "solve_v3_superset_v2", "status_code": r.status_code, "ok": ok_solve, "payload": solve_payload})

    # 3) runtime meta (attempt-first observability)
    meta_params: Dict[str, Any] = {}
    if isinstance(solve_payload, dict) and solve_payload.get("attempt_id"):
        meta_params = {"attempt_id": solve_payload.get("attempt_id")}
    else:
        meta_params = {"user_id": user_id}

    r = _request_with_retry(
        "GET",
        f"{BASE_URL}/api/v1/solve_v3_runtime_meta",
        params=meta_params,
        timeout=20,
    )
    payload = {}
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:500]}
    ok_meta = r.status_code == 200
    warning = None
    if not ok_meta and ok_solve and _is_legacy_meta_dependency(payload):
        ok_meta = True
        warning = "legacy_meta_dependency"
        runtime_meta_warned = True
        print("\x1b[31mWARN: legacy_meta_dependency - solve succeeded but /solve_v3_runtime_meta still depends on legacy prompt binding.\x1b[0m")
    checks.append(
        {
            "name": "solve_v3_runtime_meta",
            "status_code": r.status_code,
            "ok": ok_meta,
            "warning": warning,
            "payload": payload,
        }
    )

    # 4) find_error_local (JSON body path from local_router)
    r = _request_with_retry(
        "POST",
        f"{BASE_URL}/api/v1/find_error_local",
        json={
            "image_data": _blank_png_b64(),
            "selection_bbox": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8},
            "max_lines": 6,
        },
        timeout=30,
    )
    payload = {}
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:500]}
    ok_find_error = r.status_code == 200 and (
        payload.get("ok") is True
        or (isinstance(payload.get("error"), dict) and payload["error"].get("status") == "dependency_unavailable")
        or (isinstance(payload.get("error"), dict) and payload["error"].get("code") in {"NO_TEXT", "LOW_CONFIDENCE"})
    )
    checks.append(
        {
            "name": "find_error_local",
            "status_code": r.status_code,
            "ok": ok_find_error,
            "payload": payload,
        }
    )

    # 5) plot pipeline
    r = _request_with_retry(
        "POST",
        f"{BASE_URL}/api/v1/plot/pipeline",
        json={
            "problem_text": "plot y=x^2",
            "solve_result": {"visuals": {"should_visualize": True, "plots": []}},
            "graph_mode": "on",
            "tier": "STANDARD",
            "question_id": "smoke-audit",
            "use_reliable_pipeline": False,
        },
        timeout=30,
    )
    payload = {}
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:500]}
    ok_plot = r.status_code == 200 or (r.status_code == 503 and _is_dependency_unavailable(payload))
    checks.append({"name": "plot_pipeline", "status_code": r.status_code, "ok": ok_plot, "payload": payload})

    failed = [c for c in checks if not c["ok"]]
    report = {
        "base_url": BASE_URL,
        "user_id": user_id,
        "checks": checks,
        "warnings": ["legacy_meta_dependency"] if runtime_meta_warned else [],
        "ok": len(failed) == 0,
    }

    out = Path("reports/evidence/backend_smoke_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
