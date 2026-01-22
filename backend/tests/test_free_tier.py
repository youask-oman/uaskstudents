import pytest
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.llm_profiles.profiles import get_prompt_profile
from app.services.response_mapper import map_minimal_to_canonical
from app.services.solver_v3 import SolverV3

def test_get_prompt_profile_free():
    profile = get_prompt_profile("free")
    assert profile.tier == "free"
    assert "free/system.txt" in profile.system_relative_path
    assert "free/schema.json" in profile.schema_relative_path
    assert profile.max_output_tokens == 800
    assert profile.max_steps == 5

def test_get_prompt_profile_standard():
    profile = get_prompt_profile("standard")
    assert profile.tier == "standard"
    assert profile.max_output_tokens == 4096

def test_map_minimal_to_canonical():
    minimal = {
        "final_answer": "42",
        "steps": ["Step 1: Calculate", "Step 2: Done"],
        "topic": "Math",
        "confidence_score": 0.99
    }
    canonical = map_minimal_to_canonical(minimal, "What is 6 * 7?")
    
    assert canonical["final_answer"]["answer_text"] == "42"
    assert len(canonical["steps"]) == 2
    assert canonical["steps"][0]["explanation"] == "Step 1: Calculate"
    assert canonical["quality"]["confidence"] == 0.99
    assert canonical["visuals"]["should_visualize"] is False

@pytest.mark.asyncio
async def test_solver_v3_free_tier_integration():
    # Mock file reading to avoid path issues during test
    mock_system_content = "Mock System Prompt"
    mock_schema_content = json.dumps({"name": "Test", "strict": True, "schema": {"type": "object"}})
    
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        # returns file handles
        mock_file = MagicMock()
        mock_file.read.return_value = mock_system_content
        # For json.load, we mock read to return the json string? no json.load takes fp.
        # It calls fp.read().
        # We need to handle multiple open calls.
        
        # Side effect for open: return different mocks or same mock
        mock_open.return_value.__enter__.return_value.read.side_effect = [mock_system_content, mock_schema_content]
        
        # We also need to mock json.load because it might use the file object differently
        with patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"name": "Test"}
            
            solver = SolverV3()
            solver._call_llm_with_schema = AsyncMock(return_value=({"final_answer": "42", "steps": ["S1"]}, {"total": 100}))
            
            # Act
            response = await solver.solve("Problem", user_tier="free", trace=True)
            
            # Debug
            if "error" in response and response.get("error"):
                print(f"DEBUG: Solver returned error: {response['message']}")
                print(f"DEBUG: Validation errors: {response.get('validation_errors')}")

            # Assert
            # Check if response is canonical (mapped)
            assert "problem" in response
            assert response["final_answer"]["answer_text"] == "42"
