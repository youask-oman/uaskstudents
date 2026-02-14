"""
Standalone helper for deterministic plot integration into solve_v3_stream.

This module intentionally avoids LLM plotting calls. Plot config is built in Python
using the local visualization engine.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from sqlmodel import Session

logger = logging.getLogger(__name__)


async def maybe_generate_plot(
    db_session: Session,
    problem_text: str,
    solve_result: Dict[str, Any],
    graph_mode: Optional[str],
    attach_to_step_id: Optional[int],
    tier: str,
    question_id: str,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Generate plot data deterministically in Python (no OpenAI plot trigger/spec calls).
    """
    log = logger or logging.getLogger(__name__)

    result = {
        "trigger": None,
        "spec": None,
        "plot_generated": False,
        "error": None,
        "pipeline_type": "none",
    }

    mode = (graph_mode or "auto").lower().strip()
    if mode == "off":
        log.info("[PLOT_INTEGRATION] graph_mode=off, skipping plot")
        return result

    visuals = solve_result.get("visuals", {})
    should_visualize = bool(visuals.get("should_visualize", False))
    if mode == "auto" and not should_visualize:
        log.info("[PLOT_INTEGRATION] graph_mode=auto and solve says no visualization needed")
        return result

    try:
        result["pipeline_type"] = "deterministic_python"
        fallback_plotly = await generate_matplotlib_fallback(problem_text, solve_result)
        if fallback_plotly:
            result["spec"] = {
                "plot_id": "plot_matplotlib_fallback",
                "attach_to_step_id": attach_to_step_id,
                "plotly_json": fallback_plotly,
                "error": None,
            }
            result["plot_generated"] = True
            log.info("[PLOT_INTEGRATION] Deterministic plot generated.")
        else:
            result["error"] = "Deterministic plot generation returned empty result"
            log.warning("[PLOT_INTEGRATION] Deterministic plot generation returned empty result")
    except Exception as e:
        log.exception("[PLOT_INTEGRATION] Unexpected error in deterministic plot pipeline")
        result["error"] = f"Plot pipeline error: {str(e)}"

    return result


async def generate_matplotlib_fallback(
    problem_text: str,
    solve_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Generate a Plotly-compatible JSON using the local Matplotlib-based engine.
    """
    try:
        from app.services.visualization.safe_parser import get_safe_parser
        import numpy as np

        visuals = solve_result.get("visuals") or {}
        plots = visuals.get("plots") or []
        plot = plots[0] if plots else {}
        recipe = plot.get("recipe") or {}
        domain = plot.get("domain") or {}

        expr = _extract_expr(problem_text, recipe)
        if not expr:
            return None

        x_min, x_max = _extract_domain_bounds(problem_text, domain, recipe)
        if x_min >= x_max:
            x_min, x_max = -10.0, 10.0

        samples_raw = _to_int((recipe.get("sampling") or {}).get("samples"))
        samples = samples_raw if samples_raw and 50 <= samples_raw <= 2000 else 400

        parser = get_safe_parser()
        x_values = np.linspace(x_min, x_max, samples)
        y_values, err = parser.evaluate_for_plotting(expr, x_values)
        if err or y_values is None:
            return None

        points: List[Tuple[float, float]] = []
        for xv, yv in zip(x_values, y_values):
            if np.isnan(yv) or np.isinf(yv):
                continue
            points.append((float(xv), float(yv)))
        if len(points) < 2:
            return None

        line_trace = {
            "name": "f(x)",
            "x": [p[0] for p in points],
            "y": [p[1] for p in points],
            "mode": "lines",
            "type": "scatter",
        }

        marker_x = []
        marker_y = []
        marker_text = []
        for kp in (plot.get("key_points") or []):
            kx = _to_float(kp.get("x"))
            ky = _to_float(kp.get("y"))
            if kx is None or ky is None:
                continue
            marker_x.append(kx)
            marker_y.append(ky)
            marker_text.append(str(kp.get("label") or "point"))

        data = [line_trace]
        if marker_x:
            data.append(
                {
                    "name": "key points",
                    "x": marker_x,
                    "y": marker_y,
                    "text": marker_text,
                    "mode": "markers+text",
                    "textposition": "top center",
                    "type": "scatter",
                    "marker": {"size": 8},
                }
            )

        return {
            "data": data,
            "layout": {
                "title": plot.get("title") or f"Graph of {expr}",
                "xaxis": {"title": plot.get("x_label") or "x", "range": [x_min, x_max]},
                "yaxis": {"title": plot.get("y_label") or "y"},
            },
        }
    except Exception:
        return None


def _extract_expr(problem_text: str, recipe: Dict[str, Any]) -> Optional[str]:
    expr = recipe.get("expr")
    if isinstance(expr, str) and expr.strip():
        return expr.strip()

    match = re.search(r"f\(x\)\s*=\s*([^,;\n]+)", problem_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"y\s*=\s*([^,;\n]+)", problem_text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_domain_bounds(
    problem_text: str,
    domain: Dict[str, Any],
    recipe: Dict[str, Any],
) -> Tuple[float, float]:
    x_min = _to_float(domain.get("x_min"))
    x_max = _to_float(domain.get("x_max"))
    if x_min is not None and x_max is not None:
        return x_min, x_max

    sampling = recipe.get("sampling") or {}
    t_min = _to_float(sampling.get("t_min"))
    t_max = _to_float(sampling.get("t_max"))
    if t_min is not None and t_max is not None:
        return t_min, t_max

    interval = re.search(r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]", problem_text)
    if interval:
        return float(interval.group(1)), float(interval.group(2))

    return -10.0, 10.0


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    v = value.strip().lower()
    if not v:
        return None

    if v in {"sqrt(2)", "+sqrt(2)"}:
        return 2 ** 0.5
    if v == "-sqrt(2)":
        return -(2 ** 0.5)
    if v == "pi":
        return 3.141592653589793
    if v == "-pi":
        return -3.141592653589793

    try:
        return float(v)
    except Exception:
        return None


def format_plot_for_response(plot_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Format plot result for frontend response.
    """
    if not plot_result.get("plot_generated"):
        return None

    spec = plot_result.get("spec") or {}
    trigger = plot_result.get("trigger") or {}

    return {
        "plot_id": spec.get("plot_id", "plot_1"),
        "attach_to_step_id": spec.get("attach_to_step_id"),
        "plotly_json": spec.get("plotly_json", {}),
        "plot_type": trigger.get("plot_type", "function"),
        "generated_by": plot_result.get("pipeline_type", "unknown"),
    }


def apply_graph_mode_override(
    solve_result: Dict[str, Any],
    graph_mode: str,
    plot_generated: bool = False,
) -> Dict[str, Any]:
    """
    Enforce deterministic behavior on visuals based on graph_mode.
    """
    mode = (graph_mode or "auto").lower().strip()

    if "visuals" not in solve_result:
        solve_result["visuals"] = {
            "should_visualize": False,
            "decision_reason": "Default (Injected)",
            "plots": [],
            "alternative_visual": None,
        }

    visuals = solve_result["visuals"]

    if mode == "off":
        visuals["should_visualize"] = False
        visuals["plots"] = []
        visuals["alternative_visual"] = None
        visuals["decision_reason"] = "Forced OFF by user graph_mode=off"
    elif mode == "on":
        visuals["should_visualize"] = True
        visuals["decision_reason"] = "Forced ON by user graph_mode=on"
    elif mode == "auto" and plot_generated:
        visuals["should_visualize"] = True

    return solve_result
