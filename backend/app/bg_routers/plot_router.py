"""
Plot Pipeline API Endpoints for Math Solver V3.

Production plotting pipeline using DB-loaded prompts:
1. plot_trigger_v1 - Decides if visualization is justified
2. plot_spec_v1 - Generates Plotly JSON from plot plan

All prompts/schemas loaded from database at runtime.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlmodel import Session
import logging
import asyncio
import time
from collections import deque, defaultdict

from app.database import get_session
from app.plot.cache import build_cache_key, get_cached_svg, set_cached_svg
from app.plot.render_svg import render_recipe_svg
from app.schemas.plot_render import (
    PlotRenderSvgMeta,
    PlotRenderSvgRequest,
    PlotRenderSvgResponse,
)
from app.services.plot_pipeline_service import (
    get_plot_pipeline_service,
    PlotTriggerResult,
    PlotSpecResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plot", tags=["plotting"])
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_PER_WINDOW = 40
_plot_rate: dict[str, deque[float]] = defaultdict(deque)


def _enforce_plot_rate_limit(request: Request) -> None:
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    bucket = _plot_rate[ip]
    while bucket and (now - bucket[0]) > _RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= _RATE_MAX_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many plot render requests")
    bucket.append(now)


class PlotTriggerRequest(BaseModel):
    """Request to trigger plot decision."""
    problem_text: str = Field(..., description="The problem text to analyze")
    solve_result: Dict[str, Any] = Field(..., description="Solve output with visuals")
    tier: str = Field("STANDARD", description="User subscription tier")
    question_id: Optional[str] = Field(None, description="Request tracking ID")


class PlotTriggerResponse(BaseModel):
    """Response from plot trigger stage."""
    plot_needed: bool = Field(..., description="Whether a plot should be generated")
    plot_type: str = Field("", description="Type of plot")
    variables: List[str] = Field(default=[], description="Variables to plot")
    ranges: Dict[str, Any] = Field(default={}, description="Axis ranges")
    reason: str = Field("", description="Decision reason")
    series_plan: List[Dict[str, Any]] = Field(default=[], description="Series definitions")
    key_points: List[Dict[str, Any]] = Field(default=[], description="Key points to highlight")
    error: Optional[str] = Field(None, description="Error message if failed")


class PlotSpecRequest(BaseModel):
    """Request to generate plot specification."""
    problem_text: str = Field(..., description="Original problem text")
    solve_result: Dict[str, Any] = Field(..., description="Solve output")
    trigger_result: Optional[PlotTriggerResponse] = Field(None, description="Trigger output")
    attach_to_step_id: Optional[int] = Field(None, description="Step to attach plot to")
    tier: str = Field("STANDARD", description="User subscription tier")
    question_id: Optional[str] = Field(None, description="Request tracking ID")


class PlotSpecResponse(BaseModel):
    """Response with Plotly specification."""
    plot_id: str = Field("", description="Plot identifier")
    attach_to_step_id: Optional[int] = Field(None, description="Attached step")
    plotly_json: Dict[str, Any] = Field(default={}, description="Plotly figure JSON")
    error: Optional[str] = Field(None, description="Error message if failed")


class PlotPipelineRequest(BaseModel):
    """Complete pipeline request."""
    problem_text: str = Field(..., description="Original problem text")
    solve_result: Dict[str, Any] = Field(..., description="Solve output")
    graph_mode: str = Field("auto", description="off | auto | on")
    attach_to_step_id: Optional[int] = Field(None, description="Step to attach to")
    tier: str = Field("STANDARD", description="User tier")
    question_id: Optional[str] = Field(None, description="Request ID")
    use_reliable_pipeline: bool = Field(True, description="Use two-stage pipeline")


class PlotPipelineResponse(BaseModel):
    """Complete pipeline response."""
    trigger: Optional[PlotTriggerResponse] = Field(None, description="Trigger result if called")
    spec: Optional[PlotSpecResponse] = Field(None, description="Spec result if generated")
    plot_generated: bool = Field(False, description="Whether a plot was produced")
    error: Optional[str] = Field(None, description="Overall error message")


@router.post("/trigger", response_model=PlotTriggerResponse)
async def plot_trigger_v1(
    request: PlotTriggerRequest,
    db: Session = Depends(get_session),
) -> PlotTriggerResponse:
    """
    Stage 1: Plot Trigger - Decides if visualization is justified.
    
    Loads prompts from DB and uses OpenAI structured output.
    """
    service = get_plot_pipeline_service(db)
    
    result = await service._call_plot_trigger(
        problem_text=request.problem_text,
        solve_result=request.solve_result,
        tier=request.tier,
        question_id=request.question_id,
    )
    
    return PlotTriggerResponse(
        plot_needed=result.plot_needed,
        plot_type=result.plot_type,
        variables=result.variables,
        ranges=result.ranges,
        reason=result.reason,
        series_plan=result.series_plan,
        key_points=result.key_points,
        error=result.error,
    )


@router.post("/spec", response_model=PlotSpecResponse)
async def plot_spec_v1(
    request: PlotSpecRequest,
    db: Session = Depends(get_session),
) -> PlotSpecResponse:
    """
    Stage 2: Plot Spec - Generates Plotly JSON.
    
    Can be called directly or after trigger.
    """
    service = get_plot_pipeline_service(db)
    
    # Convert trigger response to internal format if provided
    trigger_result = None
    if request.trigger_result:
        trigger_result = PlotTriggerResult(
            plot_needed=request.trigger_result.plot_needed,
            plot_type=request.trigger_result.plot_type,
            variables=request.trigger_result.variables,
            ranges=request.trigger_result.ranges,
            reason=request.trigger_result.reason,
            series_plan=request.trigger_result.series_plan,
            key_points=request.trigger_result.key_points,
        )
    
    result = await service._call_plot_spec(
        problem_text=request.problem_text,
        solve_result=request.solve_result,
        attach_to_step_id=request.attach_to_step_id,
        tier=request.tier,
        question_id=request.question_id,
        trigger_result=trigger_result,
    )
    
    return PlotSpecResponse(
        plot_id=result.plot_id,
        attach_to_step_id=result.attach_to_step_id,
        plotly_json=result.plotly_json,
        error=result.error,
    )


@router.post("/pipeline", response_model=PlotPipelineResponse)
async def plot_pipeline_v1(
    request: PlotPipelineRequest,
    db: Session = Depends(get_session),
) -> PlotPipelineResponse:
    """
    Complete plotting pipeline - trigger + spec in one call.
    
    Handles both fast (skip trigger) and reliable (two-stage) pipelines.
    """
    service = get_plot_pipeline_service(db)
    
    trigger_result, spec_result = await service.execute_plotting_pipeline(
        problem_text=request.problem_text,
        solve_result=request.solve_result,
        graph_mode=request.graph_mode,  # type: ignore
        attach_to_step_id=request.attach_to_step_id,
        tier=request.tier,
        question_id=request.question_id,
        use_reliable_pipeline=request.use_reliable_pipeline,
    )
    
    response = PlotPipelineResponse(
        plot_generated=spec_result is not None and not spec_result.error,
    )
    
    if trigger_result:
        response.trigger = PlotTriggerResponse(
            plot_needed=trigger_result.plot_needed,
            plot_type=trigger_result.plot_type,
            variables=trigger_result.variables,
            ranges=trigger_result.ranges,
            reason=trigger_result.reason,
            series_plan=trigger_result.series_plan,
            key_points=trigger_result.key_points,
            error=trigger_result.error,
        )
    
    if spec_result:
        response.spec = PlotSpecResponse(
            plot_id=spec_result.plot_id,
            attach_to_step_id=spec_result.attach_to_step_id,
            plotly_json=spec_result.plotly_json,
            error=spec_result.error,
        )
    
    if not response.plot_generated:
        if trigger_result and trigger_result.error:
            response.error = f"Trigger failed: {trigger_result.error}"
        elif spec_result and spec_result.error:
            response.error = f"Spec failed: {spec_result.error}"
        else:
            response.error = "No plot generated"
    
    return response


@router.post("/render-svg", response_model=PlotRenderSvgResponse)
async def render_plot_svg_endpoint(
    payload: PlotRenderSvgRequest,
    request: Request,
) -> PlotRenderSvgResponse:
    """
    Render a stored plot recipe to deterministic SVG with Redis/disk cache.
    """
    _enforce_plot_rate_limit(request)

    if not payload.plot.should_visualize:
        raise HTTPException(status_code=400, detail="plot.should_visualize is false")

    recipe = payload.plot.recipe
    render_options = payload.render_options.model_dump()
    cache_key = build_cache_key(recipe, render_options)

    cached_svg = get_cached_svg(cache_key)
    if cached_svg:
        return PlotRenderSvgResponse(
            cache_key=cache_key,
            svg=cached_svg,
            meta=PlotRenderSvgMeta(render_ms=0, cached=True, warnings=[]),
        )

    try:
        svg, warnings, render_ms = await asyncio.wait_for(
            asyncio.to_thread(
                render_recipe_svg,
                recipe,
                width_px=payload.render_options.width_px,
                height_px=payload.render_options.height_px,
                font_scale=payload.render_options.font_scale,
            ),
            timeout=3.5,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail="Plot rendering timeout") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("plot_render_svg_failed")
        raise HTTPException(status_code=422, detail=f"Plot render failed: {exc}") from exc

    if not svg or "<svg" not in svg.lower():
        raise HTTPException(status_code=422, detail="Renderer did not produce valid SVG")

    set_cached_svg(cache_key, svg)
    return PlotRenderSvgResponse(
        cache_key=cache_key,
        svg=svg,
        meta=PlotRenderSvgMeta(render_ms=render_ms, cached=False, warnings=warnings),
    )
