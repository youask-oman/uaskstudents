from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


DISCRETE_HINT_RE = re.compile(
    r"(for\s+n\s*=|partial\s*sum|cumsum\(|\ba_n\b|\bs_n\b|versus\s+n|vs\s+n)",
    re.IGNORECASE,
)
PARAMETRIC_HINT_RE = re.compile(r"(x\s*\(\s*t\s*\)|y\s*\(\s*t\s*\)|parametric)", re.IGNORECASE)
HIST_HINT_RE = re.compile(r"(hist|histogram|bar|categorical)", re.IGNORECASE)
RANGE_RE = re.compile(r"\b([a-zA-Z])\s*=\s*(-?\d+)\s*\.\.\s*(-?\d+)\b")


def classify_recipe(recipe: Dict[str, Any]) -> str:
    series = recipe.get("series") if isinstance(recipe.get("series"), list) else []
    expressions = recipe.get("expressions") if isinstance(recipe.get("expressions"), list) else []
    haystack = " | ".join(str(x or "") for x in expressions)
    for s in series:
        if isinstance(s, dict) and str(s.get("kind") or "").strip().lower() == "sequence":
            return "DISCRETE_SEQUENCE"
    for s in series:
        if isinstance(s, dict):
            haystack += " | " + " ".join(str(s.get(k) or "") for k in ("kind", "label", "expr_latex", "y_expr_latex"))

    if PARAMETRIC_HINT_RE.search(haystack):
        return "PARAMETRIC"
    if DISCRETE_HINT_RE.search(haystack):
        return "DISCRETE_SEQUENCE"
    if HIST_HINT_RE.search(haystack):
        return "CATEGORICAL_HIST"
    return "CONTINUOUS_FUNCTION"


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_for_range(expr: str) -> Optional[Tuple[str, int, int]]:
    match = RANGE_RE.search(str(expr or ""))
    if not match:
        return None
    variable = str(match.group(1)).strip()
    lo = _safe_int(match.group(2), 1)
    hi = _safe_int(match.group(3), lo + 10)
    if lo > hi:
        lo, hi = hi, lo
    return variable, lo, hi


def _normalize_key_points(recipe: Dict[str, Any], diagnostics: List[str]) -> None:
    key_points = recipe.get("key_points")
    if not isinstance(key_points, list):
        return
    points = recipe.get("points")
    if not isinstance(points, list):
        points = []
    annotations = recipe.get("annotations")
    if not isinstance(annotations, list):
        annotations = []

    x_domain = recipe.get("x_domain") if isinstance(recipe.get("x_domain"), dict) else {}
    x_min = x_domain.get("min")
    x_max = x_domain.get("max")
    for row in key_points:
        if isinstance(row, str):
            text = row.strip()
            # Support compact marker syntax like "@{label=N=20; x=20; y=0.3}"
            if text.startswith("@{") and text.endswith("}"):
                payload = text[2:-1]
                pairs = [x.strip() for x in payload.split(";") if x.strip()]
                obj: Dict[str, Any] = {}
                for pair in pairs:
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        obj[k.strip()] = v.strip()
                row = obj
            else:
                continue
        if not isinstance(row, dict):
            continue

        label = str(row.get("label") or "").strip() or None
        x_raw = row.get("x")
        y_raw = row.get("y")
        x_num = None
        y_num = None
        try:
            if x_raw is not None and str(x_raw).strip().lower() not in {"n_range", "x_range"}:
                x_num = float(x_raw)
        except Exception:
            x_num = None
        try:
            if y_raw is not None:
                y_num = float(y_raw)
        except Exception:
            y_num = None

        if isinstance(x_raw, str) and x_raw.strip().lower() in {"n_range", "x_range"} and y_num is not None:
            if x_min is not None:
                annotations.append({"type": "hline", "y": y_num, "label": label, "x_min": x_min, "x_max": x_max})
                diagnostics.append("normalized_key_point_placeholder_to_hline")
            continue

        if x_num is not None and y_num is not None:
            points.append({"x": x_num, "y": y_num, "label": label, "kind": "custom"})
        elif x_num is not None and y_num is None:
            annotations.append({"type": "vline", "x": x_num, "label": label})
        elif y_num is not None and x_num is None:
            annotations.append({"type": "hline", "y": y_num, "label": label, "x_min": x_min, "x_max": x_max})

    recipe["points"] = points
    recipe["annotations"] = annotations


def _extract_expr_rhs(expr: str) -> str:
    text = str(expr or "").strip()
    if not text:
        return ""
    # "S_N = cumsum(...) for n=1..200" -> cumsum(...)
    if "=" in text:
        _, rhs = text.split("=", 1)
    else:
        rhs = text
    rhs = re.sub(r"\bfor\s+[a-zA-Z]\s*=\s*-?\d+\s*\.\.\s*-?\d+\b", "", rhs, flags=re.IGNORECASE).strip()
    return rhs


def _series_from_expressions(recipe: Dict[str, Any], diagnostics: List[str]) -> List[Dict[str, Any]]:
    expressions = recipe.get("expressions")
    if not isinstance(expressions, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in expressions:
        text = str(raw or "").strip()
        if not text:
            continue
        range_match = _parse_for_range(text)
        rhs = _extract_expr_rhs(text)
        label = text.split("=", 1)[0].strip() if "=" in text else text
        if range_match:
            var, lo, hi = range_match
            if "cumsum(" in rhs.lower():
                inner = rhs[rhs.lower().find("cumsum(") + len("cumsum(") :]
                if inner.endswith(")"):
                    inner = inner[:-1]
                out.append(
                    {
                        "kind": "sequence",
                        "sequence_kind": "partial_sum",
                        "label": label or "S_n",
                        "expr_sympy": inner.strip(),
                        "variable": var,
                        "n_min": lo,
                        "n_max": hi,
                    }
                )
            else:
                out.append(
                    {
                        "kind": "sequence",
                        "sequence_kind": "term",
                        "label": label or "a_n",
                        "expr_sympy": rhs.strip(),
                        "variable": var,
                        "n_min": lo,
                        "n_max": hi,
                    }
                )
        elif rhs:
            out.append({"kind": "function", "label": label or "f(x)", "y_expr_sympy": rhs, "variable": "x"})
    if out:
        diagnostics.append("normalized_expressions_to_series")
    return out


def normalize_recipe(recipe: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    normalized = dict(recipe or {})
    diagnostics: List[str] = []

    if not isinstance(normalized.get("series"), list):
        normalized["series"] = []
    if not normalized["series"]:
        normalized["series"] = _series_from_expressions(normalized, diagnostics)

    classification = classify_recipe(normalized)
    normalized["classification"] = classification

    if "x_domain" not in normalized and isinstance(normalized.get("domain"), dict):
        d = normalized.get("domain") or {}
        normalized["x_domain"] = {"min": d.get("x_min"), "max": d.get("x_max")}
        normalized["y_domain"] = {"min": d.get("y_min"), "max": d.get("y_max")}
        diagnostics.append("normalized_legacy_domain")

    # Enforce discrete integer domains from series ranges.
    if classification == "DISCRETE_SEQUENCE":
        n_min = None
        n_max = None
        for s in normalized["series"]:
            if not isinstance(s, dict):
                continue
            if s.get("kind") != "sequence":
                continue
            lo = s.get("n_min")
            hi = s.get("n_max")
            try:
                lo_i = int(lo)
                hi_i = int(hi)
            except Exception:
                continue
            n_min = lo_i if n_min is None else min(n_min, lo_i)
            n_max = hi_i if n_max is None else max(n_max, hi_i)
        if n_min is not None and n_max is not None:
            normalized["x_domain"] = {"min": int(n_min), "max": int(n_max)}
            diagnostics.append("normalized_discrete_integer_domain")

    if "grid" not in normalized:
        normalized["grid"] = True
    if "axes_lines" not in normalized:
        normalized["axes_lines"] = True
    if "legend" not in normalized:
        normalized["legend"] = True
    if "points" not in normalized or not isinstance(normalized.get("points"), list):
        normalized["points"] = []
    if "layers" not in normalized or not isinstance(normalized.get("layers"), list):
        normalized["layers"] = []
    if "annotations" not in normalized or not isinstance(normalized.get("annotations"), list):
        normalized["annotations"] = []

    _normalize_key_points(normalized, diagnostics)
    return normalized, diagnostics
