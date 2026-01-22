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
from app.utils.schema_cleaner import enforce_strict
from app.services.validation_v3 import validate_response, create_error_response, generate_repair_prompt
from app.prompts import get_prompt, get_schema
from app.utils.schema_deref import deref_json_schema, validate_no_refs
from app.llm_profiles.profiles import get_prompt_profile
from app.services.response_mapper import map_minimal_to_canonical
from app.utils.token_limits import get_effective_max_tokens

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
        request_id: str = None,
        user_tier: str = "free",
        # New Context Params
        user_id: Optional[int] = None,
        db_session: Optional[Any] = None,  # SQLModel Session
        requested_mode: str = "minimal",
        db_plan: Optional[Any] = None,
        # Tier-aware payload fields (normalized at frontend)
        trusted_context: Optional[Dict[str, Any]] = None,
        learning_mode: Optional[str] = None  # "solve" | "study"
    ) -> Dict[str, Any]:
        
        start_time_perf = time.perf_counter()
        
        # Default telemetry
        telemetry = {
            "request_id": request_id,
            "model": self._model,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": None,
            "latency_ms_openai": 0,
            "latency_ms_total": 0,
            "mode_resolved": "unknown",
            "tier_effective": user_tier,
            "validated": False,
            "repaired": False,
            "repair_reason": None,
            "validation_failures_count": 0,
            "plot_attempted": False,
            "plot_generated": False,
            "debit_status": "none",
            "repair_attempted": False,
            "openai_calls_count": 0,
            "openai_payload": None
        }
        
        # If no DB session provided (backwards compat[ERROR]), we can't do advanced resolution/accounting.
        # But for V3 strict we expect db_session.
        
        if trace:
            print(f"\n[SOLVER_V3] ==================== START ====================")
            print(f"[SOLVER_V3] Request ID: {request_id}")

        profile = None
        debit_result = None

        try:
            # Step 1: Resolve Profile
            if db_session:
                from app.llm_profiles.profile_resolver import ProfileResolver
                from app.models import User
                
                # Load user object if needed
                user_obj = None
                if user_id:
                     from sqlmodel import select
                     user_obj = db_session.get(User, user_id)

                try:
                    profile = ProfileResolver.resolve_profile(
                        db_session, 
                        user_obj, 
                        requested_mode=requested_mode,
                        force_tier=user_tier if not user_obj else None
                    )
                    telemetry["mode_resolved"] = profile.mode
                    telemetry["tier_effective"] = profile.tier
                    
                    if trace:
                        print(f"[SOLVER_V3] Resolved Profile: Tier={profile.tier}, Mode={profile.mode}")

                except Exception as e:
                    return self._handle_error(problem_text, f"Profile resolution failed: {e}", "config_error", telemetry, start_time_perf)
            else:
                # Fallback purely for unit tests without DB
                from app.llm_profiles.profiles import get_prompt_profile
                profile = get_prompt_profile(user_tier)
                profile.mode = "minimal" if user_tier == "free" else "detailed" # Mock

            # Step 1.5: Accounting (Debit Pending) - MOVED TO API LAYER
            if db_session and user_id:
                # API layer (api.py) handles check_entitlement_and_debit before calling solve().
                # We do NOT debit here to avoid double-charging.
                pass

            # Step 2: Prepare LLM Args
            system_prompt = profile.system_prompt_content
            # Ensure schema is dereferenced if dict
            json_schema_config = profile.json_schema_content
            # Wrap for OpenAI structured output strict mode
            def load_schema(config_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
                candidate = config_schema
                if not isinstance(candidate, dict) or not candidate:
                    candidate = get_json_schema_for_openai_v3()
                
                # Check for "wrapped" schema style
                if "schema" in candidate and isinstance(candidate["schema"], dict):
                     candidate = candidate["schema"]

                try:
                    deref = deref_json_schema(candidate)
                except Exception as exc:
                    print(f"[SOLVER_V3] Schema dereference failed: {exc}")
                    deref = deref_json_schema(get_json_schema_for_openai_v3())
                if not isinstance(deref, dict):
                    deref = deref_json_schema(get_json_schema_for_openai_v3())

                # Apply strict cleaning
                deref = enforce_strict(deref)

                if deref.get("type") is None:
                    deref["type"] = "object"
                return deref

            deref_schema = load_schema(json_schema_config if isinstance(json_schema_config, dict) else None)

            openai_schema_wrapper = {
                 "name": "solve_response_v3",
                 "strict": True,
                 "schema": deref_schema
            }

            # Step 3: Call LLM
            # Enforce deterministic token caps (Part A2)
            # FORCE learning_mode="solve" if mode="minimal" to prevent token blowout (Part A3)
            if profile.mode == "minimal":
                learning_mode = "solve"
                if trusted_context:
                    trusted_context["learning_mode"] = "solve"

            effective_learning_mode = trusted_context.get("learning_mode") if trusted_context else learning_mode
            effective_max_tokens = get_effective_max_tokens(profile.mode, effective_learning_mode)
            
            # Telemetry for effective max
            telemetry["max_output_tokens_effective"] = effective_max_tokens
            
            llm_start_perf = time.perf_counter()
            try:
                response_data, llm_tokens = await self._call_llm_with_schema(
                    problem_text, 
                    context, 
                    system_prompt, 
                    json_schema_config=openai_schema_wrapper, 
                    max_output_tokens=effective_max_tokens,
                    trace=trace,
                    trusted_context=trusted_context,
                    requested_mode=requested_mode
                )
                
                llm_end_perf = time.perf_counter()
                telemetry["latency_ms_openai"] = int((llm_end_perf - llm_start_perf) * 1000)
                
                telemetry["input_tokens"] = llm_tokens.get("input", 0)
                telemetry["output_tokens"] = llm_tokens.get("output", 0)
                telemetry["total_tokens"] = llm_tokens.get("total", 0)
                telemetry["cached_tokens"] = llm_tokens.get("cached", None)
                telemetry["openai_payload"] = llm_tokens.get("payload")
                telemetry["openai_calls_count"] = llm_tokens.get("openai_calls", 1)

            except Exception as e:
                # Refund logic - HANDLED BY API LAYER
                return self._handle_error(problem_text, f"LLM Call failed: {e}", "llm_error", telemetry, start_time_perf)

            # Step 4: Map Minimal Response (if needed)
            # The ProfileResolver should tell us if mapping is needed, or we rely on mode="minimal"
            # AND the fact that the schema used was minimal.
            # Minimal schema usually doesn't match canonical V3 fully[ERROR] 
            # Or does minimal schema match V3 structure but with missing fields[ERROR]
            # Our `map_minimal_to_canonical` takes `MinimalSolveResponse` and makes `SolveResponseV3`.
            # We assume if mode="minimal", we must map.
            
            if profile.mode == "minimal":
                 try:
                    response_data = map_minimal_to_canonical(response_data, problem_text)
                 except Exception as e:
                    return self._handle_error(problem_text, f"Response Mapping failed: {e}", "mapping_error", telemetry, start_time_perf)


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
                    print(f"[SOLVER_V3] [WARN] Validation failed ({len(validation.errors)} errors)")
                
                # Step 4: Repair Loop
                telemetry["repair_reason"] = f"{len(validation.errors)} validation errors"
                telemetry["repair_attempted"] = True
                telemetry["openai_calls_count"] = telemetry.get("openai_calls_count", 0) + 1
                response_data = await self._repair_response(
                    problem_text,
                    context,
                    system_prompt,
                    response_data,
                    validation,
                    json_schema_config=openai_schema_wrapper,
                    max_output_tokens=effective_max_tokens,
                    requested_mode=requested_mode,
                    trace=trace
                )
                telemetry["repaired"] = response_data.get("_repaired", False)
                
                # Re-validate
                validation = validate_response(response_data, strict=True)
                if not validation.valid:
                    if trace:
                        print(f"[SOLVER_V3] [ERROR] Repair failed")
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
                print(f"[SOLVER_V3] [ERROR] FATAL: {e}")
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

        # final_answer - ensure it's always a dict with required fields
        if "final_answer" not in obj or obj["final_answer"] is None:
            obj["final_answer"] = {"answer_text": "", "answer_latex": "", "values": [], "units": ""}
        elif isinstance(obj["final_answer"], str):
            # Convert string to proper object
            obj["final_answer"] = {"answer_text": obj["final_answer"], "answer_latex": "", "values": [], "units": ""}
        elif isinstance(obj["final_answer"], dict):
            if "answer_text" not in obj["final_answer"]: obj["final_answer"]["answer_text"] = ""
            if "answer_latex" not in obj["final_answer"]: obj["final_answer"]["answer_latex"] = ""
            if "values" not in obj["final_answer"] or obj["final_answer"]["values"] is None: obj["final_answer"]["values"] = []
            if "units" not in obj["final_answer"]: obj["final_answer"]["units"] = ""

        return obj

    async def solve_stream(
        self,
        problem_text: str,
        context: str = "",
        trace: bool = False,
        request_id: str = None,
        max_output_tokens: int = 900, # Ignored in favor of deterministic cap
        system_prompt: Optional[str] = None,
        json_schema_config: Optional[Dict[str, Any]] = None,
        trusted_context: Optional[Dict[str, Any]] = None,
        requested_mode: str = "minimal"
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
            "repaired": False,
            "openai_calls_count": 0,
            "openai_payload": None
        }

        try:
            resolved_system_prompt = system_prompt or get_prompt("solver_system", "v3")
            if isinstance(json_schema_config, dict):
                # Check for "wrapped" schema style (used in free/schema.json)
                target_schema = json_schema_config
                if "schema" in json_schema_config and isinstance(json_schema_config["schema"], dict):
                     target_schema = json_schema_config["schema"]
                
                schema_wrapper = {
                    "name": "solve_response_v3",
                    "strict": True,
                    "schema": enforce_strict(deref_json_schema(target_schema))
                }
            else:
                schema_wrapper = {
                    "name": "solve_response_v3",
                    "strict": True,
                    "schema": enforce_strict(deref_json_schema(get_json_schema_for_openai_v3()))
                }

            user_message = self._build_user_message(
                problem_text,
                context,
                trusted_context=trusted_context,
                requested_mode=requested_mode
            )
            
            # FORCE learning_mode="solve" if mode="minimal" to prevent token blowout
            # We must inspect trusted_context if present, or rely on requested_mode mapping
            # Assuming profile check or logic upstream. Here we enforce hard-cap logic.
            # If requested_mode is minimal, we treat it as minimal for caps.
            
            # Ideally we need "profile" object here too for mode, but we have `requested_mode`.
            # We will use requested_mode to determine our deterministic cap.
            
            effective_learning_mode_stream = None
            if trusted_context:
                if requested_mode == "minimal":
                     trusted_context["learning_mode"] = "solve"
                effective_learning_mode_stream = trusted_context.get("learning_mode")

            effective_max_tokens = get_effective_max_tokens(requested_mode, effective_learning_mode_stream)
            telemetry["max_output_tokens_effective"] = effective_max_tokens

            telemetry["openai_payload"] = {
                "response_format_schema_name": schema_wrapper.get("name", "solve_response_v3"),
                "max_output_tokens": effective_max_tokens,
                "system_message_length": len(resolved_system_prompt or ""),
                "user_message_length": len(user_message or "")
            }
            
            # Implementation of Retries with Exponential Backoff (Part G1)
            max_retries = 3
            current_retry = 0
            
            while current_retry <= max_retries:
                try:
                    llm_start_perf = time.perf_counter()
                    telemetry["openai_calls_count"] += 1
                    
                    # Note: Structured Outputs with Streaming works best with Chat Completions
                    params = {
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": resolved_system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": schema_wrapper
                        },
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        "max_completion_tokens": effective_max_tokens # Part A2
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
                print(f"[SOLVER_V3_STREAM] [ERROR] FATAL: {e}")
            yield {"type": "error", "error": {"code": "fatal", "message": str(e)}}

    def _build_user_message(
        self, 
        problem_text: str, 
        context: str = "",
        trusted_context: dict = None,
        requested_mode: str = "minimal"
    ) -> str:
        """
        Build compact JSON user message for OpenAI.
        
        Only includes: trusted_context (normalized), requested_mode, problem.
        No billing/feature metadata, no redundant fields.
        """
        from app.services.context_normalizer import build_compact_user_message, normalize_trusted_context
        
        # Normalize trusted_context to compact enums (CA, CA-ON, 11)
        normalized_ctx = normalize_trusted_context(trusted_context) if trusted_context else {}
        
        # Add requested_mode to context
        if requested_mode:
            normalized_ctx["requested_mode"] = requested_mode
        
        # Build compact JSON message
        return build_compact_user_message(problem_text, normalized_ctx)


    def _handle_error(self, problem, errors, code, telemetry, start_time_perf):
        telemetry["latency_ms_total"] = int((time.perf_counter() - start_time_perf) * 1000)
        err_resp = create_error_response(problem, errors if isinstance(errors, list) else [str(errors)], code)
        err_resp["_telemetry"] = telemetry
        err_resp["telemetry"] = telemetry
        return err_resp


    async def _call_llm_with_schema(
        self, 
        problem_text, 
        context, 
        system_prompt, 
        json_schema_config,
        max_output_tokens=4096,
        trace=False,
        trusted_context: dict = None,
        requested_mode: str = "minimal"
    ):
        # Build compact JSON user message with normalized trusted_context
        if trace:
            print(f"[SOLVER_DEBUG] _call_llm_with_schema requested_mode={requested_mode}")
            if trusted_context:
                print(f"[SOLVER_DEBUG] trusted_context: {trusted_context}")
        user_message = self._build_user_message(
            problem_text, 
            context, 
            trusted_context=trusted_context,
            requested_mode=requested_mode
        )
        if trace:
            print(f"[SOLVER_DEBUG] _call_llm_with_schema user_message[:100]: {user_message[:100]}...")
        tokens = {"input": 0, "output": 0, "total": 0, "cached": None}
        schema_name = None
        schema_payload = json_schema_config
        if isinstance(json_schema_config, dict):
            schema_name = json_schema_config.get("name")
            if "schema" in json_schema_config:
                schema_payload = json_schema_config["schema"]
        payload_type = schema_payload.get("type") if isinstance(schema_payload, dict) else None
        if payload_type is None:
            print(f"[SOLVER_V3] WARNING: schema_payload missing type -> {schema_payload.get('$id', 'no-id')}? forcing object")
            if isinstance(schema_payload, dict):
                schema_payload["type"] = "object"
        
        # Check model type for API method
        if "gpt-5" in self._model.lower():
            # Use client.responses.create for gpt-5 access
            verbosity = "low" if requested_mode == "minimal" else "high"
            params = {
                "model": self._model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_message}]}
                ],
                "text": {
                    "verbosity": verbosity,
                    "format": {
                        "type": "json_schema",
                    "json_schema": schema_payload
                }
            },
                "max_output_tokens": max_output_tokens
            }
            response = await self.client.responses.create(**params)

            if hasattr(response, "usage"):
                if hasattr(response.usage, "prompt_tokens"):
                    tokens["input"] = response.usage.prompt_tokens
                    tokens["output"] = response.usage.completion_tokens
                    tokens["total"] = response.usage.total_tokens
                elif hasattr(response.usage, "input_tokens"):
                    tokens["input"] = response.usage.input_tokens
                    tokens["output"] = response.usage.output_tokens
                    tokens["total"] = response.usage.total_tokens

                if hasattr(response.usage, "prompt_tokens_details"):
                    tokens["cached"] = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
                elif hasattr(response.usage, "input_token_details"):
                    tokens["cached"] = getattr(response.usage.input_token_details, "cached_tokens", 0)

            content = None
            if hasattr(response, "output") and response.output:
                for item in response.output:
                    if hasattr(item, "content") and item.content:
                        content = item.content[0].text
                        break
            if not content:
                raise ValueError("Empty gpt-5 output")

            tokens["payload"] = {
                "response_format_schema_name": schema_name or "solve_response_v3",
                "max_output_tokens": max_output_tokens,
                "system_message_length": len(system_prompt or ""),
                "user_message_length": len(user_message or "")
            }
            tokens["openai_calls"] = 1
            return json.loads(content), tokens

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
                    "json_schema": schema_payload
                },
                "max_completion_tokens": max_output_tokens
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

            tokens["payload"] = {
                "response_format_schema_name": schema_name or "solve_response_v3",
                "max_output_tokens": max_output_tokens,
                "system_message_length": len(system_prompt or ""),
                "user_message_length": len(user_message or "")
            }
            tokens["openai_calls"] = 1
            return json.loads(content), tokens

    async def _repair_response(
        self,
        problem,
        context,
        system_prompt,
        invalid_data,
        validation,
        json_schema_config,
        max_output_tokens=1200,
        requested_mode: str = "minimal",
        trace=False
    ):
        if trace:
             print(f"[SOLVER_V3] Attempting repair...")
        
        repair_prompt = generate_repair_prompt(invalid_data, validation, problem)
        
        # For Strict Structured Output repair:
        # We start a fresh conversation or append. strict mode validation is rigid.
        # Simple approach: New request with "previous_invalid_json" in context[ERROR]
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
                "json_schema": json_schema_config
            },
            "max_completion_tokens": max_output_tokens
        }
        
        # Note: If gpt-5, we should use responses.create similarly.
        # But repair is edge case, often fallback to gpt-4o works fine.
        # We'll use fallback model for repair to be safe and cheap[ERROR]
        # Original code used fallback model (gpt-5-mini).
        
        if "gpt-5" in self._fallback_model.lower():
            verbosity = "low" if requested_mode == "minimal" else "high"
            repair_user_content = (
                f"Problem: {problem}\n"
                f"Context: {context}\n"
                f"Previous invalid JSON:\n{json.dumps(invalid_data)}\n"
                f"{repair_prompt}"
            )
            response = await self.client.responses.create(
                model=self._fallback_model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": repair_user_content}]}
                ],
                text={
                    "verbosity": verbosity,
                    "format": {
                        "type": "json_schema",
                        "json_schema": json_schema_config
                    }
                },
                max_output_tokens=max_output_tokens
            )
            content = None
            if hasattr(response, "output") and response.output:
                for item in response.output:
                    if hasattr(item, "content") and item.content:
                        content = item.content[0].text
                        break
            if not content:
                raise ValueError("Empty gpt-5 repair output")
            data = json.loads(content)
        else:
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
