from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from sqlmodel import Session, select

from app.models import JsonSchemaEntry, PromptBinding, PromptModeEnum, PromptRoleEnum, PromptTemplateEntry, PromptTierEnum, User
from app.services.solver_v3 import get_solver_v3
from app.utils.schema_deref import deref_json_schema, validate_no_refs
from app.utils.structured_output_builder import build_openai_structured_output

logger = logging.getLogger(__name__)


class SolveTextPipelineError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


@dataclass
class SolveModeConfig:
    cap: int
    schema_names: List[str]
    binding_tier: str
    solver_mode: str
    batch_supported: bool


MODE_CONFIG: Dict[str, SolveModeConfig] = {
    "free_minimal": SolveModeConfig(
        cap=10,
        schema_names=["solve_free_minimal_v1_openai", "solve_free_minimal_v1"],
        binding_tier="FREE",
        solver_mode="minimal",
        batch_supported=True,
    ),
    "final_only": SolveModeConfig(
        cap=10,
        schema_names=["solve_final_answer_v1_openai", "solve_final_answer_v1"],
        binding_tier="SHORT",
        solver_mode="minimal",
        batch_supported=True,
    ),
    "standard_detailed": SolveModeConfig(
        cap=3,
        schema_names=["solve_standard_detailed_v1"],
        binding_tier="STANDARD",
        solver_mode="detailed",
        batch_supported=True,
    ),
    "research_detailed": SolveModeConfig(
        cap=1,
        schema_names=["solve_research_detailed_v1"],
        binding_tier="RESEARCH",
        solver_mode="detailed",
        batch_supported=False,
    ),
}


def _resolve_user_default_language(session: Session, user_id: int) -> str:
    user = session.get(User, user_id)
    if not user:
        raise SolveTextPipelineError("USER_NOT_FOUND", "User not found", http_status=404)

    if hasattr(user, "default_language"):
        raw_lang = getattr(user, "default_language", None)
    else:
        # Compatibility path for deployments where the profile model has not yet migrated.
        raw_lang = getattr(user, "preferred_language", None)
    lang = str(raw_lang or "").strip().lower()
    return lang or "en"


def _parse_tier_enum(raw_tier: str) -> PromptTierEnum:
    normalized = str(raw_tier or "").strip().upper()
    if normalized in {"RESEARCH", "ENTERPRISE"}:
        return PromptTierEnum.RESEARCH
    if normalized in {"STANDARD", "STUDENT_STANDARD", "PRO", "PREMIUM", "FAMILY", "FAMILY_STANDARD"}:
        return PromptTierEnum.STANDARD
    if normalized in {"SHORT", "FINAL_ONLY"}:
        return PromptTierEnum.SHORT
    return PromptTierEnum.FREE


def _find_schema_entry(session: Session, schema_names: List[str]) -> JsonSchemaEntry:
    for schema_name in schema_names:
        for candidate_schema_id in (schema_name, f"{schema_name}.schema.json"):
            row = session.exec(
                select(JsonSchemaEntry)
                .where(JsonSchemaEntry.schema_id == candidate_schema_id)
                .where(JsonSchemaEntry.is_active == True)
                .order_by(JsonSchemaEntry.version.desc(), JsonSchemaEntry.id.desc())
            ).first()
            if row:
                return row

    rows = session.exec(
        select(JsonSchemaEntry)
        .where(JsonSchemaEntry.is_active == True)
        .order_by(JsonSchemaEntry.updated_at.desc(), JsonSchemaEntry.id.desc())
    ).all()
    for row in rows:
        content = row.content if isinstance(row.content, dict) else {}
        name = str(content.get("name") or "").strip()
        if name and name in schema_names:
            return row

    raise SolveTextPipelineError(
        "SCHEMA_NOT_FOUND",
        "Configured schema not found in DB",
        http_status=500,
        details={"schema_names": schema_names},
    )


def _find_prompt_binding(
    session: Session,
    schema_id: str,
    preferred_tier: PromptTierEnum,
) -> PromptBinding:
    binding = session.exec(
        select(PromptBinding)
        .where(PromptBinding.output_schema_id == schema_id)
        .where(PromptBinding.mode == PromptModeEnum.SOLVE)
        .where(PromptBinding.tier == preferred_tier)
        .where(PromptBinding.is_active == True)
        .order_by(PromptBinding.updated_at.desc(), PromptBinding.id.desc())
    ).first()
    if binding:
        return binding

    fallback = session.exec(
        select(PromptBinding)
        .where(PromptBinding.output_schema_id == schema_id)
        .where(PromptBinding.mode == PromptModeEnum.SOLVE)
        .where(PromptBinding.is_active == True)
        .order_by(PromptBinding.updated_at.desc(), PromptBinding.id.desc())
    ).first()
    if fallback:
        return fallback

    raise SolveTextPipelineError(
        "PROMPT_BINDING_NOT_FOUND",
        "No active prompt binding found for schema",
        http_status=500,
        details={"schema_id": schema_id, "preferred_tier": preferred_tier.value},
    )


def _find_system_prompt(session: Session, prompt_id: str) -> PromptTemplateEntry:
    row = session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == prompt_id)
        .where(PromptTemplateEntry.is_active == True)
        .where(PromptTemplateEntry.role.in_([PromptRoleEnum.SYSTEM, PromptRoleEnum.DEVELOPER]))
        .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
    ).first()
    if row:
        return row
    raise SolveTextPipelineError(
        "SYSTEM_PROMPT_NOT_FOUND",
        "System prompt template is missing",
        http_status=500,
        details={"prompt_id": prompt_id},
    )


def _find_developer_prompt(session: Session, binding: PromptBinding) -> PromptTemplateEntry:
    tier = binding.tier
    row = session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == binding.developer_prompt_id)
        .where(PromptTemplateEntry.is_active == True)
        .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
        .where(PromptTemplateEntry.mode == PromptModeEnum.SOLVE)
        .where(PromptTemplateEntry.tier == tier)
        .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
    ).first()
    if row:
        return row

    fallback = session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == binding.developer_prompt_id)
        .where(PromptTemplateEntry.is_active == True)
        .where(PromptTemplateEntry.role == PromptRoleEnum.DEVELOPER)
        .where(PromptTemplateEntry.mode == PromptModeEnum.SOLVE)
        .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
    ).first()
    if fallback:
        return fallback

    raise SolveTextPipelineError(
        "DEVELOPER_PROMPT_NOT_FOUND",
        "Developer prompt template is missing",
        http_status=500,
        details={"prompt_id": binding.developer_prompt_id},
    )


def _validate_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for q in questions:
        qid = str((q or {}).get("question_id") or "").strip()
        txt = str((q or {}).get("text") or "").strip()
        if not qid or not txt:
            continue
        normalized.append({"question_id": qid, "text": txt})
    if not normalized:
        raise SolveTextPipelineError("INVALID_QUESTIONS", "At least one question with question_id and text is required", 422)
    return normalized


def _enforce_caps(requested_mode: str, count: int) -> SolveModeConfig:
    cfg = MODE_CONFIG.get(requested_mode)
    if not cfg:
        raise SolveTextPipelineError(
            "INVALID_MODE",
            "requested_mode must be one of free_minimal|final_only|standard_detailed|research_detailed",
            422,
        )

    if requested_mode == "research_detailed" and count != 1:
        raise SolveTextPipelineError(
            "TOO_MANY_QUESTIONS",
            "Research mode accepts exactly one question",
            422,
            details={"max_allowed": 1, "received": count},
        )

    if count > cfg.cap:
        raise SolveTextPipelineError(
            "TOO_MANY_QUESTIONS",
            "Question count exceeds mode cap",
            422,
            details={"max_allowed": cfg.cap, "received": count},
        )

    return cfg


def _extract_schema_object(schema_entry: JsonSchemaEntry) -> Dict[str, Any]:
    content = schema_entry.content if isinstance(schema_entry.content, dict) else {}
    if isinstance(content.get("schema"), dict):
        return content["schema"]
    if isinstance(content.get("json_schema"), dict):
        inner = content["json_schema"]
        if isinstance(inner.get("schema"), dict):
            return inner["schema"]
        return inner
    if isinstance(content, dict):
        return content
    return {}


def _extract_schema_name(schema_entry: JsonSchemaEntry) -> str:
    content = schema_entry.content if isinstance(schema_entry.content, dict) else {}
    if isinstance(content.get("name"), str) and content["name"].strip():
        return content["name"].strip()
    schema_id = str(schema_entry.schema_id or "").strip()
    return schema_id.replace(".schema.json", "") if schema_id else "unknown_schema"


def _build_problem_text(questions: List[Dict[str, str]], response_language: str) -> str:
    payload = {
        "instruction": "Solve every question. Preserve each question_id exactly as provided.",
        "response_language": response_language,
        "questions": questions,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_response_language(result: Dict[str, Any], fallback_language: str) -> str:
    top = str(result.get("response_language") or "").strip().lower()
    if top:
        return top
    problem = result.get("problem") if isinstance(result.get("problem"), dict) else {}
    lang = problem.get("language") if isinstance(problem.get("language"), dict) else {}
    nested = str(lang.get("response_language") or "").strip().lower()
    return nested or fallback_language


def _effective_max_output_tokens(
    cfg: SolveModeConfig,
    binding: PromptBinding,
    question_count: int,
    requested_mode: str,
) -> int:
    base = int(binding.max_output_tokens or 0)
    if cfg.batch_supported and question_count > 1:
        if requested_mode == "final_only":
            # Final-only legacy schema remains verbose despite empty steps.
            base = max(base, 600 * question_count + 500)
        elif cfg.solver_mode == "minimal":
            # Minimal/final batch still needs enough room for full strict JSON.
            base = max(base, 220 * question_count + 250)
        else:
            # Detailed batch responses are larger per question.
            base = max(base, 900 * question_count + 400)
    if base <= 0:
        base = 4000
    return min(base, 9000)


def _normalize_final_only_schema_for_openai(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final-only responses are post-processed to always return empty steps.
    Some legacy DB schemas define `steps` in a way OpenAI strict validation rejects.
    Remove that field from schema and enforce empty steps in response shaping.
    """
    solutions = (schema.get("properties") or {}).get("solutions")
    if not isinstance(solutions, dict):
        return schema
    items = solutions.get("items")
    if not isinstance(items, dict):
        return schema
    props = items.get("properties")
    if isinstance(props, dict) and "steps" in props:
        props.pop("steps", None)
    required = items.get("required")
    if isinstance(required, list):
        items["required"] = [k for k in required if k != "steps"]
    return schema


def _ensure_solution_question_ids(solutions: List[Dict[str, Any]], requested_questions: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for idx, sol in enumerate(solutions):
        if not isinstance(sol, dict):
            continue
        qid = str(sol.get("question_id") or "").strip()
        if not qid and idx < len(requested_questions):
            qid = requested_questions[idx]["question_id"]
            sol["question_id"] = qid
        if qid:
            by_id[qid] = sol

    ordered: List[Dict[str, Any]] = []
    for q in requested_questions:
        qid = q["question_id"]
        if qid in by_id:
            ordered.append(by_id[qid])
    return ordered


def _append_missing_solution_fallbacks(
    solutions: List[Dict[str, Any]],
    requested_questions: List[Dict[str, str]],
    *,
    response_language: str,
) -> List[Dict[str, Any]]:
    by_id = {str((s or {}).get("question_id") or "").strip() for s in solutions if isinstance(s, dict)}
    out = list(solutions)
    for q in requested_questions:
        qid = q["question_id"]
        if qid in by_id:
            continue
        fallback_text = (
            "تعذر توليد حل كامل. حاول مرة اخرى."
            if response_language == "ar"
            else "Echec de generation complete. Reessayez."
            if response_language == "fr"
            else "Could not generate a complete solution. Please retry."
        )
        out.append(
            {
                "question_id": qid,
                "steps": [],
                "final_answer": {"answer_text": fallback_text},
            }
        )
    return out


def _enforce_language_cue(
    solutions: List[Dict[str, Any]],
    *,
    response_language: str,
) -> None:
    if response_language != "fr":
        return
    for solution in solutions:
        if not isinstance(solution, dict):
            continue
        final_answer = solution.get("final_answer")
        if not isinstance(final_answer, dict):
            continue
        answer_text = final_answer.get("answer_text")
        if not isinstance(answer_text, str) or not answer_text.strip():
            continue
        lowered = answer_text.lower()
        if any(token in lowered for token in (" le ", " la ", " les ", " des ", " et ", "donc", "derivee", "etape", "solution")):
            continue
        final_answer["answer_text"] = f"Solution: {answer_text}"


async def solve_text_questions(
    *,
    session: Session,
    user_id: int,
    requested_mode: str,
    tier: str,
    questions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    start = datetime.utcnow()

    normalized_questions = _validate_questions(questions)
    cfg = _enforce_caps(requested_mode, len(normalized_questions))
    response_language = _resolve_user_default_language(session, user_id)

    schema_entry = _find_schema_entry(session, cfg.schema_names)
    schema_name = _extract_schema_name(schema_entry)
    schema_body = _extract_schema_object(schema_entry)

    preferred_tier = _parse_tier_enum(cfg.binding_tier if cfg.binding_tier else tier)
    binding = _find_prompt_binding(session, schema_entry.schema_id, preferred_tier)
    system_prompt = _find_system_prompt(session, binding.global_system_prompt_id)
    developer_prompt = _find_developer_prompt(session, binding)

    deref_schema_body = deref_json_schema(schema_body)
    validate_no_refs(deref_schema_body, raise_error=True)
    if requested_mode == "final_only":
        deref_schema_body = _normalize_final_only_schema_for_openai(deref_schema_body)

    schema_wrapper = build_openai_structured_output(
        {
            "type": "json_schema",
            "name": schema_name,
            "strict": bool((schema_entry.content or {}).get("strict", True)) if isinstance(schema_entry.content, dict) else True,
            "schema": deref_schema_body,
        },
        endpoint="responses",
        call_name="SOLVE",
    )

    solver = get_solver_v3()

    if not cfg.batch_supported:
        # Research mode: exactly one only; still routed through the same service.
        question = normalized_questions[0]
        problem_text = question["text"]
    else:
        problem_text = _build_problem_text(normalized_questions, response_language)

    context = f"response_language={response_language}; requested_mode={requested_mode}; question_count={len(normalized_questions)}"

    error_code: Optional[str] = None
    model_used: Optional[str] = None
    finish_reason: Optional[str] = None
    truncated = False
    latency_ms = 0
    tokens: Dict[str, Any] = {}

    try:
        max_output_tokens = _effective_max_output_tokens(
            cfg,
            binding,
            len(normalized_questions),
            requested_mode,
        )
        response_data, tokens, status_info, model_used, raw_content, _build_ms = await solver._call_llm_with_schema(
            problem_text=problem_text,
            context=context,
            system_prompt=system_prompt.content,
            developer_prompt=developer_prompt.content,
            json_schema_config=schema_wrapper,
            max_output_tokens=max_output_tokens,
            trace=False,
            trusted_context={"response_language": response_language, "requested_mode": requested_mode},
            requested_mode=cfg.solver_mode,
            request_id=request_id,
        )

        finish_reason = str((status_info or {}).get("finish_reason") or "")
        truncated = finish_reason == "length" or str((status_info or {}).get("status") or "") == "incomplete"

        ok, validation_msg, validated, issues, is_ambiguous = solver._check_status_and_validate(
            response_data,
            status_info or {},
            schema_wrapper.get("schema") or {},
            raw_text=raw_content,
        )
        if not ok or not isinstance(validated, dict):
            if truncated:
                error_code = "PROVIDER_TIMEOUT"
                raise SolveTextPipelineError(
                    "PROVIDER_TIMEOUT",
                    "Provider response incomplete or truncated",
                    504,
                    details={"finish_reason": finish_reason},
                )
            if is_ambiguous:
                error_code = "AMBIGUOUS_INPUT"
                raise SolveTextPipelineError("AMBIGUOUS_INPUT", validation_msg or "Ambiguous input", 422)
            # Attempt one strict schema repair pass before failing.
            try:
                repaired_data, repaired_raw = await solver._repair_response(
                    problem_text,
                    context,
                    system_prompt.content,
                    response_data,
                    validation_msg or "Schema validation failed",
                    issues,
                    schema_wrapper,
                    max_output_tokens=max_output_tokens,
                    requested_mode=cfg.solver_mode,
                    trace=False,
                    provider="openai",
                    model=model_used,
                )
                ok2, validation_msg2, validated2, issues2, _ = solver._check_status_and_validate(
                    repaired_data,
                    status_info or {},
                    schema_wrapper.get("schema") or {},
                    raw_text=repaired_raw,
                )
                if ok2 and isinstance(validated2, dict):
                    validated = validated2
                else:
                    error_code = "SCHEMA_INVALID"
                    raise SolveTextPipelineError(
                        "SCHEMA_INVALID",
                        validation_msg2 or validation_msg or "Schema validation failed",
                        502,
                        details={"issues": issues2 or issues},
                    )
            except SolveTextPipelineError:
                raise
            except Exception:
                error_code = "SCHEMA_INVALID"
                raise SolveTextPipelineError(
                    "SCHEMA_INVALID",
                    validation_msg or "Schema validation failed",
                    502,
                    details={"issues": issues},
                )

        result_payload = validated

        if cfg.batch_supported:
            raw_solutions = result_payload.get("solutions")
            if not isinstance(raw_solutions, list):
                error_code = "SCHEMA_INVALID"
                raise SolveTextPipelineError("SCHEMA_INVALID", "Batch schema output missing solutions[]", 502)
            solutions = _ensure_solution_question_ids(raw_solutions, normalized_questions)
            solutions = _append_missing_solution_fallbacks(
                solutions,
                normalized_questions,
                response_language=response_language,
            )
        else:
            single = dict(result_payload)
            if not single.get("question_id"):
                single["question_id"] = normalized_questions[0]["question_id"]
            solutions = [single]

        if requested_mode == "final_only":
            for solution in solutions:
                if isinstance(solution, dict):
                    solution["steps"] = []

        _enforce_language_cue(solutions, response_language=response_language)

        # Server-authoritative language: user profile default_language (fallback "en").
        resolved_response_language = response_language
        latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        output = {
            "ok": True,
            "request_id": request_id,
            "attempt_id": attempt_id,
            "requested_mode": requested_mode,
            "schema_name": schema_name,
            "response_language": resolved_response_language,
            "question_count": len(normalized_questions),
            "solutions": solutions,
            "raw": result_payload,
            "telemetry": {
                "request_id": request_id,
                "attempt_id": attempt_id,
                "model": model_used,
                "finish_reason": finish_reason,
                "truncated": truncated,
                "tokens": {
                    "input": tokens.get("input"),
                    "output": tokens.get("output"),
                    "total": tokens.get("total"),
                    "cached": tokens.get("cached"),
                },
                "latency_ms": latency_ms,
            },
        }

        logger.info(
            "text_solve_pipeline request_id=%s attempt_id=%s requested_mode=%s schema_name=%s question_count=%s response_language=%s tokens_total=%s latency_ms=%s finish_reason=%s truncated=%s error_code=%s",
            request_id,
            attempt_id,
            requested_mode,
            schema_name,
            len(normalized_questions),
            resolved_response_language,
            tokens.get("total"),
            latency_ms,
            finish_reason,
            truncated,
            None,
        )

        return output

    except SolveTextPipelineError:
        raise
    except Exception as exc:
        latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        error_code = error_code or "TEXT_SOLVE_FAILED"
        logger.exception(
            "text_solve_pipeline request_id=%s attempt_id=%s requested_mode=%s schema_name=%s question_count=%s response_language=%s tokens_total=%s latency_ms=%s finish_reason=%s truncated=%s error_code=%s",
            request_id,
            attempt_id,
            requested_mode,
            schema_name,
            len(normalized_questions),
            response_language,
            tokens.get("total"),
            latency_ms,
            finish_reason,
            truncated,
            error_code,
        )
        raise SolveTextPipelineError(
            error_code,
            f"Text solve failed: {exc}",
            http_status=502,
        ) from exc
