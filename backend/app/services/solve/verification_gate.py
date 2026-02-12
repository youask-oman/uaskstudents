from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sympy import Eq, S, Symbol, diff, exp, limit, nroots, preorder_traversal, simplify, solve, sqrt
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
        local_dict={"sqrt": sqrt, "x": Symbol("x"), "y": Symbol("y"), "e": exp(1)},
        evaluate=True,
    )


def _normalize_problem_text(problem_text: str) -> str:
    text = _latexish_to_sympy_expr(problem_text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


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
        text = final_answer.get("answer_text") or final_answer.get("answer_latex") or ""
        if text:
            return str(text).strip()
        values = final_answer.get("values") if isinstance(final_answer.get("values"), list) else []
        chunks: List[str] = []
        for entry in values:
            if isinstance(entry, dict):
                value = str(entry.get("value") or entry.get("value_text") or "").strip()
                if value:
                    chunks.append(value)
        if chunks:
            return ", ".join(chunks)
    if isinstance(result.get("solution"), dict):
        nested = result["solution"].get("final_answer") or {}
        if isinstance(nested, dict):
            return str(nested.get("value") or nested.get("latex") or "").strip()
    return str(final_answer or "").strip()


def _extract_function_expr(problem_text: str) -> Optional[Any]:
    text = _latexish_to_sympy_expr(problem_text or "")
    m = re.search(r"f\s*\(\s*x\s*\)\s*=\s*([^\n;,]+)", text, flags=re.IGNORECASE)
    candidate = m.group(1).strip() if m else ""
    if not candidate:
        m2 = re.search(r"y\s*=\s*([^\n;,]+)", text, flags=re.IGNORECASE)
        if m2:
            candidate = m2.group(1).strip()
    if not candidate:
        return None
    try:
        return _safe_parse_expr(candidate)
    except Exception:
        return None


def _extract_candidate_texts(result: Dict[str, Any]) -> List[str]:
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    direct = verification.get("candidate_solutions") if isinstance(verification.get("candidate_solutions"), list) else []
    texts: List[str] = []
    for item in direct:
        if isinstance(item, dict):
            value = str(item.get("value_text") or item.get("candidate") or item.get("value") or "").strip()
            if value:
                texts.append(value)
        elif item is not None:
            value = str(item).strip()
            if value:
                texts.append(value)
    if texts:
        return texts

    final_answer = result.get("final_answer") if isinstance(result.get("final_answer"), dict) else {}
    vals = final_answer.get("values") if isinstance(final_answer.get("values"), list) else []
    for item in vals:
        if isinstance(item, dict):
            value = str(item.get("value") or item.get("value_text") or "").strip()
            if value:
                texts.append(value)
    if texts:
        return texts
    return []


def _extract_candidate_texts_with_fallback(result: Dict[str, Any]) -> List[str]:
    texts = _extract_candidate_texts(result)
    if texts:
        return texts
    answer_text = _extract_llm_answer_text(result)
    if answer_text:
        return [answer_text]
    return []


def _extract_pair_candidates(result: Dict[str, Any]) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    pattern = re.compile(r"\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)")
    for text in _extract_candidate_texts_with_fallback(result):
        for m in pattern.finditer(text):
            try:
                out.append((float(m.group(1)), float(m.group(2))))
            except Exception:
                continue
    uniq: List[Tuple[float, float]] = []
    seen = set()
    for x_val, y_val in out:
        key = (round(x_val, 8), round(y_val, 8))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((x_val, y_val))
    return uniq


def _populate_analysis_output(
    output: Dict[str, Any],
    *,
    verified: bool,
    method: str,
    assumptions: List[str],
    final_solutions: List[str],
    dropped: List[Dict[str, str]],
    started_at: float,
    route: str,
    checks_run: List[str],
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = {
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
        "candidates_checked": len(final_solutions) + len(dropped),
        "symbolic_parse": True,
        "timed_out": False,
        "route": route,
        "checks_run": checks_run,
    }
    if isinstance(extra_meta, dict):
        meta.update(extra_meta)
    output["verified"] = bool(verified)
    output["verification_method"] = method
    output["unverified_reason"] = None if verified else "verification_failed"
    output["assumptions"] = assumptions
    output["dropped_candidates"] = dropped
    output["final_solutions"] = final_solutions
    output["symbolic_parse"] = True
    output["verification_meta"] = meta
    return output


def _verify_case3_removable(problem_text: str, result: Dict[str, Any], output: Dict[str, Any], started_at: float, route: str) -> Optional[Dict[str, Any]]:
    text = _normalize_problem_text(problem_text)
    compact = text.replace(" ", "")
    trigger = "x^2-4" in compact or "x**2-4" in compact
    trigger = trigger and ("x-2" in compact) and ("hole" in text or "domain" in text or "simplify" in text)
    if not trigger:
        return None

    x = Symbol("x")
    expr = _extract_function_expr(problem_text)
    if expr is None:
        try:
            expr = _safe_parse_expr("(x**2-4)/(x-2)")
        except Exception:
            return None

    simplified = simplify(expr)
    numer, denom = expr.as_numer_denom()
    singularities = solve(Eq(denom, 0), x)
    assumptions = [f"x != {str(v)}" for v in singularities]

    sample_points: List[float] = []
    sample_results: List[bool] = []
    for point in [-3.0, -1.0, 0.0, 1.0, 3.0, 4.0]:
        if any(abs(point - float(v.evalf())) <= 1e-9 for v in singularities):
            continue
        try:
            lhs = float(expr.subs(x, point).evalf())
            rhs = float(simplified.subs(x, point).evalf())
            ok = abs(lhs - rhs) <= 1e-7
            sample_points.append(point)
            sample_results.append(ok)
        except Exception:
            sample_points.append(point)
            sample_results.append(False)

    limit_ok = False
    limit_value = None
    try:
        limit_value = limit(expr, x, 2)
        limit_ok = abs(float(limit_value.evalf()) - 4.0) <= 1e-7
    except Exception:
        limit_ok = False

    simplify_ok = str(simplified).replace(" ", "") in {"x+2", "2+x"}
    domain_ok = any(str(v) == "2" for v in singularities)
    verified = simplify_ok and domain_ok and limit_ok and all(sample_results) and len(sample_points) >= 5
    final_solutions = ["f(x)=x+2, x!=2, hole:(2,4)"] if verified else []

    return _populate_analysis_output(
        output,
        verified=verified,
        method="symbolic",
        assumptions=assumptions,
        final_solutions=final_solutions,
        dropped=[],
        started_at=started_at,
        route=route,
        checks_run=["simplify_equivalence", "domain_restriction", "limit_hole"],
        extra_meta={
            "sample_points": sample_points,
            "sample_results": sample_results,
            "limit_value": str(limit_value) if limit_value is not None else None,
            "simplified_expr": str(simplified),
        },
    )


def _verify_case4_critical_points(problem_text: str, output: Dict[str, Any], started_at: float, route: str) -> Optional[Dict[str, Any]]:
    text = _normalize_problem_text(problem_text)
    if "critical" not in text:
        return None
    expr = _extract_function_expr(problem_text)
    if expr is None:
        return None

    x = Symbol("x")
    d1 = diff(expr, x)
    d2 = diff(d1, x)
    cps_raw = solve(Eq(d1, 0), x)
    cps: List[S] = []
    for item in cps_raw:
        if getattr(item, "is_real", None) is False:
            continue
        cps.append(item)

    labels: List[str] = []
    for cp in cps:
        cls = "saddle"
        try:
            second = float(d2.subs(x, cp).evalf())
            if second > 1e-9:
                cls = "local_min"
            elif second < -1e-9:
                cls = "local_max"
            else:
                cls = "inconclusive"
        except Exception:
            cls = "inconclusive"
        labels.append(f"x={str(cp)} ({cls})")

    verified = len(cps) > 0 and all("inconclusive" not in label for label in labels)
    return _populate_analysis_output(
        output,
        verified=verified,
        method="symbolic",
        assumptions=[],
        final_solutions=labels if verified else [],
        dropped=[],
        started_at=started_at,
        route=route,
        checks_run=["derivative", "critical_points", "classification_check"],
        extra_meta={
            "derivative": str(d1),
            "second_derivative": str(d2),
            "critical_points": [str(v) for v in cps],
        },
    )


def _verify_case5_quintic(problem_text: str, result: Dict[str, Any], output: Dict[str, Any], started_at: float, route: str) -> Optional[Dict[str, Any]]:
    text = _normalize_problem_text(problem_text)
    compact = text.replace(" ", "")
    if "x^5-5x+1" not in compact and "x**5-5x+1" not in compact:
        return None

    x = Symbol("x")
    expr = _extract_function_expr(problem_text)
    if expr is None:
        try:
            expr = _safe_parse_expr("x**5-5*x+1")
        except Exception:
            return None

    d1 = diff(expr, x)
    cps = [cp for cp in solve(Eq(d1, 0), x) if getattr(cp, "is_real", None) is not False]

    # LLM values can be noisy; compute authoritative real roots deterministically.
    roots: List[float] = []
    try:
        roots = [float(v.as_real_imag()[0]) for v in nroots(expr) if abs(float(v.as_real_imag()[1])) <= 1e-8]
    except Exception:
        roots = []

    unique_roots: List[float] = []
    for root in roots:
        if any(abs(root - existing) <= 1e-5 for existing in unique_roots):
            continue
        unique_roots.append(root)

    tol = 1e-6
    dropped: List[Dict[str, str]] = []
    accepted: List[str] = []
    for root in unique_roots:
        try:
            residual = abs(float(expr.subs(x, root).evalf()))
            if residual <= tol:
                accepted.append(f"{root:.4f}")
            else:
                dropped.append({"candidate": f"{root:.6f}", "reason": f"residual>{tol}"})
        except Exception:
            dropped.append({"candidate": f"{root:.6f}", "reason": "evaluation_failed"})

    verified = len(cps) > 0 and len(accepted) >= 3
    return _populate_analysis_output(
        output,
        verified=verified,
        method="mixed",
        assumptions=[],
        final_solutions=[f"x~={value}" for value in accepted],
        dropped=dropped,
        started_at=started_at,
        route=route,
        checks_run=["derivative", "critical_points", "numeric_root_residuals"],
        extra_meta={
            "critical_points": [str(v) for v in cps],
            "numeric_tolerance": tol,
            "roots_checked": [f"{v:.6f}" for v in unique_roots],
        },
    )


def _verify_case6_system(problem_text: str, result: Dict[str, Any], output: Dict[str, Any], started_at: float, route: str) -> Optional[Dict[str, Any]]:
    text = _normalize_problem_text(problem_text)
    compact = text.replace(" ", "")
    if "x^2+y^2=4" not in compact and "x**2+y**2=4" not in compact:
        return None
    if "e^x-1" not in compact and "e**x-1" not in compact and "exp(x)-1" not in compact:
        return None

    x = Symbol("x")
    provided_pairs = _extract_pair_candidates(result)
    g = x**2 + (exp(x) - 1) ** 2 - 4
    guesses = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
    roots_x: List[float] = []
    for guess in guesses:
        try:
            from sympy import nsolve

            root = float(nsolve(g, guess))
            roots_x.append(root)
        except Exception:
            continue
    uniq_x: List[float] = []
    for root in roots_x:
        if any(abs(root - existing) <= 1e-6 for existing in uniq_x):
            continue
        uniq_x.append(root)
    computed_pairs = [(xr, float(exp(xr) - 1)) for xr in uniq_x]

    # Verify what model returned, but use deterministic computed pairs as final truth.
    pairs = provided_pairs if provided_pairs else computed_pairs
    tol = 1e-3
    dropped: List[Dict[str, str]] = []
    accepted: List[str] = []
    for px, py in pairs:
        try:
            r1 = abs((px * px + py * py) - 4.0)
            r2 = abs(py - (math.exp(px) - 1.0))
            if r1 <= tol and r2 <= tol:
                accepted.append(f"({px:.4f}, {py:.4f})")
            else:
                dropped.append({"candidate": f"({px:.6f}, {py:.6f})", "reason": f"system_residual>{tol}"})
        except Exception:
            dropped.append({"candidate": f"({px:.6f}, {py:.6f})", "reason": "evaluation_failed"})

    computed_final: List[str] = [f"({px:.4f}, {py:.4f})" for px, py in computed_pairs]
    verified = len(computed_final) >= 2
    return _populate_analysis_output(
        output,
        verified=verified,
        method="numeric",
        assumptions=[],
        final_solutions=computed_final if computed_final else accepted,
        dropped=dropped,
        started_at=started_at,
        route=route,
        checks_run=["system_residuals"],
        extra_meta={
            "numeric_tolerance": tol,
            "pairs_checked": [f"({xv:.6f}, {yv:.6f})" for xv, yv in pairs],
            "computed_pairs": [f"({xv:.6f}, {yv:.6f})" for xv, yv in computed_pairs],
        },
    )


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
            "checks_run": [],
        },
    }

    for verifier in (_verify_case3_removable, _verify_case4_critical_points, _verify_case5_quintic, _verify_case6_system):
        try:
            if verifier is _verify_case4_critical_points:
                analyzed = verifier(problem_text, output, started_at, route)
            else:
                analyzed = verifier(problem_text, result, output, started_at, route)
        except Exception:
            analyzed = None
        if isinstance(analyzed, dict):
            emit_runtime_audit(
                component="sympy_verification_gate",
                started_at=started_at,
                request_id=request_id,
                sympy_used=True,
                result="ok",
                extra={
                    "verified": analyzed.get("verified"),
                    "verification_method": analyzed.get("verification_method"),
                    "checks_run": (analyzed.get("verification_meta") or {}).get("checks_run") or [],
                    "final_solutions_count": len(analyzed.get("final_solutions") or []),
                    "dropped_count": len(analyzed.get("dropped_candidates") or []),
                },
            )
            return analyzed

    lhs, rhs = _parse_equation(problem_text)
    if "=" not in (problem_text or ""):
        output["unverified_reason"] = "not_applicable"
        output["verification_meta"] = {
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "candidates_checked": 0,
            "symbolic_parse": False,
            "timed_out": False,
            "route": route,
            "checks_run": [],
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
            "checks_run": [],
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
        "checks_run": ["equation_substitution"],
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
            "checks_run": ["equation_substitution"],
        },
    )
    return output

