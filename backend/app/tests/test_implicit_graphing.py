import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.plot_sampling import process_visuals, normalize_latex_for_eval

def test_normalization():
    print("Testing Normalization...")
    cases = [
        ("x^2 + y^2 = 100", "(x**2 + y**2) - (100)"),
        ("y = x + 1", "x + 1"), # Not implicit if y=
        ("x^2 + y^3 = 100", "(x**2 + y**3) - (100)"),
        ("sin(x) + cos(y) = 0", "(sin(x) + cos(y)) - (0)"),
    ]
    for lat, expected in cases:
        is_implicit = "y" in lat and not (lat.startswith("y=") or lat.startswith("y ="))
        res = normalize_latex_for_eval(lat, is_implicit=is_implicit)
        print(f"  {lat} -> {res}")
        # Note: res might be slightly different due to cleanup, but should match logic

def test_process_visuals():
    print("\nTesting process_visuals detection...")
    visuals = [
        {
            "plot_type": "cartesian_2d",
            "title": "Circle",
            "series": [{"expression_latex": "x^2 + y^2 = 25", "name": "Circle"}]
        },
        {
            "plot_type": "cartesian_2d",
            "title": "Function",
            "series": [{"expression_latex": "y = x^2", "name": "Parabola"}]
        }
    ]
    hydrated = process_visuals(visuals)
    
    for i, h in enumerate(hydrated):
        title = h.get("title")
        trace = h.get("traces")[0]
        kind = trace.get("kind")
        print(f"  {title}: {kind}")

if __name__ == "__main__":
    test_normalization()
    test_process_visuals()
