"""
JSON Schema $ref dereferencing utility for OpenAI Structured Outputs compatibility.

OpenAI Structured Outputs does not support JSON Schema $ref/$defs references.
This module provides utilities to inline all $ref references, producing a 
self-contained schema compatible with OpenAI's strict mode.
"""

import copy
import json
from typing import Dict, Any, Set


class CyclicReferenceError(Exception):
    """Raised when cyclic $ref references are detected."""
    pass


def deref_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dereference all $ref in a JSON Schema by inlining the referenced definitions.
    
    Args:
        schema: A JSON Schema dict, possibly containing $defs and $ref
        
    Returns:
        A new schema dict with all $refs inlined and $defs removed
        
    Raises:
        CyclicReferenceError: If cyclic references are detected
        
    Example:
        >>> schema = {
        ...     "$defs": {"Foo": {"type": "string"}},
        ...     "properties": {"bar": {"$ref": "#/$defs/Foo"}}
        ... }
        >>> deref_json_schema(schema)
        {'properties': {'bar': {'type': 'string'}}}
    """
    # Make a deep copy to avoid mutating the original
    schema = copy.deepcopy(schema)
    
    # Extract $defs for resolution
    defs = schema.pop("$defs", {})
    
    # Track resolution stack for cycle detection
    resolution_stack: Set[str] = set()
    
    def resolve_ref(ref: str) -> Dict[str, Any]:
        """Resolve a $ref string to its definition."""
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"Unsupported $ref format: {ref}. Only '#/$defs/<Name>' is supported.")
        
        def_name = ref[len("#/$defs/"):]
        
        if def_name in resolution_stack:
            raise CyclicReferenceError(
                f"Cyclic reference detected: {def_name} -> {' -> '.join(resolution_stack)}"
            )
        
        if def_name not in defs:
            raise KeyError(f"Referenced definition not found: {def_name}")
        
        # Add to stack before resolving (for cycle detection)
        resolution_stack.add(def_name)
        
        # Recursively resolve the definition
        resolved = deref_node(copy.deepcopy(defs[def_name]))
        
        # Remove from stack after resolution
        resolution_stack.discard(def_name)
        
        return resolved
    
    def deref_node(node: Any) -> Any:
        """Recursively dereference a schema node."""
        if not isinstance(node, dict):
            if isinstance(node, list):
                return [deref_node(item) for item in node]
            return node
        
        # Handle $ref
        if "$ref" in node:
            ref = node.pop("$ref")
            resolved = resolve_ref(ref)
            
            # Merge any sibling keys (additional constraints alongside $ref)
            # The resolved schema takes precedence, but sibling keys are preserved
            remaining_keys = dict(node)  # Other keys besides $ref
            
            if remaining_keys:
                # Merge: resolved schema + sibling constraints
                merged = {**resolved, **remaining_keys}
                # Recursively deref the merged result
                return deref_node(merged)
            
            return resolved
        
        # Recursively process all keys
        result = {}
        for key, value in node.items():
            if key == "$defs":
                # Skip $defs at any level (shouldn't exist after top-level pop, but be safe)
                continue
            result[key] = deref_node(value)
        
        return result
    
    # Process the entire schema
    return deref_node(schema)


def validate_no_refs(schema: Dict[str, Any], raise_error: bool = True) -> bool:
    """
    Validate that a schema contains no $ref or $defs.
    
    Args:
        schema: The schema to validate
        raise_error: If True, raise AssertionError on violation
        
    Returns:
        True if schema is clean, False otherwise (if raise_error=False)
    """
    schema_str = json.dumps(schema)
    
    has_ref = '"$ref"' in schema_str
    has_defs = '"$defs"' in schema_str
    
    if has_ref or has_defs:
        if raise_error:
            violations = []
            if has_ref:
                violations.append("$ref")
            if has_defs:
                violations.append("$defs")
            raise AssertionError(
                f"Schema validation failed: contains {', '.join(violations)}. "
                f"OpenAI Structured Outputs requires fully inlined schemas."
            )
        return False
    
    return True


def get_deref_schema_for_openai(schema_getter) -> Dict[str, Any]:
    """
    Convenience wrapper that gets a schema, derefs it, and validates.
    
    Args:
        schema_getter: A callable that returns the raw schema (e.g., get_json_schema_for_openai_v3)
        
    Returns:
        A dereferenced, validated schema ready for OpenAI
    """
    raw_schema = schema_getter()
    deref_schema = deref_json_schema(raw_schema)
    validate_no_refs(deref_schema, raise_error=True)
    return deref_schema


# Development helper
if __name__ == "__main__":
    # Quick test with V3 schema
    try:
        from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3
        
        print("Testing schema dereferencing...")
        raw = get_json_schema_for_openai_v3()
        
        has_defs = "$defs" in raw
        ref_marker = '"$ref"'
        has_ref_raw = ref_marker in json.dumps(raw)
        print(f"Raw schema has $defs: {has_defs}")
        print(f"Raw schema has $ref: {has_ref_raw}")
        
        deref = deref_json_schema(raw)
        has_defs_deref = "$defs" in deref
        has_ref_deref = ref_marker in json.dumps(deref)
        print(f"\nDereferenced schema has $defs: {has_defs_deref}")
        print(f"Dereferenced schema has $ref: {has_ref_deref}")
        
        validate_no_refs(deref)
        print("\n✅ Schema dereferencing successful!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
