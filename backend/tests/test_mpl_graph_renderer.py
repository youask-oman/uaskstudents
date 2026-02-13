from __future__ import annotations

import math

import numpy as np

from app.services.graph.mpl_render import render_graph, sample_function_series


def test_tan_discontinuity_inserts_nans():
    x, y = sample_function_series("tan(x)", x_range=(-math.pi, math.pi), n=1200)
    assert x is not None and y is not None
    assert np.isnan(y).any()


def test_rational_discontinuity_at_x2():
    x, y = sample_function_series("1/(x-2)", x_range=(-5, 5), n=1200)
    assert x is not None and y is not None
    assert np.isnan(y).any()


def test_sqrt_negative_domain_becomes_nan():
    x, y = sample_function_series("sqrt(x)", x_range=(-4, 4), n=800)
    assert x is not None and y is not None
    neg_mask = x < 0
    assert np.isnan(y[neg_mask]).any()


def test_vertical_line_render_svg():
    spec = {
        "title": "Vertical",
        "axes": {"x_label": "x", "y_label": "y", "x_range": [-5, 5], "y_range": [-5, 5]},
        "series": [{"expression_latex": "x=2", "label": "x=2"}],
    }
    svg, meta = render_graph(spec, fmt="svg")
    assert svg.startswith(b"<?xml") or b"<svg" in svg[:200]
    assert meta.plot_type == "line_const"


def test_points_and_segment_render_png():
    spec = {
        "title": "Points+segment",
        "series": [
            {
                "label": "segment",
                "mode": "lines+markers",
                "points": [{"x": 0, "y": 1}, {"x": 1, "y": 2}, {"x": 2, "y": 4}],
            }
        ],
        "axes": {"x_range": [-1, 3], "y_range": [0, 5]},
    }
    png, meta = render_graph(spec, fmt="png")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert meta.plot_type == "series_points"
