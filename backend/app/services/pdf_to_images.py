from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import fitz


DEBUG_RENDER_ROOT = Path(os.getenv("GLMOCR_DEBUG_RENDER_DIR", "storage/glmocr_debug"))
DEFAULT_PDF_SCALE = float(os.getenv("GLMOCR_PDF_RENDER_SCALE", "2.2"))


def _normalize_page_selection(*, total_pages: int, pages: Optional[Sequence[int]], max_pages: int) -> List[int]:
    if total_pages <= 0:
        return []
    if pages:
        selected = sorted({int(p) for p in pages if 1 <= int(p) <= total_pages})
        return selected[:max_pages]
    return list(range(1, min(total_pages, max_pages) + 1))


def render_pdf_to_images(
    *,
    pdf_bytes: bytes,
    request_id: str,
    pages: Optional[Sequence[int]],
    max_pages: int,
    keep_rendered_pages: bool = True,
    scale: float = DEFAULT_PDF_SCALE,
) -> Tuple[List[Tuple[int, bytes]], Optional[str], int]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = document.page_count
    selected_pages = _normalize_page_selection(total_pages=total_pages, pages=pages, max_pages=max_pages)
    if not selected_pages:
        return [], None, total_pages

    debug_dir = DEBUG_RENDER_ROOT / request_id if keep_rendered_pages else None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    rendered: List[Tuple[int, bytes]] = []
    matrix = fitz.Matrix(scale, scale)
    for page_num in selected_pages:
        page = document.load_page(page_num - 1)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        png_bytes = pix.tobytes("png")
        rendered.append((page_num, png_bytes))
        if debug_dir:
            (debug_dir / f"page_{page_num:04d}.png").write_bytes(png_bytes)

    document.close()
    return rendered, str(debug_dir) if debug_dir else None, total_pages
