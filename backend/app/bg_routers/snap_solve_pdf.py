import io
import os
import time
import uuid
import hashlib
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from PIL import Image
import pypdfium2 as pdfium

from app.services.ocr.ocr_service import ocr_service


router = APIRouter()

PDF_ENABLED = os.getenv("SNAP_SOLVE_PDF_ENABLED", "true").lower() in {"1", "true", "yes"}
PDF_MAX_MB = int(os.getenv("SNAP_SOLVE_PDF_MAX_MB", "10"))
PDF_MAX_BYTES = PDF_MAX_MB * 1024 * 1024
PDF_MAX_PAGES = int(os.getenv("SNAP_SOLVE_PDF_MAX_PAGES", "50"))
PDF_TTL_SECONDS = int(os.getenv("SNAP_SOLVE_PDF_TTL_SECONDS", "3600"))
PDF_RENDER_MAX_DIM = int(os.getenv("SNAP_SOLVE_PDF_RENDER_MAX_DIM", "2000"))
PDF_DOCUMENT_EXTRACT_ENABLED = os.getenv("SNAP_SOLVE_PDF_DOCUMENT_EXTRACT_ENABLED", "false").lower() in {"1", "true", "yes"}
PDF_RENDER_SCALE_MIN = float(os.getenv("SNAP_SOLVE_PDF_RENDER_SCALE_MIN", "0.5"))
PDF_RENDER_SCALE_MAX = float(os.getenv("SNAP_SOLVE_PDF_RENDER_SCALE_MAX", "4.0"))
PDF_RASTER_CACHE_SIZE = int(os.getenv("SNAP_SOLVE_PDF_RASTER_CACHE_SIZE", "5"))
PDF_RATE_LIMIT_PREPARE = int(os.getenv("SNAP_SOLVE_PDF_RATE_LIMIT_PREPARE", "10"))
PDF_RATE_LIMIT_PAGE_IMAGE = int(os.getenv("SNAP_SOLVE_PDF_RATE_LIMIT_PAGE_IMAGE", "90"))
PDF_RATE_LIMIT_EXTRACT = int(os.getenv("SNAP_SOLVE_PDF_RATE_LIMIT_EXTRACT", "30"))
PDF_DOCUMENT_MAX_PAGES = int(os.getenv("SNAP_SOLVE_PDF_DOCUMENT_MAX_PAGES", "10"))
PDF_DOCUMENT_TIME_BUDGET_MS = int(os.getenv("SNAP_SOLVE_PDF_DOCUMENT_TIME_BUDGET_MS", "12000"))

STORE_ROOT = os.getenv("SNAP_SOLVE_PDF_STORE_DIR", os.path.join(tempfile.gettempdir(), "uask_snap_pdf"))
os.makedirs(STORE_ROOT, exist_ok=True)

_LOCK = threading.Lock()
_RATE_LOCK = threading.Lock()
_rate_windows: Dict[str, List[float]] = {}


@dataclass
class PdfSession:
    pdf_id: str
    owner_key: str
    path: str
    page_count: int
    created_at: float
    pages: List[Dict[str, Any]] = field(default_factory=list)
    raster_cache: OrderedDict[str, bytes] = field(default_factory=OrderedDict)


_PDF_STORE: Dict[str, PdfSession] = {}


class CropBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=1)
    height: float = Field(gt=1)


class ImageRender(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    scale: float = Field(gt=0)


class PdfExtractRequest(BaseModel):
    pdf_id: str
    mode: str  # crop | page | document
    page_index: Optional[int] = None
    crop: Optional[CropBox] = None
    image_render: Optional[ImageRender] = None
    question_text: Optional[str] = None
    engine_choice: str = "pix2text"


def _owner_key(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth:
        return f"auth:{hashlib.sha256(auth.encode('utf-8')).hexdigest()}"
    host = request.client.host if request.client else "unknown"
    agent = request.headers.get("user-agent", "")
    return f"anon:{hashlib.sha256(f'{host}|{agent}'.encode('utf-8')).hexdigest()}"


def _cleanup_expired() -> None:
    now = time.time()
    stale: List[str] = []
    with _LOCK:
        for pdf_id, session in _PDF_STORE.items():
            if now - session.created_at > PDF_TTL_SECONDS:
                stale.append(pdf_id)
        for pdf_id in stale:
            sess = _PDF_STORE.pop(pdf_id, None)
            if sess and os.path.exists(sess.path):
                try:
                    os.remove(sess.path)
                except OSError:
                    pass


def _assert_pdf_enabled() -> None:
    if not PDF_ENABLED:
        raise HTTPException(status_code=403, detail={"error_code": "PDF_DISABLED", "message": "PDF mode is disabled."})


def _rate_limit(request: Request, endpoint: str, limit: int, window_sec: int = 60) -> None:
    key = f"{endpoint}:{_owner_key(request)}"
    now = time.time()
    with _RATE_LOCK:
        entries = _rate_windows.get(key, [])
        entries = [t for t in entries if now - t < window_sec]
        if len(entries) >= limit:
            raise HTTPException(
                status_code=429,
                detail={"error_code": "RATE_LIMITED", "message": "Too many requests. Please slow down."},
            )
        entries.append(now)
        _rate_windows[key] = entries


def _load_session(request: Request, pdf_id: str) -> PdfSession:
    _cleanup_expired()
    with _LOCK:
        session = _PDF_STORE.get(pdf_id)
    if not session:
        raise HTTPException(status_code=404, detail={"error_code": "PDF_NOT_FOUND", "message": "PDF session expired or missing."})
    if session.owner_key != _owner_key(request):
        raise HTTPException(status_code=403, detail={"error_code": "PDF_FORBIDDEN", "message": "This PDF session is not yours."})
    return session


def _render_page_png(session: PdfSession, page_index: int, scale: float) -> Tuple[bytes, int, int]:
    key = f"{page_index}:{scale:.3f}"
    if key in session.raster_cache:
        data = session.raster_cache.pop(key)
        session.raster_cache[key] = data
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.width, img.height
        return data, width, height

    pdf = pdfium.PdfDocument(session.path)
    page = pdf.get_page(page_index)
    try:
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()
        max_dim = max(pil.width, pil.height)
        if max_dim > PDF_RENDER_MAX_DIM:
            ratio = PDF_RENDER_MAX_DIM / float(max_dim)
            pil = pil.resize((max(1, int(pil.width * ratio)), max(1, int(pil.height * ratio))), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        pil.save(out, format="PNG")
        data = out.getvalue()
    finally:
        page.close()
        pdf.close()

    session.raster_cache[key] = data
    while len(session.raster_cache) > PDF_RASTER_CACHE_SIZE:
        session.raster_cache.popitem(last=False)
    return data, pil.width, pil.height


def _extract_questions_from_image(image_bytes: bytes, engine_choice: str, page_index: Optional[int] = None) -> List[Dict[str, Any]]:
    engine_name = "local" if engine_choice == "pix2text" else "auto"
    ocr = ocr_service.recognize_region(image_bytes, engine_name=engine_name)
    text = (ocr.get("text") or "").strip()
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        lines = [text]
    questions: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines[:30]):
        questions.append(
            {
                "id": f"q_{page_index if page_index is not None else 'doc'}_{idx+1}",
                "text": line,
                "confidence": float(ocr.get("confidence") or 0.7),
                "is_valid_math": True,
                "source_page_index": page_index,
            }
        )
    return questions


def _clamp_scale(scale: float) -> float:
    return max(PDF_RENDER_SCALE_MIN, min(PDF_RENDER_SCALE_MAX, scale))


@router.post("/snap-solve/pdf/prepare")
async def snap_solve_pdf_prepare(request: Request, file: UploadFile = File(...)):
    _assert_pdf_enabled()
    _cleanup_expired()
    _rate_limit(request, "pdf_prepare", PDF_RATE_LIMIT_PREPARE)

    content_type = (file.content_type or "").lower()
    if content_type != "application/pdf":
        raise HTTPException(status_code=415, detail={"error_code": "PDF_INVALID_MIME", "message": "Only PDF files are accepted."})
    raw = await file.read()
    if len(raw) > PDF_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error_code": "PDF_TOO_LARGE", "message": f"PDF exceeds {PDF_MAX_MB}MB limit."},
        )
    if not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail={"error_code": "PDF_INVALID", "message": "Invalid PDF signature."})

    pdf_id = str(uuid.uuid4())
    path = os.path.join(STORE_ROOT, f"{pdf_id}.pdf")
    with open(path, "wb") as handle:
        handle.write(raw)

    try:
        doc = pdfium.PdfDocument(path)
        page_count = len(doc)
    except Exception:
        raise HTTPException(status_code=400, detail={"error_code": "PDF_PARSE_FAILED", "message": "Unable to parse PDF."})
    if page_count <= 0:
        raise HTTPException(status_code=400, detail={"error_code": "PDF_EMPTY", "message": "PDF has no pages."})
    if page_count > PDF_MAX_PAGES:
        raise HTTPException(
            status_code=413,
            detail={"error_code": "PDF_TOO_MANY_PAGES", "message": f"PDF exceeds max pages ({PDF_MAX_PAGES})."},
        )

    pages: List[Dict[str, Any]] = []
    for i in range(page_count):
        page = doc.get_page(i)
        width, height = page.get_size()
        pages.append({"index": i, "width_px": int(width), "height_px": int(height)})

    session = PdfSession(
        pdf_id=pdf_id,
        owner_key=_owner_key(request),
        path=path,
        page_count=page_count,
        created_at=time.time(),
        pages=pages,
    )
    with _LOCK:
        _PDF_STORE[pdf_id] = session
    return {"pdf_id": pdf_id, "page_count": page_count, "pages": pages}


@router.get("/snap-solve/pdf/page-image")
async def snap_solve_pdf_page_image(
    request: Request,
    pdf_id: str = Query(...),
    page_index: int = Query(..., ge=0),
    scale: float = Query(1.5, gt=0),
):
    _assert_pdf_enabled()
    _rate_limit(request, "pdf_page_image", PDF_RATE_LIMIT_PAGE_IMAGE)
    session = _load_session(request, pdf_id)
    if page_index >= session.page_count:
        raise HTTPException(status_code=400, detail={"error_code": "PDF_PAGE_RANGE", "message": "page_index out of range."})
    clamped_scale = _clamp_scale(scale)
    png_bytes, width, height = _render_page_png(session, page_index, clamped_scale)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "X-Page-Width": str(width),
            "X-Page-Height": str(height),
            "X-Render-Scale": str(clamped_scale),
            "X-Render-Scale-Requested": str(scale),
            "Cache-Control": "private, max-age=120",
        },
    )


@router.post("/snap-solve/pdf/extract")
async def snap_solve_pdf_extract(request: Request, body: PdfExtractRequest):
    _assert_pdf_enabled()
    _rate_limit(request, "pdf_extract", PDF_RATE_LIMIT_EXTRACT)
    session = _load_session(request, body.pdf_id)
    mode = body.mode.lower().strip()
    if mode not in {"crop", "page", "document"}:
        raise HTTPException(status_code=400, detail={"error_code": "PDF_MODE_INVALID", "message": "mode must be crop|page|document"})
    if mode == "document" and not PDF_DOCUMENT_EXTRACT_ENABLED:
        raise HTTPException(status_code=403, detail={"error_code": "PDF_DOCUMENT_DISABLED", "message": "Document extraction is disabled."})

    extracted: List[Dict[str, Any]] = []
    warnings: List[str] = []
    pages_processed = 0
    started = time.perf_counter()

    if mode in {"crop", "page"}:
        if body.page_index is None:
            raise HTTPException(status_code=400, detail={"error_code": "PDF_PAGE_REQUIRED", "message": "page_index is required."})
        if body.page_index < 0 or body.page_index >= session.page_count:
            raise HTTPException(status_code=400, detail={"error_code": "PDF_PAGE_RANGE", "message": "page_index out of range."})
        scale = _clamp_scale(float(body.image_render.scale)) if body.image_render else 1.5
        png_bytes, width, height = _render_page_png(session, body.page_index, scale)
        image = Image.open(io.BytesIO(png_bytes)).convert("RGB")

        if mode == "crop":
            if not body.crop:
                raise HTTPException(status_code=400, detail={"error_code": "PDF_CROP_REQUIRED", "message": "crop is required for crop mode."})
            x0 = int(max(0, min(width - 1, body.crop.x)))
            y0 = int(max(0, min(height - 1, body.crop.y)))
            x1 = int(max(x0 + 1, min(width, body.crop.x + body.crop.width)))
            y1 = int(max(y0 + 1, min(height, body.crop.y + body.crop.height)))
            if (x1 - x0) < 8 or (y1 - y0) < 8:
                raise HTTPException(status_code=400, detail={"error_code": "PDF_CROP_TOO_SMALL", "message": "Crop area is too small."})
            image = image.crop((x0, y0, x1, y1))

        out = io.BytesIO()
        image.save(out, format="PNG")
        extracted = _extract_questions_from_image(out.getvalue(), body.engine_choice, page_index=body.page_index)
    else:
        doc_started = time.perf_counter()
        max_pages = min(session.page_count, PDF_DOCUMENT_MAX_PAGES)
        if session.page_count > PDF_DOCUMENT_MAX_PAGES:
            warnings.append(f"Document extraction capped at {PDF_DOCUMENT_MAX_PAGES} pages.")
        for page_index in range(max_pages):
            elapsed_ms = int((time.perf_counter() - doc_started) * 1000)
            if elapsed_ms >= PDF_DOCUMENT_TIME_BUDGET_MS:
                warnings.append("Document extraction stopped due to time budget.")
                break
            png_bytes, _, _ = _render_page_png(session, page_index, scale=1.5)
            page_questions = _extract_questions_from_image(png_bytes, body.engine_choice, page_index=page_index)
            extracted.extend(page_questions)
            pages_processed += 1

    latency = int((time.perf_counter() - started) * 1000)
    if mode in {"crop", "page"}:
        pages_processed = 1
    return {
        "extracted_questions": extracted,
        "meta": {
            "mode": mode,
            "page_index": body.page_index,
            "pdf_id": body.pdf_id,
            "latency_ms": latency,
            "question_text": body.question_text or "",
            "warnings": warnings,
            "pages_processed": pages_processed,
        },
    }
