import sympy as sp
import re
import time
from typing import List, Dict, Any, Optional
from app.services.runtime_audit import emit_runtime_audit

def generate_local_steps(expr_str: str) -> List[str]:
    """
    Generate procedural steps for a math problem locally using SymPy.
    Supports:
    1. Percent/Fraction to Decimal/Percent conversions
    2. Algebraic simplification
    3. Basic arithmetic with fractions
    """
    started_at = time.perf_counter()
    steps = []
    expr_str = expr_str.strip().lower()

    # Normalize placeholders (underscores or multiple dots) to 'x'
    expr_str = re.sub(r'_{2,}', 'x', expr_str)
    expr_str = re.sub(r'\.{3,}', 'x', expr_str)

    # 0. Handle Equations (Solve for x)
    # Example: "4x-3/5 - 2x-3/2 = -2" or "50 + 60 = ___"
    if "=" in expr_str or "solve" in expr_str or ("x" in expr_str and any(c in expr_str for c in "+-*/")):
        result = _handle_equations(expr_str)
        emit_runtime_audit(
            component="sympy_step_generator_entry",
            started_at=started_at,
            sympy_used=True,
            extra={"steps_count": len(result)},
        )
        return result

    # 1. Handle "Write X as a decimal/percent"
    if "as a decimal" in expr_str or "as a percent" in expr_str:
        result = _handle_conversions(expr_str)
        emit_runtime_audit(
            component="sympy_step_generator_entry",
            started_at=started_at,
            sympy_used=True,
            extra={"steps_count": len(result)},
        )
        return result

    # 2. Handle Algebraic Expressions (Simplify/Evaluate)
    # Catch-all for any string with numbers and math operators
    has_math = any(c.isdigit() for c in expr_str) and any(c in expr_str for c in "+-*/^")
    if "simplify" in expr_str or has_math:
        result = _handle_simplification(expr_str)
        emit_runtime_audit(
            component="sympy_step_generator_entry",
            started_at=started_at,
            sympy_used=True,
            extra={"steps_count": len(result)},
        )
        return result

    result = ["No specific local solving rule matched for this query."]
    emit_runtime_audit(
        component="sympy_step_generator_entry",
        started_at=started_at,
        sympy_used=True,
        extra={"steps_count": len(result)},
    )
    return result

def _handle_equations(query: str) -> List[str]:
    steps = []
    # Clean query
    clean_q = query.replace('solve for', '').strip()
    
    # Check if there is an '=' sign. If not, it might be an implicit equation (=0)
    if "=" not in clean_q:
        clean_q += " = 0"
    
    try:
        from sympy.abc import x, y, a, b, c, d
        parts = clean_q.split('=')
        lhs_str = parts[0].strip()
        rhs_str = parts[1].strip()

        transformations = (
            sp.parsing.sympy_parser.standard_transformations +
            (sp.parsing.sympy_parser.implicit_multiplication_application,)
        )
        lhs = sp.parse_expr(lhs_str, transformations=transformations)
        rhs = sp.parse_expr(rhs_str, transformations=transformations)
        
        eq = sp.Eq(lhs, rhs)
        steps.append(f"1. Set up the equation: ${sp.latex(lhs)} = {sp.latex(rhs)}$")
        
        # Move everything to LHS
        standard_form = lhs - rhs
        steps.append(f"2. Move all terms to one side: ${sp.latex(standard_form)} = 0$")
        
        # Simplify standard form
        simplified_form = sp.simplify(standard_form)
        if simplified_form != standard_form:
            steps.append(f"3. Simplify the expression: ${sp.latex(simplified_form)} = 0$")
        
        # Solve
        solutions = sp.solve(eq)
        
        if not solutions:
            steps.append("**No real solutions found.**")
        else:
            sol_str = ", ".join([f"${sp.latex(s)}$" for s in solutions])
            steps.append(f"**Final Answer: {sol_str}**")

    except Exception as e:
        return [f"Could not solve equation: {str(e)}"]

    return steps

def _handle_conversions(query: str) -> List[str]:
    steps = []
    # Extract number or fraction
    # Regex for mixed fractions like "12 1/2" or "12.5"
    match = re.search(r'([\d\s\./]+)%?', query)
    if not match:
        return ["Could not identify the number to convert."]
    
    val_str = match.group(1).strip()
    is_percent = "%" in query or "%" in val_str
    
    # Simple mixed fraction parsing: "12 1/2" -> 12 + 1/2
    try:
        if " " in val_str:
            parts = val_str.split()
            whole = float(parts[0])
            frac_parts = parts[1].split('/')
            frac = float(frac_parts[0]) / float(frac_parts[1])
            val = whole + frac
            steps.append(f"1. Convert mixed fraction to improper/decimal: {val_str} = {val}")
        elif "/" in val_str:
            parts = val_str.split('/')
            val = float(parts[0]) / float(parts[1])
            steps.append(f"1. Evaluate fraction: {val_str} = {val}")
        else:
            val = float(val_str)
            steps.append(f"1. Identify value: {val}")

        if "as a decimal" in query:
            if is_percent:
                res = val / 100
                steps.append(f"2. Convert percent to decimal (divide by 100): {val}% / 100 = {res}")
                steps.append(f"**Final Answer: {res}**")
            else:
                steps.append(f"**Final Answer: {val}**")
        
        elif "as a percent" in query:
            res = val * 100
            steps.append(f"2. Convert to percent (multiply by 100): {val} * 100 = {res}%")
            steps.append(f"**Final Answer: {res}%**")

    except Exception as e:
        return [f"Error in conversion: {str(e)}"]

    return steps

def _handle_simplification(query: str) -> List[str]:
    steps = []
    # Clean query: Remove "simplify" and leading numbers/dots from OCR
    clean_expr = re.sub(r'^\d+\.\s*', '', query)
    clean_expr = clean_expr.replace('simplify', '').strip()
    
    try:
        # Define common symbols
        from sympy.abc import x, y, a, b, c, d
        # Standardize OCR artifacts: 'A' vs 'a'
        clean_expr = clean_expr.lower()
        
        # Parse expression
        expr = sp.parse_expr(clean_expr, transformations=(
            sp.parsing.sympy_parser.standard_transformations +
            (sp.parsing.sympy_parser.implicit_multiplication_application,)
        ))
        
        steps.append(f"1. Original expression: ${sp.latex(expr)}$")
        
        # Show intermediate expansion if relevant
        expanded = sp.expand(expr)
        if expanded != expr:
            steps.append(f"2. Expand terms: ${sp.latex(expanded)}$")
        
        # Final simplification
        simplified = sp.simplify(expanded)
        steps.append(f"**Final Result: ${sp.latex(simplified)}$**")
        
    except Exception as e:
        return [f"Could not simplify expression: {str(e)}"]
        
    return steps
