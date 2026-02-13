from __future__ import annotations

import json
import math
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

import matplotlib

matplotlib.use("Agg")

import numpy as np
from matplotlib.figure import Figure
from sympy import Abs, E, Symbol, acos, asin, atan, cos, exp, lambdify, log, pi, sin, sqrt, sympify, tan


RenderFormat = Literal["svg", "png"]
Theme = Literal["light", "dark"]

MAX_ABS_Y = 1_000_000.0
MAX_SAMPLES = 2000
MIN_SAMPLES = 200
MAX_ABS_BOUND = 10_000.0
RENDERER_VERSION = "mpl_v2"


@dataclass(frozen=True)
class RenderMeta:
    fmt: RenderFormat
    width_px: int
    height_px: int
    dpi: int
    plot_type: str


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _clamp_range(lo: float, hi: float, *, default: Tuple[float, float]) -> Tuple[float, float]:
    left = _safe_float(lo, default[0])
    right = _safe_float(hi, default[1])
    if left == right:
        right = left + 1.0
    if left > right:
        left, right = right, left
    left = _clamp(left, -MAX_ABS_BOUND, MAX_ABS_BOUND)
    right = _clamp(right, -MAX_ABS_BOUND, MAX_ABS_BOUND)
    if left == right:
        right = left + 1.0
    return left, right


def _sanitize_expr(raw: str) -> str:
    expr = (raw or "").strip()
    expr = expr.replace("^", "**").replace(" ", "")
    expr = expr.replace("f(x)=", "").replace("y=", "")
    return expr


def _display_expr(raw: str) -> str:
    expr = (raw or "").strip().replace("**", "^")
    expr = expr.replace("f(x)=", "").replace("y=", "")
    return expr


def _split_line_expr(raw_expr: str) -> Tuple[Optional[str], Optional[float]]:
    expr = (raw_expr or "").replace(" ", "")
    if "=" not in expr:
        return None, None
    left, right = expr.split("=", 1)
    if left in {"x", "y"}:
        try:
            return left, float(right)
        except (TypeError, ValueError):
            return None, None
    return None, None


def _extract_plotly_traces(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = spec.get("plotly_json")
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [trace for trace in data if isinstance(trace, dict)]
    return []


def _series_points(series_entry: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    points = series_entry.get("points")
    if isinstance(points, list):
        xs: List[float] = []
        ys: List[float] = []
        for p in points:
            if not isinstance(p, dict):
                continue
            x = _safe_float(p.get("x"), float("nan"))
            y = _safe_float(p.get("y"), float("nan"))
            if math.isfinite(x) and math.isfinite(y):
                xs.append(x)
                ys.append(y)
        return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)

    xs = series_entry.get("x")
    ys = series_entry.get("y")
    if isinstance(xs, list) and isinstance(ys, list):
        length = min(len(xs), len(ys), MAX_SAMPLES)
        xx = np.asarray([_safe_float(xs[i], float("nan")) for i in range(length)], dtype=float)
        yy = np.asarray([_safe_float(ys[i], float("nan")) for i in range(length)], dtype=float)
        mask = np.isfinite(xx) & np.isfinite(yy)
        return xx[mask], yy[mask]

    return np.asarray([], dtype=float), np.asarray([], dtype=float)


def _parse_expr_to_callable(expression: str):
    x = Symbol("x", real=True)
    local_dict = {
        "x": x,
        "sin": sin,
        "cos": cos,
        "tan": tan,
        "asin": asin,
        "acos": acos,
        "atan": atan,
        "sqrt": sqrt,
        "log": log,
        "ln": log,
        "exp": exp,
        "abs": Abs,
        "Abs": Abs,
        "pi": pi,
        "e": E,
    }
    expr = sympify(expression, locals=local_dict, evaluate=True)
    return lambdify(x, expr, modules=["numpy"])


def _parse_implicit_callable(expression: str):
    x = Symbol("x", real=True)
    y = Symbol("y", real=True)
    local_dict = {"x": x, "y": y, "pi": pi, "e": E, "sin": sin, "cos": cos, "tan": tan, "sqrt": sqrt, "log": log, "exp": exp, "Abs": Abs}
    expr = sympify(expression, locals=local_dict, evaluate=True)
    return lambdify((x, y), expr, modules=["numpy"])


def _plot_function_expression(ax: Any, expression: str, x_range: Tuple[float, float], n: int, label: str) -> bool:
    x, y = sample_function_series(expression, x_range=x_range, n=n)
    if x is None or y is None or np.all(np.isnan(y)):
        return False
    ax.plot(x, y, linewidth=2.0, label=label or "f(x)")
    return True


def sample_function_series(
    expression: str,
    *,
    x_range: Tuple[float, float],
    n: int,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    if not expression:
        return None, None
    try:
        f = _parse_expr_to_callable(_sanitize_expr(expression))
    except Exception:
        return None, None

    x = np.linspace(x_range[0], x_range[1], int(n))
    try:
        raw_y = np.asarray(f(x), dtype=np.complex128)
    except Exception:
        return None, None
    y = np.real(raw_y).astype(float, copy=False)
    y[np.abs(np.imag(raw_y)) > 1e-9] = np.nan
    if y.shape != x.shape:
        y = np.full_like(x, np.nan, dtype=float)

    y[~np.isfinite(y)] = np.nan
    y[np.abs(y) > MAX_ABS_Y] = np.nan
    if y.size > 1:
        dy = np.abs(np.diff(y))
        jump_idx = np.where(dy > 80.0)[0]
        y[jump_idx] = np.nan

    return x, y


def _plot_implicit(ax: Any, expression: str, x_range: Tuple[float, float], y_range: Tuple[float, float]) -> bool:
    if "=" not in expression:
        return False
    left, right = expression.split("=", 1)
    f_expr = f"({left})-({right})"
    try:
        f = _parse_implicit_callable(_sanitize_expr(f_expr))
    except Exception:
        return False

    n = 240
    xx = np.linspace(x_range[0], x_range[1], n)
    yy = np.linspace(y_range[0], y_range[1], n)
    X, Y = np.meshgrid(xx, yy)
    try:
        Z = np.asarray(f(X, Y), dtype=float)
    except Exception:
        return False
    if Z.shape != X.shape:
        return False
    Z[~np.isfinite(Z)] = np.nan
    ax.contour(X, Y, Z, levels=[0], linewidths=2.0)
    return True


def _plot_vertical_horizontal(ax: Any, expression: str) -> bool:
    axis, value = _split_line_expr(expression)
    if axis == "x" and value is not None:
        ax.axvline(value, linestyle="--", linewidth=2.0, color="#3b82f6")
        return True
    if axis == "y" and value is not None:
        ax.axhline(value, linestyle="--", linewidth=2.0, color="#3b82f6")
        return True
    return False


def _render_series(ax: Any, series_list: Iterable[Dict[str, Any]]) -> bool:
    rendered = False
    for idx, entry in enumerate(series_list):
        if not isinstance(entry, dict):
            continue
        xx, yy = _series_points(entry)
        if xx.size == 0 or yy.size == 0:
            continue
        mode = str(entry.get("mode") or "lines")
        label = str(entry.get("label") or entry.get("name") or f"series_{idx + 1}")
        if "markers" in mode and "lines" not in mode:
            ax.scatter(xx, yy, s=18, label=label)
        elif "lines+markers" in mode:
            ax.plot(xx, yy, linewidth=2.0, marker="o", markersize=3, label=label)
        else:
            ax.plot(xx, yy, linewidth=2.0, label=label)
        rendered = True
    return rendered


def _render_plotly_traces(ax: Any, traces: Iterable[Dict[str, Any]], expression_label: str = "") -> bool:
    rendered = False
    for idx, trace in enumerate(traces):
        if not isinstance(trace, dict):
            continue
        xx, yy = _series_points(trace)
        if xx.size == 0 or yy.size == 0:
            continue
        mode = str(trace.get("mode") or "lines")
        raw_label = str(trace.get("name") or f"trace_{idx + 1}").strip()
        lower = raw_label.lower()
        if lower in {"plot_matplotlib_fallback", "plot", "graph", "chart"} or lower.startswith("plot_") or lower == "f(x)":
            if expression_label:
                label = expression_label
            else:
                label = "f(x)"
        else:
            label = raw_label
        if "markers" in mode and "lines" not in mode:
            ax.scatter(xx, yy, s=18, label=label)
        elif "lines+markers" in mode:
            ax.plot(xx, yy, linewidth=2.0, marker="o", markersize=3, label=label)
        else:
            ax.plot(xx, yy, linewidth=2.0, label=label)
        rendered = True
    return rendered


def _pick_ranges(spec: Dict[str, Any]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    axes = spec.get("axes") if isinstance(spec.get("axes"), dict) else {}
    x_range = axes.get("x_range") if isinstance(axes, dict) else None
    y_range = axes.get("y_range") if isinstance(axes, dict) else None
    domain = spec.get("domain") if isinstance(spec.get("domain"), dict) else {}

    if isinstance(x_range, list) and len(x_range) == 2:
        xr = _clamp_range(x_range[0], x_range[1], default=(-10.0, 10.0))
    else:
        xr = _clamp_range(domain.get("x_min_latex"), domain.get("x_max_latex"), default=(-10.0, 10.0))

    if isinstance(y_range, list) and len(y_range) == 2:
        yr = _clamp_range(y_range[0], y_range[1], default=(-10.0, 10.0))
    else:
        yr = _clamp_range(domain.get("y_min_latex"), domain.get("y_max_latex"), default=(-10.0, 10.0))

    return xr, yr


def _is_generic_title(title: str) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return True
    generic_tokens = {"graph", "plot", "plot_matplotlib_fallback", "figure", "chart"}
    return t in generic_tokens or t.startswith("plot_")


def _infer_expression(spec: Dict[str, Any]) -> str:
    series = spec.get("series")
    if isinstance(series, list):
        for row in series:
            if not isinstance(row, dict):
                continue
            expr = str(row.get("expression_latex") or row.get("expression") or "").strip()
            if expr:
                return expr
    if isinstance(spec.get("recipe"), dict):
        expr = str(spec["recipe"].get("expr") or "").strip()
        if expr:
            return expr
    return ""


def _build_title(spec: Dict[str, Any]) -> str:
    raw_title = str(spec.get("title") or "").strip()
    if raw_title and not _is_generic_title(raw_title):
        return raw_title if len(raw_title) <= 90 else f"{raw_title[:87].rstrip()}..."
    expr = _infer_expression(spec)
    if expr:
        shown = _display_expr(expr)
        if len(shown) <= 55:
            return f"Graph of y = {shown}"
        return "Function Graph"
    return "Math Graph"


def _pick_reference_point(
    spec: Dict[str, Any],
    plotted_x: Optional[np.ndarray],
    plotted_y: Optional[np.ndarray],
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
) -> Tuple[float, float]:
    key_points = spec.get("key_points")
    if isinstance(key_points, list):
        for point in key_points:
            if not isinstance(point, dict):
                continue
            px = _safe_float(point.get("x"), float("nan"))
            py = _safe_float(point.get("y"), float("nan"))
            if math.isfinite(px) and math.isfinite(py):
                return px, py
    if plotted_x is not None and plotted_y is not None:
        mask = np.isfinite(plotted_x) & np.isfinite(plotted_y)
        if np.any(mask):
            valid_x = plotted_x[mask]
            valid_y = plotted_y[mask]
            idx = int(np.nanargmax(valid_y))
            return float(valid_x[idx]), float(valid_y[idx])
    return float((x_range[0] + x_range[1]) / 2.0), float((y_range[0] + y_range[1]) / 2.0)


def canonical_plot_hash_payload(spec: Dict[str, Any], *, theme: Theme, width_px: int, height_px: int, dpi: int) -> str:
    normalized = {
        "renderer_version": RENDERER_VERSION,
        "spec": spec,
        "theme": theme,
        "width_px": int(width_px),
        "height_px": int(height_px),
        "dpi": int(dpi),
    }
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def render_graph(
    spec: Dict[str, Any],
    *,
    width_px: int = 1200,
    height_px: int = 680,
    dpi: int = 120,
    theme: Theme = "light",
    fmt: RenderFormat = "svg",
    bounds: Optional[Dict[str, Any]] = None,
) -> Tuple[bytes, RenderMeta]:
    width_px = int(_clamp(width_px, 320, 2200))
    height_px = int(_clamp(height_px, 220, 1600))
    dpi = int(_clamp(dpi, 72, 240))

    x_range, y_range = _pick_ranges(spec)
    if isinstance(bounds, dict):
        x_range = _clamp_range(bounds.get("x_min"), bounds.get("x_max"), default=x_range)
        y_range = _clamp_range(bounds.get("y_min"), bounds.get("y_max"), default=y_range)

    n = int(_clamp(spec.get("samples", 1000), MIN_SAMPLES, MAX_SAMPLES))
    fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    ax = fig.add_subplot(1, 1, 1)

    if theme == "dark":
        fig.patch.set_facecolor("#0f172a")
        ax.set_facecolor("#0b1220")
        fg = "#e2e8f0"
        grid = "#334155"
        for spine in ax.spines.values():
            spine.set_color(fg)
        ax.tick_params(colors=fg)
        ax.xaxis.label.set_color(fg)
        ax.yaxis.label.set_color(fg)
        ax.title.set_color(fg)
        ax.grid(True, alpha=0.35, color=grid)
    else:
        ax.grid(True, alpha=0.28)

    rendered = False
    plot_type = "unknown"
    plotted_x: Optional[np.ndarray] = None
    plotted_y: Optional[np.ndarray] = None
    traces = _extract_plotly_traces(spec)
    expr_label = str(spec.get("expression_label") or "").strip()
    if traces:
        rendered = _render_plotly_traces(ax, traces, expression_label=expr_label)
        plot_type = "plotly_series"

    if not rendered:
        series = spec.get("series")
        if isinstance(series, list) and series:
            rendered = _render_series(ax, series)
            plot_type = "series_points"

    if not rendered:
        expr = ""
        series = spec.get("series")
        if isinstance(series, list) and series and isinstance(series[0], dict):
            expr = str(series[0].get("expression_latex") or series[0].get("expression") or "")
        if not expr and isinstance(spec.get("recipe"), dict):
            expr = str(spec["recipe"].get("expr") or "")
        expr = expr.strip()
        if expr:
            if _plot_vertical_horizontal(ax, expr):
                rendered = True
                plot_type = "line_const"
            elif ("=" in expr and "x" in expr and "y" in expr and not expr.startswith("y=")):
                rendered = _plot_implicit(ax, expr, x_range, y_range)
                plot_type = "implicit" if rendered else "unsupported"
            else:
                plotted_x, plotted_y = sample_function_series(expr, x_range=x_range, n=n)
                if plotted_x is not None and plotted_y is not None and not np.all(np.isnan(plotted_y)):
                    ax.plot(plotted_x, plotted_y, linewidth=2.0, label=f"f(x) = {_display_expr(expr)}")
                    rendered = True
                else:
                    rendered = False
                plot_type = "function" if rendered else "unsupported"

    key_points = spec.get("key_points")
    if isinstance(key_points, list):
        xp: List[float] = []
        yp: List[float] = []
        for point in key_points:
            if not isinstance(point, dict):
                continue
            x = _safe_float(point.get("x"), float("nan"))
            y = _safe_float(point.get("y"), float("nan"))
            if math.isfinite(x) and math.isfinite(y):
                xp.append(x)
                yp.append(y)
        if xp and yp:
            ax.scatter(xp, yp, s=26, color="#ef4444", zorder=4)
            rendered = True

    if not rendered:
        raise ValueError("unsupported_plot_spec")

    axes = spec.get("axes") if isinstance(spec.get("axes"), dict) else {}
    vx, vy = _pick_reference_point(spec, plotted_x, plotted_y, x_range, y_range)
    ax.axvline(vx, linestyle="--", color="#2563eb", alpha=0.9)
    ax.axhline(vy, linestyle="--", color="#2563eb", alpha=0.9)
    ax.scatter([vx], [vy], s=42, color="#2563eb", label=f"Reference ({vx:g}, {vy:g})", zorder=5)

    ax.set_title(_build_title(spec))
    ax.set_xlabel(str((axes or {}).get("x_label") or "x"))
    ax.set_ylabel(str((axes or {}).get("y_label") or "y"))
    ax.set_xlim(*x_range)
    ax.set_ylim(*y_range)
    ax.grid(True)
    handles, labels = ax.get_legend_handles_labels()
    if handles and labels:
        ax.legend(loc="best")

    output = BytesIO()
    if fmt == "svg":
        fig.savefig(output, format="svg", bbox_inches="tight")
    else:
        fig.savefig(output, format="png", bbox_inches="tight", dpi=dpi)
    return output.getvalue(), RenderMeta(fmt=fmt, width_px=width_px, height_px=height_px, dpi=dpi, plot_type=plot_type)
