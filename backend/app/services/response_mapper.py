from typing import Dict, Any, List, Optional
from app.schemas.na_math_solver_v3 import (
    SolveResponseV3, ProblemDefinitionV3, ClassificationV3, RefusalV3, 
    StepV3, CheckpointV3, FinalAnswerV3, VisualsV3, 
    QualityV3, TaskEnum, GradeBandEnum, DomainEnum, DifficultyEnum, 
    VisualKindEnum, FinalValueV3, AlternativeMethodV3, AlternativeVisualV3
)

# ============================================================================
# LLM Output Normalization Maps
# ============================================================================
# The LLM sometimes returns slightly different task/domain names than
# the strict enum values. These maps normalize common variations.

TASK_NORMALIZATION_MAP = {
    # Common LLM variations -> valid TaskEnum values
    "equation": "solve_equation",
    "inequality": "solve_inequality",
    "solving": "solve_equation",
    "simplification": "simplify",
    "factoring": "factor",
    "factorize": "factor",
    "expansion": "expand",
    "evaluation": "evaluate",
    "graphing": "graph",
    "plot": "graph",
    "roots": "find_roots",
    "intercepts": "find_intercepts",
    "vertex": "find_vertex",
    "extrema": "find_extrema",
    "system_of_equations": "system_solve",
    "systems": "system_solve",
    "derivative": "calculus_derivative",
    "differentiate": "calculus_derivative",
    "integral": "calculus_integral",
    "integrate": "calculus_integral",
    "word": "word_problem",
    "trig": "trigonometry",
    "stats": "statistics",
    "prob": "probability",
    "sequences": "sequence_series",
    "series": "sequence_series",
}

DOMAIN_NORMALIZATION_MAP = {
    # Common LLM variations -> valid DomainEnum values
    "pre_algebra": "algebra",
    "pre-algebra": "algebra",
    "prealgebra": "algebra", 
    "linear_algebra": "algebra",
    "abstract_algebra": "algebra",
    "number_theory": "discrete",
    "combinatorics": "discrete",
    "trig": "trigonometry",
    "calc": "calculus",
    "stats": "statistics",
    "prob": "probability",
    "geom": "geometry",
    "arith": "arithmetic",
}

GRADE_BAND_NORMALIZATION_MAP = {
    # Common LLM variations -> valid GradeBandEnum values
    "k-2": "K-2",
    "k2": "K-2",
    "kindergarten": "K-2",
    "3-5": "3-5",
    "elementary": "3-5",
    "6-8": "6-8",
    "middle_school": "6-8",
    "middle school": "6-8",
    "9-10": "9-10",
    "high_school": "9-10",
    "high school": "9-10",
    "11-12": "11-12",
    "advanced_high_school": "11-12",
    "college": "college_intro",
    "university": "college_intro",
    "undergraduate": "college_intro",
}

DIFFICULTY_NORMALIZATION_MAP = {
    "basic": "easy",
    "simple": "easy",
    "beginner": "easy",
    "medium": "standard",
    "moderate": "standard",
    "intermediate": "standard",
    "hard": "challenging",
    "difficult": "challenging",
    "advanced": "challenging",
}


def _normalize_task(task: str) -> str:
    """Normalize a task string to a valid TaskEnum value."""
    task_lower = task.lower().strip()
    # First check if already valid
    valid_tasks = {e.value for e in TaskEnum}
    if task_lower in valid_tasks:
        return task_lower
    # Try normalization map
    if task_lower in TASK_NORMALIZATION_MAP:
        return TASK_NORMALIZATION_MAP[task_lower]
    # Default to 'other'
    return "other"


def _normalize_domain(domain: str) -> str:
    """Normalize a domain string to a valid DomainEnum value."""
    domain_lower = domain.lower().strip()
    valid_domains = {e.value for e in DomainEnum}
    if domain_lower in valid_domains:
        return domain_lower
    if domain_lower in DOMAIN_NORMALIZATION_MAP:
        return DOMAIN_NORMALIZATION_MAP[domain_lower]
    return "unknown"


def _normalize_grade_band(grade: str) -> str:
    """Normalize a grade band string to a valid GradeBandEnum value."""
    grade_lower = grade.lower().strip()
    valid_grades = {e.value for e in GradeBandEnum}
    # Direct match (case-insensitive for some)
    for valid in valid_grades:
        if grade_lower == valid.lower():
            return valid
    if grade_lower in GRADE_BAND_NORMALIZATION_MAP:
        return GRADE_BAND_NORMALIZATION_MAP[grade_lower]
    return "unknown"


def _normalize_difficulty(difficulty: str) -> str:
    """Normalize a difficulty string to a valid DifficultyEnum value."""
    diff_lower = difficulty.lower().strip()
    valid_diffs = {e.value for e in DifficultyEnum}
    if diff_lower in valid_diffs:
        return diff_lower
    if diff_lower in DIFFICULTY_NORMALIZATION_MAP:
        return DIFFICULTY_NORMALIZATION_MAP[diff_lower]
    return "unknown"


def normalize_raw_llm_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw LLM response data in-place before Pydantic validation.
    
    This handles variations in enum values that the LLM might produce,
    converting them to values that match the strict Pydantic enums.
    
    Safe to call on both minimal and detailed responses.
    """
    if not isinstance(data, dict):
        return data
    
    # Normalize problem.detected_tasks
    if "problem" in data and isinstance(data["problem"], dict):
        raw_tasks = data["problem"].get("detected_tasks", [])
        if isinstance(raw_tasks, list):
            data["problem"]["detected_tasks"] = [
                _normalize_task(t) for t in raw_tasks if isinstance(t, str)
            ]
    
    # Normalize classification fields
    if "classification" in data and isinstance(data["classification"], dict):
        cls = data["classification"]
        
        if "domain" in cls and isinstance(cls["domain"], str):
            cls["domain"] = _normalize_domain(cls["domain"])
        
        if "grade_band" in cls and isinstance(cls["grade_band"], str):
            cls["grade_band"] = _normalize_grade_band(cls["grade_band"])
        
        if "difficulty" in cls and isinstance(cls["difficulty"], str):
            cls["difficulty"] = _normalize_difficulty(cls["difficulty"])
    
    return data


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
    # Normalize detected_tasks before Pydantic validation
    raw_tasks = prob_data.get("detected_tasks", [])
    normalized_tasks = [_normalize_task(t) for t in raw_tasks if isinstance(t, str)]
    
    problem = ProblemDefinitionV3(
        original_text=prob_data.get("original_text", original_problem_text),
        normalized_text=prob_data.get("normalized_text", original_problem_text),
        detected_tasks=normalized_tasks
    )
    
    # 2. Classification - normalize enum values
    class_data = minimal_data.get("classification", {})
    raw_grade = class_data.get("grade_band", "unknown")
    raw_domain = class_data.get("domain", "unknown")
    raw_difficulty = class_data.get("difficulty", "unknown")
    
    classification = ClassificationV3(
        grade_band=_normalize_grade_band(raw_grade) if isinstance(raw_grade, str) else raw_grade,
        domain=_normalize_domain(raw_domain) if isinstance(raw_domain, str) else raw_domain,
        topic=class_data.get("topic", "General"),
        difficulty=_normalize_difficulty(raw_difficulty) if isinstance(raw_difficulty, str) else raw_difficulty
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
