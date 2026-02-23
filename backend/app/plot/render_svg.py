from __future__ import annotations

import io
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "uask_plot_svg_v1"

import matplotlib.pyplot as plt
import numpy as np

from app.plot.sympy_safe import SympySafeError, compile_expr_1d, compile_expr_2d, latexish_to_sympy


DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 520
DEFAULT_FONT_SCALE = 1.0
MAX_ABS_BOUND = 10_000.0
MAX_FUNCTION_SAMPLES = 900
MAX_PARAMETRIC_SAMPLES = 900
MAX_IMPLICIT_GRID = 450


def _safe_float(value: Any, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(v):
        return default
    return v


def _normalized_domain(recipe: Dict[str, Any], key: str, default: Tuple[float, float]) -> Tuple[float, float]:
    obj = recipe.get(key) if isinstance(recipe.get(key), dict) else {}
    lo = _safe_float(obj.get("min"), default[0])
    hi = _safe_float(obj.get("max"), default[1])
    if lo == hi:
        hi = lo + 1.0
    if lo > hi:
        lo, hi = hi, lo
    lo = max(-MAX_ABS_BOUND, min(MAX_ABS_BOUND, lo))
    hi = max(-MAX_ABS_BOUND, min(MAX_ABS_BOUND, hi))
    if lo == hi:
        hi = lo + 1.0
    return lo, hi


def _to_svg_bytes(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", metadata={"Date": None})
    svg = buf.getvalue().decode("utf-8", errors="replace")
    svg = re.sub(r"<\?xml[\s\S]*?\?>", "", svg).strip()
    return svg


def _resolve_1d_expr(series: Dict[str, Any], *, kind: str) -> str:
    if kind == "function":
        for key in ("y_expr_sympy", "y_expr_latex", "expr_sympy", "expr_latex"):
            raw = series.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""
    for key in ("x_expr_sympy", "x_expr_latex"):
        raw = series.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _parse_param_range(series: Dict[str, Any]) -> Tuple[float, float]:
    params = series.get("params")
    if not isinstance(params, list):
        return 0.0, float(2 * np.pi)
    for row in params:
        if not isinstance(row, dict):
            continue
        candidate = str(row.get("text") or row.get("latex") or "").strip()
        if not candidate:
            continue
        normalized = latexish_to_sympy(candidate).replace("\\le", "..").replace("<=", "..")
        match = re.search(r"([-+]?\d*\.?\d+|pi)\s*\.\.\s*([-+]?\d*\.?\d+|pi)", normalized, flags=re.IGNORECASE)
        if not match:
            continue

        def to_float(tok: str) -> float:
            low = tok.strip().lower()
            if low == "pi":
                return float(np.pi)
            return _safe_float(tok, 0.0)

        lo = to_float(match.group(1))
        hi = to_float(match.group(2))
        if lo == hi:
            hi = lo + float(np.pi)
        if lo > hi:
            lo, hi = hi, lo
        return lo, hi
    return 0.0, float(2 * np.pi)


def _mask_discontinuities(y: np.ndarray, y_min: float, y_max: float) -> np.ndarray:
    yy = y.astype(float, copy=True)
    yy[~np.isfinite(yy)] = np.nan
    if yy.size < 2:
        return yy
    jump_threshold = max(20.0, abs(y_max - y_min) * 0.25)
    jumps = np.where(np.abs(np.diff(yy)) > jump_threshold)[0]
    yy[jumps + 1] = np.nan
    return yy


def _plot_function(
    ax: Any,
    series: Dict[str, Any],
    x_domain: Tuple[float, float],
    y_domain: Tuple[float, float],
    warnings: List[str],
) -> None:
    expr = _resolve_1d_expr(series, kind="function")
    if not expr:
        warnings.append("Function series missing expression.")
        return
    variable = str(series.get("variable") or "x").strip() or "x"
    try:
        compiled = compile_expr_1d(latexish_to_sympy(expr), variable=variable)
        xs = np.linspace(x_domain[0], x_domain[1], MAX_FUNCTION_SAMPLES)
        with np.errstate(all="ignore"):
            raw = np.asarray(compiled.fn(xs), dtype=np.complex128)
        ys = np.real(raw).astype(float, copy=False)
        ys[np.abs(np.imag(raw)) > 1e-9] = np.nan
        ys = _mask_discontinuities(ys, y_domain[0], y_domain[1])
        label = str(series.get("label") or "f(x)")
        ax.plot(xs, ys, linewidth=2.0, label=label)
    except (SympySafeError, Exception) as exc:  # noqa: BLE001
        warnings.append(f"Function series parse/eval failed: {exc}")


def _plot_parametric(
    ax: Any,
    series: Dict[str, Any],
    y_domain: Tuple[float, float],
    warnings: List[str],
) -> None:
    x_expr = _resolve_1d_expr(series, kind="parametric")
    y_expr = ""
    for key in ("y_expr_sympy", "y_expr_latex"):
        raw = series.get(key)
        if isinstance(raw, str) and raw.strip():
            y_expr = raw.strip()
            break
    if not x_expr or not y_expr:
        warnings.append("Parametric series missing x/y expression.")
        return
    variable = str(series.get("variable") or "t").strip() or "t"
    t_min, t_max = _parse_param_range(series)
    try:
        x_fn = compile_expr_1d(latexish_to_sympy(x_expr), variable=variable)
        y_fn = compile_expr_1d(latexish_to_sympy(y_expr), variable=variable)
        ts = np.linspace(t_min, t_max, MAX_PARAMETRIC_SAMPLES)
        with np.errstate(all="ignore"):
            xs = np.asarray(x_fn.fn(ts), dtype=np.float64)
            ys = np.asarray(y_fn.fn(ts), dtype=np.float64)
        xs[~np.isfinite(xs)] = np.nan
        ys = _mask_discontinuities(ys, y_domain[0], y_domain[1])
        label = str(series.get("label") or "parametric")
        ax.plot(xs, ys, linewidth=2.0, label=label)
    except (SympySafeError, Exception) as exc:  # noqa: BLE001
        warnings.append(f"Parametric series parse/eval failed: {exc}")


def _plot_implicit(
    ax: Any,
    series: Dict[str, Any],
    x_domain: Tuple[float, float],
    y_domain: Tuple[float, float],
    warnings: List[str],
) -> None:
    expr = ""
    for key in ("implicit_expr_sympy", "expr_sympy", "expr_latex"):
        raw = series.get(key)
        if isinstance(raw, str) and raw.strip():
            expr = raw.strip()
            break
    if not expr:
        warnings.append("Implicit series missing expression.")
        return
    norm = latexish_to_sympy(expr)
    if "=" in norm:
        left, right = norm.split("=", 1)
        norm = f"({left})-({right})"
    try:
        _, fn = compile_expr_2d(norm)
        n = MAX_IMPLICIT_GRID
        xg = np.linspace(x_domain[0], x_domain[1], n)
        yg = np.linspace(y_domain[0], y_domain[1], n)
        xx, yy = np.meshgrid(xg, yg)
        with np.errstate(all="ignore"):
            zz = np.asarray(fn(xx, yy), dtype=np.float64)
        zz[~np.isfinite(zz)] = np.nan
        label = str(series.get("label") or "implicit")
        cs = ax.contour(xx, yy, zz, levels=[0], linewidths=2.0)
        if cs.collections:
            cs.collections[0].set_label(label)
    except (SympySafeError, Exception) as exc:  # noqa: BLE001
        warnings.append(f"Implicit series parse/eval failed: {exc}")


def _plot_points(ax: Any, recipe: Dict[str, Any]) -> None:
    points = recipe.get("points")
    if not isinstance(points, list) or not points:
        return
    xs: List[float] = []
    ys: List[float] = []
    labels: List[str] = []
    for row in points:
        if not isinstance(row, dict):
            continue
        x = _safe_float(row.get("x"), float("nan"))
        y = _safe_float(row.get("y"), float("nan"))
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        xs.append(x)
        ys.append(y)
        labels.append(str(row.get("label") or "").strip())
    if not xs:
        return
    ax.scatter(xs, ys, s=32, label="points")
    for x, y, lbl in zip(xs, ys, labels):
        if lbl:
            ax.annotate(lbl, xy=(x, y), xytext=(6, 6), textcoords="offset points", fontsize=9)


def render_recipe_svg(
    recipe: Dict[str, Any],
    *,
    width_px: int = DEFAULT_WIDTH,
    height_px: int = DEFAULT_HEIGHT,
    font_scale: float = DEFAULT_FONT_SCALE,
) -> Tuple[str, List[str], int]:
    started = time.perf_counter()
    warnings: List[str] = []
    x_domain = _normalized_domain(recipe, "x_domain", (-10.0, 10.0))
    y_domain = _normalized_domain(recipe, "y_domain", (-10.0, 10.0))
    kind = str(recipe.get("kind") or "function_2d").strip()

    fig = plt.figure(figsize=(width_px / 100.0, height_px / 100.0))
    ax = fig.add_subplot(111)
    try:
        series = recipe.get("series")
        if isinstance(series, list):
            for row in series:
                if not isinstance(row, dict):
                    continue
                s_kind = str(row.get("kind") or "function").strip().lower()
                if s_kind == "function":
                    _plot_function(ax, row, x_domain, y_domain, warnings)
                elif s_kind == "parametric":
                    _plot_parametric(ax, row, y_domain, warnings)
                elif s_kind == "implicit":
                    _plot_implicit(ax, row, x_domain, y_domain, warnings)

        _plot_points(ax, recipe)

        if bool(recipe.get("axes_lines")):
            ax.axhline(0.0, linewidth=1.0, color="#64748b", alpha=0.8)
            ax.axvline(0.0, linewidth=1.0, color="#64748b", alpha=0.8)
        if bool(recipe.get("grid")):
            ax.grid(True, alpha=0.25)

        ax.set_xlim(x_domain[0], x_domain[1])
        ax.set_ylim(y_domain[0], y_domain[1])
        ax.set_title(str(recipe.get("title") or ""), fontsize=max(10, int(12 * font_scale)))
        ax.set_xlabel(str(recipe.get("x_label") or "x"), fontsize=max(9, int(10 * font_scale)))
        ax.set_ylabel(str(recipe.get("y_label") or "y"), fontsize=max(9, int(10 * font_scale)))

        if kind == "geometry_2d":
            ax.set_aspect("equal", adjustable="box")
        if bool(recipe.get("legend")):
            handles, labels = ax.get_legend_handles_labels()
            if handles and labels:
                ax.legend(loc="best", fontsize=max(8, int(9 * font_scale)))

        svg = _to_svg_bytes(fig)
        render_ms = int((time.perf_counter() - started) * 1000)
        return svg, warnings, render_ms
    finally:
        plt.close(fig)

