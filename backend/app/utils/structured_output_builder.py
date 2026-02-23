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
from typing import Any, Dict, Optional, Literal, List
from datetime import datetime

logger = logging.getLogger(__name__)

# ================================
# SHARED SCHEMA UTILITIES
# ================================

EndpointType = Literal["chat_completions", "responses"]
CallName = Literal["SOLVE", "VERIFY", "PLOT_TRIGGER", "PLOT_SPEC"]
_DISALLOWED_OPENAI_SCHEMA_KEYS = {"const", "oneOf", "allOf", "not", "if", "then", "else"}


def _unwrap_nested_schema_wrapper(schema_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guard against accidental double-wrapping:
      schema = {"type":"json_schema","name":"...","strict":true,"schema":{...}}
    which is invalid for text.format.schema.
    """
    if not isinstance(schema_obj, dict):
        return schema_obj

    # Canonical nested wrapper accidentally placed inside schema.
    if schema_obj.get("type") == "json_schema" and isinstance(schema_obj.get("schema"), dict):
        logger.warning("Detected nested json_schema wrapper inside schema; unwrapping inner schema.")
        return schema_obj["schema"]

    # Chat variant accidentally nested.
    if schema_obj.get("type") == "json_schema" and isinstance(schema_obj.get("json_schema"), dict):
        inner = schema_obj["json_schema"]
        if isinstance(inner.get("schema"), dict):
            logger.warning("Detected nested chat-style json_schema wrapper inside schema; unwrapping inner schema.")
            return inner["schema"]
    return schema_obj


def _assert_real_json_schema_root(schema_obj: Dict[str, Any], *, schema_name: str) -> None:
    """
    Validate that text.format.schema is a real JSON Schema object root,
    not a wrapper/config object.
    """
    if not isinstance(schema_obj, dict):
        raise ValueError("text.format.schema must be a JSON object.")

    # Wrapper keys at top-level usually indicate miswiring.
    if schema_obj.get("type") == "json_schema" or (
        "schema" in schema_obj and ("name" in schema_obj or "strict" in schema_obj)
    ):
        raise ValueError(
            "Invalid schema wiring: wrapper keys found inside text.format.schema. "
            "Use wrapper keys in text.format and put only real JSON Schema in text.format.schema."
        )

    if schema_obj.get("type") != "object":
        raise ValueError(
            f"Invalid JSON Schema root for '{schema_name}': text.format.schema.type must be 'object'."
        )
    if not isinstance(schema_obj.get("properties"), dict):
        raise ValueError(
            f"Invalid JSON Schema root for '{schema_name}': text.format.schema.properties must be an object."
        )


def _enforce_openai_required_properties(node: Any) -> Any:
    """
    OpenAI strict schema compatibility:
    For every object schema with `properties`, `required` must include all property keys.
    """
    if isinstance(node, list):
        for item in node:
            _enforce_openai_required_properties(item)
        return node

    if not isinstance(node, dict):
        return node

    props = node.get("properties")
    if isinstance(props, dict):
        node["required"] = list(props.keys())
        for prop_schema in props.values():
            _enforce_openai_required_properties(prop_schema)
    elif node.get("type") == "object" and "required" in node:
        # OpenAI strict requires required keys to correspond to object properties.
        node.pop("required", None)

    items = node.get("items")
    if isinstance(items, dict):
        _enforce_openai_required_properties(items)
    elif isinstance(items, list):
        for item in items:
            _enforce_openai_required_properties(item)

    defs = node.get("$defs")
    if isinstance(defs, dict):
        for sub in defs.values():
            _enforce_openai_required_properties(sub)

    for key in ("anyOf", "oneOf", "allOf"):
        value = node.get(key)
        if isinstance(value, list):
            for sub in value:
                _enforce_openai_required_properties(sub)

    for key in ("if", "then", "else", "not", "contains", "propertyNames", "additionalItems"):
        value = node.get(key)
        if isinstance(value, dict):
            _enforce_openai_required_properties(value)

    return node


def _walk_schema_for_disallowed_keys(node: Any, *, path: str = "$") -> List[str]:
    violations: List[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            if key in _DISALLOWED_OPENAI_SCHEMA_KEYS:
                violations.append(child_path)
            violations.extend(_walk_schema_for_disallowed_keys(value, path=child_path))
        return violations
    if isinstance(node, list):
        for idx, item in enumerate(node):
            violations.extend(_walk_schema_for_disallowed_keys(item, path=f"{path}[{idx}]"))
    return violations


def _walk_anyof_duplicate_object_first_key(node: Any, *, path: str = "$") -> List[str]:
    violations: List[str] = []
    if isinstance(node, dict):
        any_of = node.get("anyOf")
        if isinstance(any_of, list):
            seen: Dict[str, int] = {}
            for idx, branch in enumerate(any_of):
                if not isinstance(branch, dict):
                    continue
                props = branch.get("properties")
                if isinstance(props, dict) and props:
                    first_key = next(iter(props.keys()))
                    if first_key in seen:
                        violations.append(
                            f"{path}.anyOf has duplicate object branches with first property key '{first_key}' "
                            f"(indexes {seen[first_key]} and {idx})"
                        )
                    else:
                        seen[first_key] = idx
        for key, value in node.items():
            violations.extend(_walk_anyof_duplicate_object_first_key(value, path=f"{path}.{key}"))
        return violations
    if isinstance(node, list):
        for idx, item in enumerate(node):
            violations.extend(_walk_anyof_duplicate_object_first_key(item, path=f"{path}[{idx}]"))
    return violations


def _validate_openai_strict_preflight(schema_obj: Dict[str, Any], *, schema_name: str) -> None:
    disallowed = _walk_schema_for_disallowed_keys(schema_obj, path="$")
    if disallowed:
        sample = ", ".join(disallowed[:8])
        raise ValueError(
            f"Schema preflight failed for '{schema_name}': disallowed keys found ({sample})."
        )

    anyof_violations = _walk_anyof_duplicate_object_first_key(schema_obj, path="$")
    if anyof_violations:
        sample = "; ".join(anyof_violations[:4])
        raise ValueError(
            f"Schema preflight failed for '{schema_name}': invalid anyOf object branch overlap ({sample})."
        )


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
    inner_schema = _unwrap_nested_schema_wrapper(normalized["schema"])
    
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
    if strict:
        inner_schema = _enforce_openai_required_properties(inner_schema)

    # Ensure enforce_strict did not strip a necessary root type for object responses
    if isinstance(inner_schema, dict) and inner_schema.get('type') in (None, 'None'):
        raise ValueError(f"Invalid inner schema after enforce_strict: type={inner_schema.get('type')!r}")
    if isinstance(inner_schema, dict) and 'type' not in inner_schema and any(k in inner_schema for k in ('properties','required','additionalProperties')):
        inner_schema['type'] = 'object'

    # Final guardrails for Responses/Chat structured outputs.
    _assert_real_json_schema_root(inner_schema, schema_name=name)
    _validate_openai_strict_preflight(inner_schema, schema_name=name)
    
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
    logger.info(
        "Structured output sanity: type=%s name=%s schema.type=%s schema.has_properties=%s",
        result.get("type"),
        (result.get("name") if endpoint == "responses" else (result.get("json_schema") or {}).get("name")),
        (result.get("schema") if endpoint == "responses" else (result.get("json_schema") or {}).get("schema", {})).get("type"),
        isinstance(
            (result.get("schema") if endpoint == "responses" else (result.get("json_schema") or {}).get("schema", {})).get("properties"),
            dict,
        ),
    )
    disallowed_keys_after = _walk_schema_for_disallowed_keys(inner_schema, path="$")
    logger.info(
        "Structured output strict preflight: has_disallowed_keys=%s has_const=%s",
        bool(disallowed_keys_after),
        any(".const" in p for p in disallowed_keys_after),
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
