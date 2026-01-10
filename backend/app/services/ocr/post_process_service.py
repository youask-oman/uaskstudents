import os
import json
import logging
from typing import Dict, Any, Optional
import litellm
import base64

logger = logging.getLogger(__name__)

class PostProcessService:
    """
    LLM-based post-processor to structure OCR output into ProblemJSON.
    Uses the strict system prompt from app/prompts/ocr_post_processor.txt.
    """
    
    def __init__(self):
        self.prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "ocr_post_processor.txt")
        self.model = os.getenv("POST_PROCESS_MODEL", "openai/gpt-4o-mini")
        self._system_prompt = None

    @property
    def system_prompt(self):
        if self._system_prompt is None:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                self._system_prompt = f.read()
        return self._system_prompt

    def process(self, raw_markdown: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Calls LiteLLM to structure the OCR output using the Full-page inventory prompt.
        If image_path is provided, it does a Vision-based inventory pass.
        """
        try:
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if image_path:
                # Vision-based pass
                with open(image_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode('utf-8')
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this page and perform Full-page inventory + extraction."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                })
            else:
                # Text-only pass
                messages.append({"role": "user", "content": f"OCR Markdown Input:\n{raw_markdown}"})
            
            response = litellm.completion(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"PostProcessService failed: {e}")
            return {
                "doc_type": "mixed",
                "questions": [
                    {
                        "id": "1",
                        "prompt": raw_markdown,
                        "choices": [],
                        "has_figure": False
                    }
                ],
                "figures": [],
                "coverage_checklist": {"warnings": [str(e)]}
            }

post_process_service = PostProcessService()
