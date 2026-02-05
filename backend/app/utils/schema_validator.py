"""
Schema Validation Utilities.

Validates JSON Schema content for OpenAI Structured Outputs compatibility.
Used at save-time in admin to prevent inserting corrupted schemas.
"""

from typing import Any, List, Tuple, Optional

# Valid JSON Schema types per spec + OpenAI strict mode requirements
VALID_JSON_SCHEMA_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}

class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    def __init__(self, message: str, path: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.path = path
        self.details = details or {}


def validate_schema_types(node: Any, path: str = "$") -> List[Tuple[str, str]]:
    """
    Recursively validate that all "type" declarations in a schema are valid.
    
    Returns list of (json_path, error_message) tuples for all violations found.
    """
    issues: List[Tuple[str, str]] = []
    
    if not isinstance(node, dict):
        if isinstance(node, list):
            for i, item in enumerate(node):
                issues.extend(validate_schema_types(item, f"{path}[{i}]"))
        return issues
    
    # Check "type" field
    if "type" in node:
        type_val = node["type"]
        
        # Invalid: Python None stringified as "None"
        if type_val == "None":
            issues.append((f"{path}.type", f'Invalid type: "None" (Python None stringified). Use "null" string instead.'))
        
        # Invalid: JSON null instead of "null" string
        elif type_val is None:
            issues.append((f"{path}.type", 'Invalid type: null (JSON null). Use "null" string instead.'))
        
        # Invalid: Array containing None or "None"
        elif isinstance(type_val, list):
            for i, item in enumerate(type_val):
                if item is None:
                    issues.append((f"{path}.type[{i}]", f'Array type contains null. Use "null" string.'))
                elif item == "None":
                    issues.append((f"{path}.type[{i}]", f'Array type contains "None". Use "null" string.'))
                elif isinstance(item, str) and item not in VALID_JSON_SCHEMA_TYPES:
                    issues.append((f"{path}.type[{i}]", f'Invalid type: "{item}". Valid types: {VALID_JSON_SCHEMA_TYPES}'))
        
        # Invalid: Unknown type string (for non-wrapper schemas)
        elif isinstance(type_val, str):
            # Allow "json_schema" only at root level for wrappers
            if type_val not in VALID_JSON_SCHEMA_TYPES and type_val != "json_schema":
                issues.append((f"{path}.type", f'Invalid type: "{type_val}". Valid types: {VALID_JSON_SCHEMA_TYPES}'))
    
    # Recurse into all nested objects
    for key, value in node.items():
        if key in ("properties", "items", "$defs", "definitions", "anyOf", "oneOf", "allOf"):
            if isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    issues.extend(validate_schema_types(sub_val, f"{path}.{key}.{sub_key}"))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    issues.extend(validate_schema_types(item, f"{path}.{key}[{i}]"))
        elif isinstance(value, dict):
            issues.extend(validate_schema_types(value, f"{path}.{key}"))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                issues.extend(validate_schema_types(item, f"{path}.{key}[{i}]"))
    
    return issues


def validate_openai_schema_wrapper(schema_content: dict) -> List[Tuple[str, str]]:
    """
    Validate a schema for OpenAI Structured Outputs compatibility.
    
    Checks:
    1. Wrapper format: type="json_schema", name non-empty, strict boolean, schema object
    2. Inner schema: no invalid type declarations
    
    Returns list of (path, error_message) for all issues found.
    """
    issues: List[Tuple[str, str]] = []
    
    if not isinstance(schema_content, dict):
        issues.append(("$", "Schema must be a dict/object"))
        return issues
    
    # Check wrapper format
    if "type" in schema_content and schema_content.get("type") == "json_schema":
        # This is a wrapper - validate wrapper structure
        if not schema_content.get("name"):
            issues.append(("$.name", "Wrapper missing required 'name' field"))
        elif not isinstance(schema_content.get("name"), str):
            issues.append(("$.name", "Wrapper 'name' must be a string"))
        
        if "strict" not in schema_content:
            issues.append(("$.strict", "Wrapper missing required 'strict' field"))
        elif not isinstance(schema_content.get("strict"), bool):
            issues.append(("$.strict", "Wrapper 'strict' must be a boolean"))
        
        if "schema" not in schema_content:
            issues.append(("$.schema", "Wrapper missing required 'schema' object"))
        elif not isinstance(schema_content.get("schema"), dict):
            issues.append(("$.schema", "Wrapper 'schema' must be a dict/object"))
        else:
            # Validate inner schema types
            issues.extend(validate_schema_types(schema_content["schema"], "$.schema"))
    else:
        # Not a wrapper - validate as raw schema
        issues.extend(validate_schema_types(schema_content, "$"))
    
    return issues


def assert_valid_schema(schema_content: dict, raise_error: bool = True) -> bool:
    """
    Convenience function to validate schema and optionally raise on failure.
    
    Args:
        schema_content: The schema dict to validate
        raise_error: If True, raise SchemaValidationError on first issue
        
    Returns:
        True if valid, False otherwise (if raise_error=False)
        
    Raises:
        SchemaValidationError: If validation fails and raise_error=True
    """
    issues = validate_openai_schema_wrapper(schema_content)
    
    if issues:
        if raise_error:
            path, message = issues[0]
            raise SchemaValidationError(
                message=message,
                path=path,
                details={"all_issues": issues, "issue_count": len(issues)}
            )
        return False
    
    return True
