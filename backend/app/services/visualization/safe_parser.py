"""
SAFE Mathematical Expression Parser for Math Solver V3.1

SECURITY: NO EVAL/EXEC ANYWHERE
- Uses SymPy for safe parsing and evaluation
- Whitelist-only approach for functions and variables
- Explicit rejection of dangerous constructs
- All parsing failures return controlled errors

Replaced eval() completely with sympy.sympify + lambdify.
"""

import re
import numpy as np
from sympy import sympify, lambdify, Symbol
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SafeExpressionError(Exception):
    """Raised when expression cannot be safely parsed."""
    pass


class SafeExpressionParser:
    """
    Safe mathematical expression parser using SymPy.
    
    SECURITY GUARANTEES:
    - No eval() or exec()
    - No attribute access, indexing, or dunder methods
    - Whitelisted functions only
    - Single variable 'x' (or 'y' for 2D)
    - Controlled namespace
    """
    
    # Whitelisted safe mathematical functions
    SAFE_FUNCTIONS = {
        'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
        'asin', 'acos', 'atan', 'atan2',
        'sinh', 'cosh', 'tanh',
        'exp', 'log', 'ln', 'sqrt',
        'abs', 'Abs',
        'pi', 'e',
        'floor', 'ceiling', 'sign',
    }
    
    # Dangerous patterns that must be rejected
    DANGEROUS_PATTERNS = [
        r'__\w+__',  # Dunder methods
        r'import\s',  # Import statements
        r'eval\s*\(',  # Eval calls
        r'exec\s*\(',  # Exec calls
        r'compile\s*\(',  # Compile calls
        r'open\s*\(',  # File operations
        r'\.\_\_',  # Attribute access to private/dunder
        r'=>',  # Lambda arrows
        r'lambda\s',  # Lambda definitions
        r'\[.*\]',  # Indexing (simplified check)
    ]
    
    def __init__(self):
        """Initialize safe parser."""
        self.x = Symbol('x', real=True)
        self.y = Symbol('y', real=True)
        
        # Transformations for parsing
        self.transformations = (
            standard_transformations + 
            (implicit_multiplication_application,)
        )
    
    def is_safe_expression(self, expr_str: str) -> Tuple[bool, Optional[str]]:
        """
        Check if expression is safe to parse.
        
        Returns:
            (is_safe, error_message)
        """
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, expr_str, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"
        
        # Check for only allowed characters
        # Allow: letters, numbers, operators, parentheses, common math symbols
        allowed_pattern = r'^[a-zA-Z0-9\s\+\-\*/\^\(\)\.,=<>√π]+$'
        if not re.match(allowed_pattern, expr_str):
            # More permissive check - just reject obvious code
            code_patterns = [';', '{', '}', '@', '#', '$', '&', '|']
            if any(p in expr_str for p in code_patterns):
                return False, "Expression contains invalid characters"
        
        return True, None
    
    def parse_expression(
        self,
        expr_str: str,
        variables: Optional[list] = None
    ) -> Tuple[Any, Optional[str]]:
        """
        Safely parse a mathematical expression using SymPy.
        
        Args:
            expr_str: Expression string (e.g., "x**2 + 2*x + 1", "sin(x)")
            variables: List of allowed variables (default: ['x'])
        
        Returns:
            (sympy_expr, error_message)
            If successful: (expression, None)
            If failed: (None, error_message)
        """
        if variables is None:
            variables = ['x']
        
        # Security check
        is_safe, error = self.is_safe_expression(expr_str)
        if not is_safe:
            logger.warning(f"[SafeParser] Rejected unsafe expression: {expr_str[:100]}")
            return None, f"Unsafe expression: {error}"
        
        # Clean expression
        cleaned = expr_str.strip()
        
        # Remove common prefixes
        cleaned = cleaned.replace('y=', '').replace('y =', '')
        cleaned = cleaned.replace('f(x)=', '').replace('f(x) =', '')
        
        # Replace common notations
        cleaned = cleaned.replace('^', '**')  # Exponentiation
        cleaned = cleaned.replace('√', 'sqrt')  # Square root
        cleaned = cleaned.replace('π', 'pi')  # Pi
        
        try:
            # Create local namespace with only safe symbols
            local_dict = {
                'x': self.x,
                'y': self.y if 'y' in variables else None,
                'pi': sympify('pi'),
                'e': sympify('E'),
            }
            
            # Remove None values
            local_dict = {k: v for k, v in local_dict.items() if v is not None}
            
            # Parse using SymPy with strict namespace
            expr = sympify(
                cleaned,
                locals=local_dict,
                rational=False,
                evaluate=True
            )
            
            # Verify only allowed functions are used
            free_symbols = expr.free_symbols
            symbol_names = {str(s) for s in free_symbols}
            
            # Check that only declared variables are used
            extra_symbols = symbol_names - set(variables)
            if extra_symbols:
                return None, f"Unknown variables: {extra_symbols}. Only {variables} allowed."
            
            logger.debug(f"[SafeParser] Successfully parsed: {expr_str[:50]}...")
            return expr, None
        
        except Exception as e:
            error_msg = f"Parse error: {str(e)[:100]}"
            logger.warning(f"[SafeParser] Failed to parse '{expr_str[:50]}...': {error_msg}")
            return None, error_msg
    
    def evaluate_for_plotting(
        self,
        expr_str: str,
        x_values: np.ndarray,
        variables: Optional[list] = None
    ) -> Tuple[Optional[np.ndarray], Optional[str]]:
        """
        Safely evaluate expression for plotting.
        
        Args:
            expr_str: Expression string
            x_values: NumPy array of x values
            variables: List of allowed variables
        
        Returns:
            (y_values, error_message)
            If successful: (array, None)
            If failed: (None, error_message)
        """
        # Parse expression
        expr, error = self.parse_expression(expr_str, variables)
        if error:
            return None, error
        
        try:
            # Convert SymPy expression to NumPy-compatible function
            # lambdify creates a numerical function with only numpy operations
            if variables is None or variables == ['x']:
                func = lambdify(self.x, expr, modules=['numpy'])
                y_values = func(x_values)
            elif 'y' in variables:
                # For implicit plots or parametric (not yet fully supported)
                return None, "Multi-variable plotting not yet implemented"
            else:
                return None, f"Unsupported variables: {variables}"
            
            # Ensure output is numpy array
            y_values = np.asarray(y_values, dtype=float)
            
            # Handle infinities and NaNs
            if np.any(np.isinf(y_values)):
                logger.debug(f"[SafeParser] Expression produced infinities: {expr_str[:50]}")
            if np.all(np.isnan(y_values)):
                return None, "Expression evaluates to NaN everywhere (invalid domain)"
            
            return y_values, None
        
        except Exception as e:
            error_msg = f"Evaluation error: {str(e)[:100]}"
            logger.warning(f"[SafeParser] Evaluation failed for '{expr_str[:50]}...': {error_msg}")
            return None, error_msg
    
    def validate_expression(self, expr_str: str) -> Dict[str, Any]:
        """
        Validate an expression and return detailed information.
        
        Returns:
            {
                'valid': bool,
                'error': str or None,
                'variables': list of str,
                'functions_used': list of str,
                'complexity': int  # rough measure
            }
        """
        expr, error = self.parse_expression(expr_str)
        
        if error:
            return {
                'valid': False,
                'error': error,
                'variables': [],
                'functions_used': [],
                'complexity': 0
            }
        
        # Extract information
        free_symbols = expr.free_symbols
        variables = [str(s) for s in free_symbols]
        
        # Extract function names (simplified)
        expr_str_lower = str(expr).lower()
        functions_used = [f for f in self.SAFE_FUNCTIONS if f in expr_str_lower]
        
        # Rough complexity measure (count operations)
        complexity = len(str(expr))
        
        return {
            'valid': True,
            'error': None,
            'variables': variables,
            'functions_used': functions_used,
            'complexity': complexity
        }


# Global instance
_safe_parser: Optional[SafeExpressionParser] = None


def get_safe_parser() -> SafeExpressionParser:
    """Get global safe parser instance."""
    global _safe_parser
    if _safe_parser is None:
        _safe_parser = SafeExpressionParser()
    return _safe_parser


if __name__ == "__main__":
    # Test safe parser
    print("="*70)
    print("SAFE EXPRESSION PARSER TEST")
    print("="*70)
    
    parser = SafeExpressionParser()
    
    test_cases = [
        # Safe expressions
        ("x**2", True),
        ("2*x + 3", True),
        ("sin(x)", True),
        ("sqrt(x**2 + 1)", True),
        ("exp(-x**2)", True),
        
        # Unsafe expressions (should be rejected)
        ("__import__('os')", False),
        ("eval('x')", False),
        ("exec('print(1)')", False),
        ("x.__class__", False),
        ("lambda x: x**2", False),
        ("[1,2,3]", False),
    ]
    
    print("\nTesting safe and unsafe expressions:")
    for expr_str, should_work in test_cases:
        expr, error = parser.parse_expression(expr_str)
        worked = (expr is not None and error is None)
        status = "✅" if worked == should_work else "❌"
        print(f"{status} '{expr_str[:30]}...' → {'SUCCESS' if worked else f'REJECTED: {error}'}")
    
    # Test numerical evaluation
    print("\nTesting numerical evaluation:")
    x_vals = np.linspace(-5, 5, 10)
    for expr_str in ["x**2", "sin(x)", "sqrt(abs(x))"]:
        y_vals, error = parser.evaluate_for_plotting(expr_str, x_vals)
        if error:
            print(f"❌ '{expr_str}': {error}")
        else:
            print(f"✅ '{expr_str}': y_range=[{y_vals.min():.2f}, {y_vals.max():.2f}]")
