from __future__ import annotations

from app.services.math_render_service import (
    canonical_render_key,
    has_forbidden_svg,
    sanitize_svg_server,
    split_latex_segments,
)


def test_canonical_key_stable() -> None:
    key1 = canonical_render_key(
        latex=r"\frac{1}{2}",
        display_mode=True,
        macros={"\\RR": "\\mathbb{R}"},
        scale=1.0,
        font="tex",
    )
    key2 = canonical_render_key(
        latex=r"\frac{1}{2}",
        display_mode=True,
        macros={"\\RR": "\\mathbb{R}"},
        scale=1.0,
        font="tex",
    )
    assert key1 == key2
    assert key1.startswith("texsvg:v1:")


def test_sanitizer_removes_forbidden_constructs() -> None:
    raw = """
    <svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">
      <script>alert(1)</script>
      <foreignObject><div>bad</div></foreignObject>
      <a href="javascript:alert(1)">x</a>
      <g onclick="x()"><path d="M0 0 L1 1" /></g>
    </svg>
    """
    cleaned = sanitize_svg_server(raw)
    assert "<script" not in cleaned.lower()
    assert "foreignobject" not in cleaned.lower()
    assert "onclick=" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()
    assert not has_forbidden_svg(cleaned)


def test_latex_segmentation_ignores_code_and_escaped_dollar() -> None:
    sample = r"""
Here is $x+1$ and escaped \$ money.
```python
z = "$not_math$"
```
Then $$\int_0^1 x dx$$ and \(a+b\) and \[c+d\].
"""
    segments = split_latex_segments(sample)
    math_parts = [s for s in segments if s.get("kind") == "math"]
    assert any(m.get("latex") == "x+1" for m in math_parts)
    assert any("int_0^1" in m.get("latex", "") for m in math_parts)
    assert any(m.get("latex") == "a+b" for m in math_parts)
    assert any(m.get("latex") == "c+d" for m in math_parts)
    # Code block content should not be parsed as math.
    assert not any("$not_math$" == m.get("latex") for m in math_parts)

