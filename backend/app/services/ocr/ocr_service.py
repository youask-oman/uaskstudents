import os
import time
import logging
from typing import Optional, Dict, List, Any
import json
from pix2text import Pix2Text
try:
    from pix2text.vlm import VlmTextFormulaOCR, VlmTableOCR
except ImportError:
    VlmTextFormulaOCR = None
    VlmTableOCR = None

import litellm
import base64

logger = logging.getLogger(__name__)

class OCREngine:
    def process(self, image_path: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

class LocalEngine(OCREngine):
    def __init__(self):
        self._p2t = None

    @property
    def p2t(self):
        if self._p2t is None:
            logger.info("Initializing Local Pix2Text...")
            self._p2t = Pix2Text.from_config()
        return self._p2t

    def process(self, image_path: str, out_dir: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        # If out_dir is provided, Pix2Text will save figures there
        kwargs = {}
        if out_dir:
            kwargs['save_dir'] = out_dir
            
        result = self.p2t.recognize_page(image_path, **kwargs)
        
        # Result typically has to_markdown() and other attributes
        markdown = result.to_markdown(out_dir or "output") if hasattr(result, "to_markdown") else str(result)
        
        return {
            "markdown": markdown,
            "plain_text": markdown,
            "latex_blocks": [],
            "confidence": 0.85,
            "timings": {"ocr_ms": int((time.time() - start_time) * 1000)}
        }

class VlmEngine(OCREngine):
    def __init__(self, vlm_type: str = "text_formula"):
        self.vlm_type = vlm_type
        self._ocr = None
        # VLM settings from ENV
        self.model = os.getenv("VLM_MODEL_TEXT_FORMULA", "openai/gpt-4o") if vlm_type == "text_formula" else os.getenv("VLM_MODEL_TABLE", "openai/gpt-4o")

    @property
    def ocr(self):
        # We now use direct LiteLLM for better control and less dependency issues
        return "litellm"

    def process(self, image_path: str, custom_prompt: Optional[str] = None, response_format: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        # Load and encode image
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        system_prompt = "You are a helpful OCR assistant."
        user_prompt = "Extract all text and math from this image. Use LaTeX for math. Return only markdown."
        
        if custom_prompt:
            # If custom_prompt is provided, we use it as the main instruction
            user_prompt = custom_prompt
        elif self.vlm_type == "table":
            user_prompt = "Extract the table content from this image as a markdown table. Use LaTeX for any math inside."

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ]

        # Use litellm.completion with optional response_format
        kwargs = {}
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        response = litellm.completion(
            model=self.model,
            messages=messages,
            **kwargs
        )
        
        content = response.choices[0].message.content
        usage = getattr(response, "usage", {})
        if hasattr(usage, "dict"):
            usage = usage.dict()
            
        return {
            "markdown": content, # Still return as markdown/text field
            "json": json.loads(content) if response_format == "json_object" else None,
            "plain_text": content,
            "latex_blocks": [],
            "confidence": 0.98,
            "provider": response.get("provider", "openai"),
            "provider_model": self.model,
            "usage": usage,
            "timings": {"ocr_ms": int((time.time() - start_time) * 1000)}
        }

class OCRService:
    def __init__(self):
        self.local_engine = LocalEngine()
        self.vlm_text_engine = None # Lazy
        self.vlm_table_engine = None # Lazy

    def get_engine(self, engine_name: str, vlm_type: Optional[str] = None) -> OCREngine:
        if engine_name == "vlm":
            if vlm_type == "table":
                if not self.vlm_table_engine: self.vlm_table_engine = VlmEngine(vlm_type="table")
                return self.vlm_table_engine
            else:
                if not self.vlm_text_engine: self.vlm_text_engine = VlmEngine(vlm_type="text_formula")
                return self.vlm_text_engine
        return self.local_engine

    def process_job(self, image_path: str, engine_name: str = "local", vlm_type: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        engine = self.get_engine(engine_name, vlm_type)
        try:
            return engine.process(image_path, **kwargs)
        except Exception as e:
            logger.error(f"OCR Engine ({engine_name}) failed: {e}")
            raise e

ocr_service = OCRService()
