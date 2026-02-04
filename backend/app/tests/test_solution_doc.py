from app.services.solve.solution_doc import (
    build_solution_doc,
    latex_normalize,
    parse_solution_doc,
    render_solution_doc_markdown,
)


def test_latex_normalize_repairs_sqrt_and_delimiters():
    raw = r"\( \sqrt(x+5) = x-1 \)"
    out = latex_normalize(raw)
    assert "$" in out
    assert r"\sqrt{x+5}" in out


def test_parse_solution_doc_multiline_steps():
    text = """
Domain constraints:
- $x+5 \\ge 0$
- $x-1 \\ge 0$

Step 1: State Domain Constraints
Radicand must be nonnegative.

RHS must be nonnegative.

Step 2: Isolate The Square Root
Rewrite as $\\sqrt{x+5}=x-1$.

Verification:
1) Substitute candidate into both sides.

Final Answer: x = 4
LaTeX: x = 4
""".strip()
    doc = parse_solution_doc(text, problem_text=r"\sqrt{x+5}=x-1")
    assert doc["parse_status"] in {"ok", "partial"}
    assert len(doc["steps"]) >= 2
    assert "RHS must be nonnegative." in doc["steps"][0]["body_markdown"]


def test_autocorrect_sqrt_equation_final_answer():
    text = """
Step 1: Start Solving
$\\sqrt{x+5}=x-1$

Final Answer: x \\ge -5
LaTeX: x \\ge -5
""".strip()
    doc = build_solution_doc(text, problem_text=r"\sqrt{x+5}=x-1")
    assert doc["autocorrect"]["applied"] is True
    assert doc["final_answer"]["latex"] == "x = 4"
    assert "$x + 5 \\ge 0$" in doc["domain_constraints"] or "$x+5 \\ge 0$" in doc["domain_constraints"]


def test_json_string_solution_doc_is_parsed():
    raw = """{
  "domain_constraints": ["x + 2 != 0"],
  "steps": ["Step 1: Rewrite Relation", "Step 2: Swap Variables"],
  "final_answer": {"text": "f^{-1}(x)=(2x+1)/(1-x)", "latex": "f^{-1}(x)=\\\\frac{2x+1}{1-x}"}
}"""
    doc = parse_solution_doc(raw, problem_text="inverse f(x) = (x-1)/(x+2)")
    assert doc["parse_status"] == "ok"
    assert len(doc["steps"]) >= 2
    assert doc["final_answer"]["latex"] == r"f^{-1}(x)=\frac{2x+1}{1-x}"


def test_inverse_problem_does_not_force_empty_autocorrect():
    raw = """Step 1: Swap Variables
Set x = (y-1)/(y+2).
Final Answer: f^{-1}(x)=\\frac{2x+1}{1-x}
LaTeX: f^{-1}(x)=\\frac{2x+1}{1-x}
"""
    doc = build_solution_doc(raw, problem_text="inverse f(x) = (x-1)/(x+2)")
    assert doc["autocorrect"]["applied"] is False
    assert "varnothing" not in (doc["final_answer"]["latex"] or "")


def test_markdown_contract_sections_and_plotly_block():
    raw = """
# Recognized Problem
Solve x^2-5x+6=0

# Domain Constraints
- None

# Steps
## Step 1: Factor The Polynomial
Write as $(x-2)(x-3)=0$.

## Step 2: Solve Each Factor
Set each factor to zero.

# Graphs
```plotly
{"data":[{"type":"scatter","x":[0,1],"y":[2,3]}],"layout":{"title":"t"}}
```

# Verification
- Substitute both roots.

# Final Answer
**Text:** x = 2 or x = 3
**LaTeX:** $$x \\in \\{2,3\\}$$
""".strip()
    doc = parse_solution_doc(raw, problem_text="x^2-5x+6=0")
    assert doc["parse_status"] == "ok"
    assert len(doc["steps"]) == 2
    assert len(doc["plots"]) == 1
    md = render_solution_doc_markdown(doc)
    assert md.startswith("# Recognized Problem")
    assert "```plotly" in md
    assert '"steps": [' not in md


def test_markdown_step_body_multiline_and_duplicate_prefix_removed():
    raw = """
# Recognized Problem
Find asymptotes of $\\frac{2x^2+3}{x-1}$.

# Domain Constraints
- $x \\ne 1$

# Steps
## Step 1: Perform Polynomial Division
Step 1: Perform Polynomial Division

Write
$$
\\frac{2x^2+3}{x-1}=2x+2+\\frac{5}{x-1}.
$$

## Step 2: Read Asymptotes From Form
- Vertical: $x=1$
- Slant: $y=2x+2$

# Graphs
- None

# Verification
- Substitute sample values near $x=1$.

# Final Answer
**Text:** Vertical asymptote x=1; slant asymptote y=2x+2.
**LaTeX:** $$x=1,\\ y=2x+2$$
""".strip()
    doc = parse_solution_doc(raw, problem_text=r"\frac{2x^2+3}{x-1}")
    assert doc["parse_status"] == "ok"
    assert len(doc["steps"]) == 2
    assert not doc["steps"][0]["body_markdown"].startswith("Step 1:")
    assert "Write" in doc["steps"][0]["body_markdown"]


def test_invalid_plotly_block_records_parse_error():
    raw = """
# Recognized Problem
Plot y=x^2

# Domain Constraints
- None

# Steps
## Step 1: Define The Function
Use $y=x^2$.

# Graphs
```plotly
{"data": "invalid"}
```

# Verification
- None

# Final Answer
**Text:** The function is plotted.
**LaTeX:** $$y=x^2$$
""".strip()
    doc = parse_solution_doc(raw, problem_text="plot y=x^2")
    assert doc["parse_status"] in {"ok", "partial"}
    assert len(doc["plots"]) == 0
    assert any("plotly" in err for err in doc["parse_errors"])


def test_legacy_json_like_blob_is_salvaged():
    raw = """
{
  "domain_constraints": "• x + 2 != 0\\n• y != 1",
  "steps": [
    "Step 1: Swap Variables — Set x = (y-1)/(y+2).",
    "Step 2: Isolate Y — Solve for y."
  ],
  "final_answer": "Final Answer: f^{-1}(x)=(2x+1)/(1-x)"
}
""".strip()
    doc = parse_solution_doc(raw, problem_text="inverse f(x)=(x-1)/(x+2)")
    assert doc["parse_status"] in {"ok", "partial"}
    assert len(doc["steps"]) >= 2
    assert len(doc["domain_constraints"]) >= 1
