from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


BACKEND_ONLY_TOP_LEVEL_KEYS = {
    "_raw_llm_output",
    "debug",
    "runtime_meta",
    "timing_ms",
}

# Nullable/noisy fields we do not want to force in first-pass LLM outputs.
NULLABLE_NOISE_KEYS = {
    "alternative_visual",
    "rendered",
    "render_hint",
    "subtitle",
    "z_label",
}


def unwrap_schema(schema_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(schema_config, dict):
        return {}
    if isinstance(schema_config.get("schema"), dict):
        return schema_config["schema"]
    json_schema_block = schema_config.get("json_schema")
    if isinstance(json_schema_block, dict):
        if isinstance(json_schema_block.get("schema"), dict):
            return json_schema_block["schema"]
        return json_schema_block
    return schema_config


def optimize_schema_for_model(schema_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    schema = deepcopy(unwrap_schema(schema_config))
    if not isinstance(schema, dict) or not schema:
        return {}
    # OpenAI Responses strict format rejects top-level allOf in current runtime.
    if "allOf" in schema and isinstance(schema.get("allOf"), list):
        schema.pop("allOf", None)
    _remove_required_keys(schema, BACKEND_ONLY_TOP_LEVEL_KEYS)
    _remove_nullable_noise_required(schema)
    _ensure_object_nodes_disallow_additional(schema)
    if "additionalProperties" not in schema:
        schema["additionalProperties"] = False
    return schema


def optimize_schema_for_validation(schema_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validation should use the same contract as model output to avoid false repair loops.
    """
    return optimize_schema_for_model(schema_config)


def _remove_required_keys(node: Any, keys: set[str]) -> None:
    if not isinstance(node, dict):
        return
    required = node.get("required")
    if isinstance(required, list):
        node["required"] = [k for k in required if isinstance(k, str) and k not in keys]
    for child in _iter_schema_children(node):
        _remove_required_keys(child, keys)


def _remove_nullable_noise_required(node: Any) -> None:
    if not isinstance(node, dict):
        return

    props = node.get("properties")
    required = node.get("required")
    if isinstance(props, dict) and isinstance(required, list):
        keep: List[str] = []
        for key in required:
            prop = props.get(key) if isinstance(key, str) else None
            if (
                isinstance(key, str)
                and key in NULLABLE_NOISE_KEYS
                and _is_nullable_property(prop)
            ):
                continue
            keep.append(key)
        node["required"] = keep

    for child in _iter_schema_children(node):
        _remove_nullable_noise_required(child)


def _apply_response_kind_split_contract(schema: Dict[str, Any]) -> None:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return
    response_kind = props.get("response_kind")
    if not isinstance(response_kind, dict):
        return

    enum_vals = response_kind.get("enum")
    if not isinstance(enum_vals, list):
        return
    values = {str(v) for v in enum_vals}
    if not {"solution", "clarification", "refusal"}.issubset(values):
        return

    existing_allof = schema.get("allOf")
    allof: List[Dict[str, Any]] = []
    if isinstance(existing_allof, list):
        allof.extend([x for x in existing_allof if isinstance(x, dict)])

    # Lightweight branch contracts instead of duplicating entire schema.
    branches = []
    base_required = set(schema.get("required") or [])

    branches.append(
        {
            "type": "object",
            "properties": {"response_kind": {"const": "solution"}},
            "required": _required_with(
                base_required,
                must={"response_kind", "problem", "classification", "steps", "final_answer"},
                remove={"clarification", "refusal"},
            ),
        }
    )
    branches.append(
        {
            "type": "object",
            "properties": {"response_kind": {"const": "clarification"}},
            "required": _required_with(
                base_required,
                must={"response_kind", "problem", "clarification"},
                remove={"final_answer", "steps"},
            ),
        }
    )
    branches.append(
        {
            "type": "object",
            "properties": {"response_kind": {"const": "refusal"}},
            "required": _required_with(
                base_required,
                must={"response_kind", "problem", "refusal"},
                remove={"final_answer", "steps", "clarification"},
            ),
        }
    )

    allof.append({"oneOf": branches})
    schema["allOf"] = allof


def _required_with(base_required: set[str], must: set[str], remove: set[str]) -> List[str]:
    out = {k for k in base_required if k not in remove and isinstance(k, str)}
    out |= {k for k in must if isinstance(k, str)}
    return sorted(out)


def _is_nullable_property(prop: Any) -> bool:
    if not isinstance(prop, dict):
        return False
    t = prop.get("type")
    if isinstance(t, list) and "null" in t:
        return True
    return False


def _iter_schema_children(node: Dict[str, Any]) -> List[Any]:
    children: List[Any] = []
    for key in ("properties", "$defs", "definitions", "patternProperties"):
        block = node.get(key)
        if isinstance(block, dict):
            children.extend([v for v in block.values() if isinstance(v, dict)])
    for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
        block = node.get(key)
        if isinstance(block, list):
            children.extend([v for v in block if isinstance(v, dict)])
    items = node.get("items")
    if isinstance(items, dict):
        children.append(items)
    return children


def _ensure_object_nodes_disallow_additional(node: Any) -> None:
    if not isinstance(node, dict):
        return
    if "properties" in node and isinstance(node.get("properties"), dict):
        node["type"] = "object"
        node["additionalProperties"] = False
    elif node.get("type") == "object":
        node["additionalProperties"] = False
    for child in _iter_schema_children(node):
        _ensure_object_nodes_disallow_additional(child)
