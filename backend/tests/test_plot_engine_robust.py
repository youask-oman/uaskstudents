from __future__ import annotations

import re

from app.plot.render_svg import render_recipe_svg


def _has_svg(svg: str) -> bool:
    return "<svg" in str(svg).lower()


def test_discrete_alternating_series_partial_sum_renders() -> None:
    recipe = {
        "title": "Partial sums",
        "x_label": "N",
        "y_label": "S_N",
        "expressions": ["S_N = cumsum((-1)^(n+1)/n^2) for n=1..200"],
        "domain": {"x_min": 1, "x_max": 200, "y_min": None, "y_max": None},
        "key_points": [{"label": "N=20", "x": 20}],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert _has_svg(svg)
    assert not any("fallback_plot_rendered" == w for w in warnings)


def test_discrete_sampling_overrides_bad_n_points() -> None:
    recipe = {
        "x_domain": {"min": 1, "max": 50},
        "y_domain": {"min": None, "max": None},
        "series": [
            {
                "kind": "sequence",
                "sequence_kind": "term",
                "expr_sympy": "(-1)**(n+1)/n**2",
                "variable": "n",
                "n_min": 1,
                "n_max": 50,
                "n_points": 10,
            }
        ],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert _has_svg(svg)
    assert not any("fallback_plot_rendered" == w for w in warnings)


def test_continuous_function_with_autoscale() -> None:
    recipe = {
        "kind": "function_2d",
        "x_domain": {"min": -1, "max": 6},
        "y_domain": {"min": None, "max": None},
        "series": [{"kind": "function", "label": "f(x)", "y_expr_sympy": "x**3-6*x**2+9*x+1", "variable": "x"}],
        "points": [{"x": 1, "y": 5, "label": "critical"}],
    }
    svg, _, _ = render_recipe_svg(recipe)
    assert _has_svg(svg)


def test_parametric_circle_renders_no_blank() -> None:
    recipe = {
        "kind": "geometry_2d",
        "x_domain": {"min": -2, "max": 2},
        "y_domain": {"min": -2, "max": 2},
        "series": [
            {
                "kind": "parametric",
                "x_expr_sympy": "cos(t)",
                "y_expr_sympy": "sin(t)",
                "variable": "t",
                "params": [{"name": "t", "text": "0..2*pi"}],
            }
        ],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert _has_svg(svg)
    assert not any("fallback_plot_rendered" == w for w in warnings)


def test_invalid_recipe_uses_fallback_not_blank() -> None:
    recipe = {
        "x_domain": {"min": 0, "max": 1},
        "y_domain": {"min": None, "max": None},
        "series": [{"kind": "function", "y_expr_sympy": ""}],
        "annotations": [{"type": "hline", "y": 0.2, "label": "target"}],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert _has_svg(svg)
    assert any("fallback_plot_rendered" == w for w in warnings)


def test_key_point_placeholder_becomes_hline() -> None:
    recipe = {
        "x_domain": {"min": 1, "max": 200},
        "y_domain": {"min": None, "max": None},
        "expressions": ["S_N = cumsum((-1)^(n+1)/n^2) for n=1..200"],
        "key_points": [{"label": "S_est", "x": "N_range", "y": 0.822467}],
    }
    svg, warnings, _ = render_recipe_svg(recipe)
    assert _has_svg(svg)
    assert any("normalized_key_point_placeholder_to_hline" == w for w in warnings)

