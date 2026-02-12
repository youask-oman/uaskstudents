# backend/app/services/math/error_localizer.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import re
import time
import math
import signal
import contextlib

import numpy as np
import sympy as sp
from sympy.core.sympify import SympifyError
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor
)
from app.services.runtime_audit import emit_runtime_audit

# Optional SciPy (for root finding, optimization etc.)
try:
    from scipy import optimize
except Exception:  # pragma: no cover
    optimize = None


# -----------------------------
# Safety + normalization helpers
# -----------------------------

SAFE_FUNCS: Dict[str, Any] = {
    # constants
    "pi": sp.pi,
    "e": sp.E,
    # trig
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    # hyperbolic
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    # exp/log/sqrt
    "exp": sp.exp, "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt,
    # calculus limits
    "limit": sp.limit, "lim": sp.limit,
    "inf": sp.oo, "oo": sp.oo,
    # abs
    "abs": sp.Abs,
}

# Disallow dangerous names even if sympify tries to interpret them.
BANNED_TOKENS = {
    "__", "lambda", "import", "exec", "eval", "open", "os", "sys", "subprocess"
}

MATH_ALIASES = {
    "×": "*",
    "∙": "*",
    "·": "*",
    "÷": "/",
    "−": "-",  # unicode minus
    "–": "-",  # en dash (because humans)
    "^": "**",
}

# Common OCR screwups to normalize carefully
OCR_FIXES = [
    # "l" mistaken for "1" in some contexts, but avoid overcorrecting.
    # We'll keep these conservative.
    (r"(?<=\d)\s+(?=\d)", ""),   # remove spaces inside numbers "1 2" -> "12"
    (r"\s+", " "),               # normalize whitespace
]

EQ_SPLIT_RE = re.compile(r"(?<![<>!])=(?!=)")  # split on '=' but avoid '==' etc


@dataclass
class Budget:
    total_ms: int = 1500
    sympy_ms: int = 700
    numeric_ms: int = 700

    def deadline(self) -> float:
        return time.perf_counter() + (self.total_ms / 1000.0)


@dataclass
class OCRPayload:
    raw: str
    text: str
    confidence: float


@dataclass
class LineCheckResult:
    ok: Optional[bool]                 # True/False/None (None=inconclusive)
    confidence: float                  # 0..1
    reason: str                        # short
    minimal_fix: str                   # short, safe
    debug: Dict[str, Any]              # safe small debug info


@dataclass
class FindErrorResult:
    first_wrong_line_index: Optional[int]
    what_is_wrong: str
    minimal_fix: str
    confidence: float
    detected_format: str
    per_line: List[LineCheckResult]


class TimeBudgetExceeded(Exception):
    pass


@contextlib.contextmanager
def time_limit(seconds: float):
    """Hard wall timeout for SymPy operations on Unix."""
    if seconds <= 0:
        yield
        return

    def handler(signum, frame):
        raise TimeBudgetExceeded("time limit exceeded")

    # Only works on main thread, usually fine (FastAPI runs w/ threadpool for certain things, check validity)
    # Windows does NOT support signal.ITIMER_REAL/SIGALRM.
    # We need a fallback or skip for Windows. 
    # Current user OS is Windows. So this block WILL FAIL on Windows.
    # We must modify to just yield if on Windows.
    import platform
    if platform.system() == "Windows":
        yield
        return

    old = signal.signal(signal.SIGALRM, handler)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _contains_banned(s: str) -> bool:
    low = s.lower()
    # Check word boundaries so "cos" doesn't trigger "os"
    for tok in BANNED_TOKENS:
        # Simple regex check for \btoken\b or just token if it's symbol
        # Escape token just in case (though they are simple strings)
        if re.search(r"(?<![a-z0-9_])" + re.escape(tok) + r"(?![a-z0-9_])", low):
            return True
    return False


def normalize_ocr_text(s: str) -> str:
    if not s:
        return ""
    # Apply symbol aliases
    for k, v in MATH_ALIASES.items():
        s = s.replace(k, v)
    # Normalize placeholders (underscores or multiple dots) to 'x'
    s = re.sub(r'_{2,}', 'x', s)
    s = re.sub(r'\.{3,}', 'x', s)
    # Trim
    s = s.strip()
    return s


def split_into_lines(s: str, max_lines: int = 6) -> List[str]:
    # Split by newline or semicolon; keep short lines
    raw_lines = re.split(r"[\n\r;]+", s)
    lines = [ln.strip() for ln in raw_lines if ln.strip()]
    # Sometimes OCR returns everything on one line with commas
    if len(lines) == 1 and s.count("=") >= 2:
        # try splitting by commas too
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if len(parts) > 1:
            lines = parts
    return lines[:max_lines]


def safe_sympify(expr: str) -> sp.Expr:
    if _contains_banned(expr):
        raise SympifyError("banned token present")
    
    # Use SymPy's robust parsing with implicit multiplication (e.g. 2x -> 2*x)
    # and xor conversion (^ -> **)
    transformations = (standard_transformations + 
                       (implicit_multiplication_application, convert_xor))
    
    try:
        return parse_expr(expr, local_dict=SAFE_FUNCS, transformations=transformations, evaluate=False)
    except Exception as e:
        # Fallback for very simple cases or if parse_expr fails (though unlikely)
        # Try raw sympify but be careful
        raise SympifyError(f"Parse failed: {e}")


def parse_statement(line: str) -> Tuple[str, Union[Tuple[sp.Expr, sp.Expr], sp.Expr]]:
    """
    Returns:
      ("eq", (lhs, rhs)) or ("expr", expr)
    """
    line = normalize_ocr_text(line)
    if not line:
        raise SympifyError("empty")

    # Reject obviously hostile strings
    if _contains_banned(line):
        raise SympifyError("banned tokens")

    # If multiple '=' appear, split only first as equation and keep remainder as RHS
    parts = EQ_SPLIT_RE.split(line, maxsplit=1)
    if len(parts) == 2:
        lhs_s, rhs_s = parts[0].strip(), parts[1].strip()
        lhs, rhs = safe_sympify(lhs_s), safe_sympify(rhs_s)
        return "eq", (lhs, rhs)

    # Not an equation
    expr = safe_sympify(line)
    return "expr", expr


# -----------------------------
# Core checking primitives
# -----------------------------

def _numeric_residual(lhs: sp.Expr, rhs: sp.Expr, subs: Dict[sp.Symbol, float]) -> float:
    val = (lhs - rhs).evalf(subs=subs)
    try:
        return float(val)
    except Exception:
        return float("nan")


def _safe_sample_points(symbols: List[sp.Symbol], trials: int = 10) -> List[Dict[sp.Symbol, float]]:
    rng = np.random.default_rng(12345)
    points: List[Dict[sp.Symbol, float]] = []
    for _ in range(trials):
        d: Dict[sp.Symbol, float] = {}
        for sym in symbols:
            v = float(rng.uniform(-5.0, 5.0))
            # avoid tiny denominators
            if abs(v) < 0.25:
                v = 1.0
            d[sym] = v
        points.append(d)
    return points


def prove_equation(lhs: sp.Expr, rhs: sp.Expr, budget: Budget, deadline: float) -> LineCheckResult:
    # Try symbolic proof first (fast, exact)
    t0 = time.perf_counter()
    diff = None
    try:
        # SymPy can hang. Hard cap to sympy_ms (Unix).
        sympy_seconds = max(0.0, min((budget.sympy_ms / 1000.0), deadline - time.perf_counter()))
        with time_limit(sympy_seconds):
            diff = sp.simplify(lhs - rhs)
    except TimeBudgetExceeded:
        pass
    except Exception:
        pass

    # If proved
    if diff is not None and diff == 0:
        return LineCheckResult(
            ok=True,
            confidence=0.98,
            reason="Symbolic proof: LHS equals RHS.",
            minimal_fix="No change needed.",
            debug={"method": "sympy_simplify", "ms": int((time.perf_counter() - t0)*1000)}
        )

    # If purely numeric: compute exact numeric mismatch
    try:
        diff2 = sp.simplify(lhs - rhs) if diff is None else diff
        if diff2 is not None and len(diff2.free_symbols) == 0:
            val = float(diff2.evalf())
            if abs(val) < 1e-9:
                return LineCheckResult(True, 0.99, "Numeric equality holds.", "No change needed.",
                                       {"method": "numeric_exact"})
            # Build minimal fix for numeric eq: compute both sides
            lv = float(lhs.evalf())
            rv = float(rhs.evalf())
            return LineCheckResult(
                ok=False,
                confidence=0.99,
                reason=f"Numeric mismatch: {lv:g} ≠ {rv:g}.",
                minimal_fix=f"Replace RHS with {lv:g} (or recompute).",
                debug={"method": "numeric_exact", "lhs": lv, "rhs": rv}
            )
    except Exception:
        pass

    # Numeric sampling fallback (robust, probabilistic)
    symbols = sorted(list((lhs - rhs).free_symbols), key=lambda s: s.name)
    if not symbols:
        # not proved, not safely numeric => inconclusive
        return LineCheckResult(
            ok=None,
            confidence=0.4,
            reason="Could not determine equality.",
            minimal_fix="Re-circle a clearer region or type the equation.",
            debug={"method": "inconclusive_no_symbols"}
        )

    t1 = time.perf_counter()
    trials = 10
    points = _safe_sample_points(symbols, trials=trials)

    residuals = []
    valid = 0
    for subs in points:
        if time.perf_counter() > deadline:
            break
        r = _numeric_residual(lhs, rhs, subs)
        if math.isfinite(r):
            residuals.append(r)
            valid += 1

    if valid < max(3, trials // 2):
        return LineCheckResult(
            ok=None,
            confidence=0.45,
            reason="Too many invalid points (possible domain issue).",
            minimal_fix="Check denominators, square roots, logs; re-circle or type it.",
            debug={"method": "numeric_sampling", "valid_points": valid}
        )

    med = float(np.median(np.abs(residuals)))
    if med < 1e-6:
        return LineCheckResult(
            ok=True,
            confidence=0.75,
            reason="Likely correct (numeric sampling).",
            minimal_fix="No change needed.",
            debug={"method": "numeric_sampling", "median_abs_residual": med, "ms": int((time.perf_counter()-t1)*1000)}
        )

    return LineCheckResult(
        ok=False,
        confidence=0.85,
        reason=f"Likely incorrect (median |residual| ≈ {med:.3g}).",
        minimal_fix="Recheck arithmetic/algebra in this step.",
        debug={"method": "numeric_sampling", "median_abs_residual": med, "ms": int((time.perf_counter()-t1)*1000)}
    )


# -----------------------------
# Advanced checkers (calculus, linear algebra)
# -----------------------------

def check_derivative_statement(line: str, budget: Budget, deadline: float) -> Optional[LineCheckResult]:
    """
    Supports patterns like:
      d/dx(f(x)) = ...
      derivative of f(x) = ...
    OCR is messy; keep conservative.
    """
    s = normalize_ocr_text(line).lower()
    if "d/dx" not in s and "derivative" not in s:
        return None

    # Try to extract "d/dx( ... ) = ... "
    m = re.search(r"d/dx\((.+)\)\s*=\s*(.+)", s)
    if not m:
        return None

    f_str = m.group(1)
    rhs_str = m.group(2)
    try:
        x = sp.Symbol("x")
        f = safe_sympify(f_str)
        rhs = safe_sympify(rhs_str)
        # compare diff(f,x) == rhs
        lhs = sp.diff(f, x)
        return prove_equation(lhs, rhs, budget, deadline)
    except Exception:
        return LineCheckResult(
            ok=None, confidence=0.45,
            reason="Could not parse derivative statement.",
            minimal_fix="Type the derivative line or re-circle more clearly.",
            debug={"method": "derivative_parse_failed"}
        )


def check_integral_statement(line: str, budget: Budget, deadline: float) -> Optional[LineCheckResult]:
    """
    Supports patterns like:
      int(f(x) dx) = ...
      integral(f(x)) = ...
    """
    s = normalize_ocr_text(line).lower()
    if "int" not in s and "integral" not in s and "∫" not in line:
        return None
    
    # Try common integral patterns
    # int(f(x) dx) = rhs
    m = re.search(r"(?:int|integral|∫)\s*\((.+?)\s*d([a-z])\)\s*=\s*(.+)", s)
    # simpler: int(f(x)) = rhs (assume dx)
    if not m:
        m = re.search(r"(?:int|integral|∫)\s*\((.+)\)\s*=\s*(.+)", s)
        var_char = "x"
    else:
        var_char = m.group(2)

    if not m:
        return None

    f_str = m.group(1)
    rhs_str = m.group(3) if len(m.groups()) == 3 else m.group(2)

    try:
        x = sp.Symbol(var_char)
        f = safe_sympify(f_str)
        rhs = safe_sympify(rhs_str)
        
        # compare integrate(f,x) == rhs
        # Note: Indefinite integrals have +C constant. SymPy returns one antiderivative.
        # So we check diff(rhs, x) == f. Fundamental theorem of calculus (easier to differentiation).
        
        # Check 1: Differentiate RHS and see if it equals f
        diff_rhs = sp.diff(rhs, x)
        res = prove_equation(diff_rhs, f, budget, deadline)
        
        if res.ok:
            return res
        
        # Check 2: Integrate f and compare to rhs (ignoring constant C)
        lhs = sp.integrate(f, x)
        # Check lhs - rhs = constant?
        diff = sp.simplify(lhs - rhs)
        if diff.is_constant():
             return LineCheckResult(
                ok=True, confidence=0.90,
                reason="Integral correct (up to constant).",
                minimal_fix="No change needed.",
                debug={"method": "integral_check_constant"}
            )
            
        return res # Return the initial differentiation check result (likely false)

    except Exception:
         return LineCheckResult(
            ok=None, confidence=0.35,
            reason="Could not parse integral statement.",
            minimal_fix="Check integral notation.",
            debug={"method": "integral_parse_failed"}
        )

def check_limit_statement(line: str, budget: Budget, deadline: float) -> Optional[LineCheckResult]:
    """
    Supports: lim(x->0) f(x) = ...
    """
    s = normalize_ocr_text(line).lower()
    if "lim" not in s: 
        return None
        
    # lim(x->a) f(x) = rhs
    # Regex: lim \s* \( ([a-z]) \s* -> \s* (.*?) \) \s* (.*?) \s* = \s* (.+)
    m = re.search(r"lim\s*\(\s*([a-z])\s*(?:->|to)\s*(.*?)\)\s*(.*?)\s*=\s*(.+)", s)
    if not m:
        return None
    
    var_char = m.group(1)
    target_str = m.group(2)
    f_str = m.group(3)
    rhs_str = m.group(4)
    
    try:
        x = sp.Symbol(var_char)
        target = safe_sympify(target_str)
        f = safe_sympify(f_str)
        rhs = safe_sympify(rhs_str)
        
        lhs = sp.limit(f, x, target)
        return prove_equation(lhs, rhs, budget, deadline)
    except Exception:
        return LineCheckResult(
            ok=None, confidence=0.35,
            reason="Could not parse limit statement.",
            minimal_fix="Check limit notation.",
            debug={"method": "limit_parse_failed"}
        )


def check_matrix_equation(line: str, budget: Budget, deadline: float) -> Optional[LineCheckResult]:
    """
    Very limited: detects bracketed matrices and checks equality numerically.
    Full matrix parsing from OCR is hard; enable only if your OCR returns consistent format.
    """
    s = normalize_ocr_text(line)
    if "[" not in s or "]" not in s or "=" not in s:
        return None
    # Placeholder: implement when OCR format is controlled.
    return None


# -----------------------------
# Main entry point
# -----------------------------

def find_first_error_from_ocr(
    ocr: OCRPayload,
    transcript_hint: str = "",
    max_lines: int = 6,
    budget: Optional[Budget] = None
) -> FindErrorResult:
    started_at = time.perf_counter()

    def _audit(result: FindErrorResult) -> FindErrorResult:
        emit_runtime_audit(
            component="sympy_error_localizer_entry",
            started_at=started_at,
            sympy_used=True,
            numpy_used=True,
            extra={
                "lines": len(result.per_line or []),
                "first_wrong_line_index": result.first_wrong_line_index,
                "detected_format": result.detected_format,
            },
        )
        return result

    budget = budget or Budget()
    deadline = budget.deadline()

    text = normalize_ocr_text(ocr.text)
    lines = split_into_lines(text, max_lines=max_lines)
    if not lines:
        return _audit(FindErrorResult(
            first_wrong_line_index=None,
            what_is_wrong="No readable math detected in the selected region.",
            minimal_fix="Re-circle a larger/clearer region or type the equation.",
            confidence=0.2,
            detected_format="unknown",
            per_line=[]
        ))

    per_line: List[LineCheckResult] = []
    detected_format = "multi_line" if len(lines) > 1 else "unknown"

    for idx, line in enumerate(lines):
        if time.perf_counter() > deadline:
            per_line.append(LineCheckResult(
                ok=None, confidence=0.35,
                reason="Time budget exceeded.",
                minimal_fix="Try a smaller selection or type the equation.",
                debug={"method": "budget_exceeded"}
            ))
            break

        # Specialized calculus checker first (optional)
        deriv_res = check_derivative_statement(line, budget, deadline)
        if deriv_res is not None:
            per_line.append(deriv_res)
            if deriv_res.ok is False:
                return _audit(FindErrorResult(
                    first_wrong_line_index=idx,
                    what_is_wrong=deriv_res.reason,
                    minimal_fix=deriv_res.minimal_fix,
                    confidence=min(1.0, max(deriv_res.confidence, ocr.confidence)),
                    detected_format="equation",
                    per_line=per_line
                ))
            continue

        # Specialized integral checker
        int_res = check_integral_statement(line, budget, deadline)
        if int_res is not None:
             per_line.append(int_res)
             if int_res.ok is False:
                return _audit(FindErrorResult(
                    first_wrong_line_index=idx,
                    what_is_wrong=int_res.reason,
                    minimal_fix=int_res.minimal_fix,
                    confidence=min(1.0, max(int_res.confidence, ocr.confidence)),
                    detected_format="equation",
                    per_line=per_line
                ))
             continue

        # Specialized limit checker
        lim_res = check_limit_statement(line, budget, deadline)
        if lim_res is not None:
             per_line.append(lim_res)
             if lim_res.ok is False:
                return _audit(FindErrorResult(
                    first_wrong_line_index=idx,
                    what_is_wrong=lim_res.reason,
                    minimal_fix=lim_res.minimal_fix,
                    confidence=min(1.0, max(lim_res.confidence, ocr.confidence)),
                    detected_format="equation",
                    per_line=per_line
                ))
             continue

        try:
            kind, parsed = parse_statement(line)
            if kind == "eq":
                detected_format = "equation" if len(lines) == 1 else "multi_line"
                lhs, rhs = parsed  # type: ignore
                res = prove_equation(lhs, rhs, budget, deadline)
                per_line.append(res)

                if res.ok is False:
                    # High-quality minimal fix for purely numeric equation if available
                    return _audit(FindErrorResult(
                        first_wrong_line_index=idx,
                        what_is_wrong=res.reason,
                        minimal_fix=res.minimal_fix,
                        confidence=min(1.0, max(res.confidence, ocr.confidence)),
                        detected_format=detected_format,
                        per_line=per_line
                    ))

            else:
                # expression only (not an equation) -> inconclusive for "find error" unless transcript asks eval
                detected_format = "expression"
                per_line.append(LineCheckResult(
                    ok=None,
                    confidence=0.45,
                    reason="Detected an expression, not an equation.",
                    minimal_fix="Include '=' in the selected region, or type the full statement.",
                    debug={"method": "expr_only"}
                ))

        except Exception:
            per_line.append(LineCheckResult(
                ok=None,
                confidence=0.35,
                reason="Could not parse OCR into math.",
                minimal_fix="Re-circle more clearly or type the equation.",
                debug={"method": "parse_failed", "line": line[:120]}
            ))

    # If we got here, nothing was clearly wrong
    best_conf = max([r.confidence for r in per_line], default=0.4)
    return _audit(FindErrorResult(
        first_wrong_line_index=None,
        what_is_wrong="No definite error found in the selected region.",
        minimal_fix="If you expected an error, expand the selection to include the full step (including '=').",
        confidence=min(0.9, max(best_conf, ocr.confidence)),
        detected_format=detected_format,
        per_line=per_line
    ))
