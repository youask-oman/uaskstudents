from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sympy import Eq, S, Symbol, preorder_traversal, solve, sqrt
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from app.services.runtime_audit import emit_runtime_audit


def _latexish_to_sympy_expr(raw: str) -> str:
    expr = (raw or "").strip()
    expr = expr.replace("$$", "").replace("$", "")
    expr = expr.replace(r"\cdot", "*").replace(r"\times", "*")
    expr = expr.replace(r"\left", "").replace(r"\right", "")
    expr = expr.replace(r"\geq", ">=").replace(r"\leq", "<=").replace(r"\neq", "!=")
    expr = expr.replace("^", "**")
    expr = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", expr)
    expr = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", expr)
    expr = re.sub(r"\\([a-zA-Z]+)", r"\1", expr)
    expr = expr.replace("{", "(").replace("}", ")")
    return expr.strip()


def _safe_parse_expr(expr: str):
    transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
    return parse_expr(
        expr,
        transformations=transformations,
        local_dict={"sqrt": sqrt, "x": Symbol("x")},
        evaluate=True,
    )


def _parse_equation(problem_text: str) -> Tuple[Optional[Any], Optional[Any]]:
    line = ""
    for candidate in (problem_text or "").splitlines():
        if "=" in candidate:
            line = candidate.strip()
            break
    if not line and "=" in (problem_text or ""):
        line = (problem_text or "").strip()
    if not line or "=" not in line:
        return None, None

    lhs_raw, rhs_raw = line.split("=", 1)
    lhs_raw = re.sub(r"^\s*(solve|find|determine|compute|evaluate|simplify)\b[:\s]*", "", lhs_raw, flags=re.IGNORECASE)
    lhs_raw = re.sub(r"\bfor\s+[a-zA-Z]\b\s*$", "", lhs_raw, flags=re.IGNORECASE)
    try:
        lhs = _safe_parse_expr(_latexish_to_sympy_expr(lhs_raw))
        rhs = _safe_parse_expr(_latexish_to_sympy_expr(rhs_raw))
    except Exception:
        return None, None
    return lhs, rhs


def _contains_sqrt_like(expr: Any) -> bool:
    for node in preorder_traversal(expr):
        func = getattr(node, "func", None)
        func_name = getattr(func, "__name__", str(func))
        if func_name == "sqrt":
            return True
        if func_name == "Pow":
            args = getattr(node, "args", ())
            if len(args) == 2 and str(args[1]) in {"1/2", "0.5"}:
                return True
    return False


def _extract_domain_constraints(lhs: Any, rhs: Any, enforce_rhs_nonnegative: bool) -> List[str]:
    constraints: List[str] = []
    for expr in (lhs, rhs):
        for node in preorder_traversal(expr):
            func = getattr(node, "func", None)
            func_name = getattr(func, "__name__", str(func))
            if func_name == "sqrt" and len(getattr(node, "args", [])) == 1:
                constraints.append(f"{str(node.args[0])} >= 0")
                continue
            if func_name == "Pow":
                args = getattr(node, "args", ())
                if len(args) == 2 and str(args[1]) in {"1/2", "0.5"}:
                    constraints.append(f"{str(args[0])} >= 0")
                    continue
                if len(args) == 2:
                    exponent = args[1]
                    try:
                        if bool(getattr(exponent, "is_number", False)) and float(exponent) < 0:
                            constraints.append(f"{str(args[0])} != 0")
                    except Exception:
                        pass
            if func_name == "log" and len(getattr(node, "args", [])) >= 1:
                constraints.append(f"{str(node.args[0])} > 0")
    if enforce_rhs_nonnegative:
        constraints.append(f"{str(rhs)} >= 0")
    deduped: List[str] = []
    for item in constraints:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _extract_candidate_numbers(text: str) -> List[S]:
    # Support x = 1,2 and x in {1, 2} shapes.
    matches = re.findall(r"[-+]?\d+(?:\.\d+)?(?:/\d+)?", text or "", flags=re.IGNORECASE)
    out: List[S] = []
    for match in matches:
        try:
            out.append(S(match))
        except Exception:
            continue
    unique: List[S] = []
    for value in out:
        if value not in unique:
            unique.append(value)
    return unique


def _normalize_candidate_values(values: Iterable[Any]) -> List[S]:
    out: List[S] = []
    for value in values:
        if isinstance(value, dict):
            raw = value.get("value_text") or value.get("candidate") or value.get("value")
        else:
            raw = value
        raw_text = str(raw or "").strip()
        if not raw_text:
            continue
        if "=" in raw_text:
            raw_text = raw_text.split("=", 1)[1].strip()
        raw_text = raw_text.strip("{}[]() ")
        if not raw_text:
            continue
        try:
            out.append(S(raw_text))
        except Exception:
            continue
    unique: List[S] = []
    for value in out:
        if value not in unique:
            unique.append(value)
    return unique


def _filter_scalar_candidates(values: Iterable[S]) -> List[S]:
    out: List[S] = []
    for value in values:
        try:
            if bool(getattr(value, "is_number", False)):
                out.append(value)
        except Exception:
            continue
    return out


def _verify_candidate(lhs: Any, rhs: Any, candidate: S, enforce_rhs_nonnegative: bool) -> bool:
    x = Symbol("x")
    try:
        lhs_v = lhs.subs(x, candidate).evalf()
        rhs_v = rhs.subs(x, candidate).evalf()
        lhs_f = float(lhs_v)
        rhs_f = float(rhs_v)
    except Exception:
        return False

    if not math.isfinite(lhs_f) or not math.isfinite(rhs_f):
        return False
    if enforce_rhs_nonnegative and rhs_f < -1e-9:
        return False
    return abs(lhs_f - rhs_f) <= 1e-7


def _extract_llm_answer_text(result: Dict[str, Any]) -> str:
    final_answer = result.get("final_answer")
    if isinstance(final_answer, dict):
        return str(final_answer.get("answer_text") or final_answer.get("answer_latex") or "").strip()
    if isinstance(result.get("solution"), dict):
        nested = result["solution"].get("final_answer") or {}
        if isinstance(nested, dict):
            return str(nested.get("value") or nested.get("latex") or "").strip()
    return str(final_answer or "").strip()


def verify_solve_result(
    problem_text: str,
    result: Dict[str, Any],
    request_id: Optional[str] = None,
    *,
    candidate_values: Optional[Iterable[Any]] = None,
    route: str = "other",
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    llm_answer_text = _extract_llm_answer_text(result)
    output: Dict[str, Any] = {
        "verified": False,
        "verification_method": "none",
        "unverified_reason": "not_applicable",
        "assumptions": [],
        "dropped_candidates": [],
        "final_solutions": [],
        "llm_answer_text": llm_answer_text,
        "symbolic_parse": False,
        "verification_meta": {
            "duration_ms": 0,
            "candidates_checked": 0,
            "symbolic_parse": False,
            "timed_out": False,
            "route": route,
        },
    }

    lhs, rhs = _parse_equation(problem_text)
    if "=" not in (problem_text or ""):
        output["unverified_reason"] = "not_applicable"
        output["verification_meta"] = {
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "candidates_checked": 0,
            "symbolic_parse": False,
            "timed_out": False,
            "route": route,
        }
        return output

    if lhs is None or rhs is None:
        output["unverified_reason"] = "unable_to_verify_symbolically"
        output["verification_meta"] = {
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "candidates_checked": 0,
            "symbolic_parse": False,
            "timed_out": False,
            "route": route,
        }
        emit_runtime_audit(
            component="sympy_verification_gate",
            started_at=started_at,
            request_id=request_id,
            sympy_used=True,
            result="error",
            error_class="symbolic_parse_failed",
            extra={"verified": False, "reason": "symbolic_parse_failed"},
        )
        return output

    output["symbolic_parse"] = True
    output["verification_meta"]["symbolic_parse"] = True
    enforce_rhs_nonnegative = _contains_sqrt_like(lhs)
    constraints = _extract_domain_constraints(lhs, rhs, enforce_rhs_nonnegative)
    output["assumptions"] = constraints

    candidates: List[S] = []
    if candidate_values is not None:
        candidates = _filter_scalar_candidates(_normalize_candidate_values(candidate_values))
    if not candidates:
        verification_block = result.get("verification") if isinstance(result.get("verification"), dict) else {}
        candidates = _filter_scalar_candidates(_normalize_candidate_values(verification_block.get("candidate_solutions") or []))
    if not candidates:
        try:
            solved = solve(Eq(lhs, rhs), Symbol("x"))
            candidates = [value for value in solved if getattr(value, "is_real", False)]
        except Exception:
            candidates = []
    if not candidates:
        candidates = _extract_candidate_numbers(llm_answer_text)

    verified: List[S] = []
    dropped: List[Dict[str, str]] = []
    for candidate in candidates:
        if _verify_candidate(lhs, rhs, candidate, enforce_rhs_nonnegative):
            if candidate not in verified:
                verified.append(candidate)
        else:
            dropped.append({"candidate": str(candidate), "reason": "failed_substitution_or_domain"})

    output["dropped_candidates"] = dropped
    output["final_solutions"] = [str(v) for v in sorted(verified, key=lambda value: float(value))]
    output["verification_method"] = "symbolic"
    output["verified"] = len(verified) > 0
    output["unverified_reason"] = None if output["verified"] else "verification_failed"
    output["verification_meta"] = {
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
        "candidates_checked": len(candidates),
        "symbolic_parse": True,
        "timed_out": False,
        "route": route,
    }

    emit_runtime_audit(
        component="sympy_verification_gate",
        started_at=started_at,
        request_id=request_id,
        sympy_used=True,
        result="ok",
        extra={
            "verified": output["verified"],
            "final_solutions_count": len(output["final_solutions"]),
            "dropped_count": len(dropped),
        },
    )
    return output
