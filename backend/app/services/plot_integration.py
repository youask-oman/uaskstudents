"""
Standalone helper for integrating plot pipeline into solve_v3_stream.

Usage in solve_v3_stream:
    from app.services.plot_integration import maybe_generate_plot
    
    # After solve completes
    plot_result = await maybe_generate_plot(
        db_session=session,
        problem_text=body.confirmed_text or "",
        solve_result=solve_result,
        graph_mode=body.graph_mode,
        attach_to_step_id=body.attach_to_step_id,
        tier=effective_tier,
        question_id=str(request_id),
        logger=logger,
    )
    
    # Add to response
    final_response["plot"] = plot_result
"""

import logging
from typing import Dict, Any, Optional
from sqlmodel import Session

from app.services.plot_pipeline_service import get_plot_pipeline_service

logger = logging.getLogger(__name__)


async def maybe_generate_plot(
    db_session: Session,
    problem_text: str,
    solve_result: Dict[str, Any],
    graph_mode: Optional[str],
    attach_to_step_id: Optional[int],
    tier: str,
    question_id: str,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Standalone helper to generate plot based on solve result and graph mode.
    
    This function:
    1. Checks graph_mode to decide if plotting is needed
    2. Uses solve.visuals.should_visualize for auto mode
    3. Runs trigger→spec pipeline (reliable) or spec directly (fast)
    4. Handles errors gracefully without failing the solve
    
    Args:
        db_session: SQLModel session for DB access
        problem_text: Original problem text
        solve_result: Complete solve output (must contain 'visuals' key)
        graph_mode: 'off', 'auto', or 'on'
        attach_to_step_id: Step ID to attach plot to (or None)
        tier: User's subscription tier (STANDARD/RESEARCH/FREE)
        question_id: Request ID for tracking
        logger: Optional logger instance
        
    Returns:
        Dict with keys:
        - trigger: PlotTriggerResult fields (if trigger was called)
        - spec: PlotSpecResult fields (if spec was called)
        - plot_generated: bool - whether a plot was produced
        - error: Optional error message
        - pipeline_type: 'fast' | 'reliable' | 'none' - which pipeline was used
    """
    log = logger or logging.getLogger(__name__)
    
    result = {
        "trigger": None,
        "spec": None,
        "plot_generated": False,
        "error": None,
        "pipeline_type": "none",
    }
    
    # Normalize graph_mode
    mode = (graph_mode or "auto").lower().strip()
    
    # Check if plotting is wanted
    if mode == "off":
        log.info("[PLOT_INTEGRATION] graph_mode=off, skipping plot")
        return result
    
    # Check solve's visuals decision for auto mode
    visuals = solve_result.get("visuals", {})
    should_visualize = visuals.get("should_visualize", False)
    
    if mode == "auto" and not should_visualize:
        log.info("[PLOT_INTEGRATION] graph_mode=auto, solve says no visualization needed")
        return result
    
    try:
        # Initialize plot service
        plot_service = get_plot_pipeline_service(db_session)
        
        # Determine pipeline type
        # Fast: graph_mode=on and solve already has good visuals data
        # Reliable: graph_mode=auto, or missing plot details, or want extra safety
        has_good_visuals = (
            visuals.get("plots") or 
            visuals.get("alternative_visual") or
            solve_result.get("final_answer", {}).get("latex")
        )
        use_fast = mode == "on" and has_good_visuals
        
        if use_fast:
            log.info("[PLOT_INTEGRATION] Using FAST pipeline (skip trigger)")
            result["pipeline_type"] = "fast"
        else:
            log.info("[PLOT_INTEGRATION] Using RELIABLE pipeline (trigger→spec)")
            result["pipeline_type"] = "reliable"
        
        # Execute pipeline
        trigger_result, spec_result = await plot_service.execute_plotting_pipeline(
            problem_text=problem_text,
            solve_result=solve_result,
            graph_mode=mode,  # type: ignore
            attach_to_step_id=attach_to_step_id,
            tier=tier,
            question_id=question_id,
            use_reliable_pipeline=not use_fast,
        )
        
        # Store trigger result
        if trigger_result:
            result["trigger"] = {
                "plot_needed": trigger_result.plot_needed,
                "plot_type": trigger_result.plot_type,
                "variables": trigger_result.variables,
                "ranges": trigger_result.ranges,
                "reason": trigger_result.reason,
                "series_plan": trigger_result.series_plan,
                "key_points": trigger_result.key_points,
                "error": trigger_result.error,
            }
            
            # Check if trigger blocked the plot
            if not trigger_result.plot_needed and mode == "on":
                log.warning("[PLOT_INTEGRATION] User wanted plot but trigger refused")
                result["error"] = f"Plot not justified: {trigger_result.reason}"
                return result
        
        # Store spec result
        if spec_result:
            result["spec"] = {
                "plot_id": spec_result.plot_id,
                "attach_to_step_id": spec_result.attach_to_step_id,
                "plotly_json": spec_result.plotly_json,
                "error": spec_result.error,
            }
            
            if not spec_result.error and spec_result.plotly_json:
                result["plot_generated"] = True
                log.info(f"[PLOT_INTEGRATION] Plot generated: {spec_result.plot_id}")
            elif spec_result.error:
                log.error(f"[PLOT_INTEGRATION] Plot spec failed: {spec_result.error}")
                result["error"] = f"Plot generation failed: {spec_result.error}"
        
    except Exception as e:
        log.exception("[PLOT_INTEGRATION] Unexpected error in plot pipeline")
        result["error"] = f"Plot pipeline error: {str(e)}"
        # Don't re-raise - let solve continue without plot
    
    return result


def format_plot_for_response(plot_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Format plot result for frontend response.
    
    Returns None if no plot was generated.
    Returns formatted plot object if successful.
    """
    if not plot_result.get("plot_generated"):
        return None
    
    spec = plot_result.get("spec", {})
    trigger = plot_result.get("trigger", {})
    
    return {
        "plot_id": spec.get("plot_id", "plot_1"),
        "attach_to_step_id": spec.get("attach_to_step_id"),
        "plotly_json": spec.get("plotly_json", {}),
        "plot_type": trigger.get("plot_type", "function"),
        "generated_by": plot_result.get("pipeline_type", "unknown"),
    }
