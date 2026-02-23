import requests

question = """Solve for x on 0 <= x < 2*pi:
2 sin^2(x) - 3 sin(x) + 1 = 0.

Tasks:
1) Rewrite as a quadratic in sin(x), solve for sin(x), and keep only valid sine values in [-1, 1].
2) Find all solutions x in [0, 2*pi) in exact form (standard angles).
3) Verify each solution by substitution into the original equation.
4) Draw a plot on x in [0, 2*pi] with:
   - y = 2 sin^2(x) - 3 sin(x) + 1
   - the x-axis (y=0)
   - marked solution points (roots) on the curve
   - title, axis labels, grid, and a legend"""

body = {
  "question_id": 1,
  "question_text": question,
  "tier": "SHORT_STEPS",
  "mode": "SOLVE",
  "graph_mode": "on",
  "trusted_context": {
    "domain_mode": "reals",
    "preferred_response_language": "English",
    "capture_openai_raw_only": True
  }
}

url = "http://127.0.0.1:8000/api/v1/solve_v3?user_id=9"
resp = requests.post(url, json=body, timeout=300)
print(resp.status_code)
print(resp.text)
