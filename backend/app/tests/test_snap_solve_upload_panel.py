import io

import pytest
from PIL import Image
from sqlmodel import SQLModel, Session, create_engine
from starlette.datastructures import UploadFile

from app.bg_routers.local_router import (
    _normalize_to_rgb,
    _validate_mime,
    solve_from_image_or_sketch,
)
from app.models import User


def _png_bytes(mode: str = "RGBA") -> bytes:
    image = Image.new(mode, (200, 120), (255, 0, 0, 128) if mode == "RGBA" else (255, 255, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_rgba_sketch_conversion_to_rgb():
    image = Image.open(io.BytesIO(_png_bytes("RGBA")))
    converted = _normalize_to_rgb(image, white_bg=True)
    assert converted.mode == "RGB"


def test_mime_validation_rejects_unsupported_upload_type():
    with pytest.raises(Exception):
        _validate_mime("upload", "application/octet-stream")


@pytest.mark.asyncio
async def test_solve_from_image_or_sketch_returns_expected_json_shape(monkeypatch, tmp_path):
    class FakeSolver:
        async def solve(self, **kwargs):
            return {
                "steps": [{"title": "Step 1", "explanation": "Use OCR text"}],
                "final_answer": {"answer_text": "x=3", "answer_latex": "x=3"},
            }

    def fake_recognize_region(_bytes: bytes, engine_name: str = "auto"):
        return {"text": "Solve x + 2 = 5", "confidence": 0.99, "engine_used": engine_name}

    monkeypatch.setattr("app.bg_routers.local_router.get_solver_v3", lambda: FakeSolver())
    monkeypatch.setattr("app.bg_routers.local_router.ocr_service.recognize_region", fake_recognize_region)

    db_path = tmp_path / "snap_solve.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        upload = UploadFile(filename="input.png", file=io.BytesIO(_png_bytes("RGB")), headers={"content-type": "image/png"})
        result = await solve_from_image_or_sketch(
            request=None,  # endpoint doesn't use request object
            mode="upload",
            question_text="",
            image=upload,
            original_filename="input.png",
            client_context=None,
            session=session,
        )

    payload = result.model_dump()
    assert "answer_markdown" in payload
    assert "meta" in payload
    assert payload["meta"]["mode"] == "upload"
    assert payload["meta"]["mime"] == "image/png"


@pytest.mark.asyncio
async def test_solve_from_sketch_mode_png_success(monkeypatch, tmp_path):
    class FakeSolver:
        async def solve(self, **kwargs):
            return {"_content": "Sketch result", "final_answer": {"answer_latex": "x=1"}}

    monkeypatch.setattr("app.bg_routers.local_router.get_solver_v3", lambda: FakeSolver())
    monkeypatch.setattr(
        "app.bg_routers.local_router.ocr_service.recognize_region",
        lambda *_args, **_kwargs: {"text": "x=1"},
    )

    db_path = tmp_path / "snap_solve_sketch.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        upload = UploadFile(filename="sketch.png", file=io.BytesIO(_png_bytes("RGBA")), headers={"content-type": "image/png"})
        result = await solve_from_image_or_sketch(
            request=None,
            mode="sketch",
            question_text="",
            image=upload,
            original_filename="sketch.png",
            client_context=None,
            session=session,
        )

    payload = result.model_dump()
    assert payload["meta"]["mode"] == "sketch"
    assert payload["answer_markdown"] == "Sketch result"


@pytest.mark.asyncio
async def test_fallback_solver_passes_research_tier_to_solver(monkeypatch, tmp_path):
    captured_kwargs = {}

    class FakeSolver:
        async def solve(self, **kwargs):
            captured_kwargs.update(kwargs)
            return {"_content": "ok"}

    monkeypatch.setattr("app.bg_routers.local_router.get_solver_v3", lambda: FakeSolver())

    db_path = tmp_path / "snap_solve_tier_research.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            email="research@example.com",
            full_name="Research User",
            password_hash="x",
            subscription_tier="research",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        await solve_from_image_or_sketch(
            request=None,
            mode="upload",
            question_text="Solve x^2=1",
            image=None,
            tier="research",
            original_filename=None,
            client_context=None,
            user_id=user.id,
            session=session,
        )

    assert captured_kwargs["user_tier"] == "research"
    assert captured_kwargs["requested_mode"] == "detailed"
    assert captured_kwargs["user_id"] == user.id


@pytest.mark.asyncio
async def test_fallback_solver_clamps_requested_tier_to_entitlement(monkeypatch, tmp_path):
    captured_kwargs = {}

    class FakeSolver:
        async def solve(self, **kwargs):
            captured_kwargs.update(kwargs)
            return {"_content": "ok"}

    monkeypatch.setattr("app.bg_routers.local_router.get_solver_v3", lambda: FakeSolver())

    db_path = tmp_path / "snap_solve_tier_clamp.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            email="free@example.com",
            full_name="Free User",
            password_hash="x",
            subscription_tier="free",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        await solve_from_image_or_sketch(
            request=None,
            mode="upload",
            question_text="Solve x^2=1",
            image=None,
            tier="research",
            requested_mode="detailed",
            original_filename=None,
            client_context=None,
            user_id=user.id,
            session=session,
        )

    assert captured_kwargs["user_tier"] == "free"
    assert captured_kwargs["requested_mode"] == "detailed"
