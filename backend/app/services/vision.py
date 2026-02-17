"""
FastAPI + OpenAI Vision (Layout-Preserving Transcription → LaTeX)

What this service does:
- Accepts a CROPPED image (from your rectangle selector UI)
- Asks the vision model to return plain-text transcription with line breaks + spacing
- Converts that plain text into LaTeX that *looks like the image* (line breaks, columns, spacing)
- Returns STRICT JSON: {"latex": "<latex>"}
- Does NOT solve anything

Run:
1) pip install fastapi uvicorn openai python-multipart
2) export OPENAI_API_KEY="..."
3) uvicorn vision:app --reload

POST /latex-from-image
- multipart/form-data file=<image>
"""

import os
import base64
import json
import re
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from openai import AsyncOpenAI


# -----------------------------
# Configuration
# -----------------------------

MODEL_NAME = (os.environ.get("OPENAI_MODEL_DEFAULT") or "").strip()
if not MODEL_NAME:
    raise RuntimeError("OPENAI_MODEL_DEFAULT is required")
if MODEL_NAME != "gpt-5-mini":
    raise RuntimeError(f"OPENAI_MODEL_DEFAULT must be 'gpt-5-mini', got '{MODEL_NAME}'")
MAX_TOKENS = 500
TEMPERATURE = 0

FORBIDDEN_MARKERS = [
    "Solution", "Step", "Therefore", "We know", "Answer:", "Thus", "Hence",
    "The answer is", "Final answer"
]

SYSTEM_PROMPT = r"""
You are a transcription engine.

Task:
- Transcribe ONLY what is visible in the provided image crop.
- Preserve the visual layout using plain text:
  - Keep line breaks.
  - Keep spacing between columns (use multiple spaces where columns exist).
  - Keep punctuation and numbers exactly as shown.

Strict rules:
1) Do NOT solve, explain, simplify, or answer anything.
2) Output MUST be a JSON object with a single key: "text".
3) The value of "text" MUST be plain text (NOT LaTeX), with newline breaks.
4) If something is unreadable, write [illegible]. Do not guess.
"""

USER_TEXT_INSTRUCTIONS = r"""
Return STRICT JSON ONLY in this exact shape:
{"text":"<plain text transcription with line breaks and spacing>"}

Notes:
- Preserve line breaks.
- Preserve spacing (especially between columns/options).
- No LaTeX. No commentary.
"""


# -----------------------------
# Helper functions
# -----------------------------

def _contains_forbidden_content(s: str) -> bool:
    if not s:
        return False
    low = s.lower()
    return any(m.lower() in low for m in FORBIDDEN_MARKERS)


def _parse_json_object(content: str) -> Dict[str, Any]:
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # fallback: try to extract {"text":"..."} loosely
        m = re.search(r'"text"\s*:\s*"(.+?)"\s*}', content, re.DOTALL)
        if m:
            return {"text": m.group(1)}
        return {}


def _repair_control_chars(s: str) -> str:
    if not s:
        return s
    # Undo JSON escape corruption if any
    s = s.replace("\x0c", "")   # form-feed
    s = s.replace("\t", "    ") # tabs -> 4 spaces
    return s


def _normalize_newlines(s: str) -> str:
    if not s:
        return s
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # strip only outer whitespace, keep internal spacing
    return s.strip("\n")


def _escape_latex_text(s: str) -> str:
    """
    Escape characters that break LaTeX in math contexts.
    We'll be wrapping lines in \mathrm{...} so keep it conservative.
    """
    if not s:
        return s
    # Backslash first
    s = s.replace("\\", r"\\")
    # Common special chars
    s = s.replace("{", r"\{").replace("}", r"\}")
    s = s.replace("_", r"\_")
    s = s.replace("^", r"\^{}")
    s = s.replace("%", r"\%")
    s = s.replace("&", r"\&")
    s = s.replace("#", r"\#")
    s = s.replace("$", r"\$")
    return s


def _spaces_to_latex(s: str) -> str:
    """
    Convert spacing into something that renders like the screenshot.
    - Runs of >=4 spaces -> \qquad
    - Runs of 2-3 spaces -> \quad
    - Single space -> \  (backslash-space) inside \mathrm
    """
    if not s:
        return s

    # Mark long gaps (columns)
    s = re.sub(r"[ ]{4,}", r" \\qquad ", s)
    s = re.sub(r"[ ]{2,3}", r" \\quad ", s)

    # Remaining single spaces: keep as \  so math mode respects it
    # (We do this after larger runs are handled.)
    s = s.replace(" ", r"\ ")

    # Clean up accidental double separators
    s = re.sub(r"(\\quad)(\\quad)+", r"\\quad", s)
    s = re.sub(r"(\\qquad)(\\qquad)+", r"\\qquad", s)
    return s


def _format_choice_lines(lines: list[str]) -> list[str]:
    """
    Optional tightening: if OCR returns choices on one line like:
      "A 362 880    B 90 720"
    keep it, but add \mathrm around A/B/C/D tokens more cleanly.
    If lines are already fine, this won't harm.
    """
    out = []
    for line in lines:
        # Normalize weird "A362880" -> "A 362880" if jammed
        line = re.sub(r"\b([A-D])(?=\d)", r"\1 ", line)

        # Ensure options separated a bit if OCR jammed them like "...?A362..."
        line = re.sub(r"(\?)([A-D])\b", r"\1\n\2", line)

        out.extend(line.split("\n"))
    return out


def plain_text_to_latex(text: str) -> str:
    """
    Convert plain text transcription into LaTeX that matches the screenshot layout.
    """
    text = _normalize_newlines(_repair_control_chars(text))
    if not text:
        return ""

    # Split into lines, preserve internal spacing
    lines = text.split("\n")
    lines = [ln.rstrip() for ln in lines]  # keep left spaces if any, drop trailing
    lines = _format_choice_lines(lines)

    latex_lines = []
    for ln in lines:
        if not ln.strip():
            continue

        # Escape LaTeX specials then preserve spaces
        esc = _escape_latex_text(ln)

        # Wrap the entire line as text, but with preserved spacing
        esc = _spaces_to_latex(esc)
        latex_lines.append(rf"\mathrm{{{esc}}}")

    # Join with LaTeX line breaks
    return r" \\ ".join(latex_lines)


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
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        user_content = [
            {"type": "text", "text": USER_TEXT_INSTRUCTIONS},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "high",
                },
            },
        ]

        attempt = 0
        max_attempts = 2 if retry_once else 1
        last_raw: Optional[str] = None

        from app.utils import get_active_prompt

        from app.database import engine, Session
        
        while attempt < max_attempts:
            attempt += 1
            
            with Session(engine) as session:
                system_prompt = get_active_prompt("vision-transcription", session)
            
            if not system_prompt:
                system_prompt = SYSTEM_PROMPT # Fallback
                
            if attempt > 1:
                system_prompt += "\n\nCRITICAL: You failed. Transcribe ONLY. Preserve spacing + line breaks. JSON only."

            resp = await self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
            )

            raw = resp.choices[0].message.content or ""
            last_raw = raw

            data = _parse_json_object(raw)
            text = data.get("text", "") if isinstance(data, dict) else ""

            text = _repair_control_chars(text)
            text = _normalize_newlines(text)

            # Validate "no solving"
            if _contains_forbidden_content(text):
                if attempt < max_attempts:
                    continue
                raise HTTPException(status_code=422, detail="Model returned solution-like content. Transcription-only required.")

            latex = plain_text_to_latex(text)
            if not latex:
                if attempt < max_attempts:
                    continue

            return latex

        raise HTTPException(status_code=500, detail=f"Vision extraction failed. Raw: {last_raw}")


# -----------------------------
# FastAPI app
# -----------------------------

app = FastAPI(title="Image → LaTeX (Layout-Preserving) Transcription API")

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
    if vision_service is None:
        raise HTTPException(status_code=500, detail=startup_error)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    latex = await vision_service.extract_latex(image_bytes=image_bytes, retry_once=True)
    return {"latex": latex}
