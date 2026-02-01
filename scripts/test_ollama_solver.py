import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from app.services.solver_v3 import SolverV3
from app.services.validation_v3 import validate_response


async def main():
    solver = SolverV3()
    question = "Solve x + 1 = 2"
    start = time.perf_counter()
    result = await solver.solve(question, max_output_tokens=400)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    telemetry = result.get("telemetry") or {}
    provider = telemetry.get("provider")
    model = telemetry.get("model")
    cleaned = {k: v for k, v in result.items() if k not in {"telemetry", "_telemetry", "_timestamp"}}
    validation = validate_response(cleaned, strict=True)

    output_preview = json.dumps(cleaned, ensure_ascii=True)[:200]

    print(f"provider: {provider}")
    print(f"model: {model}")
    print(f"latency_ms: {elapsed_ms}")
    print(f"validated: {validation.valid}")
    print(f"output_preview: {output_preview}")


if __name__ == "__main__":
    asyncio.run(main())
