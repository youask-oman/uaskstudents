from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator
from sqlmodel import Session, select

from app.models import (
    JsonSchemaEntry,
    PromptTemplateEntry,
    SolverOutputAttempt,
    SystemConfig,
    User,
)
from app.services.plot_integration import apply_graph_mode_override, format_plot_for_response, maybe_generate_plot
from app.services.runtime_audit import emit_runtime_audit
from app.services.solve.cache_service import cache_service
from app.services.solve.canonicalization_service import canonicalization_service
from app.services.solve.verification_gate import verify_solve_result
from app.services.solver_v3 import get_solver_v3
from app.utils.schema_deref import deref_json_schema, validate_no_refs
from app.utils.structured_output_builder import build_openai_structured_output


class SolveV2PipelineError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 503,
        retryable: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


@dataclass
class SolveV2Config:
    system_prompt_id: str
    orchestrator_prompt_id: str
    narrator_prompt_id: str
    plot_spec_prompt_id: str
    repair_prompt_id: str
    clarify_prompt_id: str
    superset_schema_id: str
    llm_min_schema_id: str
    clarify_schema_id: str
    repair_schema_id: str
    tier_policy: Dict[str, Dict[str, Any]]
    narrator_enabled: bool
    parse_timeout_ms: int
    openai_timeout_ms: int
    verify_timeout_ms: int
    plot_timeout_ms: int


DEFAULT_TIER_POLICY = {
    "FREE": {"min_steps": 0, "max_steps": 4, "max_tokens": 2000, "narrator": False},
    "FINAL": {"min_steps": 0, "max_steps": 2, "max_tokens": 2500, "narrator": False},
    "STANDARD": {"min_steps": 6, "max_steps": 12, "max_tokens": 5000, "narrator": True},
    "RESEARCH": {"min_steps": 6, "max_steps": 20, "max_tokens": 8000, "narrator": True},
}


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _system_config_value(session: Session, key: str, default: str) -> str:
    row = session.get(SystemConfig, key)
    if not row or row.value is None:
        return default
    value = str(row.value).strip()
    return value if value else default


def load_solve_v2_config(session: Session) -> SolveV2Config:
    tier_policy_raw = _system_config_value(session, "SOLVE_TIER_POLICY_JSON", json.dumps(DEFAULT_TIER_POLICY))
    try:
        tier_policy = json.loads(tier_policy_raw)
        if not isinstance(tier_policy, dict):
            tier_policy = copy.deepcopy(DEFAULT_TIER_POLICY)
    except Exception:
        tier_policy = copy.deepcopy(DEFAULT_TIER_POLICY)

    return SolveV2Config(
        system_prompt_id=_system_config_value(session, "SOLVE_SYSTEM_PROMPT_ID", "global_system_prompt_v2_compact.txt"),
        orchestrator_prompt_id=_system_config_value(
            session,
            "SOLVE_ORCHESTRATOR_DEV_PROMPT_ID",
            "solve_orchestrator_developer_v2_compact.txt",
        ),
        narrator_prompt_id=_system_config_value(session, "SOLVE_NARRATOR_PROMPT_ID", "solve_explain_narrator_v2_compact.txt"),
        plot_spec_prompt_id=_system_config_value(session, "SOLVE_PLOT_SPEC_PROMPT_ID", "solve_plot_spec_v2_compact.txt"),
        repair_prompt_id=_system_config_value(session, "SOLVE_REPAIR_PROMPT_ID", "solve_repair_verification_patch_v1.txt"),
        clarify_prompt_id=_system_config_value(
            session,
            "SOLVE_CLARIFY_PROMPT_ID",
            "solve_clarification_patch_v1.txt",
        ),
        superset_schema_id=_system_config_value(session, "SOLVE_SCHEMA_ID", "solve_superset_v2.schema.json"),
        llm_min_schema_id=_system_config_value(session, "SOLVE_LLM_MIN_SCHEMA_ID", "solve_llm_min_v2.schema.json"),
        clarify_schema_id=_system_config_value(session, "SOLVE_CLARIFY_SCHEMA_ID", "solve_clarification_patch_v1.schema.json"),
        repair_schema_id=_system_config_value(session, "SOLVE_REPAIR_SCHEMA_ID", "solve_repair_patch_v1.schema.json"),
        tier_policy=tier_policy,
        narrator_enabled=_truthy(_system_config_value(session, "SOLVE_NARRATOR_ENABLED", "false")),
        parse_timeout_ms=int(_system_config_value(session, "SOLVE_TIMEOUT_PARSE_MS", "1500")),
        openai_timeout_ms=int(_system_config_value(session, "SOLVE_TIMEOUT_OPENAI_MS", "90000")),
        verify_timeout_ms=int(_system_config_value(session, "SOLVE_TIMEOUT_VERIFY_MS", "3000")),
        plot_timeout_ms=int(_system_config_value(session, "SOLVE_TIMEOUT_PLOT_MS", "5000")),
    )


def _latest_active_prompt(session: Session, prompt_id: str) -> PromptTemplateEntry:
    row = session.exec(
        select(PromptTemplateEntry)
        .where(PromptTemplateEntry.prompt_id == prompt_id)
        .where(PromptTemplateEntry.is_active == True)
        .order_by(PromptTemplateEntry.version.desc(), PromptTemplateEntry.id.desc())
    ).first()
    if row:
        return row
    raise SolveV2PipelineError(
        code="PROMPT_NOT_FOUND",
        message=f"Prompt not found: {prompt_id}",
        status_code=503,
        details={"prompt_id": prompt_id},
    )


def _latest_active_schema(session: Session, schema_id: str) -> JsonSchemaEntry:
    row = session.exec(
        select(JsonSchemaEntry)
        .where(JsonSchemaEntry.schema_id == schema_id)
        .where(JsonSchemaEntry.is_active == True)
        .order_by(JsonSchemaEntry.version.desc(), JsonSchemaEntry.id.desc())
    ).first()
    if row:
        return row
    raise SolveV2PipelineError(
        code="SCHEMA_NOT_FOUND",
        message=f"Schema not found: {schema_id}",
        status_code=503,
        details={"schema_id": schema_id},
    )


def _extract_schema_object(schema_entry: JsonSchemaEntry) -> Dict[str, Any]:
    content = schema_entry.content if isinstance(schema_entry.content, dict) else {}
    schema = content.get("schema") if isinstance(content.get("schema"), dict) else content
    return schema if isinstance(schema, dict) else {}


def _extract_schema_name(schema_entry: JsonSchemaEntry) -> str:
    content = schema_entry.content if isinstance(schema_entry.content, dict) else {}
    name = content.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return str(schema_entry.schema_id or "solve_superset_v2").replace(".schema.json", "")


def _tier_to_v2(raw_tier: Optional[str]) -> str:
    value = str(raw_tier or "").strip().lower()
    if value in {"research", "enterprise"}:
        return "RESEARCH"
    if value in {"standard", "pro", "premium"}:
        return "STANDARD"
    if value in {"short", "final", "final_only"}:
        return "FINAL"
    return "FREE"


def _mode_to_v2(problem_text: str) -> str:
    text = (problem_text or "").lower()
    if "=" in text:
        return "SOLVE"
    if "integral" in text or "integrate" in text:
        return "INTEGRAL"
    if "derivative" in text or "differentiate" in text:
        return "DERIVATIVE"
    if "plot" in text or "graph" in text:
        return "PLOT"
    return "OTHER"


def _detected_tasks(problem_text: str, graph_mode: str) -> List[str]:
    tasks: List[str] = []
    text = (problem_text or "").lower()
    if "=" in text:
        tasks.append("equation")
    if "plot" in text or "graph" in text or graph_mode in {"on", "auto"}:
        tasks.append("plot")
    if "integral" in text or "integrate" in text:
        tasks.append("calculus")
    if "derivative" in text or "differentiate" in text:
        tasks.append("calculus")
    if not tasks:
        tasks.append("solve")
    return tasks[:8]


def _is_multi_question(problem_text: str) -> Tuple[bool, List[str]]:
    text = (problem_text or "").strip()
    if not text:
        return False, []

    numbered = re.findall(r"(?m)^\s*(\d+[\).:-])\s*(.+)$", text)
    if len(numbered) >= 2:
        return True, [m[1].strip()[:180] for m in numbered[:6] if m[1].strip()]

    segments = [seg.strip() for seg in re.split(r"\n\s*\n", text) if seg.strip()]
    equation_segments = [s for s in segments if "=" in s or "solve" in s.lower()]
    if len(equation_segments) >= 2:
        return True, [s[:180] for s in equation_segments[:6]]

    if re.search(r"\bsolve\b.+\bsolve\b", text, re.IGNORECASE | re.DOTALL):
        return True, []
    return False, []


def _extract_verification_problem_text(problem_text: str) -> str:
    text = (problem_text or "").strip()
    if not text:
        return text
    de_latex = text.replace("$$", " ").replace("$", " ").replace("\\(", " ").replace("\\)", " ")
    y_intersection = re.search(
        r"\by\s*=\s*([^,\n;]+?)\s+\band\b\s+y\s*=\s*([^,\n;]+?)(?:[.\n;]|$)",
        de_latex,
        flags=re.IGNORECASE,
    )
    if y_intersection:
        left = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", y_intersection.group(1)).strip()
        right = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", y_intersection.group(2)).strip()
        if left and right and left != right:
            return f"{left}={right}"
    # Intersection-style prompts frequently contain two assignments like y=... and y=....
    # Convert them into a single equation so SymPy verification can parse deterministically.
    assignment_matches = re.findall(
        r"([A-Za-z])\s*=\s*([^=,\n;]+?)(?=(?:\s+\band\b\s+[A-Za-z]\s*=)|[,\n;.]|$)",
        de_latex,
        flags=re.IGNORECASE,
    )
    if len(assignment_matches) >= 2:
        first_var, first_expr = assignment_matches[0][0], assignment_matches[0][1]
        for var, expr in assignment_matches[1:]:
            if var.strip().lower() == first_var.strip().lower():
                left = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", first_expr).strip()
                right = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", expr).strip()
                if left and right and left != right:
                    return f"{left}={right}"
    eq_zero = re.findall(r"([A-Za-z0-9_\^\+\-\*/\(\)\.\s]{1,120}=\s*0(?:\.0+)?)", de_latex)
    for candidate in eq_zero:
        value = re.sub(r"\s+", " ", candidate).strip()
        if "=" not in value:
            continue
        lhs, rhs = value.split("=", 1)
        lhs = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", lhs)
        rhs = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", rhs)
        lhs_match = re.search(r"([xXyY0-9\(][A-Za-z0-9_\^\+\-\*/\(\)\.\s]{0,80})$", lhs.strip())
        lhs_clean = lhs_match.group(1).strip() if lhs_match else lhs.strip()
        rhs_clean = rhs.strip().split(" ")[0].strip()
        compact = f"{lhs_clean}={rhs_clean}".strip()
        if "=" in compact and len(compact) >= 3:
            return compact
    raw_candidates = re.findall(r"([^,\n;]+=[^,\n;]+)", de_latex)
    cleaned: List[str] = []
    banned_words = {"include", "plot", "show", "graph", "intercept", "solve the equation", "and include"}
    math_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-*/^().= ")
    for candidate in raw_candidates:
        if any(ch not in math_chars for ch in candidate):
            continue
        value = re.sub(r"\s+", " ", candidate).strip()
        lower = value.lower()
        if any(word in lower for word in banned_words):
            continue
        if value.count("=") != 1:
            continue
        if len(value) < 3:
            continue
        cleaned.append(value)
    preferred = [c for c in cleaned if "=0" in c.replace(" ", "")]
    if preferred:
        return preferred[0]
    if cleaned:
        return cleaned[0]
    if "=" in de_latex:
        lhs, rhs = de_latex.split("=", 1)
        lhs_tail = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", lhs)[-80:]
        rhs_head = re.sub(r"[^A-Za-z0-9_\^\+\-\*/\(\)\.\s]", " ", rhs)[:80]
        compact = re.sub(r"\s+", " ", f"{lhs_tail}={rhs_head}").strip()
        if len(compact) >= 3:
            return compact
    return text


def _select_verification_problem_text(problem_text: str, math_obj: Any) -> str:
    full_text = str(problem_text or "")
    full_lower = full_text.lower()
    analysis_markers = (
        "simplify",
        "domain restriction",
        "hole",
        "critical point",
        "critical points",
        "classify",
        "newton",
        "intersection",
        "intersections",
        "system",
        "equilibrium",
    )
    if any(marker in full_lower for marker in analysis_markers):
        return full_text.replace("^", "**")

    extracted = _extract_verification_problem_text(problem_text)
    if extracted and "=" in extracted and len(extracted) <= 180:
        return extracted.replace("^", "**")
    if isinstance(math_obj, str):
        candidate = re.sub(r"\s+", " ", math_obj).strip()
        lower = candidate.lower()
        noisy_markers = {"include", "plot", "graph", "show", "solve", "find", "intersection"}
        if (
            candidate
            and "=" in candidate
            and candidate.count("=") == 1
            and len(candidate) <= 180
            and not any(marker in lower for marker in noisy_markers)
        ):
            return candidate.replace("^", "**")
    return (extracted or str(problem_text or "")).replace("^", "**")


def _solution_item(value: Any) -> Dict[str, Any]:
    value_text = str(value or "").strip() or "?"
    return {"value_text": value_text, "value_latex": value_text}


def _default_runtime_meta(
    request_id: str,
    attempt_id: str,
    provider: str,
    model: Optional[str],
    timing_ms: Dict[str, int],
) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "attempt_id": attempt_id,
        "provider": provider,
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "latency_ms_total": timing_ms.get("total", 0),
        "latency_ms_openai": timing_ms.get("openai", 0),
        "finish_reason": None,
        "truncated": False,
        "cache_hit": False,
        "timing_ms": {
            "parse": timing_ms.get("parse", 0),
            "canonicalize": timing_ms.get("canonicalize", 0),
            "openai": timing_ms.get("openai", 0),
            "verify": timing_ms.get("verify", 0),
            "total": timing_ms.get("total", 0),
        },
    }


def _base_response(
    *,
    request_id: str,
    attempt_id: str,
    tier: str,
    mode: str,
    problem_text: str,
    preferred_response_language: str,
    response_kind: str,
    graph_mode: str,
    timing_ms: Dict[str, int],
) -> Dict[str, Any]:
    return {
        "schema_version": "v2",
        "tier": tier,
        "mode": mode,
        "response_kind": response_kind,
        "_raw_llm_output": None,
        "refusal": {"is_refusal": False, "reason": None, "safe_alternative": None},
        "problem": {
            "original_text": problem_text,
            "normalized_text": problem_text,
            "language": {
                "user_language": preferred_response_language,
                "response_language": preferred_response_language,
                "preferred_response_language": preferred_response_language,
            },
            "detected_tasks": _detected_tasks(problem_text, graph_mode),
        },
        "classification": {
            "grade_band": "grades_9_10",
            "domain": "other",
            "topic": "math",
            "difficulty": "medium",
        },
        "clarification": {
            "needs_clarification": response_kind == "clarification",
            "questions": [],
            "note": None,
        },
        "assumptions": [],
        "steps": [],
        "final_answer": {
            "answer_text": "Pending",
            "answer_latex": None,
            "values": [],
            "units": None,
        },
        "verification": {
            "verified": False,
            "verification_method": "none",
            "unverified_reason": "not_applicable",
            "assumptions_used": [],
            "candidate_solutions": [],
            "dropped_candidates": [],
            "final_solutions": [],
            "verification_meta": {
                "symbolic_parse": False,
                "duration_ms": 0,
                "candidates_checked": 0,
                "timed_out": False,
                "route": "other",
            },
        },
        "visuals": {
            "should_visualize": graph_mode == "on",
            "decision_reason": "Graph mode requested by user" if graph_mode == "on" else "No visualization required",
            "plots": [],
            "alternative_visual": {
                "kind": "none",
                "description": "No additional visualization.",
                "data": "n/a",
            },
        },
        "quality": {"confidence": 0.6, "common_mistakes": []},
        "runtime_meta": _default_runtime_meta(request_id, attempt_id, "openai", os.getenv("OPENAI_MODEL_DEFAULT"), timing_ms),
    }


def _as_solution_items(values: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not isinstance(values, list):
        return items
    for entry in values:
        if isinstance(entry, dict):
            value = str(entry.get("value") or entry.get("value_text") or "").strip()
            latex = str(entry.get("latex") or entry.get("value_latex") or value).strip() or value
            label = str(entry.get("label") or "solution").strip() or "solution"
            if value:
                items.append({"label": label, "value": value, "value_latex": latex})
        elif entry is not None:
            value = str(entry).strip()
            if value:
                items.append({"label": "solution", "value": value, "value_latex": value})
    return items[:12]


def _to_superset_plot_recipe(recipe: Dict[str, Any]) -> Dict[str, Any]:
    symbols = recipe.get("symbols") if isinstance(recipe.get("symbols"), list) else []
    expressions = recipe.get("expressions") if isinstance(recipe.get("expressions"), list) else []
    domain = recipe.get("domain") if isinstance(recipe.get("domain"), dict) else {}
    sampling = recipe.get("sampling") if isinstance(recipe.get("sampling"), dict) else {}
    expr = "; ".join(str(x) for x in expressions if str(x).strip())[:200000] or None
    return {
        "generator": "function_2d",
        "expr": expr,
        "system": None,
        "symbols": [str(x) for x in symbols if str(x).strip()][:10],
        "data_ref": None,
        "params": {"zeta": None, "beta": None, "omega": None, "gamma": None},
        "initial_conditions": {"x0": None, "v0": None},
        "sampling": {
            "t_min": domain.get("x_min"),
            "t_max": domain.get("x_max"),
            "dt": None,
            "samples": int(sampling.get("n_points")) if sampling.get("n_points") else None,
            "discard": None,
            "samples_per_period": None,
            "transient_periods": None,
            "keep_periods": None,
        },
        "sweep": {"param": None, "min": None, "max": None, "steps": None},
    }


def _llm_min_to_superset(
    *,
    llm_payload: Dict[str, Any],
    base: Dict[str, Any],
    problem_text: str,
    graph_mode: str,
    tier: str,
    mode: str,
) -> Dict[str, Any]:
    payload = copy.deepcopy(base)
    response_kind = str(llm_payload.get("response_kind") or "solution").strip().lower()
    if response_kind not in {"solution", "clarification", "refusal"}:
        response_kind = "solution"
    payload["response_kind"] = response_kind
    payload["tier"] = tier
    payload["mode"] = mode
    payload["problem"]["original_text"] = problem_text
    payload["problem"]["normalized_text"] = problem_text

    language = llm_payload.get("language") if isinstance(llm_payload.get("language"), dict) else {}
    payload["problem"]["language"]["preferred_response_language"] = str(
        language.get("preferred_response_language") or payload["problem"]["language"]["preferred_response_language"]
    )
    payload["problem"]["language"]["response_language"] = str(
        language.get("response_language") or payload["problem"]["language"]["response_language"]
    )
    payload["problem"]["language"]["user_language"] = str(
        language.get("user_language") or payload["problem"]["language"]["user_language"]
    )

    payload["assumptions"] = [str(x) for x in (llm_payload.get("assumptions") or []) if str(x).strip()][:20]
    payload["steps"] = llm_payload.get("steps") if isinstance(llm_payload.get("steps"), list) else []

    llm_final = llm_payload.get("final_answer") if isinstance(llm_payload.get("final_answer"), dict) else None
    if response_kind == "solution" and llm_final:
        values = _as_solution_items(llm_final.get("values"))
        payload["final_answer"] = {
            "answer_text": str(llm_final.get("answer_text") or "").strip() or "Pending backend verification",
            "answer_latex": llm_final.get("answer_latex"),
            "values": values,
            "units": None,
        }
    elif response_kind in {"clarification", "refusal"}:
        payload["final_answer"] = None

    llm_candidates = _as_solution_items(llm_payload.get("candidates"))
    if not llm_candidates and llm_final:
        llm_candidates = _as_solution_items(llm_final.get("values"))
    if not llm_candidates and llm_final:
        answer_text = str(llm_final.get("answer_text") or "")
        inferred = [x.group(0) for x in re.finditer(r"[-+]?\d+(?:\.\d+)?(?:/\d+)?", answer_text)]
        llm_candidates = [{"label": "solution", "value": v, "value_latex": v} for v in inferred[:6]]
    payload["verification"]["candidate_solutions"] = [
        {"value_text": c["value"], "value_latex": c["value_latex"]} for c in llm_candidates
    ]
    payload["verification"]["verified"] = False
    payload["verification"]["verification_method"] = "none"
    payload["verification"]["unverified_reason"] = "Pending backend verification (symbolic substitution/domain checks)."
    payload["verification"]["assumptions_used"] = payload["assumptions"]
    payload["verification"]["dropped_candidates"] = []
    payload["verification"]["final_solutions"] = []

    llm_clarify = llm_payload.get("clarification") if isinstance(llm_payload.get("clarification"), dict) else {}
    llm_refusal = llm_payload.get("refusal") if isinstance(llm_payload.get("refusal"), dict) else {}
    payload["clarification"]["needs_clarification"] = bool(llm_clarify.get("needs_clarification")) or response_kind == "clarification"
    payload["clarification"]["questions"] = llm_clarify.get("questions") if isinstance(llm_clarify.get("questions"), list) else []
    payload["clarification"]["note"] = llm_clarify.get("note")
    payload["refusal"]["is_refusal"] = bool(llm_refusal.get("is_refusal")) or response_kind == "refusal"
    payload["refusal"]["reason"] = llm_refusal.get("reason")
    payload["refusal"]["safe_alternative"] = llm_refusal.get("safe_alternative")

    llm_plot = llm_payload.get("plot") if isinstance(llm_payload.get("plot"), dict) else {}
    llm_recipe = llm_plot.get("recipe") if isinstance(llm_plot.get("recipe"), dict) else None
    should_visualize = bool(llm_plot.get("should_visualize")) and response_kind == "solution"
    if graph_mode == "off":
        should_visualize = False
    payload["visuals"]["should_visualize"] = should_visualize
    payload["visuals"]["decision_reason"] = str(
        llm_plot.get("decision_reason") or payload["visuals"]["decision_reason"]
    )[:20000]
    payload["visuals"]["plots"] = []
    if should_visualize and llm_recipe:
        axis_labels = llm_recipe.get("axis_labels") if isinstance(llm_recipe.get("axis_labels"), dict) else {}
        domain = llm_recipe.get("domain") if isinstance(llm_recipe.get("domain"), dict) else {}
        key_points_raw = llm_recipe.get("key_points") if isinstance(llm_recipe.get("key_points"), list) else []
        key_points = []
        for kp in key_points_raw[:30]:
            if isinstance(kp, dict):
                key_points.append(
                    {"label": str(kp.get("label") or "point"), "x": kp.get("x"), "y": kp.get("y")}
                )
        payload["visuals"]["plots"] = [
            {
                "kind": str(llm_recipe.get("plot_intent") or "function_2d"),
                "title": str(llm_recipe.get("title") or "Generated plot"),
                "subtitle": None,
                "x_label": axis_labels.get("x"),
                "y_label": axis_labels.get("y"),
                "z_label": None,
                "domain": {
                    "x_min": domain.get("x_min"),
                    "x_max": domain.get("x_max"),
                    "y_min": domain.get("y_min"),
                    "y_max": domain.get("y_max"),
                },
                "series": [],
                "key_points": key_points,
                "render_hint": {"preferred": "matplotlib", "notes": "backend_recipe"},
                "recipe": _to_superset_plot_recipe(llm_recipe),
                "rendered": {"image_ref": None, "mime": None, "width_px": None, "height_px": None, "caption": None},
            }
        ]
    return payload


def _clarification_patch_to_superset(
    *,
    patch_payload: Dict[str, Any],
    base: Dict[str, Any],
    choices: List[str],
) -> Dict[str, Any]:
    payload = copy.deepcopy(base)
    payload["response_kind"] = "clarification"
    payload["steps"] = []
    payload["final_answer"] = None
    payload["visuals"]["should_visualize"] = False
    payload["visuals"]["plots"] = []
    payload["verification"]["verified"] = False
    payload["verification"]["verification_method"] = "none"
    payload["verification"]["unverified_reason"] = "needs_clarification"
    payload["clarification"]["needs_clarification"] = True

    questions = patch_payload.get("questions") if isinstance(patch_payload.get("questions"), list) else []
    if not questions:
        questions = [
            {
                "id": "q1",
                "question": "Which single question should I solve first?",
                "choices": choices if choices else ["Question 1", "Question 2"],
            }
        ]
    payload["clarification"]["questions"] = questions[:2]
    payload["clarification"]["note"] = str(
        patch_payload.get("reason") or "Please send one question per solve request."
    )[:20000]
    return payload


def _apply_repair_patch(payload: Dict[str, Any], patch_payload: Dict[str, Any]) -> Dict[str, Any]:
    patched = copy.deepcopy(payload)
    action = str(patch_payload.get("action") or "repair").strip().lower()
    if action == "clarification":
        patched["response_kind"] = "clarification"
        patched["steps"] = []
        patched["final_answer"] = None
        patched["visuals"]["should_visualize"] = False
        questions = patch_payload.get("clarification_questions")
        if isinstance(questions, list):
            patched["clarification"]["needs_clarification"] = True
            patched["clarification"]["questions"] = questions[:2]
        return patched

    edits = patch_payload.get("edits")
    if not isinstance(edits, list):
        return patched

    for edit in edits[:10]:
        if not isinstance(edit, dict):
            continue
        path = str(edit.get("path") or "").strip()
        value = edit.get("value")
        if path in {"$.candidates", "$.verification.candidate_solutions", "$.final_solutions"}:
            items = _as_solution_items(value if isinstance(value, list) else [])
            patched["verification"]["candidate_solutions"] = [
                {"value_text": item["value"], "value_latex": item["value_latex"]} for item in items
            ]
        elif path in {"$.steps"} and isinstance(value, list):
            patched["steps"] = value
        elif path in {"$.assumptions"} and isinstance(value, list):
            patched["assumptions"] = [str(x) for x in value if str(x).strip()][:20]
        elif path in {"$.final_answer", "$.final_answer.answer_text"}:
            if isinstance(value, dict):
                answer = str(value.get("answer_text") or "").strip()
            else:
                answer = str(value or "").strip()
            if not isinstance(patched.get("final_answer"), dict):
                patched["final_answer"] = {"answer_text": "", "answer_latex": None, "values": [], "units": None}
            patched["final_answer"]["answer_text"] = answer
            patched["final_answer"]["answer_latex"] = answer
        elif path in {"$.plot.should_visualize", "$.visuals.should_visualize"}:
            patched["visuals"]["should_visualize"] = bool(value)
        elif path in {"$.plot.decision_reason", "$.visuals.decision_reason"}:
            patched["visuals"]["decision_reason"] = str(value or "")[:20000]
    return patched


def _sanitize_steps(data: Dict[str, Any], *, min_steps: int, max_steps: int) -> None:
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list):
        raw_steps = []
    clean: List[Dict[str, Any]] = []
    for idx, step in enumerate(raw_steps, start=1):
        if not isinstance(step, dict):
            continue
        math_latex = step.get("math_latex")
        if isinstance(math_latex, str):
            math_latex = [math_latex] if math_latex.strip() else []
        if not isinstance(math_latex, list):
            math_latex = []
        clean.append(
            {
                "index": idx,
                "title": str(step.get("title") or f"Step {idx}")[:200] or f"Step {idx}",
                "explanation": str(step.get("explanation") or "Proceed with the next transformation.")[:20000] or "Proceed with the next transformation.",
                "math_latex": [str(x)[:200000] for x in math_latex][:40],
                "rules_used": [str(x)[:500] for x in (step.get("rules_used") or []) if str(x).strip()][:12],
                "plots_used": [str(x) for x in (step.get("plots_used") or []) if str(x).strip()][:6],
                "checks": [str(x)[:800] for x in (step.get("checks") or []) if str(x).strip()][:8],
                "notes": (str(step.get("notes"))[:20000] if step.get("notes") is not None else None),
            }
        )
    while len(clean) < min_steps:
        idx = len(clean) + 1
        clean.append(
            {
                "index": idx,
                "title": f"Step {idx}",
                "explanation": "Continue the verified derivation from the previous step.",
                "math_latex": [],
                "rules_used": [],
                "plots_used": [],
                "checks": [],
                "notes": None,
            }
        )
    data["steps"] = clean[: max(0, max_steps)]


def _candidate_strings(data: Dict[str, Any]) -> List[str]:
    verification = data.get("verification") if isinstance(data.get("verification"), dict) else {}
    values: List[str] = []
    for candidate in verification.get("candidate_solutions") or []:
        if isinstance(candidate, dict):
            raw = str(candidate.get("value_text") or "").strip()
            if raw:
                values.append(raw)
    if values:
        return values
    answer_text = ""
    final_answer = data.get("final_answer")
    if isinstance(final_answer, dict):
        answer_text = str(final_answer.get("answer_text") or "")
    return [x.group(0) for x in re.finditer(r"[-+]?\d+(?:\.\d+)?(?:/\d+)?", answer_text)]


def _numeric_verify_equation(problem_text: str, candidate_values: List[str]) -> Dict[str, Any]:
    if "=" not in (problem_text or "") or not candidate_values:
        return {"verified": False, "final_solutions": [], "dropped_candidates": []}
    try:
        from sympy import Symbol, sympify
        def _sympy_ready(expr: str) -> str:
            out = expr
            out = re.sub(r"(\d)([A-Za-z])", r"\1*\2", out)
            out = re.sub(r"([A-Za-z])(\d)", r"\1*\2", out)
            out = re.sub(r"([A-Za-z0-9\)])\(", r"\1*(", out)
            out = re.sub(r"\)\s*([A-Za-z0-9])", r")*\1", out)
            return out
        text = (problem_text or "").replace("^", "**")
        left, right = text.split("=", 1)
        lhs = sympify(_sympy_ready(left.strip()))
        rhs = sympify(_sympy_ready(right.strip()))
        expr = lhs - rhs
        symbols = list(expr.free_symbols)
        target_symbol = symbols[0] if symbols else Symbol("x", real=True)
        final: List[str] = []
        dropped: List[Dict[str, str]] = []
        for raw in candidate_values:
            try:
                v = sympify(raw)
                delta = expr.subs(target_symbol, v).evalf()
                if abs(float(delta)) <= 1e-7:
                    final.append(str(v))
                else:
                    dropped.append({"candidate": str(raw), "reason": "numeric_substitution_failed"})
            except Exception:
                dropped.append({"candidate": str(raw), "reason": "invalid_candidate"})
        return {"verified": len(final) > 0, "final_solutions": final, "dropped_candidates": dropped}
    except Exception:
        return {"verified": False, "final_solutions": [], "dropped_candidates": []}


def _apply_verification(data: Dict[str, Any], *, problem_text: str, request_id: str, route: str) -> Dict[str, Any]:
    candidate_values = _candidate_strings(data)
    verification_meta = verify_solve_result(
        problem_text,
        data,
        request_id=request_id,
        candidate_values=candidate_values,
        route=route if route in {"rule_engine", "openai", "cache"} else "other",
    )
    ver_meta = verification_meta.get("verification_meta") or {}
    if (
        not bool(verification_meta.get("verified"))
        and not bool(ver_meta.get("symbolic_parse"))
        and "=" in (problem_text or "")
        and candidate_values
    ):
        numeric = _numeric_verify_equation(problem_text, candidate_values)
        if numeric.get("verified"):
            verification_meta["verified"] = True
            verification_meta["verification_method"] = "numeric"
            verification_meta["unverified_reason"] = None
            verification_meta["final_solutions"] = numeric.get("final_solutions") or []
            verification_meta["dropped_candidates"] = numeric.get("dropped_candidates") or []
    verification = data.get("verification")
    if not isinstance(verification, dict):
        verification = {}

    final_solution_items = [_solution_item(v) for v in verification_meta.get("final_solutions") or []]
    dropped_items = []
    for dropped in verification_meta.get("dropped_candidates") or []:
        if not isinstance(dropped, dict):
            continue
        dropped_items.append(
            {
                "candidate": _solution_item(dropped.get("candidate")),
                "reason": str(dropped.get("reason") or "failed_substitution_or_domain"),
            }
        )

    verification.update(
        {
            "verified": bool(verification_meta.get("verified")),
            "verification_method": verification_meta.get("verification_method") or "none",
            "unverified_reason": verification_meta.get("unverified_reason"),
            "assumptions_used": verification_meta.get("assumptions") or [],
            "candidate_solutions": verification.get("candidate_solutions") or [],
            "dropped_candidates": dropped_items,
            "final_solutions": final_solution_items,
            "verification_meta": {
                "symbolic_parse": bool((verification_meta.get("verification_meta") or {}).get("symbolic_parse")),
                "duration_ms": int((verification_meta.get("verification_meta") or {}).get("duration_ms") or 0),
                "candidates_checked": int((verification_meta.get("verification_meta") or {}).get("candidates_checked") or 0),
                "timed_out": bool((verification_meta.get("verification_meta") or {}).get("timed_out", False)),
                "route": str((verification_meta.get("verification_meta") or {}).get("route") or route or "other"),
            },
        }
    )
    data["verification"] = verification
    data["assumptions"] = verification.get("assumptions_used") or []

    if verification.get("verified") and final_solution_items:
        answer_text = ", ".join(item["value_text"] for item in final_solution_items)
        final_answer = data.get("final_answer") if isinstance(data.get("final_answer"), dict) else {}
        final_answer["answer_text"] = answer_text
        final_answer["answer_latex"] = answer_text
        final_answer["values"] = [
            {"label": "solution", "value": item["value_text"], "value_latex": item["value_latex"]}
            for item in final_solution_items
        ]
        final_answer["units"] = final_answer.get("units")
        data["final_answer"] = final_answer
    elif not verification.get("verified"):
        final_answer = data.get("final_answer") if isinstance(data.get("final_answer"), dict) else {}
        answer_text = str(final_answer.get("answer_text") or "").strip()
        if answer_text:
            final_answer["answer_text"] = f"Unverified explanation: {answer_text}"
            data["final_answer"] = final_answer
    return data


def _extract_schema_validator(schema_entry: JsonSchemaEntry) -> Tuple[str, Dict[str, Any], Draft202012Validator]:
    schema_obj = _extract_schema_object(schema_entry)
    deref_schema = deref_json_schema(schema_obj)
    validate_no_refs(deref_schema, raise_error=True)
    return _extract_schema_name(schema_entry), deref_schema, Draft202012Validator(deref_schema)


def _schema_wrapper(name: str, schema: Dict[str, Any], call_name: str) -> Dict[str, Any]:
    return build_openai_structured_output(
        {"type": "json_schema", "name": name, "strict": True, "schema": schema},
        endpoint="responses",
        call_name=call_name,
    )


def _load_user_language(session: Session, user_id: int) -> str:
    user = session.get(User, user_id)
    if not user:
        return "en"
    raw = str(getattr(user, "preferred_language", None) or "en").strip().lower()
    lang_map = {
        "en": "en",
        "english": "en",
        "english (us)": "en",
        "fr": "fr",
        "french": "fr",
        "francais": "fr",
        "fran\u00e7ais": "fr",
        "ar": "ar",
        "arabic": "ar",
        "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "ar",
        "es": "es",
        "spanish": "es",
        "espanol": "es",
        "espa\u00f1ol": "es",
        "pt": "pt",
        "portuguese": "pt",
        "portugues": "pt",
        "portugu\u00eas": "pt",
        "ru": "ru",
        "russian": "ru",
        "\u0440\u0443\u0441\u0441\u043a\u0438\u0439": "ru",
        "it": "it",
        "italian": "it",
        "italiano": "it",
    }
    return lang_map.get(raw, (raw[:2] if len(raw) >= 2 else "en"))


def _normalize_plot_from_pipeline(payload: Dict[str, Any], plot_data: Dict[str, Any]) -> Dict[str, Any]:
    spec = (plot_data or {}).get("spec") if isinstance(plot_data, dict) else None
    if not isinstance(spec, dict):
        return payload
    plotly = spec.get("plotly_json") if isinstance(spec.get("plotly_json"), dict) else {}
    data_series: List[Dict[str, Any]] = []
    for trace in plotly.get("data") or []:
        if not isinstance(trace, dict):
            continue
        mode = str(trace.get("mode") or "lines")
        if mode not in {"lines", "markers", "lines+markers", "bars"}:
            mode = "lines"
        data_series.append(
            {
                "name": str(trace.get("name") or "Series"),
                "x": (trace.get("x") if isinstance(trace.get("x"), list) else [])[:200],
                "y": (trace.get("y") if isinstance(trace.get("y"), list) else [])[:200],
                "mode": mode,
            }
        )
    if not data_series:
        return payload

    visuals = payload.get("visuals") if isinstance(payload.get("visuals"), dict) else {}
    plots = visuals.get("plots") if isinstance(visuals.get("plots"), list) else []
    first = plots[0] if plots and isinstance(plots[0], dict) else {
        "kind": "function_2d",
        "title": "Generated Plot",
        "subtitle": None,
        "x_label": "x",
        "y_label": "y",
        "z_label": None,
        "domain": {"x_min": None, "x_max": None, "y_min": None, "y_max": None},
        "series": [],
        "key_points": [],
        "render_hint": {"preferred": "plotly", "notes": None},
        "recipe": None,
        "rendered": {"image_ref": None, "mime": None, "width_px": None, "height_px": None, "caption": None},
    }
    first["series"] = data_series[:6]
    visuals["plots"] = [first]
    visuals["should_visualize"] = True
    visuals["decision_reason"] = str(visuals.get("decision_reason") or "Plot rendered by backend pipeline")
    if not isinstance(visuals.get("alternative_visual"), dict):
        visuals["alternative_visual"] = {"kind": "none", "description": "No alternative visual", "data": "n/a"}
    payload["visuals"] = visuals
    return payload


def _is_verification_applicable(mode: str, problem_text: str) -> bool:
    mode_upper = str(mode or "").strip().upper()
    if mode_upper in {"PROOF", "OTHER"}:
        return False
    text = (problem_text or "").lower()
    if any(keyword in text for keyword in ("prove", "show that", "integral", "integrate", "inequality")):
        return False
    if "=" in text:
        return True
    analysis_keywords = (
        "simplify",
        "domain",
        "hole",
        "critical point",
        "critical points",
        "classify",
        "newton",
        "root",
        "roots",
        "intersection",
        "intersections",
        "equilibrium",
    )
    if any(keyword in text for keyword in analysis_keywords):
        return True
    return True


def _verification_failure_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
    return {
        "verified": bool(verification.get("verified")),
        "verification_method": verification.get("verification_method"),
        "unverified_reason": verification.get("unverified_reason"),
        "assumptions_used": verification.get("assumptions_used") or [],
        "dropped_candidates": verification.get("dropped_candidates") or [],
        "final_solutions": verification.get("final_solutions") or [],
        "verification_meta": verification.get("verification_meta") or {},
    }


def _copy_math_protected_fields(src: Dict[str, Any], dst: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(dst)
    merged["verification"] = copy.deepcopy(src.get("verification"))
    merged["assumptions"] = copy.deepcopy(src.get("assumptions"))
    merged["final_answer"] = copy.deepcopy(src.get("final_answer"))
    merged["visuals"] = copy.deepcopy(src.get("visuals"))
    merged["problem"] = copy.deepcopy(src.get("problem"))
    merged["classification"] = copy.deepcopy(src.get("classification"))
    return merged


async def run_solve_v3_superset_v2(
    *,
    session: Session,
    user_id: int,
    problem_text: str,
    requested_tier: Optional[str],
    requested_mode: str,
    graph_mode: str,
    trusted_context: Optional[Dict[str, Any]],
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    config = load_solve_v2_config(session)
    request_id = (idempotency_key or "").strip() or str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    preferred_response_language = _load_user_language(session, user_id)
    tier = _tier_to_v2(requested_tier)
    mode = "SOLVE"

    timing_ms = {"parse": 0, "canonicalize": 0, "openai": 0, "verify": 0, "total": 0}
    route = "openai"
    start_total = time.perf_counter()

    attempt = SolverOutputAttempt(
        request_id=request_id,
        attempt_id=attempt_id,
        user_id=user_id,
        status="processing",
        output_format="superset_v2",
        provider="openai",
        model=os.getenv("OPENAI_MODEL_DEFAULT"),
        input_text_raw=problem_text,
        input_text_normalized=problem_text,
        prompt_meta={
            "graph_mode": graph_mode,
            "requested_mode": requested_mode,
            "tier_requested": requested_tier,
            "tier_effective": tier,
            "response_schema": config.superset_schema_id,
            "llm_response_schema": config.llm_min_schema_id,
            "trusted_context": trusted_context or {},
        },
    )
    session.add(attempt)
    session.commit()

    base = _base_response(
        request_id=request_id,
        attempt_id=attempt_id,
        tier=tier,
        mode=mode,
        problem_text=problem_text,
        preferred_response_language=preferred_response_language,
        response_kind="solution",
        graph_mode=graph_mode,
        timing_ms=timing_ms,
    )

    try:
        t_parse = time.perf_counter()
        is_multi, choices = _is_multi_question(problem_text)
        timing_ms["parse"] = int((time.perf_counter() - t_parse) * 1000)
        emit_runtime_audit(
            component="solve_v3_stage_parse",
            started_at=t_parse,
            request_id=request_id,
            route=route,
            result="ok",
            extra={"attempt_id": attempt_id, "multi_question": is_multi, "mode_detected": mode},
        )

        t_canonical = time.perf_counter()
        intent = canonicalization_service.get_intent(problem_text)
        math_obj, assumptions = canonicalization_service.normalize_math_object(problem_text, intent)
        canonical_key = canonicalization_service.compute_canonical_key(
            intent,
            math_obj,
            {**(assumptions or {}), "domain_mode": "real", "solve_mode": requested_mode},
        )
        timing_ms["canonicalize"] = int((time.perf_counter() - t_canonical) * 1000)
        emit_runtime_audit(
            component="solve_v3_stage_canonicalize",
            started_at=t_canonical,
            request_id=request_id,
            route=route,
            sympy_used=True,
            result="ok",
            extra={"attempt_id": attempt_id},
        )

        cached = cache_service.get_cached_solution(session, canonical_key) if canonical_key else None
        if isinstance(cached, dict) and isinstance(cached.get("verification"), dict):
            route = "cache"
            payload = copy.deepcopy(cached)
            timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
            payload["runtime_meta"] = _default_runtime_meta(request_id, attempt_id, "cache", "cached", timing_ms)
            payload["runtime_meta"]["cache_hit"] = True
            attempt.status = "success"
            attempt.validation_json = payload
            attempt.prompt_meta = {**(attempt.prompt_meta or {}), "route": route}
            session.add(attempt)
            session.commit()
            payload["request_id"] = request_id
            payload["attempt_id"] = attempt_id
            payload["verified"] = bool((payload.get("verification") or {}).get("verified"))
            payload["verification_method"] = (payload.get("verification") or {}).get("verification_method")
            payload["timing_ms"] = payload["runtime_meta"]["timing_ms"]
            return payload

        superset_schema_entry = _latest_active_schema(session, config.superset_schema_id)
        _superset_name, _superset_body, schema_validator = _extract_schema_validator(superset_schema_entry)
        llm_schema_entry = _latest_active_schema(session, config.llm_min_schema_id)
        llm_schema_name, llm_schema_body, _llm_validator = _extract_schema_validator(llm_schema_entry)
        llm_schema_wrapper = _schema_wrapper(llm_schema_name, llm_schema_body, "SOLVE_LLM_MIN_V2")
        clarify_schema_entry = _latest_active_schema(session, config.clarify_schema_id)
        clarify_schema_name, clarify_schema_body, _clarify_validator = _extract_schema_validator(clarify_schema_entry)
        clarify_schema_wrapper = _schema_wrapper(clarify_schema_name, clarify_schema_body, "SOLVE_CLARIFICATION_PATCH_V1")
        repair_schema_entry = _latest_active_schema(session, config.repair_schema_id)
        repair_schema_name, repair_schema_body, _repair_validator = _extract_schema_validator(repair_schema_entry)
        repair_schema_wrapper = _schema_wrapper(repair_schema_name, repair_schema_body, "SOLVE_REPAIR_PATCH_V1")
        system_prompt = _latest_active_prompt(session, config.system_prompt_id)
        orchestrator_prompt = _latest_active_prompt(session, config.orchestrator_prompt_id)
        clarify_prompt = _latest_active_prompt(session, config.clarify_prompt_id)
        repair_prompt = _latest_active_prompt(session, config.repair_prompt_id)
        solver = get_solver_v3()
        max_tokens = int(
            (config.tier_policy.get(tier, {}) or {}).get("max_tokens")
            or DEFAULT_TIER_POLICY.get(tier, {}).get("max_tokens")
            or (8000 if requested_mode == "detailed" else 4000)
        )
        developer_runtime = {
            "tier": tier,
            "mode": mode,
            "graph_mode": graph_mode,
            "domain_mode": "real",
            "preferred_response_language": preferred_response_language,
            "requested_mode": requested_mode,
            "assumptions_detected": assumptions or {},
        }
        verification_problem_text = _select_verification_problem_text(problem_text, math_obj)

        if is_multi:
            route = "other"
            model_used = os.getenv("OPENAI_MODEL_DEFAULT")
            tokens = {"input": 0, "output": 0, "total": 0}
            status_info: Dict[str, Any] = {"finish_reason": None}
            if choices:
                payload = _clarification_patch_to_superset(
                    patch_payload={"reason": "Multiple questions detected.", "questions": []},
                    base=base,
                    choices=choices,
                )
            else:
                payload = copy.deepcopy(base)
                try:
                    t_openai = time.perf_counter()
                    clarify_parsed, tokens, status_info, model_used, clarify_raw, _ = await asyncio.wait_for(
                        solver._call_llm_with_schema(
                            problem_text=problem_text,
                            context=json.dumps(
                                {
                                    "multi_question": True,
                                    "detected_choices": choices,
                                    "preferred_response_language": preferred_response_language,
                                    "max_questions": 2,
                                },
                                ensure_ascii=True,
                            ),
                            system_prompt=system_prompt.content,
                            developer_prompt=clarify_prompt.content,
                            json_schema_config=clarify_schema_wrapper,
                            max_output_tokens=min(1200, max_tokens),
                            requested_mode=requested_mode,
                            request_id=request_id,
                        ),
                        timeout=max(3, config.openai_timeout_ms // 1000),
                    )
                    timing_ms["openai"] = int((time.perf_counter() - t_openai) * 1000)
                    ok, _validation_msg, validated, _issues, _is_ambiguous = solver._check_status_and_validate(
                        clarify_parsed,
                        status_info or {},
                        clarify_schema_wrapper.get("schema") or {},
                        raw_text=clarify_raw,
                    )
                    patch_payload = validated if ok and isinstance(validated, dict) else {}
                    payload = _clarification_patch_to_superset(patch_payload=patch_payload, base=base, choices=choices)
                    payload["_raw_llm_output"] = clarify_raw[:500000] if isinstance(clarify_raw, str) else None
                    emit_runtime_audit(
                        component="solve_v3_stage_clarification",
                        started_at=t_openai,
                        request_id=request_id,
                        route=route,
                        result="ok",
                        extra={"attempt_id": attempt_id},
                    )
                except Exception as clarify_error:
                    payload = _clarification_patch_to_superset(
                        patch_payload={"reason": "Clarification required.", "questions": []},
                        base=base,
                        choices=choices,
                    )
                    emit_runtime_audit(
                        component="solve_v3_stage_clarification",
                        started_at=time.perf_counter(),
                        request_id=request_id,
                        route=route,
                        result="error",
                        error_class=type(clarify_error).__name__,
                        extra={"attempt_id": attempt_id},
                    )

            timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
            payload["runtime_meta"] = _default_runtime_meta(request_id, attempt_id, "openai", model_used, timing_ms)
            payload["runtime_meta"]["input_tokens"] = int(tokens.get("input") or 0)
            payload["runtime_meta"]["output_tokens"] = int(tokens.get("output") or 0)
            payload["runtime_meta"]["total_tokens"] = int(tokens.get("total") or 0)
            payload["runtime_meta"]["finish_reason"] = status_info.get("finish_reason")
            attempt.status = "success"
            attempt.validation_json = payload
            attempt.prompt_meta = {
                **(attempt.prompt_meta or {}),
                "route": route,
                "multi_question": True,
                "assumptions_detected": assumptions if isinstance(assumptions, dict) else {},
            }
            session.add(attempt)
            session.commit()
            payload["request_id"] = request_id
            payload["attempt_id"] = attempt_id
            payload["verified"] = False
            payload["verification_method"] = "none"
            payload["timing_ms"] = payload["runtime_meta"]["timing_ms"]
            return payload

        t_openai = time.perf_counter()
        parsed, tokens, status_info, model_used, raw, _ = await asyncio.wait_for(
            solver._call_llm_with_schema(
                problem_text=problem_text,
                context=json.dumps(developer_runtime, ensure_ascii=True),
                system_prompt=system_prompt.content,
                developer_prompt=orchestrator_prompt.content,
                json_schema_config=llm_schema_wrapper,
                max_output_tokens=max_tokens,
                requested_mode=requested_mode,
                request_id=request_id,
            ),
            timeout=max(3, config.openai_timeout_ms // 1000),
        )
        timing_ms["openai"] = int((time.perf_counter() - t_openai) * 1000)
        emit_runtime_audit(
            component="solve_v3_stage_openai",
            started_at=t_openai,
            request_id=request_id,
            route=route,
            result="ok",
            extra={
                "attempt_id": attempt_id,
                "provider": "openai",
                "model": model_used,
                "input_tokens": int(tokens.get("input") or 0),
                "output_tokens": int(tokens.get("output") or 0),
            },
        )

        ok, validation_msg, validated, issues, _is_ambiguous = solver._check_status_and_validate(
            parsed,
            status_info or {},
            llm_schema_wrapper.get("schema") or {},
            raw_text=raw,
        )
        if not ok or not isinstance(validated, dict):
            repaired_data, tokens_repair, status_repair, model_repair, repaired_raw, _ = await asyncio.wait_for(
                solver._call_llm_with_schema(
                    problem_text=problem_text,
                    context=json.dumps(
                        {
                            **developer_runtime,
                            "schema_repair_mode": True,
                            "schema_validation_error": validation_msg or "Schema validation failed",
                            "schema_issues": issues or [],
                        },
                        ensure_ascii=True,
                    ),
                    system_prompt=system_prompt.content,
                    developer_prompt=orchestrator_prompt.content,
                    json_schema_config=llm_schema_wrapper,
                    max_output_tokens=max_tokens,
                    requested_mode=requested_mode,
                    request_id=request_id,
                ),
                timeout=max(3, config.openai_timeout_ms // 1000),
            )
            ok2, validation_msg2, validated2, _issues2, _ = solver._check_status_and_validate(
                repaired_data,
                status_repair or {},
                llm_schema_wrapper.get("schema") or {},
                raw_text=repaired_raw,
            )
            if not ok2 or not isinstance(validated2, dict):
                raise SolveV2PipelineError(
                    code="llm_invalid_output",
                    message=validation_msg2 or validation_msg or "Schema repair failed",
                    status_code=422,
                    details={"issues": issues or []},
                )
            validated = validated2
            raw = repaired_raw
            tokens["input"] = int(tokens.get("input") or 0) + int(tokens_repair.get("input") or 0)
            tokens["output"] = int(tokens.get("output") or 0) + int(tokens_repair.get("output") or 0)
            tokens["total"] = int(tokens.get("total") or 0) + int(tokens_repair.get("total") or 0)
            model_used = model_repair or model_used

        payload = _llm_min_to_superset(
            llm_payload=validated,
            base=base,
            problem_text=problem_text,
            graph_mode=graph_mode,
            tier=tier,
            mode=mode,
        )
        payload["_raw_llm_output"] = raw[:500000] if isinstance(raw, str) else None

        policy = config.tier_policy.get(tier) or DEFAULT_TIER_POLICY.get(tier) or DEFAULT_TIER_POLICY["STANDARD"]
        if payload.get("response_kind") == "solution":
            policy_min_steps = int(policy.get("min_steps", 0))
            if tier == "RESEARCH":
                policy_min_steps = max(policy_min_steps, 10)
            _sanitize_steps(payload, min_steps=policy_min_steps, max_steps=int(policy.get("max_steps", 20)))

            t_verify = time.perf_counter()
            payload = await asyncio.wait_for(
                asyncio.to_thread(
                    _apply_verification,
                    payload,
                    problem_text=verification_problem_text,
                    request_id=request_id,
                    route=route,
                ),
                timeout=max(1, config.verify_timeout_ms // 1000),
            )
            timing_ms["verify"] = int((time.perf_counter() - t_verify) * 1000)
            emit_runtime_audit(
                component="solve_v3_stage_verify",
                started_at=t_verify,
                request_id=request_id,
                route=route,
                sympy_used=True,
                result="ok",
                extra={
                    "attempt_id": attempt_id,
                    "verified": bool((payload.get("verification") or {}).get("verified")),
                    "verification_problem": verification_problem_text[:120],
                },
            )

            verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
            verifiable = _is_verification_applicable(mode, verification_problem_text)
            if not verifiable:
                verification["verified"] = False
                verification["verification_method"] = "none"
                verification["unverified_reason"] = "not_applicable"
                payload["verification"] = verification
            elif not bool(verification.get("verified")):
                t_repair = time.perf_counter()
                try:
                    repair_context = {
                        "repair_scope_snapshot": {
                            "problem_text": problem_text,
                            "assumptions": payload.get("assumptions") or [],
                            "candidates": (payload.get("verification") or {}).get("candidate_solutions") or [],
                            "verification_failure": _verification_failure_payload(payload),
                        },
                    }
                    repaired_patch, tokens_repair, _status_repair, model_repair, raw_repair, _ = await asyncio.wait_for(
                        solver._call_llm_with_schema(
                            problem_text=problem_text,
                            context=json.dumps(repair_context, ensure_ascii=True),
                            system_prompt=system_prompt.content,
                            developer_prompt=repair_prompt.content,
                            json_schema_config=repair_schema_wrapper,
                            max_output_tokens=min(1200, max_tokens),
                            requested_mode=requested_mode,
                            request_id=request_id,
                        ),
                        timeout=max(3, config.openai_timeout_ms // 1000),
                    )
                    ok_repair, _, validated_repair, _, _ = solver._check_status_and_validate(
                        repaired_patch,
                        _status_repair or {},
                        repair_schema_wrapper.get("schema") or {},
                        raw_text=raw_repair,
                    )
                    if ok_repair and isinstance(validated_repair, dict):
                        payload = _apply_repair_patch(payload, validated_repair)
                        payload = await asyncio.wait_for(
                            asyncio.to_thread(
                                _apply_verification,
                                payload,
                                problem_text=verification_problem_text,
                                request_id=request_id,
                                route=route,
                            ),
                            timeout=max(1, config.verify_timeout_ms // 1000),
                        )
                        payload["_raw_llm_output"] = raw_repair[:500000] if isinstance(raw_repair, str) else payload.get("_raw_llm_output")
                        tokens["input"] = int(tokens.get("input") or 0) + int(tokens_repair.get("input") or 0)
                        tokens["output"] = int(tokens.get("output") or 0) + int(tokens_repair.get("output") or 0)
                        tokens["total"] = int(tokens.get("total") or 0) + int(tokens_repair.get("total") or 0)
                        model_used = model_repair or model_used
                    emit_runtime_audit(
                        component="solve_v3_stage_verification_repair",
                        started_at=t_repair,
                        request_id=request_id,
                        route=route,
                        result="ok",
                        sympy_used=True,
                        extra={
                            "attempt_id": attempt_id,
                            "verified_after_repair": bool((payload.get("verification") or {}).get("verified")),
                        },
                    )
                except Exception as verify_repair_error:
                    emit_runtime_audit(
                        component="solve_v3_stage_verification_repair",
                        started_at=t_repair,
                        request_id=request_id,
                        route=route,
                        result="error",
                        sympy_used=True,
                        error_class=type(verify_repair_error).__name__,
                        extra={"attempt_id": attempt_id},
                    )
        else:
            payload["steps"] = []
            payload["verification"]["verified"] = False
            payload["verification"]["verification_method"] = "none"
            payload["verification"]["unverified_reason"] = (
                "not_applicable" if payload.get("response_kind") == "refusal" else "needs_clarification"
            )
            payload["visuals"]["should_visualize"] = False
            payload["visuals"]["plots"] = []

        if (
            config.narrator_enabled
            and bool((trusted_context or {}).get("narrator_requested"))
            and tier in {"STANDARD", "RESEARCH"}
            and isinstance(payload.get("steps"), list)
            and payload.get("response_kind") == "solution"
        ):
            t_narrator = time.perf_counter()
            narrator_prompt = _latest_active_prompt(session, config.narrator_prompt_id)
            try:
                narrator_context = {
                    "tier": tier,
                    "mode": mode,
                    "protected_paths": [
                        "verification",
                        "assumptions",
                        "problem",
                        "classification",
                        "visuals",
                        "final_answer.values",
                    ],
                    "verified_payload": payload,
                }
                narrator_data, narrator_tokens, narrator_status, narrator_model, narrator_raw, _ = await asyncio.wait_for(
                    solver._call_llm_with_schema(
                        problem_text=problem_text,
                        context=json.dumps(narrator_context, ensure_ascii=True),
                        system_prompt=system_prompt.content,
                        developer_prompt=narrator_prompt.content,
                        json_schema_config=llm_schema_wrapper,
                        max_output_tokens=max_tokens,
                        requested_mode=requested_mode,
                        request_id=request_id,
                    ),
                    timeout=max(3, config.openai_timeout_ms // 1000),
                )
                ok_narrator, _, validated_narrator, _, _ = solver._check_status_and_validate(
                    narrator_data,
                    narrator_status or {},
                    llm_schema_wrapper.get("schema") or {},
                    raw_text=narrator_raw,
                )
                if ok_narrator and isinstance(validated_narrator, dict):
                    narrative_superset = _llm_min_to_superset(
                        llm_payload=validated_narrator,
                        base=base,
                        problem_text=problem_text,
                        graph_mode=graph_mode,
                        tier=tier,
                        mode=mode,
                    )
                    payload = _copy_math_protected_fields(payload, narrative_superset)
                    payload["_raw_llm_output"] = narrator_raw[:500000] if isinstance(narrator_raw, str) else payload.get("_raw_llm_output")
                    tokens["input"] = int(tokens.get("input") or 0) + int(narrator_tokens.get("input") or 0)
                    tokens["output"] = int(tokens.get("output") or 0) + int(narrator_tokens.get("output") or 0)
                    tokens["total"] = int(tokens.get("total") or 0) + int(narrator_tokens.get("total") or 0)
                    model_used = narrator_model or model_used
                emit_runtime_audit(
                    component="solve_v3_stage_narrator",
                    started_at=t_narrator,
                    request_id=request_id,
                    route=route,
                    result="ok",
                    extra={"attempt_id": attempt_id},
                )
            except Exception as narrator_error:
                emit_runtime_audit(
                    component="solve_v3_stage_narrator",
                    started_at=t_narrator,
                    request_id=request_id,
                    route=route,
                    result="error",
                    error_class=type(narrator_error).__name__,
                    extra={"attempt_id": attempt_id},
                )

        # Ensure tier step policy still holds after any optional narrator rewrite.
        policy = config.tier_policy.get(tier) or DEFAULT_TIER_POLICY.get(tier) or DEFAULT_TIER_POLICY["STANDARD"]
        _sanitize_steps(payload, min_steps=int(policy.get("min_steps", 0)), max_steps=int(policy.get("max_steps", 20)))

        if payload.get("response_kind") == "solution":
            try:
                t_plot = time.perf_counter()
                payload = apply_graph_mode_override(payload, graph_mode=graph_mode)
                plot_data = await asyncio.wait_for(
                    maybe_generate_plot(
                        db_session=session,
                        problem_text=problem_text,
                        solve_result=payload,
                        graph_mode=graph_mode,
                        attach_to_step_id=None,
                        tier=tier,
                        question_id=request_id,
                    ),
                    timeout=max(1, config.plot_timeout_ms // 1000),
                )
                if plot_data.get("plot_generated"):
                    payload = _normalize_plot_from_pipeline(payload, plot_data)
                payload = format_plot_for_response(payload, plot_data)
                emit_runtime_audit(
                    component="solve_v3_stage_plot",
                    started_at=t_plot,
                    request_id=request_id,
                    route=route,
                    numpy_used=True,
                    result="ok",
                    extra={"attempt_id": attempt_id, "plot_generated": bool(plot_data.get("plot_generated"))},
                )
            except Exception as plot_error:
                emit_runtime_audit(
                    component="solve_v3_stage_plot",
                    started_at=time.perf_counter(),
                    request_id=request_id,
                    route=route,
                    numpy_used=True,
                    result="error",
                    error_class=type(plot_error).__name__,
                    extra={"attempt_id": attempt_id},
                )

        timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
        payload["runtime_meta"] = _default_runtime_meta(request_id, attempt_id, "openai", model_used, timing_ms)
        payload["runtime_meta"]["input_tokens"] = int(tokens.get("input") or 0)
        payload["runtime_meta"]["output_tokens"] = int(tokens.get("output") or 0)
        payload["runtime_meta"]["total_tokens"] = int(tokens.get("total") or 0)
        payload["runtime_meta"]["finish_reason"] = status_info.get("finish_reason")
        payload["runtime_meta"]["truncated"] = str(status_info.get("finish_reason") or "").lower() == "length"
        payload["runtime_meta"]["latency_ms_openai"] = timing_ms["openai"]
        payload["runtime_meta"]["latency_ms_total"] = timing_ms["total"]

        errors = list(schema_validator.iter_errors(payload))
        if errors:
            raise SolveV2PipelineError(
                code="schema_invalid_after_verification",
                message=f"Response does not match {config.superset_schema_id} after verification/plot normalization",
                status_code=503,
                details={"errors": [e.message for e in errors[:10]]},
            )

        if canonical_key and bool((payload.get("verification") or {}).get("verified")):
            try:
                cache_service.store_solution(
                    session,
                    canonical_key,
                    problem_text,
                    intent,
                    math_obj,
                    [],
                    assumptions if isinstance(assumptions, dict) else {},
                    payload,
                )
            except Exception:
                session.rollback()

        attempt.status = "success"
        attempt.validation_json = payload
        attempt.raw_solution_text = json.dumps(payload, ensure_ascii=False)
        attempt.extracted_answer = str((payload.get("final_answer") or {}).get("answer_text") or "")
        attempt.input_tokens = int(tokens.get("input") or 0)
        attempt.output_tokens = int(tokens.get("output") or 0)
        attempt.total_tokens = int(tokens.get("total") or 0)
        attempt.latency_ms = int(timing_ms["total"])
        attempt.prompt_meta = {
            **(attempt.prompt_meta or {}),
            "route": route,
            "timing_ms": timing_ms,
            "assumptions_detected": assumptions if isinstance(assumptions, dict) else {},
            "schema_id": config.superset_schema_id,
            "llm_schema_id": config.llm_min_schema_id,
            "clarify_schema_id": config.clarify_schema_id,
            "repair_schema_id": config.repair_schema_id,
            "system_prompt_id": config.system_prompt_id,
            "orchestrator_prompt_id": config.orchestrator_prompt_id,
            "clarify_prompt_id": config.clarify_prompt_id,
            "repair_prompt_id": config.repair_prompt_id,
            "graph_mode": graph_mode,
        }
        session.add(attempt)
        session.commit()

        payload["request_id"] = request_id
        payload["attempt_id"] = attempt_id
        payload["verified"] = bool((payload.get("verification") or {}).get("verified"))
        payload["verification_method"] = (payload.get("verification") or {}).get("verification_method")
        payload["assumptions_used"] = (payload.get("verification") or {}).get("assumptions_used") or []
        payload["dropped_candidates"] = (payload.get("verification") or {}).get("dropped_candidates") or []
        payload["final_solutions"] = (payload.get("verification") or {}).get("final_solutions") or []
        payload["timing_ms"] = payload["runtime_meta"]["timing_ms"]
        return payload

    except SolveV2PipelineError as err:
        timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
        attempt.status = "failed_controlled"
        attempt.failure_code = err.code
        attempt.error_message = err.message
        attempt.prompt_meta = {**(attempt.prompt_meta or {}), "timing_ms": timing_ms, "route": route, "error": err.details}
        session.add(attempt)
        session.commit()
        raise
    except Exception as err:
        timing_ms["total"] = int((time.perf_counter() - start_total) * 1000)
        attempt.status = "failed_controlled"
        attempt.failure_code = type(err).__name__
        attempt.error_message = str(err)
        attempt.prompt_meta = {**(attempt.prompt_meta or {}), "timing_ms": timing_ms, "route": route}
        session.add(attempt)
        session.commit()
        raise SolveV2PipelineError(
            code="dependency_unavailable",
            message=str(err),
            status_code=503,
            details={"timing_ms": timing_ms},
        )
