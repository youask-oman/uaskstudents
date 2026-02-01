"""
Hybrid OCR Service
==================
Production-grade OCR service supporting multiple engines:
- VLM (GPT-4o Vision): Fast, accurate, cloud-based (default)
- Local (Pix2Text): Private, slower, runs on-premise

Configuration via environment variables:
- OCR_ENGINE: "vlm" (default), "local", or "auto" (VLM with local fallback)
- VLM_MODEL_OCR: Model to use for VLM engine (default: gpt-4o)
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
import json

# ============================================================
# FIX: Redirect all logging/cache directories to /tmp for Docker
# This prevents "[Errno 30] Read-only file system" errors
# These MUST be set before any ML library imports!
# ============================================================
os.environ.setdefault("TENSORBOARD_LOGDIR", "/tmp/tensorboard_logs")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("HF_HOME", "/tmp/huggingface")
os.environ.setdefault("TRANSFORMERS_CACHE", "/tmp/transformers_cache")
os.environ.setdefault("TORCH_HOME", "/tmp/torch")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/xdg_cache")
os.environ.setdefault("PIX2TEXT_MODEL_DIR", "/tmp/pix2text_models")
os.environ.setdefault("ONNXRUNTIME_EXTENSIONS_CACHE_DIR", "/tmp/onnxruntime")

# YOLO/Ultralytics specific - these control where "runs" and config are stored
os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", "/tmp/Ultralytics")
os.environ.setdefault("HOME", "/tmp")  # Fallback for libraries that use ~/

# Create /tmp subdirectories (safe on any Linux system)
for _dir in ["/tmp/tensorboard_logs", "/tmp/matplotlib", "/tmp/huggingface", "/tmp/p2t_output", 
             "/tmp/xdg_cache", "/tmp/pix2text_models", "/tmp/onnxruntime", "/tmp/torch",
             "/tmp/Ultralytics", "/tmp/Ultralytics/runs"]:
    try:
        os.makedirs(_dir, exist_ok=True)
    except Exception:
        pass  # Best effort, /tmp should always be writable

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
    """Base class for OCR engines."""
    
    def process(self, image_path: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
    
    @property
    def engine_name(self) -> str:
        return "base"


class LocalEngine(OCREngine):
    """
    Pix2Text-based local OCR engine.
    Pros: Privacy (data stays local), no API costs
    Cons: Slower (15-25s), requires GPU for best performance
    """
    
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
        """Creates 2-3 variants of the image for robust OCR (Requirement D)."""
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
        """Deterministic router for Pix2Text mode selection."""
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
        """Requirement 3: Detect if output is only a figure placeholder (even multi-line)."""
        s = markdown.strip()
        if not s: return True
        
        # Remove all figure placeholders: ![](figures/...)
        # We use a non-greedy match for the content between parentheses
        clean = re.sub(r'!\[\]\(figures\/.*?\)', '', s).strip()
        
        # If after removing figures, there's no math and very little alphanumeric signal
        if not clean: return True
        
        if not self.looks_like_math(clean):
            # Check if remaining text is just fluff/noise
            if len(clean) < 5 or not any(c.isalnum() for c in clean):
                return True
                
        return False

    def looks_like_math(self, text: str) -> bool:
        """Requirement 3: Heuristic for math presence."""
        math_tokens = [r"\\", r"\^", r"_", r"=", r"\+", r"\-", r"\*", r"\/", r"\(", r"\)", r"\[", r"\]"]
        if any(re.search(t, text) for t in math_tokens): return True
        if any(c.isdigit() for c in text): return True
        return False

    def _format_output(self, text: str, mode: str) -> str:
        """Standardized formatting rules."""
        s = text.strip()
        if not s: return s
        
        if mode == "recognize_formula":
            # Always wrap formula mode output
            if not (s.startswith("$$") and s.endswith("$$")):
                s = s.replace("$", "") # Remove single $ if present
                return f"$${s}$$"
            return s
            
        if mode == "recognize_text_formula":
            # Heuristic: if it's purely a latex string and no surrounding text, wrap it
            if "\\" in s and len(s.split()) == 1 and not (s.startswith("$") or s.startswith("$$")):
                return f"$${s}$$"
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
            debug_dir = f"/tmp/ocr_debug/{request_id}"
            os.makedirs(debug_dir, exist_ok=True)
            shutil.copy(image_path, os.path.join(debug_dir, "input.png"))
            logger.info(f"Debug telemetry enabled at {debug_dir}")

        try:
            # 1. Generate Preprocessing Variants (Requirement D/4)
            variant_paths = self._preprocess_variants(image_path, debug_dir)
            
            # 2. Determine APIs to try based on user_selection (Requirement 2/B)
            if user_selection == "crop":
                api_order = ["recognize_text_formula", "recognize_formula", "recognize"]
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
                            raw = res.to_markdown(out_dir or "/tmp/p2t_output") if hasattr(res, "to_markdown") else str(res)
                        elif api_name == "recognize_text_formula":
                            raw = self.p2t.recognize_text_formula(v_path, return_text=True)
                        elif api_name == "recognize_formula":
                            raw = self.p2t.recognize_formula(v_path)
                        else: # recognize
                            raw = self.p2t.recognize(v_path)
                        
                        candidate = self._format_output(str(raw), api_name)
                        is_weak = self.is_figure_only(candidate)
                        
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
    """
    GPT-4o Vision-based OCR engine.
    Pros: Fast (2-5s), highly accurate, excellent handwriting recognition
    Cons: Requires API key, costs per image, data sent to cloud
    """
    
    def __init__(self):
        self.model = os.getenv("VLM_MODEL_OCR", "gpt-4o")

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
            error_msg = str(e).lower()
            if "timeout" in error_msg:
                raise OCREngineError("Request timed out", engine="vlm", is_timeout=True)
            elif "api_key" in error_msg or "authentication" in error_msg:
                raise OCREngineError("API key invalid or missing", engine="vlm", is_auth_error=True)
            elif "rate_limit" in error_msg or "429" in error_msg:
                raise OCREngineError("Rate limit exceeded", engine="vlm", is_rate_limit=True)
            else:
                raise OCREngineError(f"API request failed: {e}", engine="vlm")
        
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
    """
    Hybrid OCR service with multiple engine support.
    
    Configuration:
    - OCR_ENGINE env var: "vlm" (default), "local", or "auto"
    - Auto mode: tries VLM first, falls back to local on failure
    """
    
    def __init__(self):
        self._local_engine = None
        self._vlm_engine = None

    @property
    def local_engine(self) -> LocalEngine:
        """Lazy initialization of local engine."""
        if self._local_engine is None:
            self._local_engine = LocalEngine()
        return self._local_engine

    @property
    def vlm_engine(self) -> VlmEngine:
        """Lazy initialization of VLM engine."""
        if self._vlm_engine is None:
            self._vlm_engine = VlmEngine()
        return self._vlm_engine

    def get_default_engine(self) -> str:
        """Get default engine from environment."""
        return os.getenv("OCR_ENGINE", "vlm").lower()

    def get_engine(self, engine_name: str) -> OCREngine:
        """Get engine instance by name."""
        if engine_name == "local":
            return self.local_engine
        elif engine_name in ("vlm", "auto"):
            return self.vlm_engine
        else:
            # Default to VLM
            return self.vlm_engine

    def process_job(self, image_path: str, engine_name: str = "auto", crop_meta: Optional[Dict[str, Any]] = None, debug: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Process an image with the specified or default engine.
        
        Args:
            image_path: Path to the image file
            engine_name: Engine to use ("vlm", "local", "auto")
            crop_meta: Metadata about the crop (rotation, fullPage, etc.)
            debug: Whether to save debug artifacts
            **kwargs: Additional arguments passed to the engine
            
        Returns:
            Dict with OCR results including markdown, confidence, timing, etc.
        """
        # Resolve "auto" to env default
        if engine_name == "auto":
            engine_name = self.get_default_engine()
        
        # Special handling for "auto" mode with fallback
        use_fallback = self.get_default_engine() == "auto" and engine_name == "vlm"
        
        logger.info(f"OCR processing: engine={engine_name}, image={image_path}")
        
        try:
            engine = self.get_engine(engine_name)
            process_kwargs = {**kwargs}
            if engine_name == "local":
                process_kwargs["crop_meta"] = crop_meta
                process_kwargs["debug"] = debug
            
            result = engine.process(image_path, **process_kwargs)
            result["engine_used"] = engine.engine_name
            # If local OCR returns empty/weak content, optionally fall back to VLM.
            if engine_name == "local":
                enable_lmm_fallback = os.getenv("ENABLE_LMM_FALLBACK", "true").lower() == "true"
                content = (result.get("markdown") or result.get("plain_text") or "").strip()
                confidence = float(result.get("confidence") or 0.0)
                if enable_lmm_fallback and (not content or confidence <= 0.1):
                    logger.warning("Local OCR returned empty/low-confidence result. Falling back to VLM...")
                    vlm_res = self.vlm_engine.process(image_path, **kwargs)
                    vlm_res["engine_used"] = "vlm"
                    vlm_res["fallback_from"] = "local"
                    return vlm_res
            return result
            
        except OCREngineError as e:
            logger.error(f"OCR engine '{e.engine}' failed: {e}")
            
            # Fallback Logic (Requirement G/7)
            # 1. auto mode (vlm -> local)
            if use_fallback and e.engine == "vlm":
                logger.warning("VLM failed, falling back to local Pix2Text engine...")
                try:
                    result = self.local_engine.process(image_path, crop_meta=crop_meta, debug=debug, **kwargs)
                    result["engine_used"] = "local"
                    result["fallback_reason"] = str(e)
                    return result
                except Exception as fallback_error:
                    logger.error(f"Fallback to local engine also failed: {fallback_error}")
                    raise OCREngineError(f"Both VLM and local engines failed. VLM: {e}. Local: {fallback_error}", engine="auto")
            
            # 2. explicit local with LMM fallback (Requirement G)
            enable_lmm_fallback = os.getenv("ENABLE_LMM_FALLBACK", "true").lower() == "true"
            if engine_name == "local" and enable_lmm_fallback:
                logger.warning("Local engine failed, falling back to LMM (VLM) engine...")
                try:
                    vlm_res = self.vlm_engine.process(image_path, **kwargs)
                    vlm_res["engine_used"] = "vlm"
                    vlm_res["fallback_from"] = "local"
                    # Merge telemetry if available
                    return vlm_res
                except Exception as lmm_err:
                    logger.error(f"Fallback to LMM also failed: {lmm_err}")
            
            raise
                
        except Exception as e:
            logger.error(f"Unexpected OCR error: {e}")
            raise OCREngineError(f"OCR processing failed: {e}", engine=engine_name)
    
    def recognize_region(self, image_bytes: bytes, engine_name: str = "local", fallback_to_vlm: bool = True) -> Dict[str, Any]:
        """
        Recognize text in an image region (for local find error feature).
        
        Args:
            image_bytes: Raw image bytes
            engine_name: Engine to use (default: "local" for privacy)
            fallback_to_vlm: If true, falls back to VLM if local engine fails or yields low confidence
            
        Returns:
            {
                "text": str,  # Normalized text
                "raw": str,   # Raw OCR output
                "confidence": float,
                "engine_used": str
            }
        """
        import tempfile
        from PIL import Image, ImageEnhance, ImageOps
        import io
        
        try:
            # Load image
            img = Image.open(io.BytesIO(image_bytes))
            
            # 2. Enhance contrast and sharpen
            from PIL import ImageFilter
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.8)
            img = img.filter(ImageFilter.SHARPEN)
            
            # 3. Upscale significantly for small crops (crucial for handwriting/math)
            if img.width < 800 or img.height < 400:
                scale = 3 if (img.width < 300) else 2
                img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
            
            # Save to temp file for OCR engine
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img.save(tmp.name, 'PNG')
                tmp_path = tmp.name
            
            try:
                # Attempt with preferred engine
                engine = self.get_engine(engine_name)
                result = engine.process(tmp_path)
                
                raw_text = result.get("markdown", "") or result.get("text", "")
                confidence = result.get("confidence", 0.5)
                
                # Check if result is poor (empty or missing math structure)
                stripped = raw_text.strip()
                has_numbers = any(c.isdigit() for c in stripped)
                has_math_ops = any(c in stripped for c in "+-*/=")
                
                # If we have numbers but no operators and we're in local mode, it might have missed them
                is_poor = not stripped or (len(stripped) < 3 and engine_name == "local")
                if has_numbers and not has_math_ops and engine_name == "local":
                    is_poor = True

                if is_poor and fallback_to_vlm and engine_name != "vlm":
                    logger.warning(f"Local OCR result poor/empty/non-math. Falling back to VLM for region...")
                    vlm_result = self.vlm_engine.process(tmp_path)
                    raw_text = vlm_result.get("markdown", "")
                    confidence = vlm_result.get("confidence", 0.9)
                    engine_name = "vlm"
                
                # Basic normalization
                normalized = raw_text.strip()
                
                # Cap length for logs/payload
                display_raw = raw_text
                if len(display_raw) > 500:
                    display_raw = display_raw[:500] + "..."
                
                return {
                    "text": normalized,
                    "raw": display_raw,
                    "confidence": confidence,
                    "engine_used": engine_name
                }
            finally:
                # Cleanup temp file
                import os
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Region recognition failed: {e}")
            return {
                "text": "",
                "raw": "",
                "confidence": 0.0,
                "engine_used": engine_name
            }


# Singleton instance
ocr_service = OCRService()
