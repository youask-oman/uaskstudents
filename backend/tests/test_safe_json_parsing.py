import pytest
import json
from app.utils.safe_json import safe_parse_json

# Sample schemas
REQUIRED_KEYS = ["schema_version", "problem", "steps", "final_answer"]

def test_single_json_object():
    """Test parsing a single valid JSON object."""
    data = {
        "schema_version": "v1",
        "problem": {"text": "2+2"},
        "steps": [],
        "final_answer": {"value": "4"}
    }
    raw = json.dumps(data)
    parsed = safe_parse_json(raw, prefer_last=True, required_keys=REQUIRED_KEYS)
    assert parsed == data

def test_multiple_json_objects_pick_last():
    """Test parsing multiple JSON objects, picking the last one with required keys."""
    obj1 = {"meta": "info", "value": 1} # No required keys
    obj2 = {
        "schema_version": "v1",
        "problem": {"text": "3+3"},
        "steps": [],
        "final_answer": {"value": "6"}
    }
    
    # Concatenated strings
    raw = json.dumps(obj1) + "\n" + json.dumps(obj2)
    parsed = safe_parse_json(raw, prefer_last=True, required_keys=REQUIRED_KEYS)
    assert parsed == obj2

def test_sse_contamination():
    """Test parsing JSON embedded in SSE data: lines."""
    obj = {
        "schema_version": "v1",
        "problem": {"text": "5+5"},
        "steps": [],
        "final_answer": {"value": "10"}
    }
    
    # Simulate SSE stream artifacts
    raw = f"data: {json.dumps(obj)}\n\n"
    parsed = safe_parse_json(raw, prefer_last=True, required_keys=REQUIRED_KEYS)
    assert parsed == obj

def test_truncated_json_raises_error():
    """Test that truncated JSON raises ValueError which can be caught for repair."""
    obj = {
        "schema_version": "v1",
        "problem": {"text": "10+10"},
        "steps": [],
        "final_answer": {"value": "20"}
    }
    raw = json.dumps(obj)
    truncated = raw[:-5] # Cut off closing braces
    
    with pytest.raises(ValueError) as excinfo:
        safe_parse_json(truncated, prefer_last=True, required_keys=REQUIRED_KEYS)
    
    assert "Truncated JSON" in str(excinfo.value) or "No valid JSON" in str(excinfo.value)

def test_ignore_partial_objects():
    """Test that it ignores partial/invalid objects and finds the valid one if present."""
    valid = {
        "schema_version": "v1",
        "problem": {"text": "test"},
        "steps": [],
        "final_answer": {"value": "test"}
    }
    
    # Garbage + Valid
    raw = '{"broken": ' + json.dumps(valid)
    parsed = safe_parse_json(raw, prefer_last=True, required_keys=REQUIRED_KEYS)
    assert parsed == valid

def test_repair_hook_called():
    """Test that repair_fn is called when parsing fails."""
    
    def mock_repair(bad_json):
        return json.dumps({
            "schema_version": "v1",
            "problem": {"text": "repaired"},
            "steps": [],
            "final_answer": {"value": "repaired"}
        })
        
    raw = '{"broken": "json"'
    parsed = safe_parse_json(raw, repair_fn=mock_repair, prefer_last=True, required_keys=REQUIRED_KEYS)
    assert parsed["problem"]["text"] == "repaired"
