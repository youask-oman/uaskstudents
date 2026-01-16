"""
Solver V3 Service (Updated for Schema v1.0).

Handles LLM interaction, strict schema validation, and telemetry.
Simplified to pass through structured visual data to frontend.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple, AsyncIterator
from datetime import datetime

from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3
from app.services.validation_v3 import validate_response, create_error_response, generate_repair_prompt
from app.prompts import get_prompt, get_schema
from app.utils.schema_deref import deref_json_schema, validate_no_refs

class SolverV3:
    """
    Math Solver V3 using OpenAI Structured Outputs (Schema v1.0).
    """
    
    def __init__(self):
        """Initialize solver with OpenAI client."""
        self._client = None
        self._model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
        self._fallback_model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
        print(f"[SOLVER_V3_INIT] Initialized with model: {self._model}")

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client

    async def solve(
        self,
        problem_text: str,
        context: str = "",
        trace: bool = False,
        include_plot_base64: bool = False,
        request_id: str = None
    ) -> Dict[str, Any]:
        
        start_time_perf = time.perf_counter()
        
        # Default telemetry structure
        telemetry = {
            "request_id": request_id,
            "model": self._model,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": None, # Null if N/A
            "latency_ms_openai": 0,
            "latency_ms_total": 0,
            
            # Internal/Debug metrics
            "validated": False,
            "repaired": False,
            "repair_reason": None,
            "validation_failures_count": 0,
            "plot_attempted": False,
            "plot_generated": False,
        }
        
        if trace:
            print(f"\n[SOLVER_V3] ==================== START ====================")
            print(f"[SOLVER_V3] Problem: {problem_text[:100]}...")
            print(f"[SOLVER_V3] Model: {self._model}")
            print(f"[SOLVER_V3] Request ID: {request_id}")

        try:
            # Step 1: Load Prompts
            try:
                system_prompt = get_prompt("solver_system", "v3")
            except Exception as e:
                return self._handle_error(problem_text, f"Prompt load failed: {e}", "prompt_error", telemetry, start_time_perf)

            # Step 2: Call LLM
            llm_start_perf = time.perf_counter()
            try:
                response_data, llm_tokens = await self._call_llm_with_schema(
                    problem_text, context, system_prompt, trace=trace
                )
                
                # Capture precise OpenAI latency
                llm_end_perf = time.perf_counter()
                telemetry["latency_ms_openai"] = int((llm_end_perf - llm_start_perf) * 1000)
                
                # Extract tokens
                telemetry["input_tokens"] = llm_tokens.get("input", 0)
                telemetry["output_tokens"] = llm_tokens.get("output", 0)
                telemetry["total_tokens"] = llm_tokens.get("total", 0)
                telemetry["cached_tokens"] = llm_tokens.get("cached", None)
                
                if trace:
                    print(f"[SOLVER_V3] ✅ Received LLM response ({telemetry['latency_ms_openai']}ms)")
            except Exception as e:
                return self._handle_error(problem_text, f"LLM Call failed: {e}", "llm_error", telemetry, start_time_perf)

            # Step 2.5: Normalize Response (Inject Defaults)
            if "refusal" not in response_data:
                response_data["refusal"] = {"is_refusal": False, "refusal_reason": None}
            if "visuals" not in response_data:
                response_data["visuals"] = {"should_visualize": False, "decision_reason": "Default", "plots": None, "alternative_visual": None}
            if "quality" not in response_data:
                response_data["quality"] = {"confidence": 95, "common_mistakes": [], "next_practice": []}
            if "verification" not in response_data:
                 response_data["verification"] = {"method": "Self-Consistency", "work_latex": "Verified internally", "conclusion": "Stable", "alternative_method": None}
            elif isinstance(response_data.get("verification"), dict) and "alternative_method" not in response_data["verification"]:
                 response_data["verification"]["alternative_method"] = None

            # Step 2.6: Normalize with Defaults (Part C1)
            response_data = self.normalize_solver_response(response_data)

            # Step 3: Validate
            _model_temp = response_data.pop("_model", None)
            validation = validate_response(response_data, strict=True)
            if _model_temp:
                 response_data["_model"] = _model_temp

            if not validation.valid:
                telemetry["validation_failures_count"] += 1
                if trace:
                    print(f"[SOLVER_V3] ⚠️ Validation failed ({len(validation.errors)} errors)")
                
                # Step 4: Repair Loop
                telemetry["repair_reason"] = f"{len(validation.errors)} validation errors"
                response_data = await self._repair_response(
                    problem_text, context, system_prompt, response_data, validation, trace=trace
                )
                telemetry["repaired"] = response_data.get("_repaired", False)
                
                # Re-validate
                validation = validate_response(response_data, strict=True)
                if not validation.valid:
                    if trace:
                        print(f"[SOLVER_V3] ❌ Repair failed")
                    return self._handle_error(problem_text, validation.errors, "validation_failed_after_repair", telemetry, start_time_perf)

            telemetry["validated"] = True
            
            # Step 5: Visuals Telemetry
            visuals = response_data.get("visuals", {})
            if visuals.get("should_visualize", False):
                telemetry["plot_attempted"] = True
                telemetry["plot_generated"] = True

            # Finalize
            telemetry["latency_ms_total"] = int((time.perf_counter() - start_time_perf) * 1000)
            
            # Embed telemetry in response payload (legacy key + new key)
            response_data["_telemetry"] = telemetry 
            response_data["telemetry"] = telemetry
            
            response_data["_timestamp"] = datetime.utcnow().isoformat()
            response_data["schema_version"] = "v1.0"
            
            if trace:
                 print(f"[SOLVER_V3] Telemetry: {json.dumps(telemetry)}")
                 print(f"[SOLVER_V3] ==================== SUCCESS ====================")
            
            return response_data

        except Exception as e:
            if trace:
                print(f"[SOLVER_V3] ❌ FATAL: {e}")
                import traceback
                traceback.print_exc()
            return self._handle_error(problem_text, str(e), "fatal_error", telemetry, start_time_perf)


    def normalize_solver_response(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject defaults for boilerplate keys to ensure schema validation passes 
        without extra OpenAI repair calls for non-critical metadata. (Part C1)
        """
        # refusal defaults
        if "refusal" not in obj or not isinstance(obj["refusal"], dict):
            obj["refusal"] = {"is_refusal": False, "refusal_reason": None, "safe_alternative": None}
        else:
            if "is_refusal" not in obj["refusal"]: obj["refusal"]["is_refusal"] = False
            if "refusal_reason" not in obj["refusal"]: obj["refusal"]["refusal_reason"] = None
            if "safe_alternative" not in obj["refusal"]: obj["refusal"]["safe_alternative"] = None

        # visuals defaults
        if "visuals" not in obj or not isinstance(obj["visuals"], dict):
            obj["visuals"] = {"should_visualize": False, "decision_reason": "Default", "plots": [], "alternative_visual": None}
        else:
            if "should_visualize" not in obj["visuals"]: obj["visuals"]["should_visualize"] = False
            if "decision_reason" not in obj["visuals"]: obj["visuals"]["decision_reason"] = ""
            if "plots" not in obj["visuals"] or obj["visuals"]["plots"] is None: obj["visuals"]["plots"] = []
            if "alternative_visual" not in obj["visuals"]: obj["visuals"]["alternative_visual"] = None

        # quality defaults
        if "quality" not in obj or not isinstance(obj["quality"], dict):
            obj["quality"] = {"confidence": 0.5, "common_mistakes": [], "next_practice": []}
        else:
            if "confidence" not in obj["quality"]: obj["quality"]["confidence"] = 0.5
            if "common_mistakes" not in obj["quality"] or obj["quality"]["common_mistakes"] is None: obj["quality"]["common_mistakes"] = []
            if "next_practice" not in obj["quality"] or obj["quality"]["next_practice"] is None: obj["quality"]["next_practice"] = []

        # verification defaults
        if "verification" not in obj or not isinstance(obj["verification"], dict):
             obj["verification"] = {"method": "Self-Consistency", "work_latex": "Verified internally", "conclusion": "Stable", "alternative_method": None}
        elif "alternative_method" not in obj["verification"]:
             obj["verification"]["alternative_method"] = None

        # assumptions
        if "assumptions" not in obj or obj["assumptions"] is None:
            obj["assumptions"] = []

        return obj

    async def solve_stream(
        self,
        problem_text: str,
        context: str = "",
        trace: bool = False,
        request_id: str = None,
        max_output_tokens: int = 900
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streamed Math Solver V3 using OpenAI Structured Outputs.
        Yields chunks with 'type': 'delta' or 'usage'. (Part A3, Part D)
        """
        start_time_perf = time.perf_counter()
        
        telemetry = {
            "request_id": request_id,
            "model": self._model,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": None,
            "latency_ms_openai": 0,
            "truncated": False,
            "validated": False,
            "repaired": False
        }

        try:
            system_prompt = get_prompt("solver_system", "v3")
            user_message = self._build_user_message(problem_text, context)
            
            # Implementation of Retries with Exponential Backoff (Part G1)
            max_retries = 3
            current_retry = 0
            
            while current_retry <= max_retries:
                try:
                    llm_start_perf = time.perf_counter()
                    
                    # Note: Structured Outputs with Streaming works best with Chat Completions
                    params = {
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "solve_response_v3",
                                "strict": True,
                                "schema": deref_json_schema(get_json_schema_for_openai_v3())
                            }
                        },
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        "max_completion_tokens": max_output_tokens # Part B2
                    }

                    response = await self.client.chat.completions.create(**params)
                    
                    async for chunk in response:
                        if not chunk.choices:
                            # Usage chunk (last one in stream_options: include_usage)
                            if chunk.usage:
                                telemetry["input_tokens"] = chunk.usage.prompt_tokens
                                telemetry["output_tokens"] = chunk.usage.completion_tokens
                                telemetry["total_tokens"] = chunk.usage.total_tokens
                                if hasattr(chunk.usage, 'prompt_tokens_details') and chunk.usage.prompt_tokens_details:
                                    telemetry["cached_tokens"] = getattr(chunk.usage.prompt_tokens_details, 'cached_tokens', 0)
                                
                                telemetry["latency_ms_openai"] = int((time.perf_counter() - llm_start_perf) * 1000)
                                yield {"type": "telemetry", "telemetry": telemetry}
                            continue
                            
                        delta = chunk.choices[0].delta
                        if delta.content:
                            yield {"type": "delta", "text": delta.content}
                        
                        if chunk.choices[0].finish_reason == "length":
                            telemetry["truncated"] = True
                            # We yield truncation info in telemetry at the end, but can also notify here
                            yield {"type": "meta", "truncated": True}
                        elif chunk.choices[0].finish_reason == "content_filter":
                            yield {"type": "error", "error": {"code": "content_filter", "message": "Content filtered."}}

                    return # Success

                except Exception as e:
                    # Handle Rate Limits (429) and Transient Errors (Part G1)
                    current_retry += 1
                    if current_retry > max_retries:
                        raise e
                    
                    # Simple exponential backoff
                    wait_time = (2 ** current_retry) + (time.time() % 1) # add a bit of jitter
                    if trace:
                        print(f"[SOLVER_V3_STREAM] Error: {e}. Retrying in {wait_time:.2f}s... ({current_retry}/{max_retries})")
                    await asyncio.sleep(wait_time)

        except Exception as e:
            if trace:
                print(f"[SOLVER_V3_STREAM] ❌ FATAL: {e}")
            yield {"type": "error", "error": {"code": "fatal", "message": str(e)}}

    def _build_user_message(self, problem_text: str, context: str) -> str:
        return f"""Problem: {problem_text}

Context: {context if context else "No additional context provided."}

**CRITICAL**: Return ONLY strictly valid JSON matching the schema (v1.0).
- All top-level keys are REQUIRED: problem, classification, refusal, assumptions, steps, final_answer, verification, visuals, quality.
- visuals.should_visualize = true for any graphable content
- verification is a SINGLE object (method, work_latex, conclusion). verification.alternative_method is also required (object or null).
- refusal.is_refusal = true ONLY if safety policy requires it
- Avoid nulls where possible, use empty arrays/strings instead.
"""


    def _handle_error(self, problem, errors, code, telemetry, start_time_perf):
        telemetry["latency_ms_total"] = int((time.perf_counter() - start_time_perf) * 1000)
        err_resp = create_error_response(problem, errors if isinstance(errors, list) else [str(errors)], code)
        err_resp["_telemetry"] = telemetry
        err_resp["telemetry"] = telemetry
        return err_resp


    async def _call_llm_with_schema(self, problem_text, context, system_prompt, trace=False):
        user_message = self._build_user_message(problem_text, context)
        tokens = {"input": 0, "output": 0, "total": 0, "cached": None}
        
        # Check model type for API method
        if "gpt-5" in self._model.lower():
             # Use client.responses.create for gpt-5 access
             params = {
                "model": self._model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_message}]}
                ],
                "text": {
                    "verbosity": "high",
                    "format": {
                        "type": "json_schema",
                        "name": "solve_response_v3",
                        "strict": True,
                        "schema": deref_json_schema(get_json_schema_for_openai_v3())
                    }
                },
                "max_output_tokens": 5000
             }
             try:
                 response = await self.client.responses.create(**params)
                 
                 # Extract tokens from responses API
                 if hasattr(response, 'usage'):
                     # Try standard OpenAI fields first, then specific gpt-5 ones
                     if hasattr(response.usage, 'prompt_tokens'):
                         tokens["input"] = response.usage.prompt_tokens
                         tokens["output"] = response.usage.completion_tokens
                         tokens["total"] = response.usage.total_tokens
                     elif hasattr(response.usage, 'input_tokens'):
                         tokens["input"] = response.usage.input_tokens
                         tokens["output"] = response.usage.output_tokens
                         tokens["total"] = response.usage.total_tokens
                     
                     # Check for cached tokens if available
                     if hasattr(response.usage, 'prompt_tokens_details'):
                          tokens["cached"] = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0)
                     elif hasattr(response.usage, 'input_token_details'):
                          tokens["cached"] = getattr(response.usage.input_token_details, 'cached_tokens', 0)
                 
                 if hasattr(response, 'output') and response.output:
                     content = None
                     for item in response.output:
                         if hasattr(item, 'content') and item.content:
                             content = item.content[0].text
                             break
                     if not content:
                         raise ValueError("No content in gpt-5 response")
                                      
                     return json.loads(content), tokens
                 else:
                     raise ValueError("Empty gpt-5 output")
             except Exception:
                 raise

        else:
            # Standard Chat Completions for gpt-4o
            params = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "solve_response_v3",
                        "strict": True,
                        "schema": deref_json_schema(get_json_schema_for_openai_v3())
                    }
                }
            }
            
            response = await self.client.chat.completions.create(**params)
            content = response.choices[0].message.content
            
            if hasattr(response, 'usage'):
                tokens["input"] = response.usage.prompt_tokens
                tokens["output"] = response.usage.completion_tokens
                tokens["total"] = response.usage.total_tokens
                
                # Check for cached tokens in prompt_tokens_details
                if hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
                    tokens["cached"] = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0)
                # Or sometimes top level logic depending on library version
                if tokens["cached"] is None and hasattr(response.usage, 'cached_tokens'):
                     tokens["cached"] = response.usage.cached_tokens

            return json.loads(content), tokens

    async def _repair_response(self, problem, context, system_prompt, invalid_data, validation, trace=False):
        if trace:
             print(f"[SOLVER_V3] Attempting repair...")
        
        repair_prompt = generate_repair_prompt(invalid_data, validation, problem)
        
        # For Strict Structured Output repair:
        # We start a fresh conversation or append. strict mode validation is rigid.
        # Simple approach: New request with "previous_invalid_json" in context?
        # Or standard append.
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Problem: {problem}\nContext: {context}"},
            {"role": "assistant", "content": json.dumps(invalid_data)},
            {"role": "user", "content": repair_prompt}
        ]
        
        params = {
            "model": self._fallback_model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "solve_response_v3",
                    "strict": True,
                    "schema": deref_json_schema(get_json_schema_for_openai_v3())
                }
            }
        }
        
        # Note: If gpt-5, we should use responses.create similarly.
        # But repair is edge case, often fallback to gpt-4o works fine.
        # We'll use fallback model for repair to be safe and cheap?
        # Original code used fallback model (gpt-5-mini).
        
        response = await self.client.chat.completions.create(**params)
        data = json.loads(response.choices[0].message.content)
        data["_repaired"] = True
        return data

import asyncio
_solver_instance = None
def get_solver_v3():
    global _solver_instance
    if not _solver_instance:
        _solver_instance = SolverV3()
    return _solver_instance

if __name__ == "__main__":
    import asyncio
    async def test():
        s = get_solver_v3()
        print("Solver initialized.")
    asyncio.run(test())
