"""
FastAPI + OpenAI Vision (Transcription-Only LaTeX)

What this service does:
- Accepts a CROPPED image (from your rectangle selector UI)
- Sends it to OpenAI vision model
- Returns STRICT JSON: {"latex": "<transcription>"}
- Does NOT solve anything (transcribe only)
- Prevents the classic JSON-escape corruption:
    "\text" -> tab + "ext"
    "\frac" -> formfeed + "rac"
  by forcing JSON-safe escaping and repairing if needed.

How to run:
1) pip install fastapi uvicorn openai python-multipart
2) export OPENAI_API_KEY="..."
3) uvicorn app:app --reload

POST /latex-from-image
- multipart/form-data file=<image>
"""

import os
import base64
import json
import re
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from openai import AsyncOpenAI


# -----------------------------
# Configuration
# -----------------------------

MODEL_NAME = "gpt-5-mini"  # keep consistent with your current stack
MAX_TOKENS = 800
TEMPERATURE = 0

# If you want to block "helpful solving", check for these markers.
FORBIDDEN_MARKERS = [
    "Solution", "Step", "Therefore", "We know", "Answer:", "Thus", "Hence"
]

# System prompt: keep it simple, do NOT mix JSON escaping rules here.
SYSTEM_PROMPT = r"""
You are a transcription engine.

Task:
- Transcribe ONLY what is visible in the provided image crop.

Strict rules:
1) Do NOT solve, explain, simplify, or answer anything.
2) Output LaTeX transcription ONLY. No markdown, no code fences, no commentary.
3) Do NOT wrap output in $...$ or $$...$$ or \[...\].
4) Do NOT use \m or any non-standard macros. Never output "\m".
5) Any normal English words MUST be wrapped in \mathrm{...}.
   - Wrap EACH word individually to preserve spacing.
   - Example: \mathrm{How} \mathrm{many} \mathrm{words}
   - Do NOT output: \mathrm{Howmanywords}
6) Use standard LaTeX for math: \frac, \ln, \sin, \cos, exponents, derivatives, etc.
7) Preserve line breaks using \\.
8) If unreadable, write [illegible]. Do not guess.

Return ONLY the LaTeX transcription.
"""



# User prompt: THIS is where we enforce JSON + escaping requirements.
# The critical piece: "DOUBLE backslashes inside JSON string"
USER_TEXT_INSTRUCTIONS = r"""
Return STRICT JSON ONLY:
{"latex":"<transcription>"}

IMPORTANT (JSON escaping):
Inside the JSON string, every LaTeX backslash MUST be DOUBLE escaped.
Example: \\frac{1}{2}, \\ln(2x), \\mathrm{find}

No $ or $$ wrappers. No explanations. Transcribe only.
"""



# -----------------------------
# Helper functions
# -----------------------------

def _strip_math_wrappers(s: str) -> str:
    """Remove $$...$$, \\[...\\], or single $...$ if the model includes them."""
    s = s.strip()

    # Remove code fences if model returns them (it shouldn't, but humans love chaos)
    s = re.sub(r'\\m\s*', "", s)
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)

    # Remove $$ wrappers (robust multiline)
    # Using specific literal checks first if regex fails on newlines
    if s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    
    s = re.sub(r"^\s*\$\$\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"\s*\$\$\s*$", "", s, flags=re.MULTILINE)

    # Remove \[ \] wrappers
    s = re.sub(r"^\s*\\\[\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"\s*\\\]\s*$", "", s, flags=re.MULTILINE)

    # Remove single $ wrappers (only if it is clearly wrapped at start/end)
    if s.startswith("$") and s.endswith("$") and len(s) > 2:
        s = s[1:-1].strip()

    return s


def _repair_json_escape_corruption(latex: str) -> str:
    """
    Fix the classic issue when the model fails to double-escape backslashes in JSON,
    and json.loads turns sequences like:
      \\t -> tab
      \\f -> form-feed
    Resulting in:
      ext{...} instead of \\mathrm{...} / \\text{...}
      rac{...} instead of \\frac{...}
    """
    if not latex:
        return latex

    # Repair actual control characters that may have been introduced by JSON parsing
    # \x0c is form-feed (comes from '\f')
    latex = latex.replace("\x0c", "\\")  # form-feed -> backslash
    latex = latex.replace("\t", " ")     # tabs -> spaces

    # If we now have \rac{...}, fix it to \frac{...}
    latex = re.sub(r"\\rac\{", r"\\frac{", latex)

    return latex


def _normalize_spacing(latex: str) -> str:
    """Normalize spacing without destroying LaTeX structure too aggressively."""
    latex = latex.replace("\t", " ")
    latex = re.sub(r"[ ]{2,}", " ", latex).strip()
    return latex


def _add_missing_backslashes_safely(latex: str) -> str:
    """
    Add missing backslashes ONLY when absent, and do it safely (regex with negative lookbehind).
    This prevents turning \frac into \\frac.
    """
    latex = re.sub(r"(?<!\\)\bfrac\{", r"\\frac{", latex)
    latex = re.sub(r"(?<!\\)\bsqrt\{", r"\\sqrt{", latex)
    latex = re.sub(r"(?<!\\)\bln\(", r"\\ln(", latex)
    latex = re.sub(r"(?<!\\)\bsin\(", r"\\sin(", latex)
    latex = re.sub(r"(?<!\\)\bcos\(", r"\\cos(", latex)
    latex = re.sub(r"(?<!\\)\btan\(", r"\\tan(", latex)
    return latex


def _force_mathrm_words(latex: str) -> str:
    """
    If the model outputs ext{...} or text{...}, convert to \\mathrm{...}.
    Do NOT do a naive replace that can over-match; keep it minimal and safe.
    """
    # Fix common corruption: ext{ -> \mathrm{
    latex = re.sub(r"(^|[^\\])ext\{", r"\1\\mathrm{", latex)

    # Convert \text{...} to \mathrm{...} if it sneaks in
    latex = latex.replace("\\text{", "\\mathrm{")

    # If "text{" appears with missing backslash, convert to \mathrm{
    latex = re.sub(r"(^|[^\\])text\{", r"\1\\mathrm{", latex)

    # Fix "athrm{" -> "\mathrm{"
    latex = re.sub(r"(^|[^\\])athrm\{", r"\1\\mathrm{", latex)

    return latex


def _contains_forbidden_content(latex: str) -> bool:
    """Detect obvious solution-like responses."""
    if not latex:
        return False
    return any(marker.lower() in latex.lower() for marker in FORBIDDEN_MARKERS)


def _parse_strict_json(content: str) -> str:
    """
    Parse the model's JSON response.
    If parsing fails (rare in JSON mode), attempt a fallback extraction.
    """
    if not content:
        return ""

    try:
        data = json.loads(content)
        return data.get("latex", "") or ""
    except json.JSONDecodeError:
        # fallback: try to extract latex field with regex
        match = re.search(r'"latex"\s*:\s*"(.+?)"\s*}', content, re.DOTALL)
        if match:
            return match.group(1)
        return content


# -----------------------------
# OpenAI client wrapper
# -----------------------------

class VisionService:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured.")
        self.client = AsyncOpenAI(api_key=api_key)

    async def extract_latex(self, image_bytes: bytes, retry_once: bool = True) -> str:
        """
        Calls OpenAI vision to transcribe LaTeX ONLY.
        Returns the processed LaTeX string (no wrappers, no explanations).
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        user_content = [
            {"type": "text", "text": USER_TEXT_INSTRUCTIONS},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "high"
                }
            }
        ]

        attempt = 0
        max_attempts = 2 if retry_once else 1
        last_raw: Optional[str] = None

        while attempt < max_attempts:
            attempt += 1

            # If retrying, reinforce "no solving"
            system_prompt = SYSTEM_PROMPT
            if attempt > 1:
                system_prompt += "\n\nCRITICAL: You failed. Transcribe ONLY. Do NOT solve. JSON only."

            resp = await self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},  # JSON mode
            )

            raw = resp.choices[0].message.content or ""
            last_raw = raw

            latex = _parse_strict_json(raw)

            # Post-processing pipeline (safe, ordered)
            latex = _strip_math_wrappers(latex)
            latex = _repair_json_escape_corruption(latex)
            latex = _force_mathrm_words(latex)
            latex = _add_missing_backslashes_safely(latex)
            latex = _normalize_spacing(latex)

            # Validate "no solving"
            if _contains_forbidden_content(latex):
                # retry once
                if attempt < max_attempts:
                    continue
                # if still bad, fail
                raise HTTPException(
                    status_code=422,
                    detail="Model returned solution-like content. Transcription-only required."
                )

            return latex

        # If we somehow exit loop without return:
        raise HTTPException(status_code=500, detail=f"Vision extraction failed. Raw: {last_raw}")


# -----------------------------
# FastAPI app
# -----------------------------

app = FastAPI(title="Image → LaTeX Transcription API")

# Create service once at startup
try:
    vision_service = VisionService()
except RuntimeError as e:
    vision_service = None
    startup_error = str(e)


@app.get("/health")
async def health():
    if vision_service is None:
        return {"ok": False, "error": startup_error}
    return {"ok": True}


@app.post("/latex-from-image")
async def latex_from_image(file: UploadFile = File(...)):
    """
    Receive a cropped image and return transcription-only LaTeX.
    """
    if vision_service is None:
        raise HTTPException(status_code=500, detail=startup_error)

    # Basic input validation
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    latex = await vision_service.extract_latex(image_bytes=image_bytes, retry_once=True)
    return {"latex": latex}
