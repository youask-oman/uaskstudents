from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def validate_recipe(recipe: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(recipe, dict) or not recipe:
        return False, ["recipe_empty_or_invalid"], warnings

    series = recipe.get("series")
    if not isinstance(series, list) or not series:
        errors.append("series_missing_or_empty")

    x_domain = recipe.get("x_domain")
    if not isinstance(x_domain, dict):
        errors.append("x_domain_missing")
    else:
        x_min = x_domain.get("min")
        x_max = x_domain.get("max")
        if not _is_number(x_min) or not _is_number(x_max):
            errors.append("x_domain_non_numeric")
        else:
            if float(x_min) >= float(x_max):
                errors.append("x_domain_invalid_order")

    y_domain = recipe.get("y_domain")
    if isinstance(y_domain, dict):
        y_min = y_domain.get("min")
        y_max = y_domain.get("max")
        if y_min is not None and y_max is not None and _is_number(y_min) and _is_number(y_max):
            if float(y_min) >= float(y_max):
                warnings.append("y_domain_invalid_order_will_autoscale")

    for idx, s in enumerate(series if isinstance(series, list) else []):
        if not isinstance(s, dict):
            errors.append(f"series_{idx}_not_object")
            continue
        kind = str(s.get("kind") or "").strip().lower()
        if not kind:
            errors.append(f"series_{idx}_kind_missing")
            continue
        if kind == "function":
            if not any(isinstance(s.get(k), str) and str(s.get(k)).strip() for k in ("y_expr_sympy", "y_expr_latex", "expr_sympy", "expr_latex")):
                errors.append(f"series_{idx}_function_expr_missing")
        if kind == "parametric":
            x_ok = any(isinstance(s.get(k), str) and str(s.get(k)).strip() for k in ("x_expr_sympy", "x_expr_latex"))
            y_ok = any(isinstance(s.get(k), str) and str(s.get(k)).strip() for k in ("y_expr_sympy", "y_expr_latex"))
            if not x_ok or not y_ok:
                errors.append(f"series_{idx}_parametric_expr_missing")
        if kind == "sequence":
            if not isinstance(s.get("expr_sympy"), str) or not str(s.get("expr_sympy")).strip():
                errors.append(f"series_{idx}_sequence_expr_missing")
            try:
                int(s.get("n_min"))
                int(s.get("n_max"))
            except Exception:
                errors.append(f"series_{idx}_sequence_range_invalid")

    layers = recipe.get("layers")
    if isinstance(layers, list):
        has_slope = False
        has_phase = False
        for idx, layer in enumerate(layers):
            if not isinstance(layer, dict):
                warnings.append(f"layer_{idx}_not_object")
                continue
            layer_type = str(layer.get("type") or "").strip().lower()
            if not layer_type:
                warnings.append(f"layer_{idx}_type_missing")
                continue
            if layer_type == "slope_field":
                has_slope = True
            if layer_type == "phase_line":
                has_phase = True
        if has_slope or has_phase:
            dy_expr = recipe.get("dy_dx_sympy")
            if not isinstance(dy_expr, str) or not dy_expr.strip():
                warnings.append("layers_dy_dx_sympy_missing")

    return len(errors) == 0, errors, warnings
