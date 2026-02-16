import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm.clients import OpenAIClient

QUESTION = """Problem: Multivariable Calculus + Lagrange Multipliers + Geometry

Let S be the surface defined by x^2 + y^2 + z^2 = 9 with the constraint plane x + 2y + 2z = 3.

You must do ALL of the following (12 requirements):

Describe geometrically the intersection curve C = S n {x + 2y + 2z = 3}.
Set up the constrained optimization problem to find the maximum and minimum of f(x,y,z) = x - y + 2z on C.
Use Lagrange multipliers with two constraints to compute all critical points.
Solve the resulting system exactly and list all candidate points.
Compute the value of f at each candidate point.
Identify the global maximum and global minimum and justify why they are global.
Find the distance from the origin to the plane and relate it to the circle radius of intersection.
Parametrize the curve C explicitly using an orthonormal basis in the plane.
Verify your extrema by substituting the parametrization into f and doing a single-variable maximization.
State the geometric meaning of the gradient alignment conditions.
Report the final max/min values and the points where they occur.
Provide a brief check that your points lie on both constraints."""

captured = {"openai_generate_calls": []}
_original_generate = OpenAIClient.generate

async def _capturing_generate(self, **kwargs):
    call = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "max_tokens": kwargs.get("max_tokens"),
        "model_param": kwargs.get("model"),
        "timeout_ms": kwargs.get("timeout_ms"),
    }
    try:
        resp = await _original_generate(self, **kwargs)
        call["response"] = {
            "status": resp.status,
            "usage": resp.usage,
            "payload": resp.payload,
        }
        captured["openai_generate_calls"].append(call)
        return resp
    except Exception as e:
        call["exception"] = {"type": type(e).__name__, "message": str(e), "details": getattr(e, "details", None)}
        captured["openai_generate_calls"].append(call)
        raise

OpenAIClient.generate = _capturing_generate

report = {
  "timestamp_utc": datetime.now(timezone.utc).isoformat(),
  "endpoint": "/api/v1/solve_v3_stream",
  "query": {"user_id": "1"},
  "request_body": {
    "confirmed_text": QUESTION,
    "requested_mode": "minimal",
    "tier": "FINAL",
    "graph_mode": "off",
    "trusted_context": {"learning_mode": "solve"},
    "features_used": {"ocr_used": False, "voice_used": False, "plot_requested": False}
  }
}

try:
    client = TestClient(app)
    with client.stream("POST", "/api/v1/solve_v3_stream?user_id=1", json=report["request_body"]) as response:
        report["http_status"] = response.status_code
        sse = ""
        for txt in response.iter_text():
            sse += txt
        report["raw_sse"] = sse
finally:
    OpenAIClient.generate = _original_generate

# parse done
for block in report.get("raw_sse", "").split("\n\n"):
    if block.startswith("event: done"):
        for ln in block.splitlines():
            if ln.startswith("data:"):
                try:
                    report["done_event"] = json.loads(ln.split(":", 1)[1].strip())
                except Exception:
                    report["done_event"] = ln

report["captured"] = captured
out = "backend/tmp_real_api_openai_full_values_same_question_5000.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(out)
print("openai_calls:", len(captured["openai_generate_calls"]))
if captured["openai_generate_calls"]:
    print("max_tokens_sent:", captured["openai_generate_calls"][0].get("max_tokens"))
print("done:", report.get("done_event"))
