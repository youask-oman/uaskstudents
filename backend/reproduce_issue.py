from app.services.plot_sampling import generate_points, safe_eval_math

test_cases = [
    "y = x^2",
    "y = \\sin(x)",
    "y = \\text{sin}(x)",
    "y = \\operatorname{sin}(x)",
    "f(x) = x + 1"
]

print("--- Testing Plot Sampling ---")
for case in test_cases:
    print(f"\nTesting: {case}")
    try:
        points = generate_points(case, -3, 3, 5)
        if points:
            print(f"Success! {len(points)} points generated.")
            print(f"First point: {points[0]}")
        else:
            print("FAILED: No points generated.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
