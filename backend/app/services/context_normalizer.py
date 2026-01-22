"""
Context Normalizer: Normalizes trusted_context fields to compact enums
before sending to OpenAI.

Mappings:
- region_country: "Canada" -> "CA", "United States" -> "US"
- region_state_province: "ON" -> "CA-ON", "California" -> "US-CA"
- grade_level: "Grade 11" -> "11", "College-1" -> "C1"
- learning_mode: "study" | "solve" (kept as-is)
"""
from typing import Dict, Any, Optional
import re

# Country normalization
COUNTRY_MAP = {
    "canada": "CA",
    "ca": "CA",
    "united states": "US",
    "usa": "US",
    "us": "US",
}

# Province/State normalization (prefix with country code)
PROVINCE_STATE_MAP = {
    # Canadian provinces
    "on": "CA-ON", "ontario": "CA-ON",
    "bc": "CA-BC", "british columbia": "CA-BC",
    "ab": "CA-AB", "alberta": "CA-AB",
    "qc": "CA-QC", "quebec": "CA-QC",
    "mb": "CA-MB", "manitoba": "CA-MB",
    "sk": "CA-SK", "saskatchewan": "CA-SK",
    "ns": "CA-NS", "nova scotia": "CA-NS",
    "nb": "CA-NB", "new brunswick": "CA-NB",
    "nl": "CA-NL", "newfoundland": "CA-NL",
    "pe": "CA-PE", "pei": "CA-PE",
    "nt": "CA-NT", "yt": "CA-YT", "nu": "CA-NU",
    # US states
    "ca": "US-CA", "california": "US-CA",
    "ny": "US-NY", "new york": "US-NY",
    "tx": "US-TX", "texas": "US-TX",
    "fl": "US-FL", "florida": "US-FL",
    "wa": "US-WA", "washington": "US-WA",
    "il": "US-IL", "illinois": "US-IL",
    "pa": "US-PA", "pennsylvania": "US-PA",
    "oh": "US-OH", "ohio": "US-OH",
    "ga": "US-GA", "georgia": "US-GA",
    "nc": "US-NC", "north carolina": "US-NC",
    "mi": "US-MI", "michigan": "US-MI",
    "nj": "US-NJ", "new jersey": "US-NJ",
    "va": "US-VA", "virginia": "US-VA",
    "az": "US-AZ", "arizona": "US-AZ",
    "ma": "US-MA", "massachusetts": "US-MA",
    "tn": "US-TN", "tennessee": "US-TN",
    "in": "US-IN", "indiana": "US-IN",
    "mo": "US-MO", "missouri": "US-MO",
    "md": "US-MD", "maryland": "US-MD",
    "wi": "US-WI", "wisconsin": "US-WI",
    "co": "US-CO", "colorado": "US-CO",
    "mn": "US-MN", "minnesota": "US-MN",
    "sc": "US-SC", "south carolina": "US-SC",
    "al": "US-AL", "alabama": "US-AL",
    "la": "US-LA", "louisiana": "US-LA",
    "ky": "US-KY", "kentucky": "US-KY",
    "or": "US-OR", "oregon": "US-OR",
    "ok": "US-OK", "oklahoma": "US-OK",
    "ct": "US-CT", "connecticut": "US-CT",
    "ut": "US-UT", "utah": "US-UT",
    "ia": "US-IA", "iowa": "US-IA",
    "nv": "US-NV", "nevada": "US-NV",
    "ar": "US-AR", "arkansas": "US-AR",
    "ms": "US-MS", "mississippi": "US-MS",
    "ks": "US-KS", "kansas": "US-KS",
    "nm": "US-NM", "new mexico": "US-NM",
    "ne": "US-NE", "nebraska": "US-NE",
    "wv": "US-WV", "west virginia": "US-WV",
    "id": "US-ID", "idaho": "US-ID",
    "hi": "US-HI", "hawaii": "US-HI",
    "nh": "US-NH", "new hampshire": "US-NH",
    "me": "US-ME", "maine": "US-ME",
    "ri": "US-RI", "rhode island": "US-RI",
    "mt": "US-MT", "montana": "US-MT",
    "de": "US-DE", "delaware": "US-DE",
    "sd": "US-SD", "south dakota": "US-SD",
    "nd": "US-ND", "north dakota": "US-ND",
    "ak": "US-AK", "alaska": "US-AK",
    "dc": "US-DC", "district of columbia": "US-DC",
    "vt": "US-VT", "vermont": "US-VT",
    "wy": "US-WY", "wyoming": "US-WY",
}

# Grade level normalization
GRADE_PATTERN = re.compile(r"grade\s*(\d+)", re.IGNORECASE)
COLLEGE_PATTERN = re.compile(r"college[-\s]*(\d+)", re.IGNORECASE)


def normalize_country(value: Optional[str]) -> Optional[str]:
    """Normalize country to 2-letter code."""
    if not value:
        return None
    key = value.strip().lower()
    return COUNTRY_MAP.get(key, value.upper()[:2] if len(value) <= 3 else None)


def normalize_province_state(value: Optional[str], country: Optional[str] = None) -> Optional[str]:
    """Normalize province/state to XX-YY format."""
    if not value:
        return None
    key = value.strip().lower()
    
    # If already in XX-YY format, return as-is
    if re.match(r"^[A-Z]{2}-[A-Z]{2}$", value.upper()):
        return value.upper()
    
    # Look up in map
    if key in PROVINCE_STATE_MAP:
        return PROVINCE_STATE_MAP[key]
    
    # If we have country context, prefix it
    if country and len(value) <= 3:
        return f"{country.upper()}-{value.upper()}"
    
    return None


def normalize_grade_level(value: Optional[str]) -> Optional[str]:
    """Normalize grade level to compact form (e.g., '11', 'C1')."""
    if not value:
        return None
    
    # Already a number or short form
    if value.isdigit():
        return value
    
    val = value.strip()
    
    # Match "Grade 11" -> "11"
    grade_match = GRADE_PATTERN.search(val)
    if grade_match:
        return grade_match.group(1)
    
    # Match "College-1" -> "C1"
    college_match = COLLEGE_PATTERN.search(val)
    if college_match:
        return f"C{college_match.group(1)}"
    
    # Handle K, Pre-K
    if val.lower() in ("k", "kindergarten"):
        return "K"
    if val.lower() in ("pre-k", "prek", "pre k"):
        return "PK"
    
    return val


def normalize_subject(value: Optional[str]) -> Optional[str]:
    """Normalize subject to compact form."""
    if not value:
        return None
    
    val = value.strip().lower()
    mapping = {
        "mathematics": "math",
        "physics": "phys",
        "chemistry": "chem",
        "biology": "bio",
    }
    return mapping.get(val, val[:4] if len(val) > 4 else val)


def normalize_difficulty(value: Optional[str]) -> Optional[str]:
    """Normalize difficulty to compact form."""
    if not value:
        return None
    
    val = value.strip().lower()
    mapping = {
        "high school": "hs",
        "high school / ap": "hs",
        "middle school": "ms",
        "elementary": "elem",
        "college": "col",
        "university": "uni",
        "ap": "ap",
    }
    
    for key, short in mapping.items():
        if key in val:
            return short
    return val[:4] if len(val) > 4 else val


def normalize_trusted_context(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize all trusted_context fields to compact enums.
    
    Input:
        {
            "learning_mode": "study",
            "grade_level": "Grade 11",
            "region_country": "Canada",
            "region_state_province": "ON"
        }
    
    Output:
        {
            "learning_mode": "study",
            "grade_level": "11",
            "region_country": "CA",
            "region_state_province": "CA-ON"
        }
    """
    if not ctx:
        return {}
    
    normalized = {}
    
    # learning_mode: kept as-is (already "study" | "solve")
    if "learning_mode" in ctx and ctx["learning_mode"]:
        normalized["learning_mode"] = ctx["learning_mode"]
    
    # grade_level: "Grade 11" -> "11"
    if "grade_level" in ctx:
        grade = normalize_grade_level(ctx["grade_level"])
        if grade:
            normalized["grade_level"] = grade
    
    # region_country: "Canada" -> "CA"
    country = None
    if "region_country" in ctx:
        country = normalize_country(ctx["region_country"])
        if country:
            normalized["region_country"] = country
    
    # region_state_province: "ON" -> "CA-ON"
    if "region_state_province" in ctx:
        province = normalize_province_state(ctx["region_state_province"], country)
        if province:
            normalized["region_state_province"] = province
    
    return normalized


def build_compact_user_message(
    problem_text: str,
    trusted_context: Optional[Dict[str, Any]] = None,
    task: Optional[str] = None
) -> str:
    """
    Build compact JSON user message for OpenAI.
    
    Returns JSON string like:
    {"trusted_context":{"learning_mode":"study","grade_level":"11","region_country":"CA"},"problem":"expand(x-1)..."}
    """
    import json
    
    message = {}
    
    # Add normalized trusted_context (only if non-empty)
    if trusted_context:
        normalized = normalize_trusted_context(trusted_context)
        if normalized:
            message["trusted_context"] = normalized
    
    # Add task hint (optional)
    if task:
        message["task"] = task
    
    # Add problem (required)
    message["problem"] = problem_text.strip()
    
    return json.dumps(message, separators=(",", ":"))
