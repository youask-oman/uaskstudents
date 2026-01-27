
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.solver_v3 import SolverV3
from app.schemas.na_math_solver_v3 import SolveResponseV3

# Mock response objects
class MockResponse:
    def __init__(self, content=None, status="completed", finish_reason="stop", incomplete_reason=None):
        self.output = [MagicMock(content=[MagicMock(text=content)])] if content else []
        self.status = status
        self.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        self.incomplete_details = {"reason": incomplete_reason} if incomplete_reason else None
        
        # For chat completions interface fallback
        self.choices = [MagicMock(finish_reason=finish_reason, message=MagicMock(content=content))]

@pytest.fixture
def mock_solver():
    solver = SolverV3()
    solver._client = AsyncMock()
    return solver

@pytest.fixture
def valid_json_content():
    return json.dumps({
        "schema_version": "v1.0",
        "problem": {"original_text": "1+1", "normalized_text": "1+1", "detected_tasks": ["solve_equation"]},
        "classification": {"grade_band": "3-5", "domain": "arithmetic", "topic": "addition", "difficulty": "easy"},
        "refusal": {"is_refusal": False, "reason": "none", "safe_alternative": "none"},
        "assumptions": [],
        "steps": [{"index":1, "title":"Add", "explanation":"Add numbers.", "math_latex":"1+1=2", "rules_used":[], "checkpoint":{"question":"?", "answer":"?"}}],
        "final_answer": {"answer_text": "2", "answer_latex": "2", "values": [{"label":"x", "value":2, "value_latex":"2"}], "units": ""},
        "visuals": {"should_visualize": False, "decision_reason": "simple", "plots": [], "alternative_visual": {"kind": "none", "description": "none", "data": []}},
        "quality": {"confidence": 1.0, "common_mistakes": []}
    })

@pytest.mark.asyncio
async def test_solve_success_pass_1(mock_solver, valid_json_content):
    """Test that valid response on Pass 1 returns data without fallback."""
    # Setup mock to return success (gpt-5 style)
    mock_solver.client.responses.create.return_value = MockResponse(content=valid_json_content, status="completed")
    
    # Execute
    result = await mock_solver.solve("1+1", requested_mode="detailed", max_output_tokens=100)
    
    # Verify
    assert result["final_answer"]["answer_text"] == "2"
    assert result["telemetry"]["openai_calls_count"] == 1
    assert result["telemetry"]["fallback_triggered"] is False
    assert result["telemetry"]["validated"] is True
    
    # Verify args
    call_args = mock_solver.client.responses.create.call_args[1]
    assert call_args["max_output_tokens"] == 100
    assert call_args["reasoning"]["effort"] == "low"
    assert "detailed" in str(call_args["text"]["verbosity"]) or "high" in str(call_args["text"]["verbosity"])

@pytest.mark.asyncio
async def test_solve_fallback_incomplete(mock_solver, valid_json_content):
    """Test that 'incomplete' status triggers fallback to minimal."""
    # Setup mock: First call incomplete, Second call success
    response_fail = MockResponse(content=None, status="incomplete", incomplete_reason="max_tokens")
    response_success = MockResponse(content=valid_json_content, status="completed")
    
    mock_solver.client.responses.create.side_effect = [response_fail, response_success]
    
    # Execute
    result = await mock_solver.solve("1+1", requested_mode="detailed", max_output_tokens=100)
    
    # Verify
    assert result["final_answer"]["answer_text"] == "2"
    assert result["telemetry"]["openai_calls_count"] == 2
    assert result["telemetry"]["fallback_triggered"] is True
    
    # Verify calls
    assert mock_solver.client.responses.create.call_count == 2
    
    # Check Pass 2 args (minimal)
    call_args_2 = mock_solver.client.responses.create.call_args_list[1][1]
    assert call_args_2["text"]["verbosity"] == "low" # Minimal triggers 'low' verbosity

@pytest.mark.asyncio
async def test_solve_fallback_validation_fail(mock_solver):
    """Test that schema validation failure triggers fallback."""
    # Invalid content (missing required fields)
    invalid_content = json.dumps({"foo": "bar"}) 
    
    # Valid content for second pass
    valid_content = json.dumps({
        "schema_version": "v1.0",
        "problem": {"original_text": "1+1", "normalized_text": "1+1", "detected_tasks": []},
        "classification": {"grade_band": "unknown", "domain": "unknown", "topic": "unknown", "difficulty": "unknown"},
        "refusal": {"is_refusal": False, "reason": "none", "safe_alternative": "none"},
        "assumptions": [],
        "steps": [],
        "final_answer": {"answer_text": "2", "answer_latex": "2", "values": [], "units": ""},
        "visuals": {"should_visualize": False, "decision_reason": "simple", "plots": [], "alternative_visual": {"kind": "none", "description": "none", "data": []}},
        "quality": {"confidence": 0.5, "common_mistakes": []}
    })
    
    mock_solver.client.responses.create.side_effect = [
        MockResponse(content=invalid_content, status="completed"),
        MockResponse(content=valid_content, status="completed")
    ]
    
    result = await mock_solver.solve("1+1", requested_mode="detailed")
    
    assert result["telemetry"]["fallback_triggered"] is True
    
    # Check status checks: 1 fail, 1 success
    checks = result["telemetry"]["status_checks"]
    assert len(checks) == 2
    assert checks[0]["valid"] is False
    assert checks[1]["valid"] is True

@pytest.mark.asyncio
async def test_solve_exhausted_retries(mock_solver):
    """Test that double failure returns managed error object (not empty)"""
    mock_solver.client.responses.create.return_value = MockResponse(content=None, status="incomplete")
    
    result = await mock_solver.solve("1+1", requested_mode="detailed")
    
    assert result["error"] is True
    assert result["error_type"] == "exhausted_retries"
    assert result["telemetry"]["openai_calls_count"] == 2
