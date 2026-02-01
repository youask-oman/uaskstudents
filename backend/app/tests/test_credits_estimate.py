from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bg_routers import credits_router
from app.bg_routers.credits_router import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_credits_estimate_snap_pdf_breakdown(monkeypatch):
    monkeypatch.setattr(
        credits_router,
        "_resolve_pricing",
        lambda _session: {
            "pricing_version": "2026-02-01",
            "tiers": {"FREE": 1, "STANDARD": 2, "RESEARCH": 4},
            "addons": {"ocr": 1, "voice": 2, "verify": 0.5, "plot": 0.5},
            "asset_addons": {"none": 0, "image": 0, "pdf": 1},
        },
    )
    client = _client()
    res = client.post(
        "/credits/estimate",
        json={
            "tier": "STANDARD",
            "input_type": "snap",
            "asset_type": "pdf",
            "question_count": 3,
            "addons": {"ocr": True, "voice": False, "verify": False, "plot": False},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["per_question_credits"] == 4.0
    assert data["total_credits"] == 12.0
    assert data["breakdown"]["tier_base"] == 2.0
    assert data["breakdown"]["ocr"] == 1.0
    assert data["breakdown"]["asset_type_addon"] == 1.0


def test_credits_estimate_voice_auto_addon(monkeypatch):
    monkeypatch.setattr(
        credits_router,
        "_resolve_pricing",
        lambda _session: {
            "pricing_version": "2026-02-01",
            "tiers": {"FREE": 1, "STANDARD": 2, "RESEARCH": 4},
            "addons": {"ocr": 1, "voice": 2, "verify": 0, "plot": 0},
            "asset_addons": {"none": 0, "image": 0, "pdf": 0},
        },
    )
    client = _client()
    res = client.post(
        "/credits/estimate",
        json={
            "tier": "FREE",
            "input_type": "voice",
            "asset_type": "none",
            "question_count": 1,
            "addons": {"ocr": False, "voice": False, "verify": False, "plot": False},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["per_question_credits"] == 3.0
    assert data["breakdown"]["voice"] == 2.0

