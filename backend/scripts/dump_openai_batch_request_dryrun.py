import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.database import engine
from sqlmodel import Session

from app.models import PromptModeEnum
from app.services.prompt_binding_policy import SOLVE_TIER_POLICY, normalize_external_tier
from app.services.prompt_manager import prompt_manager
from app.services.llm.clients import _normalize_openai_schema_wrapper
from app.services.solve.batch_tier_runtime import (
    _build_runtime_questions,
    _coerce_domain_mode,
    _coerce_graph_mode,
    _coerce_mode,
    _replace_prompt_tokens,
)
from app.utils.structured_output_builder import build_openai_structured_output


QUESTION_TEXT = """Solve for x on 0 ≤ x < 2π:
2 sin^2(x) - 3 sin(x) + 1 = 0.

Tasks:
1) Rewrite as a quadratic in sin(x), solve for sin(x), and keep only valid sine values in [-1, 1].
2) Find all solutions x in [0, 2π) in exact form (standard angles).
3) Verify each solution by substitution into the original equation.
4) Draw a plot on x ∈ [0, 2π] with:
   - y = 2 sin^2(x) - 3 sin(x) + 1
   - the x-axis (y=0)
   - marked solution points (roots) on the curve
   - title, axis labels, grid, and a legend"""


def _convert_messages_for_responses(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    input_items: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, list):
            converted: List[Dict[str, Any]] = []
            for part in content:
                part_type = part.get("type")
                if part_type in {"text", "input_text"}:
                    converted.append({"type": "input_text", "text": part.get("text", "")})
                elif part_type in {"image_url", "input_image"}:
                    image_url = part.get("image_url")
                    if isinstance(image_url, dict):
                        image_url = image_url.get("url")
                    converted.append({"type": "input_image", "image_url": image_url})
            content_list = converted
        else:
            content_list = [{"type": "input_text", "text": str(content)}]
        input_items.append({"role": role, "content": content_list})
    return input_items


def main() -> None:
    external_tier = normalize_external_tier("SHORT_STEPS")
    tier_policy = SOLVE_TIER_POLICY[external_tier]
    prompt_tier = tier_policy.prompt_tier

    runtime_request_id = str(uuid.uuid4())
    runtime_attempt_id = str(uuid.uuid4())
    runtime_mode = _coerce_mode("SOLVE")
    runtime_graph = _coerce_graph_mode("ON")
    runtime_domain = _coerce_domain_mode("reals")
    runtime_lang = "English"

    normalized_questions = _build_runtime_questions(
        [
            {
                "question_id": "q1",
                "question_text": QUESTION_TEXT,
                "mode": "SOLVE",
                "graph_mode": "ON",
                "domain_mode": "reals",
            }
        ]
    )
    questions_json_text = json.dumps(normalized_questions, ensure_ascii=False)

    with Session(engine) as session:
        binding_bundle = prompt_manager.get_binding(session, prompt_tier, PromptModeEnum.SOLVE)

    binding = binding_bundle.get("binding") or {}
    max_questions_allowed = int(binding.get("max_questions_allowed") or 0)
    system_prompt = str(binding_bundle["global_system_prompt"] or "")
    developer_prompt_template = str(binding_bundle["developer_prompt"] or "")
    schema_wrapper = binding_bundle["schema"]

    developer_prompt = _replace_prompt_tokens(
        developer_prompt_template,
        {
            "REQUEST_ID": runtime_request_id,
            "ATTEMPT_ID": runtime_attempt_id,
            "TIER": external_tier,
            "MAX_QUESTIONS": str(max_questions_allowed),
            "MODE": runtime_mode,
            "GRAPH_MODE": runtime_graph,
            "DOMAIN_MODE": runtime_domain,
            "PREFERRED_RESPONSE_LANGUAGE": runtime_lang,
            "QUESTIONS_JSON": questions_json_text,
            "ALLOW_AUTO_SPLIT": "false",
            "allow_auto_split": "false",
            "MAX_TASKS_PER_QUESTION": "6",
            "max_tasks_per_question": "6",
        },
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "developer", "content": developer_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request_id": runtime_request_id,
                    "attempt_id": runtime_attempt_id,
                    "tier": external_tier,
                    "questions_count": len(normalized_questions),
                },
                ensure_ascii=False,
            ),
        },
    ]

    model_name = (str((binding.get("features") or {}).get("model") or "")).strip() or "gpt-5-mini"
    max_tokens = int(binding.get("max_output_tokens") or 5000)
    top_p = float(binding.get("top_p") or 1.0)
    reasoning_effort = (str((binding.get("features") or {}).get("reasoning_effort") or "").strip() or "minimal")
    if reasoning_effort not in {"minimal", "low", "medium", "high"}:
        reasoning_effort = "minimal"

    try:
        json_schema_norm = _normalize_openai_schema_wrapper(schema_wrapper)
    except Exception:
        # Some environments still store raw schema bodies in DB.
        # For dry-run request assembly, coerce into canonical wrapper.
        inferred_name = ""
        if isinstance(schema_wrapper, dict):
            inferred_name = str(schema_wrapper.get("name") or "").strip()
            if not inferred_name:
                props = schema_wrapper.get("properties")
                if isinstance(props, dict):
                    schema_name_field = props.get("schema_name")
                    if isinstance(schema_name_field, dict):
                        enum_vals = schema_name_field.get("enum")
                        if isinstance(enum_vals, list) and enum_vals:
                            inferred_name = str(enum_vals[0] or "").strip()
        if not inferred_name:
            inferred_name = str(binding.get("output_schema_id") or "youask_math_openai_v1")
        json_schema_norm = {
            "type": "json_schema",
            "name": inferred_name,
            "strict": True,
            "schema": schema_wrapper if isinstance(schema_wrapper, dict) else {},
        }
    text_format = build_openai_structured_output(
        db_wrapper=json_schema_norm,
        endpoint="responses",
        call_name="SOLVE",
    )

    input_items = _convert_messages_for_responses(messages)

    params: Dict[str, Any] = {
        "model": model_name,
        "input": input_items,
        "max_output_tokens": max_tokens,
        "text": {
            "verbosity": "low",
            "format": text_format,
        },
        "top_p": top_p,
        "reasoning": {"effort": reasoning_effort},
    }

    sanity = {
        "format_type_is_json_schema": text_format.get("type") == "json_schema",
        "format_name": text_format.get("name"),
        "schema_type": (text_format.get("schema") or {}).get("type"),
        "schema_has_properties": isinstance((text_format.get("schema") or {}).get("properties"), dict),
    }

    project_backend_root = Path(__file__).resolve().parents[1]
    out_dir = project_backend_root / "app" / "storage" / "debug" / "openai_dryrun"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{ts}_responses_api_payload_dryrun.txt"

    body = []
    body.append("DRY RUN ONLY: NO REQUEST SENT TO OPENAI")
    body.append("")
    body.append("=== Runtime Context ===")
    body.append(json.dumps(
        {
            "external_tier": external_tier,
            "prompt_tier": prompt_tier.value,
            "request_id": runtime_request_id,
            "attempt_id": runtime_attempt_id,
            "binding_id": binding.get("id"),
            "output_schema_id": binding.get("output_schema_id"),
            "developer_prompt_id": binding.get("developer_prompt_id"),
            "global_system_prompt_id": binding.get("global_system_prompt_id"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    body.append("")
    body.append("=== Sanity Checks ===")
    body.append(json.dumps(sanity, ensure_ascii=False, indent=2))
    body.append("")
    body.append("=== Full Request Payload (responses.create kwargs) ===")
    body.append(json.dumps(params, ensure_ascii=False, indent=2))
    body.append("")
    body.append("=== Full Messages (Pre-Conversion) ===")
    body.append(json.dumps(messages, ensure_ascii=False, indent=2))

    out_path.write_text("\n".join(body), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
