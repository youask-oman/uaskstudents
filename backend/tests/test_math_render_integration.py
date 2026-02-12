from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi.testclient import TestClient


def _client() -> TestClient:
    os.environ["DISABLE_OPENAI"] = "true"
    from app.main import app

    return TestClient(app)


def test_math_render_never_break_per_item() -> None:
    with _client() as client:
        payload: Dict[str, Any] = {
            "items": [
                {"latex": r"\frac{1}{2}", "display_mode": False, "macros": {}, "scale": 1.0},
                {
                    "latex": r"\frac{1}{2}",
                    "display_mode": False,
                    "macros": {f"\\m{i}": "x" for i in range(30)},
                    "scale": 1.0,
                },
            ],
            "options": {"font": "tex", "sanitize": True, "return_metrics": True},
        }
        resp = client.post("/api/v1/math/render", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        results: List[Dict[str, Any]] = body.get("results") or []
        assert len(results) == 2
        assert results[0]["ok"] is True
        assert str(results[0]["svg"]).startswith("<")
        assert results[1]["ok"] is False
        assert "error" in results[1]


def test_math_render_cache_hit_on_second_call() -> None:
    with _client() as client:
        payload = {
            "items": [{"latex": r"\sqrt{x+1}", "display_mode": True, "macros": {}, "scale": 1.0}],
            "options": {"font": "tex", "sanitize": True, "return_metrics": True},
        }
        r1 = client.post("/api/v1/math/render", json=payload)
        r2 = client.post("/api/v1/math/render", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        b2 = r2.json()
        assert (b2.get("results") or [])[0].get("cache") == "hit"


def test_disable_openai_guard_during_math_render(monkeypatch) -> None:
    os.environ["DISABLE_OPENAI"] = "true"
    import app.main as app_main

    def _boom():
        raise AssertionError("OpenAI manager must not be initialized in DISABLE_OPENAI mode")

    monkeypatch.setattr(app_main, "get_llm_manager", _boom, raising=True)
    with TestClient(app_main.app) as client:
        resp = client.post(
            "/api/v1/math/render",
            json={
                "items": [{"latex": r"x^2+1", "display_mode": False, "macros": {}, "scale": 1.0}],
                "options": {"font": "tex", "sanitize": True, "return_metrics": True},
            },
        )
        assert resp.status_code == 200
