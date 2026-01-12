import math

def safe_eval_math(expression: str, x: float) -> float | None:
    """
    Safely evaluates simple mathematical expressions for a given x.
    Supports: sin, cos, tan, sqrt, pi, e, +, -, *, /, ^
    """
    try:
        # 1. Basic normalization & Character fixed
        expr = expression.strip()
        # Handle U+F070 and other weird pi representations
        expr = expr.replace("\u03c0", "pi") # Greek pi
        expr = expr.replace("\uf070", "pi") # Private use pi
        expr = expr.replace("\u1d70a", "pi") 
        
        expr = expr.lower()
        
        # 2. Cleanup LaTeX function wrappers (\text{sin} -> sin)
        import re
        # Handle cases where \t might be interpreted as tab if not raw
        expr = expr.replace("\t", " t") 
        
        # Remove text{...}, mathrm{...}, operatorname{...} but keep content
        expr = re.sub(r'\\?(text|mathrm|operatorname|mathtxt)\s*\{([^}]+)\}', r'\2', expr)
        # Remove remaining backslashes for standard functions (latex \sin -> sin)
        expr = expr.replace("\\", "")
        # Remove spaces
        expr = expr.replace(" ", "")
        
        # 3. Strip LHS (y=, f(x)=, etc)
        if "=" in expr:
            expr = expr.split("=")[-1]
            
        # 4. Replace constants
        expr = expr.replace("pi", str(math.pi))
        expr = expr.replace("e", str(math.e))
        
        # 5. Handle operators
        expr = expr.replace("^", "**")
        
        # 6. Handle implicit multiplication (2x -> 2*x)
        # Ensure x is not inside an identifier (though x is our only one)
        expr = re.sub(r'(\d)([a-z\(])', r'\1*\2', expr)
        
        # 7. Prepare local scope - restrict to math functions
        allowed_names = {
            "x": x,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "sqrt": math.sqrt,
            "abs": abs,
            "pow": pow,
            "log": math.log,
            "exp": math.exp
        }
        
        # 5. Clean expression mapping
        # Map latex 'y=' to empty
        if "=" in expr:
            expr = expr.split("=")[-1]
            
        # Remove backslashes for standard functions (latex \sin -> sin)
        expr = expr.replace("\\", "")
        
        # 6. Evaluate
        # WARNING: eval is generally unsafe. In production, use AST parsing or libraries like 'simpleeval'.
        # Here we rely on the restricted scope somewhat, but it's not sandbox-proof.
        return eval(expr, {"__builtins__": {}}, allowed_names)
        
    except Exception:
        return None

def generate_points(
    expression: str, 
    x_min: float = -10.0, 
    x_max: float = 10.0, 
    num_points: int = 400
) -> list[dict]:
    """
    Generates a list of {x, y} points for a given expression.
    """
    points = []
    
    if x_max <= x_min:
        x_max = x_min + 10.0
        
    step = (x_max - x_min) / num_points
    
    x = x_min
    for _ in range(num_points + 1):
        y = safe_eval_math(expression, x)
        
        # Filter undefined or infinite values (e.g. tan(pi/2))
        if y is not None and not math.isnan(y) and not math.isinf(y):
            # Clamp extremely large values for rendering sanity
            if abs(y) < 1e6:
                points.append({"x": x, "y": y})
        
        x += step
        
    return points

def parse_domain(domain_str: str | None) -> float | None:
    """Parses domain strings like '-2\\pi' into floats."""
    if not domain_str:
        return None
    
    s = domain_str.lower().replace("\\pi", str(math.pi)).replace("pi", str(math.pi))
    try:
        return float(eval(s, {"__builtins__": {}}))
    except:
        return None

def process_visuals(visuals: list[dict]) -> list[dict]:
    """
    Hydrates visual requests or incomplete visuals with actual plot data.
    
    Supports:
    - function_plot_request/function_plot: Single function plots
    - line_plot: Line through two points
    - multi_plot_request: Multiple functions (for systems)
    - number_line: For inequalities (V2)
    """
    processed = []
    
    for v in visuals:
        v_type = v.get("type")
        has_series = bool(v.get("series") and len(v.get("series", [{}])[0].get("points", [])) > 0)
        
        # 1. If it already has data, pass through
        if has_series:
            processed.append(v)
            continue
            
        # 2. Handle function_plot_request/function_plot
        func_data = v.get("function") or {}
        latex = func_data.get("latex")
        
        if (v_type in ["function_plot_request", "function_plot", "graph"]) and latex:
            domain = v.get("domain", {})
            x_min = parse_domain(str(domain.get("x_min_latex") or "")) or -10.0
            x_max = parse_domain(str(domain.get("x_max_latex") or "")) or 10.0
            
            # Generate Points
            pts = generate_points(latex, x_min, x_max)
            
            if pts:
                new_visual = {
                    "id": v.get("id"),
                    "type": "function_plot",
                    "title": v.get("title"),
                    "axes": v.get("axes") or {"x_label": "x", "y_label": "y"},
                    "series": [
                        {
                            "label": latex,
                            "points": pts
                        }
                    ],
                    "markers": v.get("markers") or []
                }
                processed.append(new_visual)
                continue
            else:
                print(f"DEBUG: Failed to generate points for latex: {latex}")

        # 3. Handle multi_plot_request (V2) - Systems of equations
        if v_type == "multi_plot_request" and not has_series:
            functions = v.get("functions", [])
            domain = v.get("domain_multi", {})
            x_min = parse_domain(str(domain.get("x_min_latex") or "")) or -10.0
            x_max = parse_domain(str(domain.get("x_max_latex") or "")) or 10.0
            
            series_list = []
            for func in functions:
                latex_expr = func.get("latex")
                label = func.get("label", latex_expr)
                if latex_expr:
                    pts = generate_points(latex_expr, x_min, x_max)
                    if pts:
                        series_list.append({
                            "label": label,
                            "points": pts
                        })
            
            if series_list:
                new_visual = {
                    "id": v.get("id"),
                    "type": "function_plot",  # Convert to function_plot with multiple series
                    "title": v.get("title", "System of Equations"),
                    "axes": {"x_label": "x", "y_label": "y"},
                    "series": series_list,
                    "markers": v.get("markers", [])
                }
                processed.append(new_visual)
                continue

        # 4. Handle line_plot without series
        if v_type == "line_plot" and not has_series:
            # V2: Check for points array
            points_array = v.get("points", [])
            if len(points_array) >= 2:
                try:
                    p1 = {"x": float(points_array[0].get("x", 0)), "y": float(points_array[0].get("y", 0))}
                    p2 = {"x": float(points_array[1].get("x", 0)), "y": float(points_array[1].get("y", 0))}
                    
                    dx = p2["x"] - p1["x"]
                    x_min = min(p1["x"], p2["x"]) - 5
                    x_max = max(p1["x"], p2["x"]) + 5
                    
                    if abs(dx) < 1e-9:  # Vertical
                        line_pts = [
                            {"x": p1["x"], "y": min(p1["y"], p2["y"]) - 5},
                            {"x": p1["x"], "y": max(p1["y"], p2["y"]) + 5}
                        ]
                    else:
                        slope = (p2["y"] - p1["y"]) / dx
                        y_start = p1["y"] + slope * (x_min - p1["x"])
                        y_end = p1["y"] + slope * (x_max - p1["x"])
                        line_pts = [{"x": x_min, "y": y_start}, {"x": x_max, "y": y_end}]
                    
                    v["series"] = [{"label": "Line", "points": line_pts}]
                    v["type"] = "line_plot"
                    v["markers"] = [p1, p2]  # Keep original points as markers
                    processed.append(v)
                    continue
                except Exception as e:
                    print(f"DEBUG: Line plot (points array) generation failed: {e}")
            
            # Fallback: try markers array (old format)
            markers = v.get("markers", [])
            if len(markers) >= 2:
                try:
                    p1, p2 = markers[0], markers[1]
                    dx = p2["x"] - p1["x"]
                    
                    x_min = min(p1["x"], p2["x"]) - 5
                    x_max = max(p1["x"], p2["x"]) + 5
                    
                    if abs(dx) < 1e-9:  # Vertical
                        line_pts = [
                            {"x": p1["x"], "y": min(p1["y"], p2["y"]) - 5},
                            {"x": p1["x"], "y": max(p1["y"], p2["y"]) + 5}
                        ]
                    else:
                        slope = (p2["y"] - p1["y"]) / dx
                        y_start = p1["y"] + slope * (x_min - p1["x"])
                        y_end = p1["y"] + slope * (x_max - p1["x"])
                        line_pts = [{"x": x_min, "y": y_start}, {"x": x_max, "y": y_end}]
                    
                    v["series"] = [{"label": "Line", "points": line_pts}]
                    v["type"] = "line_plot"
                    processed.append(v)
                    continue
                except Exception as e:
                    print(f"DEBUG: Line plot generation failed: {e}")

        # 5. Handle number_line (V2) - For inequalities
        if v_type == "number_line":
            # Number line doesn't need point generation - pass through as-is
            # Frontend will render based on intervals
            processed.append(v)
            continue

        # Fallback: keep as is if we can't do anything better
        processed.append(v)
            
    return processed
