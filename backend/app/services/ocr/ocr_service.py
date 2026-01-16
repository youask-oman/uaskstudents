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
from typing import Optional, Dict, Any
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

    def process(self, image_path: str, out_dir: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        try:
            # If out_dir is provided, Pix2Text will save figures there
            kwargs = {}
            if out_dir:
                kwargs['save_dir'] = out_dir
                
            result = self.p2t.recognize_page(image_path, **kwargs)
            
            # Result typically has to_markdown() and other attributes
            # Use /tmp fallback to ensure writability in Docker
            markdown = result.to_markdown(out_dir or "/tmp/p2t_output") if hasattr(result, "to_markdown") else str(result)
            
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"LocalEngine processed image in {latency_ms}ms")
            
            return {
                "markdown": markdown,
                "plain_text": markdown,
                "latex_blocks": [],
                "confidence": 0.85,
                "engine": "local",
                "provider": "pix2text",
                "timings": {"ocr_ms": latency_ms}
            }
        except Exception as e:
            logger.error(f"LocalEngine failed: {e}")
            raise OCREngineError(f"Pix2Text processing failed: {e}", engine="local")


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

    def process_job(self, image_path: str, engine_name: str = "auto", **kwargs) -> Dict[str, Any]:
        """
        Process an image with the specified or default engine.
        
        Args:
            image_path: Path to the image file
            engine_name: Engine to use ("vlm", "local", "auto")
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
            result = engine.process(image_path, **kwargs)
            result["engine_used"] = engine.engine_name
            return result
            
        except OCREngineError as e:
            logger.error(f"OCR engine '{e.engine}' failed: {e}")
            
            # Attempt fallback to local if configured for auto mode
            if use_fallback and e.engine == "vlm":
                logger.warning("VLM failed, falling back to local Pix2Text engine...")
                try:
                    result = self.local_engine.process(image_path, **kwargs)
                    result["engine_used"] = "local"
                    result["fallback_reason"] = str(e)
                    return result
                except Exception as fallback_error:
                    logger.error(f"Fallback to local engine also failed: {fallback_error}")
                    raise OCREngineError(
                        f"Both VLM and local engines failed. VLM: {e}. Local: {fallback_error}",
                        engine="auto"
                    )
            else:
                raise
                
        except Exception as e:
            logger.error(f"Unexpected OCR error: {e}")
            raise OCREngineError(f"OCR processing failed: {e}", engine=engine_name)


# Singleton instance
ocr_service = OCRService()
