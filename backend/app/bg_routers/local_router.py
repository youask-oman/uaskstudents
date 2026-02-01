from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlmodel import Session, select
from pydantic import BaseModel, Field, confloat
from typing import Optional, Dict, Any, List
import time
import uuid
import os
import base64
import io
from PIL import Image
import logging

from app.database import get_session
from app.models import Crop
from app.services.ocr.ocr_service import ocr_service
from app.services.ocr.crop_service import STORAGE_DIR
from app.services.solver_v3 import get_solver_v3
from app.services.math.error_localizer import (
    OCRPayload, Budget, find_first_error_from_ocr
)
from app.services.math.step_generator import generate_local_steps

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = int(os.getenv("SNAP_SOLVE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_DIM = int(os.getenv("SNAP_SOLVE_MAX_IMAGE_DIM", "2000"))
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_UPLOAD_MIME = ALLOWED_IMAGE_MIME | {"application/pdf"}

class BBox(BaseModel):
    x: confloat(ge=0.0, le=1.0)
    y: confloat(ge=0.0, le=1.0)
    w: confloat(gt=0.0, le=1.0)
    h: confloat(gt=0.0, le=1.0)

class FindErrorLocalRequest(BaseModel):
    crop_hash: Optional[str] = Field(None, min_length=8, max_length=128)
    image_data: Optional[str] = None
    selection_bbox: BBox
    ocr_hint: Optional[str] = Field(default="math")
    max_lines: int = Field(default=6, ge=1, le=12)

class FindErrorLocalResponse(BaseModel):
    ok: bool
    request_id: str
    selection_bbox: BBox
    ocr: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    local_steps: Optional[List[str]] = None
    error: Optional[Dict[str, str]] = None
    timings_ms: Dict[str, int]


class SolveFromImageOrSketchResponse(BaseModel):
    answer_markdown: str
    answer_latex: Optional[str] = None
    meta: Dict[str, Any]

def load_cropped_image_by_hash(crop_hash: str, session: Session):
    """
    Return PIL image for the cropped image cached in pipeline.
    """
    # 1. Look up in DB
    crop_record = session.exec(select(Crop).where(Crop.crop_image_hash == crop_hash)).first()
    
    file_path = None
    if crop_record:
        file_path = crop_record.cropped_storage_url
    else:
        # Fallback to filesystem prediction
        filename = f"crop_{crop_hash[:16]}.png"
        file_path = os.path.join(STORAGE_DIR, filename)
    
    if file_path and os.path.exists(file_path):
        return Image.open(file_path)
    
    return None

def crop_region(pil_img, bbox: BBox):
    """
    Convert normalized bbox to pixel box and crop safely with clamping.
    """
    W, H = pil_img.size
    x0 = int(max(0, min(W-1, bbox.x * W)))
    y0 = int(max(0, min(H-1, bbox.y * H)))
    x1 = int(max(0, min(W, (bbox.x + bbox.w) * W)))
    y1 = int(max(0, min(H, (bbox.y + bbox.h) * H)))

    if (x1 - x0) < 25 or (y1 - y0) < 25:
        return None, {"code": "BBOX_TOO_SMALL", "message": "Selection too small. Re-circle a larger area."}

    return pil_img.crop((x0, y0, x1, y1)), None

def ocr_region_with_pix2text(pil_region):
    """
    Use LocalEngine (Pix2Text) from ocr_service.py.
    Return (raw_text, normalized_text, confidence).
    """
    # Convert PIL to bytes
    region_bytes_io = io.BytesIO()
    pil_region.save(region_bytes_io, format="PNG")
    region_bytes = region_bytes_io.getvalue()
    
    # Recognize
    ocr_out = ocr_service.recognize_region(region_bytes, engine_name="local")
    
    # Map result
    raw = ocr_out.get("raw", "")
    text = ocr_out.get("text", "")
    conf = ocr_out.get("confidence", 0.0)
    
    return raw, text, conf


def _validate_mime(mode: str, mime_type: str) -> None:
    if mode == "sketch":
        if mime_type != "image/png":
            raise HTTPException(status_code=400, detail="Sketch mode requires image/png.")
        return
    if mode == "upload":
        if mime_type not in ALLOWED_UPLOAD_MIME:
            raise HTTPException(status_code=400, detail="Unsupported upload MIME type.")
        return
    raise HTTPException(status_code=400, detail="mode must be 'upload' or 'sketch'.")


def _normalize_to_rgb(image: Image.Image, white_bg: bool = True) -> Image.Image:
    if image.mode in ("RGBA", "LA") and white_bg:
        alpha = image.convert("RGBA")
        background = Image.new("RGB", alpha.size, (255, 255, 255))
        background.paste(alpha, mask=alpha.split()[-1])
        return background
    if image.mode == "P":
        converted = image.convert("RGBA")
        background = Image.new("RGB", converted.size, (255, 255, 255))
        background.paste(converted, mask=converted.split()[-1])
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _downscale_if_needed(image: Image.Image, max_dim: int = MAX_IMAGE_DIM) -> Image.Image:
    w, h = image.size
    if max(w, h) <= max_dim:
        return image
    scale = max_dim / float(max(w, h))
    target = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(target, Image.Resampling.LANCZOS)


def _render_answer_markdown(result: Dict[str, Any]) -> Dict[str, Optional[str]]:
    content = result.get("_content")
    if isinstance(content, str) and content.strip():
        answer_latex = (
            result.get("final_answer", {}).get("answer_latex")
            if isinstance(result.get("final_answer"), dict)
            else None
        )
        return {"markdown": content.strip(), "latex": answer_latex}

    lines: List[str] = []
    problem = result.get("problem", {})
    if isinstance(problem, dict):
        original = problem.get("original_text") or problem.get("goal")
        if original:
            lines.append(f"**Problem**: {original}")

    steps = result.get("steps", [])
    if isinstance(steps, list) and steps:
        lines.append("")
        lines.append("### Steps")
        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            title = step.get("title") or f"Step {idx}"
            explanation = step.get("explanation") or ""
            lines.append(f"{idx}. **{title}**")
            if explanation:
                lines.append(f"   - {explanation}")

    final_answer = result.get("final_answer")
    answer_latex = None
    if isinstance(final_answer, dict):
        answer_text = final_answer.get("answer_text") or final_answer.get("answer") or ""
        answer_latex = final_answer.get("answer_latex")
    else:
        answer_text = str(final_answer or "")

    if answer_text or answer_latex:
        lines.append("")
        lines.append("### Final Answer")
        if answer_text:
            lines.append(answer_text)
        if answer_latex:
            lines.append(f"$$ {answer_latex} $$")

    markdown = "\n".join(lines).strip() or "No answer returned."
    return {"markdown": markdown, "latex": answer_latex}


@router.post("/find_error_local", response_model=FindErrorLocalResponse)
def find_error_local(req: FindErrorLocalRequest, session: Session = Depends(get_session)):
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    # Feature flag
    if not os.getenv("FEATURE_LOCAL_FIND_ERROR", "false").lower() == "true":
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            selection_bbox=req.selection_bbox,
            error={"code": "DISABLED", "message": "Local find-error is disabled."},
            timings_ms={"total": int((time.perf_counter()-t0)*1000)}
        )

    try:
        img = None
        # Load Image (Hash or Base64)
        if req.image_data:
            try:
                img_bytes = base64.b64decode(req.image_data)
                img = Image.open(io.BytesIO(img_bytes))
            except Exception as e:
                 return FindErrorLocalResponse(
                    ok=False, request_id=request_id, selection_bbox=req.selection_bbox,
                    error={"code": "INVALID_IMAGE", "message": "Invalid base64 data"},
                    timings_ms={"total": int((time.perf_counter()-t0)*1000)}
                )
        elif req.crop_hash:
            img = load_cropped_image_by_hash(req.crop_hash, session)
            
        if not img:
            return FindErrorLocalResponse(
                ok=False, request_id=request_id, selection_bbox=req.selection_bbox,
                error={"code": "IMAGE_NOT_FOUND", "message": "Could not retrieve source image"},
                timings_ms={"total": int((time.perf_counter()-t0)*1000)}
            )

        t_crop0 = time.perf_counter()
        if req.image_data:
            # If base64 is provided, the frontend already cropped to the selection
            region = img
            crop_err = None
        else:
            # Hash-based lookup requires cropping relative to the source image
            region, crop_err = crop_region(img, req.selection_bbox)
        
        crop_ms = int((time.perf_counter()-t_crop0)*1000)
        if crop_err:
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=req.selection_bbox,
                error=crop_err,
                timings_ms={"crop": crop_ms, "total": int((time.perf_counter()-t0)*1000)}
            )

        t_ocr0 = time.perf_counter()
        raw_text, norm_text, ocr_conf = ocr_region_with_pix2text(region)
        ocr_ms = int((time.perf_counter()-t_ocr0)*1000)

        # Cap raw text to avoid flooding logs/clients
        raw_text = (raw_text or "")[:500]
        norm_text = (norm_text or "")[:500]

        # Run local SymPy/SciPy checks
        t_chk0 = time.perf_counter()
        ocr_payload = OCRPayload(raw=raw_text, text=norm_text, confidence=float(ocr_conf or 0.0))
        budget = Budget(
            total_ms=int(os.getenv("LOCAL_FINDERR_TOTAL_MS", "1500")),
            sympy_ms=int(os.getenv("LOCAL_FINDERR_SYMPY_MS", "700")),
            numeric_ms=int(os.getenv("LOCAL_FINDERR_NUMERIC_MS", "700")),
        )
        result = find_first_error_from_ocr(ocr_payload, transcript_hint="find_error", max_lines=req.max_lines, budget=budget)
        chk_ms = int((time.perf_counter()-t_chk0)*1000)

        # Generate local steps if no definite error or if solving a prompt
        local_steps = []
        if not result.first_wrong_line_index or result.confidence < 0.3:
            local_steps = generate_local_steps(norm_text)


        return FindErrorLocalResponse(
            ok=True,
            request_id=request_id,
            selection_bbox=req.selection_bbox,
            ocr={
                "raw": raw_text[:120],          # keep UI readable
                "text": norm_text,
                "confidence": float(ocr_payload.confidence)
            },
            analysis={
                "detected_format": result.detected_format,
                "first_wrong_line_index": result.first_wrong_line_index,
                "what_is_wrong": result.what_is_wrong,
                "minimal_fix": result.minimal_fix,
                "confidence": float(result.confidence),
                "per_line": [
                    {
                        "ok": r.ok,
                        "confidence": float(r.confidence),
                        "reason": r.reason,
                        "minimal_fix": r.minimal_fix
                    } for r in result.per_line
                ]
            },
            local_steps=local_steps,
            timings_ms={
                "crop": crop_ms,
                "ocr": ocr_ms,
                "check": chk_ms,
                "total": int((time.perf_counter()-t0)*1000)
            }
        )

    except Exception as e:
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            selection_bbox=req.selection_bbox,
            error={"code": "INTERNAL_ERROR", "message": f"Failed to analyze selection: {str(e)}"},
            timings_ms={"total": int((time.perf_counter()-t0)*1000)}
        )


@router.post("/math/solve_from_image_or_sketch", response_model=SolveFromImageOrSketchResponse)
async def solve_from_image_or_sketch(
    request: Request,
    mode: str = Form(...),
    question_text: str = Form(""),
    image: Optional[UploadFile] = File(default=None),
    original_filename: Optional[str] = Form(default=None),
    client_context: Optional[str] = Form(default=None),
    session: Session = Depends(get_session),
):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    mode_normalized = (mode or "").strip().lower()
    image_mime = image.content_type if image else "text/plain"

    if mode_normalized not in {"upload", "sketch"}:
        raise HTTPException(status_code=400, detail="mode must be upload or sketch.")

    image_text = ""
    if image is not None:
        _validate_mime(mode_normalized, image_mime or "")
        raw_bytes = await image.read()
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds max upload size.")

        if image_mime == "application/pdf":
            raise HTTPException(status_code=400, detail="PDF is not enabled on this endpoint yet. Use legacy Snap flow.")

        try:
            pil_image = Image.open(io.BytesIO(raw_bytes))
            pil_image = _normalize_to_rgb(pil_image, white_bg=True)
            pil_image = _downscale_if_needed(pil_image, max_dim=MAX_IMAGE_DIM)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            preprocessed = buffer.getvalue()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image payload: {exc}") from exc

        ocr_result = ocr_service.recognize_region(preprocessed, engine_name=os.getenv("OCR_ENGINE", "auto"))
        image_text = (ocr_result.get("text") or "").strip()
        logger.info(
            "[snap_solve] request_id=%s mode=%s mime=%s extracted_chars=%s filename=%s",
            request_id,
            mode_normalized,
            image_mime,
            len(image_text),
            original_filename or getattr(image, "filename", None),
        )

    question_text = (question_text or "").strip()
    if not image_text and not question_text:
        raise HTTPException(status_code=400, detail="Provide an image/sketch or question text.")

    combined_prompt = question_text
    if image_text:
        combined_prompt = f"{question_text}\n\nExtracted content:\n{image_text}".strip()

    solver = get_solver_v3()
    solve_result = await solver.solve(
        problem_text=combined_prompt,
        context="",
        request_id=request_id,
        user_tier="free",
        requested_mode="minimal",
        db_session=session,
        trusted_context={"client_context": client_context} if client_context else None,
    )
    rendered = _render_answer_markdown(solve_result if isinstance(solve_result, dict) else {})
    latency_ms = int((time.perf_counter() - start) * 1000)

    return SolveFromImageOrSketchResponse(
        answer_markdown=rendered["markdown"] or "No answer returned.",
        answer_latex=rendered["latex"],
        meta={
            "mode": mode_normalized,
            "mime": image_mime,
            "latency_ms": latency_ms,
            "request_id": request_id,
        },
    )
