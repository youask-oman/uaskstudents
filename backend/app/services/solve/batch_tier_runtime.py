import json
import logging
import math
import os
import re
import time
import hashlib
import unicodedata
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator
from sqlmodel import Session, select

from app.models import (
    PromptBinding,
    PromptModeEnum,
    PromptTierEnum,
    SystemConfig,
    User,
)
from app.services.llm.manager import LLMManager, get_configured_ollama_model, get_llm_manager
from app.services.llm.clients import LLMProviderError
from app.services.prompt_manager import prompt_manager
from app.services.prompt_binding_policy import (
    ALLOWED_PROMPT_IDS,
    ALLOWED_SCHEMA_IDS,
    SOLVE_TIER_POLICY,
    normalize_external_tier,
)
from app.services.solve.local_final_solver import try_solve_final_with_sympy_numpy
from app.services.solve.ollama_short_user_extractor import build_short_tier_extraction
from app.services.solve.sympy_numpy_gate import run_mandatory_sympy_numpy_gate


logger = logging.getLogger(__name__)

SOLVER_RUNTIME_CONFIG_DEFAULTS: Dict[str, Dict[str, str]] = {
    "SOLVE_LOCAL_SYMPY_NUMPY_ENABLED": {
        "value": "true",
        "description": "Enable local SymPy/NumPy solve path before LLM fallback (FINAL/SHORT tiers).",
    },
}

PLACEHOLDER_TOKEN_RE = re.compile(r"\{[A-Z_]+\}")
FREE_BATCH_SCHEMA_NAME = "solve_batch_free_v2"
FREE_BATCH_SCHEMA_VERSION = "v2"
FREE_BATCH_MAX_QUESTIONS = 5
FREE_BATCH_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "openai_schemas"
    / "schema__solve_batch_free_v2.schema_openai_strict.json"
)


def _tier_default_max_steps(external_tier: str) -> int:
    t = (external_tier or "").strip().upper()
    if t == "FINAL":
        return 2
    if t == "SHORT_STEPS":
        return 6
    if t == "STANDARD":
        return 12
    if t == "RESEARCH":
        return 20
    return 8


def _tier_default_step_style(external_tier: str) -> str:
    t = (external_tier or "").strip().upper()
    if t in {"FINAL", "SHORT_STEPS"}:
        return "compact"
    if t == "RESEARCH":
        return "detailed"
    return "standard"


def _to_bool_text(value: Any, default: bool) -> str:
    if value is None:
        return "true" if default else "false"
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return "true"
    if s in {"0", "false", "no", "off"}:
        return "false"
    return "true" if default else "false"


def _resolve_user_prompt_context(
    *,
    session: Session,
    user_id: Optional[int],
    trusted_context: Optional[Dict[str, Any]],
    binding_features: Dict[str, Any],
) -> Dict[str, str]:
    ctx = trusted_context if isinstance(trusted_context, dict) else {}
    user: Optional[User] = None
    if user_id is not None:
        try:
            user = session.get(User, int(user_id))
        except Exception:
            user = None

    country = str(
        ctx.get("country")
        or (getattr(user, "profile_country", None) if user else None)
        or (getattr(user, "country", None) if user else None)
        or ""
    ).strip()
    region = str(
        ctx.get("region")
        or ctx.get("region_state_province")
        or (getattr(user, "profile_province_state", None) if user else None)
        or ""
    ).strip()
    curriculum = str(ctx.get("curriculum") or binding_features.get("curriculum") or "").strip()
    grade_level = str(ctx.get("grade_level") or (getattr(user, "grade_level", None) if user else None) or "").strip()
    course = str(ctx.get("course") or binding_features.get("course") or "").strip()
    notation_profile = str(
        ctx.get("notation_profile")
        or binding_features.get("notation_profile")
        or "decimal_dot,radians_default"
    ).strip()

    return {
        "COUNTRY": country or "unknown",
        "REGION": region or "unknown",
        "CURRICULUM": curriculum or "unknown",
        "GRADE_LEVEL": grade_level or "unknown",
        "COURSE": course or "unknown",
        "NOTATION_PROFILE": notation_profile,
    }


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
ALLOWED_LOCAL_TASKS = {
    "solve",
    "simplify",
    "factor",
    "expand",
    "evaluate",
    "equation",
    "inequality",
    "system",
    "word_problem",
    "graph",
    "plot",
    "geometry",
    "trigonometry",
    "calculus",
    "probability",
    "statistics",
    "linear_algebra",
    "matrix_algebra",
    "diagonalization",
    "eigenvalues",
    "eigenvectors",
    "svd",
    "pca",
    "determinants",
    "rank",
    "nullspace",
    "orthogonality",
    "quadratic_forms",
    "spectral_theory",
    "numerical_linear_algebra",
    "real_analysis",
    "complex_analysis",
    "functional_analysis",
    "measure_theory",
    "topology",
    "differential_equations",
    "ode",
    "pde",
    "dynamical_systems",
    "stability_analysis",
    "bifurcation_analysis",
    "chaos",
    "fourier_analysis",
    "laplace_transform",
    "z_transform",
    "number_theory",
    "discrete_math",
    "combinatorics",
    "graph_theory",
    "logic",
    "set_theory",
    "optimization",
    "convex_optimization",
    "nonconvex_optimization",
    "linear_programming",
    "integer_programming",
    "variational_methods",
    "stochastic_processes",
    "markov_chains",
    "bayesian_inference",
    "time_series",
    "regression",
    "hypothesis_testing",
    "statistical_learning",
    "information_theory",
    "numerical_analysis",
    "approximation",
    "interpolation",
    "integration",
    "differentiation",
    "monte_carlo",
    "simulation",
    "abstract_algebra",
    "group_theory",
    "ring_theory",
    "field_theory",
    "galois_theory",
    "geometry_analytic",
    "geometry_differential",
    "tensor_calculus",
    "vector_calculus",
    "physics_math",
    "signals_systems",
    "control_theory",
    "computer_algebra",
    "proof",
    "counterexample",
    "verification",
    "derivation",
    "error_analysis",
    "data_science",
    "machine_learning_math",
    "other",
}


def _is_final_local_only_enabled() -> bool:
    # Safe default: FINAL should stay local-only unless explicitly opted into fallback.
    allow_fallback = os.environ.get("FINAL_TIER_ALLOW_OPENAI_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}
    if allow_fallback:
        return False
    raw = os.environ.get("FINAL_TIER_LOCAL_ONLY", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _parse_bool_flag(raw: Any, default: bool) -> bool:
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _read_system_bool_config(
    session: Session,
    key: str,
    *,
    default: bool,
) -> bool:
    # DB config is source of truth for admin toggles. Env key remains fallback for safety.
    try:
        row = session.get(SystemConfig, key)
        if row and row.value is not None:
            return _parse_bool_flag(row.value, default)
    except Exception:
        pass
    return _parse_bool_flag(os.environ.get(key), default)


def _flatten_messages_for_ollama_prompt(messages: Optional[List[Dict[str, Any]]]) -> str:
    chunks: List[str] = []
    for msg in messages or []:
        role = str((msg or {}).get("role") or "user").upper()
        content = (msg or {}).get("content", "")
        if isinstance(content, list):
            text_parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") in {"text", "input_text"}:
                    text_parts.append(str(part.get("text") or ""))
            content_text = "\n".join([p for p in text_parts if p])
        else:
            content_text = str(content)
        chunks.append(f"[{role}]\n{content_text}")
    return "\n\n".join([c for c in chunks if c.strip()]).strip()


def _dump_ollama_runtime_prompt_txt(
    *,
    runtime_request_id: str,
    runtime_attempt_id: str,
    tier: str,
    model_name: str,
    request_id_suffix: str,
    force_json_only: bool,
    call_messages: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    flag = (os.environ.get("OLLAMA_DUMP_RUNTIME_PROMPT") or "").strip().lower()
    enabled = (
        flag in {"1", "true", "yes", "on"}
        or (flag == "" and str(tier).upper() == "SHORT_STEPS")
    )
    if not enabled:
        return None

    try:
        dump_dir = Path((os.environ.get("OLLAMA_PROMPT_DUMP_DIR") or ".").strip() or ".")
        dump_dir.mkdir(parents=True, exist_ok=True)
        safe_request = re.sub(r"[^a-zA-Z0-9_-]", "_", runtime_request_id or "no_request")
        safe_suffix = re.sub(r"[^a-zA-Z0-9_-]", "_", request_id_suffix or "")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = (
            f"ollama_runtime_prompt_{safe_request}{safe_suffix}_{ts}.txt"
            if safe_suffix
            else f"ollama_runtime_prompt_{safe_request}_{ts}.txt"
        )
        out_path = dump_dir / filename
        prompt_text = _flatten_messages_for_ollama_prompt(call_messages)
        payload = (
            f"timestamp_utc: {datetime.now(timezone.utc).isoformat()}\n"
            f"request_id: {runtime_request_id}\n"
            f"attempt_id: {runtime_attempt_id}\n"
            f"tier: {tier}\n"
            f"provider: ollama\n"
            f"model: {model_name}\n"
            f"request_id_suffix: {request_id_suffix}\n"
            f"force_json_only: {str(force_json_only).lower()}\n"
            "\n---BEGIN_PROMPT---\n"
            f"{prompt_text}\n"
            "---END_PROMPT---\n"
        )
        out_path.write_text(payload, encoding="utf-8")
        return str(out_path)
    except Exception as exc:
        logger.warning("Failed to dump Ollama runtime prompt: %s", exc)
        return None


def _enforce_solve_binding_allowlist() -> bool:
    return os.environ.get("SOLVE_BINDING_ENFORCE_ALLOWLIST", "").strip().lower() in {"1", "true", "yes", "on"}


def _allow_openai_fallback_for_ollama_first_tiers() -> bool:
    # Default OFF: SHORT_STEPS/FINAL should stay Ollama-only unless explicitly enabled.
    # Accept both keys to avoid config drift across runtime paths.
    for key in ("ALLOW_OPENAI_FALLBACK_SHORT_FINAL", "FINAL_TIER_ALLOW_OPENAI_FALLBACK"):
        raw = (os.environ.get(key) or "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
    return False


def _managed_prompt_feature_enabled() -> bool:
    raw = (os.environ.get("OPENAI_PROMPT_ID_ENABLED") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Default OFF: managed prompt must be explicitly enabled.
    return False


def _build_managed_prompt_batch_input(questions: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, q in enumerate(questions or [], start=1):
        qtext = str((q or {}).get("question_text") or "").strip()
        if qtext:
            lines.append(f"Q{idx}: {qtext}")
    return "\n\n".join(lines).strip()


def _questions_json_compact(questions: List[Dict[str, Any]]) -> str:
    return json.dumps(questions or [], ensure_ascii=False, separators=(",", ":"))


def _load_free_batch_schema_wrapper() -> Dict[str, Any]:
    try:
        raw = json.loads(FREE_BATCH_SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BatchSolveError(
            "Failed to load FREE batch schema file.",
            status_code=500,
            code="schema_load_failed",
            details={"path": str(FREE_BATCH_SCHEMA_PATH), "error": str(exc)},
        ) from exc
    wrapper = _coerce_to_openai_schema_wrapper(raw, schema_name_fallback=FREE_BATCH_SCHEMA_NAME)
    if str(wrapper.get("name") or "").strip() != FREE_BATCH_SCHEMA_NAME:
        raise BatchSolveError(
            "FREE batch schema wrapper has unexpected schema name.",
            status_code=500,
            code="schema_wrapper_invalid",
            details={"expected": FREE_BATCH_SCHEMA_NAME, "actual": wrapper.get("name")},
        )
    return wrapper


def _build_free_batch_prompt_variables(
    *,
    runtime_request_id: str,
    runtime_attempt_id: str,
    runtime_mode: str,
    runtime_graph: str,
    runtime_domain: str,
    runtime_lang: str,
    normalized_questions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    questions_json_str = _questions_json_compact(normalized_questions)
    return {
        "REQUEST_ID": runtime_request_id,
        "ATTEMPT_ID": runtime_attempt_id,
        "TIER": "FREE",
        "MAX_QUESTIONS": str(FREE_BATCH_MAX_QUESTIONS),
        "MODE": runtime_mode,
        "GRAPH_MODE": runtime_graph,
        "DOMAIN_MODE": runtime_domain,
        "PREFERRED_RESPONSE_LANGUAGE": runtime_lang,
        "QUESTIONS_JSON": questions_json_str,
    }


def _resolve_mapping_path(source: Dict[str, Any], path: str) -> Any:
    cursor: Any = source
    for token in str(path or "").split("."):
        key = token.strip()
        if not key:
            continue
        if isinstance(cursor, dict) and key in cursor:
            cursor = cursor[key]
            continue
        return None
    return cursor


def _build_managed_prompt_variables(
    mapping: Dict[str, Any],
    *,
    runtime_request_id: str,
    runtime_attempt_id: str,
    external_tier: str,
    runtime_mode: str = "SOLVE",
    runtime_graph: str = "AUTO",
    runtime_domain: str = "reals",
    runtime_lang: str = "English",
    max_questions_allowed: int = 0,
    normalized_questions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    first_question = str((normalized_questions[0] or {}).get("question_text") or "").strip() if normalized_questions else ""
    joined_questions = _build_managed_prompt_batch_input(normalized_questions)
    questions_json_str = _questions_json_compact(normalized_questions)
    context: Dict[str, Any] = {
        "request_id": runtime_request_id,
        "attempt_id": runtime_attempt_id,
        "tier": external_tier,
        "mode": runtime_mode,
        "graph_mode": runtime_graph,
        "domain_mode": runtime_domain,
        "preferred_response_language": runtime_lang,
        "max_questions": int(max_questions_allowed or 0),
        "question": first_question,
        "question_text": first_question,
        "questions_joined": joined_questions,
        "questions_json_str": questions_json_str,
        "questions_json": normalized_questions,
        "payload": {
            "request_id": runtime_request_id,
            "attempt_id": runtime_attempt_id,
            "tier": external_tier,
            "mode": runtime_mode,
            "graph_mode": runtime_graph,
            "domain_mode": runtime_domain,
            "preferred_response_language": runtime_lang,
            "max_questions_allowed": int(max_questions_allowed or 0),
            "question": first_question,
            "question_text": first_question,
            "questions_joined": joined_questions,
            "questions_json_str": questions_json_str,
            "questions_json": normalized_questions,
        },
    }
    out: Dict[str, Any] = {}
    for var_name, rule in (mapping or {}).items():
        key = str(var_name or "").strip()
        if not key:
            continue
        if isinstance(rule, str) and rule.strip():
            value = _resolve_mapping_path(context, rule.strip())
        else:
            value = rule
        if value is None:
            value = ""
        if not isinstance(value, (str, dict, list)):
            value = str(value)
        if isinstance(value, str) and not value.strip():
            # Safety defaults for common prompt variables if mapping path is wrong.
            if key in {"question", "question_text"}:
                value = first_question
            elif key == "questions_joined":
                value = joined_questions
            elif key in {"questions_json", "questions_json_str", "questions_json_array"}:
                value = questions_json_str
            elif key == "request_id":
                value = runtime_request_id
            elif key == "attempt_id":
                value = runtime_attempt_id
            elif key == "tier":
                value = external_tier
        out[key] = value

    # Canonical safety keys: always provide these runtime fields even if mapping omits them.
    canonical_defaults: Dict[str, Any] = {
        "REQUEST_ID": runtime_request_id,
        "ATTEMPT_ID": runtime_attempt_id,
        "TIER": external_tier,
        "MODE": runtime_mode,
        "GRAPH_MODE": runtime_graph,
        "DOMAIN_MODE": runtime_domain,
        "PREFERRED_RESPONSE_LANGUAGE": runtime_lang,
        "MAX_QUESTIONS": str(int(max_questions_allowed or 0)),
        "QUESTION": first_question,
        "QUESTION_TEXT": first_question,
        "QUESTIONS_JOINED": joined_questions,
        "QUESTIONS_JSON": questions_json_str,
        "QUESTIONS_JSON_ARRAY": questions_json_str,
        "request_id": runtime_request_id,
        "attempt_id": runtime_attempt_id,
        "tier": external_tier,
        "mode": runtime_mode,
        "graph_mode": runtime_graph,
        "domain_mode": runtime_domain,
        "preferred_response_language": runtime_lang,
        "max_questions": int(max_questions_allowed or 0),
        "question": first_question,
        "question_text": first_question,
        "questions_joined": joined_questions,
        "questions_json_str": questions_json_str,
        "questions_json": questions_json_str,
        "questions_json_array": questions_json_str,
    }
    for k, v in canonical_defaults.items():
        existing = out.get(k)
        if existing is None:
            out[k] = v
            continue
        if isinstance(existing, str) and not existing.strip():
            out[k] = v

    # Do not send empty question payload vars to OpenAI managed prompt runtime.
    # If a value is missing/empty, omit the key entirely instead of sending blanks.
    removable_when_empty = {
        "QUESTION",
        "question",
        "QUESTION_TEXT",
        "question_text",
        "QUESTIONS_JSON_ARRAY",
        "questions_json_array",
    }
    for key in list(out.keys()):
        if key not in removable_when_empty:
            continue
        raw_val = out.get(key)
        txt = str(raw_val or "").strip()
        if not txt:
            out.pop(key, None)
            continue
        if key in {"QUESTIONS_JSON_ARRAY", "questions_json_array"} and txt == "[]":
            out.pop(key, None)
    return out


def _render_prompt_cache_key(template: str, replacements: Dict[str, Any]) -> str:
    raw_template = str(template or "").strip()
    if not raw_template:
        return ""
    str_replacements = {str(k): str(v) for k, v in (replacements or {}).items()}
    rendered = _replace_prompt_tokens(raw_template, str_replacements).strip()
    rendered = PLACEHOLDER_TOKEN_RE.sub("", rendered).strip()
    if len(rendered) <= 64:
        return rendered
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:48]
    return f"pbk:{digest}"


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


def _schema_version_for_prompt(schema_body: Dict[str, Any], default: str = "v1") -> str:
    if not isinstance(schema_body, dict):
        return default
    props = schema_body.get("properties")
    if not isinstance(props, dict):
        return default
    ver = props.get("schema_version")
    if not isinstance(ver, dict):
        return default
    const_val = ver.get("const")
    if isinstance(const_val, str) and const_val.strip():
        return const_val.strip()
    enum_vals = ver.get("enum")
    if isinstance(enum_vals, list) and enum_vals and isinstance(enum_vals[0], str) and enum_vals[0].strip():
        return str(enum_vals[0]).strip()
    return default


def _enforce_authoritative_dev_prompt_lines(prompt_text: str, replacements: Dict[str, str]) -> str:
    """
    Normalize known binding lines even when legacy templates are hard-coded
    instead of using placeholders.
    """
    out = str(prompt_text or "")
    mapping = {
        "SCHEMA_NAME": ("SCHEMA_NAME=", True),
        "SCHEMA_VERSION": ("SCHEMA_VERSION=", True),
        "TIER": ("TIER=", True),
        "request_id": ("request_id:", False),
        "attempt_id": ("attempt_id:", False),
        "preferred_response_language": ("preferred_response_language:", False),
        "max_questions_allowed": ("max_questions_allowed:", False),
        "default_mode": ("default_mode:", False),
        "default_domain_mode": ("default_domain_mode:", False),
        "graph_mode": ("graph_mode:", False),
        "max_steps": ("max_steps:", False),
        "step_style": ("step_style:", False),
        "include_task_results": ("include_task_results:", False),
        "prefer_exact": ("prefer_exact:", False),
        "country": ("country:", False),
        "region": ("region:", False),
        "curriculum": ("curriculum:", False),
        "grade_level": ("grade_level:", False),
        "course": ("course:", False),
        "notation_profile": ("notation_profile:", False),
        "question": ("question:", False),
        "questions_json_array": ("questions_json_array:", False),
    }

    for key, (prefix, upper_key) in mapping.items():
        rep_key = key if not upper_key else key
        if upper_key:
            value = str(replacements.get(rep_key, "")).strip()
        else:
            value = str(replacements.get(key.upper(), "")).strip()
        if not value:
            continue
        pattern = rf"(?im)^(?P<lead>\s*{re.escape(prefix)}\s*)(?P<val>.*)$"
        out = re.sub(pattern, lambda m: f"{m.group('lead')}{value}", out)
    return out


def _preview_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _as_questions_json_array(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _preflight_mapped_inputs(payload: Dict[str, Any]) -> None:
    """
    Validate mapped prompt inputs before any provider call:
    - If QUESTIONS_JSON_ARRAY exists and non-empty, each item must include
      non-empty question_id and question_text.
    - Otherwise QUESTION must be a non-empty string.
    """
    qarr = payload.get("QUESTIONS_JSON_ARRAY")
    qarr_items = _as_questions_json_array(qarr)
    if qarr_items:
        for idx, item in enumerate(qarr_items):
            qid = str(item.get("question_id") or "").strip()
            qtext = str(item.get("question_text") or "").strip()
            if not qid:
                raise BatchSolveError(
                    f"Missing question_id at index {idx}",
                    status_code=400,
                    code="missing_mapped_input",
                )
            if not qtext:
                raise BatchSolveError(
                    f"Missing question_text at index {idx}",
                    status_code=400,
                    code="missing_mapped_input",
                )
        return

    question = payload.get("QUESTION")
    if isinstance(question, str) and question.strip():
        return

    raise BatchSolveError(
        "Missing mapped input: send QUESTIONS_JSON_ARRAY or QUESTION",
        status_code=400,
        code="missing_mapped_input",
    )


def _is_managed_prompt_unavailable_error(exc: Exception) -> bool:
    """
    Detect OpenAI managed prompt missing/disabled errors so runtime can
    fall back to DB prompt binding content for the same request.
    """
    text = str(exc or "").lower()
    status_code = 0
    if isinstance(exc, LLMProviderError):
        try:
            status_code = int(exc.status_code or 0)
        except Exception:
            status_code = 0
        details = exc.details if isinstance(exc.details, dict) else {}
        if status_code <= 0:
            try:
                status_code = int(details.get("status_code") or 0)
            except Exception:
                status_code = 0
        detail_msg = str(details.get("message") or "").lower()
        if detail_msg:
            text = f"{text}\n{detail_msg}"

    prompt_unavailable = (
        ("prompt with id" in text and "not found" in text)
        or ("managed prompt" in text and "not found" in text)
        or ("prompt" in text and "disabled" in text)
    )
    prompt_variable_hard_fail = (
        "managed prompt variables are required" in text
        or "managed_prompt_variables_required" in text
    )
    return bool((prompt_unavailable and (status_code in {0, 400, 404})) or prompt_variable_hard_fail)


def _capture_openai_raw_and_stop(
    *,
    runtime_request_id: str,
    provider_response: Any,
) -> None:
    raw_payload = getattr(provider_response, "payload", None) if provider_response is not None else None
    raw_response = raw_payload.get("openai_response_raw") if isinstance(raw_payload, dict) else None
    if raw_response is None:
        raise BatchSolveError(
            "Requested raw OpenAI capture, but raw response was unavailable.",
            status_code=500,
            code="openai_raw_capture_missing",
        )
    out_dir = Path(__file__).resolve().parents[2] / "storage" / "debug" / "openai_raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{ts}_{runtime_request_id}_raw_before_processing.json"
    out_path.write_text(json.dumps(raw_response, ensure_ascii=False, indent=2), encoding="utf-8")
    raise BatchSolveError(
        "Stopped after raw OpenAI response capture (before parsing/saving).",
        status_code=409,
        code="openai_raw_capture_stop",
        details={"raw_response_path": str(out_path), "request_id": runtime_request_id},
    )


def _extract_json_candidate(raw: str) -> Optional[str]:
    text = (raw or "").strip()
    if not text:
        return None
    # Prefer fenced JSON block if present.
    fence = re.search(r"```json\s*(\{[\s\S]*\})\s*```", text, flags=re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    # Fallback: largest object-looking slice.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1].strip()


_PLACEHOLDER_RE = re.compile(
    r"(your\s+final\s+answer\s+here|computed\s+using\s+python|^\s*\.\.\.\s*$|\{formatted_answer\}|\{formatted answer\})",
    re.IGNORECASE | re.MULTILINE,
)


def _text_extractor_enabled() -> bool:
    return os.environ.get("OLLAMA_TEXT_EXTRACTOR_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}


def _clean(s: Optional[str]) -> str:
    if not s:
        return ""
    out = s.replace("\r\n", "\n").replace("\r", "\n")
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def strip_trailing_bracket_noise(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: List[str] = []
    for ln in lines:
        if re.fullmatch(r"\s*\]+[\s\]]*", ln):
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def extract_latex_blocks(text: str) -> List[str]:
    text = _clean(text)
    blocks: List[str] = []
    for rx in (
        re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
        re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
        re.compile(r"\\\((.+?)\\\)", re.DOTALL),
    ):
        for m in rx.finditer(text):
            blocks.append(_clean(m.group(1)))
    seen = set()
    out: List[str] = []
    for b in blocks:
        if b and b not in seen:
            seen.add(b)
            out.append(b)
    return out


def strip_latex(text: str) -> str:
    out = _clean(text)
    out = re.sub(r"\$\$(.+?)\$\$", "", out, flags=re.DOTALL)
    out = re.sub(r"\\\[(.+?)\\\]", "", out, flags=re.DOTALL)
    out = re.sub(r"\\\((.+?)\\\)", "", out, flags=re.DOTALL)
    return _clean(out)


def extract_boxed_numbers(text: str) -> List[float]:
    vals: List[float] = []
    for b in re.findall(r"\\boxed\{([^}]*)\}", text):
        b = _clean(b)
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", b):
            vals.append(float(b))
    return vals


def _extract_boxed_answer(text: str) -> Optional[str]:
    src = str(text or "")
    key = "\\boxed{"
    start = src.rfind(key)
    if start == -1:
        return None
    i = start + len(key)
    depth = 1
    out: List[str] = []
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(ch)
        i += 1
    candidate = "".join(out).strip()
    return candidate or None


def _strip_math_wrappers(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    wrappers = [
        (r"^\\\(([\s\S]+)\\\)$", 1),
        (r"^\\\[([\s\S]+)\\\]$", 1),
        (r"^\$([\s\S]+)\$$", 1),
    ]
    changed = True
    while changed:
        changed = False
        for pattern, group_idx in wrappers:
            m = re.match(pattern, text)
            if m:
                text = m.group(group_idx).strip()
                changed = True
    return text


def _extract_final_line_answer(text: str) -> Optional[str]:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    line_noise = re.compile(r"^(choices?|step\s*\d+|item\s*\d+|level)\b", flags=re.IGNORECASE)
    for ln in reversed(lines):
        if line_noise.search(ln):
            continue
        if re.search(r"\b(final\s*answer|therefore|hence)\b", ln, flags=re.IGNORECASE):
            rhs = re.split(r"[:=]\s*", ln, maxsplit=1)
            cand = rhs[-1].strip() if rhs else ln.strip()
            cand = _strip_math_wrappers(cand)
            if cand and not _PLACEHOLDER_RE.search(cand):
                return cand.rstrip(" .")
    for ln in reversed(lines):
        if line_noise.search(ln):
            continue
        if "=" in ln:
            cand = ln.split("=")[-1].strip()
            cand = _strip_math_wrappers(cand)
            if cand and not _PLACEHOLDER_RE.search(cand):
                return cand.rstrip(" .")
    for ln in reversed(lines[-8:]):
        if line_noise.search(ln):
            continue
        cand = _strip_math_wrappers(ln).strip()
        if cand and not _PLACEHOLDER_RE.search(cand):
            return cand.rstrip(" .")
    return None


BEGIN_SOLUTION_RE = re.compile(r"\bbegin\s*[_\-\s]*solution\b", re.IGNORECASE)
END_SOLUTION_RE = re.compile(r"\bend\s*[_\-\s]*solution\b", re.IGNORECASE)
BEGIN_STEPS_RE = re.compile(r"\bbegin\s*[_\-\s]*steps\b", re.IGNORECASE)
END_STEPS_RE = re.compile(r"\bend\s*[_\-\s]*steps\b", re.IGNORECASE)
BEGIN_FINAL_RE = re.compile(r"\bbegin\s*(?:[_\-\s]*|\(\s*)final(?:\s*\))?\b", re.IGNORECASE)
END_FINAL_RE = re.compile(r"\bend\s*[_\-\s]*final\b", re.IGNORECASE)


def _slice_between_markers(text: str, start_re: re.Pattern[str], end_re: re.Pattern[str]) -> str:
    m1 = start_re.search(text)
    if not m1:
        return ""
    tail = text[m1.end() :]
    m2 = end_re.search(tail)
    return tail[: m2.start()].strip() if m2 else tail.strip()


def _slice_steps_region(text: str) -> str:
    m_steps = BEGIN_STEPS_RE.search(text)
    if not m_steps:
        return ""
    tail = text[m_steps.end() :]
    m_end_steps = END_STEPS_RE.search(tail)
    m_begin_final = BEGIN_FINAL_RE.search(tail)
    if m_end_steps and m_begin_final:
        end_idx = min(m_end_steps.start(), m_begin_final.start())
    elif m_end_steps:
        end_idx = m_end_steps.start()
    elif m_begin_final:
        end_idx = m_begin_final.start()
    else:
        end_idx = len(tail)
    return tail[:end_idx].strip()


def parse_steps_block(steps_block: str) -> List[Dict[str, Any]]:
    steps_block = _clean(steps_block)
    if not steps_block:
        return []
    chunks = re.findall(r"(?ms)^\s*(\d+)\)\s*(.+?)(?=^\s*\d+\)\s*|\Z)", steps_block)
    steps: List[Dict[str, Any]] = []
    for num_s, body in chunks:
        idx = int(num_s)
        body = body.strip()
        latex = extract_latex_blocks(body)
        explanation = strip_latex(body)
        steps.append(
            {
                "index": idx,
                "title": f"Step {idx}",
                "explanation": explanation,
                "math_latex": latex,
            }
        )
    steps.sort(key=lambda x: int(x["index"]))
    return steps


@dataclass
class _ParsedBlock:
    kind: str
    content: str


@dataclass
class _ParsedStep:
    index: int
    kind: str
    blocks: List[_ParsedBlock]
    raw: str


@dataclass
class _ParsedSection:
    label: str
    heading: str
    steps: List[_ParsedStep]
    final_answer: Optional[str]
    incomplete: bool


@dataclass
class _ParsedResult:
    sections: List[_ParsedSection]
    global_final_answer: Optional[str]
    warnings: List[str]


_GARBLED_HEADER_RE = re.compile(r"^\s*\[[^\]]{1,40}\]\s*\n+", re.UNICODE)
_SECTION_HEAD_RE = re.compile(r"(?m)^\s*\((?P<label>[a-zA-Z0-9]+)\)\s+")
_MATH_BLOCK_RE = re.compile(r"(?s)(\\\[(?:.*?){1,}?\\\]|\\\((?:.*?){1,}?\\\)|\$\$(?:.*?){1,}?\$\$)")
_FINAL_CUE_RE = re.compile(r"(?i)\b(final answer|answer|therefore|thus|hence|solution is|we conclude|so,?\s+)\b")
_CONCLUSION_CUES = (
    "therefore",
    "thus",
    "hence",
    "so,",
    "so ",
    "final answer",
    "answer:",
    "solution is",
    "we get:",
    "this gives",
    "conclude",
)
_NOTE_CUES = ("note:", "remark:", "warning:", "this is not correct", "incorrect", "however")


def _clean_llm_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    text = _GARBLED_HEADER_RE.sub("", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _split_into_sections(text: str) -> List[Tuple[str, str]]:
    matches = list(_SECTION_HEAD_RE.finditer(text))
    if not matches:
        return [("main", text)]
    out: List[Tuple[str, str]] = []
    for i, m in enumerate(matches):
        label = m.group("label")
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((label, text[start:end].strip()))
    return out


def _split_blocks_preserve_math(text: str) -> List[_ParsedBlock]:
    blocks: List[_ParsedBlock] = []
    pos = 0
    for m in _MATH_BLOCK_RE.finditer(text):
        if m.start() > pos:
            chunk = text[pos : m.start()]
            if chunk.strip():
                blocks.append(_ParsedBlock(kind="text", content=chunk.strip()))
        blocks.append(_ParsedBlock(kind="math", content=m.group(1).strip()))
        pos = m.end()
    if pos < len(text):
        tail = text[pos:]
        if tail.strip():
            blocks.append(_ParsedBlock(kind="text", content=tail.strip()))
    return blocks


def _classify_step_kind(paragraph: str) -> str:
    low = str(paragraph or "").lower()
    if any(cue in low for cue in _NOTE_CUES):
        return "note"
    if any(cue in low for cue in _CONCLUSION_CUES):
        return "conclusion"
    return "work"


def _paragraph_split(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def _looks_incomplete(text: str) -> bool:
    t = str(text or "")
    if t.count(r"\[") != t.count(r"\]"):
        return True
    if t.count(r"\(") != t.count(r"\)"):
        return True
    if t.count("$$") % 2 == 1:
        return True
    tail = t.strip()[-20:].lower()
    if tail.endswith((r"\frac{", r"\sqrt{", r"\left", r"\right", "=")):
        return True
    if re.search(r"[A-Za-z]\s*$", t):
        return True
    return False


def _extract_final_answer(section_text: str) -> Optional[str]:
    paras = _paragraph_split(section_text)
    cue_idxs = [i for i, p in enumerate(paras) if _FINAL_CUE_RE.search(p)]
    candidate_para = paras[cue_idxs[-1]] if cue_idxs else None

    def _last_math_in(text: str) -> Optional[str]:
        blks = _split_blocks_preserve_math(text)
        for b in reversed(blks):
            if b.kind == "math":
                return b.content
        return None

    boxed = _extract_boxed_answer(section_text)
    if boxed:
        return boxed

    if candidate_para:
        m = _last_math_in(candidate_para)
        if m:
            return m
        return candidate_para.strip()

    all_blocks = _split_blocks_preserve_math(section_text)
    for b in reversed(all_blocks):
        if b.kind == "math":
            return b.content
    # Avoid treating arbitrary trailing prose as a final answer.
    return None


def _parse_llm_solution(raw_text: str) -> _ParsedResult:
    warnings: List[str] = []
    text = _clean_llm_text(raw_text)
    raw_sections = _split_into_sections(text)
    sections: List[_ParsedSection] = []

    for label, sec_text in raw_sections:
        paras = _paragraph_split(sec_text)
        steps: List[_ParsedStep] = []
        for i, p in enumerate(paras, start=1):
            blocks = _split_blocks_preserve_math(p)
            steps.append(_ParsedStep(index=i, kind=_classify_step_kind(p), blocks=blocks, raw=p))
        final_answer = _extract_final_answer(sec_text)
        incomplete = _looks_incomplete(sec_text)
        heading = f"({label})" if label != "main" else "main"
        sections.append(
            _ParsedSection(
                label=str(label),
                heading=heading,
                steps=steps,
                final_answer=final_answer,
                incomplete=incomplete,
            )
        )

    global_final: Optional[str] = None
    for s in reversed(sections):
        if s.final_answer:
            global_final = s.final_answer
            break
    if any(s.incomplete for s in sections):
        warnings.append("Model output looks truncated or has unclosed math delimiters in at least one section.")

    return _ParsedResult(sections=sections, global_final_answer=global_final, warnings=warnings)


def parse_ollama_math_response(raw_text: str) -> Dict[str, Any]:
    t = strip_trailing_bracket_noise(raw_text)
    t = _clean_llm_text(_clean(t))

    # Strict marker parse first.
    steps_block = _slice_steps_region(t)
    final_block = _slice_between_markers(t, BEGIN_FINAL_RE, END_FINAL_RE)
    steps = parse_steps_block(steps_block) if steps_block else []

    # Fallback: parse any freeform output.
    if not final_block or not steps:
        parsed = _parse_llm_solution(t)
        if not steps:
            step_rows: List[Dict[str, Any]] = []
            for sec in parsed.sections:
                if len(step_rows) >= 6:
                    break
                sec_text = "\n\n".join([s.raw for s in sec.steps]).strip()
                explanation = _clean(strip_latex(sec_text))
                if len(explanation) > 260:
                    explanation = explanation[:257].rstrip() + "..."
                math_latex: List[str] = []
                for st in sec.steps:
                    for b in st.blocks:
                        if b.kind == "math":
                            math_latex.append(_clean(b.content))
                        if len(math_latex) >= 6:
                            break
                    if len(math_latex) >= 6:
                        break
                title = sec.heading if sec.heading != "main" else f"Step {len(step_rows) + 1}"
                step_rows.append(
                    {
                        "index": len(step_rows) + 1,
                        "title": title,
                        "explanation": explanation or "Computed from model output.",
                        "math_latex": [m for m in math_latex if m][:6],
                    }
                )
            steps = step_rows
        if not final_block:
            final_block = _clean(parsed.global_final_answer or "")
        if not final_block:
            final_block = _extract_boxed_answer(t) or (_extract_final_line_answer(t) or "")

    boxed_vals = extract_boxed_numbers(final_block)
    values = [{"label": f"boxed_{i}", "value": v, "value_latex": None} for i, v in enumerate(boxed_vals, start=1)]
    answer_text = _clean(strip_latex(final_block))
    if not answer_text and _clean(final_block):
        answer_text = _strip_math_wrappers(_clean(final_block))
    final_answer = {
        "answer_text": answer_text[:4000],
        "answer_latex": _clean(final_block),
        "values": values,
        "units": None,
    }
    return {"steps": steps, "final_answer": final_answer}


def _parse_ollama_short_with_user_extractor(raw_text: str) -> Dict[str, Any]:
    return build_short_tier_extraction(str(raw_text or ""))


def _is_placeholder_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if _PLACEHOLDER_RE.search(text):
        return True
    lower = text.lower()
    blocked_fragments = (
        "your final answer here",
        "step-by-step reasoning goes here",
        "placeholder",
        "tbd",
        "todo",
    )
    return any(fragment in lower for fragment in blocked_fragments)


def _is_substantive_answer_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if _is_placeholder_text(text):
        return False
    lower = text.lower()
    blocked = (
        "unsolvable:",
        "cannot solve",
        "insufficient information",
        "model output did not include a concrete final answer",
    )
    return not any(token in lower for token in blocked)


def _infer_detected_tasks(question_text: str) -> List[str]:
    q = str(question_text or "").lower()
    tags: List[str] = []
    if any(k in q for k in ("integral", "differentiate", "derivative", "limit")):
        tags.append("calculus")
    if any(k in q for k in ("probability", "without replacement", "random", "binomial")):
        tags.append("probability")
    if any(k in q for k in ("matrix", "eigen", "det(")):
        tags.append("linear_algebra")
    if any(k in q for k in ("contour", "residue", "complex")):
        tags.append("complex_analysis")
    if any(k in q for k in ("solve", "find", "compute", "evaluate")):
        tags.append("solve")
    if not tags:
        tags.append("other")
    # Keep deterministic, unique order.
    out: List[str] = []
    for t in tags:
        if t in ALLOWED_LOCAL_TASKS and t not in out:
            out.append(t)
    return out or ["other"]


def _extract_first_float(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _extract_first_int(pattern: str, text: str) -> Optional[int]:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _binom_pmf(n: int, k: int, p: float) -> float:
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * (p ** k) * ((1.0 - p) ** (n - k))


def _try_binomial_numeric_postcheck(question_text: str) -> Optional[Dict[str, Any]]:
    q = str(question_text or "")
    ql = q.lower()
    if "binomial" not in ql and "sample of" not in ql:
        return None
    n = _extract_first_int(r"sample of\s+(\d+)", q)
    p = _extract_first_float(r"probability[^0-9\-+]*([01](?:\.\d+)?)", q)
    if n is None or p is None or p < 0.0 or p > 1.0:
        return None

    at_least_k = _extract_first_int(r"at least\s+(\d+)", q)
    between_match = re.search(r"between\s+(\d+)\s+and\s+(\d+)\s+inclusive", q, flags=re.IGNORECASE)
    between_a: Optional[int] = None
    between_b: Optional[int] = None
    if between_match:
        try:
            between_a = int(between_match.group(1))
            between_b = int(between_match.group(2))
        except Exception:
            between_a = None
            between_b = None

    parts: List[str] = []
    values: List[Dict[str, Any]] = []
    if at_least_k is not None:
        prob_a = sum(_binom_pmf(n, k, p) for k in range(max(0, at_least_k), n + 1))
        parts.append(f"(a) P(X >= {at_least_k}) = {prob_a:.6f}")
        values.append({"label": f"P(X >= {at_least_k})", "value": float(f"{prob_a:.6f}"), "value_latex": None})
    if between_a is not None and between_b is not None:
        lo = min(between_a, between_b)
        hi = max(between_a, between_b)
        prob_b = sum(_binom_pmf(n, k, p) for k in range(max(0, lo), min(n, hi) + 1))
        parts.append(f"(b) P({lo} <= X <= {hi}) = {prob_b:.6f}")
        values.append({"label": f"P({lo} <= X <= {hi})", "value": float(f"{prob_b:.6f}"), "value_latex": None})
    mean = n * p
    sd = math.sqrt(n * p * (1.0 - p))
    parts.append(f"E[X] = {mean:.6f}")
    parts.append(f"SD[X] = {sd:.6f}")
    values.append({"label": "E[X]", "value": float(f"{mean:.6f}"), "value_latex": None})
    values.append({"label": "SD[X]", "value": float(f"{sd:.6f}"), "value_latex": None})

    if not parts:
        return None
    return {"answer_text": "; ".join(parts), "values": values}


def _extract_ollama_text_payload(
    *,
    raw_text: str,
    questions: List[Dict[str, Any]],
    tier: str,
    runtime_request_id: str,
    runtime_attempt_id: str,
    runtime_lang: str,
    runtime_allow_auto_split: bool,
    max_questions_allowed: int,
    runtime_max_tasks_per_question: int,
) -> Dict[str, Any]:
    tier_upper = str(tier or "").upper()
    is_prod_v2_tier = tier_upper in {"FINAL", "STANDARD", "RESEARCH"}
    if tier_upper == "SHORT_STEPS":
        first_q = questions[0] if questions else {}
        parsed = build_short_tier_extraction(
            str(raw_text or ""),
            question_text=str((first_q or {}).get("question_text") or ""),
            question_id=str((first_q or {}).get("question_id") or "q1"),
            mode=str((first_q or {}).get("mode") or "SOLVE"),
        )
    else:
        parsed = parse_ollama_math_response(raw_text)
    parsed_steps = list(parsed.get("steps") or [])
    parsed_final = dict(parsed.get("final_answer") or {})
    answer_text_global = str(parsed_final.get("answer_text") or "").strip()
    answer_latex_global = str(parsed_final.get("answer_latex") or "").strip()
    answer_values_global = list(parsed_final.get("values") or [])
    if _is_placeholder_text(answer_text_global):
        answer_text_global = ""
    if _is_placeholder_text(answer_latex_global):
        answer_latex_global = ""

    items: List[Dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        q_text = str(q.get("question_text") or "")
        detected_tasks = _infer_detected_tasks(q_text)
        answer_text = answer_text_global
        answer_latex = answer_latex_global or answer_text
        answer_values: List[Dict[str, Any]] = list(answer_values_global)

        numeric_override = _try_binomial_numeric_postcheck(q_text)
        if numeric_override is not None:
            answer_text = str(numeric_override.get("answer_text") or answer_text).strip()
            answer_latex = answer_text
            answer_values = list(numeric_override.get("values") or [])

        item_steps: List[Dict[str, Any]] = parsed_steps if tier != "FINAL" else []
        if tier != "FINAL" and not item_steps and answer_text:
            item_steps = [
                {
                    "index": 1,
                    "title": "Short Steps",
                    "explanation": "Computed from model output.",
                    "math_latex": [answer_latex] if answer_latex else [],
                }
            ]

        if answer_text:
            final_answer_obj = {
                "answer_text": answer_text,
                "answer_latex": answer_latex,
                "values": answer_values,
                "units": None,
            }
            if is_prod_v2_tier:
                final_answer_obj["kind"] = "solution"
                final_answer_obj["target"] = None
            refusal_obj = {"is_refusal": False, "reason": None, "safe_next_step": None}
            confidence = 0.62
        else:
            final_answer_obj = {
                "answer_text": "Model output did not include a concrete final answer.",
                "answer_latex": None,
                "values": [],
                "units": None,
            }
            if is_prod_v2_tier:
                final_answer_obj["kind"] = "solution"
                final_answer_obj["target"] = None
            refusal_obj = {
                "is_refusal": True,
                "reason": "missing_final_answer",
                "safe_next_step": "Retry or enable alternative provider fallback.",
            }
            confidence = 0.25

        item_obj: Dict[str, Any] = {
            "question_id": q["question_id"],
            "question_index": idx,
            "mode": q["mode"],
            "problem": {
                "original_text": q_text,
                "normalized_text": q_text[:300],
                "detected_tasks": detected_tasks,
                "extra": [],
            },
            "classification": {
                "grade_band": "college_intro",
                "domain": "other",
                "topic": "ollama_text_extraction",
                "difficulty": "medium",
            },
            "steps": item_steps,
            "final_answer": final_answer_obj,
            "refusal": refusal_obj,
            "quality": {"confidence": confidence, "common_mistakes": []},
        }
        if not is_prod_v2_tier:
            item_obj["assumptions"] = []
            item_obj["clarification"] = {
                "needs_clarification": False,
                "note": None,
                "questions": [],
            }
            item_obj["plot"] = _local_plot_stub()
        items.append(item_obj)

    payload: Dict[str, Any] = {
        "schema_version": "prod_v2" if is_prod_v2_tier else "v2",
        "tier": "FREE" if tier_upper == "SHORT_STEPS" else tier_upper,
        "language": {
            "user_language": runtime_lang,
            "preferred_response_language": runtime_lang,
            "response_language": runtime_lang,
        },
        "items": items,
    }
    if tier_upper == "SHORT_STEPS" and parsed.get("raw_user_extraction") is not None:
        payload["raw_user_extraction"] = parsed.get("raw_user_extraction")
    if tier_upper == "SHORT_STEPS" and isinstance(parsed.get("question"), dict):
        payload["question"] = parsed.get("question")
    if tier_upper == "SHORT_STEPS" and isinstance(parsed.get("problem"), dict):
        payload["problem"] = parsed.get("problem")
    if is_prod_v2_tier:
        payload["runtime"] = {
            "request_id": runtime_request_id,
            "attempt_id": runtime_attempt_id,
            "preferred_response_language": runtime_lang,
            "default_mode": "GENERAL",
            "default_graph_mode": "OFF",
            "default_domain_mode": "reals",
            "allow_auto_split": bool(runtime_allow_auto_split),
            "max_questions_allowed": int(max_questions_allowed),
            "max_tasks_per_question": int(runtime_max_tasks_per_question),
        }
    return payload


def _json_error_summary(errors: List[Any], limit: int = 10) -> str:
    parts: List[str] = []
    for err in errors[:limit]:
        path = "$" + "".join([f"[{repr(p)}]" for p in err.path])
        parts.append(f"{path}: {err.message}")
    return "; ".join(parts)


def _extract_schema_body(schema_wrapper: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema_wrapper, dict):
        raise BatchSolveError(
            "Schema wrapper is not an object.",
            status_code=500,
            code="schema_wrapper_invalid",
        )
    # 1) Native wrapper shape: {"name": "...", "schema": {...}}
    schema = schema_wrapper.get("schema")
    if isinstance(schema, dict):
        return schema

    # 2) OpenAI response_format shape:
    #    {"type":"json_schema","json_schema":{"name":"...","schema":{...}}}
    json_schema_block = schema_wrapper.get("json_schema")
    if isinstance(json_schema_block, dict):
        nested_schema = json_schema_block.get("schema")
        if isinstance(nested_schema, dict):
            return nested_schema
        # Also accept {"json_schema": {...raw schema...}}
        if isinstance(json_schema_block.get("type"), str):
            # If it has a "type" key as a JSON Schema root, treat as direct schema.
            return json_schema_block

    # 3) Direct/raw JSON Schema stored in DB.
    #    Accept if it looks like a schema root.
    if isinstance(schema_wrapper.get("type"), (str, list)):
        return schema_wrapper
    if isinstance(schema_wrapper.get("properties"), dict):
        return schema_wrapper
    if isinstance(schema_wrapper.get("$defs"), dict):
        return schema_wrapper

    raise BatchSolveError(
        "Schema payload invalid: expected schema wrapper or JSON Schema object.",
        status_code=500,
        code="schema_wrapper_invalid",
    )


def _infer_schema_name_from_raw_schema(raw_schema: Dict[str, Any], fallback: str) -> str:
    if not isinstance(raw_schema, dict):
        return fallback
    props = raw_schema.get("properties")
    if isinstance(props, dict):
        schema_name_prop = props.get("schema_name")
        if isinstance(schema_name_prop, dict):
            enum_vals = schema_name_prop.get("enum")
            if isinstance(enum_vals, list) and enum_vals:
                candidate = str(enum_vals[0] or "").strip()
                if candidate:
                    return candidate
            const_val = schema_name_prop.get("const")
            if isinstance(const_val, str) and const_val.strip():
                return const_val.strip()
    return fallback


def _coerce_to_openai_schema_wrapper(
    schema_payload: Any,
    *,
    schema_name_fallback: str,
) -> Dict[str, Any]:
    """
    Normalize DB schema payload into canonical OpenAI wrapper shape:
      {"type":"json_schema","name":str,"strict":bool,"schema":{...}}
    """
    if not isinstance(schema_payload, dict):
        raise BatchSolveError(
            "Schema payload is not an object.",
            status_code=500,
            code="schema_wrapper_invalid",
        )

    # Canonical wrapper
    if (
        schema_payload.get("type") == "json_schema"
        and isinstance(schema_payload.get("schema"), dict)
        and isinstance(schema_payload.get("name"), str)
        and schema_payload.get("name", "").strip()
    ):
        return {
            "type": "json_schema",
            "name": str(schema_payload.get("name")).strip(),
            "strict": bool(schema_payload.get("strict", True)),
            "schema": schema_payload["schema"],
        }

    # Legacy wrapper
    if isinstance(schema_payload.get("schema"), dict) and isinstance(schema_payload.get("name"), str):
        name = str(schema_payload.get("name") or "").strip()
        if name:
            return {
                "type": "json_schema",
                "name": name,
                "strict": bool(schema_payload.get("strict", True)),
                "schema": schema_payload["schema"],
            }

    # Raw schema body from DB
    if (
        isinstance(schema_payload.get("properties"), dict)
        or isinstance(schema_payload.get("$defs"), dict)
        or isinstance(schema_payload.get("required"), list)
        or isinstance(schema_payload.get("type"), (str, list))
    ):
        inferred_name = _infer_schema_name_from_raw_schema(schema_payload, schema_name_fallback)
        return {
            "type": "json_schema",
            "name": inferred_name,
            "strict": True,
            "schema": schema_payload,
        }

    raise BatchSolveError(
        "Schema payload invalid: expected wrapper or JSON Schema object.",
        status_code=500,
        code="schema_wrapper_invalid",
    )


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
    if _enforce_solve_binding_allowlist() and ALLOWED_PROMPT_IDS and binding.developer_prompt_id not in ALLOWED_PROMPT_IDS:
        raise BatchSolveError(
            f"Unexpected developer prompt binding for tier={tier.value}.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"actual": binding.developer_prompt_id, "tier": tier.value},
        )
    if _enforce_solve_binding_allowlist() and ALLOWED_SCHEMA_IDS and binding.output_schema_id not in ALLOWED_SCHEMA_IDS:
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


def _normalize_local_tasks(tasks: List[str]) -> List[str]:
    normalized: List[str] = []
    for raw in tasks or []:
        token = str(raw or "").strip().lower()
        if token in ALLOWED_LOCAL_TASKS:
            normalized.append(token)
            continue
        if token in {"limit", "algebra"}:
            normalized.append("evaluate")
            continue
    deduped: List[str] = []
    for t in normalized:
        if t not in deduped:
            deduped.append(t)
    return deduped or ["solve"]


def _extract_allowed_task_enum(schema_body: Dict[str, Any]) -> List[str]:
    try:
        # prod_v2 shape
        vals = (
            (((schema_body.get("$defs") or {}).get("problem") or {}).get("properties") or {})
            .get("detected_tasks", {})
            .get("items", {})
            .get("enum", [])
        )
        if isinstance(vals, list) and vals:
            return [str(v) for v in vals if isinstance(v, str)]
    except Exception:
        pass
    try:
        # legacy shape
        vals = (
            (((schema_body.get("properties") or {}).get("problem") or {}).get("properties") or {})
            .get("detected_tasks", {})
            .get("items", {})
            .get("enum", [])
        )
        if isinstance(vals, list) and vals:
            return [str(v) for v in vals if isinstance(v, str)]
    except Exception:
        pass
    return []


def _coerce_tasks_to_schema(tasks: List[str], allowed: List[str]) -> List[str]:
    if not allowed:
        return tasks or ["solve"]
    allowed_set = set(allowed)
    mapped: List[str] = []
    remap = {
        "differentiation": "calculus",
        "integration": "calculus",
        "ode": "calculus",
        "pde": "calculus",
        "eigenvalues": "linear_algebra",
        "eigenvectors": "linear_algebra",
        "determinants": "linear_algebra",
        "matrix_algebra": "linear_algebra",
        "optimization": "evaluate",
        "combinatorics": "evaluate",
    }
    for t in tasks or []:
        token = str(t or "").strip().lower()
        if token in allowed_set:
            mapped.append(token)
            continue
        token2 = remap.get(token, "other")
        if token2 in allowed_set:
            mapped.append(token2)
    deduped: List[str] = []
    for t in mapped:
        if t not in deduped:
            deduped.append(t)
    return deduped or (["solve"] if "solve" in allowed_set else [allowed[0]])


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


def _clean_question_text_for_local_solver(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    # Defensive cleanup for duplicated split prefixes such as:
    # "Question 1 ... 1) Question 1 ... Question 2 ..."
    matches = list(re.finditer(r"\bquestion\s+\d+\b", text, flags=re.IGNORECASE))
    if len(matches) >= 2:
        start = matches[-1].start()
        tail = text[start:].strip()
        if tail:
            return tail
    return text


def _post_assertions(
    payload: Dict[str, Any],
    *,
    schema_body: Dict[str, Any],
    questions: List[Dict[str, Any]],
    tier: str,
) -> None:
    defs = schema_body.get("$defs") if isinstance(schema_body.get("$defs"), dict) else {}

    def _resolve_schema_ref(schema_obj: Any) -> Dict[str, Any]:
        if not isinstance(schema_obj, dict):
            return {}
        ref = schema_obj.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            key = ref.split("/")[-1]
            resolved = defs.get(key)
            return resolved if isinstance(resolved, dict) else {}
        return schema_obj

    items = payload.get("items")
    if not isinstance(items, list):
        raise BatchSolveError("Output missing items[].", status_code=502, code="post_assert_failed")
    if len(items) != len(questions):
        raise BatchSolveError(
            f"items length mismatch: expected {len(questions)}, got {len(items)}.",
            status_code=502,
            code="post_assert_failed",
        )

    solve_item_schema = _resolve_schema_ref(((defs.get("SolveItem") if isinstance(defs, dict) else {}) or {}))
    solve_item_props = solve_item_schema.get("properties") if isinstance(solve_item_schema.get("properties"), dict) else {}
    expect_question_index = "question_index" in solve_item_props

    problem_schema = _resolve_schema_ref(solve_item_props.get("problem"))
    problem_props = problem_schema.get("properties") if isinstance(problem_schema.get("properties"), dict) else {}
    classification_schema = _resolve_schema_ref(solve_item_props.get("classification"))
    classification_props = (
        classification_schema.get("properties") if isinstance(classification_schema.get("properties"), dict) else {}
    )
    quality_schema = _resolve_schema_ref(solve_item_props.get("quality"))
    quality_props = quality_schema.get("properties") if isinstance(quality_schema.get("properties"), dict) else {}
    plot_schema = _resolve_schema_ref(solve_item_props.get("plot"))
    plot_props = plot_schema.get("properties") if isinstance(plot_schema.get("properties"), dict) else {}

    enum_tasks: set[str] = set()
    try:
        if "detected_tasks" in problem_props:
            enum_tasks = set(
                (_resolve_schema_ref(problem_props.get("detected_tasks")).get("items") or {}).get("enum", [])
            )
        elif "detected_tasks" in classification_props:
            enum_tasks = set(
                (_resolve_schema_ref(classification_props.get("detected_tasks")).get("items") or {}).get("enum", [])
            )
    except Exception:
        enum_tasks = set()

    for idx, (item, qin) in enumerate(zip(items, questions), start=1):
        if not isinstance(item, dict):
            raise BatchSolveError("Each item must be an object.", status_code=502, code="post_assert_failed")
        if str(item.get("question_id")) != qin["question_id"]:
            logger.warning(
                "batch_question_id_mismatch_normalized index=%s expected=%s got=%s",
                idx,
                qin["question_id"],
                item.get("question_id"),
            )
            item["question_id"] = qin["question_id"]
        if expect_question_index and int(item.get("question_index") or -1) != idx:
            logger.warning(
                "batch_question_index_mismatch_normalized index=%s expected=%s got=%s",
                idx,
                idx,
                item.get("question_index"),
            )
            item["question_index"] = idx

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

        detected_tasks: List[Any] = []
        if "problem" in solve_item_props:
            problem = item.get("problem") if isinstance(item.get("problem"), dict) else {}
            expected_text = qin["question_text"]
            got_text = str(problem.get("original_text") or "")
            # Always persist canonical original_text from input question so UI/header rendering
            # remains stable even when model summarizes or truncates the question text.
            if _normalize_question_text(got_text) != _normalize_question_text(expected_text):
                logger.warning(
                    "batch_original_text_mismatch_normalized item=%s expected=%r got=%r",
                    idx,
                    expected_text,
                    got_text,
                )
            if "original_text" in problem_props:
                problem["original_text"] = expected_text
            if "normalized_text" in problem_props:
                normalized_text = str(problem.get("normalized_text") or "").strip()
                if not normalized_text:
                    problem["normalized_text"] = expected_text
            item["problem"] = problem
            detected_tasks = problem.get("detected_tasks") if isinstance(problem.get("detected_tasks"), list) else []
        elif "classification" in solve_item_props:
            classification_obj = item.get("classification") if isinstance(item.get("classification"), dict) else {}
            detected_tasks = (
                classification_obj.get("detected_tasks")
                if isinstance(classification_obj.get("detected_tasks"), list)
                else []
            )

        if (
            ("detected_tasks" in problem_props or "detected_tasks" in classification_props)
            and not detected_tasks
        ):
            logger.warning("batch_detected_tasks_empty_normalized item=%s", idx)
            detected_tasks = ["solve"]
            if "problem" in solve_item_props:
                problem_obj = item.get("problem") if isinstance(item.get("problem"), dict) else {}
                problem_obj["detected_tasks"] = detected_tasks
                item["problem"] = problem_obj
            elif "classification" in solve_item_props:
                classification_obj = item.get("classification") if isinstance(item.get("classification"), dict) else {}
                classification_obj["detected_tasks"] = detected_tasks
                item["classification"] = classification_obj
        if enum_tasks and any(str(t) not in enum_tasks for t in detected_tasks):
            normalized_tasks = [str(t) for t in detected_tasks if str(t) in enum_tasks]
            if not normalized_tasks and "solve" in enum_tasks:
                normalized_tasks = ["solve"]
            if not normalized_tasks and enum_tasks:
                normalized_tasks = [sorted(enum_tasks)[0]]
            logger.warning(
                "batch_detected_tasks_enum_normalized item=%s before=%s after=%s",
                idx,
                detected_tasks,
                normalized_tasks,
            )
            detected_tasks = normalized_tasks
            if "problem" in solve_item_props:
                problem_obj = item.get("problem") if isinstance(item.get("problem"), dict) else {}
                problem_obj["detected_tasks"] = detected_tasks
                item["problem"] = problem_obj
            elif "classification" in solve_item_props:
                classification_obj = item.get("classification") if isinstance(item.get("classification"), dict) else {}
                classification_obj["detected_tasks"] = detected_tasks
                item["classification"] = classification_obj

        classification = item.get("classification") if isinstance(item.get("classification"), dict) else {}
        if "difficulty" in classification_props and str(classification.get("difficulty") or "") not in DIFFICULTY_ENUM:
            raise BatchSolveError(
                f"classification.difficulty invalid for item {idx}.",
                status_code=502,
                code="post_assert_failed",
            )

        plot = item.get("plot") if isinstance(item.get("plot"), dict) else {}
        if "decision_reason" in plot_props and not str(plot.get("decision_reason") or "").strip():
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
        if not bool(refusal.get("is_refusal")) and isinstance(final_answer, dict):
            ans_text = str(final_answer.get("answer_text") or "")
            ans_latex = str(final_answer.get("answer_latex") or "")
            if _is_placeholder_text(ans_text) and _is_placeholder_text(ans_latex):
                raise BatchSolveError(
                    f"final_answer contains placeholder text for item {idx}.",
                    status_code=502,
                    code="post_assert_failed",
                )
        # Optional simplified schema guard (for local/ollama experiments):
        # status == OK -> non-empty final_answer
        # status == ERR -> non-empty error
        status_val = item.get("status")
        if status_val is not None:
            status_text = str(status_val).strip().upper()
            if status_text not in {"OK", "ERR"}:
                raise BatchSolveError(
                    f"status must be one of OK/ERR for item {idx}.",
                    status_code=502,
                    code="post_assert_failed",
                )
            if status_text == "OK":
                if isinstance(final_answer, str):
                    if not final_answer.strip():
                        raise BatchSolveError(
                            f"final_answer must be non-empty when status=OK for item {idx}.",
                            status_code=502,
                            code="post_assert_failed",
                        )
            else:
                err_text = str(item.get("error") or "").strip()
                if not err_text:
                    raise BatchSolveError(
                        f"error must be non-empty when status=ERR for item {idx}.",
                        status_code=502,
                        code="post_assert_failed",
                    )

        # Optional simplified steps guard: when steps is string-array, enforce non-empty <= 6.
        steps_val = item.get("steps")
        if isinstance(steps_val, list) and steps_val and all(isinstance(s, str) for s in steps_val):
            if len(steps_val) > 6:
                raise BatchSolveError(
                    f"steps length must be <= 6 for item {idx}.",
                    status_code=502,
                    code="post_assert_failed",
                )
            for s_idx, step in enumerate(steps_val, start=1):
                if not step.strip():
                    raise BatchSolveError(
                        f"steps[{s_idx}] must be non-empty for item {idx}.",
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
        if tier == "FINAL" and "common_mistakes" in quality_props and len(mistakes) != 0:
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


def _local_plot_stub() -> Dict[str, Any]:
    return {
        "should_visualize": False,
        "decision_reason": "Plot omitted for compact tier response.",
        "recipe": None,
    }


def _local_single_step(answer_latex: Optional[str]) -> List[Dict[str, Any]]:
    return [
        {
            "index": 1,
            "title": "Local Result",
            "explanation": "Computed using SymPy with NumPy numerical checks.",
            "math_latex": [str(answer_latex)] if answer_latex else [],
        }
    ]


def _build_local_batch_payload(
    *,
    external_tier: str,
    runtime_lang: str,
    runtime_request_id: str,
    runtime_attempt_id: str,
    runtime_allow_auto_split: bool,
    max_questions_allowed: int,
    runtime_max_tasks_per_question: int,
    solved_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schema_version": "prod_v2",
        "tier": external_tier,
        "language": {
            "user_language": runtime_lang,
            "preferred_response_language": runtime_lang,
            "response_language": runtime_lang,
        },
        "runtime": {
            "request_id": runtime_request_id,
            "attempt_id": runtime_attempt_id,
            "preferred_response_language": runtime_lang,
            "default_mode": "GENERAL",
            "default_graph_mode": "OFF",
            "default_domain_mode": "reals",
            "allow_auto_split": bool(runtime_allow_auto_split),
            "max_questions_allowed": int(max_questions_allowed),
            "max_tasks_per_question": int(runtime_max_tasks_per_question),
        },
        "items": solved_items,
    }


def _build_local_refusal_like_item(
    *,
    question_id: str,
    question_index: int,
    mode: str,
    original_text: str,
    reason: str,
) -> Dict[str, Any]:
    # Keep schema-compatible shape while signaling local-only non-solve.
    # final_answer is kept non-null to satisfy strict schemas; post-assertions
    # will normalize final_answer to null when refusal.is_refusal=true.
    return {
        "question_id": question_id,
        "question_index": question_index,
        "mode": mode,
        "problem": {
            "original_text": original_text,
            "normalized_text": original_text,
            "detected_tasks": ["other"],
            "extra": [],
        },
        "classification": {
            "grade_band": "undergraduate_upper",
            "domain": "other",
            "topic": "local verification fallback",
            "difficulty": "medium",
        },
        "steps": [],
        "final_answer": {
            "answer_text": "Local SymPy/NumPy solver could not produce a high-confidence complete result for this item.",
            "answer_latex": None,
            "values": [],
            "units": None,
            "kind": "solution",
            "target": None,
        },
        "refusal": {
            "is_refusal": True,
            "reason": reason,
            "safe_next_step": "Try a simpler formulation or allow OpenAI fallback for unresolved FINAL items.",
        },
        "quality": {"confidence": 0.45, "common_mistakes": []},
    }


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
    allow_auto_split: Optional[bool] = None,
    max_tasks_per_question: Optional[int] = None,
    user_id: Optional[int] = None,
    trusted_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    started = time.perf_counter()
    external_tier = normalize_external_tier(tier)
    tier_policy = SOLVE_TIER_POLICY[external_tier]
    prompt_tier = tier_policy.prompt_tier
    normalized_questions = _build_runtime_questions(questions_json)
    local_sympy_enabled = _read_system_bool_config(
        session,
        "SOLVE_LOCAL_SYMPY_NUMPY_ENABLED",
        default=True,
    )
    sympy_numpy_reports: List[Dict[str, Any]] = []
    if local_sympy_enabled:
        for q in normalized_questions:
            qtext = str(q.get("question_text") or "")
            try:
                gate_result = run_mandatory_sympy_numpy_gate(qtext)
                sympy_numpy_reports.append(
                    {
                        "question_id": str(q.get("question_id") or ""),
                        **gate_result.as_dict(),
                    }
                )
            except Exception as exc:
                raise BatchSolveError(
                    "Mandatory SymPy/NumPy gate failed.",
                    status_code=500,
                    code="sympy_numpy_gate_failed",
                    details={
                        "question_id": str(q.get("question_id") or ""),
                        "error": str(exc),
                    },
                ) from exc

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
    if external_tier == "SHORT_STEPS" and len(normalized_questions) > FREE_BATCH_MAX_QUESTIONS:
        raise BatchSolveError(
            f"FREE tier supports at most {FREE_BATCH_MAX_QUESTIONS} questions.",
            status_code=400,
            code="free_batch_limit_exceeded",
            details={"max_questions": FREE_BATCH_MAX_QUESTIONS, "count": len(normalized_questions)},
        )
    system_prompt = str(binding_bundle["global_system_prompt"] or "")
    developer_prompt_template = str(binding_bundle["developer_prompt"] or "")
    raw_schema_payload = binding_bundle["schema"]
    schema_wrapper = _coerce_to_openai_schema_wrapper(
        raw_schema_payload,
        schema_name_fallback=str(_bget("output_schema_id") or "youask_math_openai_v1"),
    )
    schema_body = _extract_schema_body(schema_wrapper)
    allowed_task_enum = _extract_allowed_task_enum(schema_body)

    runtime_request_id = (request_id or str(uuid.uuid4())).strip()
    runtime_attempt_id = (attempt_id or str(uuid.uuid4())).strip()
    runtime_mode = _coerce_mode(mode)
    runtime_graph = _coerce_graph_mode(graph_mode)
    runtime_domain = _coerce_domain_mode(domain_mode)
    runtime_lang = (preferred_response_language or "English").strip() or "English"
    # Batch policy: multi-question payloads must always enable auto-splitting.
    # This keeps developer prompt runtime flags aligned with solve-page multi-question intent,
    # including FINAL tier.
    is_multi_question = len(normalized_questions) > 1
    runtime_allow_auto_split = is_multi_question or bool(allow_auto_split)
    runtime_max_tasks_per_question = int(max_tasks_per_question or 6)
    questions_json_text = json.dumps(normalized_questions, ensure_ascii=False)
    questions_json_text_compact = _questions_json_compact(normalized_questions)
    first_question_text = str((normalized_questions[0] or {}).get("question_text") or "").strip() if normalized_questions else ""
    binding_features_prompt = _bget("features") if isinstance(_bget("features"), dict) else {}

    def _binding_field(name: str, default: Any = None) -> Any:
        if isinstance(binding, dict):
            return binding.get(name, default)
        return getattr(binding, name, default)

    binding_openai_prompt_id = str(_binding_field("openai_prompt_id", "") or "").strip()
    binding_openai_prompt_version = str(_binding_field("openai_prompt_version", "") or "").strip()
    binding_openai_prompt_use_latest = bool(_binding_field("openai_prompt_use_latest", False))
    binding_openai_prompt_variable_mapping_raw = _binding_field("openai_prompt_variable_mapping", None)
    binding_openai_prompt_cache_key_template = str(_binding_field("openai_prompt_cache_key_template", "") or "").strip()
    binding_openai_prompt_cache_retention = str(_binding_field("openai_prompt_cache_retention", "") or "").strip()
    binding_openai_prompt_variable_mapping = (
        binding_openai_prompt_variable_mapping_raw
        if isinstance(binding_openai_prompt_variable_mapping_raw, dict)
        else {}
    )

    # Backward-compatibility only: prefer dedicated binding columns; fall back to legacy features map when unset.
    managed_prompt_id = str(
        binding_openai_prompt_id
        or binding_features_prompt.get("openai_prompt_id")
        or ""
    ).strip()
    managed_prompt_version = str(
        binding_openai_prompt_version
        or binding_features_prompt.get("openai_prompt_version")
        or ""
    ).strip()
    managed_prompt_use_latest = bool(
        binding_openai_prompt_use_latest
        if binding_openai_prompt_id
        else binding_features_prompt.get("openai_prompt_use_latest", False)
    )
    mapping_candidate = (
        binding_openai_prompt_variable_mapping
        if binding_openai_prompt_variable_mapping
        else binding_features_prompt.get("openai_prompt_variable_mapping")
    )
    managed_prompt_variable_mapping = mapping_candidate if isinstance(mapping_candidate, dict) else {}
    managed_prompt_cache_key_template = str(
        binding_openai_prompt_cache_key_template
        or binding_features_prompt.get("openai_prompt_cache_key_template")
        or ""
    ).strip()
    managed_prompt_cache_retention = str(
        binding_openai_prompt_cache_retention
        or binding_features_prompt.get("openai_prompt_cache_retention")
        or ""
    ).strip()
    if external_tier == "SHORT_STEPS":
        # FREE batch solve v2 wiring:
        # use managed prompt only when configured in DB binding.
        managed_prompt_use_latest = bool(binding_openai_prompt_use_latest)
        schema_wrapper = _load_free_batch_schema_wrapper()
        schema_body = _extract_schema_body(schema_wrapper)
        allowed_task_enum = _extract_allowed_task_enum(schema_body)
    managed_prompt_input = _build_managed_prompt_batch_input(normalized_questions)
    managed_prompt_cache_key = _render_prompt_cache_key(
        managed_prompt_cache_key_template,
        {
            "REQUEST_ID": runtime_request_id,
            "ATTEMPT_ID": runtime_attempt_id,
            "TIER": external_tier,
            "MODE": runtime_mode,
            "GRAPH_MODE": runtime_graph,
            "DOMAIN_MODE": runtime_domain,
            "PREFERRED_RESPONSE_LANGUAGE": runtime_lang,
            "MAX_QUESTIONS": max_questions_allowed,
            "QUESTION": str((normalized_questions[0] or {}).get("question_text") or "").strip() if normalized_questions else "",
            "QUESTIONS_JSON": questions_json_text_compact,
        },
    )
    if not managed_prompt_cache_key and managed_prompt_id:
        question_fingerprint = hashlib.sha256(questions_json_text_compact.encode("utf-8")).hexdigest()[:24]
        raw_fallback_cache_key = (
            f"solve:{managed_prompt_id}:{managed_prompt_version or 'latest'}:"
            f"{external_tier}:{runtime_mode}:{runtime_graph}:{runtime_domain}:{runtime_lang}:{question_fingerprint}:{runtime_request_id}"
        )
        if len(raw_fallback_cache_key) <= 64:
            managed_prompt_cache_key = raw_fallback_cache_key
        else:
            managed_prompt_cache_key = "pbk:" + hashlib.sha256(raw_fallback_cache_key.encode("utf-8")).hexdigest()[:48]
    if managed_prompt_id and managed_prompt_cache_key:
        # Enforce request-scoped cache key to prevent stale payload replay across requests.
        if runtime_request_id not in managed_prompt_cache_key:
            request_scoped_key = f"{managed_prompt_cache_key}:{runtime_request_id}"
            if len(request_scoped_key) <= 64:
                managed_prompt_cache_key = request_scoped_key
            else:
                managed_prompt_cache_key = "pbk:" + hashlib.sha256(request_scoped_key.encode("utf-8")).hexdigest()[:48]
    managed_prompt_variables = (
        _build_managed_prompt_variables(
            managed_prompt_variable_mapping,
            runtime_request_id=runtime_request_id,
            runtime_attempt_id=runtime_attempt_id,
            external_tier=external_tier,
            runtime_mode=runtime_mode,
            runtime_graph=runtime_graph,
            runtime_domain=runtime_domain,
            runtime_lang=runtime_lang,
            max_questions_allowed=max_questions_allowed,
            normalized_questions=normalized_questions,
        )
        if managed_prompt_variable_mapping
        else {}
    )
    if external_tier == "SHORT_STEPS":
        if managed_prompt_variable_mapping:
            managed_prompt_variables = _build_managed_prompt_variables(
                managed_prompt_variable_mapping,
                runtime_request_id=runtime_request_id,
                runtime_attempt_id=runtime_attempt_id,
                external_tier="FREE",
                runtime_mode=runtime_mode,
                runtime_graph=runtime_graph,
                runtime_domain=runtime_domain,
                runtime_lang=runtime_lang,
                max_questions_allowed=FREE_BATCH_MAX_QUESTIONS,
                normalized_questions=normalized_questions,
            )
        else:
            managed_prompt_variables = _build_free_batch_prompt_variables(
                runtime_request_id=runtime_request_id,
                runtime_attempt_id=runtime_attempt_id,
                runtime_mode=runtime_mode,
                runtime_graph=runtime_graph,
                runtime_domain=runtime_domain,
                runtime_lang=runtime_lang,
                normalized_questions=normalized_questions,
            )
    if isinstance(managed_prompt_variables, dict) and managed_prompt_variables:
        if not any(str(v).strip() for v in managed_prompt_variables.values() if v is not None):
            logger.warning(
                "managed_prompt_variables_empty_fallback_to_input request_id=%s attempt_id=%s",
                runtime_request_id,
                runtime_attempt_id,
            )
            managed_prompt_variables = {}

    def _is_effectively_empty_json_array(raw_text: str) -> bool:
        txt = str(raw_text or "").strip()
        if not txt:
            return True
        try:
            parsed = json.loads(txt)
            return isinstance(parsed, list) and len(parsed) == 0
        except Exception:
            return False

    # Hard preflight: never call provider without question payload inputs.
    if not first_question_text and _is_effectively_empty_json_array(questions_json_text_compact):
        raise BatchSolveError(
            "Missing prompt input: QUESTION/QUESTIONS_JSON_ARRAY are empty. Skipping provider call.",
            status_code=400,
            code="missing_mapped_input",
            details={"required": ["QUESTION", "QUESTIONS_JSON_ARRAY"]},
        )
    managed_prompt_enabled = _read_system_bool_config(
        session,
        "OPENAI_PROMPT_ID_ENABLED",
        default=_managed_prompt_feature_enabled(),
    )
    managed_prompt_active = (
        managed_prompt_enabled
        and managed_prompt_id != ""
        and (managed_prompt_use_latest or managed_prompt_version != "")
    )
    managed_prompt_runtime_active = managed_prompt_active
    if managed_prompt_runtime_active and external_tier == "STANDARD":
        mp_vars = managed_prompt_variables if isinstance(managed_prompt_variables, dict) else {}
        q_var = str(mp_vars.get("QUESTION") or mp_vars.get("question") or "").strip()
        qarr_var = str(
            mp_vars.get("QUESTIONS_JSON_ARRAY")
            or mp_vars.get("questions_json_array")
            or mp_vars.get("QUESTIONS_JSON")
            or mp_vars.get("questions_json")
            or ""
        ).strip()
        if not q_var and _is_effectively_empty_json_array(qarr_var):
            logger.warning(
                "managed_prompt_missing_required_inputs_fallback_to_binding_identity request_id=%s attempt_id=%s prompt_id=%s",
                runtime_request_id,
                runtime_attempt_id,
                managed_prompt_id,
            )
            managed_prompt_runtime_active = False

    # Production preflight guard: fail fast before provider call if mapped inputs are missing.
    preflight_payload: Dict[str, Any]
    if managed_prompt_runtime_active:
        mp_vars = managed_prompt_variables if isinstance(managed_prompt_variables, dict) else {}
        preflight_payload = {
            "QUESTION": mp_vars.get("QUESTION", mp_vars.get("question")),
            "QUESTIONS_JSON_ARRAY": mp_vars.get(
                "QUESTIONS_JSON_ARRAY",
                mp_vars.get("questions_json_array", mp_vars.get("QUESTIONS_JSON", mp_vars.get("questions_json"))),
            ),
        }
    else:
        preflight_payload = {
            "QUESTION": first_question_text,
            "QUESTIONS_JSON_ARRAY": normalized_questions,
        }
    _preflight_mapped_inputs(preflight_payload)

    if external_tier == "SHORT_STEPS" and managed_prompt_active:
        required_vars = {
            "REQUEST_ID",
            "ATTEMPT_ID",
            "TIER",
            "MAX_QUESTIONS",
            "MODE",
            "GRAPH_MODE",
            "DOMAIN_MODE",
            "PREFERRED_RESPONSE_LANGUAGE",
            "QUESTIONS_JSON",
        }
        if not isinstance(managed_prompt_variables, dict) or not managed_prompt_variables:
            raise BatchSolveError(
                "Managed prompt variables are required for FREE tier.",
                status_code=500,
                code="managed_prompt_variables_missing",
            )
        missing_vars = sorted(
            [
                key
                for key in required_vars
                if str((managed_prompt_variables or {}).get(key) or "").strip() == ""
            ]
        )
        if missing_vars:
            raise BatchSolveError(
                "Managed prompt variables missing required FREE runtime bindings.",
                status_code=500,
                code="managed_prompt_variables_missing",
                details={"missing": missing_vars},
            )
    schema_name_for_prompt = str(schema_wrapper.get("name") or _bget("output_schema_id") or "youask_math_openai_v1").strip()
    schema_version_for_prompt = _schema_version_for_prompt(schema_body, default="v1")
    max_steps_value = int(_bget("max_steps") or binding_features_prompt.get("max_steps") or _tier_default_max_steps(external_tier))
    step_style_value = str(binding_features_prompt.get("step_style") or _tier_default_step_style(external_tier)).strip()
    include_task_results_value = _to_bool_text(binding_features_prompt.get("include_task_results"), True)
    # Enforce task results for SHORT_STEPS so multi-task prompts stay traceable end-to-end.
    if external_tier == "SHORT_STEPS":
        include_task_results_value = "true"
    prefer_exact_value = _to_bool_text(binding_features_prompt.get("prefer_exact"), False)
    user_prompt_ctx = _resolve_user_prompt_context(
        session=session,
        user_id=user_id,
        trusted_context=trusted_context,
        binding_features=binding_features_prompt,
    )

    if external_tier == "FINAL" and local_sympy_enabled:
        reports_by_id = {str(rep.get("question_id") or ""): rep for rep in sympy_numpy_reports}
        local_items: List[Dict[str, Any]] = []
        local_fully_solved = True
        local_failure_reason: Optional[str] = None
        local_failure_question_id: Optional[str] = None
        local_only_mode = _is_final_local_only_enabled()
        for idx, q in enumerate(normalized_questions, start=1):
            qid = str(q.get("question_id") or "")
            qtext = str(q.get("question_text") or "")
            qtext_for_solver = _clean_question_text_for_local_solver(qtext)
            report = reports_by_id.get(qid) or {}
            if not bool(report.get("sympy_used")) or not bool(report.get("numpy_used")):
                local_fully_solved = False
                local_failure_reason = "sympy_numpy_gate_missing_usage"
                local_failure_question_id = qid
                if local_only_mode:
                    local_items.append(
                        _build_local_refusal_like_item(
                            question_id=qid,
                            question_index=idx,
                            mode=str(q.get("mode") or "SOLVE"),
                            original_text=qtext,
                            reason=local_failure_reason,
                        )
                    )
                    continue
                break
            if float(report.get("numpy_finite_ratio") or 0.0) <= 0.0:
                local_fully_solved = False
                local_failure_reason = "sympy_numpy_gate_non_finite"
                local_failure_question_id = qid
                if local_only_mode:
                    local_items.append(
                        _build_local_refusal_like_item(
                            question_id=qid,
                            question_index=idx,
                            mode=str(q.get("mode") or "SOLVE"),
                            original_text=qtext,
                            reason=local_failure_reason,
                        )
                    )
                    continue
                break
            solved = try_solve_final_with_sympy_numpy(qtext_for_solver)
            if not solved or float(solved.confidence) < 0.90:
                local_fully_solved = False
                local_failure_reason = "local_solver_no_high_confidence_result"
                local_failure_question_id = qid
                if local_only_mode:
                    local_items.append(
                        _build_local_refusal_like_item(
                            question_id=qid,
                            question_index=idx,
                            mode=str(q.get("mode") or "SOLVE"),
                            original_text=qtext,
                            reason=local_failure_reason,
                        )
                    )
                    continue
                break
            local_items.append(
                {
                    "question_id": qid,
                    "question_index": idx,
                    "mode": str(q.get("mode") or "SOLVE"),
                    "problem": {
                        "original_text": qtext,
                        "normalized_text": qtext,
                        "detected_tasks": _coerce_tasks_to_schema(
                            _normalize_local_tasks(solved.detected_tasks[:30] if solved.detected_tasks else ["solve"]),
                            allowed_task_enum,
                        ),
                        "extra": [],
                    },
                    "classification": {
                        "grade_band": "undergraduate_upper",
                        "domain": solved.classification_domain,
                        "topic": solved.classification_topic,
                        "difficulty": solved.classification_difficulty,
                    },
                    "steps": _local_single_step(solved.answer_latex),
                    "final_answer": {
                        "answer_text": solved.answer_text,
                        "answer_latex": solved.answer_latex,
                        "values": solved.values,
                        "units": None,
                        "kind": "solution",
                        "target": None,
                    },
                    "refusal": {"is_refusal": False, "reason": None, "safe_next_step": None},
                    "quality": {"confidence": float(solved.confidence), "common_mistakes": []},
                }
            )
        if (local_fully_solved and len(local_items) == len(normalized_questions)) or (
            local_only_mode and len(local_items) == len(normalized_questions)
        ):
            local_payload = _build_local_batch_payload(
                external_tier=external_tier,
                runtime_lang=runtime_lang,
                runtime_request_id=runtime_request_id,
                runtime_attempt_id=runtime_attempt_id,
                runtime_allow_auto_split=runtime_allow_auto_split,
                max_questions_allowed=max_questions_allowed,
                runtime_max_tasks_per_question=runtime_max_tasks_per_question,
                solved_items=local_items,
            )
            validator = Draft202012Validator(schema_body)
            errors = sorted(validator.iter_errors(local_payload), key=lambda e: e.path)
            if not errors:
                _post_assertions(
                    local_payload,
                    schema_body=schema_body,
                    questions=normalized_questions,
                    tier=external_tier,
                )
                telemetry = {
                    "request_id": runtime_request_id,
                    "attempt_id": runtime_attempt_id,
                    "tier": external_tier,
                    "questions_count": len(normalized_questions),
                    "allow_auto_split_effective": runtime_allow_auto_split,
                    "model": "sympy-numpy-local",
                    "provider": "local",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms_openai": 0,
                    "latency_ms_total": int((time.perf_counter() - started) * 1000),
                    "schema_name": str(schema_wrapper.get("name") or _bget("output_schema_id") or external_tier),
                    "schema_version": schema_version_for_prompt,
                    "model_bound": "sympy-numpy-local",
                    "temperature_bound": 0,
                    "top_p_bound": 1,
                    "timeout_ms_bound": 0,
                    "max_questions_allowed_bound": max_questions_allowed,
                    "prompt_binding_id": binding_id,
                    "global_system_prompt_id": _bget("global_system_prompt_id"),
                    "developer_prompt_id": _bget("developer_prompt_id"),
                    "output_schema_id": _bget("output_schema_id"),
                    "openai_calls_count": 0,
                    "repair_attempted": False,
                    "schema_valid": True,
                    "sympy_numpy_reports": sympy_numpy_reports,
                    "sympy_used": True,
                    "numpy_used": True,
                    "final_local_short_circuit": True,
                    "partial_local_refusals": bool(not local_fully_solved and local_only_mode),
                }
                return local_payload, telemetry
            logger.warning(
                "final_local_short_circuit_schema_invalid request_id=%s attempt_id=%s errors=%s",
                runtime_request_id,
                runtime_attempt_id,
                [
                    {
                        "path": "$" + "".join([f"[{repr(p)}]" for p in err.path]),
                        "message": err.message,
                    }
                    for err in errors[:10]
                ],
            )
            local_failure_reason = "local_payload_schema_invalid"

        if local_only_mode:
            raise BatchSolveError(
                "FINAL local-only mode is enabled and local SymPy/NumPy solve was not complete.",
                status_code=422,
                code="final_local_only_unsatisfied",
                details={
                    "tier": external_tier,
                    "reason": local_failure_reason or "unknown",
                    "question_id": local_failure_question_id,
                    "items_solved_locally": len(local_items),
                    "items_total": len(normalized_questions),
                    "openai_fallback_blocked": True,
                },
            )

    developer_prompt = _replace_prompt_tokens(
        developer_prompt_template,
        {
            "SCHEMA_NAME": schema_name_for_prompt,
            "SCHEMA_VERSION": schema_version_for_prompt,
            "REQUEST_ID": runtime_request_id,
            "ATTEMPT_ID": runtime_attempt_id,
            "TIER": external_tier,
            "MAX_QUESTIONS": str(max_questions_allowed),
            "MAX_QUESTIONS_ALLOWED": str(max_questions_allowed),
            "MODE": runtime_mode,
            "GRAPH_MODE": runtime_graph,
            "DOMAIN_MODE": runtime_domain,
            "PREFERRED_RESPONSE_LANGUAGE": runtime_lang,
            "MAX_STEPS": str(max_steps_value),
            "STEP_STYLE": step_style_value,
            "INCLUDE_TASK_RESULTS": include_task_results_value,
            "PREFER_EXACT": prefer_exact_value,
            "QUESTION": str((normalized_questions[0] or {}).get("question_text") or "").strip() if normalized_questions else "",
            "QUESTIONS_JSON": questions_json_text_compact,
            "QUESTIONS_JSON_ARRAY": questions_json_text_compact,
            "ALLOW_AUTO_SPLIT": "true" if runtime_allow_auto_split else "false",
            "allow_auto_split": "true" if runtime_allow_auto_split else "false",
            "MAX_TASKS_PER_QUESTION": str(runtime_max_tasks_per_question),
            "max_tasks_per_question": str(runtime_max_tasks_per_question),
            **user_prompt_ctx,
        },
    )
    developer_prompt = _enforce_authoritative_dev_prompt_lines(
        developer_prompt,
        {
            "SCHEMA_NAME": schema_name_for_prompt,
            "SCHEMA_VERSION": schema_version_for_prompt,
            "TIER": external_tier,
            "REQUEST_ID": runtime_request_id,
            "ATTEMPT_ID": runtime_attempt_id,
            "PREFERRED_RESPONSE_LANGUAGE": runtime_lang,
            "MAX_QUESTIONS_ALLOWED": str(max_questions_allowed),
            "MODE": runtime_mode,
            "DOMAIN_MODE": runtime_domain,
            "GRAPH_MODE": runtime_graph,
            "MAX_STEPS": str(max_steps_value),
            "STEP_STYLE": step_style_value,
            "INCLUDE_TASK_RESULTS": include_task_results_value,
            "PREFER_EXACT": prefer_exact_value,
            "QUESTION": str((normalized_questions[0] or {}).get("question_text") or "").strip() if normalized_questions else "",
            "QUESTIONS_JSON_ARRAY": questions_json_text_compact,
            "COUNTRY": user_prompt_ctx.get("COUNTRY", "unknown"),
            "REGION": user_prompt_ctx.get("REGION", "unknown"),
            "CURRICULUM": user_prompt_ctx.get("CURRICULUM", "unknown"),
            "GRADE_LEVEL": user_prompt_ctx.get("GRADE_LEVEL", "unknown"),
            "COURSE": user_prompt_ctx.get("COURSE", "unknown"),
            "NOTATION_PROFILE": user_prompt_ctx.get("NOTATION_PROFILE", "decimal_dot,radians_default"),
        },
    )
    unresolved_placeholders = sorted(set(PLACEHOLDER_TOKEN_RE.findall(developer_prompt)))
    if unresolved_placeholders:
        raise BatchSolveError(
            "Developer prompt contains unresolved placeholders.",
            status_code=500,
            code="developer_prompt_unresolved_placeholders",
            details={
                "placeholders": unresolved_placeholders,
                "binding_id": binding_id,
                "developer_prompt_id": _bget("developer_prompt_id"),
            },
        )

    user_runtime_payload: Dict[str, Any] = {
        "request_id": runtime_request_id,
        "attempt_id": runtime_attempt_id,
        "tier": external_tier,
        "questions_count": len(normalized_questions),
    }
    first_question_text_for_user = (
        str((normalized_questions[0] or {}).get("question_text") or "").strip()
        if normalized_questions
        else ""
    )
    if first_question_text_for_user:
        user_runtime_payload["QUESTION"] = first_question_text_for_user
    if normalized_questions:
        # Authoritative fallback payload for identity-bound prompts.
        # Only include when present; do not send empty arrays.
        user_runtime_payload["QUESTIONS_JSON_ARRAY"] = normalized_questions

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "developer", "content": developer_prompt},
        {
            "role": "user",
            "content": json.dumps(user_runtime_payload, ensure_ascii=False),
        },
    ]

    llm_manager = get_llm_manager()
    primary_provider = llm_manager.get_active_provider(session)
    binding_provider = str(_bget("provider") or "").strip().lower()
    provider_candidates: List[str] = [primary_provider]
    if external_tier == "SHORT_STEPS":
        # FREE batch solve v2 is pinned to OpenAI managed prompt.
        provider_candidates = ["openai"]
    ollama_first_tier = external_tier in {"SHORT_STEPS", "FINAL"}
    if binding_provider in {"openai", "ollama"}:
        provider_candidates = [binding_provider]
        if binding_provider == "ollama" and _allow_openai_fallback_for_ollama_first_tiers():
            provider_candidates.append("openai")
    elif ollama_first_tier:
        provider_candidates = ["ollama"]
        if _allow_openai_fallback_for_ollama_first_tiers():
            provider_candidates.append("openai")
    elif (not local_sympy_enabled):
        provider_candidates = [primary_provider]
    # Preserve order and remove accidental duplicates.
    seen: set[str] = set()
    provider_candidates = [p for p in provider_candidates if not (p in seen or seen.add(p))]
    # Hard-stop on first provider attempt: no retry/re-attempt fallback chain.
    provider_candidates = provider_candidates[:1]
    provider_name = provider_candidates[0]
    client = llm_manager.get_client(provider_name)
    binding_features = _bget("features") if isinstance(_bget("features"), dict) else {}
    model_name = (model or str(binding_features.get("model") or "")).strip()
    ollama_model_name = get_configured_ollama_model(external_tier) if "ollama" in provider_candidates else ""

    def _ollama_direct_text_mode_active() -> bool:
        return provider_name == "ollama" and external_tier in {"SHORT_STEPS", "FINAL"}
    if provider_name == "openai" and not model_name:
        raise BatchSolveError(
            "Binding is missing required model setting.",
            status_code=500,
            code="prompt_binding_invalid",
            details={"tier": prompt_tier.value, "binding_id": binding_id},
        )
    bound_max_output_tokens = int(_bget("max_output_tokens") or 0)
    if bound_max_output_tokens < 1:
        # Keep runtime resilient for legacy bindings missing this field.
        # STANDARD defaults to 20000, others to 5000.
        bound_max_output_tokens = 20000 if external_tier == "STANDARD" else 5000
    max_tokens = int(max_output_tokens) if max_output_tokens is not None else bound_max_output_tokens
    bound_temperature = float(_bget("temperature") or 0.0)
    bound_top_p = float(_bget("top_p") or 1.0)
    bound_timeout_ms = int(_bget("timeout_ms") or 60000)
    provider_raw_text: str = ""
    provider_raw_payload: Any = None
    ollama_prompt_dump_files: List[str] = []

    async def _call_provider(
        *,
        request_id_suffix: str = "",
        force_json_only: bool = False,
        repair_context: Optional[str] = None,
    ):
        call_messages = messages
        if provider_name == "ollama" and not force_json_only:
            if _ollama_direct_text_mode_active():
                tier_system_prompt = (
                    "You are a math solver.\n\n"
                    "OUTPUT FORMAT (must follow exactly, plain text only):\n"
                    "BEGIN_SOLUTION\n"
                    "BEGIN_STEPS\n"
                    "1) <short step, may include LaTeX using \\( \\) or \\[ \\]>\n"
                    "2) <short step>\n"
                    "3) <short step>\n"
                    "END_STEPS\n"
                    "BEGIN_FINAL\n"
                    "<final results only; if multiple parts, label (a), (b), ...>\n"
                    "END_FINAL\n"
                    "END_SOLUTION\n\n"
                    "Rules:\n"
                    "- No markdown headings, no code fences, no JSON.\n"
                    "- Keep steps concise (max 6).\n"
                    "- Put all final results in BEGIN_FINAL only.\n"
                    "- If you cannot solve, write in BEGIN_FINAL: UNSOLVABLE: <one-line reason>."
                )
                if len(normalized_questions) == 1:
                    user_question = str((normalized_questions[0] or {}).get("question_text") or "").strip()
                else:
                    user_question = "\n".join(
                        [
                            f"{idx}. {str((q or {}).get('question_text') or '').strip()}"
                            for idx, q in enumerate(normalized_questions, start=1)
                        ]
                    ).strip()
                direct_user_prompt = (
                    "Provide the final computed results clearly. "
                    "If multiple parts are requested, label them (a), (b), etc.\n\n"
                    f"Question:\n{user_question}"
                )
                call_messages = [
                    {"role": "system", "content": tier_system_prompt},
                    {"role": "user", "content": direct_user_prompt},
                ]
                tier_developer_prompt = ""
            else:
                tier_system_prompt = (
                    "FINAL tier policy: solve the problem and return only concrete final answers in schema-valid JSON. "
                    "Do not include derivations, intermediate reasoning, or commentary. "
                    "Never output placeholders, templates, or symbolic markers such as "
                    "{formatted answer}, {Value: ...}, ____ , TBD, or similar."
                    if external_tier == "FINAL"
                    else (
                        "Solve this question."
                        if external_tier == "SHORT_STEPS"
                        else (
                            "Return schema-valid JSON only, with concrete computed values. "
                            "Do not output placeholders or templates."
                        )
                    )
                )
                tier_developer_prompt = developer_prompt
                call_messages = [
                    {"role": "system", "content": tier_system_prompt},
                    {"role": "developer", "content": tier_developer_prompt},
                    messages[-1],
                ]
        if force_json_only:
            strict_system = (
                "Return only one valid JSON object that matches the provided schema. "
                "Do not include markdown fences, prose, explanations, or trailing text."
            )
            strict_dev = (
                developer_prompt
                + "\n\nSTRICT OUTPUT RULES:\n"
                + "- Output must be valid JSON object.\n"
                + "- No markdown code fences.\n"
                + "- No extra keys outside schema."
            )
            call_messages = [
                {"role": "system", "content": strict_system},
                {"role": "developer", "content": strict_dev},
                messages[-1],
            ]
            if repair_context:
                call_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Previous output was invalid. Repair it into schema-valid JSON only.\n"
                            f"INVALID_CONTEXT:\n{repair_context}"
                        ),
                    }
                )

        # Local Ollama inference can exceed default binding timeouts on long JSON tasks.
        effective_timeout_ms = bound_timeout_ms
        if provider_name == "ollama":
            try:
                min_ollama_timeout_ms = int((os.environ.get("OLLAMA_MIN_REQUEST_TIMEOUT_MS") or "180000").strip())
            except Exception:
                min_ollama_timeout_ms = 180000
            effective_timeout_ms = max(effective_timeout_ms, max(1000, min_ollama_timeout_ms))
            dump_path = _dump_ollama_runtime_prompt_txt(
                runtime_request_id=runtime_request_id,
                runtime_attempt_id=runtime_attempt_id,
                tier=external_tier,
                model_name=(ollama_model_name or model_name or "").strip(),
                request_id_suffix=request_id_suffix,
                force_json_only=force_json_only,
                call_messages=call_messages,
            )
            if dump_path:
                ollama_prompt_dump_files.append(dump_path)

        return await client.generate(
            messages=call_messages,
            system_prompt=None,
            prompt=None,
            json_schema=None if _ollama_direct_text_mode_active() else schema_wrapper,
            max_tokens=max_tokens,
            temperature=bound_temperature,
            top_p=bound_top_p,
            stream=False,
            request_id=f"{runtime_request_id}{request_id_suffix}",
            timeout_ms=effective_timeout_ms,
            model=model_name if provider_name == "openai" else ollama_model_name,
            verbosity="low",
            reasoning_effort=(str(binding_features.get("reasoning_effort") or "").strip() or "minimal"),
            managed_prompt_id=(managed_prompt_id if (provider_name == "openai" and managed_prompt_runtime_active) else None),
            managed_prompt_version=(managed_prompt_version if (provider_name == "openai" and managed_prompt_runtime_active) else None),
            managed_prompt_use_latest=(managed_prompt_use_latest if (provider_name == "openai" and managed_prompt_runtime_active) else False),
            managed_prompt_variables=(managed_prompt_variables if (provider_name == "openai" and managed_prompt_runtime_active and managed_prompt_variables) else None),
            managed_prompt_input=(managed_prompt_input if (provider_name == "openai" and managed_prompt_runtime_active) else None),
            prompt_cache_key=(managed_prompt_cache_key if (provider_name == "openai" and managed_prompt_runtime_active and managed_prompt_cache_key) else None),
            prompt_cache_retention=(managed_prompt_cache_retention if (provider_name == "openai" and managed_prompt_runtime_active and managed_prompt_cache_retention) else None),
            require_managed_prompt_variables=bool(provider_name == "openai" and managed_prompt_runtime_active and external_tier == "STANDARD"),
        )

    async def _parse_validate_response(
        initial_response: Any,
        *,
        allow_repair_retry: bool = True,
    ) -> Tuple[Dict[str, Any], Any, bool]:
        nonlocal provider_raw_text, provider_raw_payload
        relaxed_short_final = provider_name == "ollama" and external_tier in {"SHORT_STEPS", "FINAL"}

        def _capture_provider_raw(resp: Any) -> None:
            nonlocal provider_raw_text, provider_raw_payload
            content = getattr(resp, "content", None)
            provider_raw_text = content if isinstance(content, str) else ("" if content is None else str(content))
            provider_raw_payload = getattr(resp, "payload", None)

        response_local = initial_response
        _capture_provider_raw(response_local)
        validator = Draft202012Validator(schema_body)
        repair_attempted_local = False

        raw_local = (response_local.content or "").strip()
        if not raw_local:
            raise BatchSolveError(
                "Empty provider response content.",
                status_code=502,
                code=f"empty_{provider_name}_response",
                details={
                    "provider_status": response_local.status,
                    "provider_payload": response_local.payload,
                },
            )

        if _ollama_direct_text_mode_active():
            def _extract_payload_from_text(src_text: str) -> Dict[str, Any]:
                return _extract_ollama_text_payload(
                    raw_text=src_text,
                    questions=normalized_questions,
                    tier=external_tier,
                    runtime_request_id=runtime_request_id,
                    runtime_attempt_id=runtime_attempt_id,
                    runtime_lang=runtime_lang,
                    runtime_allow_auto_split=runtime_allow_auto_split,
                    max_questions_allowed=max_questions_allowed,
                    runtime_max_tasks_per_question=runtime_max_tasks_per_question,
                )

            extracted_payload = _extract_payload_from_text(raw_local)

            extracted_errors = [] if relaxed_short_final else sorted(
                validator.iter_errors(extracted_payload), key=lambda e: e.path
            )
            if extracted_errors:
                raise BatchSolveError(
                    "Extracted payload failed schema validation.",
                    status_code=502,
                    code="schema_validation_failed",
                    details={
                        "errors": [
                            {"path": "$" + "".join([f"[{repr(p)}]" for p in err.path]), "message": err.message}
                            for err in extracted_errors[:30]
                        ],
                        "raw_preview": _preview_text(raw_local),
                    },
            )
            _post_assertions(
                extracted_payload,
                schema_body=schema_body,
                questions=normalized_questions,
                tier=external_tier,
            )
            return extracted_payload, response_local, False

        payload_local: Optional[Dict[str, Any]] = None
        parse_error_local: Optional[Exception] = None
        try:
            payload_local = json.loads(raw_local)
        except Exception as exc:
            parse_error_local = exc
            candidate = _extract_json_candidate(raw_local)
            if candidate:
                try:
                    payload_local = json.loads(candidate)
                    parse_error_local = None
                except Exception as inner_exc:
                    parse_error_local = inner_exc

        if payload_local is None:
            if provider_name == "ollama" and _text_extractor_enabled():
                extracted_payload = _extract_ollama_text_payload(
                    raw_text=raw_local,
                    questions=normalized_questions,
                    tier=external_tier,
                    runtime_request_id=runtime_request_id,
                    runtime_attempt_id=runtime_attempt_id,
                    runtime_lang=runtime_lang,
                    runtime_allow_auto_split=runtime_allow_auto_split,
                    max_questions_allowed=max_questions_allowed,
                    runtime_max_tasks_per_question=runtime_max_tasks_per_question,
                )
                extracted_errors = [] if relaxed_short_final else sorted(
                    validator.iter_errors(extracted_payload), key=lambda e: e.path
                )
                if not extracted_errors:
                    _post_assertions(
                        extracted_payload,
                        schema_body=schema_body,
                        questions=normalized_questions,
                        tier=external_tier,
                    )
                    return extracted_payload, response_local, False
                if relaxed_short_final:
                    return extracted_payload, response_local, False
            raise BatchSolveError(
                "Provider returned invalid JSON payload.",
                status_code=502,
                code=f"invalid_{provider_name}_json",
                details={
                    "error": str(parse_error_local) if parse_error_local else "unknown_parse_error",
                    "provider_status": response_local.status,
                    "raw_preview": _preview_text(raw_local),
                },
            )

        errors_local = [] if relaxed_short_final else sorted(
            validator.iter_errors(payload_local), key=lambda e: e.path
        )
        if errors_local:
            if provider_name == "ollama" and _text_extractor_enabled():
                extracted_payload = _extract_ollama_text_payload(
                    raw_text=raw_local,
                    questions=normalized_questions,
                    tier=external_tier,
                    runtime_request_id=runtime_request_id,
                    runtime_attempt_id=runtime_attempt_id,
                    runtime_lang=runtime_lang,
                    runtime_allow_auto_split=runtime_allow_auto_split,
                    max_questions_allowed=max_questions_allowed,
                    runtime_max_tasks_per_question=runtime_max_tasks_per_question,
                )
                extracted_errors = [] if relaxed_short_final else sorted(
                    validator.iter_errors(extracted_payload), key=lambda e: e.path
                )
                if not extracted_errors:
                    _post_assertions(
                        extracted_payload,
                        schema_body=schema_body,
                        questions=normalized_questions,
                        tier=external_tier,
                    )
                    return extracted_payload, response_local, True
                if relaxed_short_final:
                    return extracted_payload, response_local, True
            raise BatchSolveError(
                "Schema validation failed for provider payload.",
                status_code=502,
                code="schema_validation_failed",
                details={
                    "errors": [
                        {"path": "$" + "".join([f"[{repr(p)}]" for p in err.path]), "message": err.message}
                        for err in errors_local[:30]
                    ]
                },
            )
        try:
            _post_assertions(
                payload_local,
                schema_body=schema_body,
                questions=normalized_questions,
                tier=external_tier,
            )
        except BatchSolveError as post_exc:
            if provider_name == "ollama" and _text_extractor_enabled():
                extracted_payload = _extract_ollama_text_payload(
                    raw_text=raw_local,
                    questions=normalized_questions,
                    tier=external_tier,
                    runtime_request_id=runtime_request_id,
                    runtime_attempt_id=runtime_attempt_id,
                    runtime_lang=runtime_lang,
                    runtime_allow_auto_split=runtime_allow_auto_split,
                    max_questions_allowed=max_questions_allowed,
                    runtime_max_tasks_per_question=runtime_max_tasks_per_question,
                )
                extracted_errors = sorted(validator.iter_errors(extracted_payload), key=lambda e: e.path)
                if not extracted_errors:
                    _post_assertions(
                        extracted_payload,
                        schema_body=schema_body,
                        questions=normalized_questions,
                        tier=external_tier,
                    )
                    return extracted_payload, response_local, False
            if allow_repair_retry and provider_name in {"openai", "ollama"}:
                repair_attempted_local = True
                repair_context = (
                    f"post_assert_error: {str(post_exc)}\n"
                    f"expected_items_count: {len(normalized_questions)}\n"
                    f"raw_response:\n{raw_local[:12000]}"
                )
                logger.warning(
                    "batch_post_assert_repair_retry request_id=%s attempt_id=%s provider=%s error=%s",
                    runtime_request_id,
                    runtime_attempt_id,
                    provider_name,
                    str(post_exc),
                )
                repaired_response = await _call_provider(
                    request_id_suffix="-repair",
                    force_json_only=True,
                    repair_context=repair_context,
                )
                repaired_payload, repaired_response_obj, _ = await _parse_validate_response(
                    repaired_response,
                    allow_repair_retry=False,
                )
                return repaired_payload, repaired_response_obj, True
            raise
        return payload_local, response_local, repair_attempted_local

    selected_provider = provider_name
    attempted_providers: List[str] = []
    response = None
    payload: Optional[Dict[str, Any]] = None
    repair_attempted = False
    last_provider_error: Optional[BatchSolveError] = None
    for idx, candidate in enumerate(provider_candidates):
        provider_name = candidate
        selected_provider = candidate
        attempted_providers.append(candidate)
        client = llm_manager.get_client(provider_name)
        try:
            response = await _call_provider()
            if bool((trusted_context or {}).get("capture_openai_raw_only")):
                _capture_openai_raw_and_stop(
                    runtime_request_id=runtime_request_id,
                    provider_response=response,
                )
            payload, response, repair_attempted = await _parse_validate_response(response)
            last_provider_error = None
            break
        except (LLMProviderError, BatchSolveError) as exc:
            # Managed prompt can be disabled/deleted on OpenAI side while DB binding still references it.
            # In that case, retry once using the binding's DB prompt text path (no managed prompt id).
            if (
                isinstance(exc, LLMProviderError)
                and provider_name == "openai"
                and managed_prompt_runtime_active
                and _is_managed_prompt_unavailable_error(exc)
            ):
                logger.warning(
                    "managed_prompt_unavailable_fallback_to_binding_identity request_id=%s attempt_id=%s tier=%s prompt_id=%s",
                    runtime_request_id,
                    runtime_attempt_id,
                    external_tier,
                    managed_prompt_id,
                )
                managed_prompt_runtime_active = False
                try:
                    response = await _call_provider(request_id_suffix="-binding-fallback")
                    if bool((trusted_context or {}).get("capture_openai_raw_only")):
                        _capture_openai_raw_and_stop(
                            runtime_request_id=runtime_request_id,
                            provider_response=response,
                        )
                    payload, response, repair_attempted = await _parse_validate_response(response)
                    last_provider_error = None
                    break
                except (LLMProviderError, BatchSolveError) as retry_exc:
                    exc = retry_exc

            if isinstance(exc, LLMProviderError):
                logger.exception(
                    "Batch solve provider request failed",
                    extra={
                        "request_id": runtime_request_id,
                        "attempt_id": runtime_attempt_id,
                        "tier": external_tier,
                        "provider": provider_name,
                        "model": model_name,
                        "provider_details": getattr(exc, "details", None),
                    },
                )
                last_provider_error = BatchSolveError(
                    "Provider call failed during batch solve.",
                    status_code=502,
                    code=f"{provider_name}_request_failed",
                    details={
                        "message": str(exc),
                        "provider_details": getattr(exc, "details", None),
                        "provider": provider_name,
                    },
                )
            else:
                last_provider_error = exc
            raise last_provider_error
    if response is None or payload is None:
        if last_provider_error is not None:
            raise last_provider_error
        raise BatchSolveError(
            "No provider response available.",
            status_code=502,
            code="provider_unavailable",
            details={"providers_tried": provider_candidates},
        )

    telemetry = {
        "request_id": runtime_request_id,
        "attempt_id": runtime_attempt_id,
        "tier": external_tier,
        "questions_count": len(normalized_questions),
        "allow_auto_split_effective": runtime_allow_auto_split,
        "model": response.model,
        "provider": response.provider,
        "input_tokens": int((response.usage or {}).get("input") or 0),
        "output_tokens": int((response.usage or {}).get("output") or 0),
        "total_tokens": int((response.usage or {}).get("total") or 0),
        "latency_ms_openai": int(response.latency_ms or 0),
        "latency_ms_total": int((time.perf_counter() - started) * 1000),
        "schema_name": str(schema_wrapper.get("name") or _bget("output_schema_id") or external_tier),
        "schema_version": schema_version_for_prompt,
        "model_bound": model_name if selected_provider == "openai" else str(response.model or selected_provider),
        "temperature_bound": bound_temperature,
        "top_p_bound": bound_top_p,
        "timeout_ms_bound": bound_timeout_ms,
        "max_questions_allowed_bound": max_questions_allowed,
        "prompt_binding_id": binding_id,
        "global_system_prompt_id": _bget("global_system_prompt_id"),
        "developer_prompt_id": _bget("developer_prompt_id"),
        "output_schema_id": _bget("output_schema_id"),
        "openai_calls_count": 1 if response.provider == "openai" else 0,
        "openai_prompt_id": (response.payload or {}).get("openai_prompt_id"),
        "openai_prompt_version": (response.payload or {}).get("openai_prompt_version"),
        "openai_prompt_use_latest": (response.payload or {}).get("openai_prompt_use_latest"),
        "openai_prompt_variables_used": (response.payload or {}).get("openai_prompt_variables_used"),
        "openai_prompt_cache_key": (response.payload or {}).get("openai_prompt_cache_key"),
        "openai_prompt_cache_retention": (response.payload or {}).get("openai_prompt_cache_retention"),
        "repair_attempted": repair_attempted,
        "schema_valid": True,
        "sympy_numpy_reports": sympy_numpy_reports,
        "sympy_used": bool(local_sympy_enabled),
        "numpy_used": bool(local_sympy_enabled),
        "local_sympy_numpy_enabled": bool(local_sympy_enabled),
        "provider_chain": provider_candidates,
        "providers_attempted": attempted_providers,
        "ollama_attempted": "ollama" in attempted_providers,
        "ollama_fallback_to_openai": (
            "ollama" in attempted_providers
            and "openai" in attempted_providers
            and (attempted_providers.index("openai") > attempted_providers.index("ollama"))
            and response.provider == "openai"
        ),
        # Preserve exact provider text for persistence/debug (especially SHORT_STEPS via Ollama).
        "provider_raw_text": provider_raw_text,
        "provider_raw_payload": provider_raw_payload,
        "ollama_prompt_dump_files": ollama_prompt_dump_files,
    }
    return payload, telemetry
