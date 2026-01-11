import re

class MathSpeechNormalizer:
    def __init__(self):
        # Longest-Match-First patterns
        self.patterns = [
            (r"\bequals\b", "="),
            (r"\bplus\b", "+"),
            (r"\bminus\b", "-"),
            (r"\btimes\b", "*"),
            (r"\bmultiplied by\b", "*"),
            (r"\bdivided by\b", "/"),
            (r"\bover\b", "/"),
            (r"\bsquare root of\b", "sqrt"),
            (r"\bsquared\b", "^2"),
            (r"\bcubed\b", "^3"),
            (r"\bto the power of\b", "^"),
            (r"\bx\b", "x"),
            (r"\by\b", "y"),
            (r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten)\b", self._replace_number),
        ]

    def _replace_number(self, match):
        mapping = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
        }
        return mapping[match.group(0)]

    def normalize(self, text: str) -> dict:
        """
        Normalizes text and checks for ambiguities.
        Returns: { "normalized_text": str, "ambiguity_flags": list, "clarifier": dict }
        """
        normalized = text.lower()
        
        # 1. Detection Phase (Before destructive replacements)
        ambiguity_flags = []
        clarifier = None
        
        # POWER_SCOPE Detection: "x plus y squared"
        if re.search(r"(\bplus\b|\bminus\b)\s+\w+\s+\bsquared\b", normalized):
            ambiguity_flags.append("POWER_SCOPE")
            # Generate options
            # Option 1: (x+y)^2
            # Option 2: x+y^2
            # Extract variables (simplified)
            parts = re.split(r"\bplus\b|\bminus\b", normalized)
            if len(parts) >= 2:
                v1 = parts[0].strip()
                v2 = parts[1].replace("squared", "").strip()
                op = "+" if "plus" in normalized else "-"
                clarifier = {
                    "question": f"Did you mean the whole expression {v1} {op} {v2} is squared?",
                    "options": [
                        {"label": f"({v1} {op} {v2})²", "value": f"({v1}{op}{v2})^2"},
                        {"label": f"{v1} {op} {v2}²", "value": f"{v1}{op}{v2}^2"}
                    ]
                }

        # FRACTION_SCOPE Detection: "a plus b over c"
        if not clarifier and re.search(r"(\w+)\s+(\bplus\b|\bminus\b)\s+(\w+)\s+\bover\b\s+(\w+)", normalized):
            ambiguity_flags.append("FRACTION_SCOPE")
            match = re.search(r"(\w+)\s+(\bplus\b|\bminus\b)\s+(\w+)\s+\bover\b\s+(\w+)", normalized)
            v1, op, v2, v3 = match.groups()
            op_sym = "+" if "plus" in op else "-"
            clarifier = {
                "question": f"Is '{v1} {op_sym} {v2}' the entire numerator?",
                "options": [
                    {"label": f"({v1} {op_sym} {v2}) / {v3}", "value": f"({v1}{op_sym}{v2})/{v3}"},
                    {"label": f"{v1} {op_sym} ({v2} / {v3})", "value": f"{v1}{op_sym}({v2}/{v3})"}
                ]
            }
        
        # 2. Replacement Phase
        for pattern, replacement in self.patterns:
            normalized = re.sub(pattern, replacement, normalized)
        
        # Post-processing: remove extra spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()
        
        return {
            "normalized_text": normalized,
            "ambiguity_flags": ambiguity_flags,
            "clarifier": clarifier
        }
