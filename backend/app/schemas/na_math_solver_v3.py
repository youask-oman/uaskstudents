"""
Pydantic v2 models for Math Solver V3 (North America).

Based on JSON Schema Draft 2020-12 from static_design/solver_developer.txt.
This is the canonical schema for tutoring-quality math solutions with:
- Strict validation
- Always-visualize policy
- At least 2 verification methods
- Tutor-grade step-by-step explanations
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class TopicEnum(str, Enum):
    """Mathematical topics."""
    ALGEBRA = "algebra"
    FUNCTIONS = "functions"
    GRAPHING = "graphing"
    GEOMETRY = "geometry"
    TRIGONOMETRY = "trigonometry"
    CALCULUS = "calculus"
    LINEAR_ALGEBRA = "linear_algebra"
    COMPLEX_NUMBERS = "complex_numbers"
    STATISTICS_PROBABILITY = "statistics_probability"
    DISCRETE = "discrete"
    WORD_PROBLEM = "word_problem"
    OTHER = "other"


class PlotTypeEnum(str, Enum):
    """Types of visualizations."""
    FUNCTION = "function"
    IMPLICIT = "implicit"
    PARAMETRIC = "parametric"
    SYSTEM = "system"
    INEQUALITY_REGION = "inequality_region"
    NUMBER_LINE = "number_line"
    GEOMETRY = "geometry"
    COMPLEX_PLANE = "complex_plane"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOXPLOT = "boxplot"
    OTHER = "other"


class ObjectKind(str, Enum):
    """Types of plot objects."""
    CURVE = "curve"
    REGION = "region"
    POINTS = "points"
    LINE = "line"
    VECTOR = "vector"
    SHAPE = "shape"


class SamplingStrategy(str, Enum):
    """Sampling strategies for plots."""
    UNIFORM = "uniform"
    ADAPTIVE = "adaptive"
    PIECEWISE = "piecewise"
    GRID = "grid"


# ============================================================================
# Problem Definition
# ============================================================================

class ProblemV3(BaseModel):
    """Problem definition with context."""
    input: str = Field(..., min_length=1, description="Original problem text")
    topic: TopicEnum = Field(..., description="Mathematical topic")
    goal: str = Field(..., min_length=1, description="What needs to be solved")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made")
    given_data: List[str] = Field(default_factory=list, description="Known information")
    unknowns: List[str] = Field(default_factory=list, description="Variables to solve for")


# ============================================================================
# Analysis
# ============================================================================

class DetectedEntitiesV3(BaseModel):
    """Mathematical entities detected in the problem."""
    expressions: List[str] = Field(default_factory=list)
    equations: List[str] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class AnalysisV3(BaseModel):
    """Problem analysis and solution plan."""
    plan: List[str] = Field(..., min_length=1, description="Solution plan steps")
    detected_entities: DetectedEntitiesV3


# ============================================================================
# Solution
# ============================================================================

class CheckpointV3(BaseModel):
    """Checkpoint question for student understanding."""
    question: str = Field(..., description="Question to ask")
    expected_answer: str = Field(..., description="Expected answer")


class SolutionStepV3(BaseModel):
    """A single step in the solution with tutor-grade detail."""
    index: int = Field(..., ge=1, description="Step number (1-indexed)")
    title: str = Field(..., description="Step heading")
    concept: str = Field(..., min_length=1, description="Mathematical concept used")
    rules_used: List[str] = Field(..., min_length=1, description="Formulas/rules applied")
    work: List[str] = Field(..., min_length=1, description="Mathematical transformations")
    result: str = Field(..., min_length=1, description="Result of this step")
    checkpoint: CheckpointV3 = Field(..., description="Understanding check")


class FinalFormsV3(BaseModel):
    """Various forms of the final answer.""" 
    simplified: Optional[str] = None
    factored: Optional[str] = None
    vertex_form: Optional[str] = None
    standard_form: Optional[str] = None
    general_solution_set: Optional[str] = None


class PointV3(BaseModel):
    """2D point."""
    x: float
    y: float


class InterceptsV3(BaseModel):
    """Function intercepts."""
    x: Optional[List[PointV3]] = None
    y: Optional[PointV3] = None


class FeaturesV3(BaseModel):
    """Mathematical features of the solution."""
    intercepts: Optional[InterceptsV3] = None
    vertex: Optional[PointV3] = None
    axis_of_symmetry: Optional[str] = None
    asymptotes: Optional[List[str]] = None
    turning_points: Optional[List[PointV3]] = None
    domain: Optional[str] = None
    range: Optional[str] = None
    units: Optional[str] = None


class SolutionV3(BaseModel):
    """Complete solution with all steps."""
    final_answer: str = Field(..., min_length=1, description="Concise final answer")
    final_forms: Optional[FinalFormsV3] = None
    steps: List[SolutionStepV3] = Field(..., min_length=1, description="Solution steps")
    key_concepts: List[str] = Field(default_factory=list, description="Key concepts used")
    common_mistakes: List[str] = Field(default_factory=list, description="Common errors to avoid")
    features: Optional[FeaturesV3] = None


# ============================================================================
# Verification
# ============================================================================

class VerificationMethodV3(BaseModel):
    """A method used to verify the solution."""
    method: str = Field(..., description="Method name")
    why_it_works: str = Field(..., description="Why this verification is valid")
    steps: List[str] = Field(..., min_length=1, description="Verification steps")
    conclusion: str = Field(..., description="Verification result")


# ============================================================================
# Plot/Visualization
# ============================================================================

class AxesV3(BaseModel):
    """Axis labels."""
    x_label: str
    y_label: str


class RecommendedWindowV3(BaseModel):
    """Plot window bounds."""
    x_min: float
    x_max: float
    y_min: float
    y_max: float


class StyleHintsV3(BaseModel):
    """Visual style hints."""
    dashed: Optional[bool] = None
    shade: Optional[bool] = None


class PlotObjectV3(BaseModel):
    """An object to plot."""
    kind: ObjectKind
    expression: str = Field(..., description="Mathematical expression")
    label: str
    style_hints: Optional[StyleHintsV3] = None


class AnnotationV3(BaseModel):
    """Plot annotation."""
    name: str
    detail: str
    point: Optional[PointV3] = None


class SamplingV3(BaseModel):
    """Sampling configuration for plots."""
    strategy: SamplingStrategy
    resolution: int = Field(..., ge=50, description="Number of sample points")
    domain_restrictions: Optional[List[str]] = None
    discontinuities: Optional[List[str]] = None


class PlotPlanV3(BaseModel):
    """Complete plot specification."""
    title: str
    axes: AxesV3
    recommended_window: RecommendedWindowV3
    objects: List[PlotObjectV3] = Field(..., min_length=1)
    annotations: List[AnnotationV3] = Field(default_factory=list)
    sampling: SamplingV3


class VisualizationAlternativeV3(BaseModel):
    """Alternative visualization when standard plot not applicable."""
    type: str = Field(..., description="Type of alternative visualization")
    reason_no_standard_plot: str
    instructions: List[str] = Field(..., min_length=1)


class PlotV3(BaseModel):
    """Visualization specification."""
    should_plot: bool = Field(..., description="Whether to generate a plot")
    plot_type: PlotTypeEnum
    plan: PlotPlanV3
    visualization_alternative: Optional[VisualizationAlternativeV3] = None


# ============================================================================
# Similar Examples
# ============================================================================

class SimilarExampleV3(BaseModel):
    """A similar practice problem."""
    problem: str = Field(..., description="Problem statement")
    key_idea: str = Field(..., description="Key concept to practice")
    short_solution: str = Field(..., description="Brief solution approach")


# ============================================================================
# Metadata
# ============================================================================

class LocalizationV3(BaseModel):
    """Localization settings."""
    region: Literal["north_america"] = Field(default="north_america")
    notation: Literal["standard"] = Field(default="standard")


class MetaV3(BaseModel):
    """Response metadata."""
    confidence: float = Field(..., ge=0.0, le=1.0, description="Solution confidence")
    localization: LocalizationV3
    rounding_policy: str = Field(..., description="How numbers are rounded")


# ============================================================================
# Complete Response
# ============================================================================

class SolveResponseV3(BaseModel):
    """
    Complete Math Solver V3 response.
    
    Validates against JSON Schema Draft 2020-12 from solver_developer.txt.
    """
    problem: ProblemV3
    analysis: AnalysisV3
    solution: SolutionV3
    verification: List[VerificationMethodV3] = Field(..., min_length=2, description="At least 2 verification methods")
    plot: PlotV3
    similar_examples: List[SimilarExampleV3] = Field(..., min_length=2, description="At least 2 similar problems")
    meta: MetaV3
    
    @field_validator('verification')
    @classmethod
    def validate_verification_minimum(cls, v):
        """Ensure at least 2 verification methods when possible."""
        if len(v) < 1:
            raise ValueError("Must have at least 1 verification method")
        # Note: Schema requires min 2, but we allow 1 for edge cases
        # The LLM should provide 2+ whenever possible
        return v


# ============================================================================
# Error Response Schema
# ============================================================================

class ErrorResponseV3(BaseModel):
    """Response schema for validation failures."""
    error: bool = Field(default=True)
    error_type: str
    message: str
    validation_errors: List[str] = Field(default_factory=list)
    original_problem: Optional[str] = None


# ============================================================================
# Schema Generation for OpenAI
# ============================================================================

def get_json_schema_for_openai_v3() -> dict:
    """
    Generate JSON schema strictly compatible with OpenAI Structured Outputs.
    Recursively ensures additionalProperties: False and all fields are required.
    Removes nullable unions to discourage null outputs.
    """
    schema = SolveResponseV3.model_json_schema()
    
    def enforce_strict(node: dict):
        if not isinstance(node, dict):
            return node
            
        # Clean metadata
        node.pop('title', None)
        node.pop('description', None)
        node.pop('default', None) # OpenAI strict schema dislikes default values usually
        
        # Handle Object Type
        if node.get("type") == "object" or "properties" in node:
            node["type"] = "object"
            node["additionalProperties"] = False
            
             # OpenAI strict schema requires required to include every property key.
            props = node.get("properties", {})
            node["required"] = list(props.keys()) if props else []

            # Recursively process properties
            for prop_name, prop_schema in props.items():
                enforce_strict(prop_schema)
                
        # Handle Arrays
        if node.get("type") == "array":
            if "items" in node:
                enforce_strict(node["items"])
                
        # Handle Definitions ($defs)
        if "$defs" in node:
            for def_name, def_schema in node["$defs"].items():
                enforce_strict(def_schema)
                
        # Strip nullable unions to avoid null outputs in strict schemas.
        if isinstance(node.get("type"), list):
            node["type"] = [t for t in node["type"] if t != "null"]
            if len(node["type"]) == 1:
                node["type"] = node["type"][0]

        # Handle anyOf / allOf
        for key in ["anyOf", "allOf", "oneOf"]:
            if key in node:
                non_null_nodes = []
                for sub_node in node[key]:
                    if isinstance(sub_node, dict) and sub_node.get("type") == "null":
                        continue
                    enforce_strict(sub_node)
                    non_null_nodes.append(sub_node)
                if key in ["anyOf", "oneOf"] and len(non_null_nodes) == 1:
                    node.pop(key, None)
                    node.update(non_null_nodes[0])
                else:
                    node[key] = non_null_nodes
                    
        return node

    return enforce_strict(schema)


if __name__ == "__main__":
    # Test schema generation
    import json
    
    print("Testing V3 Schema Generation...")
    schema = get_json_schema_for_openai_v3()
    
    print(f"\nTop-level properties: {list(schema['properties'].keys())}")
    print(f"Required fields: {schema['required']}")
    print(f"\nDefinitions: {list(schema.get('$defs', {}).keys())}")
    
    # Test validation with a minimal valid response
    print("\n--- Testing Minimal Valid Response ---")
    minimal_response = {
        "problem": {
            "input": "Solve x + 5 = 10",
            "topic": "algebra",
            "goal": "Find x"
        },
        "analysis": {
            "plan": ["Isolate x"],
            "detected_entities": {
                "expressions": [],
                "equations": ["x+5=10"],
                "functions": [],
                "constraints": []
            }
        },
        "solution": {
            "final_answer": "x = 5",
            "steps": [
                {
                    "index": 1,
                    "title": "Subtract 5",
                    "concept": "Inverse operations",
                    "rules_used": ["Subtraction property of equality"],
                    "work": ["x + 5 - 5 = 10 - 5", "x = 5"],
                    "result": "x = 5",
                    "checkpoint": {
                        "question": "What is x?",
                        "expected_answer": "5"
                    }
                }
            ]
        },
        "verification": [
            {
                "method": "Substitution",
                "why_it_works": "Plugging answer back verifies it satisfies original equation",
                "steps": ["5 + 5 = 10 ✓"],
                "conclusion": "Solution is correct"
            },
            {
                "method": "Inverse check",
                "why_it_works": "Applying inverse operations confirms the result",
                "steps": ["10 - 5 = 5 ✓"],
                "conclusion": "Confirmed"
            }
        ],
        "plot": {
            "should_plot": False,
            "plot_type": "number_line",
            "plan": {
                "title": "Solution on number line",
                "axes": {"x_label": "x", "y_label": ""},
                "recommended_window": {"x_min": 0, "x_max": 10, "y_min": -1, "y_max": 1},
                "objects": [
                    {"kind": "points", "expression": "x=5", "label": "Solution"}
                ],
                "annotations": [],
                "sampling": {"strategy": "uniform", "resolution": 100}
            }
        },
        "similar_examples": [
            {
                "problem": "Solve x + 3 = 8",
                "key_idea": "Inverse operations",
                "short_solution": "Subtract 3 from both sides: x = 5"
            },
            {
                "problem": "Solve x - 2 = 7",
                "key_idea": "Inverse operations",
                "short_solution": "Add 2 to both sides: x = 9"
            }
        ],
        "meta": {
            "confidence": 0.95,
            "localization": {"region": "north_america", "notation": "standard"},
            "rounding_policy": "Round to 2 decimal places when needed"
        }
    }
    
    try:
        validated = SolveResponseV3(**minimal_response)
        print("✅ Minimal response validated successfully!")
        print(f"   - Problem: {validated.problem.goal}")
        print(f"   - Steps: {len(validated.solution.steps)}")
        print(f"   - Verification methods: {len(validated.verification)}")
        print(f"   - Should plot: {validated.plot.should_plot}")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
