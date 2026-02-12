
import pytest
from app.services.solve.canonicalization_service import canonicalization_service

def test_intent_detection():
    assert canonicalization_service.get_intent("solve x^2 + 2x + 1 = 0") == "solve_equation"
    assert canonicalization_service.get_intent("find the roots of x^2 + 5x + 6") == "solve_equation"
    assert canonicalization_service.get_intent("factor x^2-5x+6") == "factor"
    assert canonicalization_service.get_intent("simplify (x+1)/(x^2-1)") == "simplify"
    assert canonicalization_service.get_intent("graph y=sin(x)") == "graph"
    assert canonicalization_service.get_intent("plot x^2") == "graph"
    assert canonicalization_service.get_intent("evaluate sin(pi/2)") == "evaluate"
    assert canonicalization_service.get_intent("explain pythagorean theorem") == "explain"

def test_canonical_math_equivalence():
    # Whitespace and Implicit Mult
    text1 = "2x + 1"
    text2 = "2*x+1"
    
    m1, _ = canonicalization_service.normalize_math_object(text1, "solve_equation")
    m2, _ = canonicalization_service.normalize_math_object(text2, "solve_equation")
    assert m1 == m2, f"Expected '{m1}' to equal '{m2}'"

    # Power operator
    text3 = "x^2 + y^2"
    text4 = "x**2 + y**2"
    m3, _ = canonicalization_service.normalize_math_object(text3, "solve_equation")
    m4, _ = canonicalization_service.normalize_math_object(text4, "solve_equation")
    assert m3 == m4

    # Unicode formatting
    text5 = "x − 5 = 0" # unicode minus
    text6 = "x - 5 = 0" # ascii minus
    m5, _ = canonicalization_service.normalize_math_object(text5, "solve_equation")
    m6, _ = canonicalization_service.normalize_math_object(text6, "solve_equation")
    assert m5 == m6

def test_equation_vs_expression():
    # Expression defaults to = 0 for solve intent
    text = "x^2 - 4"
    math, assumptions = canonicalization_service.normalize_math_object(text, "solve_equation")
    assert assumptions.get("implicit_eq_zero") is True
    # Verify it parsed as Eq(..., 0)
    # srepr should show Equality/Add/Pow...
    # Simple check:
    assert "Equality" in math or "Relational" in math or "Eq" in math # srepr varies by version
    
    # Expression kept as expression for simplify intent
    math2, assumptions2 = canonicalization_service.normalize_math_object(text, "simplify")
    assert "implicit_eq_zero" not in assumptions2
    # Should not be Equality
    # SymPy 1.12 srepr for Eq is 'Eq' or 'Equality'
    # srepr for x^2-4 is Add...
    # We can check specific srepr output if needed, but uniqueness is key.

def test_key_uniqueness():
    # Same math, different intent
    text = "x^2 - 4"
    math, assumptions = canonicalization_service.normalize_math_object(text, "solve_equation")
    k1 = canonicalization_service.compute_canonical_key("solve_equation", math, assumptions)
    
    math2, assumptions2 = canonicalization_service.normalize_math_object(text, "factor")
    k2 = canonicalization_service.compute_canonical_key("factor", math2, assumptions2)
    
    assert k1 != k2


def test_expression_canonicalization_never_boolean():
    canonical = canonicalization_service.canonicalize_expression(
        canonicalization_service._parse_relation("sin(x)^2 + cos(x)^2 = 1").lhs  # noqa: SLF001
    )
    assert isinstance(canonical, str)
    assert canonical.lower() not in {"true", "false"}


def test_relation_canonicalization_preserves_relation_shape():
    rel = canonicalization_service._parse_relation("sin(x)^2 + cos(x)^2 = 1")  # noqa: SLF001
    assert rel is not None
    canonical = canonicalization_service.canonicalize_relation(rel)
    assert "Equality" in canonical


def test_factor_forms_canonicalize_equivalently_for_solve_intent():
    m1, _ = canonicalization_service.normalize_math_object("x^2 - 4", "solve_equation")
    m2, _ = canonicalization_service.normalize_math_object("(x-2)(x+2)", "solve_equation")
    assert m1 == m2
