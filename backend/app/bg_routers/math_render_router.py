from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.services.math_render_service import get_math_render_service


router = APIRouter(prefix="/math", tags=["math_render"])


class MathRenderItem(BaseModel):
    latex: str = Field(default="")
    display_mode: bool = Field(default=False)
    macros: Dict[str, Any] = Field(default_factory=dict)
    scale: float = Field(default=1.0)


class MathRenderOptions(BaseModel):
    font: str = Field(default="tex")
    sanitize: bool = Field(default=True)
    return_metrics: bool = Field(default=True)


class MathRenderRequest(BaseModel):
    items: List[MathRenderItem] = Field(default_factory=list)
    options: MathRenderOptions = Field(default_factory=MathRenderOptions)


@router.post("/render")
async def render_math_svg(req: MathRenderRequest):
    service = get_math_render_service()
    # Never-break mode: per-item errors, no request-wide failure for bad formulas.
    payload = await service.render_batch(
        items=[item.model_dump() for item in req.items],
        options=req.options.model_dump(),
    )
    return JSONResponse(payload)


@router.get("/svg/{key}.svg")
async def get_cached_svg(key: str):
    service = get_math_render_service()
    svg_text: Optional[str] = await service.get_svg_by_key(key)
    if not svg_text:
        return JSONResponse({"error": {"code": "not_found", "message": "SVG not found"}, "key": key}, status_code=404)
    headers = {
        "Content-Type": "image/svg+xml",
        "Content-Security-Policy": "script-src 'none'; object-src 'none'",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "public, max-age=86400",
    }
    return Response(content=svg_text, media_type="image/svg+xml", headers=headers)

