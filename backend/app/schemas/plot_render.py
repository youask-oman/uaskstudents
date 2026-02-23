from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlotRenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width_px: int = Field(default=900, ge=320, le=2200)
    height_px: int = Field(default=520, ge=240, le=1800)
    font_scale: float = Field(default=1.0, ge=0.6, le=1.8)


class PlotEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    should_visualize: bool = True
    recipe: Dict[str, Any]
    notes: Optional[str] = None
    python_code: Optional[str] = None

    @field_validator("recipe")
    @classmethod
    def validate_recipe_object(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict) or not value:
            raise ValueError("plot.recipe must be a non-empty object")
        return value


class PlotRenderSvgRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: Optional[str] = None
    plot: PlotEnvelope
    render_options: PlotRenderOptions = Field(default_factory=PlotRenderOptions)


class PlotRenderSvgMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    render_ms: int
    cached: bool
    warnings: List[str] = Field(default_factory=list)


class PlotRenderSvgResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cache_key: str
    svg: str
    meta: PlotRenderSvgMeta
