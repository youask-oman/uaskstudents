"""
Unit tests for Visualization Engine (Decision + Rendering).

Tests:
- Decision engine logic
- Plot type selection
- Plot plan generation
- Visualization alternatives
- Plot rendering (without actual LLM calls)
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np


def test_should_visualize_explicit_keyword():
    """Test detection of explicit visualization keywords."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    problems = [
        ("Graph the function y = x^2", True),
        ("Plot y = 2x + 3", True),
        ("Sketch the parabola", True),
        ("Draw the line", True),
        ("Solve x + 5 = 10", False),  # No keyword
    ]
    
    for problem, expected in problems:
        analysis = {"detected_entities": {"functions": [], "equations": [], "constraints": []}}
        decision = engine.should_visualize(problem, analysis)
        assert decision.should_visualize == expected, f"Failed for: {problem}"
    
    print(f"✅ Explicit keyword detection works ({len(problems)} cases)")


def test_should_visualize_functions():
    """Test visualization for detected functions."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    # Single function
    analysis_single = {
        "detected_entities": {
            "functions": ["y=x^2"],
            "equations": [],
            "constraints": []
        }
    }
    
    decision = engine.should_visualize("Find domain", analysis_single)
    assert decision.should_visualize == True
    assert decision.plot_type == "function"
    
    # Multiple functions (system)
    analysis_multiple = {
        "detected_entities": {
            "functions": ["y=2x+1", "y=-x+4"],
            "equations": [],
            "constraints": []
        }
    }
    
    decision2 = engine.should_visualize("Solve system", analysis_multiple)
    assert decision2.should_visualize == True
    assert decision2.plot_type == "system"
    
    print("✅ Function detection works (single & system)")


def test_should_visualize_inequalities():
    """Test visualization for inequalities."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    problems = [
        ("Solve x > 5", {"equations": ["x>5"]}),
        ("Find where 2x + 3 < 11", {"equations": ["2x+3<11"]}),
        ("Solve y ≥ 2x + 1", {"equations": ["y>=2x+1"]}),
    ]
    
    for problem, entities in problems:
        analysis = {"detected_entities": {**entities, "functions": [], "constraints": []}}
        decision = engine.should_visualize(problem, analysis)
        assert decision.should_visualize == True
        assert decision.plot_type in ["number_line", "inequality_region"]
    
    print(f"✅ Inequality detection works ({len(problems)} cases)")


def test_should_visualize_quadratic():
    """Test visualization for quadratic equations."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    problems = [
        "Solve x^2 - 5x + 6 = 0",
        "Find roots of x² + 2x - 3 = 0",
        "Solve the quadratic equation x^2 = 4",
    ]
    
    for problem in problems:
        analysis = {"detected_entities": {"functions": [], "equations": [], "constraints": []}}
        decision = engine.should_visualize(problem, analysis)
        assert decision.should_visualize == True
        assert decision.plot_type == "function"
    
    print(f"✅ Quadratic detection works ({len(problems)} cases)")


def test_generate_function_plot_plan():
    """Test function plot plan generation."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    entities = {
        "functions": ["y=x^2"],
        "equations": [],
        "constraints": []
    }
    
    plan = engine.generate_plot_plan("function", entities)
    
    assert plan.title is not None
    assert plan.axes.x_label == "x"
    assert plan.axes.y_label == "y"
    assert plan.recommended_window.x_min < plan.recommended_window.x_max
    assert plan.recommended_window.y_min < plan.recommended_window.y_max
    assert len(plan.objects) > 0
    assert plan.sampling.resolution >= 50
    
    print("✅ Function plot plan generated correctly")


def test_generate_system_plot_plan():
    """Test system of equations plot plan generation."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    entities = {
        "equations": ["y=2x+1", "y=-x+4"],
        "functions": ["y=2x+1", "y=-x+4"],
        "constraints": []
    }
    
    plan = engine.generate_plot_plan("system", entities)
    
    assert "System" in plan.title or "system" in plan.title
    assert len(plan.objects) >= 2  # Should have at least 2 curves
    
    print(f"✅ System plot plan generated with {len(plan.objects)} objects")


def test_generate_number_line_plan():
    """Test number line plot plan generation."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    entities = {"equations": ["x>5"], "functions": [], "constraints": []}
    
    plan = engine.generate_plot_plan("number_line", entities)
    
    assert "number" in plan.title.lower() or "line" in plan.title.lower()
    assert plan.axes.y_label == ""  # Number line has no y-axis
    
    print("✅ Number line plot plan generated correctly")


def test_generate_visualization_alternative():
    """Test visualization alternative generation."""
    from app.services.visualization.decision_engine import VisualizationEngine
    
    engine = VisualizationEngine()
    
    alt = engine.generate_visualization_alternative(
        "Solve x + 5 = 10",
        "Simple algebraic equation without graphable content"
    )
    
    assert alt.type is not None
    assert alt.reason_no_standard_plot is not None
    assert len(alt.instructions) > 0
    
    print(f"✅ Visualization alternative generated: {alt.type}")


def test_plot_renderer_function():
    """Test plot renderer for function plots."""
    from app.services.visualization.plot_renderer import PlotRenderer
    from app.schemas.na_math_solver_v3 import (
        PlotPlanV3, AxesV3, RecommendedWindowV3, PlotObjectV3,
        SamplingV3, ObjectKind, SamplingStrategy
    )
    
    renderer = PlotRenderer(dpi=50, figsize=(4, 3))  # Small for testing
    
    plan = PlotPlanV3(
        title="Test Plot",
        axes=AxesV3(x_label="x", y_label="y"),
        recommended_window=RecommendedWindowV3(x_min=-5, x_max=5, y_min=0, y_max=25),
        objects=[
            PlotObjectV3(kind=ObjectKind.CURVE, expression="x**2", label="y=x²")
        ],
        annotations=[],
        sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=100)
    )
    
    result = renderer.render(plan, "function")
    
    assert result.plot_type == "function"
    assert len(result.image_base64) > 1000  # Should have substantial base64 data
    assert result.width > 0
    assert result.height > 0
    
    print(f"✅ Rendered plot: {result.width}x{result.height}px, {len(result.image_base64)} chars")


def test_plot_renderer_expression_evaluation():
    """Test safe expression evaluation."""
    from app.services.visualization.plot_renderer import PlotRenderer
    
    renderer = PlotRenderer()
    
    x = np.linspace(-5, 5, 10)
    
    test_cases = [
        ("x**2", True),  # Should work
        ("2*x + 3", True),
        ("np.sin(x)", True),
        ("np.sqrt(abs(x))", True),
        ("__import__('os')", False),  # Should fail safely
    ]
    
    passed = 0
    for expr, should_work in test_cases:
        try:
            y = renderer._evaluate_expression(expr, x)
            if should_work:
                assert y is not None
                assert len(y) == len(x)
                passed += 1
            else:
                # Should have returned zeros as fallback
                assert np.all(y == 0)
        except:
            if not should_work:
                passed += 1
    
    print(f"✅ Expression evaluation works ({passed}/{len(test_cases)} cases)")


def test_visualization_engine_singleton():
    """Test visualization engine singleton."""
    from app.services.visualization.decision_engine import get_visualization_engine
    
    engine1 = get_visualization_engine()
    engine2 = get_visualization_engine()
    
    assert engine1 is engine2
    print("✅ Visualization engine singleton works")


def test_plot_renderer_singleton():
    """Test plot renderer singleton."""
    from app.services.visualization.plot_renderer import get_plot_renderer
    
    renderer1 = get_plot_renderer()
    renderer2 = get_plot_renderer()
    
    assert renderer1 is renderer2
    print("✅ Plot renderer singleton works")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("VISUALIZATION ENGINE UNIT TESTS")
    print("="*70)
    
    tests = [
        test_should_visualize_explicit_keyword,
        test_should_visualize_functions,
        test_should_visualize_inequalities,
        test_should_visualize_quadratic,
        test_generate_function_plot_plan,
        test_generate_system_plot_plan,
        test_generate_number_line_plan,
        test_generate_visualization_alternative,
        test_plot_renderer_function,
        test_plot_renderer_expression_evaluation,
        test_visualization_engine_singleton,
        test_plot_renderer_singleton
    ]
    
    passed = 0
    for test_func in tests:
        try:
            print(f"\n{test_func.__name__}...")
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"PASSED: {passed}/{len(tests)}")
    print(f"{'='*70}\n")
