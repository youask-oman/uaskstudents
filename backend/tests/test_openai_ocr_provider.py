import base64
import json
import asyncio
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.api as api_module
from app.services.prompt_registry_service import prompt_registry_service


def _make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _valid_openai_ocr_doc() -> dict:
    return {
        "schema_version": "image_extract_v1",
        "request_id": "req-1",
        "source": {"source_type": "image", "file_name": "x.png", "page_count": 1},
        "pages": [
            {
                "page_index": 0,
                "width_px": 1000,
                "height_px": 1000,
                "rotation_degrees": 0,
                "segments": [],
            }
        ],
        "questions": [
            {
                "question_id": "q1",
                "page_index": 0,
                "bbox": [0.1, 0.1, 0.9, 0.3],
                "question_number": "1",
                "question_text": "Solve x+1=2",
                "question_latex": "x+1=2",
                "subparts": [],
                "answer_choices": [],
                "figure_refs": [],
                "confidence": 0.9,
            }
        ],
        "figures": [],
        "warnings": [],
        "needs_human_review": False,
        "usage": {"provider": "openai", "model": "gpt-5-mini", "tokens_in": 10, "tokens_out": 20},
    }


class _FakeOpenAIClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("No fake responses left")
        return self._responses.pop(0)


def _make_response(payload_text: str):
    return SimpleNamespace(
        output_text=payload_text,
        status="completed",
        incomplete_details=None,
        usage=SimpleNamespace(input_tokens=10, output_tokens=20, input_token_details=None, prompt_tokens_details=None),
    )


def test_openai_provider_uses_registry_prompt_and_schema(monkeypatch):
    session = _make_session()
    prompt_registry_service.ensure_ocr_extract_prompts(session, updated_by="test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VLM_MODEL_OPENA_AI_OCR", "gpt-5-mini")
    monkeypatch.setenv("VISION_OCR_ENABLED_PROVIDERS", "openai")

    fake_client = _FakeOpenAIClient([_make_response(json.dumps(_valid_openai_ocr_doc()))])
    monkeypatch.setattr(api_module, "AsyncOpenAI", lambda api_key: fake_client)

    out = asyncio.run(
        api_module._call_extract_questions(
            session=session,
            image_bytes=base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABJACfWQAAAABJRU5ErkJggg=="
            ),
            max_output_tokens=800,
            engine_choice="openai",
            crop_meta={"page_number": 0, "source": "image"},
        )
    )

    assert out["ocr_provider_used"] == "openai"
    assert out["ocr_model_used"] == "gpt-5-mini"
    assert out["payload"]["ok"] is True
    call = fake_client.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert call["text"]["format"]["name"] == prompt_registry_service.OCR_EXTRACT_OPENAI_SCHEMA_ID
    assert call["text"]["format"]["schema"]["title"] == "image_extract_v1"
    assert "OCR + math-structure extraction engine" in call["input"][0]["content"][0]["text"]


def test_openai_provider_retries_invalid_json_once(monkeypatch):
    session = _make_session()
    prompt_registry_service.ensure_ocr_extract_prompts(session, updated_by="test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VISION_OCR_ENABLED_PROVIDERS", "openai")

    fake_client = _FakeOpenAIClient([
        _make_response("not-json"),
        _make_response(json.dumps(_valid_openai_ocr_doc())),
    ])
    monkeypatch.setattr(api_module, "AsyncOpenAI", lambda api_key: fake_client)

    out = asyncio.run(
        api_module._call_extract_questions(
            session=session,
            image_bytes=b"test-bytes",
            max_output_tokens=800,
            engine_choice="openai",
            crop_meta={"page_number": 0, "source": "image"},
        )
    )
    assert out["payload"]["ok"] is True
    assert len(fake_client.calls) >= 2
