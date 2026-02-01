import io

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.bg_routers import snap_solve_pdf
from app.bg_routers.snap_solve_pdf import router


def _pdf_bytes(page_count: int = 1) -> bytes:
    first = Image.new("RGB", (220, 180), "white")
    images = [Image.new("RGB", (220, 180), "white") for _ in range(max(0, page_count - 1))]
    stream = io.BytesIO()
    first.save(stream, format="PDF", save_all=True, append_images=images)
    return stream.getvalue()


def _app_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_prepare_enforces_max_pages(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    monkeypatch.setattr(snap_solve_pdf, "PDF_MAX_PAGES", 1)
    snap_solve_pdf._PDF_STORE.clear()
    client = _app_client()

    files = {"file": ("two-pages.pdf", _pdf_bytes(page_count=2), "application/pdf")}
    res = client.post("/snap-solve/pdf/prepare", files=files)

    assert res.status_code == 413
    assert res.json()["detail"]["error_code"] == "PDF_TOO_MANY_PAGES"


def test_forbidden_access_for_other_owner(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    snap_solve_pdf._PDF_STORE.clear()
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("owned.pdf", _pdf_bytes(page_count=1), "application/pdf")},
        headers={"Authorization": "Bearer owner-a"},
    )
    assert prep.status_code == 200
    pdf_id = prep.json()["pdf_id"]

    page = client.get(
        "/snap-solve/pdf/page-image",
        params={"pdf_id": pdf_id, "page_index": 0, "scale": 1.5},
        headers={"Authorization": "Bearer owner-b"},
    )
    assert page.status_code == 403
    assert page.json()["detail"]["error_code"] == "PDF_FORBIDDEN"

    extract = client.post(
        "/snap-solve/pdf/extract",
        headers={"Authorization": "Bearer owner-b"},
        json={
            "pdf_id": pdf_id,
            "mode": "page",
            "page_index": 0,
            "crop": None,
            "image_render": {"width": 300, "height": 200, "scale": 1.5},
            "question_text": "",
            "engine_choice": "pix2text",
        },
    )
    assert extract.status_code == 403
    assert extract.json()["detail"]["error_code"] == "PDF_FORBIDDEN"


def test_page_image_returns_png_and_is_reusable(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    snap_solve_pdf._PDF_STORE.clear()
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("one-page.pdf", _pdf_bytes(page_count=1), "application/pdf")},
    )
    assert prep.status_code == 200
    pdf_id = prep.json()["pdf_id"]

    params = {"pdf_id": pdf_id, "page_index": 0, "scale": 1.5}
    first = client.get("/snap-solve/pdf/page-image", params=params)
    second = client.get("/snap-solve/pdf/page-image", params=params)

    assert first.status_code == 200
    assert first.headers["content-type"] == "image/png"
    assert second.status_code == 200
    assert first.content == second.content


def test_page_image_scale_is_clamped(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    monkeypatch.setattr(snap_solve_pdf, "PDF_RENDER_SCALE_MIN", 0.5)
    monkeypatch.setattr(snap_solve_pdf, "PDF_RENDER_SCALE_MAX", 4.0)
    snap_solve_pdf._PDF_STORE.clear()
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("one-page.pdf", _pdf_bytes(page_count=1), "application/pdf")},
    )
    pdf_id = prep.json()["pdf_id"]
    res = client.get("/snap-solve/pdf/page-image", params={"pdf_id": pdf_id, "page_index": 0, "scale": 100.0})

    assert res.status_code == 200
    assert res.headers["X-Render-Scale"] == "4.0"
    assert res.headers["X-Render-Scale-Requested"] == "100.0"


def test_extract_crop_uses_crop_dimensions(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    snap_solve_pdf._PDF_STORE.clear()
    seen = {}

    def fake_extract(image_bytes, *_args, **_kwargs):
        with Image.open(io.BytesIO(image_bytes)) as image:
            seen["size"] = (image.width, image.height)
        return [{"id": "q1", "text": "x+1=2", "confidence": 0.9, "is_valid_math": True}]

    monkeypatch.setattr(snap_solve_pdf, "_extract_questions_from_image", fake_extract)
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("one-page.pdf", _pdf_bytes(page_count=1), "application/pdf")},
    )
    pdf_id = prep.json()["pdf_id"]

    res = client.post(
        "/snap-solve/pdf/extract",
        json={
            "pdf_id": pdf_id,
            "mode": "crop",
            "page_index": 0,
            "crop": {"x": 10, "y": 20, "width": 40, "height": 30},
            "image_render": {"width": 330, "height": 270, "scale": 1.5},
            "engine_choice": "pix2text",
        },
    )

    assert res.status_code == 200
    assert seen["size"] == (40, 30)
    payload = res.json()
    assert isinstance(payload["extracted_questions"], list)
    assert payload["meta"]["mode"] == "crop"


def test_rate_limit_returns_429_and_isolated_buckets(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    monkeypatch.setattr(snap_solve_pdf, "PDF_RATE_LIMIT_PAGE_IMAGE", 1)
    monkeypatch.setattr(snap_solve_pdf, "PDF_RATE_LIMIT_EXTRACT", 1)
    snap_solve_pdf._PDF_STORE.clear()
    snap_solve_pdf._rate_windows.clear()
    monkeypatch.setattr(
        snap_solve_pdf,
        "_extract_questions_from_image",
        lambda *_args, **_kwargs: [{"id": "q1", "text": "x=1", "confidence": 0.9, "is_valid_math": True}],
    )
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("rl.pdf", _pdf_bytes(page_count=1), "application/pdf")},
        headers={"Authorization": "Bearer rl"},
    )
    pdf_id = prep.json()["pdf_id"]

    first_page = client.get(
        "/snap-solve/pdf/page-image",
        params={"pdf_id": pdf_id, "page_index": 0, "scale": 1.5},
        headers={"Authorization": "Bearer rl"},
    )
    assert first_page.status_code == 200
    limited_page = client.get(
        "/snap-solve/pdf/page-image",
        params={"pdf_id": pdf_id, "page_index": 0, "scale": 1.5},
        headers={"Authorization": "Bearer rl"},
    )
    assert limited_page.status_code == 429
    assert limited_page.json()["detail"]["error_code"] == "RATE_LIMITED"

    extract_ok = client.post(
        "/snap-solve/pdf/extract",
        headers={"Authorization": "Bearer rl"},
        json={
            "pdf_id": pdf_id,
            "mode": "page",
            "page_index": 0,
            "crop": None,
            "image_render": {"width": 330, "height": 270, "scale": 1.5},
            "question_text": "",
            "engine_choice": "pix2text",
        },
    )
    assert extract_ok.status_code == 200

    extract_limited = client.post(
        "/snap-solve/pdf/extract",
        headers={"Authorization": "Bearer rl"},
        json={
            "pdf_id": pdf_id,
            "mode": "page",
            "page_index": 0,
            "crop": None,
            "image_render": {"width": 330, "height": 270, "scale": 1.5},
            "question_text": "",
            "engine_choice": "pix2text",
        },
    )
    assert extract_limited.status_code == 429
    assert extract_limited.json()["detail"]["error_code"] == "RATE_LIMITED"


def test_prepare_page_image_extract_page_flow(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    snap_solve_pdf._PDF_STORE.clear()
    monkeypatch.setattr(
        snap_solve_pdf,
        "_extract_questions_from_image",
        lambda *_args, **_kwargs: [{"id": "q1", "text": "Solve 2x=4", "confidence": 0.8, "is_valid_math": True}],
    )
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("flow.pdf", _pdf_bytes(page_count=1), "application/pdf")},
    )
    assert prep.status_code == 200
    pdf_id = prep.json()["pdf_id"]

    page = client.get("/snap-solve/pdf/page-image", params={"pdf_id": pdf_id, "page_index": 0, "scale": 1.5})
    assert page.status_code == 200

    extracted = client.post(
        "/snap-solve/pdf/extract",
        json={
            "pdf_id": pdf_id,
            "mode": "page",
            "page_index": 0,
            "crop": None,
            "image_render": {"width": int(page.headers["X-Page-Width"]), "height": int(page.headers["X-Page-Height"]), "scale": 1.5},
            "question_text": "",
            "engine_choice": "pix2text",
        },
    )
    assert extracted.status_code == 200
    body = extracted.json()
    assert "extracted_questions" in body
    assert body["meta"]["mode"] == "page"


def test_document_mode_cap_and_warning(monkeypatch):
    monkeypatch.setattr(snap_solve_pdf, "PDF_ENABLED", True)
    monkeypatch.setattr(snap_solve_pdf, "PDF_DOCUMENT_EXTRACT_ENABLED", True)
    monkeypatch.setattr(snap_solve_pdf, "PDF_DOCUMENT_MAX_PAGES", 2)
    snap_solve_pdf._PDF_STORE.clear()
    monkeypatch.setattr(
        snap_solve_pdf,
        "_extract_questions_from_image",
        lambda *_args, page_index=None, **_kwargs: [
            {"id": f"q{page_index}", "text": f"Page {page_index}", "confidence": 0.8, "is_valid_math": True}
        ],
    )
    client = _app_client()

    prep = client.post(
        "/snap-solve/pdf/prepare",
        files={"file": ("multi.pdf", _pdf_bytes(page_count=4), "application/pdf")},
    )
    pdf_id = prep.json()["pdf_id"]

    res = client.post(
        "/snap-solve/pdf/extract",
        json={
            "pdf_id": pdf_id,
            "mode": "document",
            "page_index": None,
            "crop": None,
            "image_render": None,
            "question_text": "",
            "engine_choice": "pix2text",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["pages_processed"] == 2
    assert any("capped" in warning.lower() for warning in body["meta"]["warnings"])
