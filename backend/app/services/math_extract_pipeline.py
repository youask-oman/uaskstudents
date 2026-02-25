from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.services.glmocr_direct import parse_image_with_ollama_generate
from app.services.math_extract_normalize import normalize_math_extraction
from app.services.pdf_to_images import render_pdf_to_images
from app.services.quality_score import compute_quality_score


logger = logging.getLogger(__name__)

OBSERVABILITY_JSONL_PATH = Path(os.getenv("GLMOCR_OBSERVABILITY_JSONL", "reports/glmocr_extract_requests.jsonl"))


async def run_math_extraction_pipeline(
    *,
    request_id: str,
    source_type: str,
    filename: str,
    content_bytes: bytes,
    pages: Optional[Sequence[int]] = None,
    max_pages: int = 5,
    enable_layout: bool = True,
    keep_rendered_pages: bool = True,
) -> Dict[str, Any]:
    del enable_layout
    source_type_norm = (source_type or "").strip().lower()
    if source_type_norm not in {"pdf", "image"}:
        raise ValueError("source_type must be pdf or image")

    started = time.perf_counter()
    warnings: List[str] = []
    backend_used = "unknown"
    page_numbers: List[int] = []
    page_count: Optional[int] = None
    rendered_debug_dir: Optional[str] = None

    markdown_chunks: List[str] = []
    json_chunks: List[Dict[str, Any]] = []

    if source_type_norm == "pdf":
        rendered_pages, rendered_debug_dir, total_pages = render_pdf_to_images(
            pdf_bytes=content_bytes,
            request_id=request_id,
            pages=pages,
            max_pages=max_pages,
            keep_rendered_pages=keep_rendered_pages,
        )
        page_count = total_pages
        for page_num, image_bytes in rendered_pages:
            page_numbers.append(page_num)
            parsed = await parse_image_with_ollama_generate(
                image_bytes,
                request_id=request_id,
                mime_type="image/png",
                filename=f"{filename}#page={page_num}",
            )
            backend_used = parsed.get("backend_used", backend_used)
            warnings.extend(parsed.get("warnings") or [])
            markdown_chunks.append(str(parsed.get("markdown_result") or ""))
            json_payload = parsed.get("json_result")
            if isinstance(json_payload, dict):
                json_payload = dict(json_payload)
                json_payload["page"] = page_num
            else:
                json_payload = {"page": page_num, "raw": json_payload}
            json_chunks.append(json_payload)
    else:
        page_numbers = [1]
        parsed = await parse_image_with_ollama_generate(
            content_bytes,
            request_id=request_id,
            mime_type=_guess_mime_type(filename),
            filename=filename,
        )
        backend_used = parsed.get("backend_used", backend_used)
        warnings.extend(parsed.get("warnings") or [])
        markdown_chunks.append(str(parsed.get("markdown_result") or ""))
        json_payload = parsed.get("json_result")
        json_chunks.append(json_payload if isinstance(json_payload, dict) else {"raw": json_payload})

    merged_markdown = "\n\n".join(chunk.strip() for chunk in markdown_chunks if chunk and chunk.strip()).strip()
    merged_json: Dict[str, Any] = {
        "pages": json_chunks if source_type_norm == "pdf" else None,
        "result": json_chunks[0] if source_type_norm == "image" and json_chunks else {},
    }

    normalized = normalize_math_extraction(merged_markdown, merged_json)
    quality_score, quality_warnings = compute_quality_score(
        str(normalized.get("question_text") or ""),
        str(normalized.get("markdown") or ""),
    )
    warnings.extend(quality_warnings)
    warnings = sorted({str(w) for w in warnings if w})

    runtime_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "math_extract request_id=%s filename=%s type=%s pages=%s runtime_ms=%s quality_score=%.3f warnings=%s backend_used=%s",
        request_id,
        filename,
        source_type_norm,
        page_numbers,
        runtime_ms,
        quality_score,
        warnings,
        backend_used,
    )
    _emit_jsonl_observation(
        request_id=request_id,
        filename=filename,
        source_type=source_type_norm,
        pages=page_numbers,
        runtime_ms=runtime_ms,
        quality_score=quality_score,
        warnings=warnings,
        backend_used=backend_used,
    )

    return {
        "source": {
            "filename": filename,
            "type": source_type_norm,
            "pages": page_numbers,
            "page_count": page_count,
            "rendered_debug_dir": rendered_debug_dir,
        },
        "extraction": {
            "question_text": normalized.get("question_text", ""),
            "question_latex": normalized.get("question_latex", ""),
            "markdown": normalized.get("markdown", ""),
            "json": normalized.get("json", {}),
            "warnings": warnings,
            "quality_score": quality_score,
            "backend_used": backend_used,
            "runtime_ms": runtime_ms,
        },
    }


def _guess_mime_type(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _emit_jsonl_observation(
    *,
    request_id: str,
    filename: str,
    source_type: str,
    pages: List[int],
    runtime_ms: int,
    quality_score: float,
    warnings: List[str],
    backend_used: str,
) -> None:
    try:
        OBSERVABILITY_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "request_id": request_id,
            "filename": filename,
            "type": source_type,
            "pages_processed": pages,
            "runtime_ms": runtime_ms,
            "quality_score": quality_score,
            "warnings": warnings,
            "backend_used": backend_used,
        }
        with OBSERVABILITY_JSONL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("failed_to_write_glmocr_jsonl request_id=%s", request_id)
