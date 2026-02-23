from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Tuple

import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


class SympySafeError(ValueError):
    pass


ALLOWED_FUNCS: Dict[str, object] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sqrt": sp.sqrt,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "abs": sp.Abs,
    "Abs": sp.Abs,
}
ALLOWED_CONSTS: Dict[str, object] = {"pi": sp.pi, "E": sp.E, "e": sp.E}
ALLOWED_SYMBOL_NAMES = {"x", "y", "t", "u", "n"}
FORBIDDEN_TOKEN_RE = re.compile(
    r"(__|import|lambda|eval|exec|open\(|os\.|sys\.|subprocess|@|;|\{|\}|\[|\]|while\s|for\s)",
    re.IGNORECASE,
)


def _normalize_expr_for_eval(expr: str) -> str:
    text = (expr or "").strip()
    if not text:
        return text
    text = (
        text.replace("\\left", "")
        .replace("\\right", "")
        .replace("\\cdot", "*")
        .replace("\\pi", "pi")
        .replace("\\sin", "sin")
        .replace("\\cos", "cos")
        .replace("\\tan", "tan")
        .replace("\\sqrt", "sqrt")
        .replace("\\log", "log")
        .replace("\\ln", "ln")
        .replace("\\exp", "exp")
        .replace("^", "**")
    )
    text = re.sub(r"\b(sin|cos|tan|sqrt|log|ln|exp|abs)\s+([A-Za-z][A-Za-z0-9_]*)", r"\1(\2)", text)
    text = re.sub(r"^\s*y\s*=\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*f\s*\(\s*x\s*\)\s*=\s*", "", text, flags=re.IGNORECASE)
    return text


def latexish_to_sympy(expr: str) -> str:
    return _normalize_expr_for_eval(expr)


def safe_parse_expr(expr: str, *, allowed_symbols: Iterable[str]) -> sp.Expr:
    source = _normalize_expr_for_eval(expr)
    if not source:
        raise SympySafeError("Empty expression")
    if FORBIDDEN_TOKEN_RE.search(source):
        raise SympySafeError("Forbidden token detected")

    symbol_set = set(allowed_symbols)
    unknown = symbol_set - ALLOWED_SYMBOL_NAMES
    if unknown:
        raise SympySafeError(f"Unknown symbol(s) requested: {sorted(unknown)}")

    locals_dict: Dict[str, object] = {}
    for name in symbol_set:
        locals_dict[name] = sp.Symbol(name, real=True)
    locals_dict.update(ALLOWED_FUNCS)
    locals_dict.update(ALLOWED_CONSTS)

    transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
    try:
        parsed = parse_expr(source, local_dict=locals_dict, transformations=transformations, evaluate=True)
    except Exception as exc:  # noqa: BLE001
        raise SympySafeError(f"Parse failed: {exc}") from exc

    extra = {str(sym) for sym in parsed.free_symbols} - symbol_set
    if extra:
        raise SympySafeError(f"Unknown symbols in expression: {sorted(extra)}")
    return parsed


@dataclass(frozen=True)
class CompiledExpr1D:
    source: str
    variable: str
    fn: Callable[[np.ndarray], np.ndarray]


def compile_expr_1d(expr: str, *, variable: str) -> CompiledExpr1D:
    parsed = safe_parse_expr(expr, allowed_symbols=[variable])
    var_symbol = sp.Symbol(variable, real=True)
    fn = sp.lambdify(var_symbol, parsed, modules=["numpy"])
    return CompiledExpr1D(source=str(parsed), variable=variable, fn=fn)


def compile_expr_2d(expr: str) -> Tuple[str, Callable[[np.ndarray, np.ndarray], np.ndarray]]:
    parsed = safe_parse_expr(expr, allowed_symbols=["x", "y"])
    x = sp.Symbol("x", real=True)
    y = sp.Symbol("y", real=True)
    fn = sp.lambdify((x, y), parsed, modules=["numpy"])
    return str(parsed), fn
