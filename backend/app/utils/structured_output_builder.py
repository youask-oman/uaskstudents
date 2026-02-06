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
    Normalize a schema record from DB into a single internal shape:

      {"type": "json_schema", "name": <str>, "strict": <bool>, "schema": <dict>}

    Accepted inputs:
    - DB wrapper (preferred):
        {"type":"json_schema","name":"...","strict":true,"schema":{...}}
    - OpenAI chat wrapper (should not be stored, but tolerated):
        {"type":"json_schema","json_schema":{"name":"...","strict":true,"schema":{...}}}
    - Simple wrapper (legacy):
        {"name":"...","strict":true,"schema":{...}}
    - Raw JSON Schema (draft):
        {"$schema": "...", "type":"object", ...}  OR a schema-like dict containing schema keywords.

    Rejected:
    - Half-wrapper: {"schema": {...}} (ambiguous and caused production bugs)
    """
    if not isinstance(db_wrapper, dict) or not db_wrapper:
        raise ValueError(f"Schema wrapper must be a non-empty dict, got {type(db_wrapper)}")

    keys = set(db_wrapper.keys())

    # Reject the known-bad half-wrapper.
    if keys == {"schema"}:
        logger.error("Invalid schema wrapper: only 'schema' key present (half-wrapper).")
        raise ValueError("Invalid schema wrapper: missing required keys (type/name/strict).")

    def _require_str(v: Any, field: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"Invalid schema wrapper: '{field}' must be a non-empty string.")
        return v.strip()

    def _require_bool(v: Any, field: str) -> bool:
        if isinstance(v, bool):
            return v
        # Allow 0/1 or "true"/"false" if DB is messy, but normalize.
        if isinstance(v, (int, float)) and v in (0, 1):
            return bool(v)
        if isinstance(v, str) and v.lower() in ("true", "false"):
            return v.lower() == "true"
        raise ValueError(f"Invalid schema wrapper: '{field}' must be boolean.")

    def _require_dict(v: Any, field: str) -> Dict[str, Any]:
        if not isinstance(v, dict) or not v:
            raise ValueError(f"Invalid schema wrapper: '{field}' must be a non-empty object.")
        return v

    # Case 1: Full wrapper (DB canonical)
    if db_wrapper.get("type") == "json_schema" and "schema" in db_wrapper:
        name = _require_str(db_wrapper.get("name"), "name")
        strict = _require_bool(db_wrapper.get("strict", True), "strict")
        schema = _require_dict(db_wrapper.get("schema"), "schema")
        return {"type": "json_schema", "name": name, "strict": strict, "schema": schema}

    # Case 2: OpenAI chat wrapper (nested json_schema)
    if db_wrapper.get("type") == "json_schema" and "json_schema" in db_wrapper and isinstance(db_wrapper["json_schema"], dict):
        inner = db_wrapper["json_schema"]
        name = _require_str(inner.get("name"), "json_schema.name")
        strict = _require_bool(inner.get("strict", True), "json_schema.strict")
        schema = _require_dict(inner.get("schema"), "json_schema.schema")
        return {"type": "json_schema", "name": name, "strict": strict, "schema": schema}

    # Case 3: Simple wrapper (legacy)
    if "name" in db_wrapper and "schema" in db_wrapper:
        name = _require_str(db_wrapper.get("name"), "name")
        strict = _require_bool(db_wrapper.get("strict", True), "strict")
        schema = _require_dict(db_wrapper.get("schema"), "schema")
        return {"type": "json_schema", "name": name, "strict": strict, "schema": schema}

    # Case 4: Raw JSON Schema (draft / schema-like)
    schema_like_keys = {"$schema", "$id", "$ref", "type", "properties", "required", "anyOf", "oneOf", "allOf", "enum", "const", "items"}
    if keys.intersection(schema_like_keys):
        # Treat as raw schema. Caller must provide a name elsewhere or accept "raw_schema".
        return {"type": "json_schema", "name": "raw_schema", "strict": True, "schema": db_wrapper}

    logger.error(f"Unrecognized schema wrapper format. Keys={sorted(keys)}")
    raise ValueError(f"Invalid schema wrapper format. Keys={sorted(keys)}")


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
    
    # Step 2: Validate inner schema is a dict and looks like JSON Schema
    if not isinstance(inner_schema, dict) or not inner_schema:
        raise ValueError(f"inner_schema must be a non-empty dict, got {type(inner_schema)}")

    # Reject explicit corruption values (this is the actual "type: None" bug class)
    if "type" in inner_schema and inner_schema.get("type") in (None, "None"):
        logger.error(f"CORRUPTION DETECTED: inner_schema.type={inner_schema.get('type')!r}")
        raise ValueError(f"Invalid inner schema: type is {inner_schema.get('type')!r}")

    # If type is missing, only auto-set when the schema clearly represents an object response.
    if "type" not in inner_schema:
        if any(k in inner_schema for k in ("properties", "required", "additionalProperties")):
            inner_schema["type"] = "object"
        # Otherwise allow combinators ($ref/oneOf/anyOf/allOf) to define shape.
        elif any(k in inner_schema for k in ("$ref", "oneOf", "anyOf", "allOf")):
            pass
        else:
            raise ValueError("Invalid inner schema: missing 'type' and no schema-defining keywords present.")

    # Step 2.5: Clean schema for Strict Mode compliance (remove allOf, defaults, etc.)
    # We always deep-clean to ensure 'allOf' is removed, as it causes 400 violations.
    from app.utils.schema_cleaner import enforce_strict
    # We operate on a deep copy to avoid mutating the cached schema in memory
    import copy
    inner_schema = enforce_strict(copy.deepcopy(inner_schema))

    # Ensure enforce_strict did not strip a necessary root type for object responses
    if isinstance(inner_schema, dict) and inner_schema.get('type') in (None, 'None'):
        raise ValueError(f"Invalid inner schema after enforce_strict: type={inner_schema.get('type')!r}")
    if isinstance(inner_schema, dict) and 'type' not in inner_schema and any(k in inner_schema for k in ('properties','required','additionalProperties')):
        inner_schema['type'] = 'object'
    
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
