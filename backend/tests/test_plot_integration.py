import pytest
from app.services.plot_integration import apply_graph_mode_override

def test_apply_graph_mode_override_off():
    solve_result = {
        "visuals": {
            "should_visualize": True,
            "plots": [{"id": "test_plot"}],
            "alternative_visual": {"kind": "table"}
        }
    }
    result = apply_graph_mode_override(solve_result, "off")
    assert result["visuals"]["should_visualize"] is False
    assert result["visuals"]["plots"] == []
    assert result["visuals"]["alternative_visual"] is None
    assert "Forced OFF" in result["visuals"]["decision_reason"]

def test_apply_graph_mode_override_on():
    solve_result = {
        "visuals": {
            "should_visualize": False,
            "plots": []
        }
    }
    result = apply_graph_mode_override(solve_result, "on")
    assert result["visuals"]["should_visualize"] is True
    assert "Forced ON" in result["visuals"]["decision_reason"]

def test_apply_graph_mode_override_auto_no_plot():
    solve_result = {
        "visuals": {
            "should_visualize": False,
            "decision_reason": "original reasoning"
        }
    }
    result = apply_graph_mode_override(solve_result, "auto", plot_generated=False)
    assert result["visuals"]["should_visualize"] is False
    assert result["visuals"]["decision_reason"] == "original reasoning"

def test_apply_graph_mode_override_auto_with_plot():
    solve_result = {
        "visuals": {
            "should_visualize": False,
            "decision_reason": "original reasoning"
        }
    }
    result = apply_graph_mode_override(solve_result, "auto", plot_generated=True)
    assert result["visuals"]["should_visualize"] is True

def test_apply_graph_mode_override_missing_visuals():
    solve_result = {}
    result = apply_graph_mode_override(solve_result, "on")
    assert result["visuals"]["should_visualize"] is True
    assert result["visuals"]["plots"] == []
