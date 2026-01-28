from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# --- Intent Schemas ---

class IntentConstraints(BaseModel):
    no_work: Optional[bool] = False
    show_steps: Optional[bool] = True

class VoiceCommandIntent(BaseModel):
    intent: Literal[
        "FINAL_ANSWER_ONLY", 
        "NEXT_STEP_ONLY", 
        "HINT_ONLY", 
        "DETAILED_SOLUTION", 
        "FIND_FIRST_ERROR", 
        "VERIFY_ANSWER", 
        "GRAPH_PLOT", 
        "EXPLAIN_CONCEPT", 
        "EXTRACT_QUESTIONS"
    ]
    verbosity: Literal["minimal", "normal", "detailed"] = "normal"
    target: Literal["selection", "question_ids", "full_crop"] = "full_crop"
    constraints: Optional[IntentConstraints] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    normalized_transcript: str

# --- API Request/Response Schemas ---

class TranscribeResponse(BaseModel):
    ok: bool
    transcript: Optional[str] = None
    error: Optional[str] = None
    request_id: Optional[str] = None

class SelectionBBox(BaseModel):
    x: float
    y: float
    w: float
    h: float

class PageContext(BaseModel):
    source: Literal["pdf_page", "image"]
    page_number: Optional[int] = None
    rotation: Optional[int] = 0
    crop_bbox: Optional[SelectionBBox] = None

class VoiceCommandRequest(BaseModel):
    transcript: str
    mode_hint: Optional[str] = None
    selection_bbox: Optional[SelectionBBox] = None
    question_ids: Optional[List[str]] = None
    page_context: Optional[PageContext] = None

class VoiceCommandResponse(BaseModel):
    ok: bool
    command: Optional[VoiceCommandIntent] = None
    request_id: str
    timings: Optional[Dict[str, float]] = None
    error: Optional[Dict[str, Any]] = None

class FindErrorRequest(BaseModel):
    transcript: str
    selection_bbox: SelectionBBox
    image_context: Dict[str, Any] # crop_hash or blob
    policy: Optional[Dict[str, Any]] = None

class FindErrorResponse(BaseModel):
    ok: bool
    first_wrong_step_index: Optional[int] = None
    what_is_wrong: Optional[str] = None
    minimal_fix: Optional[str] = None
    confidence: Optional[float] = None
    error: Optional[str] = None
