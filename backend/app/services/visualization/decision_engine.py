"""
Visualization Decision Engine for Math Solver V3.

Determines whether a problem should be visualized and generates
appropriate plot plans for graphable mathematical content.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.schemas.na_math_solver_v3 import (
    PlotTypeEnum,
    PlotPlanV3,
    AxesV3,
    RecommendedWindowV3,
    PlotObjectV3,
    AnnotationV3,
    SamplingV3,
    ObjectKind,
    SamplingStrategy,
    VisualizationAlternativeV3
)


@dataclass
class VisualizationDecision:
    """Decision about whether and how to visualize."""
    should_visualize: bool
    plot_type: str
    reason: str
    confidence: float  # 0.0 to 1.0


class VisualizationEngine:
    """
    Decides whether a problem should be visualized and generates plot plans.
    
    Always-Visualize Policy:
    - If the problem has graphable content, ALWAYS set should_plot=true
    - For non-graphable content, provide visualization_alternative
    """
    
    def __init__(self):
        """Initialize visualization engine."""
        self.visual_keywords = [
            'graph', 'plot', 'draw', 'sketch', 'diagram', 'chart',
            'visualize', 'show', 'illustrate', 'picture'
        ]
    
    def should_visualize(
        self,
        problem_text: str,
        analysis: Dict[str, Any]
    ) -> VisualizationDecision:
        """
        Determine if visualization is appropriate.
        
        Args:
            problem_text: The problem statement
            analysis: Problem analysis with detected entities
        
        Returns:
            VisualizationDecision with recommendation
        """
        text_lower = problem_text.lower()
        entities = analysis.get('detected_entities', {})
        
        # 1. Explicit user request
        has_visual_keyword = any(kw in text_lower for kw in self.visual_keywords)
        if has_visual_keyword:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="function",  # Default, will be refined
                reason="User explicitly requested visualization",
                confidence=1.0
            )
        
        # 2. Functions (always plot)
        functions = entities.get('functions', [])
        if functions:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="function" if len(functions) == 1 else "system",
                reason=f"Problem contains {len(functions)} function(s)",
                confidence=0.95
            )
        
        # 3. Systems of equations (2+ equations)
        equations = entities.get('equations', [])
        if len(equations) >= 2:
            # Check if they can be treated as y=f(x)
            has_y_equals = any('y=' in eq or 'y =' in eq for eq in equations)
            if has_y_equals:
                return VisualizationDecision(
                    should_visualize=True,
                    plot_type="system",
                    reason="System of equations with multiple functions",
                    confidence=0.9
                )
        
        # 4. Inequalities (number line visualization)
        has_inequality = any(op in problem_text for op in ['<', '>', '≤', '≥', 'less than', 'greater than'])
        if has_inequality and len(equations) > 0:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="inequality_region" if 'y' in problem_text else "number_line",
                reason="Inequality problem benefits from number line or region visualization",
                confidence=0.85
            )
        
        # 5. Quadratic equations (parabola plot)
        is_quadratic = 'x^2' in problem_text or 'x²' in problem_text or 'quadratic' in text_lower
        if is_quadratic:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="function",
                reason="Quadratic equation benefits from parabola visualization",
                confidence=0.9
            )
        
        # 6. Trigonometric functions
        trig_funcs = ['sin', 'cos', 'tan', 'cot', 'sec', 'csc']
        has_trig = any(f in text_lower for f in trig_funcs)
        if has_trig:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="function",
                reason="Trigonometric function benefits from periodic visualization",
                confidence=0.88
            )
        
        # 7. Statistics data (histogram/scatter)
        is_stats = any(kw in text_lower for kw in ['mean', 'median', 'mode', 'data', 'histogram', 'scatter'])
        if is_stats:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="histogram",
                reason="Statistical data benefits from distribution visualization",
                confidence=0.8
            )
        
        # 8. Geometry problems (geometric diagram)
        is_geometry = any(kw in text_lower for kw in ['triangle', 'circle', 'rectangle', 'polygon', 'angle', 'area', 'perimeter'])
        if is_geometry:
            return VisualizationDecision(
                should_visualize=True,
                plot_type="geometry",
                reason="Geometry problem benefits from diagram",
                confidence=0.85
            )
        
        # Default: No standard visualization
        return VisualizationDecision(
            should_visualize=False,
            plot_type="other",
            reason="Problem is primarily algebraic without graphable elements",
            confidence=0.7
        )
    
    def generate_plot_plan(
        self,
        plot_type: str,
        entities: Dict[str, Any],
        solution_features: Optional[Dict[str, Any]] = None
    ) -> PlotPlanV3:
        """
        Generate a complete plot plan based on problem type.
        
        Args:
            plot_type: Type of plot to generate
            entities: Detected mathematical entities
            solution_features: Optional solution features (intercepts, vertex, etc.)
        
        Returns:
            PlotPlanV3 object
        """
        if plot_type == "function":
            return self._generate_function_plan(entities, solution_features)
        elif plot_type == "system":
            return self._generate_system_plan(entities, solution_features)
        elif plot_type == "number_line":
            return self._generate_number_line_plan(entities, solution_features)
        elif plot_type == "inequality_region":
            return self._generate_inequality_region_plan(entities, solution_features)
        elif plot_type == "histogram":
            return self._generate_histogram_plan(entities, solution_features)
        else:
            # Default generic plan
            return self._generate_generic_plan(entities)
    
    def _generate_function_plan(
        self,
        entities: Dict[str, Any],
        solution_features: Optional[Dict[str, Any]] = None
    ) -> PlotPlanV3:
        """Generate plan for single function plot."""
        functions = entities.get('functions', [])
        function_expr = functions[0] if functions else "y = x"
        
        # Default window
        window = RecommendedWindowV3(x_min=-10, x_max=10, y_min=-10, y_max=10)
        
        # Adjust window based on features
        if solution_features:
            # TODO: Adjust window based on intercepts, vertex, etc.
            pass
        
        objects = [
            PlotObjectV3(
                kind=ObjectKind.CURVE,
                expression=function_expr,
                label="f(x)"
            )
        ]
        
        annotations = []
        if solution_features:
            # Add intercepts, vertex, etc. as annotations
            if 'vertex' in solution_features:
                vertex = solution_features['vertex']
                annotations.append(AnnotationV3(
                    name="Vertex",
                    detail=f"({vertex.get('x', 0)}, {vertex.get('y', 0)})"
                ))
        
        return PlotPlanV3(
            title=f"Graph of {function_expr}",
            axes=AxesV3(x_label="x", y_label="y"),
            recommended_window=window,
            objects=objects,
            annotations=annotations,
            sampling=SamplingV3(
                strategy=SamplingStrategy.UNIFORM,
                resolution=200
            )
        )
    
    def _generate_system_plan(
        self,
        entities: Dict[str, Any],
        solution_features: Optional[Dict[str, Any]] = None
    ) -> PlotPlanV3:
        """Generate plan for system of equations."""
        equations = entities.get('equations', [])
        
        objects = []
        for i, eq in enumerate(equations[:4]):  # Max 4 equations
            objects.append(PlotObjectV3(
                kind=ObjectKind.CURVE,
                expression=eq,
                label=f"Equation {i+1}"
            ))
        
        return PlotPlanV3(
            title="System of Equations",
            axes=AxesV3(x_label="x", y_label="y"),
            recommended_window=RecommendedWindowV3(x_min=-10, x_max=10, y_min=-10, y_max=10),
            objects=objects,
            annotations=[],
            sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=200)
        )
    
    def _generate_number_line_plan(
        self,
        entities: Dict[str, Any],
        solution_features: Optional[Dict[str, Any]] = None
    ) -> PlotPlanV3:
        """Generate plan for number line (inequalities)."""
        return PlotPlanV3(
            title="Solution on Number Line",
            axes=AxesV3(x_label="x", y_label=""),
            recommended_window=RecommendedWindowV3(x_min=-10, x_max=10, y_min=-1, y_max=1),
            objects=[
                PlotObjectV3(
                    kind=ObjectKind.LINE,
                    expression="number_line",
                    label="Solution region"
                )
            ],
            annotations=[],
            sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=100)
        )
    
    def _generate_inequality_region_plan(
        self,
        entities: Dict[str, Any],
        solution_features: Optional[Dict[str, Any]] = None
    ) -> PlotPlanV3:
        """Generate plan for inequality region."""
        return PlotPlanV3(
            title="Inequality Region",
            axes=AxesV3(x_label="x", y_label="y"),
            recommended_window=RecommendedWindowV3(x_min=-10, x_max=10, y_min=-10, y_max=10),
            objects=[
                PlotObjectV3(
                    kind=ObjectKind.REGION,
                    expression="inequality_region",
                    label="Solution region"
                )
            ],
            annotations=[],
            sampling=SamplingV3(strategy=SamplingStrategy.GRID, resolution=100)
        )
    
    def _generate_histogram_plan(
        self,
        entities: Dict[str, Any],
        solution_features: Optional[Dict[str, Any]] = None
    ) -> PlotPlanV3:
        """Generate plan for histogram (statistics)."""
        return PlotPlanV3(
            title="Data Distribution",
            axes=AxesV3(x_label="Value", y_label="Frequency"),
            recommended_window=RecommendedWindowV3(x_min=0, x_max=100, y_min=0, y_max=10),
            objects=[
                PlotObjectV3(
                    kind=ObjectKind.POINTS,
                    expression="data_points",
                    label="Distribution"
                )
            ],
            annotations=[],
            sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=50)
        )
    
    def _generate_generic_plan(self, entities: Dict[str, Any]) -> PlotPlanV3:
        """Generate generic fallback plan."""
        return PlotPlanV3(
            title="Mathematical Visualization",
            axes=AxesV3(x_label="x", y_label="y"),
            recommended_window=RecommendedWindowV3(x_min=-10, x_max=10, y_min=-10, y_max=10),
            objects=[
                PlotObjectV3(
                    kind=ObjectKind.CURVE,
                    expression="generic",
                    label="Plot"
                )
            ],
            annotations=[],
            sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=200)
        )
    
    def generate_visualization_alternative(
        self,
        problem_text: str,
        reason: str
    ) -> VisualizationAlternativeV3:
        """
        Generate alternative visualization instructions for non-plottable problems.
        
        Args:
            problem_text: The problem text
            reason: Why standard plotting isn't applicable
        
        Returns:
            VisualizationAlternativeV3 object
        """
        # Determine alternative type
        if any(kw in problem_text.lower() for kw in ['number', 'integer', 'real']):
            alt_type = "number_line_concept"
            instructions = [
                "Visualize the solution as a point on a number line",
                "Mark the solution value clearly",
                "Optionally show the path from 0 to the solution"
            ]
        elif "word" in problem_text.lower() or "problem" in problem_text.lower():
            alt_type = "conceptual_diagram"
            instructions = [
                "Create a conceptual diagram showing relationships between quantities",
                "Label all known and unknown values",
                "Show the logical flow from given information to solution"
            ]
        else:
            alt_type = "step_visualization"
            instructions = [
                "Consider visualizing each major step's transformation",
                "Show how the equation changes form at each step",
                "Highlight the isolation of the variable"
            ]
        
        return VisualizationAlternativeV3(
            type=alt_type,
            reason_no_standard_plot=reason,
            instructions=instructions
        )


# Singleton instance
_viz_engine: Optional[VisualizationEngine] = None


def get_visualization_engine() -> VisualizationEngine:
    """Get the global visualization engine instance."""
    global _viz_engine
    if _viz_engine is None:
        _viz_engine = VisualizationEngine()
    return _viz_engine


if __name__ == "__main__":
    # Test the visualization engine
    print("Testing Visualization Engine...")
    
    engine = VisualizationEngine()
    
    test_cases = [
        ("Graph the function y = x^2", {"detected_entities": {"functions": ["y=x^2"], "equations": [], "functions": ["y=x^2"], "constraints": []}}),
        ("Solve 2x + 3 = 7", {"detected_entities": {"expressions": [], "equations": ["2x+3=7"], "functions": [], "constraints": []}}),
        ("Solve the system: y = 2x + 1, y = -x + 4", {"detected_entities": {"expressions": [], "equations": ["y=2x+1", "y=-x+4"], "functions": ["y=2x+1", "y=-x+4"], "constraints": []}}),
        ("Solve x > 5", {"detected_entities": {"expressions": [], "equations": ["x>5"], "functions": [], "constraints": ["x>5"]}}),
    ]
    
    for i, (problem, analysis) in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {problem[:50]}... ---")
        decision = engine.should_visualize(problem, analysis)
        print(f"Should visualize: {decision.should_visualize}")
        print(f"Plot type: {decision.plot_type}")
        print(f"Reason: {decision.reason}")
        print(f"Confidence: {decision.confidence:.2f}")
        
        if decision.should_visualize:
            plan = engine.generate_plot_plan(decision.plot_type, analysis['detected_entities'])
            print(f"✅ Generated plot plan: {plan.title}")
            print(f"   Objects: {len(plan.objects)}")
            print(f"   Window: x[{plan.recommended_window.x_min}, {plan.recommended_window.x_max}]")
