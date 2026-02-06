from __future__ import annotations

"""
schema_cleaner.py

Purpose:
- Provide a conservative "strict compatibility" normalizer for JSON Schemas used with
  OpenAI Structured Outputs / json_schema response formatting.

Design principles (production):
- DO NOT destructively rewrite schema meaning (e.g., do not drop allOf/if/then).
- DO NOT force every property to be required (respect author's schema).
- DO normalize obvious corruption introduced by Python/DB serialization (None/"None"/null).
- DO enforce additionalProperties=false for objects unless explicitly set otherwise.

This function mutates the input dict in-place (consistent with prior behavior).
"""

from typing import Any, Dict, List, Union


_JSON_PRIMITIVE_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}


def _normalize_type_value(t: Any) -> Any:
    """Normalize common corrupt/invalid type values."""
    if t is None:
        return "null"
    if isinstance(t, str):
        if t == "None":
            return "null"
        # allow valid primitive types; otherwise keep as-is (caller may have custom handling)
        return t
    if isinstance(t, list):
        out: List[Any] = []
        for x in t:
            if x is None:
                out.append("null")
            elif isinstance(x, str) and x == "None":
                out.append("null")
            else:
                out.append(x)
        # de-dup while preserving order
        seen = set()
        deduped = []
        for x in out:
            if x not in seen:
                deduped.append(x)
                seen.add(x)
        return deduped
    return t


def enforce_strict(node: Any) -> Any:
    """
    Conservative schema normalizer for OpenAI structured outputs.

    - Removes non-semantic metadata keys that sometimes cause strict validators to reject.
    - Normalizes corrupted type declarations: None/"None" -> "null".
    - Ensures object schemas default to additionalProperties=false unless explicitly set.
    - Recurses through properties/items/$defs/anyOf/oneOf/allOf/if/then/else safely.
    """
    if isinstance(node, list):
        for item in node:
            enforce_strict(item)
        return node

    if not isinstance(node, dict):
        return node

    # Remove common metadata keys (safe to drop)
    for k in ("title", "description", "default", "examples"):
        node.pop(k, None)

    # Normalize "type"
    if "type" in node:
        node["type"] = _normalize_type_value(node["type"])

    # Normalize enum that accidentally contains Python None or "None"
    if "enum" in node and isinstance(node["enum"], list):
        new_enum = []
        for v in node["enum"]:
            if v is None:
                new_enum.append(None)  # keep explicit JSON nulls in enums
            elif isinstance(v, str) and v == "None":
                new_enum.append(None)
            else:
                new_enum.append(v)
        node["enum"] = new_enum

    # If schema looks like an object schema, enforce additionalProperties=false unless set
    looks_like_object = (
        node.get("type") == "object"
        or "properties" in node
        or "required" in node
    )
    if looks_like_object:
        node["type"] = "object"
        if "additionalProperties" not in node:
            node["additionalProperties"] = False

        props = node.get("properties")
        if isinstance(props, dict):
            for _, prop_schema in props.items():
                enforce_strict(prop_schema)

    # Arrays
    if node.get("type") == "array":
        if "items" in node:
            enforce_strict(node["items"])

    # Definitions
    if "$defs" in node and isinstance(node["$defs"], dict):
        for _, def_schema in node["$defs"].items():
            enforce_strict(def_schema)

    # Combinators and conditionals: do NOT delete them; just recurse.
    for comb_key in ("anyOf", "oneOf", "allOf"):
        if comb_key in node and isinstance(node[comb_key], list):
            for sub in node[comb_key]:
                enforce_strict(sub)

    for cond_key in ("if", "then", "else"):
        if cond_key in node and isinstance(node[cond_key], dict):
            enforce_strict(node[cond_key])

    # Also recurse into nested schema-bearing keys commonly used
    for k in ("not", "contains", "propertyNames", "additionalItems"):
        if k in node and isinstance(node[k], dict):
            enforce_strict(node[k])

    return node
