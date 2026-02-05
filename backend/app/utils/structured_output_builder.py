"""
Structured Output Builder

Single source of truth for building OpenAI structured output request parameters.
Used by SOLVE, VERIFY, PLOT_TRIGGER, and PLOT_SPEC to ensure consistent schema handling.

This module ensures:
- No double-wrapping of schemas
- Correct format for Chat Completions (response_format) vs Responses (text.format)
- Detailed logging for debugging
"""
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Literal
from datetime import datetime

logger = logging.getLogger(__name__)

# ================================
# SHARED SCHEMA UTILITIES
# ================================

EndpointType = Literal["chat_completions", "responses"]
CallName = Literal["SOLVE", "VERIFY", "PLOT_TRIGGER", "PLOT_SPEC"]


def compute_schema_hash(schema: Dict[str, Any]) -> str:
    """Compute SHA256 hash of schema for comparison/logging."""
    return hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()[:16]


def unwrap_db_schema(db_wrapper: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the core schema object from various DB wrapper formats.
    
    Handles these formats:
    1. Full wrapper: {"type": "json_schema", "name": "...", "schema": {...}}
    2. Simple wrapper: {"name": "...", "schema": {...}}
    3. Raw schema: {"type": "object", "properties": {...}}
    
    Returns: {"name": <str>, "strict": <bool>, "schema": <dict>}
    """
    if not isinstance(db_wrapper, dict):
        raise ValueError(f"db_wrapper must be dict, got {type(db_wrapper)}")
    
    # Case 1: Full DB wrapper with type: json_schema
    if db_wrapper.get("type") == "json_schema":
        inner = db_wrapper.get("schema", {})
        name = db_wrapper.get("name", "unnamed_schema")
        strict = db_wrapper.get("strict", True)
        
        # Nested check: inner might also be a wrapper (shouldn't happen but be safe)
        if isinstance(inner, dict) and inner.get("type") == "json_schema":
            # Double-wrapped! Unwrap again
            logger.warning("Detected double-wrapped schema, unwrapping inner layer")
            inner = inner.get("schema", inner)
            name = inner.get("name", name)
        
        return {"name": name, "strict": strict, "schema": inner}
    
    # Case 2: Simple wrapper with name + schema keys
    if "schema" in db_wrapper and "name" in db_wrapper:
        return {
            "name": db_wrapper["name"],
            "strict": db_wrapper.get("strict", True),
            "schema": db_wrapper["schema"]
        }
    
    # Case 3: Raw schema (no wrapper) - assume it's the schema itself
    if db_wrapper.get("type") in ("object", "array", "string"):
        return {
            "name": "raw_schema",
            "strict": True,
            "schema": db_wrapper
        }
    
    # Fallback: treat the whole thing as the schema
    logger.warning(f"Unknown schema format, treating as raw schema. Keys: {list(db_wrapper.keys())}")
    return {
        "name": "unknown_schema",
        "strict": True,
        "schema": db_wrapper
    }


def build_openai_structured_output(
    db_wrapper: Dict[str, Any],
    endpoint: EndpointType,
    call_name: Optional[CallName] = None,
) -> Dict[str, Any]:
    """
    Build the correct structured output parameter for OpenAI API.
    
    This is THE SINGLE SOURCE OF TRUTH for constructing structured output requests.
    
    Args:
        db_wrapper: Schema from DB, may be in various wrapper formats
        endpoint: "chat_completions" or "responses"
        call_name: Optional call identifier for logging (SOLVE, VERIFY, etc.)
    
    Returns:
        For chat_completions: {"type": "json_schema", "json_schema": {"name": ..., "strict": ..., "schema": ...}}
        For responses: {"type": "json_schema", "name": ..., "strict": ..., "schema": ...}
    """
    # Step 1: Normalize/unwrap the DB schema
    normalized = unwrap_db_schema(db_wrapper)
    name = normalized["name"]
    strict = normalized["strict"]
    inner_schema = normalized["schema"]
    
    # Step 2: Validate inner schema has required fields
    if not isinstance(inner_schema, dict):
        raise ValueError(f"inner_schema must be dict, got {type(inner_schema)}")
    
    # Check for corruption that would cause type: "None" error
    if inner_schema.get("type") in (None, "None", "null"):
        logger.error(f"CORRUPTION DETECTED: inner_schema.type = {inner_schema.get('type')!r}")
        # Attempt to fix if properties exist
        if "properties" in inner_schema:
            logger.warning("Auto-fixing: setting type to 'object' since properties exist")
            inner_schema["type"] = "object"
        else:
            raise ValueError(f"Invalid inner schema type: {inner_schema.get('type')!r}")
    
    # Step 3: Build output format based on endpoint
    if endpoint == "chat_completions":
        # Chat Completions API uses response_format
        result = {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": strict,
                "schema": inner_schema
            }
        }
    elif endpoint == "responses":
        # Responses API uses text.format
        result = {
            "type": "json_schema",
            "name": name,
            "strict": strict,
            "schema": inner_schema
        }
    else:
        raise ValueError(f"Unknown endpoint: {endpoint}")
    
    # Logging
    schema_hash = compute_schema_hash(inner_schema)
    logger.info(
        f"build_openai_structured_output: call={call_name} endpoint={endpoint} "
        f"name={name} strict={strict} schema_hash={schema_hash}"
    )
    
    return result


# ================================
# REQUEST TRACE LOGGING
# ================================

_trace_records = []


def log_openai_request_trace(
    call_name: CallName,
    user_id: Optional[int],
    tier: Optional[str],
    binding_id: Optional[str],
    model: str,
    endpoint: EndpointType,
    max_output_tokens: int,
    schema_wrapper: Dict[str, Any],
    structured_output_param: Dict[str, Any],
    messages_info: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a complete trace of an OpenAI request for debugging.
    
    Returns the trace record for potential file output.
    """
    # Build trace record
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "call_name": call_name,
        "user_id": user_id,
        "tier": tier,
        "binding_id": binding_id,
        "model": model,
        "endpoint": endpoint,
        "max_output_tokens": max_output_tokens,
        "request_id": request_id,
        
        # Schema info
        "schema_wrapper_name": schema_wrapper.get("name") if isinstance(schema_wrapper, dict) else None,
        "schema_wrapper_strict": schema_wrapper.get("strict") if isinstance(schema_wrapper, dict) else None,
        "schema_hash": compute_schema_hash(schema_wrapper.get("schema", {})) if isinstance(schema_wrapper, dict) else None,
        
        # The actual structured output param being sent
        "structured_output_shape": _describe_shape(structured_output_param),
        "structured_output_keys": list(structured_output_param.keys()) if isinstance(structured_output_param, dict) else None,
        
        # Messages info (summarized, not full content)
        "messages_info": messages_info,
    }
    
    _trace_records.append(record)
    
    # Log to console
    logger.info(
        f"[TRACE] {call_name} user={user_id} tier={tier} binding={binding_id} "
        f"model={model} endpoint={endpoint} schema={record.get('schema_wrapper_name')}"
    )
    
    return record


def _describe_shape(obj: Any, max_depth: int = 3, current_depth: int = 0) -> str:
    """Describe the shape of an object for logging."""
    if current_depth >= max_depth:
        return "..."
    
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return str(obj).lower()
    if isinstance(obj, (int, float)):
        return type(obj).__name__
    if isinstance(obj, str):
        return f'str[{len(obj)}]'
    if isinstance(obj, list):
        if not obj:
            return "[]"
        return f"[{_describe_shape(obj[0], max_depth, current_depth+1)}, ...]"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        inner = ", ".join(f'"{k}": {_describe_shape(v, max_depth, current_depth+1)}' 
                          for k, v in list(obj.items())[:5])
        if len(obj) > 5:
            inner += ", ..."
        return "{" + inner + "}"
    return type(obj).__name__


def get_all_traces() -> list:
    """Get all recorded traces."""
    return list(_trace_records)


def clear_traces():
    """Clear all recorded traces."""
    _trace_records.clear()


def save_traces_to_file(filepath: str, include_full_output: bool = False):
    """Save all traces to a JSON or text file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        if filepath.endswith('.json'):
            json.dump(_trace_records, f, indent=2, default=str)
        else:
            f.write("=" * 80 + "\n")
            f.write("OPENAI REQUEST TRACE REPORT\n")
            f.write(f"Generated: {datetime.utcnow().isoformat()}\n")
            f.write(f"Total Traces: {len(_trace_records)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, record in enumerate(_trace_records, 1):
                f.write(f"--- TRACE {i}: {record.get('call_name', 'UNKNOWN')} ---\n")
                for key, value in record.items():
                    if key == 'structured_output_shape':
                        f.write(f"  {key}:\n    {value}\n")
                    else:
                        f.write(f"  {key}: {value}\n")
                f.write("\n")
