import os
import json
import logging
from typing import Dict, Any, Optional

# Lazy import - only load litellm when actually needed (worker only)
try:
    import litellm
except ImportError:
    litellm = None

import base64
from sqlmodel import Session
from sqlmodel import Session

logger = logging.getLogger(__name__)

class PostProcessService:
    """
    LLM-based post-processor to structure OCR output into ProblemJSON.
    Uses the strict system prompt from app/prompts/ocr_post_processor.txt.
    """
    
    def process(self, raw_markdown: str, image_path: Optional[str] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Calls LiteLLM to structure the OCR output using the Full-page inventory prompt.
        If image_path is provided, it does a Vision-based inventory pass.
        """
        try:
            from app.utils import get_active_prompt

            
            # If no DB session provided, we need one to fetch the prompt
            if db:
                sys_prompt = get_active_prompt("ocr-post-processor", db)
            else:
                from app.database import engine, Session as DBSession
                with DBSession(engine) as session:
                    sys_prompt = get_active_prompt("ocr-post-processor", session)
            
            # Use file as fallback if not in DB
            if not sys_prompt:
                prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "ocr_post_processor.txt")
                with open(prompt_path, "r", encoding="utf-8") as f:
                    sys_prompt = f.read()

            messages = [{"role": "system", "content": sys_prompt}]
            
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
                response_format={"type": "json_object"},
                request_timeout=30 # P1 Remediation
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
