import json
import os
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator
from sqlmodel import Session

from app.models import PromptTierEnum, PromptModeEnum
from app.services.message_builder import build_user_message
from app.prompts.db_loader import load_prompt_bundle
from app.services.llm import get_llm_manager, LLMProviderError


class ModeExecutionError(Exception):
    def __init__(self, payload: Dict[str, Any], status_code: int = 422):
        super().__init__(payload.get("details") if isinstance(payload, dict) else str(payload))
        self.payload = payload
        self.status_code = status_code


def _json_path(path_items) -> str:
    path = "$"
    for item in path_items:
        if isinstance(item, int):
            path += f"[{item}]"
        else:
            path += f".{item}"
    return path


def _validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> List[Dict[str, str]]:
    validator = Draft202012Validator(schema)
    issues: List[Dict[str, str]] = []
    for err in validator.iter_errors(data):
        issues.append(
            {"type": "schema_error", "message": err.message, "path": _json_path(err.absolute_path)}
        )
        if len(issues) >= 20:
            break
    return issues


def _repair_prompt(schema_json: Dict[str, Any], raw_text: str, error_list_json: List[Dict[str, str]]) -> str:
    return (
        "You are a strict JSON repair engine.\n"
        "Your task: output ONLY valid JSON that matches the provided JSON Schema exactly.\n"
        "Do not include markdown, commentary, or extra keys.\n\n"
        f"JSON Schema:\n{json.dumps(schema_json, ensure_ascii=True)}\n\n"
        f"Invalid output:\n{raw_text}\n\n"
        f"Validation/parsing errors:\n{json.dumps(error_list_json, ensure_ascii=True)}\n\n"
        "Return ONLY the corrected JSON."
    )


class ModeExecutionService:
    def __init__(self):
        self._llm_manager = get_llm_manager()

    async def run(
        self,
        session: Session,
        *,
        tier: PromptTierEnum,
        mode: PromptModeEnum,
        question_payload: Dict[str, Any],
        context_payload: Dict[str, Any],
        runtime_hints: Dict[str, Any],
        request_id: str,
    ) -> Dict[str, Any]:
        binding_payload = load_prompt_bundle(tier=tier.value, mode=mode.value, session=session)
        schema = binding_payload["schema"]
        system_prompt = binding_payload["system_prompt"]
        developer_prompt = binding_payload["developer_prompt"]
        user_message = build_user_message(question_payload, context_payload, runtime_hints)

        providers = self._llm_manager.get_provider_chain()
        last_error = None
        last_status_code = 422
        for provider in providers:
            try:
                client = self._llm_manager.get_client(provider)
                response = await client.generate(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "developer", "content": developer_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    system_prompt=system_prompt,
                    prompt=None,
                    json_schema=schema if provider == "openai" else None,
                    max_tokens=1200,
                    temperature=None,
                    stream=False,
                    request_id=request_id,
                    verbosity="low",
                )

                raw = response.content or ""
                parsed = None
                error_list: List[Dict[str, str]] = []
                try:
                    parsed = json.loads(raw)
                except Exception as exc:
                    error_list.append({"type": "parse_error", "message": str(exc), "path": "$"})

                if parsed is not None:
                    error_list.extend(_validate_against_schema(parsed, schema))

                if not error_list:
                    return {"ok": True, "provider": provider, "schema_valid": True, "output": parsed}

                if os.environ.get("LLM_REPAIR_ENABLED", "true").lower() in {"1", "true", "yes"}:
                    repair_prompt = _repair_prompt(schema, raw, error_list)
                    repair_resp = await client.generate(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "developer", "content": developer_prompt},
                            {"role": "user", "content": repair_prompt},
                        ],
                        system_prompt=system_prompt,
                        prompt=None,
                        json_schema=schema if provider == "openai" else None,
                        max_tokens=1200,
                        temperature=None,
                        stream=False,
                        request_id=request_id,
                        verbosity="low",
                    )
                    repaired_raw = repair_resp.content or ""
                    repaired_data = json.loads(repaired_raw)
                    repaired_errors = _validate_against_schema(repaired_data, schema)
                    if not repaired_errors:
                        return {
                            "ok": True,
                            "provider": provider,
                            "schema_valid": True,
                            "repaired": True,
                            "output": repaired_data,
                        }

                last_error = {"code": "LLM_SCHEMA_INVALID", "details": error_list}
            except (LLMProviderError, json.JSONDecodeError, ValueError) as exc:
                error_message = str(exc).strip() or repr(exc)
                last_error = {
                    "code": "LLM_PROVIDER_ERROR",
                    "provider": getattr(exc, "provider", provider),
                    "details": error_message,
                }
                if isinstance(exc, LLMProviderError) and exc.details:
                    last_error.update(exc.details)
                    if "base_url" not in last_error and isinstance(exc.details, dict):
                        base_url = exc.details.get("base_url")
                        if base_url:
                            last_error["base_url"] = base_url
                last_status_code = 503 if isinstance(exc, LLMProviderError) and exc.is_transient else 422
                self._llm_manager.note_error(provider, exc)
                continue

        raise ModeExecutionError(last_error or {"code": "UNKNOWN_ERROR"}, status_code=last_status_code)


mode_execution_service = ModeExecutionService()
