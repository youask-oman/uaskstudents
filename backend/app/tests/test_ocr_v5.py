import base64
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from app.main import app
from app.database import get_session
import app.api as api_module

engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

app.router.on_startup.clear()
app.router.on_shutdown.clear()


def override_get_session():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


def test_ocr_v5_rejects_pdf():
    client = TestClient(app)
    pdf_bytes = b"%PDF-1.4 fake"
    res = client.post(
        "/api/v1/ocr_v5",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"page_number": "1"},
    )
    assert res.status_code == 415


def test_ocr_v5_cache_hit(monkeypatch):
    async def fake_ocr(_bytes: bytes):
        return {
            "payload": {
                "extracted_text": "x + 1",
                "extracted_markdown": None,
                "questions": ["x + 1"],
            },
            "input_tokens": 10,
            "output_tokens": 5,
            "cached_tokens": 0,
        }

    monkeypatch.setattr(api_module, "_call_ocr_v5", fake_ocr)

    client = TestClient(app)
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9oM2pVQAAAAASUVORK5CYII="
    )

    res1 = client.post(
        "/api/v1/ocr_v5",
        files={"file": ("test.png", png_bytes, "image/png")},
        data={"page_number": "1"},
    )
    assert res1.status_code == 200
    assert res1.json()["cache_hit"] is False

    res2 = client.post(
        "/api/v1/ocr_v5",
        files={"file": ("test.png", png_bytes, "image/png")},
        data={"page_number": "1"},
    )
    assert res2.status_code == 200
    assert res2.json()["cache_hit"] is True
