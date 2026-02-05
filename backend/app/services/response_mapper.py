from typing import Dict, Any, List, Optional
from app.schemas.na_math_solver_v3 import (
    SolveResponseV3, ProblemDefinitionV3, ClassificationV3, RefusalV3, 
    StepV3, CheckpointV3, FinalAnswerV3, VisualsV3, 
    QualityV3, TaskEnum, GradeBandEnum, DomainEnum, DifficultyEnum, 
    VisualKindEnum, FinalValueV3, AlternativeMethodV3, AlternativeVisualV3
)

def map_minimal_to_canonical(
    minimal_data: Dict[str, Any], 
    original_problem_text: str
) -> Dict[str, Any]:
    """
    Converts a minimal Free Tier JSON response (MinimalSolveResponse schema)
    into the full canonical Solver V3 format.
    """
    
    # 1. Problem Definition (Partial Map)
    prob_data = minimal_data.get("problem", {})
    problem = ProblemDefinitionV3(
        original_text=prob_data.get("original_text", original_problem_text),
        normalized_text=prob_data.get("normalized_text", original_problem_text),
        detected_tasks=prob_data.get("detected_tasks", [])
    )
    
    # 2. Classification
    class_data = minimal_data.get("classification", {})
    classification = ClassificationV3(
        grade_band=class_data.get("grade_band", GradeBandEnum.UNKNOWN),
        domain=class_data.get("domain", DomainEnum.UNKNOWN),
        topic=class_data.get("topic", "General"),
        difficulty=class_data.get("difficulty", DifficultyEnum.UNKNOWN)
    )
    
    # 3. Refusal
    ref_data = minimal_data.get("refusal", {})
    refusal = RefusalV3(
        is_refusal=ref_data.get("is_refusal", False),
        reason=ref_data.get("reason") or "",
        safe_alternative=ref_data.get("safe_alternative") or ""
    )
    
    # 4. Steps
    raw_steps = minimal_data.get("steps", [])
    canonical_steps = []
    
    # Handle both list of strings (old minimal) and list of objects (new minimal)
    # The new schema is list of objects.
    
    for idx, step_item in enumerate(raw_steps):
        if isinstance(step_item, dict):
            # New Schema
            canonical_steps.append(StepV3(
                index=step_item.get("index", idx + 1),
                title=step_item.get("title", f"Step {idx + 1}"),
                explanation=step_item.get("explanation", ""),
                math_latex=step_item.get("math_latex", ""),
                rules_used=[], # Minimal doesn't strictly track rules list in earlier versions, but new schema might? New schema has no rules_used in minimal? Check schema.
                # Minimal schema check: "steps": items: properties: index, title, explanation, math_latex, checkpoint. 
                # No rules_used. So empty.
                checkpoint=CheckpointV3(
                    question=step_item.get("checkpoint", {}).get("question", ""),
                    answer=step_item.get("checkpoint", {}).get("answer", "")
                )
            ))
        else:
            # Fallback for string steps (deprecated but safe)
            canonical_steps.append(StepV3(
                index=idx + 1,
                title=f"Step {idx + 1}",
                explanation=str(step_item),
                math_latex="",
                rules_used=[],
                checkpoint=CheckpointV3(question="", answer="")
            ))
        
    # 5. Final Answer
    fa_source = minimal_data.get("final_answer", {})
    answer_text = ""
    answer_latex = ""
    units = ""
    
    if isinstance(fa_source, str):
        answer_text = fa_source
    elif isinstance(fa_source, dict):
        answer_text = fa_source.get("answer_text", "")
        answer_latex = fa_source.get("answer_latex", "")
        units = fa_source.get("units", "")

    final_answer = FinalAnswerV3(
        answer_text=answer_text,
        answer_latex=answer_latex,
        values=[], # Minimal doesn't separate values
        units=units
    )
    
    # 6. Verification - Removed in v1.1
    # qc_data = minimal_data.get("quick_check", {})
    # verification = ...
    
    # 7. Visuals
    needs_visual = minimal_data.get("needs_visual", False)
    plot_sugg = minimal_data.get("plot_suggestion")
    
    plots = []
    if needs_visual and plot_sugg:
        # Construct a PlotV3 from suggestion
        # Schema expects list of PlotSpecV3 (ref #/$defs/plot_spec)
        # We need to build a dict compliant with PlotSpecV3 or use helper models if available?
        # The mapper works with Pydantic models usually. VisualsV3.plots is List[Dict] or List[PlotSpec]? 
        # In V3 schema, `plots` is usually List[Dict] (JSON).
        
        series_obj = {
            "name": "Function",
            "kind": "function_y_of_x",
            "expression_latex": plot_sugg.get("expression_latex", ""),
            "points": plot_sugg.get("key_points", []),
            "style_hint": "solid"
        }
        
        plot_obj = {
            "plot_id": "plot_1",
            "plot_type": "cartesian_2d",
            "title": "Graph",
            "x_label": "x",
            "y_label": "y",
            "x_min": plot_sugg.get("x_min", -10),
            "x_max": plot_sugg.get("x_max", 10),
            "y_min": plot_sugg.get("y_min", -10),
            "y_max": plot_sugg.get("y_max", 10),
            "series": [series_obj],
            "key_points": plot_sugg.get("key_points", []),
            "annotations": []
        }
        plots.append(plot_obj)
    
    visuals = VisualsV3(
        should_visualize=needs_visual,
        decision_reason=plot_sugg.get("notes") if plot_sugg else "No visual needed",
        plots=plots,
        alternative_visual=AlternativeVisualV3(kind=VisualKindEnum.NONE, description="N/A", data=[])
    )
    
    # 8. Quality
    q_data = minimal_data.get("quality", {})
    # Handle confidence range 0-1
    conf_val = q_data.get("confidence", 1.0)
    # Minimal schema has confidence_score or quality.confidence? 
    # New minimal schema has `quality` object with `confidence`. 
    # Check old schema: had `confidence_score` at root.
    # We should support both if transitioning, but strictly new schema uses `quality.confidence`.
    
    # Fallback to root confidence_score if quality empty
    if "confidence_score" in minimal_data:
        conf_val = float(minimal_data["confidence_score"])
        
    quality = QualityV3(
        confidence=float(conf_val),
        common_mistakes=q_data.get("common_mistakes", [])
    )
    
    # Construct Root Object
    response = SolveResponseV3(
        schema_version="v1.0",
        problem=problem,
        classification=classification,
        refusal=refusal,
        assumptions=minimal_data.get("assumptions", []),
        steps=canonical_steps,
        final_answer=final_answer,
        # verification removed
        visuals=visuals,
        quality=quality
    )
    
    return response.model_dump()
