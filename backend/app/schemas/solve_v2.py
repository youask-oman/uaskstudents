"""
Pydantic v2 models for Solver V2 with OpenAI Structured Outputs.

This module defines the comprehensive schema for tutoring-quality math/physics solutions
with enhanced depth, proactive visuals, verification, and conceptual explanations.
"""

from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Problem Definition
# ============================================================================

class ProblemDefinitionV2(BaseModel):
    """Enhanced problem definition with structured context."""
    goal: str = Field(..., description="Brief description of what needs to be solved")
    latex: Optional[str] = Field(None, description="Original problem in LaTeX notation")
    givens: List[str] = Field(default_factory=list, description="Known information")
    unknowns: List[str] = Field(default_factory=list, description="What we're solving for")
    assumptions: List[str] = Field(default_factory=list, description="Any assumptions made")


# ============================================================================
# Solution Components
# ============================================================================

class MathBlock(BaseModel):
    """Mathematical expressions in LaTeX."""
    latex_lines: List[str] = Field(..., description="Array of LaTeX expressions")


class SolutionStepV2(BaseModel):
    """Enhanced solution step with tutoring context."""
    index: int = Field(..., description="Step number (1-indexed)", ge=1)
    title: str = Field(..., description="Step heading")
    explanation: str = Field(..., description="2-5+ sentences for non-trivial steps", min_length=10)
    why: str = Field(..., description="Why this step is mathematically valid", min_length=10)
    math: MathBlock = Field(..., description="Mathematical expressions")
    common_mistake: str = Field(..., description="What students often do wrong here", min_length=10)
    checkpoint: str = Field(..., description="Question to verify understanding", min_length=10)
    visual_refs: List[str] = Field(default_factory=list, description="IDs of visuals referenced")


class SolutionV2(BaseModel):
    """Complete solution with planning and steps."""
    plan: List[str] = Field(..., description="1-3 planning bullets", min_length=1, max_length=3)
    steps: List[SolutionStepV2] = Field(..., description="Solution steps", min_length=2)
    final_answer: str = Field(..., description="Concise final answer", min_length=1)


# ============================================================================
# Verification
# ============================================================================

class VerificationMethodV2(BaseModel):
    """A method used to verify the solution."""
    name: str = Field(..., description="Method name (e.g., 'Substitution Check')")
    description: str = Field(..., description="What this method does")
    steps: List[str] = Field(..., description="Verification steps", min_length=1)
    expected_result: str = Field(..., description="What we expect to see")


class VerificationV2(BaseModel):
    """Verification of the solution."""
    methods_used: List[VerificationMethodV2] = Field(..., description="Verification methods", min_length=1)


# ============================================================================
# Concepts
# ============================================================================

class ConceptV2(BaseModel):
    """Mathematical or physical concept with context."""
    name: str = Field(..., description="Concept name")
    description: str = Field(..., description="General description")
    applies_here: str = Field(..., description="How it applies to this specific problem", min_length=10)


# ============================================================================
# Visuals
# ============================================================================

class FunctionDef(BaseModel):
    """Function definition for plotting."""
    latex: str = Field(..., description="Function in LaTeX")
    variable: str = Field(..., description="Independent variable")


class Domain(BaseModel):
    """Domain for function plotting."""
    x_min_latex: str = Field(..., description="Minimum x value")
    x_max_latex: str = Field(..., description="Maximum x value")


class Point(BaseModel):
    """2D point."""
    x: str = Field(..., description="X coordinate")
    y: str = Field(..., description="Y coordinate")


class FunctionLabel(BaseModel):
    """Labeled function for multi-plot."""
    latex: str = Field(..., description="Function in LaTeX")
    variable: str = Field(..., description="Independent variable")
    label: str = Field(..., description="Function label")


class Interval(BaseModel):
    """Interval for number line."""
    from_: str = Field(..., alias="from", description="Start value")
    to: str = Field(..., description="End value")
    closed_left: bool = Field(..., description="Left endpoint closed")
    closed_right: bool = Field(..., description="Right endpoint closed")


class VisualRequestV2(BaseModel):
    """Visual plot request with type-specific fields."""
    id: str = Field(..., description="Unique identifier (e.g., 'v1')")
    type: Literal["function_plot_request", "line_plot", "multi_plot_request", "number_line"] = Field(
        ..., description="Visual type"
    )
    title: str = Field(..., description="Visual title")
    why_included: str = Field(..., description="Educational rationale")
    
    # Type-specific fields (optional depending on type)
    function: Optional[FunctionDef] = Field(None, description="For function_plot_request")
    domain: Optional[Domain] = Field(None, description="For function_plot_request")
    points: Optional[List[Point]] = Field(None, description="For line_plot", min_length=2, max_length=2)
    functions: Optional[List[FunctionLabel]] = Field(None, description="For multi_plot_request", min_length=2)
    domain_multi: Optional[Domain] = Field(None, description="For multi_plot_request")
    intervals: Optional[List[Interval]] = Field(None, description="For number_line", min_length=1)


class VisualPolicyV2(BaseModel):
    """Visual policy indicating if visuals are required."""
    required: bool = Field(..., description="True if visuals are mandatory for this problem type")
    reason: str = Field(..., description="Why visuals are required/not required")


# ============================================================================
# Complete Response
# ============================================================================

class SolveResponseV2(BaseModel):
    """Complete solver response with tutoring depth."""
    problem: ProblemDefinitionV2
    solution: SolutionV2
    verification: VerificationV2
    concepts: List[ConceptV2] = Field(..., min_length=3, max_length=5)
    visual_policy: VisualPolicyV2
    visuals_suggested: List[VisualRequestV2] = Field(default_factory=list)
    visuals: List[VisualRequestV2] = Field(default_factory=list)
    response_intent: List[str] = Field(default_factory=list)
    difficulty: Literal["trivial", "standard", "advanced"] = Field(..., description="Problem difficulty")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence 0.0-1.0")
    
    @field_validator('concepts')
    @classmethod
    def validate_concepts_count(cls, v):
        """Ensure 3-5 concepts."""
        if not (3 <= len(v) <= 5):
            raise ValueError(f"Expected 3-5 concepts, got {len(v)}")
        return v
    
    @field_validator('verification')
    @classmethod
    def validate_verification_methods(cls, v, info):
        """Validate minimum verification methods based on difficulty."""
        difficulty = info.data.get('difficulty')
        min_methods = 1 if difficulty == 'trivial' else 2
        if len(v.methods_used) < min_methods:
            raise ValueError(f"Difficulty '{difficulty}' requires >={min_methods} verification methods")
        return v
    
    @field_validator('solution')
    @classmethod
    def validate_steps_count(cls, v, info):
        """Validate steps count based on difficulty."""
        difficulty = info.data.get('difficulty')
        step_count = len(v.steps)
        
        if difficulty == 'trivial' and not (2 <= step_count <= 4):
            raise ValueError(f"Trivial difficulty expects 2-4 steps, got {step_count}")
        elif difficulty == 'standard' and not (4 <= step_count <= 10):
            raise ValueError(f"Standard difficulty expects 4-10 steps, got {step_count}")
        elif difficulty == 'advanced' and not (7 <= step_count <= 14):
            raise ValueError(f"Advanced difficulty expects 7-14 steps, got {step_count}")
        
        return v


# ============================================================================
# JSON Schema Generation
# ============================================================================

def get_json_schema_for_openai() -> dict:
    """
    Generate JSON schema compatible with OpenAI Structured Outputs.
    
    Returns:
        dict: JSON schema for text.format json_schema.schema
    """
    schema = SolveResponseV2.model_json_schema()
    
    # Clean up for OpenAI compatibility
    # Remove title if it exists (OpenAI doesn't need it)
    schema.pop('title', None)
    
    # Ensure all required fields are marked
    # OpenAI Structured Outputs requires strict: true
    return {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
        "additionalProperties": False
    }


if __name__ == "__main__":
    # Example: Generate and print schema
    import json
    schema = get_json_schema_for_openai()
    print(json.dumps(schema, indent=2))
