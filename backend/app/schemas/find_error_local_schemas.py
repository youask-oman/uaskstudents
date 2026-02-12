"""
Schemas for local find error feature
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class SelectionBBox(BaseModel):
    x: float = Field(..., ge=0, le=1, description="Normalized x coordinate")
    y: float = Field(..., ge=0, le=1, description="Normalized y coordinate")
    w: float = Field(..., ge=0, le=1, description="Normalized width")
    h: float = Field(..., ge=0, le=1, description="Normalized height")

class FindErrorLocalRequest(BaseModel):
    crop_hash: Optional[str] = None
    selection_bbox: SelectionBBox
    ocr_hint: Optional[str] = "math"
    max_lines: Optional[int] = 6
    # Fallback: allow direct image upload if crop_hash not available
    image_data: Optional[str] = None  # base64 encoded

class OCRResult(BaseModel):
    text: str
    raw: str
    confidence: float

class AnalysisResult(BaseModel):
    detected_format: str
    first_wrong_line_index: Optional[int]
    what_is_wrong: str
    minimal_fix: str
    confidence: float

class TimingsMs(BaseModel):
    crop: Optional[float] = 0
    ocr: Optional[float] = 0
    parse: Optional[float] = 0
    check: Optional[float] = 0
    total: Optional[float] = 0

class FindErrorLocalResponse(BaseModel):
    ok: bool
    request_id: str
    selection_bbox: Optional[SelectionBBox] = None
    ocr: Optional[OCRResult] = None
    analysis: Optional[AnalysisResult] = None
    timings_ms: Optional[TimingsMs] = None
    error: Optional[Dict[str, Any]] = None
