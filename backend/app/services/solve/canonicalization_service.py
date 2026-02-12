
import re
import hashlib
import unicodedata
import json
import time
from typing import Tuple, Dict, Any, Optional
from sympy import parse_expr, srepr, simplify, Eq
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations, implicit_multiplication_application,
    convert_xor
)
from app.config import get_settings
from app.services.runtime_audit import emit_runtime_audit

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
        started_at = time.perf_counter()
        audit_result = "ok"
        audit_error_class = None
        # 1. Unicode normalize
        text = unicodedata.normalize('NFKC', text)
        text = text.replace('−', '-').replace('×', '*').replace('÷', '/')
        
        # 2. Extract math token candidates
        clean_text = self._clean_text_for_parsing(text)
        
        # If text is empty after cleaning (e.g. "solve"), fail early
        if not clean_text:
            return "", {"error": "empty_input"}

        try:
            assumptions = {}

            relation = self._parse_relation(clean_text)
            if relation is not None:
                canonical_obj = self.canonicalize_relation(relation)
            else:
                expr = parse_expr(clean_text, transformations=self.transformations)
                if intent == "solve_equation":
                    assumptions["implicit_eq_zero"] = True
                    canonical_obj = self.canonicalize_relation(Eq(expr, 0, evaluate=False))
                else:
                    canonical_obj = self.canonicalize_expression(expr)
            return canonical_obj, assumptions
            
        except Exception as e:
            audit_result = "error"
            audit_error_class = type(e).__name__
            # Fallback: Use robust text normalization for word problems
            # This gives consistent hashes even with OCR variations
            fallback = self._normalize_text_for_hashing(text)
            return fallback, {"parse_error": str(e), "normalized_text": True}
        finally:
            emit_runtime_audit(
                component="sympy_canonicalization",
                started_at=started_at,
                sympy_used=True,
                result=audit_result,
                error_class=audit_error_class,
            )
            
    def _parse_relation(self, clean_text: str) -> Optional[Eq]:
        if clean_text.count("=") != 1:
            return None
        lhs_str, rhs_str = clean_text.split("=", 1)
        lhs = parse_expr(lhs_str, transformations=self.transformations)
        rhs = parse_expr(rhs_str, transformations=self.transformations)
        return Eq(lhs, rhs, evaluate=False)

    def canonicalize_expression(self, expr: Any) -> str:
        simplified = simplify(expr)
        if isinstance(simplified, bool):
            simplified = expr
        return srepr(simplified)

    def canonicalize_relation(self, relation: Eq) -> str:
        # Keep a relation shape for cache keys; normalize to diff == 0.
        normalized = simplify(relation.lhs - relation.rhs)
        if isinstance(normalized, bool):
            normalized = relation.lhs - relation.rhs
        return srepr(Eq(normalized, 0, evaluate=False))

    def _clean_text_for_parsing(self, text: str) -> str:
        # Remove common english command words mostly
        words = ["solve", "for", "please", "find", "the", "calculate", "simplify", "factor", "what", "is", "graph", "plot"]
        pattern = r'\b(' + '|'.join(words) + r')\b'
        cleaned = re.sub(pattern, '', text, flags=re.IGNORECASE)
        # Remove common sentence punctuation
        cleaned = re.sub(r'[?]$', '', cleaned.strip())
        return cleaned.strip()

    def _normalize_text_for_hashing(self, text: str) -> str:
        """
        Aggressively normalize text for consistent hashing.
        Used when SymPy parsing fails (word problems, etc.)
        """
        # Unicode normalize
        text = unicodedata.normalize('NFKC', text)
        
        # Lowercase
        text = text.lower()
        
        # Replace common OCR variations
        text = text.replace('−', '-').replace('×', '*').replace('÷', '/')
        text = text.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
        
        # Normalize whitespace (collapse multiple spaces, newlines -> single space)
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove common sentence-ending punctuation that might vary
        text = re.sub(r'[.!?]+$', '', text)
        
        # Normalize fractions (both forms should hash the same)
        # e.g., "1/5" and "\\frac{1}{5}" -> same form
        text = re.sub(r'\\frac\{(\d+)\}\{(\d+)\}', r'\1/\2', text)
        
        # Remove LaTeX wrappers that might vary
        text = re.sub(r'\$+', '', text)
        text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)  # Remove \textbf{...} -> ...
        
        # For multiple choice, normalize option markers
        text = re.sub(r'\b([A-D])\s*[):\.]', r'\1)', text)
        
        return text

    def compute_canonical_key(self, intent: str, math_obj: str, assumptions: Dict) -> str:
        settings = self.settings
        # Key = sha256(intent + math + assumptions + versions)
        # Use simple separator structure
        ver_str = f"{settings.PROMPT_VERSION}:{settings.SCHEMA_VERSION}:{settings.SOLVER_VERSION}"
        assumptions_str = json.dumps(assumptions, sort_keys=True)
        raw = f"{intent}|{math_obj}|{assumptions_str}|{ver_str}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

canonicalization_service = CanonicalizationService()
