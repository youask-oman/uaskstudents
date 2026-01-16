
import re
import hashlib
import unicodedata
import json
from typing import Tuple, Dict, Any, Optional
from sympy import parse_expr, srepr, simplify, Eq, Symbol
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations, implicit_multiplication_application,
    convert_xor
)
from app.config import get_settings

class CanonicalizationService:
    def __init__(self):
        self.settings = get_settings()
        self.transformations = (standard_transformations + 
            (implicit_multiplication_application, convert_xor))

    def get_intent(self, text: str) -> str:
        text = text.lower()
        if any(w in text for w in ["graph", "plot"]):
            return "graph"
        if "factor" in text:
            return "factor"
        if "simplify" in text:
            return "simplify"
        if any(w in text for w in ["evaluate", "when", "calculate"]):
            return "evaluate"
        if any(w in text for w in ["what is", "explain", "define", "concept"]):
            return "explain"
        
        # Defaults
        # Check for solve last or as default?
        if any(w in text for w in ["solve", "solution", "root", "zero", "find"]):
            return "solve_equation"
            
        return "solve_equation" # Most common math query default

    def normalize_math_object(self, text: str, intent: str) -> Tuple[str, Dict[str, Any]]:
        # 1. Unicode normalize
        text = unicodedata.normalize('NFKC', text)
        text = text.replace('−', '-').replace('×', '*').replace('÷', '/')
        
        # 2. Extract math token candidates
        clean_text = self._clean_text_for_parsing(text)
        
        # If text is empty after cleaning (e.g. "solve"), fail early
        if not clean_text:
            return "", {"error": "empty_input"}

        try:
            # 3. Handle "=" manually (SymPy parse_expr dislikes "=")
            if "=" in clean_text:
                parts = clean_text.split("=")
                if len(parts) == 2:
                    lhs_str, rhs_str = parts[0], parts[1]
                    lhs = parse_expr(lhs_str, transformations=self.transformations)
                    rhs = parse_expr(rhs_str, transformations=self.transformations)
                    expr = Eq(lhs, rhs)
                else:
                    # Multiple =, take first? or parser error
                    expr = parse_expr(clean_text.replace("=", "=="), transformations=self.transformations)
            else:
                expr = parse_expr(clean_text, transformations=self.transformations)

            assumptions = {}

            # 4. Handle Equation vs Expression Logic
            if intent == "solve_equation":
                if not isinstance(expr, Eq) and not isinstance(expr, bool): # bool can happen if 1==1
                    # default expr=0
                    expr = Eq(expr, 0)
                    assumptions["implicit_eq_zero"] = True
            
            # 5. Canonical String
            # Using srepr() ensures structural uniqueness (x+y vs y+x might differ?)
            # Actually srepr doesn't sort Commutative ops by default in all versions.
            # But SymPy expressions usually auto-sort args of Add/Mul.
            # So srepr(x+y) should be same as srepr(y+x).
            
            canonical_obj = srepr(expr)
            return canonical_obj, assumptions
            
        except Exception as e:
            # Fallback: Normalize whitespace and lower case as "math object"
            # This allows "semantic" cache or just basic string match to still work partially
            fallback = re.sub(r'\s+', '', clean_text).lower()
            return fallback, {"parse_error": str(e)}

    def _clean_text_for_parsing(self, text: str) -> str:
        # Remove common english command words mostly
        words = ["solve", "for", "please", "find", "the", "calculate", "simplify", "factor", "what", "is", "graph", "plot"]
        pattern = r'\b(' + '|'.join(words) + r')\b'
        cleaned = re.sub(pattern, '', text, flags=re.IGNORECASE)
        # Remove common sentence punctuation
        cleaned = re.sub(r'[?]$', '', cleaned.strip())
        return cleaned.strip()

    def compute_canonical_key(self, intent: str, math_obj: str, assumptions: Dict) -> str:
        settings = self.settings
        # Key = sha256(intent + math + assumptions + versions)
        # Use simple separator structure
        ver_str = f"{settings.PROMPT_VERSION}:{settings.SCHEMA_VERSION}:{settings.SOLVER_VERSION}"
        assumptions_str = json.dumps(assumptions, sort_keys=True)
        raw = f"{intent}|{math_obj}|{assumptions_str}|{ver_str}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

canonicalization_service = CanonicalizationService()
