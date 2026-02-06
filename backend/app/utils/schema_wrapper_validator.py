"""
Schema Wrapper Validator

Fail-fast assertions for OpenAI Structured Output schema wrappers.
Prevents silent fallback to raw_schema and ensures DB wrapper integrity.

Usage:
    validate_schema_wrapper(wrapper, binding_id=binding_id, schema_id=schema_id)
    
Raises:
    SchemaWrapperCorruptError if validation fails
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SchemaWrapperCorruptError(Exception):
    """Raised when a schema wrapper is invalid or corrupt."""
    
    def __init__(
        self,
        message: str,
        wrapper_keys: Optional[list] = None,
        binding_id: Optional[str] = None,
        schema_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.wrapper_keys = wrapper_keys
        self.binding_id = binding_id
        self.schema_id = schema_id
    
    def __str__(self):
        details = [super().__str__()]
        if self.wrapper_keys:
            details.append(f"wrapper_keys={self.wrapper_keys}")
        if self.binding_id:
            details.append(f"binding_id={self.binding_id}")
        if self.schema_id:
            details.append(f"schema_id={self.schema_id}")
        return " | ".join(details)


def validate_schema_wrapper(
    wrapper: Any,
    *,
    binding_id: Optional[str] = None,
    schema_id: Optional[str] = None,
    context: str = "OpenAI call",
) -> Dict[str, Any]:
    """
    Validate a schema wrapper before calling OpenAI.
    
    Required wrapper structure:
    {
        "type": "json_schema",
        "name": <non-empty string>,
        "strict": <boolean>,
        "schema": <dict with "type" key>
    }
    
    Args:
        wrapper: The schema wrapper to validate
        binding_id: Optional binding ID for error context
        schema_id: Optional schema ID for error context
        context: Description of where validation is happening
    
    Returns:
        The validated wrapper (same object if valid)
    
    Raises:
        SchemaWrapperCorruptError: If validation fails
    """
    wrapper_keys = list(wrapper.keys()) if isinstance(wrapper, dict) else None
    
    # Check 1: Must be dict
    if not isinstance(wrapper, dict):
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: wrapper is not a dict, got {type(wrapper).__name__}"
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper must be a dict, got {type(wrapper).__name__}",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 2: Must have required keys
    required_keys = {"type", "name", "strict", "schema"}
    missing_keys = required_keys - set(wrapper.keys())
    if missing_keys:
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: missing required keys {missing_keys}. "
            f"Has keys: {wrapper_keys}"
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper missing required keys: {missing_keys}",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 3: type must be "json_schema"
    if wrapper.get("type") != "json_schema":
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: type must be 'json_schema', "
            f"got {wrapper.get('type')!r}"
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper type must be 'json_schema', got {wrapper.get('type')!r}",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 4: name must be non-empty string
    name = wrapper.get("name")
    if not isinstance(name, str) or not name.strip():
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: name must be non-empty string, "
            f"got {name!r}"
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper name must be non-empty string, got {name!r}",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 5: name must NOT be "raw_schema" (indicates upstream bug)
    if name == "raw_schema":
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: name='raw_schema' indicates "
            f"upstream wrapper corruption. This should never happen with DB schemas."
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper name='raw_schema' indicates upstream corruption",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 6: strict must be boolean
    strict = wrapper.get("strict")
    if not isinstance(strict, bool):
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: strict must be boolean, "
            f"got {type(strict).__name__}"
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper strict must be boolean, got {type(strict).__name__}",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 7: schema must be dict
    inner_schema = wrapper.get("schema")
    if not isinstance(inner_schema, dict) or not inner_schema:
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: schema must be non-empty dict, "
            f"got {type(inner_schema).__name__}"
        )
        raise SchemaWrapperCorruptError(
            f"Schema wrapper schema must be non-empty dict",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    # Check 8: inner schema must have type or be a valid combinator
    has_type = "type" in inner_schema
    has_combinator = any(k in inner_schema for k in ("$ref", "oneOf", "anyOf", "allOf"))
    has_properties = "properties" in inner_schema
    
    if not has_type and not has_combinator:
        # If it has properties but no type, that's a soft corruption we can fix
        if has_properties:
            logger.warning(
                f"[SCHEMA_WRAPPER_SOFT_FIX] {context}: inner schema has 'properties' "
                f"but no 'type'. Will assume 'object'."
            )
        else:
            logger.error(
                f"[SCHEMA_WRAPPER_CORRUPT] {context}: inner schema must have 'type' "
                f"or a combinator keyword. Keys: {list(inner_schema.keys())[:10]}"
            )
            raise SchemaWrapperCorruptError(
                f"Inner schema missing 'type' and combinator keywords",
                wrapper_keys=wrapper_keys,
                binding_id=binding_id,
                schema_id=schema_id,
            )
    
    # Check 9: inner schema type must not be None or "None"
    if has_type and inner_schema.get("type") in (None, "None"):
        logger.error(
            f"[SCHEMA_WRAPPER_CORRUPT] {context}: inner schema type is {inner_schema.get('type')!r}"
        )
        raise SchemaWrapperCorruptError(
            f"Inner schema type is {inner_schema.get('type')!r}",
            wrapper_keys=wrapper_keys,
            binding_id=binding_id,
            schema_id=schema_id,
        )
    
    logger.debug(
        f"[SCHEMA_WRAPPER_VALID] {context}: name={name}, strict={strict}, "
        f"inner_type={inner_schema.get('type')}"
    )
    
    return wrapper


def create_wrapped_schema(
    inner_schema: Dict[str, Any],
    name: str,
    strict: bool = True,
) -> Dict[str, Any]:
    """
    Create a properly wrapped schema from an inner schema.
    
    This is the CORRECT pattern for re-wrapping after deref/clean operations:
    
        wrapper_out = create_wrapped_schema(
            inner_schema=cleaned_inner,
            name=original_wrapper["name"],
            strict=original_wrapper["strict"],
        )
    
    Args:
        inner_schema: The cleaned/dereferenced inner schema
        name: The schema name from the original wrapper
        strict: The strict flag from the original wrapper
    
    Returns:
        A properly structured OpenAI schema wrapper
    """
    if not isinstance(inner_schema, dict) or not inner_schema:
        raise ValueError("inner_schema must be a non-empty dict")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    
    return {
        "type": "json_schema",
        "name": name.strip(),
        "strict": bool(strict),
        "schema": inner_schema,
    }
