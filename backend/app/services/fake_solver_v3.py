import json
import time
from typing import Any, AsyncIterator, Dict, Optional


class FakeSolverV3:
    """
    DEV/TEST fake solver that returns deterministic content and telemetry.
    Never calls external providers.
    """

    default_model = "gpt-5-mini"
    default_provider = "openai_simulated"

    def _resolve_tokens(self, debug_simulated_tokens: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tokens = debug_simulated_tokens or {}
        input_tokens = int(tokens.get("input_tokens", 2000))
        output_tokens = int(tokens.get("output_tokens", 1000))
        cached_tokens = int(tokens.get("cached_tokens", 0))
        total_tokens = int(tokens.get("total_tokens", input_tokens + output_tokens))
        model = str(tokens.get("model", self.default_model))
        provider = str(tokens.get("provider", self.default_provider))
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "total_tokens": total_tokens,
            "model": model,
            "provider": provider,
        }

    async def solve(
        self,
        problem_text: str,
        context: str = "",
        trace: bool = False,
        user_id: Optional[int] = None,
        db_session=None,
        attempt_id: Optional[str] = None,
        request_id: Optional[str] = None,
        debug_simulated_tokens: Optional[Dict[str, Any]] = None,
        debug_force_error: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        if debug_force_error:
            raise RuntimeError("Simulated solver failure (FakeSolverV3)")

        tokens = self._resolve_tokens(debug_simulated_tokens)
        data = {
            "schema_version": "v1",
            "problem": {
                "goal": "Solve",
                "statement": problem_text or "No problem provided",
            },
            "steps": [
                {"index": 1, "title": "Identify", "work": "We parse the problem."},
                {"index": 2, "title": "Solve", "work": "We apply a deterministic rule."},
            ],
            "final_answer": {"value": "x = 1", "latex": "x = 1"},
            "status": "ok",
            "meta": {
                "provider": tokens["provider"],
                "model": tokens["model"],
                "token_usage": {
                    "input_tokens": tokens["input_tokens"],
                    "output_tokens": tokens["output_tokens"],
                    "cached_tokens": tokens["cached_tokens"],
                    "total_tokens": tokens["total_tokens"],
                },
                "latency_ms_total": 5,
            },
        }
        return data

    async def solve_stream(
        self,
        problem_text: str,
        context: str = "",
        trace: bool = False,
        request_id: str = None,
        max_output_tokens: int = 900,
        system_prompt: Optional[str] = None,
        developer_prompt: Optional[str] = None,
        json_schema_config: Optional[Dict[str, Any]] = None,
        trusted_context: Optional[Dict[str, Any]] = None,
        requested_mode: str = "minimal",
        attempt_id: Optional[str] = None,
        debug_simulated_tokens: Optional[Dict[str, Any]] = None,
        debug_force_error: bool = False,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        if debug_force_error:
            yield {
                "type": "failure",
                "error": {
                    "code": "simulated_error",
                    "message": "Simulated solver failure (FakeSolverV3)",
                    "request_id": request_id,
                },
            }
            return

        tokens = self._resolve_tokens(debug_simulated_tokens)
        response_obj = {
            "schema_version": "v1",
            "problem": {
                "goal": "Solve",
                "statement": problem_text or "No problem provided",
            },
            "steps": [
                {"index": 1, "title": "Identify", "work": "We parse the problem."},
                {"index": 2, "title": "Solve", "work": "We apply a deterministic rule."},
            ],
            "final_answer": {"value": "x = 1", "latex": "x = 1"},
            "status": "ok",
        }

        yield {"type": "delta", "text": json.dumps(response_obj)}

        telemetry = {
            "request_id": request_id,
            "provider": tokens["provider"],
            "model": tokens["model"],
            "input_tokens": tokens["input_tokens"],
            "output_tokens": tokens["output_tokens"],
            "cached_tokens": tokens["cached_tokens"],
            "total_tokens": tokens["total_tokens"],
            "latency_ms_openai": int((time.perf_counter() * 1000) % 1000),
            "truncated": False,
            "validated": True,
            "repaired": False,
            "openai_calls_count": 0,
            "requested_mode": requested_mode,
            "learning_mode": (trusted_context or {}).get("learning_mode") or "solve",
        }
        yield {"type": "usage", "telemetry": telemetry}

    async def _repair_response(self, *args, **kwargs):
        return None, None
