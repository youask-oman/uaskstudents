"""
Pydantic v2 models for Math Solver V3 (North America).

Based on JSON Schema v1.0 from static_design/solver_developer.txt.
This is the canonical schema for tutoring-quality math solutions.
"""

from typing import List, Optional, Literal, Union, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from app.utils.schema_cleaner import enforce_strict

# ============================================================================
# Enums
# ============================================================================

class TaskEnum(str, Enum):
    SOLVE_EQUATION = "solve_equation"
    SOLVE_INEQUALITY = "solve_inequality"
    SIMPLIFY = "simplify"
    FACTOR = "factor"
    EXPAND = "expand"
    EVALUATE = "evaluate"
    GRAPH = "graph"
    FIND_INTERCEPTS = "find_intercepts"
    FIND_VERTEX = "find_vertex"
    FIND_EXTREMA = "find_extrema"
    FIND_ROOTS = "find_roots"
    SYSTEM_SOLVE = "system_solve"
    SYSTEM = "system"  # Fallback alias returned by some LLM responses
    SOLVE = "solve"  # Fallback alias returned by some LLM responses
    WORD_PROBLEM = "word_problem"
    GEOMETRY = "geometry"
    TRIGONOMETRY = "trigonometry"
    CALCULUS_DERIVATIVE = "calculus_derivative"
    CALCULUS_INTEGRAL = "calculus_integral"
    STATISTICS = "statistics"
    PROBABILITY = "probability"
    SEQUENCE_SERIES = "sequence_series"
    OTHER = "other"

class GradeBandEnum(str, Enum):
    K_2 = "K-2"
    NR_3_5 = "3-5"
    NR_6_8 = "6-8"
    NR_9_10 = "9-10"
    NR_11_12 = "11-12"
    COLLEGE_INTRO = "college_intro"
    UNKNOWN = "unknown"

class DomainEnum(str, Enum):
    ARITHMETIC = "arithmetic"
    ALGEBRA = "algebra"
    GEOMETRY = "geometry"
    TRIGONOMETRY = "trigonometry"
    CALCULUS = "calculus"
    STATISTICS = "statistics"
    PROBABILITY = "probability"
    DISCRETE = "discrete"
    MIXED = "mixed"
    UNKNOWN = "unknown"

class DifficultyEnum(str, Enum):
    EASY = "easy"
    STANDARD = "standard"
    CHALLENGING = "challenging"
    UNKNOWN = "unknown"

class VisualKindEnum(str, Enum):
    NONE = "none"
    NUMBER_LINE = "number_line"
    TABLE = "table"
    DIAGRAM = "diagram"

class PlotTypeEnum(str, Enum):
    CARTESIAN_2D = "cartesian_2d"
    CARTESIAN_3D = "cartesian_3d"
    NUMBER_LINE_1D = "number_line_1d"
    COORDINATE_GEOMETRY_2D = "coordinate_geometry_2d"
    STATISTICS_CHART = "statistics_chart"

class SeriesKindEnum(str, Enum):
    FUNCTION_Y_OF_X = "function_y_of_x"
    IMPLICIT = "implicit"
    PARAMETRIC = "parametric"
    SCATTER = "scatter"
    LINE_SEGMENTS = "line_segments"
    HISTOGRAM = "histogram"
    BAR = "bar"

# ============================================================================
# Definitions ($defs)
# ============================================================================

class PointV3(BaseModel):
    x: float
    y: float
    label: str

class SeriesV3(BaseModel):
    name: str
    kind: SeriesKindEnum
    expression_latex: str
    points: Optional[List[PointV3]] = None
    style_hint: Optional[str] = None

class AnnotationV3(BaseModel):
    text: str
    x: float
    y: float

class PlotSpecV3(BaseModel):
    plot_id: str
    plot_type: PlotTypeEnum
    title: str
    x_label: str
    y_label: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    series: Optional[List[SeriesV3]] = None
    key_points: Optional[List[PointV3]] = None
    annotations: Optional[List[AnnotationV3]] = None

# ============================================================================
# Top Level Components
# ============================================================================

class ProblemDefinitionV3(BaseModel):
    original_text: str
    normalized_text: str
    detected_tasks: List[TaskEnum]

class ClassificationV3(BaseModel):
    grade_band: GradeBandEnum
    domain: DomainEnum
    topic: str
    difficulty: DifficultyEnum

class RefusalV3(BaseModel):
    is_refusal: bool
    reason: Optional[str] = None
    safe_alternative: Optional[str] = None

class CheckpointV3(BaseModel):
    question: str
    answer: str

class StepV3(BaseModel):
    index: int = Field(..., ge=1)
    title: str
    explanation: str
    math_latex: Union[str, List[str]]  # Supports both minimal (str) and detailed (List[str]) schemas
    rules_used: List[str]
    checkpoint: CheckpointV3

class FinalValueV3(BaseModel):
    label: str
    value: Union[float, str, None] = None
    value_latex: str

class FinalAnswerV3(BaseModel):
    answer_text: str
    answer_latex: str
    values: List[FinalValueV3]
    units: Optional[str] = None

class AlternativeMethodV3(BaseModel):
    name: str
    summary: str

# VerificationV3 removed in v1.1

class VisualDataPointV3(BaseModel):
    label: str
    x: Optional[float] = None
    y: Optional[float] = None

class AlternativeVisualV3(BaseModel):
    kind: VisualKindEnum
    description: str
    data: Optional[List[VisualDataPointV3]] = None

class VisualsV3(BaseModel):
    should_visualize: bool
    decision_reason: str
    plots: Optional[List[PlotSpecV3]] = None
    alternative_visual: Optional[AlternativeVisualV3] = None

class QualityV3(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0)
    common_mistakes: List[str]

# ============================================================================
# Root Response
# ============================================================================

class SolveResponseV3(BaseModel):
    """
    Complete Math Tutor Response.
    Matches schema v1.0.
    """
    schema_version: Literal["v1.0"] = "v1.0"
    problem: ProblemDefinitionV3
    classification: ClassificationV3
    refusal: RefusalV3
    assumptions: List[str]
    steps: List[StepV3]
    final_answer: FinalAnswerV3
    # verification removed
    visuals: VisualsV3
    quality: QualityV3

# ============================================================================
# Error Response
# ============================================================================

class ErrorResponseV3(BaseModel):
    """Fallback schema when solution fails."""
    error: bool = Field(default=True)
    error_type: str
    message: str
    validation_errors: List[str] = Field(default_factory=list)
    original_problem: Optional[str] = None

# ============================================================================
# Schema Generation
# ============================================================================

def get_json_schema_for_openai_v3() -> dict:
    """
    Generate JSON schema strictly compatible with OpenAI Structured Outputs.
    """
    schema = SolveResponseV3.model_json_schema()
    strict_schema = enforce_strict(schema)
    
    return {
        "name": "math_solver_response",
        "strict": True,
        "schema": strict_schema
    }

if __name__ == "__main__":
    import json
    try:
        s = get_json_schema_for_openai_v3()
        print("Schema generated successfully.")
        print("Top level keys:", list(s['properties'].keys()))
    except Exception as e:
        print(f"Schema generation failed: {e}")
