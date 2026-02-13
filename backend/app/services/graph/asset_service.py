from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

from sqlmodel import Session, select

from app.models import SolverOutputAttempt
from app.services.graph.mpl_render import canonical_plot_hash_payload, render_graph

logger = logging.getLogger(__name__)

GRAPH_CACHE_TTL_SECONDS = 60 * 60


def _storage_dir() -> Path:
    base = Path(__file__).resolve().parents[3]
    path = base / "storage" / "attempt_graphs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extract_plot_spec(validation_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    problem = validation_json.get("problem") if isinstance(validation_json.get("problem"), dict) else {}
    fallback_title = (
        (problem or {}).get("goal")
        or (problem or {}).get("original_text")
        or (problem or {}).get("normalized_text")
        or "Graph"
    )
    visuals = validation_json.get("visuals")
    if not isinstance(visuals, dict):
        return None
    plots = visuals.get("plots")
    if not isinstance(plots, list) or not plots:
        return None
    first = plots[0]
    if not isinstance(first, dict):
        return None
    first_title = str(first.get("title") or "").strip()
    is_generic = first_title.lower() in {"plot_matplotlib_fallback", "plot", "graph", "chart"} or first_title.lower().startswith("plot_")
    key_points = _extract_key_points(validation_json)
    expression_label = _extract_expression_label(validation_json)
    if isinstance(first.get("plotly_json"), dict):
        return {
            "title": fallback_title if is_generic else (first_title or fallback_title),
            "axes": {
                "x_label": first.get("x_label") or "x",
                "y_label": first.get("y_label") or "y",
            },
            "plotly_json": first.get("plotly_json"),
            "key_points": key_points,
            "expression_label": expression_label,
        }
    if not first.get("title") or is_generic:
        first = {**first, "title": fallback_title}
    if key_points:
        first = {**first, "key_points": key_points}
    if expression_label:
        first = {**first, "expression_label": expression_label}
    return first


def _extract_key_points(validation_json: Dict[str, Any]) -> List[Dict[str, float]]:
    points: List[Dict[str, float]] = []
    final_answer = validation_json.get("final_answer") if isinstance(validation_json.get("final_answer"), dict) else {}
    values = final_answer.get("values") if isinstance(final_answer, dict) and isinstance(final_answer.get("values"), list) else []
    for entry in values:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip().lower()
        raw = str(entry.get("value_latex") or entry.get("value") or "").strip()
        if not raw:
            continue
        if label and all(k not in label for k in ("extreme", "vertex", "maximum", "minimum", "point")):
            continue
        match = re.search(r"\(?\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)?", raw)
        if not match:
            continue
        try:
            x = float(match.group(1))
            y = float(match.group(2))
        except (TypeError, ValueError):
            continue
        points.append({"x": x, "y": y, "label": "reference"})
    return points


def _extract_expression_label(validation_json: Dict[str, Any]) -> str:
    problem = validation_json.get("problem") if isinstance(validation_json.get("problem"), dict) else {}
    candidates = [
        str((problem or {}).get("normalized_text") or "").strip(),
        str((problem or {}).get("original_text") or "").strip(),
    ]
    for text in candidates:
        if not text:
            continue
        # Prefer explicit function forms only for legend clarity.
        if "=" in text and ("x" in text or "f(x)" in text or "y" in text):
            cleaned = re.sub(r"\s+", "", text)
            if len(cleaned) > 80:
                cleaned = cleaned[:77] + "..."
            return cleaned
    return ""


def _load_attempt_with_access(session: Session, attempt_id: str, user_id: Optional[int]) -> Optional[SolverOutputAttempt]:
    if user_id is None:
        return session.exec(
            select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)
        ).first()
    attempt = session.exec(
        select(SolverOutputAttempt).where(
            SolverOutputAttempt.attempt_id == attempt_id,
            SolverOutputAttempt.user_id == user_id,
        )
    ).first()
    return attempt


def _cache_key(spec: Dict[str, Any], *, fmt: str, theme: str, width_px: int, height_px: int, dpi: int) -> str:
    payload = canonical_plot_hash_payload(
        spec,
        theme=theme,  # type: ignore[arg-type]
        width_px=width_px,
        height_px=height_px,
        dpi=dpi,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{digest}.{fmt}"


def _write_alias_pointer(attempt_id: str, filename: str) -> None:
    pointer = _storage_dir() / f"{attempt_id}.json"
    pointer.write_text(json.dumps({"file": filename}, separators=(",", ":")), encoding="utf-8")

def _try_redis_set(attempt_id: str, filename: str) -> None:
    try:
        from app.services.whatsapp.whatsapp_state import get_redis

        get_redis().setex(f"graph:attempt:{attempt_id}", GRAPH_CACHE_TTL_SECONDS, filename)
    except Exception:
        pass


def get_or_render_graph_bytes(
    session: Session,
    *,
    attempt_id: str,
    user_id: Optional[int] = None,
    fmt: str = "svg",
    theme: str = "light",
    width_px: int = 920,
    height_px: int = 520,
    dpi: int = 120,
) -> Tuple[Optional[bytes], Optional[str]]:
    if fmt not in {"svg", "png"}:
        return None, "invalid_format"

    attempt = _load_attempt_with_access(session, attempt_id, user_id)
    if attempt is None:
        return None, "attempt_not_found"
    if not isinstance(attempt.validation_json, dict):
        return None, "no_structured_output"

    spec = _extract_plot_spec(attempt.validation_json)
    if not spec:
        return None, "no_plot_spec"

    started = time.perf_counter()
    filename = _cache_key(spec, fmt=fmt, theme=theme, width_px=width_px, height_px=height_px, dpi=dpi)
    path = _storage_dir() / filename
    if path.exists():
        logger.info(
            "graph_render cache_hit=true attempt_id=%s fmt=%s bytes=%s",
            attempt_id,
            fmt,
            path.stat().st_size,
        )
        _write_alias_pointer(attempt_id, filename)
        _try_redis_set(attempt_id, filename)
        return path.read_bytes(), None

    try:
        rendered_bytes, meta = render_graph(
            spec,
            width_px=width_px,
            height_px=height_px,
            dpi=dpi,
            theme=theme if theme in {"light", "dark"} else "light",
            fmt=fmt,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.warning("graph_render failed attempt_id=%s reason=%s", attempt_id, str(exc))
        return None, "render_failed"

    path.write_bytes(rendered_bytes)
    _write_alias_pointer(attempt_id, filename)
    _try_redis_set(attempt_id, filename)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "graph_render cache_hit=false attempt_id=%s fmt=%s render_ms=%s output_bytes=%s plot_type=%s",
        attempt_id,
        fmt,
        elapsed_ms,
        len(rendered_bytes),
        meta.plot_type,
    )
    return rendered_bytes, None


def pre_render_attempt_graph(
    session: Session,
    *,
    attempt_id: str,
    user_id: int,
    theme: str = "light",
) -> bool:
    data, err = get_or_render_graph_bytes(
        session,
        attempt_id=attempt_id,
        user_id=user_id,
        fmt="svg",
        theme=theme,
    )
    return data is not None and err is None
