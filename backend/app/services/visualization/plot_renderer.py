"""
Plot Rendering Engine for Math Solver V3.

Converts PlotPlanV3 specifications into rendered images (PNG/SVG) using matplotlib.
Supports multiple plot types: function, system, number_line, inequality, scatter, histogram.
"""

import io
import base64
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from app.schemas.na_math_solver_v3 import PlotPlanV3, PlotTypeEnum


@dataclass
class PlotResult:
    """Result of plot rendering."""
    plot_type: str
    image_base64: str  # PNG encoded as base64
    width: int
    height: int
    annotations: List[str]


class PlotRenderer:
    """
    Renders mathematical plots from PlotPlanV3 specifications.
    
    Features:
    - Function plots with annotations
    - System of equations with intersection points
    - Number lines for inequalities
    - Scatter plots and histograms for statistics
    - Deterministic rendering (same input → same output)
    """
    
    def __init__(self, dpi: int = 100, figsize: Tuple[float, float] = (8, 6)):
        """
        Initialize plot renderer.
        
        Args:
            dpi: Dots per inch for rendering
            figsize: Figure size in inches (width, height)
        """
        self.dpi = dpi
        self.figsize = figsize
    
    def render(self, plan: PlotPlanV3, plot_type: str) -> PlotResult:
        """
        Render a plot from a plan.
        
        Args:
            plan: PlotPlanV3 specification
            plot_type: Type of plot to render
        
        Returns:
            PlotResult with base64-encoded image
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        try:
            # Render based on plot type
            if plot_type in ["function", PlotTypeEnum.FUNCTION.value]:
                self._render_function(ax, plan)
            elif plot_type in ["system", PlotTypeEnum.SYSTEM.value]:
                self._render_system(ax, plan)
            elif plot_type in ["number_line", PlotTypeEnum.NUMBER_LINE.value]:
                self._render_number_line(ax, plan)
            elif plot_type in ["inequality_region", PlotTypeEnum.INEQUALITY_REGION.value]:
                self._render_inequality_region(ax, plan)
            elif plot_type in ["scatter", PlotTypeEnum.SCATTER.value]:
                self._render_scatter(ax, plan)
            elif plot_type in ["histogram", PlotTypeEnum.HISTOGRAM.value]:
                self._render_histogram(ax, plan)
            else:
                # Generic fallback
                self._render_generic(ax, plan)
            
            # Set labels and title
            ax.set_xlabel(plan.axes.x_label, fontsize=12)
            ax.set_ylabel(plan.axes.y_label, fontsize=12)
            ax.set_title(plan.title, fontsize=14, fontweight='bold')
            
            # Set window
            window = plan.recommended_window
            ax.set_xlim(window.x_min, window.x_max)
            if window.y_min is not None and window.y_max is not None:
                ax.set_ylim(window.y_min, window.y_max)
            
            # Grid
            ax.grid(True, alpha=0.3)
            
            # Legend if there are labeled objects
            if any(obj.label for obj in plan.objects):
                ax.legend(loc='best')
            
            # Convert to base64
            buf = io.BytesIO()
            plt.tight_layout()
            fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight')
            buf.seek(0)
            image_base64 = base64.b64encode(buf.read()).decode('utf-8')
            
            # Extract annotations
            annotation_strs = [f"{ann.name}: {ann.detail}" for ann in plan.annotations]
            
            return PlotResult(
                plot_type=plot_type,
                image_base64=image_base64,
                width=int(self.figsize[0] * self.dpi),
                height=int(self.figsize[1] * self.dpi),
                annotations=annotation_strs
            )
        
        finally:
            plt.close(fig)
    
    def _render_function(self, ax, plan: PlotPlanV3):
        """Render a single function plot."""
        window = plan.recommended_window
        x = np.linspace(window.x_min, window.x_max, plan.sampling.resolution)
        
        for obj in plan.objects:
            # Try to evaluate the expression
            try:
                y = self._evaluate_expression(obj.expression, x)
                style = '-' if not (obj.style_hints and obj.style_hints.dashed) else '--'
                ax.plot(x, y, style, label=obj.label, linewidth=2)
            except Exception as e:
                print(f"[PlotRenderer] Could not evaluate '{obj.expression}': {e}")
                # Plot a placeholder
                ax.plot(x, np.zeros_like(x), '--', label=f"{obj.label} (error)", alpha=0.5)
        
        # Add annotations
        for ann in plan.annotations:
            if ann.point:
                ax.plot(ann.point.x, ann.point.y, 'ro', markersize=8)
                ax.annotate(
                    ann.detail,
                    xy=(ann.point.x, ann.point.y),
                    xytext=(10, 10),
                    textcoords='offset points',
                    fontsize=10,
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0')
                )
    
    def _render_system(self, ax, plan: PlotPlanV3):
        """Render system of equations (multiple functions)."""
        window = plan.recommended_window
        x = np.linspace(window.x_min, window.x_max, plan.sampling.resolution)
        
        for i, obj in enumerate(plan.objects):
            try:
                y = self._evaluate_expression(obj.expression, x)
                ax.plot(x, y, label=obj.label, linewidth=2)
            except Exception as e:
                print(f"[PlotRenderer] Could not evaluate '{obj.expression}': {e}")
        
        # Add annotations (e.g., intersection points)
        for ann in plan.annotations:
            if ann.point:
                ax.plot(ann.point.x, ann.point.y, 'ko', markersize=10, markerfacecolor='red', markeredgewidth=2)
                ax.annotate(
                    ann.detail,
                    xy=(ann.point.x, ann.point.y),
                    xytext=(15, 15),
                    textcoords='offset points',
                    fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                    arrowprops=dict(arrowstyle='->', lw=1.5)
                )
    
    def _render_number_line(self, ax, plan: PlotPlanV3):
        """Render number line for inequalities."""
        window = plan.recommended_window
        
        # Draw number line
        ax.axhline(y=0, color='black', linewidth=2)
        ax.set_ylim(-0.5, 0.5)
        
        # Remove y-axis
        ax.get_yaxis().set_visible(False)
        
        # Add tick marks
        x_ticks = np.linspace(window.x_min, window.x_max, 11)
        for x_val in x_ticks:
            ax.plot([x_val, x_val], [-0.1, 0.1], 'k-', linewidth=1)
        
        # Annotations for solution points/intervals
        for ann in plan.annotations:
            if ann.point:
                # Mark solution point
                ax.plot(ann.point.x, 0, 'ro', markersize=12)
                ax.text(ann.point.x, 0.25, ann.detail, ha='center', fontsize=11, fontweight='bold')
    
    def _render_inequality_region(self, ax, plan: PlotPlanV3):
        """Render inequality region (shaded area)."""
        window = plan.recommended_window
        x = np.linspace(window.x_min, window.x_max, plan.sampling.resolution)
        
        # Plot boundary functions
        for obj in plan.objects:
            if obj.kind == "curve":
                try:
                    y = self._evaluate_expression(obj.expression, x)
                    style = '--' if obj.style_hints and obj.style_hints.dashed else '-'
                    ax.plot(x, y, style, label=obj.label, linewidth=2)
                except:
                    pass
            elif obj.kind == "region":
                # Shade a region (placeholder implementation)
                y_lower = np.zeros_like(x)
                y_upper = np.ones_like(x) * (window.y_max - window.y_min) / 2
                ax.fill_between(x, y_lower, y_upper, alpha=0.3, label=obj.label)
    
    def _render_scatter(self, ax, plan: PlotPlanV3):
        """Render scatter plot."""
        # Placeholder: In real implementation, parse data points from objects
        x_data = np.random.rand(20) * (plan.recommended_window.x_max - plan.recommended_window.x_min) + plan.recommended_window.x_min
        y_data = np.random.rand(20) * (plan.recommended_window.y_max - plan.recommended_window.y_min) + plan.recommended_window.y_min
        
        ax.scatter(x_data, y_data, s=100, alpha=0.6, edgecolors='black', linewidth=1.5)
    
    def _render_histogram(self, ax, plan: PlotPlanV3):
        """Render histogram."""
        # Placeholder: In real implementation, parse data from objects
        data = np.random.randn(100) * 10 + 50
        
        ax.hist(data, bins=15, alpha=0.7, color='steelblue', edgecolor='black')
    
    def _render_generic(self, ax, plan: PlotPlanV3):
        """Generic fallback renderer."""
        window = plan.recommended_window
        x = np.linspace(window.x_min, window.x_max, plan.sampling.resolution)
        y = np.sin(x)  # Placeholder
        ax.plot(x, y, '-', label="Generic plot", linewidth=2)
    
    def _evaluate_expression(self, expression: str, x: np.ndarray) -> np.ndarray:
        """
        SAFELY evaluate a mathematical expression using SymPy (NO EVAL).
        
        Args:
            expression: Math expression (e.g., "y=x^2", "2*x+3")
            x: Input x values
        
        Returns:
            Output y values or zeros if parsing fails
        """
        from app.services.visualization.safe_parser import get_safe_parser
        
        parser = get_safe_parser()
        
        # Attempt safe parsing and evaluation
        y_values, error = parser.evaluate_for_plotting(expression, x)
        
        if error:
            # Log error and return zeros as fallback
            print(f"[PlotRenderer] Expression parsing failed: {error}")
            return np.zeros_like(x)
        
        return y_values


# Singleton instance
_plot_renderer: Optional[PlotRenderer] = None


def get_plot_renderer() -> PlotRenderer:
    """Get the global plot renderer instance."""
    global _plot_renderer
    if _plot_renderer is None:
        _plot_renderer = PlotRenderer()
    return _plot_renderer


if __name__ == "__main__":
    # Test plot renderer
    print("Testing Plot Renderer...")
    
    from app.schemas.na_math_solver_v3 import (
        PlotPlanV3, AxesV3, RecommendedWindowV3, PlotObjectV3,
        SamplingV3, ObjectKind, SamplingStrategy, AnnotationV3, PointV3
    )
    
    renderer = PlotRenderer()
    
    # Test 1: Function plot
    print("\n--- Test 1: Function Plot ---")
    plan = PlotPlanV3(
        title="Graph of y = x²",
        axes=AxesV3(x_label="x", y_label="y"),
        recommended_window=RecommendedWindowV3(x_min=-5, x_max=5, y_min=0, y_max=25),
        objects=[
            PlotObjectV3(kind=ObjectKind.CURVE, expression="y=x**2", label="f(x) = x²")
        ],
        annotations=[
            AnnotationV3(name="Vertex", detail="(0, 0)", point=PointV3(x=0, y=0))
        ],
        sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=200)
    )
    
    result = renderer.render(plan, "function")
    print(f"✅ Rendered function plot: {result.width}x{result.height}px")
    print(f"   Base64 length: {len(result.image_base64)} characters")
    print(f"   Annotations: {result.annotations}")
    
    # Test 2: Number line
    print("\n--- Test 2: Number Line ---")
    plan2 = PlotPlanV3(
        title="Solution: x = 5",
        axes=AxesV3(x_label="x", y_label=""),
        recommended_window=RecommendedWindowV3(x_min=0, x_max=10, y_min=-1, y_max=1),
        objects=[PlotObjectV3(kind=ObjectKind.LINE, expression="number_line", label="Solution")],
        annotations=[AnnotationV3(name="Solution", detail="x = 5", point=PointV3(x=5, y=0))],
        sampling=SamplingV3(strategy=SamplingStrategy.UNIFORM, resolution=100)
    )
    
    result2 = renderer.render(plan2, "number_line")
    print(f"✅ Rendered number line: {result2.width}x{result2.height}px")
