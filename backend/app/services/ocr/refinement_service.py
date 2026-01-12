import os
import logging
from typing import List, Dict, Any, Optional
from app.services.ocr.ocr_service import ocr_service

logger = logging.getLogger(__name__)

class FigureRefinementService:
    """
    Refines detected figure blocks (like answer choice grids) 
    by running targeted second-pass OCR.
    """
    def __init__(self):
        self.figure_prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "figure_parser.txt")
        self._figure_prompt = None

    @property
    def figure_prompt(self):
        # We'll use a wrapper that tries dynamic DB first
        return self._fetch_dynamic_prompt()

    def _fetch_dynamic_prompt(self, db=None) -> str:
        from app.utils import get_active_prompt

        try:
            if db:
                p = get_active_prompt("figure-parser", db)
            else:
                from app.database import engine, Session
                with Session(engine) as session:
                    p = get_active_prompt("figure-parser", session)
            if p:
                return p
        except:
            pass
            
        if self._figure_prompt is None:
            if os.path.exists(self.figure_prompt_path):
                with open(self.figure_prompt_path, "r", encoding="utf-8") as f:
                    self._figure_prompt = f.read()
            else:
                logger.warning("figure_parser.txt prompt not found, using fallback")
                self._figure_prompt = "Extract graph details as JSON."
        return self._figure_prompt

    def refine_blocks(self, blocks: List[Dict[str, Any]], image_path: str, base_dir: Optional[str] = None, db=None) -> List[Dict[str, Any]]:
        refined_blocks = []
        
        for block in blocks:
            if block["type"] == "figure":
                try:
                    # Determine strategy: if it looks like a table or choices
                    # For now, we use VlmEngine for best accuracy on refinement
                    asset_id = block.get("asset_id")
                    logger.info(f"Refining figure block: {asset_id}")
                    
                    target_path = asset_id
                    if base_dir and asset_id and not asset_id.startswith("/"):
                        target_path = os.path.join(base_dir, asset_id)

                    refinement_result = ocr_service.process_job(
                        image_path=target_path, # Path to the figure asset
                        engine_name="vlm",
                        custom_prompt=self._fetch_dynamic_prompt(db),
                        response_format="json_object"
                    )
                    
                    block["data_json"] = refinement_result.get("json", {})
                    block["refined_content"] = refinement_result.get("markdown", "")
                    block["type"] = "refined_figure" # Mark as refined
                    
                except Exception as e:
                    logger.error(f"Failed to refine figure {block.get('asset_id')}: {e}")
                    block["warnings"] = [f"REFINEMENT_FAILED: {str(e)}"]
            
            refined_blocks.append(block)
            
        return refined_blocks

figure_refinement_service = FigureRefinementService()
