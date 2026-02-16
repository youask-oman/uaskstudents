import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator
from sqlmodel import Session, select

from app.models import (
    PromptBinding,
    PromptModeEnum,
    PromptTierEnum,
)
from app.services.llm.manager import LLMManager
from app.services.llm.clients import LLMProviderError
from app.services.prompt_manager import prompt_manager
from app.services.prompt_binding_policy import (
    ALLOWED_PROMPT_IDS,
    ALLOWED_SCHEMA_IDS,
    SOLVE_TIER_POLICY,
    SYSTEM_PROMPT_ID,
    normalize_external_tier,
)


logger = logging.getLogger(__name__)


class BatchSolveError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str = "batch_solve_failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details or {}


DIFFICULTY_ENUM = {"very_easy", "easy", "medium", "hard", "very_hard", "research"}


def _coerce_graph_mode(value: Optional[str]) -> str:
    raw = (value or "").strip().upper()
    if raw in {"OFF", "ON", "AUTO"}:
        return raw
    return "AUTO"


def _coerce_domain_mode(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    if raw in {"reals", "complex"}:
        return raw
    return "reals"


def _coerce_mode(value: Optional[str]) -> str:
    raw = (value or "").strip().upper()
    if raw:
        return raw
    return "SOLVE"


def _replace_prompt_tokens(template: str, replacements: Dict[str, str]) -> str:
    out = template
    for key, val in replacements.items():
        out = out.replace("{{" + key + "}}", val)
        out = out.replace("{" + key + "}", val)
    return out


def _extract_schema_body(schema_wrapper: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema_wrapper, dict):
        raise BatchSolveError(
            "Schema wrapper is not an object.",
            status_code=500,
            code="schema_wrapper_invalid",
        )
    schema = schema_wrapper.get("schema")
    if not isinstance(schema, dict):
        raise BatchSolveError(
            "Schema wrapper missing object field 'schema'.",
            status_code=500,
            code="schema_wrapper_invalid",
        )
    return schema


def _validate_binding_strict(
    session: Session,
    tier: PromptTierEnum,
) -> PromptBinding:
    active_bindings = session.exec(
        select(PromptBinding)
        .where(PromptBinding.mode == PromptModeEnum.SOLVE)
        .where(PromptBinding.tier == tier)
        .where(PromptBinding.is_active == True)
        .order_by(PromptBinding.updated_at.desc())
    ).all()
    if len(active_bindings) != 1:
        raise BatchSolveError(
            f"Expected exactly 1 active SOLVE binding for tier={tier.value}, found {len(active_bindings)}.",
            status_code=500,
            code="prompt_binding_invalid",
        )
    binding = active_bindings[0]
    if binding.global_system_prompt_id != SYSTEM_PROMPT_ID:
        raise BatchSolveError(
            f"Unexpected system prompt binding for tier={tier.value}.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"expected": SYSTEM_PROMPT_ID, "actual": binding.global_system_prompt_id, "tier": tier.value},
        )
    if binding.developer_prompt_id not in ALLOWED_PROMPT_IDS:
        raise BatchSolveError(
            f"Unexpected developer prompt binding for tier={tier.value}.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"actual": binding.developer_prompt_id, "tier": tier.value},
        )
    if binding.output_schema_id not in ALLOWED_SCHEMA_IDS:
        raise BatchSolveError(
            f"Unexpected output schema binding for tier={tier.value}.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"actual": binding.output_schema_id, "tier": tier.value},
        )
    return binding


def _build_runtime_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for q in questions:
        qid = str(q.get("question_id") or "").strip()
        qtext = str(q.get("question_text") or "").strip()
        if not qid or not qtext:
            raise BatchSolveError(
                "Each question requires non-empty question_id and question_text.",
                status_code=400,
                code="invalid_question_item",
            )
        out.append(
            {
                "question_id": qid,
                "question_text": qtext,
                "mode": _coerce_mode(q.get("mode")),
                "graph_mode": _coerce_graph_mode(q.get("graph_mode")),
                "domain_mode": _coerce_domain_mode(q.get("domain_mode")),
            }
        )
    return out


def _scan_for_xy_arrays(node: Any, path: str = "$") -> Optional[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            next_path = f"{path}.{k}"
            if k in {"x", "y"} and isinstance(v, list):
                return next_path
            found = _scan_for_xy_arrays(v, next_path)
            if found:
                return found
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            found = _scan_for_xy_arrays(item, f"{path}[{idx}]")
            if found:
                return found
    return None


def _normalize_question_text(value: Any) -> str:
    text = str(value or "")
    # Accept model whitespace/line-wrap normalization without failing the run.
    return " ".join(text.split()).strip()


def _post_assertions(
    payload: Dict[str, Any],
    *,
    schema_body: Dict[str, Any],
    questions: List[Dict[str, Any]],
    tier: str,
) -> None:
    items = payload.get("items")
    if not isinstance(items, list):
        raise BatchSolveError("Output missing items[].", status_code=502, code="post_assert_failed")
    if len(items) != len(questions):
        raise BatchSolveError(
            f"items length mismatch: expected {len(questions)}, got {len(items)}.",
            status_code=502,
            code="post_assert_failed",
        )

    enum_tasks: set[str] = set()
    try:
        enum_tasks = set(
            (((schema_body.get("$defs") or {}).get("problem") or {}).get("properties") or {})
            .get("detected_tasks", {})
            .get("items", {})
            .get("enum", [])
        )
    except Exception:
        enum_tasks = set()

    for idx, (item, qin) in enumerate(zip(items, questions), start=1):
        if not isinstance(item, dict):
            raise BatchSolveError("Each item must be an object.", status_code=502, code="post_assert_failed")
        if str(item.get("question_id")) != qin["question_id"]:
            raise BatchSolveError(
                f"question_id mismatch at index={idx}.",
                status_code=502,
                code="post_assert_failed",
            )
        if int(item.get("question_index") or -1) != idx:
            raise BatchSolveError(
                f"question_index mismatch at index={idx}.",
                status_code=502,
                code="post_assert_failed",
            )

        clarification = item.get("clarification") if isinstance(item.get("clarification"), dict) else {}
        if bool(clarification.get("needs_clarification")):
            raise BatchSolveError(
                f"clarification must be off for item {idx}.",
                status_code=502,
                code="clarification_not_allowed",
            )
        if list(clarification.get("questions") or []):
            raise BatchSolveError(
                f"clarification.questions must be empty for item {idx}.",
                status_code=502,
                code="clarification_not_allowed",
            )

        problem = item.get("problem") if isinstance(item.get("problem"), dict) else {}
        expected_text = qin["question_text"]
        got_text = str(problem.get("original_text") or "")
        if _normalize_question_text(got_text) != _normalize_question_text(expected_text):
            # Do not fail the entire request for benign model reformatting.
            # Keep downstream UI stable by forcing canonical original_text from input.
            logger.warning(
                "batch_original_text_mismatch_normalized item=%s expected=%r got=%r",
                idx,
                expected_text,
                got_text,
            )
            problem["original_text"] = expected_text
            item["problem"] = problem
        detected_tasks = problem.get("detected_tasks") if isinstance(problem.get("detected_tasks"), list) else []
        if not detected_tasks:
            raise BatchSolveError(
                f"problem.detected_tasks must be non-empty for item {idx}.",
                status_code=502,
                code="post_assert_failed",
            )
        if enum_tasks and any(str(t) not in enum_tasks for t in detected_tasks):
            raise BatchSolveError(
                f"problem.detected_tasks contains out-of-enum value for item {idx}.",
                status_code=502,
                code="post_assert_failed",
            )

        classification = item.get("classification") if isinstance(item.get("classification"), dict) else {}
        if str(classification.get("difficulty") or "") not in DIFFICULTY_ENUM:
            raise BatchSolveError(
                f"classification.difficulty invalid for item {idx}.",
                status_code=502,
                code="post_assert_failed",
            )

        plot = item.get("plot") if isinstance(item.get("plot"), dict) else {}
        if not str(plot.get("decision_reason") or "").strip():
            # Keep runtime tolerant: decision_reason is informational and may be omitted.
            # We normalize instead of failing the entire batch.
            plot["decision_reason"] = "No plot rationale provided."
            item["plot"] = plot

        refusal = item.get("refusal") if isinstance(item.get("refusal"), dict) else {}
        final_answer = item.get("final_answer")
        if bool(refusal.get("is_refusal")) and final_answer is not None:
            # Runtime normalization guard: refusal payloads must not carry final answers.
            item["final_answer"] = None
            if isinstance(item.get("steps"), list):
                item["steps"] = []
            plot_obj = item.get("plot") if isinstance(item.get("plot"), dict) else {}
            plot_obj["should_visualize"] = False
            plot_obj["recipe"] = None
            item["plot"] = plot_obj
            logger.warning("batch_refusal_normalized item=%s reason=final_answer_non_null", idx)
        elif bool(refusal.get("is_refusal")):
            if isinstance(item.get("steps"), list):
                item["steps"] = []
            plot_obj = item.get("plot") if isinstance(item.get("plot"), dict) else {}
            plot_obj["should_visualize"] = False
            plot_obj["recipe"] = None
            item["plot"] = plot_obj
        if not bool(refusal.get("is_refusal")) and final_answer is None:
            raise BatchSolveError(
                f"final_answer must be non-null when refusal=false for item {idx}.",
                status_code=502,
                code="post_assert_failed",
            )

        quality = item.get("quality") if isinstance(item.get("quality"), dict) else {}
        conf = quality.get("confidence")
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
            raise BatchSolveError(
                f"quality.confidence out of range for item {idx}.",
                status_code=502,
                code="post_assert_failed",
            )
        mistakes = quality.get("common_mistakes") if isinstance(quality.get("common_mistakes"), list) else []
        if tier == "FINAL" and len(mistakes) != 0:
            raise BatchSolveError(
                f"FINAL tier requires quality.common_mistakes = []. item={idx}",
                status_code=502,
                code="post_assert_failed",
            )

        bad_xy_path = _scan_for_xy_arrays(item.get("plot"))
        if bad_xy_path:
            raise BatchSolveError(
                f"x/y arrays are not allowed (recipe-only plotting). Found at {bad_xy_path}.",
                status_code=502,
                code="post_assert_failed",
            )


async def execute_batch_solve(
    *,
    session: Session,
    tier: str,
    request_id: Optional[str],
    attempt_id: Optional[str],
    mode: Optional[str],
    graph_mode: Optional[str],
    domain_mode: Optional[str],
    preferred_response_language: Optional[str],
    questions_json: List[Dict[str, Any]],
    model: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    started = time.perf_counter()
    external_tier = normalize_external_tier(tier)
    tier_policy = SOLVE_TIER_POLICY[external_tier]
    prompt_tier = tier_policy.prompt_tier
    normalized_questions = _build_runtime_questions(questions_json)

    if len(normalized_questions) < 1:
        raise BatchSolveError(
            "At least one question is required.",
            status_code=400,
            code="empty_batch",
        )

    _validate_binding_strict(session, prompt_tier)
    binding_bundle = prompt_manager.get_binding(session, prompt_tier, PromptModeEnum.SOLVE)
    binding = binding_bundle.get("binding") or {}

    def _bget(name: str, default: Any = None) -> Any:
        if isinstance(binding, dict):
            return binding.get(name, default)
        return getattr(binding, name, default)

    binding_id = str(_bget("id") or "")
    max_questions_allowed = int(_bget("max_questions_allowed") or 0)
    if max_questions_allowed < 1:
        raise BatchSolveError(
            "Binding is missing required max_questions_allowed.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"tier": prompt_tier.value, "binding_id": binding_id},
        )
    if len(normalized_questions) > max_questions_allowed:
        raise BatchSolveError(
            f"Batch exceeds tier limit for {external_tier}: max={max_questions_allowed}, got={len(normalized_questions)}.",
            status_code=400,
            code="batch_limit_exceeded",
            details={"max_questions": max_questions_allowed, "count": len(normalized_questions)},
        )
    system_prompt = str(binding_bundle["global_system_prompt"] or "")
    developer_prompt_template = str(binding_bundle["developer_prompt"] or "")
    schema_wrapper = binding_bundle["schema"]
    schema_body = _extract_schema_body(schema_wrapper)

    runtime_request_id = (request_id or str(uuid.uuid4())).strip()
    runtime_attempt_id = (attempt_id or str(uuid.uuid4())).strip()
    runtime_mode = _coerce_mode(mode)
    runtime_graph = _coerce_graph_mode(graph_mode)
    runtime_domain = _coerce_domain_mode(domain_mode)
    runtime_lang = (preferred_response_language or "English").strip() or "English"
    questions_json_text = json.dumps(normalized_questions, ensure_ascii=False)

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

    llm_manager = LLMManager()
    client = llm_manager.get_client("openai")
    binding_features = _bget("features") if isinstance(_bget("features"), dict) else {}
    model_name = (model or str(binding_features.get("model") or "")).strip()
    if not model_name:
        raise BatchSolveError(
            "Binding is missing required model setting.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"tier": prompt_tier.value, "binding_id": binding_id},
        )
    bound_max_output_tokens = int(_bget("max_output_tokens") or 0)
    if bound_max_output_tokens < 1:
        # Keep runtime resilient for legacy bindings missing this field.
        bound_max_output_tokens = 2200
    max_tokens = int(max_output_tokens) if max_output_tokens is not None else bound_max_output_tokens
    bound_temperature = float(_bget("temperature") or 0.0)
    bound_top_p = float(_bget("top_p") or 1.0)
    bound_timeout_ms = int(_bget("timeout_ms") or 60000)

    try:
        response = await client.generate(
            messages=messages,
            system_prompt=None,
            prompt=None,
            json_schema=schema_wrapper,
            max_tokens=max_tokens,
            temperature=bound_temperature,
            top_p=bound_top_p,
            stream=False,
            request_id=runtime_request_id,
            timeout_ms=bound_timeout_ms,
            model=model_name,
            verbosity="low",
            reasoning_effort=(str(binding_features.get("reasoning_effort") or "").strip() or None),
        )
    except LLMProviderError as exc:
        raise BatchSolveError(
            "OpenAI call failed during batch solve.",
            status_code=502,
            code="openai_request_failed",
            details={"message": str(exc)},
        ) from exc

    raw = (response.content or "").strip()
    if not raw:
        raise BatchSolveError(
            "Empty OpenAI response content.",
            status_code=502,
            code="empty_openai_response",
        )

    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise BatchSolveError(
            "OpenAI returned invalid JSON payload.",
            status_code=502,
            code="invalid_openai_json",
            details={"error": str(exc)},
        ) from exc

    validator = Draft202012Validator(schema_body)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
        raise BatchSolveError(
            "Schema validation failed for OpenAI payload.",
            status_code=502,
            code="schema_validation_failed",
            details={
                "errors": [
                    {"path": "$" + "".join([f"[{repr(p)}]" for p in err.path]), "message": err.message}
                    for err in errors[:30]
                ]
            },
        )

    _post_assertions(
        payload,
        schema_body=schema_body,
        questions=normalized_questions,
        tier=external_tier,
    )

    telemetry = {
        "request_id": runtime_request_id,
        "attempt_id": runtime_attempt_id,
        "tier": external_tier,
        "model": response.model,
        "provider": response.provider,
        "input_tokens": int((response.usage or {}).get("input") or 0),
        "output_tokens": int((response.usage or {}).get("output") or 0),
        "total_tokens": int((response.usage or {}).get("total") or 0),
        "latency_ms_openai": int(response.latency_ms or 0),
        "latency_ms_total": int((time.perf_counter() - started) * 1000),
        "schema_name": str(schema_wrapper.get("name") or tier_policy.schema_id),
        "model_bound": model_name,
        "temperature_bound": bound_temperature,
        "top_p_bound": bound_top_p,
        "timeout_ms_bound": bound_timeout_ms,
        "max_questions_allowed_bound": max_questions_allowed,
        "prompt_binding_id": binding_id,
        "global_system_prompt_id": _bget("global_system_prompt_id"),
        "developer_prompt_id": _bget("developer_prompt_id"),
        "output_schema_id": _bget("output_schema_id"),
        "openai_calls_count": 1,
        "repair_attempted": False,
        "schema_valid": True,
    }
    return payload, telemetry
