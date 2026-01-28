from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel, Field, confloat
from typing import Optional, Dict, Any, List
import time
import uuid
import os
import base64
import io
from PIL import Image

from app.db import get_session
from app.models import Crop
from app.services.ocr.ocr_service import ocr_service
from app.services.ocr.crop_service import STORAGE_DIR
from app.services.math.error_localizer import (
    OCRPayload, Budget, find_first_error_from_ocr
)

router = APIRouter()

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
    error: Optional[Dict[str, str]] = None
    timings_ms: Dict[str, int]

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
