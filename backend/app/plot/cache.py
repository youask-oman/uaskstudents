from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.whatsapp.whatsapp_state import get_redis
from app.plot.recipe_normalizer import normalize_recipe


PLOT_RENDERER_VERSION = "plot_svg_renderer_v2"
PLOT_SVG_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30
PLOT_SVG_CACHE_DIR = Path(
    os.environ.get(
        "PLOT_SVG_CACHE_DIR",
        str(Path(__file__).resolve().parents[2] / "storage" / "plot_svg_cache"),
    )
)


def _ensure_cache_dir() -> Path:
    PLOT_SVG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return PLOT_SVG_CACHE_DIR


def canonical_plot_payload(plot_recipe: Dict[str, Any], render_options: Dict[str, Any]) -> str:
    normalized_recipe, _ = normalize_recipe(plot_recipe if isinstance(plot_recipe, dict) else {})
    payload = {
        "renderer_version": PLOT_RENDERER_VERSION,
        "plot_recipe": normalized_recipe,
        "render_options": render_options,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_cache_key(plot_recipe: Dict[str, Any], render_options: Dict[str, Any]) -> str:
    canonical = canonical_plot_payload(plot_recipe, render_options)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _redis_key(cache_key: str) -> str:
    return f"plot:svg:{cache_key}"


def get_cached_svg(cache_key: str) -> Optional[str]:
    try:
        raw = get_redis().get(_redis_key(cache_key))
        if raw:
            return str(raw)
    except Exception:
        pass

    disk = _ensure_cache_dir() / f"{cache_key.replace(':', '_')}.svg"
    if disk.exists():
        try:
            return disk.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def set_cached_svg(cache_key: str, svg: str) -> None:
    if not svg:
        return
    try:
        get_redis().setex(_redis_key(cache_key), PLOT_SVG_CACHE_TTL_SECONDS, svg)
    except Exception:
        pass

    disk = _ensure_cache_dir() / f"{cache_key.replace(':', '_')}.svg"
    try:
        disk.write_text(svg, encoding="utf-8")
    except Exception:
        pass
