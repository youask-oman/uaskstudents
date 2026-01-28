"""
Local Math Error Localization
==============================
Production-grade error detection using SymPy and numeric validation.
NO LLM calls - fully deterministic.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from sympy import sympify, simplify, symbols, Eq, solve
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

logger = logging.getLogger(__name__)

# Safe transformations for sympify
SAFE_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

def normalize_ocr_text(text: str) -> str:
    """Normalize OCR output for math parsing."""
    if not text:
        return ""
    
    # Replace common OCR artifacts
    replacements = {
        '×': '*',
        '÷': '/',
        '−': '-',
        '–': '-',
        '—': '-',
        '√': 'sqrt',
        '²': '**2',
        '³': '**3',
        '≠': '!=',
        '≈': '~',
        '≤': '<=',
        '≥': '>=',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def split_lines(text: str) -> List[str]:
    """Split text into individual mathematical statements."""
    # Split by newlines and semicolons
    lines = re.split(r'[\n;]', text)
    # Filter empty lines
    return [line.strip() for line in lines if line.strip()]

def parse_statement(line: str) -> Dict[str, Any]:
    """
    Parse a mathematical statement into structured form.
    
    Returns:
        {
            "kind": "equation" | "expression" | "unknown",
            "lhs_str": str (if equation),
            "rhs_str": str (if equation),
            "expr_str": str (if expression),
            "lhs_expr": sympy expr (if parseable),
            "rhs_expr": sympy expr (if parseable),
            "expr": sympy expr (if expression),
            "parse_error": str (if failed)
        }
    """
    result = {
        "kind": "unknown",
        "raw": line,
        "parse_error": None
    }
    
    # Check if it's an equation (contains =)
    if '=' in line:
        parts = line.split('=', 1)
        if len(parts) == 2:
            lhs_str, rhs_str = parts[0].strip(), parts[1].strip()
            result["kind"] = "equation"
            result["lhs_str"] = lhs_str
            result["rhs_str"] = rhs_str
            
            try:
                # Try to parse both sides
                lhs_expr = parse_expr(lhs_str, transformations=SAFE_TRANSFORMATIONS, evaluate=False)
                rhs_expr = parse_expr(rhs_str, transformations=SAFE_TRANSFORMATIONS, evaluate=False)
                result["lhs_expr"] = lhs_expr
                result["rhs_expr"] = rhs_expr
            except Exception as e:
                result["parse_error"] = f"Failed to parse equation: {str(e)}"
                logger.debug(f"Parse error for '{line}': {e}")
    else:
        # It's an expression
        result["kind"] = "expression"
        result["expr_str"] = line
        
        try:
            expr = parse_expr(line, transformations=SAFE_TRANSFORMATIONS, evaluate=False)
            result["expr"] = expr
        except Exception as e:
            result["parse_error"] = f"Failed to parse expression: {str(e)}"
            logger.debug(f"Parse error for '{line}': {e}")
    
    return result

def validate_equation(parsed: Dict[str, Any], timeout_ms: int = 500) -> Dict[str, Any]:
    """
    Validate an equation using symbolic and numeric methods.
    
    Returns:
        {
            "is_correct": bool | None,
            "confidence": float,
            "method": "symbolic" | "numeric" | "failed",
            "residual": float (if numeric),
            "explanation": str
        }
    """
    if parsed.get("parse_error"):
        return {
            "is_correct": None,
            "confidence": 0.0,
            "method": "failed",
            "explanation": parsed["parse_error"]
        }
    
    lhs = parsed.get("lhs_expr")
    rhs = parsed.get("rhs_expr")
    
    if lhs is None or rhs is None:
        return {
            "is_correct": None,
            "confidence": 0.0,
            "method": "failed",
            "explanation": "Could not parse equation"
        }
    
    # Try symbolic simplification
    try:
        diff = simplify(lhs - rhs)
        
        # Check if it simplifies to zero
        if diff == 0:
            return {
                "is_correct": True,
                "confidence": 0.95,
                "method": "symbolic",
                "explanation": "Equation is symbolically correct"
            }
        
        # Check if it's a pure number (no symbols)
        if diff.is_number:
            residual = float(abs(diff))
            is_correct = residual < 1e-10
            return {
                "is_correct": is_correct,
                "confidence": 1.0 if is_correct else 0.98,
                "method": "symbolic",
                "residual": residual,
                "explanation": f"Numeric residual: {residual}"
            }
        
        # Has symbols - try numeric sampling
        free_symbols = diff.free_symbols
        if free_symbols:
            return _numeric_validation(lhs, rhs, list(free_symbols))
        
        # Non-zero symbolic result
        return {
            "is_correct": False,
            "confidence": 0.90,
            "method": "symbolic",
            "explanation": f"Symbolic difference: {diff}"
        }
        
    except Exception as e:
        logger.debug(f"Symbolic validation failed: {e}")
        # Fallback to numeric if possible
        free_symbols = set()
        try:
            free_symbols = lhs.free_symbols | rhs.free_symbols
        except:
            pass
        
        if free_symbols:
            return _numeric_validation(lhs, rhs, list(free_symbols))
        
        return {
            "is_correct": None,
            "confidence": 0.0,
            "method": "failed",
            "explanation": f"Validation error: {str(e)}"
        }

def _numeric_validation(lhs, rhs, free_symbols: List) -> Dict[str, Any]:
    """Validate equation using numeric sampling."""
    try:
        # Sample 10 random points
        n_samples = 10
        residuals = []
        
        for _ in range(n_samples):
            # Generate random values for each symbol
            subs = {}
            for sym in free_symbols:
                # Use safe range to avoid overflow
                subs[sym] = np.random.uniform(-10, 10)
            
            try:
                lhs_val = float(lhs.subs(subs))
                rhs_val = float(rhs.subs(subs))
                residuals.append(abs(lhs_val - rhs_val))
            except (ValueError, ZeroDivisionError, OverflowError):
                # Skip problematic points
                continue
        
        if not residuals:
            return {
                "is_correct": None,
                "confidence": 0.3,
                "method": "numeric",
                "explanation": "Could not evaluate at sample points"
            }
        
        avg_residual = np.mean(residuals)
        max_residual = np.max(residuals)
        
        # If all residuals are tiny, likely correct
        if max_residual < 1e-8:
            return {
                "is_correct": True,
                "confidence": 0.75,
                "method": "numeric",
                "residual": avg_residual,
                "explanation": f"Numeric sampling suggests correct (avg residual: {avg_residual:.2e})"
            }
        
        # If residuals are large, likely incorrect
        if avg_residual > 0.01:
            return {
                "is_correct": False,
                "confidence": 0.70,
                "method": "numeric",
                "residual": avg_residual,
                "explanation": f"Numeric sampling suggests incorrect (avg residual: {avg_residual:.2e})"
            }
        
        # Uncertain
        return {
            "is_correct": None,
            "confidence": 0.40,
            "method": "numeric",
            "residual": avg_residual,
            "explanation": f"Inconclusive (avg residual: {avg_residual:.2e})"
        }
        
    except Exception as e:
        logger.debug(f"Numeric validation failed: {e}")
        return {
            "is_correct": None,
            "confidence": 0.0,
            "method": "failed",
            "explanation": f"Numeric validation error: {str(e)}"
        }

def analyze_error(ocr_text: str, max_lines: int = 6) -> Dict[str, Any]:
    """
    Main analysis function.
    
    Returns:
        {
            "detected_format": str,
            "first_wrong_line_index": int | None,
            "what_is_wrong": str,
            "minimal_fix": str,
            "confidence": float,
            "lines": List[Dict]  # Debug info
        }
    """
    normalized = normalize_ocr_text(ocr_text)
    lines = split_lines(normalized)[:max_lines]
    
    if not lines:
        return {
            "detected_format": "unknown",
            "first_wrong_line_index": None,
            "what_is_wrong": "No text detected",
            "minimal_fix": "Please ensure the selection contains visible text",
            "confidence": 0.0,
            "lines": []
        }
    
    # Parse all lines
    parsed_lines = [parse_statement(line) for line in lines]
    
    # Determine format
    has_equations = any(p["kind"] == "equation" for p in parsed_lines)
    detected_format = "multi_line" if len(lines) > 1 else ("equation" if has_equations else "expression")
    
    # Validate each equation
    results = []
    first_wrong_index = None
    
    for idx, parsed in enumerate(parsed_lines):
        if parsed["kind"] == "equation":
            validation = validate_equation(parsed)
            results.append({
                "line_index": idx,
                "line": lines[idx],
                "parsed": parsed,
                "validation": validation
            })
            
            # Track first incorrect line
            if first_wrong_index is None and validation.get("is_correct") is False:
                first_wrong_index = idx
    
    # Generate output
    if not results:
        return {
            "detected_format": detected_format,
            "first_wrong_line_index": None,
            "what_is_wrong": "No equations found to validate",
            "minimal_fix": "Please select a region containing an equation (with =)",
            "confidence": 0.5,
            "lines": parsed_lines
        }
    
    if first_wrong_index is not None:
        wrong_result = results[first_wrong_index]
        validation = wrong_result["validation"]
        parsed = wrong_result["parsed"]
        
        # Try to compute correct answer
        minimal_fix = "Check your calculation"
        try:
            lhs_val = float(parsed["lhs_expr"].evalf())
            rhs_val = float(parsed["rhs_expr"].evalf())
            if abs(lhs_val - rhs_val) > 1e-6:
                minimal_fix = f"{parsed['lhs_str']} = {lhs_val:.4g}, not {rhs_val:.4g}"
        except:
            pass
        
        return {
            "detected_format": detected_format,
            "first_wrong_line_index": first_wrong_index,
            "what_is_wrong": f"Incorrect equation at line {first_wrong_index + 1}",
            "minimal_fix": minimal_fix,
            "confidence": validation.get("confidence", 0.5),
            "lines": results
        }
    
    # All equations appear correct
    all_confident = all(r["validation"].get("confidence", 0) > 0.7 for r in results)
    
    return {
        "detected_format": detected_format,
        "first_wrong_line_index": None,
        "what_is_wrong": "No errors detected" if all_confident else "Uncertain - equations may be correct",
        "minimal_fix": "All equations appear valid" if all_confident else "Consider manual verification",
        "confidence": min(r["validation"].get("confidence", 0) for r in results) if results else 0.5,
        "lines": results
    }
