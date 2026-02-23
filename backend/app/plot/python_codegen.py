from __future__ import annotations

import re
from typing import Any, Dict, List

from app.plot.recipe_normalizer import normalize_recipe


def _expr_to_python(expr: str) -> str:
    text = str(expr or "").strip()
    if not text:
        return text
    text = text.replace("^", "**")
    text = text.replace("\\pi", "np.pi")
    text = text.replace("pi", "np.pi")
    text = text.replace("\\sin", "np.sin").replace("sin", "np.sin")
    text = text.replace("\\cos", "np.cos").replace("cos", "np.cos")
    text = text.replace("\\tan", "np.tan").replace("tan", "np.tan")
    text = text.replace("\\sqrt", "np.sqrt").replace("sqrt", "np.sqrt")
    text = text.replace("\\exp", "np.exp").replace("exp", "np.exp")
    text = text.replace("\\log", "np.log").replace("log", "np.log")
    text = re.sub(r"\bAbs\(", "np.abs(", text)
    text = re.sub(r"\babs\(", "np.abs(", text)
    return text


def generate_python_code_from_recipe(recipe: Dict[str, Any]) -> str:
    normalized, _ = normalize_recipe(recipe if isinstance(recipe, dict) else {})
    x_domain = normalized.get("x_domain") if isinstance(normalized.get("x_domain"), dict) else {}
    y_domain = normalized.get("y_domain") if isinstance(normalized.get("y_domain"), dict) else {}
    x_min = x_domain.get("min", -10)
    x_max = x_domain.get("max", 10)
    y_min = y_domain.get("min")
    y_max = y_domain.get("max")
    title = str(normalized.get("title") or "Generated Plot")
    x_label = str(normalized.get("x_label") or "x")
    y_label = str(normalized.get("y_label") or "y")

    lines: List[str] = [
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "",
        "fig, ax = plt.subplots(figsize=(10, 5.6))",
    ]

    series = normalized.get("series") if isinstance(normalized.get("series"), list) else []
    for idx, row in enumerate(series, start=1):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "").lower()
        label = str(row.get("label") or f"series_{idx}").replace("'", "\\'")
        if kind == "sequence":
            n_min = int(row.get("n_min", x_min))
            n_max = int(row.get("n_max", x_max))
            expr = _expr_to_python(str(row.get("expr_sympy") or row.get("y_expr_sympy") or "0"))
            lines.extend(
                [
                    f"n{idx} = np.arange({n_min}, {n_max + 1}, dtype=int)",
                    f"y{idx} = {expr.replace('n', f'n{idx}')}",
                ]
            )
            if str(row.get("sequence_kind") or "").lower() == "partial_sum":
                lines.append(f"y{idx} = np.cumsum(y{idx})")
            lines.append(f"ax.plot(n{idx}, y{idx}, marker='o', markersize=2.5, linewidth=1.8, label='{label}')")
        elif kind == "function":
            expr = _expr_to_python(str(row.get('y_expr_sympy') or row.get('y_expr_latex') or row.get('expr_sympy') or '0'))
            lines.extend(
                [
                    f"x{idx} = np.linspace({x_min}, {x_max}, 500)",
                    f"y{idx} = {expr.replace('x', f'x{idx}')}",
                    f"ax.plot(x{idx}, y{idx}, linewidth=2.0, label='{label}')",
                ]
            )
        elif kind == "parametric":
            x_expr = _expr_to_python(str(row.get("x_expr_sympy") or row.get("x_expr_latex") or "0"))
            y_expr = _expr_to_python(str(row.get("y_expr_sympy") or row.get("y_expr_latex") or "0"))
            lines.extend(
                [
                    f"t{idx} = np.linspace(0, 2*np.pi, 800)",
                    f"xp{idx} = {x_expr.replace('t', f't{idx}')}",
                    f"yp{idx} = {y_expr.replace('t', f't{idx}')}",
                    f"ax.plot(xp{idx}, yp{idx}, linewidth=2.0, label='{label}')",
                ]
            )

    points = normalized.get("points") if isinstance(normalized.get("points"), list) else []
    if points:
        lines.append("")
        lines.append("# points")
        for p_idx, p in enumerate(points, start=1):
            if not isinstance(p, dict):
                continue
            x = p.get("x")
            y = p.get("y")
            label = str(p.get("label") or "").replace("'", "\\'")
            lines.append(f"ax.scatter([{x}], [{y}], s=30, zorder=5)")
            if label:
                lines.append(f"ax.annotate('{label}', ({x}, {y}), xytext=(6, 6), textcoords='offset points')")

    annotations = normalized.get("annotations") if isinstance(normalized.get("annotations"), list) else []
    if annotations:
        lines.append("")
        lines.append("# annotations")
        for a in annotations:
            if not isinstance(a, dict):
                continue
            a_type = str(a.get("type") or "").lower()
            if a_type == "hline" and a.get("y") is not None:
                y = a.get("y")
                lines.append(f"ax.axhline({y}, linestyle='--', linewidth=1.2, color='#0f766e')")
            if a_type == "vline" and a.get("x") is not None:
                x = a.get("x")
                lines.append(f"ax.axvline({x}, linestyle='--', linewidth=1.2, color='#0f766e')")

    lines.extend(
        [
            "",
            f"ax.set_title({title!r})",
            f"ax.set_xlabel({x_label!r})",
            f"ax.set_ylabel({y_label!r})",
            "ax.grid(True, alpha=0.25)",
            "ax.axhline(0, linewidth=1.0, color='#64748b', alpha=0.8)",
            "ax.axvline(0, linewidth=1.0, color='#64748b', alpha=0.8)",
            f"ax.set_xlim({x_min}, {x_max})",
        ]
    )
    if y_min is not None and y_max is not None:
        lines.append(f"ax.set_ylim({y_min}, {y_max})")
    if bool(normalized.get("legend", True)):
        lines.append("ax.legend(loc='best')")
    lines.extend(["plt.tight_layout()", "plt.show()"])
    return "\n".join(lines).strip() + "\n"

