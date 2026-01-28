import sys
import os
import math

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.services.plot_sampling import process_visuals

def test_graphing_logic():
    print("--- Testing 2D Function: tan(x) (Discontinuity Check) ---")
    visuals = [{
        "type": "graph",
        "function": {"latex": "tan(x)"}
    }]
    processed = process_visuals(visuals)
    spec = processed[0]
    print(f"Graph Type: {spec['graph_type']}")
    print(f"Segments: {len(spec['traces'])}")
    # tan(x) should have multiple segments due to asymptotes
    assert len(spec['traces']) > 1
    print("SUCCESS: tan(x) handled with multiple segments.")

    print("\n--- Testing Roots: cbrt(-x) ---")
    visuals = [{
        "type": "graph",
        "function": {"latex": "root(3, -x)"}
    }]
    processed = process_visuals(visuals)
    spec = processed[0]
    # Check a point where x=8 -> root(3, -8) = -2
    trace = spec['traces'][0]
    # Find x near -8
    found_negative_root = False
    for x, y in zip(trace['x'], trace['y']):
        if x is not None and abs(x - 8) < 0.1:
            print(f"f(8) = {y}")
            if y is not None and abs(y + 2) < 0.1:
                found_negative_root = True
                break
    assert found_negative_root
    print("SUCCESS: cbrt(-8) correctly evaluated to -2.")

    print("\n--- Testing 3D Surface: x^2 + y^2 ---")
    visuals = [{
        "type": "graph",
        "function": {"latex": "z = x^2 + y^2"}
    }]
    processed = process_visuals(visuals)
    spec = processed[0]
    print(f"Graph Type: {spec['graph_type']}")
    assert spec['graph_type'] == "3d_surface"
    assert spec['traces'][0]['kind'] == "surface"
    assert "z_matrix" in spec['traces'][0]
    print("SUCCESS: 3D surface correctly identified and sampled.")

if __name__ == "__main__":
    try:
        test_graphing_logic()
        print("\nALL BACKEND GRAPHING TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
