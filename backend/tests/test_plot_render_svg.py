from __future__ import annotations

import pytest

from app.plot.cache import build_cache_key
from app.plot.render_svg import render_recipe_svg
from app.plot.sympy_safe import SympySafeError, safe_parse_expr


def test_function_plot_svg_contains_svg_tag() -> None:
    recipe = {
        "kind": "function_2d",
        "title": "Parabola",
        "x_label": "x",
        "y_label": "y",
        "x_domain": {"min": -4, "max": 4},
        "y_domain": {"min": -2, "max": 10},
        "grid": True,
        "axes_lines": True,
        "legend": True,
        "series": [{"kind": "function", "label": "y=x^2", "y_expr_sympy": "x**2", "variable": "x"}],
        "points": [],
        "shapes": [],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert "<svg" in svg.lower()
    assert warnings == [] or isinstance(warnings, list)


def test_parametric_circle_renders() -> None:
    recipe = {
        "kind": "geometry_2d",
        "title": "Circle",
        "x_label": "x",
        "y_label": "y",
        "x_domain": {"min": -2, "max": 2},
        "y_domain": {"min": -2, "max": 2},
        "grid": True,
        "axes_lines": True,
        "legend": True,
        "series": [
            {
                "kind": "parametric",
                "label": "unit circle",
                "x_expr_sympy": "cos(t)",
                "y_expr_sympy": "sin(t)",
                "variable": "t",
                "params": [{"name": "t", "text": "0..2*pi"}],
            }
        ],
        "points": [],
        "shapes": [],
    }
    svg, _, _ = render_recipe_svg(recipe)
    assert "<svg" in svg.lower()


def test_implicit_circle_contour_renders() -> None:
    recipe = {
        "kind": "geometry_2d",
        "title": "Implicit circle",
        "x_label": "x",
        "y_label": "y",
        "x_domain": {"min": -2, "max": 2},
        "y_domain": {"min": -2, "max": 2},
        "grid": True,
        "axes_lines": True,
        "legend": True,
        "series": [{"kind": "implicit", "label": "x^2+y^2=1", "implicit_expr_sympy": "x**2 + y**2 - 1"}],
        "points": [],
        "shapes": [],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert "<svg" in svg.lower()
    assert isinstance(warnings, list)


def test_discontinuity_breaks_no_crash() -> None:
    recipe = {
        "kind": "function_2d",
        "title": "tan(x)",
        "x_label": "x",
        "y_label": "y",
        "x_domain": {"min": -3.14, "max": 3.14},
        "y_domain": {"min": -10, "max": 10},
        "grid": True,
        "axes_lines": True,
        "legend": False,
        "series": [{"kind": "function", "label": "tan(x)", "y_expr_sympy": "tan(x)", "variable": "x"}],
        "points": [],
        "shapes": [],
    }
    svg, _, _ = render_recipe_svg(recipe)
    assert "<svg" in svg.lower()


def test_cache_key_stable() -> None:
    recipe = {"kind": "function_2d", "series": [{"kind": "function", "y_expr_sympy": "x+1"}]}
    opts = {"width_px": 900, "height_px": 520, "font_scale": 1.0}
    key1 = build_cache_key(recipe, opts)
    key2 = build_cache_key(recipe, opts)
    assert key1 == key2


def test_safe_parser_rejects_bad_input() -> None:
    with pytest.raises(SympySafeError):
        safe_parse_expr("__import__('os').system('whoami')", allowed_symbols=["x"])
