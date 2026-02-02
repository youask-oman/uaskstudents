import os

from app.services.ocr.vision_routing import (
    VisionRoutingConfig,
    build_provider_plan,
    get_openai_ocr_model,
)


def test_openai_ocr_model_default(monkeypatch):
    monkeypatch.delenv("VLM_MODEL_OPENA_AI_OCR", raising=False)
    assert get_openai_ocr_model() == "gpt-5-mini"


def test_openai_ocr_model_from_env(monkeypatch):
    monkeypatch.setenv("VLM_MODEL_OPENA_AI_OCR", "gpt-5-mini")
    assert get_openai_ocr_model() == "gpt-5-mini"


def test_router_auto_order(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VISION_OCR_ENABLED_PROVIDERS", "pix2txt,qwen,openai")
    monkeypatch.setenv("VISION_OCR_FALLBACK_ORDER", "pix2txt,qwen,openai")
    cfg = VisionRoutingConfig.from_env()
    assert build_provider_plan("auto", cfg) == ["pix2txt", "qwen", "openai"]


def test_openai_disabled_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("VISION_OCR_ENABLED_PROVIDERS", "pix2txt,qwen,openai")
    cfg = VisionRoutingConfig.from_env()
    assert "openai" not in cfg.enabled_providers
