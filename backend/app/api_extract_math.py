from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.math_extract_pipeline import run_math_extraction_pipeline


router = APIRouter(prefix="/api/extract", tags=["extract"])

MAX_UPLOAD_BYTES = int(os.getenv("MATH_EXTRACT_MAX_UPLOAD_BYTES", str(30 * 1024 * 1024)))
GLMOCR_DEV_LOCAL_PATHS_ENABLED = os.getenv("GLMOCR_DEV_LOCAL_PATHS_ENABLED", "false").lower() in {"1", "true", "yes"}


class ExtractSource(BaseModel):
    filename: str
    type: str
    pages: List[int]
    page_count: Optional[int] = None
    rendered_debug_dir: Optional[str] = None


class ExtractPayload(BaseModel):
    question_text: str
    question_latex: str
    markdown: str
    json: dict
    warnings: List[str]
    quality_score: float = Field(ge=0.0, le=1.0)
    backend_used: str


class MathQuestionExtractResponse(BaseModel):
    source: ExtractSource
    extraction: ExtractPayload


def _parse_pages(raw_pages: Optional[str]) -> Optional[List[int]]:
    if not raw_pages:
        return None
    raw_pages = raw_pages.strip()
    if not raw_pages:
        return None
    if raw_pages.startswith("["):
        arr = json.loads(raw_pages)
        return [int(x) for x in arr]
    return [int(x.strip()) for x in raw_pages.split(",") if x.strip()]


@router.post("/math-question", response_model=MathQuestionExtractResponse)
async def extract_math_question(
    source_type: str = Form(...),
    file: Optional[UploadFile] = File(default=None),
    local_path: Optional[str] = Form(default=None),
    pages: Optional[str] = Form(default=None),
    max_pages: int = Form(default=5),
    enable_layout: bool = Form(default=True),
    keep_rendered_pages: bool = Form(default=True),
):
    source_type_norm = (source_type or "").strip().lower()
    if source_type_norm not in {"pdf", "image"}:
        raise HTTPException(status_code=400, detail="source_type must be pdf or image")

    request_id = str(uuid.uuid4())
    try:
        parsed_pages = _parse_pages(pages)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid pages parameter: {exc}") from exc
    max_pages = max(1, min(int(max_pages), 30))

    filename = ""
    content_bytes: bytes
    if file is not None:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if len(content_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Upload too large")
        filename = file.filename or f"upload-{request_id}"
    elif local_path:
        if not GLMOCR_DEV_LOCAL_PATHS_ENABLED:
            raise HTTPException(status_code=403, detail="local_path is disabled")
        path_obj = Path(local_path).expanduser()
        if not path_obj.exists() or not path_obj.is_file():
            raise HTTPException(status_code=404, detail="local_path not found")
        filename = path_obj.name
        content_bytes = path_obj.read_bytes()
    else:
        raise HTTPException(status_code=400, detail="Provide file upload or local_path")

    try:
        result = await run_math_extraction_pipeline(
            request_id=request_id,
            source_type=source_type_norm,
            filename=filename,
            content_bytes=content_bytes,
            pages=parsed_pages,
            max_pages=max_pages,
            enable_layout=bool(enable_layout),
            keep_rendered_pages=bool(keep_rendered_pages),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {type(exc).__name__}: {exc}") from exc

    source = result.get("source") or {}
    extraction = result.get("extraction") or {}
    return MathQuestionExtractResponse(
        source=ExtractSource(
            filename=str(source.get("filename") or filename),
            type=str(source.get("type") or source_type_norm),
            pages=[int(x) for x in (source.get("pages") or [])],
            page_count=(int(source.get("page_count")) if source.get("page_count") is not None else None),
            rendered_debug_dir=(str(source.get("rendered_debug_dir")) if source.get("rendered_debug_dir") else None),
        ),
        extraction=ExtractPayload(
            question_text=str(extraction.get("question_text") or ""),
            question_latex=str(extraction.get("question_latex") or ""),
            markdown=str(extraction.get("markdown") or ""),
            json=extraction.get("json") if isinstance(extraction.get("json"), dict) else {"raw": extraction.get("json")},
            warnings=[str(w) for w in (extraction.get("warnings") or [])],
            quality_score=float(extraction.get("quality_score") or 0.0),
            backend_used=str(extraction.get("backend_used") or "unknown"),
        ),
    )

