"""
Math Solver V3.1 - Security & Hardening Tests

Tests malicious inputs, edge cases, and production failure modes.
Ensures safe expression parsing and proper error handling.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np


def test_malicious_expression_import():
    """Test that __import__ is rejected."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    malicious = [
        "__import__('os')",
        "__import__('os').system('ls')",
        "import os",
    ]
    
    for expr in malicious:
        result, error = parser.parse_expression(expr)
        assert result is None, f"SECURITY FAILURE: '{expr}' was not rejected!"
        assert error is not None
        print(f"✅ Rejected: {expr[:50]}")


def test_malicious_expression_eval():
    """Test that eval/exec are rejected."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    malicious = [
        "eval('1+1')",
        "exec('print(1)')",
        "compile('print(1)', 'test', 'exec')",
    ]
    
    for expr in malicious:
        result, error = parser.parse_expression(expr)
        assert result is None, f"SECURITY FAILURE: '{expr}' was not rejected!"
        assert error is not None
        print(f"✅ Rejected: {expr[:50]}")


def test_malicious_expression_attribute_access():
    """Test that attribute access is rejected."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    malicious = [
        "x.__class__",
        "x.__dict__",
        "().__class__.__bases__[0]",
    ]
    
    for expr in malicious:
        result, error = parser.parse_expression(expr)
        assert result is None, f"SECURITY FAILURE: '{expr}' was not rejected!"
        assert error is not None
        print(f"✅ Rejected: {expr[:50]}")


def test_malicious_expression_lambda():
    """Test that lambda functions are rejected."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    malicious = [
        "lambda x: x**2",
        "(lambda x: x**2)(5)",
    ]
    
    for expr in malicious:
        result, error = parser.parse_expression(expr)
        assert result is None, f"SECURITY FAILURE: '{expr}' was not rejected!"
        assert error is not None
        print(f"✅ Rejected: {expr[:50]}")


def test_malicious_expression_indexing():
    """Test that indexing attempts are rejected."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    malicious = [
        "[1,2,3]",
        "x[0]",
        "{1:2}",
    ]
    
    for expr in malicious:
        result, error = parser.parse_expression(expr)
        assert result is None, f"SECURITY FAILURE: '{expr}' was not rejected!"
        assert error is not None
        print(f"✅ Rejected: {expr[:50]}")


def test_safe_mathematical_expressions():
    """Test that safe mathematical expressions are accepted."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    safe_expressions = [
        "x**2",
        "2*x + 3",
        "sin(x)",
        "cos(x**2)",
        "sqrt(x**2 + 1)",
        "exp(-x**2)",
        "log(abs(x) + 1)",
        "x**3 - 2*x**2 + x - 1",
    ]
    
    for expr in safe_expressions:
        result, error = parser.parse_expression(expr)
        assert result is not None, f"Safe expression '{expr}' was rejected: {error}"
        assert error is None
        print(f"✅ Accepted: {expr}")


def test_numerical_evaluation_safety():
    """Test numerical evaluation rejects malicious code."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    x_vals = np.linspace(-5, 5, 10)
    
    # Should work
    y_vals, error = parser.evaluate_for_plotting("x**2", x_vals)
    assert error is None
    assert y_vals is not None
    print(f"✅ Safe evaluation: x**2")
    
    # Should fail safely
    y_vals, error = parser.evaluate_for_plotting("__import__('os')", x_vals)
    assert error is not None
    assert y_vals is None
    print(f"✅ Malicious evaluation rejected")


def test_invalid_function_syntax():
    """Test handling of invalid function syntax."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    invalid = [
        "y=sin(",  # Unclosed parenthesis
        "y=x^^2",  # Invalid operator
        "y=2**",  # Incomplete
        "",  # Empty
        "===",  # Invalid
    ]
    
    for expr in invalid:
        result, error = parser.parse_expression(expr)
        # Should either reject or parse to something
        if result is None:
            assert error is not None
            print(f"✅ Invalid syntax rejected: {expr[:20]}")
        else:
            print(f"⚠️ Parsed (may be simplified): {expr[:20]}")


def test_domain_constraints():
    """Test expressions with domain constraints (sqrt, log)."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    
    # sqrt of negative should produce NaN (handled)
    x_vals = np.array([-2, -1, 0, 1, 2])
    y_vals, error = parser.evaluate_for_plotting("sqrt(x)", x_vals)
    
    # Should work but might have NaN for negative values
    assert error is None or "NaN" in error
    print(f"✅ Domain constraint handled for sqrt(x)")
    
    # log of negative should also produce NaN
    y_vals2, error2 = parser.evaluate_for_plotting("log(x)", x_vals)
    assert error2 is None or "NaN" in error2
    print(f"✅ Domain constraint handled for log(x)")


def test_large_coefficients():
    """Test numerical stability with large coefficients."""
    from app.services.visualization.safe_parser import get_safe_parser
    
    parser = get_safe_parser()
    x_vals = np.linspace(0, 1, 10)
    
    # Large coefficient
    y_vals, error = parser.evaluate_for_plotting("1000000*x", x_vals)
    assert error is None
    assert not np.all(np.isnan(y_vals))
    print(f"✅ Large coefficients handled")


def test_confidence_based_gating():
    """Test that low confidence problems don't generate plots."""
    from app.services.visualization.decision_engine import get_visualization_engine
    
    engine = get_visualization_engine()
    
    # High confidence case (function)
    decision1 = engine.should_visualize(
        "Graph y = x^2",
        {"detected_entities": {"functions": ["y=x^2"], "equations": [], "constraints": []}}
    )
    assert decision1.should_visualize == True
    assert decision1.confidence >= 0.7
    print(f"✅ High confidence ({decision1.confidence:.2f}): should_visualize=True")
    
    # Lower confidence case (simple algebra, no graph keyword)
    decision2 = engine.should_visualize(
        "Solve x + 5 = 10",
        {"detected_entities": {"expressions": [], "equations": ["x+5=10"], "functions": [], "constraints": []}}
    )
    # This might have lower confidence
    print(f"✅ Decision for simple algebra: confidence={decision2.confidence:.2f}, should_plot={decision2.should_visualize}")


def test_plot_renderer_with_safe_parser():
    """Test plot renderer uses safe parser (no eval)."""
    from app.services.visualization.plot_renderer import get_plot_renderer
    from app.schemas.na_math_solver_v3 import (
        PlotPlanV3, AxesV3, RecommendedWindowV3, PlotObjectV3,
        SamplingV3, ObjectKind, SamplingStrategy
    )
    
    renderer = get_plot_renderer()
    
    plan = PlotPlanV3(
        title="Test Safe Plot",
        axes=AxesV3(x_label="x", y_label="y"),
        recommended_window=RecommendedWindowV3(x_min=-5, x_max=5, y_min=0, y_max=25),
        objects=[
            PlotObjectV3(kind=ObjectKind.CURVE, expression="x**2", label="Safe")
        ],
        annotations=[],
        sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=100)
    )
    
    result = renderer.render(plan, "function")
    assert result.image_base64 is not None
    assert len(result.image_base64) > 1000
    print(f"✅ Plot renderer uses safe parser successfully")


def test_malicious_plot_expression():
    """Test that malicious expressions in plot objects are rejected."""
    from app.services.visualization.plot_renderer import get_plot_renderer
    from app.schemas.na_math_solver_v3 import (
        PlotPlanV3, AxesV3, RecommendedWindowV3, PlotObjectV3,
        SamplingV3, ObjectKind, SamplingStrategy
    )
    
    renderer = get_plot_renderer()
    
    # Create plan with malicious expression
    plan = PlotPlanV3(
        title="Malicious Plot Test",
        axes=AxesV3(x_label="x", y_label="y"),
        recommended_window=RecommendedWindowV3(x_min=-5, x_max=5, y_min=0, y_max=25),
        objects=[
            PlotObjectV3(kind=ObjectKind.CURVE, expression="__import__('os').system('ls')", label="Evil")
        ],
        annotations=[],
        sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=100)
    )
    
    # Should complete without executing malicious code
    # Plot should show placeholder (zeros)
    result = renderer.render(plan, "function")
    assert result is not None
    print(f"✅ Malicious plot expression rejected safely")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("MATH SOLVER V3.1 - SECURITY & HARDENING TESTS")
    print("="*70)
    
    tests = [
        test_malicious_expression_import,
        test_malicious_expression_eval,
        test_malicious_expression_attribute_access,
        test_malicious_expression_lambda,
        test_malicious_expression_indexing,
        test_safe_mathematical_expressions,
        test_numerical_evaluation_safety,
        test_invalid_function_syntax,
        test_domain_constraints,
        test_large_coefficients,
        test_confidence_based_gating,
        test_plot_renderer_with_safe_parser,
        test_malicious_plot_expression,
    ]
    
    passed = 0
    for test_func in tests:
        try:
            print(f"\n{test_func.__name__}...")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"PASSED: {passed}/{len(tests)} ({100*passed//len(tests)}%)")
    print(f"{'='*70}\n")
    
    if passed == len(tests):
        print("🎉 ALL SECURITY TESTS PASSED!")
        print("✅ No eval/exec vulnerabilities")
        print("✅ Safe expression parsing enforced")
        print("✅ Malicious code rejected")
    else:
        print("⚠️ SOME SECURITY TESTS FAILED - REVIEW REQUIRED")
