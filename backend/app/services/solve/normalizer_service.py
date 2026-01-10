import re
import hashlib
import json
from typing import Dict, Any

class ProblemNormalizerService:
    """
    Normalizes structured medical/math problem data for deterministic hashing.
    Used to identify duplicate problems even with minor whitespace or punctuation changes.
    """
    
    def normalize_text(self, text: str) -> str:
        if not text: return ""
        # 1. Lowercase
        text = text.lower()
        # 2. Collapse all whitespace
        text = re.sub(r'\s+', '', text)
        # 3. Normalize punctuation
        text = re.sub(r'[.,!?;:]', '', text)
        # 4. Standardize math symbols
        text = text.replace('−', '-').replace('×', '*').replace('÷', '/')
        return text

    def get_hash(self, problem_json: Dict[str, Any]) -> str:
        """
        Computes a stable hash from standardized problem fields.
        """
        # We focus on the core question text and sorted choices for the hash
        q_text = self.normalize_text(problem_json.get("question", ""))
        
        choices = problem_json.get("choices", {}) or {}
        sorted_choices = []
        for key in sorted(["A", "B", "C", "D"]):
            if key in choices:
                sorted_choices.append(f"{key}:{self.normalize_text(choices[key])}")
        
        # Combine and hash
        canonical_string = f"q:{q_text}|c:{'|'.join(sorted_choices)}"
        return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()

problem_normalizer_service = ProblemNormalizerService()
