import math
import re
from typing import List, Optional, Dict, Any, Tuple
from ..schemas.graph_spec import GraphSpec, GraphType, GraphTrace, TraceKind, KeyPoint, GraphAxes

# --- Core Math Helpers ---

def cbrt(x: float) -> float:
    """Real-valued cube root that handles negative numbers."""
    if x >= 0:
        return x ** (1/3)
    else:
        return -(abs(x) ** (1/3))

def root(n: float, x: float) -> float | None:
    """Real-valued nth root for general cases."""
    if n == 0: return None
    if x == 0: return 0.0
    
    # If n is even, x must be non-negative for real result
    if abs(n % 2) < 1e-9: # Even-ish
        if x < 0: return None
        return x ** (1/n)
    
    # If n is odd, handle negative x
    if abs(n % 2 - 1) < 1e-9: # Odd-ish
        if x >= 0:
            return x ** (1/n)
        else:
            return -(abs(x) ** (1/n))
            
    # Fractional or other n
    if x < 0: return None
    return x ** (1/n)

def safe_eval_math(expression: str, locals_dict: Dict[str, Any]) -> float | None:
    """Evaluates a normalized expression within a restricted scope."""
    try:
        # Restriction: __builtins__ is empty, only allowed math functions
        res = eval(expression, {"__builtins__": {}}, locals_dict)
        return res
    except Exception:
        return None

def normalize_latex_for_eval(latex: str, is_implicit: bool = False) -> str:
    """Converts LaTeX math to Python-evaluatable string."""
    expr = latex.strip()
    
    # 1. Root variations -> safe functions
    expr = re.sub(r'\\root\s*\{?([^}\s]+)\}?\s*\\of\s*\{([^}]+)\}', r'root(\1, \2)', expr)
    expr = re.sub(r'\\root\s*\{([^}]+)\}\s*\{([^}]+)\}', r'root(\1, \2)', expr)
    expr = re.sub(r'\\root\s+([0-9a-z]+)\s+\{([^}]+)\}', r'root(\1, \2)', expr)
    expr = re.sub(r'\\sqrt\s*\[([^\]]+)\]\s*\{([^}]+)\}', r'root(\1, \2)', expr)
    expr = re.sub(r'\\sqrt\s*\{([^}]+)\}', r'root(2, \1)', expr)
    
    # 2. Basic replacements
    expr = expr.replace("\u03c0", "pi").replace("\uf070", "pi").replace("\u1d70a", "pi")
    
    # 3. Handle common LaTeX math commands
    expr = re.sub(r'\\(sin|cos|tan|asin|acos|atan|sqrt|log|exp|abs|pi|e)\b', r'\1', expr)
    
    # 4. Standard cleanups
    expr = re.sub(r'\\?(text|mathrm|operatorname|mathtxt)\s*\{([^}]+)\}', r'\2', expr)
    expr = expr.replace("\\", "") # Clean up remaining slashes
    
    if "=" in expr:
        if is_implicit:
            # Rewrite f(x,y) = g(x,y) as (f(x,y)) - (g(x,y))
            lhs, rhs = expr.split("=", 1)
            expr = f"({lhs.strip()}) - ({rhs.strip()})"
        else:
            expr = expr.split("=")[-1]
        
    expr = expr.replace("^", "**")
    
    # Implicit multiplication (2x -> 2*x)
    expr = re.sub(r'(\d)([a-z\(])', r'\1*\2', expr)
    
    return expr.strip()

def get_math_scope(vars_dict: Dict[str, float]) -> Dict[str, Any]:
    """Returns the scope with allowed math functions."""
    scope = {
        "pi": math.pi,
        "e": math.e,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "sqrt": math.sqrt,
        "abs": abs,
        "pow": pow,
        "log": math.log,
        "exp": math.exp,
        "root": root,
        "cbrt": cbrt,
    }
    scope.update(vars_dict)
    return scope

# --- Sampling Engine ---

def is_valid(y: Any) -> bool:
    """Checks if a value is a finite real number."""
    return isinstance(y, (int, float)) and not math.isnan(y) and not math.isinf(y)

def sample_2d_function(
    expr: str, 
    x_min: float, 
    x_max: float
) -> Tuple[List[List[float]], List[List[float]], List[str]]:
    """
    Performs adaptive sampling for a 2D function.
    Returns: list of x_segments, list of y_segments, list of warnings
    """
    x_segments = []
    y_segments = []
    current_x_seg = []
    current_y_seg = []
    warnings = []
    
    py_expr = normalize_latex_for_eval(expr)
    
    def eval_at(x_val):
        return safe_eval_math(py_expr, get_math_scope({"x": x_val}))

    # Uniform base grid
    base_n = 400
    xs = [x_min + i * (x_max - x_min) / base_n for i in range(base_n + 1)]
    
    # Simple discontinuity-aware collection
    for x in xs:
        y = eval_at(x)
        if is_valid(y):
            # Asymptote/Jump detection
            if current_y_seg:
                dy = abs(y - current_y_seg[-1])
                # Sensitive jump detection for splitting tan(x) etc.
                if dy > 15:
                    if current_x_seg:
                        x_segments.append(current_x_seg)
                        y_segments.append(current_y_seg)
                    current_x_seg = [x]
                    current_y_seg = [y]
                    continue
                    
            current_x_seg.append(x)
            current_y_seg.append(y)
        else:
            if current_x_seg:
                x_segments.append(current_x_seg)
                y_segments.append(current_y_seg)
            current_x_seg = []
            current_y_seg = []
            
    if current_x_seg:
        x_segments.append(current_x_seg)
        y_segments.append(current_y_seg)
        
    return x_segments, y_segments, warnings

def sample_2d_implicit(
    expr: str,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float]
) -> Tuple[List[float], List[float], List[List[Optional[float]]]]:
    """Generates a grid of points for a 2D implicit plot (contour)."""
    # Force implicit normalization (keeps '=' as subtraction)
    py_expr = normalize_latex_for_eval(expr, is_implicit=True)
    n = 100 # Improved resolution for contours
    
    xs = [x_range[0] + i * (x_range[1] - x_range[0]) / n for i in range(n + 1)]
    ys = [y_range[0] + i * (y_range[1] - y_range[0]) / n for i in range(n + 1)]
    z_matrix = []
    
    for y_val in ys:
        row = []
        for x_val in xs:
            scope = get_math_scope({"x": x_val, "y": y_val})
            z = safe_eval_math(py_expr, scope)
            if is_valid(z):
                row.append(round(float(z), 6))
            else:
                row.append(None)
        z_matrix.append(row)
        
    return xs, ys, z_matrix

def sample_3d_surface(
    expr: str,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float]
) -> Tuple[List[float], List[float], List[List[Optional[float]]]]:
    """Generates a grid of points for a 3D surface."""
    py_expr = normalize_latex_for_eval(expr)
    n = 60 # Grid resolution
    
    xs = [x_range[0] + i * (x_range[1] - x_range[0]) / n for i in range(n + 1)]
    ys = [y_range[0] + i * (y_range[1] - y_range[0]) / n for i in range(n + 1)]
    z_matrix = []
    
    for y_val in ys:
        row = []
        for x_val in xs:
            scope = get_math_scope({"x": x_val, "y": y_val})
            z = safe_eval_math(py_expr, scope)
            if is_valid(z):
                row.append(round(float(z), 4))
            else:
                row.append(None)
        z_matrix.append(row)
        
    return xs, ys, z_matrix

def extract_key_points_2d(expr: str, x_min: float, x_max: float) -> List[KeyPoint]:
    """Basic extraction of intercepts."""
    py_expr = normalize_latex_for_eval(expr)
    def eval_at(x_val):
        return safe_eval_math(py_expr, get_math_scope({"x": x_val}))
    
    keys = []
    # Y-intercept
    if x_min <= 0 <= x_max:
        y0 = eval_at(0)
        if is_valid(y0):
            keys.append(KeyPoint(label="y-intercept", x=0, y=round(float(y0), 3)))
    
    # Rough x-intercept search
    n = 100
    for i in range(n):
        xa = x_min + i * (x_max - x_min) / n
        xb = x_min + (i+1) * (x_max - x_min) / n
        ya, yb = eval_at(xa), eval_at(xb)
        if is_valid(ya) and is_valid(yb) and ya * yb <= 0:
            keys.append(KeyPoint(label="x-intercept", x=round((xa+xb)/2, 3), y=0))
            
    return keys

# --- Main Entry Point ---

def process_visuals(visuals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hydrates visuals using the new GraphSpec format, mapping from PlotSpecV3."""
    processed = []
    
    for v in visuals:
        try:
            # v follows PlotSpecV3 from na_math_solver_v3.py
            plot_type = v.get("plot_type", "cartesian_2d")
            title = v.get("title") or "Graph"
            
            # 1. Initialize GraphSpec
            graph_type = GraphType.TWO_D_FUNCTION
            if plot_type == "cartesian_3d":
                graph_type = GraphType.THREE_D_SURFACE
            
            x_min = float(v.get("x_min", -10.0))
            x_max = float(v.get("x_max", 10.0))
            y_min = float(v.get("y_min", -10.0))
            y_max = float(v.get("y_max", 10.0))
            
            axes = GraphAxes(
                x_label=v.get("x_label", "x"),
                y_label=v.get("y_label", "y"),
                z_label="z" if graph_type == GraphType.THREE_D_SURFACE else None,
                x_range=[x_min, x_max],
                y_range=[y_min, y_max]
            )
            
            spec = GraphSpec(
                graph_type=graph_type,
                title=title,
                axes=axes
            )
            
            # 2. Process Series
            raw_series = v.get("series") or []
            if not raw_series and v.get("function"):
                # Handle legacy/simple "function" key
                raw_series = [{"expression_latex": v["function"].get("latex"), "name": title}]

            for s in raw_series:
                expr = s.get("expression_latex") or s.get("label") or s.get("name")
                if not expr: continue
                
                # Check for 3D if not already set (fallback detection)
                if "z" in expr.lower() or "z=" in expr.lower():
                    spec.graph_type = GraphType.THREE_D_SURFACE
                    spec.axes.z_label = "z"
                
                if spec.graph_type == GraphType.THREE_D_SURFACE:
                    xs, ys, zm = sample_3d_surface(expr, (x_min, x_max), (y_min, y_max))
                    spec.traces.append(GraphTrace(
                        name=s.get("name") or expr,
                        kind=TraceKind.SURFACE,
                        x=xs,
                        y=ys,
                        z_matrix=zm
                    ))
                else:
                    # 2D case: Check if implicit (contains y or an equals sign that isn't y=...)
                    is_implicit = False
                    if "y" in expr.lower():
                        # If it has 'y' but isn't a simple 'y = ...' or 'f(x) = ...'
                        # Actually, any equation with 'y' that isn't just the output variable is implicit.
                        normalized_lower = expr.lower().replace(" ", "")
                        if "=" in normalized_lower:
                            lhs = normalized_lower.split("=")[0]
                            if lhs != "y" and lhs != "f(x)":
                                is_implicit = True
                        else:
                            is_implicit = True # No equals but has y? e.g. x^2 + y^2
                            
                    if is_implicit:
                        xs, ys, zm = sample_2d_implicit(expr, (x_min, x_max), (y_min, y_max))
                        spec.traces.append(GraphTrace(
                            name=s.get("name") or expr,
                            kind=TraceKind.CONTOUR,
                            x=xs,
                            y=ys,
                            z_matrix=zm
                        ))
                    else:
                        x_segs, y_segs, warnings = sample_2d_function(expr, x_min, x_max)
                        spec.warnings.extend(warnings)
                        for i, (xs, ys) in enumerate(zip(x_segs, y_segs)):
                            spec.traces.append(GraphTrace(
                                name=s.get("name") or expr,
                                kind=TraceKind.SCATTER,
                                x=xs,
                                y=ys,
                                show_legend=(i == 0)
                            ))
            
            # 3. Map Key Points provided by LLM
            llm_points = v.get("key_points") or []
            for kp in llm_points:
                try:
                    spec.key_points.append(KeyPoint(
                        label=kp.get("label", "Point"),
                        x=float(kp.get("x", 0.0)),
                        y=float(kp.get("y", 0.0)),
                        z=float(kp.get("z", 0.0)) if kp.get("z") is not None else None
                    ))
                except: pass
            
            # 4. Auto-extract key points if 2D
            if spec.graph_type == GraphType.TWO_D_FUNCTION and raw_series:
                primary_expr = raw_series[0].get("expression_latex") or raw_series[0].get("label")
                if primary_expr:
                    auto_keys = extract_key_points_2d(primary_expr, x_min, x_max)
                    # Merge (avoid duplicates if close)
                    for ak in auto_keys:
                        if not any(abs(ak.x - lk.x) < 0.1 and abs(ak.y - lk.y) < 0.1 for lk in spec.key_points):
                            spec.key_points.append(ak)
            
            processed.append(spec.dict())
            
        except Exception as e:
            v["warnings"] = [f"Graphing hydration error: {str(e)}"]
            processed.append(v)
            
    return processed
