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
                log.warning("[PLOT_INTEGRATION] User wanted plot but trigger refused. Trying fallback.")
                # We'll try fallback below if spec_result is missing
        
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
                log.info(f"[PLOT_INTEGRATION] Plot generated (LLM): {spec_result.plot_id}")
            elif spec_result.error:
                log.error(f"[PLOT_INTEGRATION] Plot spec failed: {spec_result.error}")
                result["error"] = f"Plot generation failed: {spec_result.error}"

        # --- FALLBACK TO MATPLOTLIB MODEL ---
        if not result["plot_generated"] and mode in ("on", "auto"):
            if mode == "on" or (mode == "auto" and should_visualize):
                log.info("[PLOT_INTEGRATION] LLM plot failed or missing. Trying Matplotlib fallback.")
                try:
                    fallback_plotly = await generate_matplotlib_fallback(problem_text, solve_result)
                    if fallback_plotly:
                        result["spec"] = {
                            "plot_id": "plot_matplotlib_fallback",
                            "attach_to_step_id": attach_to_step_id,
                            "plotly_json": fallback_plotly,
                            "error": None,
                        }
                        result["plot_generated"] = True
                        result["pipeline_type"] = "matplotlib_fallback"
                        log.info("[PLOT_INTEGRATION] Matplotlib fallback plot generated.")
                except Exception as fe:
                    log.error(f"[PLOT_INTEGRATION] Matplotlib fallback failed: {fe}")

    except Exception as e:
        log.exception("[PLOT_INTEGRATION] Unexpected error in plot pipeline")
        result["error"] = f"Plot pipeline error: {str(e)}"
        # Don't re-raise - let solve continue without plot
    
    return result


async def generate_matplotlib_fallback(
    problem_text: str,
    solve_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Generate a Plotly-compatible JSON using the local Matplotlib-based engine.
    Used when the LLM pipeline fails to produce a plot.
    """
    try:
        from app.services.visualization.decision_engine import get_visualization_engine
        from app.services.visualization.plot_renderer import get_plot_renderer
        import re

        engine = get_visualization_engine()
        renderer = get_plot_renderer()

        # Extract entities heuristically if not present
        entities = solve_result.get("problem", {}).get("detected_entities")
        if not entities:
            # Simple extraction: look for y=... or f(x)=...
            # This matches y=x^2, f(x)=sin(x), etc.
            found_funcs = re.findall(r'[yf]\(x\)?\s*=\s*[^,;]+', problem_text)
            if not found_funcs:
                # Try just expressions with x
                found_funcs = re.findall(r'[x0-9\+\-\*\/\^\(\)\.]{2,}', problem_text)
                found_funcs = [f for f in found_funcs if 'x' in f and len(f) > 3]

            entities = {
                "functions": found_funcs,
                "equations": found_funcs,
                "detected_entities": {"functions": found_funcs, "equations": found_funcs}
            }

        analysis = {"detected_entities": entities}
        decision = engine.should_visualize(problem_text, analysis)

        if not decision.should_visualize:
            return None

        plan = engine.generate_plot_plan(decision.plot_type, entities)
        series_data = renderer.generate_data(plan)

        if not series_data:
            return None

        # Convert to Plotly JSON
        plotly_data = []
        for s in series_data:
            plotly_data.append({
                "name": s["label"],
                "x": [p["x"] for p in s["points"]],
                "y": [p["y"] for p in s["points"]],
                "mode": "lines",
                "type": "scatter"
            })

        return {
            "data": plotly_data,
            "layout": {
                "title": plan.title,
                "xaxis": {"title": plan.axes.x_label},
                "yaxis": {"title": plan.axes.y_label}
            }
        }
    except Exception:
        # Quietly fail if fallback has issues
        return None


def format_plot_for_response(plot_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Format plot result for frontend response.
    
    Returns None if no plot was generated.
    Returns formatted plot object if successful.
    """
    if not plot_result.get("plot_generated"):
        return None
    
    spec = plot_result.get("spec") or {}
    trigger = plot_result.get("trigger") or {}
    
    return {
        "plot_id": spec.get("plot_id", "plot_1"),
        "attach_to_step_id": spec.get("attach_to_step_id"),
        "plotly_json": spec.get("plotly_json", {}),
        "plot_type": trigger.get("plot_type", "function"),
        "generated_by": plot_result.get("pipeline_type", "unknown"),
    }


def apply_graph_mode_override(
    solve_result: Dict[str, Any], 
    graph_mode: str,
    plot_generated: bool = False
) -> Dict[str, Any]:
    """
    Enforce deterministic behavior on the solve_result based on graph_mode.
    
    Rules:
    - 'off': visuals.should_visualize = False, visuals.plots = [], visuals.alternative_visual = None
    - 'on': visuals.should_visualize = True
    - 'auto': visuals.should_visualize = solve_result.visuals.should_visualize OR plot_generated
    
    Args:
        solve_result: The raw solve output (V3 schema)
        graph_mode: off | auto | on
        plot_generated: Whether the plotting pipeline successfully produced a plot
        
    Returns:
        Updated solve_result
    """
    mode = (graph_mode or "auto").lower().strip()
    print(f"[PLOT_OVERRIDE] mode='{mode}', initial_should_visualize={solve_result.get('visuals', {}).get('should_visualize')}")

    
    # Ensure visuals key exists
    if "visuals" not in solve_result:
        solve_result["visuals"] = {
            "should_visualize": False,
            "decision_reason": "Default (Injected)",
            "plots": [],
            "alternative_visual": None
        }
    
    visuals = solve_result["visuals"]
    
    if mode == "off":
        visuals["should_visualize"] = False
        visuals["plots"] = []
        visuals["alternative_visual"] = None
        visuals["decision_reason"] = "Forced OFF by user graph_mode=off"
        
    elif mode == "on":
        # Force visualization even if LLM said no
        visuals["should_visualize"] = True
        visuals["decision_reason"] = "Forced ON by user graph_mode=on"
             
    elif mode == "auto":
        # If plot was generated by pipeline, ensure should_visualize is true
        if plot_generated:
            visuals["should_visualize"] = True
            
    return solve_result

