from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


RenderEventType = Literal[
    "MESSAGE_START",
    "QUESTION_SET",
    "STEP_START",
    "BLOCK_APPEND_TEXT",
    "BLOCK_SET_MATH",
    "STEP_END",
    "FINAL_ANSWER_SET",
    "PLOT_SET",
    "PYTHON_CODE_SET",
    "MESSAGE_END",
]


class RenderProfile(BaseModel):
    text_cps: int = Field(default=52, ge=1, le=500)
    chunk_size_chars: int = Field(default=12, ge=1, le=120)
    jitter_ms: int = Field(default=32, ge=0, le=500)
    step_pause_ms: int = Field(default=320, ge=0, le=5000)
    math_drop_delay_ms: int = Field(default=160, ge=0, le=5000)
    plot_delay_ms: int = Field(default=420, ge=0, le=5000)
    code_delay_ms: int = Field(default=260, ge=0, le=5000)
    seed: str = Field(default="")
    profile_version: str = Field(default="v1")


class RenderEvent(BaseModel):
    id: str
    at_ms: int = Field(ge=0)
    type: RenderEventType
    payload: Dict[str, Any] = Field(default_factory=dict)


class RenderEventsEnvelope(BaseModel):
    render_profile: RenderProfile
    render_events: List[RenderEvent] = Field(default_factory=list)
