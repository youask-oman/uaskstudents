"""
Hybrid OCR Service
==================
Production-grade OCR service supporting multiple engines:
- OpenAI Vision OCR: Fast, accurate, cloud-based
- Local (Pix2Text): Private, slower, runs on-premise

Configuration via environment variables:
- OCR_ENGINE: "openai", "local", or "auto"
- VLM_MODEL_OCR: Model to use for OpenAI OCR
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
import json

# ============================================================
# FIX: Redirect all logging/cache directories to system temp
# This prevents "[Errno 30] Read-only file system" errors
# These MUST be set before any ML library imports!
# ============================================================
import tempfile
_TEMP_DIR = tempfile.gettempdir()

os.environ.setdefault("TENSORBOARD_LOGDIR", os.path.join(_TEMP_DIR, "tensorboard_logs"))
os.environ.setdefault("MPLCONFIGDIR", os.path.join(_TEMP_DIR, "matplotlib"))
os.environ.setdefault("HF_HOME", os.path.join(_TEMP_DIR, "huggingface"))
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(_TEMP_DIR, "transformers_cache"))
os.environ.setdefault("TORCH_HOME", os.path.join(_TEMP_DIR, "torch"))
os.environ.setdefault("XDG_CACHE_HOME", os.path.join(_TEMP_DIR, "xdg_cache"))
os.environ.setdefault("PIX2TEXT_MODEL_DIR", os.path.join(_TEMP_DIR, "pix2text_models"))
os.environ.setdefault("ONNXRUNTIME_EXTENSIONS_CACHE_DIR", os.path.join(_TEMP_DIR, "onnxruntime"))

# YOLO/Ultralytics specific - these control where "runs" and config are stored
os.environ.setdefault("YOLO_CONFIG_DIR", os.path.join(_TEMP_DIR, "Ultralytics"))
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", os.path.join(_TEMP_DIR, "Ultralytics"))
os.environ.setdefault("HOME", _TEMP_DIR)  # Fallback for libraries that use ~/

# Create temp subdirectories
_DIRS_TO_CREATE = [
    "tensorboard_logs", "matplotlib", "huggingface", "p2t_output", 
    "xdg_cache", "pix2text_models", "onnxruntime", "torch",
    "Ultralytics", "Ultralytics/runs"
]

for _sub in _DIRS_TO_CREATE:
    _dir = os.path.join(_TEMP_DIR, _sub)
    try:
        os.makedirs(_dir, exist_ok=True)
    except Exception:
        pass  # Best effort

# Lazy import - only load pix2text when actually needed (worker only)
try:
    from pix2text import Pix2Text
except ImportError:
    Pix2Text = None

# Lazy import for litellm
try:
    import litellm
except ImportError:
    litellm = None

import base64
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np
import io
import shutil
import hashlib
import re

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5  # seconds
VLM_TIMEOUT = 30  # seconds

# Optimized prompt for math/science OCR
MATH_OCR_PROMPT = """You are an expert OCR assistant specialized in extracting mathematical content.

TASK: Extract ALL content from this image with perfect accuracy.

FORMATTING RULES:
1. Convert ALL mathematical expressions to LaTeX:
   - Use $ for inline math (e.g., $x^2 + y^2 = r^2$)
   - Use $$ for display/block math
2. Preserve the exact structure and ordering of content
3. For multiple choice questions, format as:
   A) option text
   B) option text
   etc.
4. For graphs/diagrams, add: [FIGURE: brief description]
5. For tables, use markdown table format

OUTPUT:
- Return ONLY the extracted content as clean markdown
- No preamble, no explanations, no "Here is the content:"
- Just the raw extracted text with proper LaTeX formatting"""


# ============================================================
# Engine Implementations
# ============================================================

class OCREngine:
    # Base class for OCR engines.
    
    def process(self, image_path: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
    
    @property
    def engine_name(self) -> str:
        return "base"


class LocalEngine(OCREngine):
    # Pix2Text-based local OCR engine.
    # Pros: Privacy (data stays local), no API costs
    # Cons: Slower (15-25s), requires GPU for best performance
    
    def __init__(self):
        self._p2t = None

    @property
    def engine_name(self) -> str:
        return "local"

    @property
    def p2t(self):
        if self._p2t is None:
            if Pix2Text is None:
                raise ImportError("Pix2Text is not installed. This engine requires worker dependencies.")
            logger.info("Initializing Local Pix2Text engine...")
            self._p2t = Pix2Text.from_config()
            logger.info("Pix2Text initialized successfully")
        return self._p2t
    
    def _preprocess_variants(self, image_path: str, debug_dir: Optional[str] = None) -> List[str]:
        # Creates 2-3 variants of the image for robust OCR (Requirement D).
        variants = []
        img_orig = cv2.imread(image_path) if cv2 else None
        
        if img_orig is None:
            return [image_path]

        def add_padding(img):
            # Pad borders for radicals/integrals (Requirement 4)
            return cv2.copyMakeBorder(img, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=[255, 255, 255])

        # v0: Padded Original
        v0_path = image_path.replace(".png", "_v0.png").replace(".jpg", "_v0.png")
        cv2.imwrite(v0_path, add_padding(img_orig))
        variants.append(v0_path)

        # v1: Grayscale + CLAHE + Denoise + Unsharp
        gray = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl1 = clahe.apply(gray)
        denoised = cv2.fastNlMeansDenoising(cl1, None, 10, 7, 21)
        # Unsharp
        blurred = cv2.GaussianBlur(denoised, (0, 0), 3)
        unsharp = cv2.addWeighted(denoised, 1.5, blurred, -0.5, 0)
        
        v1_path = image_path.replace(".png", "_v1.png").replace(".jpg", "_v1.png")
        cv2.imwrite(v1_path, add_padding(unsharp))
        variants.append(v1_path)

        # v2: Adaptive Threshold (Chalkboard/Low Contrast)
        thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        v2_path = image_path.replace(".png", "_v2.png").replace(".jpg", "_v2.png")
        cv2.imwrite(v2_path, add_padding(thresh))
        variants.append(v2_path)
        
        if debug_dir:
            for i, p in enumerate(variants):
                shutil.copy(p, os.path.join(debug_dir, f"variant_v{i}.png"))
        return variants

    def _select_ocr_mode(self, width: int, height: int, crop_meta: Optional[Dict[str, Any]] = None) -> str:
        # Deterministic router for Pix2Text mode selection.
        full_page = crop_meta.get("fullPage", False) if crop_meta else False
        aspect_ratio = height / width if width > 0 else 0
        
        # 1. Page Mode
        if full_page or aspect_ratio > 0.9 or (width > 2000 and height > 2000):
            return "recognize_page"
        
        # 2. Formula Mode (tight/line-like)
        if (width / height >= 3.0) or (height < 100):
            return "recognize_formula"
        
        # 3. Text-Formula Mode (paragraph-like)
        return "recognize_text_formula"

    def is_figure_only(self, markdown: str) -> bool:
        # Requirement 3: Detect if output is only a figure placeholder (even multi-line).
        s = markdown.strip()
        if not s: return True
        
        # Remove all figure placeholders: ![](figures/...)
        # We use a non-greedy match for the content between parentheses
        clean = re.sub(r'!\[\]\(figures\/.*?\)', '', s).strip()
        
        # If after removing figures, there's no math and very little alphanumeric signal
        if not clean: return True
        
        if not self.looks_like_math(clean):
            # Check if remaining text is just fluff/noise
            # Relaxed: Allow very short text (1+ chars) if alphanumeric
            if not any(c.isalnum() for c in clean):
                logger.info(f"Filtered (no alphanumeric): '{clean}'")
                return True
            if len(clean) < 1:
                return True
                
        return False

    def looks_like_math(self, text: str) -> bool:
        # Requirement 3: Heuristic for math presence.
        math_tokens = [r"\\", r"\^", r"_", r"=", r"\+", r"\-", r"\*", r"\/", r"\(", r"\)", r"\[", r"\]"]
        if any(re.search(t, text) for t in math_tokens): return True
        if re.search(r"\d+\s*[A-Za-z]|[A-Za-z]\s*\d+", text):
            return True
        return False

    def _has_strong_math_signal(self, text: str) -> bool:
        """Stricter signal to reject page-heading OCR noise on tight crops."""
        s = (text or "").strip()
        if not s:
            return False
        if re.search(r"(=|\\sqrt|√|[\+\-\*/\^])", s):
            return True
        if re.search(r"[A-Za-z]\s*=\s*[A-Za-z0-9]", s):
            return True
        if re.search(r"\b(?:sin|cos|tan|log|ln)\b", s, flags=re.IGNORECASE):
            return True
        return False

    def _normalize_delimiters(self, text: str) -> str:
        # Convert $$...$$ to \[...\]
        # We use a simple regex that matches content between $$ tags
        # Note: This assumes balanced tags from Pix2Text
        text = re.sub(r'\$\$(.*?)\$\$', r'\\[\1\\]', text, flags=re.DOTALL)
        
        # Convert $...$ to \(...\)
        # Negative lookahead/lookbehind to ensure we don't match double $ if any remain
        text = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', r'\\(\1\\)', text, flags=re.DOTALL)
        return text

    def _format_output(self, text: str, mode: str) -> str:
        # Standardized formatting rules.
        s = text.strip()
        if not s: return s
        
        # Normalize delimiters first (convert $ -> \( and $$ -> \[)
        s = self._normalize_delimiters(s)

        if mode == "recognize_formula":
            # Ensure it is wrapped in block math if not already
            if not (s.startswith("\\[") and s.endswith("\\]")):
                 # It might be standard text now?
                 # If we stripped $, it might be naked.
                 # But _normalize_delimiters handles pairs.
                 # If the WHOLE thing is a formula but Pix2Text didn't wrap it in $$,
                 # verify if it has delimiters.
                 if not (s.startswith("\\(") and s.endswith("\\)")):
                      return f"\\[{s}\\]"
            return s
            
        if mode == "recognize_text_formula":
            return s
            
        return s
            
        return s

    def process(self, image_path: str, out_dir: Optional[str] = None, crop_meta: Optional[Dict[str, Any]] = None, debug: bool = False) -> Dict[str, Any]:
        overall_start = time.time()
        fallback_chain = []
        debug_dir = None
        user_selection = crop_meta.get("user_selection", "crop") if crop_meta else "crop"

        if Pix2Text is None:
            raise OCREngineError("Pix2Text is not installed. This engine requires worker dependencies.", engine="local")
        
        # Determine image stats
        try:
            with Image.open(image_path) as img_stat:
                width, height = img_stat.size
                img_bytes_count = os.path.getsize(image_path)
        except:
            width, height, img_bytes_count = 0, 0, 0

        if debug:
            request_id = hashlib.md5(f"{image_path}{time.time()}".encode()).hexdigest()[:8]
            debug_dir = os.path.join(_TEMP_DIR, "ocr_debug", request_id)
            os.makedirs(debug_dir, exist_ok=True)
            shutil.copy(image_path, os.path.join(debug_dir, "input.png"))
            logger.info(f"Debug telemetry enabled at {debug_dir}")

        try:
            # 1. Generate Preprocessing Variants (Requirement D/4)
            variant_paths = self._preprocess_variants(image_path, debug_dir)
            
            # 2. Determine APIs to try based on user_selection (Requirement 2/B)
            if user_selection == "crop":
                # For tight crops, formula/text_formula are more reliable than page layout mode.
                api_order = ["recognize_text_formula", "recognize_formula", "recognize", "recognize_page"]
            else: # whole_page
                api_order = ["recognize_page", "recognize_text_formula"]

            winning_markdown = ""
            method_used = ""
            
            # Fallback Ladder: Variant x API
            for v_path in variant_paths:
                for api_name in api_order:
                    step_start = time.time()
                    try:
                        if api_name == "recognize_page":
                            res = self.p2t.recognize_page(v_path, save_dir=out_dir)
                            raw = res.to_markdown(out_dir or os.path.join(_TEMP_DIR, "p2t_output")) if hasattr(res, "to_markdown") else str(res)
                        elif api_name == "recognize_text_formula":
                            raw = self.p2t.recognize_text_formula(v_path, return_text=True)
                        elif api_name == "recognize_formula":
                            raw = self.p2t.recognize_formula(v_path)
                        else: # recognize
                            raw = self.p2t.recognize(v_path)
                        
                        candidate = self._format_output(str(raw), api_name)
                        is_weak = self.is_figure_only(candidate)
                        if (
                            not is_weak
                            and user_selection == "crop"
                            and api_name == "recognize_page"
                            and not self._has_strong_math_signal(candidate)
                        ):
                            is_weak = True

                        fallback_chain.append({
                            "variant": os.path.basename(v_path),
                            "method": api_name,
                            "is_weak": is_weak,
                            "len": len(candidate),
                            "ms": int((time.time() - step_start) * 1000)
                        })

                        if not is_weak:
                            winning_markdown = candidate
                            method_used = api_name
                            break
                    except Exception as step_err:
                        logger.warning(f"Pix2Text step {api_name} failed: {step_err}")
                
                if winning_markdown: break

            # Cleanup variants
            for p in variant_paths:
                if p != image_path:
                    try: os.unlink(p)
                    except: pass

            latency_ms = int((time.time() - overall_start) * 1000)
            
            # Requirement E: Return full telemetry
            telemetry = {
                "ocr_engine_choice": "pix2text",
                "user_selection": user_selection,
                "method_used": method_used,
                "fallback_chain": fallback_chain,
                "input_mime": "image/png",
                "bytes": img_bytes_count,
                "width": width,
                "height": height,
                "preprocessing_steps": ["padding", "clahe", "denoise", "unsharp", "adaptive_threshold"],
                "time_ms": latency_ms,
                "output_type": "markdown/latex"
            }

            res = {
                "markdown": winning_markdown,
                "plain_text": winning_markdown,
                "confidence": 0.9 if winning_markdown else 0.0,
                "engine": "local",
                "provider": "pix2text",
                "telemetry": telemetry
            }
            
            if debug and debug_dir:
                with open(os.path.join(debug_dir, "telemetry.json"), "w") as f:
                    json.dump(res, f, indent=2)
            
            return res
            
        except Exception as e:
            logger.error(f"LocalEngine failed: {e}")
            raise OCREngineError(f"Pix2Text pipeline failed: {e}", engine="local")


class VlmEngine(OCREngine):
    # GPT-4o Vision-based OCR engine.
    # Pros: Fast (2-5s), highly accurate, excellent handwriting recognition
    # Cons: Requires API key, costs per image, data sent to cloud
    
    def __init__(self):
        self.model = os.getenv("VLM_MODEL_OCR") or os.getenv("OPENAI_MODEL_DEFAULT")
        if not self.model:
            raise RuntimeError("VLM_MODEL_OCR or OPENAI_MODEL_DEFAULT is required")

    @property
    def engine_name(self) -> str:
        return "vlm"

    def process(self, image_path: str, custom_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        if litellm is None:
            raise ImportError("litellm is not installed. VLM engine requires litellm.")
        
        start_time = time.time()
        last_error = None
        
        # Retry logic with exponential backoff
        for attempt in range(MAX_RETRIES):
            try:
                result = self._make_request(image_path, custom_prompt)
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"VlmEngine processed image in {latency_ms}ms (attempt {attempt + 1})")
                
                result["timings"] = {"ocr_ms": latency_ms}
                return result
                
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(f"VlmEngine attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"VlmEngine failed after {MAX_RETRIES} attempts: {e}")
        
        raise OCREngineError(f"VLM processing failed after {MAX_RETRIES} attempts: {last_error}", engine="vlm")

    def _make_request(self, image_path: str, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        # Load and encode image
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode('utf-8')
        except FileNotFoundError:
            raise OCREngineError(f"Image file not found: {image_path}", engine="vlm")
        except Exception as e:
            raise OCREngineError(f"Failed to read image file: {e}", engine="vlm")
        
        # Determine image format for data URI
        image_format = "jpeg"
        if image_path.lower().endswith(".png"):
            image_format = "png"
        elif image_path.lower().endswith(".webp"):
            image_format = "webp"
        
        # Use custom prompt or default math OCR prompt
        prompt = custom_prompt or MATH_OCR_PROMPT

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{image_format};base64,{base64_image}"}
                    }
                ]
            }
        ]

        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                timeout=VLM_TIMEOUT,
                max_tokens=4096,  # Ensure enough tokens for complex documents
            )
        except Exception as e:
            error_type = type(e).__name__
            error_msg_lower = str(e).lower()
            
            if isinstance(e, TimeoutError) or "timeout" in error_msg_lower:
                raise OCREngineError("Request timed out", engine="vlm", is_timeout=True)
            elif "api_key" in error_msg_lower or "authentication" in error_msg_lower or "unauthorized" in error_msg_lower:
                raise OCREngineError("API key invalid or missing", engine="vlm", is_auth_error=True)
            elif "rate_limit" in error_msg_lower or "429" in error_msg_lower or "too many requests" in error_msg_lower:
                raise OCREngineError("Rate limit exceeded", engine="vlm", is_rate_limit=True)
            elif "connection" in error_msg_lower or "network" in error_msg_lower:
                raise OCREngineError(f"Network connection error: {e}", engine="vlm")
            elif "quota" in error_msg_lower or "billing" in error_msg_lower:
                raise OCREngineError(f"API quota exceeded: {e}", engine="vlm")
            else:
                raise OCREngineError(f"API request failed ({error_type}): {e}", engine="vlm")
        
        content = response.choices[0].message.content or ""
        
        # Clean up common artifacts from LLM responses
        content = self._clean_response(content)
        
        # Extract usage info
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }
            
        return {
            "markdown": content,
            "plain_text": content,
            "latex_blocks": [],
            "confidence": 0.95,
            "engine": "vlm",
            "provider": "openai",
            "provider_model": self.model,
            "usage": usage,
        }
    
    def _clean_response(self, content: str) -> str:
        """Clean up common LLM response artifacts."""
        # Remove markdown code fences if present
        if content.startswith("```markdown"):
            content = content[11:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        # Strip leading/trailing whitespace
        content = content.strip()
        
        return content


class OCREngineError(Exception):
    """Custom exception for OCR engine failures with metadata."""
    
    def __init__(self, message: str, engine: str, is_timeout: bool = False, 
                 is_auth_error: bool = False, is_rate_limit: bool = False):
        super().__init__(message)
        self.engine = engine
        self.is_timeout = is_timeout
        self.is_auth_error = is_auth_error
        self.is_rate_limit = is_rate_limit


# ============================================================
# Main OCR Service
# ============================================================



class OCRService:
    # Hybrid OCR service with multiple engine support.
    # Configuration:
    # - OCR_ENGINE env var: "openai", "local", or "auto"
    # - Auto mode follows OCR_ENGINE_RESOLVE_AUTO_TO (defaults to openai)
    
    def __init__(self):
        self._local_engine = None
        self._vlm_engine = None

    @property
    def local_engine(self) -> LocalEngine:
        # Lazy initialization of local engine.
        if self._local_engine is None:
            self._local_engine = LocalEngine()
        return self._local_engine

    @property
    def vlm_engine(self) -> VlmEngine:
        # Lazy initialization of VLM engine.
        if self._vlm_engine is None:
            self._vlm_engine = VlmEngine()
        return self._vlm_engine

    def get_default_engine(self) -> str:
        configured = (os.getenv("OCR_ENGINE") or "").strip().lower()
        if configured in {"openai", "vlm", "local", "auto"}:
            return "openai" if configured == "vlm" else configured
        return "auto"

    def get_engine(self, engine_name: str) -> OCREngine:
        # Get engine instance by name.
        if engine_name == "local":
            return self.local_engine
        elif engine_name in ("vlm", "openai", "auto"):
            return self.vlm_engine
        else:
            raise OCREngineError(f"Unsupported OCR engine: {engine_name}", engine=engine_name)

    def process_job(self, image_path: str, engine_name: str = "auto", crop_meta: Optional[Dict[str, Any]] = None, debug: bool = False, **kwargs) -> Dict[str, Any]:
        # Process an image with the specified or default engine.
        # Args:
        #     image_path: Path to the image file
        #     engine_name: Engine to use ("vlm", "local", "auto")
        #     crop_meta: Metadata about the crop
        #     debug: Whether to save debug artifacts
        #     **kwargs: Additional arguments
        # Returns:
        #     Dict with OCR results including markdown, confidence, timing, etc.
        # Resolve "auto" to configured target
        if engine_name == "auto":
            auto_target = (os.getenv("OCR_ENGINE_RESOLVE_AUTO_TO") or "openai").strip().lower()
            engine_name = "openai" if auto_target in {"openai", "vlm"} else "local"
        elif engine_name == "openai":
            engine_name = "vlm"
        
        use_fallback = (os.getenv("OCR_ENGINE_FALLBACK_ENABLED") or "false").lower() in {"1", "true", "yes"}
        
        logger.info(f"OCR processing: engine={engine_name}, image={image_path}")
        
        try:
            engine = self.get_engine(engine_name)
            process_kwargs = {**kwargs}
            if engine_name == "local":
                process_kwargs["crop_meta"] = crop_meta
                process_kwargs["debug"] = debug
            
            result = engine.process(image_path, **process_kwargs)
            result["engine_used"] = engine.engine_name
            # If local OCR returns empty/weak content, optionally fall back to OpenAI OCR.
            if engine_name == "local":
                enable_lmm_fallback = os.getenv("ENABLE_LMM_FALLBACK", "true").lower() == "true"
                content = (result.get("markdown") or result.get("plain_text") or "").strip()
                confidence = float(result.get("confidence") or 0.0)
                if enable_lmm_fallback and use_fallback and (not content or confidence <= 0.1):
                    logger.warning("Local OCR returned empty/low-confidence result. Falling back to OpenAI OCR.")
                    vlm_res = self.vlm_engine.process(image_path, **kwargs)
                    vlm_res["engine_used"] = "vlm"
                    vlm_res["fallback_from"] = "local"
                    return vlm_res
            return result

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {
                "text": "",
                "raw": "",
                "confidence": 0.0,
                "engine_used": engine_name
            }

    def recognize_region(self, image_data: bytes, engine_name: str = "auto", fallback_to_vlm: bool = True) -> Dict[str, Any]:
        # Recognize text in a specific region buffer.
        # Wrapper around process_job for in-memory bytes.
        import tempfile
        import os
        
        # Write to temp file
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        
        try:
            with open(tmp_path, "wb") as f:
                f.write(image_data)
            
            # Use process_job
            # We map engine_name to what process_job expects
            result = self.process_job(
                image_path=tmp_path,
                engine_name=engine_name,
                debug=False
            )
            
            normalized = (result.get("markdown") or result.get("plain_text") or "").strip()
            confidence = float(result.get("confidence") or 0.0)
            engine_used = result.get("engine_used") or engine_name
            
            if not normalized:
                 logger.warning(f"recognize_region: {engine_name} returned empty text.")
            
            display_raw = result.get("raw") or normalized or ""
            
            if len(display_raw) > 500:
                display_raw = display_raw[:500] + "..."
            
            return {
                "text": normalized,
                "raw": display_raw,
                "confidence": confidence,
                "engine_used": engine_used
            }

        except Exception as e:
            logger.error(f"Region recognition failed: {e}")
            return {
                "text": "",
                "raw": "",
                "confidence": 0.0,
                "engine_used": engine_name
            }
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except:
                pass


# Singleton instance
ocr_service = OCRService()
