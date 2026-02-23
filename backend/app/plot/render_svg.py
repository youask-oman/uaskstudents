from __future__ import annotations

import io
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "uask_plot_svg_v2"

import matplotlib.pyplot as plt
import numpy as np

from app.plot.recipe_normalizer import normalize_recipe
from app.plot.recipe_validator import validate_recipe
from app.plot.sympy_safe import SympySafeError, compile_expr_1d, compile_expr_2d, latexish_to_sympy
from app.telemetry.plot_telemetry import build_plot_telemetry


logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 520
DEFAULT_FONT_SCALE = 1.0
MAX_ABS_BOUND = 10_000.0
DEFAULT_CONTINUOUS_SAMPLES = 500
DEFAULT_PARAMETRIC_SAMPLES = 1000
MAX_IMPLICIT_GRID = 450


class PlotRenderError(ValueError):
    pass


def _safe_float(value: Any, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(v):
        return default
    return v


def _extract_domain(recipe: Dict[str, Any], key: str, default: Tuple[float, float], *, allow_missing: bool = False) -> Optional[Tuple[float, float]]:
    obj = recipe.get(key) if isinstance(recipe.get(key), dict) else {}
    lo_raw = obj.get("min")
    hi_raw = obj.get("max")
    if allow_missing and (lo_raw is None or hi_raw is None):
        return None
    lo = _safe_float(lo_raw, default[0])
    hi = _safe_float(hi_raw, default[1])
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
    return buf.getvalue().decode("utf-8", errors="replace").strip()


def _finite(values: np.ndarray) -> np.ndarray:
    vals = np.asarray(values, dtype=np.float64)
    vals[~np.isfinite(vals)] = np.nan
    return vals


def _sanitize_complex(arr: np.ndarray, warnings: List[str], *, tag: str) -> np.ndarray:
    raw = np.asarray(arr)
    if np.iscomplexobj(raw):
        imag_max = float(np.nanmax(np.abs(np.imag(raw)))) if raw.size else 0.0
        if imag_max <= 1e-10:
            warnings.append(f"{tag}:complex_to_real")
            raw = np.real(raw)
        else:
            raise PlotRenderError(f"{tag}:complex_output")
    return _finite(np.asarray(raw, dtype=np.float64))


def _mask_discontinuities(y: np.ndarray, y_range_hint: Optional[Tuple[float, float]]) -> np.ndarray:
    yy = _finite(y)
    if yy.size < 2:
        return yy
    if y_range_hint is None:
        finite = yy[np.isfinite(yy)]
        if finite.size < 2:
            return yy
        span = float(np.nanmax(finite) - np.nanmin(finite))
    else:
        span = abs(y_range_hint[1] - y_range_hint[0])
    jump_threshold = max(20.0, span * 0.25 if span > 0 else 20.0)
    diffs = np.abs(np.diff(yy))
    jumps = np.where(np.isfinite(diffs) & (diffs > jump_threshold))[0]
    yy[jumps + 1] = np.nan
    return yy


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


def _resolve_expr(series: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for key in keys:
        raw = series.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _build_discrete_grid(series: Dict[str, Any], recipe_x_domain: Tuple[float, float]) -> np.ndarray:
    n_min = int(series.get("n_min", int(recipe_x_domain[0])))
    n_max = int(series.get("n_max", int(recipe_x_domain[1])))
    if n_min > n_max:
        n_min, n_max = n_max, n_min
    return np.arange(n_min, n_max + 1, dtype=np.int64)


def _safe_eval_sequence(expr: str, variable: str, n_values: np.ndarray, warnings: List[str]) -> np.ndarray:
    normalized = latexish_to_sympy(expr).replace("{", "(").replace("}", ")").replace("^", "**")
    compiled = compile_expr_1d(normalized, variable=variable)
    with np.errstate(all="ignore"):
        raw = compiled.fn(n_values)
    values = _sanitize_complex(np.asarray(raw), warnings, tag="sequence")
    if np.all(~np.isfinite(values)):
        raise PlotRenderError("sequence:nan_only")
    return values


def _plot_function(
    ax: Any,
    series: Dict[str, Any],
    x_domain: Tuple[float, float],
    y_hint: Optional[Tuple[float, float]],
    warnings: List[str],
) -> Optional[np.ndarray]:
    expr = _resolve_expr(series, ("y_expr_sympy", "y_expr_latex", "expr_sympy", "expr_latex"))
    if not expr:
        raise PlotRenderError("function:expr_missing")
    variable = str(series.get("variable") or "x").strip() or "x"
    compiled = compile_expr_1d(latexish_to_sympy(expr), variable=variable)
    n = int(series.get("n_points") or DEFAULT_CONTINUOUS_SAMPLES)
    n = max(50, min(4000, n))
    xs = np.linspace(x_domain[0], x_domain[1], n)
    with np.errstate(all="ignore"):
        raw = compiled.fn(xs)
    ys = _sanitize_complex(np.asarray(raw), warnings, tag="function")
    ys = _mask_discontinuities(ys, y_hint)
    if np.all(~np.isfinite(ys)):
        raise PlotRenderError("function:nan_only")
    label = str(series.get("label") or "f(x)")
    ax.plot(xs, ys, linewidth=2.0, label=label)
    return ys


def _plot_parametric(
    ax: Any,
    series: Dict[str, Any],
    warnings: List[str],
) -> Optional[np.ndarray]:
    x_expr = _resolve_expr(series, ("x_expr_sympy", "x_expr_latex"))
    y_expr = _resolve_expr(series, ("y_expr_sympy", "y_expr_latex"))
    if not x_expr or not y_expr:
        raise PlotRenderError("parametric:expr_missing")
    variable = str(series.get("variable") or "t").strip() or "t"
    t_min, t_max = _parse_param_range(series)
    n = int(series.get("n_points") or DEFAULT_PARAMETRIC_SAMPLES)
    n = max(100, min(5000, n))
    ts = np.linspace(t_min, t_max, n)
    x_fn = compile_expr_1d(latexish_to_sympy(x_expr), variable=variable)
    y_fn = compile_expr_1d(latexish_to_sympy(y_expr), variable=variable)
    with np.errstate(all="ignore"):
        xs_raw = x_fn.fn(ts)
        ys_raw = y_fn.fn(ts)
    xs = _sanitize_complex(np.asarray(xs_raw), warnings, tag="parametric_x")
    ys = _sanitize_complex(np.asarray(ys_raw), warnings, tag="parametric_y")
    if np.all(~np.isfinite(xs)) or np.all(~np.isfinite(ys)):
        raise PlotRenderError("parametric:nan_only")
    label = str(series.get("label") or "parametric")
    ax.plot(xs, ys, linewidth=2.0, label=label)
    return ys


def _plot_implicit(
    ax: Any,
    series: Dict[str, Any],
    x_domain: Tuple[float, float],
    y_domain: Tuple[float, float],
    warnings: List[str],
) -> Optional[np.ndarray]:
    expr = _resolve_expr(series, ("implicit_expr_sympy", "expr_sympy", "expr_latex"))
    if not expr:
        raise PlotRenderError("implicit:expr_missing")
    norm = latexish_to_sympy(expr)
    if "=" in norm:
        left, right = norm.split("=", 1)
        norm = f"({left})-({right})"
    _, fn = compile_expr_2d(norm)
    n = int(series.get("grid_n") or MAX_IMPLICIT_GRID)
    n = max(80, min(MAX_IMPLICIT_GRID, n))
    xg = np.linspace(x_domain[0], x_domain[1], n)
    yg = np.linspace(y_domain[0], y_domain[1], n)
    xx, yy = np.meshgrid(xg, yg)
    with np.errstate(all="ignore"):
        zz_raw = fn(xx, yy)
    zz = _sanitize_complex(np.asarray(zz_raw), warnings, tag="implicit")
    if np.all(~np.isfinite(zz)):
        raise PlotRenderError("implicit:nan_only")
    label = str(series.get("label") or "implicit")
    cs = ax.contour(xx, yy, zz, levels=[0], linewidths=2.0)
    if cs.collections:
        cs.collections[0].set_label(label)
    return zz[np.isfinite(zz)]


def _plot_sequence(
    ax: Any,
    series: Dict[str, Any],
    x_domain: Tuple[float, float],
    warnings: List[str],
) -> Optional[np.ndarray]:
    expr = _resolve_expr(series, ("expr_sympy", "expr_latex", "y_expr_sympy", "y_expr_latex"))
    if not expr:
        raise PlotRenderError("sequence:expr_missing")
    variable = str(series.get("variable") or "n").strip() or "n"
    n_values = _build_discrete_grid(series, x_domain)
    y_values = _safe_eval_sequence(expr, variable, n_values, warnings)

    if str(series.get("sequence_kind") or "").lower() == "partial_sum":
        y_values = np.cumsum(y_values)

    label = str(series.get("label") or "sequence")
    style = str(series.get("plot_style") or "").lower()
    if style in {"stem", "discrete", "points"}:
        markerline, stemlines, baseline = ax.stem(n_values, y_values, label=label, basefmt=" ")
        plt.setp(stemlines, linewidth=1.2)
        plt.setp(markerline, markersize=4)
    elif style in {"scatter"}:
        ax.scatter(n_values, y_values, label=label, s=18)
    else:
        ax.plot(n_values, y_values, linewidth=1.8, marker="o", markersize=2.6, label=label)
    return y_values


def _plot_points(ax: Any, recipe: Dict[str, Any]) -> Optional[np.ndarray]:
    points = recipe.get("points")
    if not isinstance(points, list) or not points:
        return None
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
        return None
    ax.scatter(xs, ys, s=34, label="points")
    for x, y, lbl in zip(xs, ys, labels):
        if lbl:
            ax.annotate(lbl, xy=(x, y), xytext=(6, 6), textcoords="offset points", fontsize=9)
    return np.asarray(ys, dtype=np.float64)


def _apply_annotations(ax: Any, recipe: Dict[str, Any], x_domain: Tuple[float, float]) -> None:
    annotations = recipe.get("annotations")
    if not isinstance(annotations, list):
        return
    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        ann_type = str(ann.get("type") or "").lower()
        label = str(ann.get("label") or "")
        if ann_type == "hline":
            try:
                y = float(ann.get("y"))
            except Exception:
                continue
            x_min = _safe_float(ann.get("x_min"), x_domain[0])
            x_max = _safe_float(ann.get("x_max"), x_domain[1])
            ax.hlines(y, x_min, x_max, colors="#0f766e", linestyles="--", linewidth=1.2, label=label or None)
        elif ann_type == "vline":
            try:
                x = float(ann.get("x"))
            except Exception:
                continue
            ax.axvline(x, color="#0f766e", linestyle="--", linewidth=1.2, label=label or None)


def _autoscale_y(ax: Any, recipe: Dict[str, Any], y_samples: List[np.ndarray], warnings: List[str]) -> Tuple[float, float]:
    y_domain = _extract_domain(recipe, "y_domain", (-1.0, 1.0), allow_missing=True)
    if y_domain is not None:
        return y_domain

    finite: List[float] = []
    for sample in y_samples:
        if sample is None:
            continue
        vals = np.asarray(sample, dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if vals.size:
            finite.extend(vals.tolist())

    if not finite:
        warnings.append("autoscale:no_finite_values_default_used")
        return -1.0, 1.0

    y_min = float(np.min(finite))
    y_max = float(np.max(finite))
    if not np.isfinite(y_min) or not np.isfinite(y_max):
        warnings.append("autoscale:non_finite_default_used")
        return -1.0, 1.0
    if y_min == y_max:
        pad = 1.0
    else:
        pad = max(1e-6, 0.05 * abs(y_max - y_min))
    return y_min - pad, y_max + pad


def _render_fallback_axes(
    ax: Any,
    recipe: Dict[str, Any],
    x_domain: Tuple[float, float],
    warnings: List[str],
) -> Tuple[float, float]:
    y_min, y_max = -1.0, 1.0
    ax.set_xlim(x_domain[0], x_domain[1])
    ax.set_ylim(y_min, y_max)
    ax.text(
        0.5,
        0.5,
        "Plot unavailable (diagnostics recorded)",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=10,
        color="#991b1b",
    )
    _apply_annotations(ax, recipe, x_domain)
    warnings.append("fallback_plot_rendered")
    return y_min, y_max


def render_recipe_svg(
    recipe: Dict[str, Any],
    *,
    width_px: int = DEFAULT_WIDTH,
    height_px: int = DEFAULT_HEIGHT,
    font_scale: float = DEFAULT_FONT_SCALE,
) -> Tuple[str, List[str], int]:
    started = time.perf_counter()

    normalized_recipe, normalize_notes = normalize_recipe(recipe)
    is_valid, validation_errors, validation_warnings = validate_recipe(normalized_recipe)
    warnings: List[str] = [*normalize_notes, *validation_warnings]

    classification = str(normalized_recipe.get("classification") or "CONTINUOUS_FUNCTION")
    x_domain = _extract_domain(normalized_recipe, "x_domain", (-10.0, 10.0), allow_missing=False)
    if x_domain is None:
        raise PlotRenderError("x_domain_missing_after_normalization")

    fig = plt.figure(figsize=(width_px / 100.0, height_px / 100.0))
    ax = fig.add_subplot(111)
    fallback_used = False
    sampling_info: Dict[str, Any] = {"classification": classification}

    try:
        if not is_valid:
            warnings.extend(validation_errors)
            fallback_used = True
            y_min, y_max = _render_fallback_axes(ax, normalized_recipe, x_domain, warnings)
        else:
            y_samples: List[np.ndarray] = []
            series = normalized_recipe.get("series")
            series = series if isinstance(series, list) else []
            for idx, row in enumerate(series):
                if not isinstance(row, dict):
                    warnings.append(f"series_{idx}:invalid_object")
                    continue
                kind = str(row.get("kind") or "function").strip().lower()
                try:
                    if kind == "function":
                        sample = _plot_function(ax, row, x_domain, _extract_domain(normalized_recipe, "y_domain", (-1, 1), allow_missing=True), warnings)
                    elif kind == "parametric":
                        sample = _plot_parametric(ax, row, warnings)
                    elif kind == "implicit":
                        y_domain_for_implicit = _extract_domain(normalized_recipe, "y_domain", (-10.0, 10.0), allow_missing=False)
                        if y_domain_for_implicit is None:
                            raise PlotRenderError("implicit:y_domain_missing")
                        sample = _plot_implicit(ax, row, x_domain, y_domain_for_implicit, warnings)
                    elif kind == "sequence":
                        sample = _plot_sequence(ax, row, x_domain, warnings)
                        sampling_info["discrete_grid"] = {
                            "n_min": int(row.get("n_min", int(x_domain[0]))),
                            "n_max": int(row.get("n_max", int(x_domain[1]))),
                            "variable": str(row.get("variable") or "n"),
                        }
                    elif kind in {"scatter", "points"}:
                        sample = _plot_points(ax, {"points": row.get("samples") or []})
                    else:
                        warnings.append(f"series_{idx}:unsupported_kind:{kind}")
                        sample = None
                    if sample is not None:
                        y_samples.append(np.asarray(sample, dtype=np.float64))
                except PlotRenderError as exc:
                    warnings.append(f"series_{idx}:{exc}")
                except (SympySafeError, Exception) as exc:  # noqa: BLE001
                    warnings.append(f"series_{idx}:eval_failed:{exc}")

            points_sample = _plot_points(ax, normalized_recipe)
            if points_sample is not None:
                y_samples.append(points_sample)
            _apply_annotations(ax, normalized_recipe, x_domain)

            if not y_samples:
                fallback_used = True
                y_min, y_max = _render_fallback_axes(ax, normalized_recipe, x_domain, warnings)
            else:
                y_min, y_max = _autoscale_y(ax, normalized_recipe, y_samples, warnings)

        if bool(normalized_recipe.get("axes_lines")):
            ax.axhline(0.0, linewidth=1.0, color="#64748b", alpha=0.8)
            ax.axvline(0.0, linewidth=1.0, color="#64748b", alpha=0.8)
        if bool(normalized_recipe.get("grid")):
            ax.grid(True, alpha=0.25)

        ax.set_xlim(x_domain[0], x_domain[1])
        ax.set_ylim(y_min, y_max)
        ax.set_title(str(normalized_recipe.get("title") or ""), fontsize=max(10, int(12 * font_scale)))
        ax.set_xlabel(str(normalized_recipe.get("x_label") or "x"), fontsize=max(9, int(10 * font_scale)))
        ax.set_ylabel(str(normalized_recipe.get("y_label") or "y"), fontsize=max(9, int(10 * font_scale)))

        if str(normalized_recipe.get("kind") or "").strip() == "geometry_2d":
            ax.set_aspect("equal", adjustable="box")

        if bool(normalized_recipe.get("legend")):
            handles, labels = ax.get_legend_handles_labels()
            if handles and labels:
                ax.legend(loc="best", fontsize=max(8, int(9 * font_scale)))

        telemetry = build_plot_telemetry(
            classification=classification,
            normalized_recipe=normalized_recipe,
            sampling=sampling_info,
            warnings=warnings,
            errors=validation_errors,
            fallback_used=fallback_used,
        )
        logger.info("plot_render_telemetry=%s", telemetry)

        svg = _to_svg_bytes(fig)
        render_ms = int((time.perf_counter() - started) * 1000)
        return svg, warnings, render_ms
    finally:
        plt.close(fig)

