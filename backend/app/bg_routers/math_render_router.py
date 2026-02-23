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


class LegacyMathSvgRequest(BaseModel):
    tex: str = Field(default="")
    display: bool = Field(default=False)


class LegacyMathSvgBatchItem(BaseModel):
    tex: str = Field(default="")
    display: bool = Field(default=False)


class LegacyMathSvgBatchRequest(BaseModel):
    items: List[LegacyMathSvgBatchItem] = Field(default_factory=list)


@router.post("/render")
async def render_math_svg(req: MathRenderRequest):
    service = get_math_render_service()
    # Never-break mode: per-item errors, no request-wide failure for bad formulas.
    payload = await service.render_batch(
        items=[item.model_dump() for item in req.items],
        options=req.options.model_dump(),
    )
    return JSONResponse(payload)


@router.post("/svg")
async def render_math_svg_legacy(req: LegacyMathSvgRequest):
    """
    Backward-compatible endpoint used by frontend MathSvg component.
    Request: { tex: string, display: boolean }
    Response: { ok: boolean, svg?: string, key?: string, error?: string }
    """
    service = get_math_render_service()
    payload = await service.render_batch(
        items=[
            {
                "latex": req.tex,
                "display_mode": bool(req.display),
                "macros": {},
                "scale": 1.0,
            }
        ],
        options=MathRenderOptions().model_dump(),
    )
    results = payload.get("results") if isinstance(payload, dict) else []
    first = results[0] if isinstance(results, list) and results else {}
    if not isinstance(first, dict):
        first = {}
    ok = bool(first.get("ok"))
    if ok:
        return JSONResponse(
            {
                "ok": True,
                "svg": first.get("svg") or "",
                "key": first.get("key"),
                "metrics": first.get("metrics") if isinstance(first.get("metrics"), dict) else None,
            }
        )
    error_obj = first.get("error") if isinstance(first.get("error"), dict) else {}
    return JSONResponse(
        {
            "ok": False,
            "error": error_obj.get("message") or "Math SVG render failed.",
            "code": error_obj.get("code") or "RENDER_FAIL",
            "fallback_text": first.get("fallback_text") or req.tex,
            "key": first.get("key"),
        },
        status_code=200,
    )


@router.post("/svg/batch")
async def render_math_svg_batch_legacy(req: LegacyMathSvgBatchRequest):
    """
    Backward-compatible endpoint used by UnifiedMathRenderer batch client.
    Request: { items: [{ tex: string, display: boolean }] }
    Response: { results: [{ ok, svg?, error?, key? }, ...] }
    """
    service = get_math_render_service()
    payload = await service.render_batch(
        items=[
            {
                "latex": item.tex,
                "display_mode": bool(item.display),
                "macros": {},
                "scale": 1.0,
            }
            for item in req.items
        ],
        options=MathRenderOptions().model_dump(),
    )
    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list):
        results = []
    normalized: List[Dict[str, Any]] = []
    for row in results:
        if not isinstance(row, dict):
            normalized.append({"ok": False, "error": "Math SVG render failed."})
            continue
        if bool(row.get("ok")):
            normalized.append(
                {
                    "ok": True,
                    "svg": row.get("svg") or "",
                    "key": row.get("key"),
                    "metrics": row.get("metrics") if isinstance(row.get("metrics"), dict) else None,
                }
            )
            continue
        error_obj = row.get("error") if isinstance(row.get("error"), dict) else {}
        normalized.append(
            {
                "ok": False,
                "error": error_obj.get("message") or "Math SVG render failed.",
                "code": error_obj.get("code") or "RENDER_FAIL",
                "fallback_text": row.get("fallback_text") or "",
                "key": row.get("key"),
            }
        )
    return JSONResponse({"results": normalized})


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

