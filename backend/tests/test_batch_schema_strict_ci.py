import json
from pathlib import Path
from typing import Any, Dict, List


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "app" / "schemas" / "openai_schemas"
SCHEMA_FILES = [
    "schema__solve_batch_final_v2.schema_openai_strict.json",
    "schema__solve_batch_free_v2.schema_openai_strict.json",
    "schema__solve_batch_standard_v2.schema_openai_strict.json",
    "schema__solve_batch_research_v2.schema_openai_strict.json",
]


def _walk(node: Any, path: str = "$") -> List[tuple[str, Dict[str, Any]]]:
    out: List[tuple[str, Dict[str, Any]]] = []
    if isinstance(node, dict):
        out.append((path, node))
        for k, v in node.items():
            out.extend(_walk(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(_walk(v, f"{path}[{i}]"))
    return out


def _load_schema(file_name: str) -> Dict[str, Any]:
    raw = json.loads((SCHEMA_DIR / file_name).read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{file_name}: file must parse to object"
    assert isinstance(raw.get("schema"), dict), f"{file_name}: wrapper must contain object 'schema'"
    return raw["schema"]


def test_batch_schemas_openai_strict_contract() -> None:
    errors: List[str] = []

    for file_name in SCHEMA_FILES:
        schema = _load_schema(file_name)

        if schema.get("type") != "object":
            errors.append(f"{file_name}: root schema.type must be object")
        if schema.get("additionalProperties") is not False:
            errors.append(f"{file_name}: root additionalProperties must be false")
        if "anyOf" in schema:
            errors.append(f"{file_name}: root anyOf is not allowed")

        for path, node in _walk(schema):
            if not isinstance(node, dict):
                continue

            if "uniqueItems" in node:
                errors.append(
                    f"{file_name}: {path} uses uniqueItems, which is incompatible with OpenAI strict structured outputs"
                )

            has_props = isinstance(node.get("properties"), dict)
            if node.get("type") == "object" or has_props:
                if node.get("additionalProperties") is not False:
                    errors.append(f"{file_name}: {path} object must set additionalProperties=false")
                if has_props:
                    props = list((node.get("properties") or {}).keys())
                    req = node.get("required")
                    if not isinstance(req, list):
                        errors.append(f"{file_name}: {path} must include required[]")
                    elif set(req) != set(props):
                        errors.append(
                            f"{file_name}: {path} required[] must include exactly all properties keys"
                        )

    assert not errors, "Strict schema contract violations:\n" + "\n".join(f"- {e}" for e in errors)
