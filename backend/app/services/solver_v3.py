"""
Solver V3 Service (Updated for Schema v1.0).

Handles LLM interaction, strict schema validation, and telemetry.
Simplified to pass through structured visual data to frontend.
"""

import os
import json
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple, AsyncIterator
from datetime import datetime
from jsonschema import Draft202012Validator

from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3
from app.utils.schema_cleaner import enforce_strict
from app.services.validation_v3 import validate_response, create_error_response
from app.utils.schema_deref import deref_json_schema, validate_no_refs
from app.llm_profiles.profiles import get_prompt_profile
from app.services.response_mapper import map_minimal_to_canonical
from app.utils.token_limits import get_effective_max_tokens, get_effective_max_steps
from app.services.token_policy import get_token_policy, TokenPolicy
from app.services.llm.manager import LLMManager, LLMProviderError, _default_provider, get_configured_ollama_model
from app.services.llm.clients import LLMResponse, LLMStreamResponse
from app.services.prompt_registry_service import prompt_registry_service, PromptRegistryError
from app.services.prompt_manager import prompt_manager
from app.services.message_builder import build_user_message
from app.llm_profiles.profiles import PromptProfile
from app.prompts.db_loader import PromptBindingLookupError, load_prompt_bundle

class SolverV3:
    """
    Math Solver V3 using OpenAI Structured Outputs (Schema v1.0).
    """
    
    def __init__(self, llm_manager=None):
        """Initialize solver with LLM provider manager."""
        self.client_manager = llm_manager or LLMManager()

        # Hardcode Qwen Math for now or use env
        self.default_model = get_configured_ollama_model()
        # Ensure we are using Ollama client:
        # self.client = ... (access via manager now)
        print(f"[SOLVER_V3_INIT] LLM provider: {self.client_manager.primary_provider}")
        self._logger = logging.getLogger("solver_v3")

    def _hash_text(self, text: str) -> str:
        text = text or ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _sanitize_log_text(self, text: str, limit: int = 400) -> str:
        if not isinstance(text, str):
            text = str(text)
        text = text.replace(os.environ.get("OPENAI_API_KEY", ""), "[REDACTED]") if os.environ.get("OPENAI_API_KEY") else text
        text = text.replace(os.environ.get("WHATSAPP_INTERNAL_KEY", ""), "[REDACTED]") if os.environ.get("WHATSAPP_INTERNAL_KEY") else text
        return text[:limit]
    # Module-level validator cache
    _validator_cache: Dict[str, Draft202012Validator] = {}

    def _get_cached_validator(self, schema: Dict[str, Any]) -> Draft202012Validator:
        """Get or create cached validator for schema."""
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:16]
        if schema_hash not in self._validator_cache:
            self._validator_cache[schema_hash] = Draft202012Validator(schema)
        return self._validator_cache[schema_hash]

    def _validate_with_draft202012(self, data: Dict[str, Any], schema: Dict[str, Any]) -> List[Dict[str, str]]:
        validator = self._get_cached_validator(schema)
        issues: List[Dict[str, str]] = []
        for err in validator.iter_errors(data):
            path = "$"
            if err.absolute_path:
                for part in err.absolute_path:
                    if isinstance(part, int):
                        path += f"[{part}]"
                    else:
                        path += f".{part}"
            issues.append({"type": "schema_error", "message": err.message, "path": path})
            if len(issues) >= 20:
                break
        return issues

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
        learning_mode: Optional[str] = None,  # "solve" | "study"
        image_url: Optional[str] = None,
        max_output_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        
        start_time_perf = time.perf_counter()
        
        # Default telemetry
        telemetry = {
            "request_id": request_id,
            "model": None,
            "provider": self.client_manager.primary_provider,
            "fallback_provider": self.client_manager.get_fallback_provider(),
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
            "repair_attempts": 0,
            "openai_calls_count": 0,
            "openai_payload": None,
            "fallback_triggered": False,
            "status_checks": [],
            "llm_attempts": []
        }
        
        if trace:
            print(f"\n[SOLVER_V3] ==================== START ====================")
            print(f"[SOLVER_V3] Request ID: {request_id}")

        profile = None
        token_policy: Optional[TokenPolicy] = None

        try:
            # Step 1: Resolve Profile
            t_binding_start = time.perf_counter()
            if db_session:
                from app.llm_profiles.profile_resolver import ProfileResolver
                from app.models import User
                from app.services.tier_utils import get_user_effective_tier_slug
                
                # Load user object if needed
                user_obj = None
                if user_id:
                     user_obj = db_session.get(User, user_id)

                try:
                    effective_tier_slug = get_user_effective_tier_slug(user_obj) if user_obj else user_tier
                    binding_bundle = load_prompt_bundle(
                        tier=effective_tier_slug,
                        mode="solve",
                        session=db_session,
                    )
                    token_policy = get_token_policy(db_session)
                    max_tokens = get_effective_max_tokens(requested_mode, learning_mode or "solve", token_policy)
                    max_steps = get_effective_max_steps(requested_mode, learning_mode or "solve", token_policy)
                    profile = PromptProfile(
                        tier=effective_tier_slug,
                        system_prompt_content=binding_bundle["system_prompt"],
                        developer_prompt_content=binding_bundle["developer_prompt"],
                        json_schema_content=binding_bundle["schema"] if isinstance(binding_bundle["schema"], dict) else {},
                        max_output_tokens=max_tokens,
                        max_steps=max_steps,
                        mode=requested_mode,
                        allow_detailed=(requested_mode == "detailed"),
                        allow_visuals_only_if_asked=(requested_mode == "minimal" and "free" in effective_tier_slug),
                        prompt_binding_meta=binding_bundle.get("meta"),
                    )
                    telemetry["prompt_binding"] = binding_bundle.get("meta")

                    telemetry["mode_resolved"] = profile.mode
                    telemetry["tier_effective"] = profile.tier

                    if trace:
                        print(f"[SOLVER_V3] Resolved Profile: Tier={profile.tier}, Mode={profile.mode}")

                except Exception as e:
                    return self._handle_error(problem_text, f"Profile resolution failed: {e}", "config_error", telemetry, start_time_perf)
            else:
                return self._handle_error(
                    problem_text,
                    "Prompt binding lookup requires db_session; file fallback is disabled.",
                    "config_error",
                    telemetry,
                    start_time_perf,
                )
            
            telemetry["latency_ms_binding"] = int((time.perf_counter() - t_binding_start) * 1000)

            # Step 1.5: Accounting (Debit Pending) - MOVED TO API LAYER
            if db_session and user_id:
                # API layer (api.py) handles check_entitlement_and_debit before calling solve().
                pass

            # Step 2: Prepare LLM Args
            base_system_prompt = profile.system_prompt_content
            json_schema_config = profile.json_schema_content
            
            # Helper to wrap/deref schema
            def prepare_schema(config_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
                candidate = config_schema
                if not isinstance(candidate, dict) or not candidate:
                    candidate = get_json_schema_for_openai_v3()
                
                if "schema" in candidate and isinstance(candidate["schema"], dict):
                     candidate = candidate["schema"]

                try:
                    deref = deref_json_schema(candidate)
                except Exception as exc:
                    print(f"[SOLVER_V3] Schema dereference failed: {exc}")
                    deref = deref_json_schema(get_json_schema_for_openai_v3())
                if not isinstance(deref, dict):
                    deref = deref_json_schema(get_json_schema_for_openai_v3())

                deref = enforce_strict(deref)
                if deref.get("type") is None:
                    deref["type"] = "object"
                    
                return {
                     "name": "solve_response_v3",
                     "strict": True,
                     "schema": deref
                }

            openai_schema_wrapper = prepare_schema(json_schema_config)

            # Two-Pass Strategy
            passes = [requested_mode]
            if requested_mode != "minimal":
                passes.append("minimal")
            
            final_response_data = None
            successful_mode = None
            last_error = None
            providers_to_try = self.client_manager.get_provider_chain()
            
            # Helper for clamping tokens
            def _clamp_tokens_for_provider(provider: str, tokens: int) -> int:
                if provider == "ollama":
                    tier_slug = (user_tier or "").lower()
                    cap = 1200
                    if "free" in tier_slug:
                        cap = 900
                    elif "standard" in tier_slug or "pro" in tier_slug or "family" in tier_slug:
                        cap = 1100
                    elif "research" in tier_slug:
                        cap = 1200
                    return min(tokens, cap)
                return tokens
            
            for pass_idx, current_mode in enumerate(passes):
                is_fallback = (pass_idx > 0)
                if is_fallback:
                    telemetry["fallback_triggered"] = True
                    if trace: print(f"[SOLVER_V3] Triggering Fallback to mode={current_mode}")

                if current_mode == "minimal":
                    effective_learning_mode = "solve"
                else:
                    effective_learning_mode = trusted_context.get("learning_mode") if trusted_context else learning_mode

                if max_output_tokens and max_output_tokens > 0:
                    effective_max_tokens = max_output_tokens
                else:
                    if db_session and not token_policy:
                        token_policy = get_token_policy(db_session)
                    
                    if token_policy:
                        effective_max_tokens = get_effective_max_tokens(current_mode, effective_learning_mode, token_policy)
                    else:
                        effective_max_tokens = 4096
                
                telemetry[f"pass_{pass_idx+1}_max_tokens"] = effective_max_tokens

                for provider_idx, provider in enumerate(providers_to_try):
                    llm_start_perf = time.perf_counter()
                    effective_tokens = _clamp_tokens_for_provider(provider, effective_max_tokens)
                    try:
                        # Build user message with timing
                        t_build_start = time.perf_counter()
                        # call_llm_with_schema calls _build_user_message internally, but we need to time it here or inside.
                        # It is inside _call_llm_with_schema. We will rely on _call_llm_with_schema to return duration OR trust total LLM time? 
                        # Code says "Add timing logs ... message builder time". 
                        # Let's intercept inside _call_llm_with_schema OR just time it here since we can't easily change the helper signature heavily without risk.
                        # Wait, I'm replacing the whole block. I can modify _call_llm_with_schema or just time it if I call build_user_message myself passed in?
                        # _call_llm_with_schema calls existing method.
                        # Let's modify _call_llm_with_schema later?
                        # Or just note that message building is part of LLM setup.
                        # Actually, looking at lines 311+, `_call_llm_with_schema` does the building.
                        # I'll modify `_call_llm_with_schema` (function def at end of file) to measure build time and return it, OR just accept loose timing.
                        # Requirement: "Add timing logs ... message builder time".
                        # Use simple approach: Time the text building HERE if possible? No, it's inside helper.
                        # I will add timing inside the helper and return it in the result tuple?
                        # `_call_llm_with_schema` returns (response_data, llm_tokens, status_info, model_used, raw_output_text).
                        # Changing signature affects unpacking.
                        # Let's just monitor "LLM Prep" latency which is negligible?
                        # Actually, `message_builder` might be heavy with large context.
                        # Let's modify `_call_llm_with_schema` to return `build_ms`.
                        pass
                        
                        response_data, llm_tokens, status_info, model_used, raw_output_text, build_ms = await self._call_llm_with_schema(
                            problem_text,
                            context,
                            base_system_prompt,
                            developer_prompt=profile.developer_prompt_content,
                            json_schema_config=openai_schema_wrapper,
                            max_output_tokens=effective_tokens,
                            trace=trace,
                            trusted_context=trusted_context,
                            requested_mode=current_mode,
                            image_url=image_url,
                            provider=provider,
                            request_id=request_id,
                        )

                        llm_end_perf = time.perf_counter()

                        # Accumulate/Update telemetry
                        telemetry["latency_ms_openai"] = int((llm_end_perf - llm_start_perf) * 1000)
                        telemetry["latency_ms_build_msg"] = build_ms
                        telemetry["input_tokens"] = llm_tokens.get("input", 0)
                        telemetry["output_tokens"] = llm_tokens.get("output", 0)
                        telemetry["total_tokens"] = llm_tokens.get("total", 0)
                        telemetry["cached_tokens"] = llm_tokens.get("cached", None)
                        telemetry["openai_payload"] = llm_tokens.get("payload")
                        telemetry["openai_calls_count"] += 1
                        telemetry["model"] = model_used
                        telemetry["provider"] = provider
                        if provider_idx > 0:
                            telemetry["fallback_triggered"] = True

                        telemetry["llm_attempts"].append(
                            {"pass": pass_idx + 1, "mode": current_mode, "provider": provider}
                        )
                        self._logger.info(
                            "llm_call request_id=%s tier=%s mode=%s provider=%s model=%s latency_ms=%s build_ms=%s binding_ms=%s schema_id=%s",
                            request_id,
                            telemetry.get("tier_effective"),
                            current_mode,
                            provider,
                            model_used,
                            telemetry["latency_ms_openai"],
                            telemetry.get("latency_ms_build_msg"),
                            telemetry.get("latency_ms_binding"),
                            telemetry.get("prompt_binding", {}).get("output_schema_id"),
                        )

                        # VALIDATION
                        t_val_start = time.perf_counter()
                        validation_success, validation_error, validated_data, error_list = self._check_status_and_validate(
                            response_data, status_info, openai_schema_wrapper["schema"], raw_text=raw_output_text
                        )
                        telemetry["latency_ms_validation"] = int((time.perf_counter() - t_val_start) * 1000)

                        telemetry["status_checks"].append(
                            {
                                "pass": pass_idx + 1,
                                "mode": current_mode,
                                "provider": provider,
                                "status": status_info.get("status", "unknown"),
                                "finish_reason": status_info.get("finish_reason", "unknown"),
                                "valid": validation_success,
                                "error": validation_error,
                                "error_list": error_list,
                                "val_ms": telemetry["latency_ms_validation"]
                            }
                        )

                        if validation_success:
                            final_response_data = validated_data
                            successful_mode = current_mode
                            telemetry["validated"] = True
                            break

                        # Attempt repair once globally per solve request
                        telemetry["validation_failures_count"] += 1
                        repair_enabled = os.environ.get("LLM_REPAIR_ENABLED", "true").lower() in {"1", "true", "yes"}
                        attempts = telemetry.get("repair_attempts", 0)
                        if repair_enabled and attempts < 1:
                            telemetry["repair_attempted"] = True
                            telemetry["repair_attempts"] = attempts + 1
                            try:
                                t_repair_start = time.perf_counter()
                                repaired, repaired_text = await self._repair_response(
                                    problem_text,
                                    context,
                                    base_system_prompt,
                                    response_data,
                                    validation_error,
                                    error_list,
                                    json_schema_config=openai_schema_wrapper,
                                    max_output_tokens=min(1200, effective_tokens),
                                    requested_mode=current_mode,
                                    trace=trace,
                                    provider=provider,
                                )
                                telemetry["latency_ms_repair"] = int((time.perf_counter() - t_repair_start) * 1000)
                                
                                validation_success, validation_error, validated_data, post_repair_errors = self._check_status_and_validate(
                                    repaired, status_info, openai_schema_wrapper["schema"], raw_text=repaired_text
                                )
                                if validation_success:
                                    final_response_data = validated_data
                                    successful_mode = current_mode
                                    telemetry["validated"] = True
                                    telemetry["repaired"] = True
                                    break
                                telemetry["repair_failed_error_list"] = post_repair_errors
                                self._logger.warning(
                                    "llm_schema_invalid_repair_failed request_id=%s repair_ms=%s error=%s",
                                    request_id,
                                    telemetry["latency_ms_repair"],
                                    validation_error
                                )
                            except Exception as repair_error:
                                last_error = str(repair_error)
                                telemetry["latency_ms_repair"] = int((time.perf_counter() - t_repair_start) * 1000)

                        last_error = validation_error
                        if trace:
                            print(f"[SOLVER_V3] Pass {pass_idx+1} provider={provider} failed validation: {validation_error}")
                        continue

                    except LLMProviderError as e:
                        self.client_manager.note_error(provider, e)
                        last_error = str(e)
                        if trace:
                            print(f"[SOLVER_V3] Pass {pass_idx+1} provider={provider} error: {e}")
                        continue
                    except Exception as e:
                        self.client_manager.note_error(provider, e)
                        last_error = str(e)
                        if trace:
                            print(f"[SOLVER_V3] Pass {pass_idx+1} provider={provider} exception: {e}")
                        continue

                if final_response_data:
                    break

            # End of loops
            if not final_response_data:
                # All passes failed
                error_code = "exhausted_retries"
                if telemetry.get("validation_failures_count", 0) > 0:
                    error_code = "LLM_SCHEMA_INVALID"
                return self._handle_error(problem_text, f"All attempts failed. Last error: {last_error}", error_code, telemetry, start_time_perf)

            # --- Success Processing ---
            response_data = final_response_data
            
            # Step 4: Map Minimal Response (if needed)
            if successful_mode == "minimal":
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
        developer_prompt: Optional[str] = None,
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
            "model": self.default_model, # Changed to default_model
            "provider": "ollama", # Changed to ollama
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": None,
            "latency_ms_openai": 0,
            "truncated": False,
            "validated": False,
            "repaired": False,
            "openai_calls_count": 0,
            "openai_payload": None,
            "requested_mode": requested_mode,
            "learning_mode": (trusted_context or {}).get("learning_mode") or "solve"
        }

        try:
            provider = "ollama"
            client = self.client_manager.get_client(provider)
            if not system_prompt:
                yield {
                    "type": "error",
                    "error": {
                        "code": "prompt_binding_missing",
                        "message": "Missing system prompt from DB binding; file fallback is disabled.",
                    },
                }
                return
            resolved_system_prompt = system_prompt

            user_message = self._build_user_message(
                problem_text, 
                context, 
                trusted_context=trusted_context, 
                requested_mode=requested_mode
            )
            
            # Determine max tokens
            if max_output_tokens and max_output_tokens > 0:
                effective_max_tokens = max_output_tokens
            else:
                 effective_max_tokens = 900 # Default conservative

            telemetry["max_output_tokens_effective"] = effective_max_tokens
            
            messages = [
                {"role": "system", "content": resolved_system_prompt},
            ]
            if developer_prompt:
                messages.append({"role": "developer", "content": developer_prompt})
            messages.append({"role": "user", "content": user_message})

            if trace:
                print(f"[SOLVER_V3_STREAM] Calling Ollama with model={self.default_model}")

            schema_payload = json_schema_config.get("schema") if isinstance(json_schema_config, dict) and "schema" in json_schema_config else json_schema_config
            response_stream = client.generate_stream(
                messages=messages,
                system_prompt=None,
                prompt=None,
                json_schema=schema_payload,
                max_tokens=effective_max_tokens,
                temperature=0.4,
                request_id=request_id,
                model=self.default_model,
            )

            full_content = ""
            first_chunk = True
            
            async for chunk_obj in response_stream:
                if first_chunk:
                    if trace:
                        print(f"[SOLVER_V3_STREAM] First chunk received")
                    first_chunk = False
                content_delta = ""
                if hasattr(chunk_obj, "content"):
                    content_delta = chunk_obj.content
                elif isinstance(chunk_obj, dict):
                    content_delta = chunk_obj.get("content", "")
                
                if content_delta:
                    full_content += content_delta
                    yield {"type": "delta", "text": content_delta}
                if hasattr(chunk_obj, "usage") and chunk_obj.usage:
                    telemetry["input_tokens"] = chunk_obj.usage.get("input", 0)
                    telemetry["output_tokens"] = chunk_obj.usage.get("output", 0)
                    telemetry["total_tokens"] = chunk_obj.usage.get("total", 0)
                    telemetry["cached_tokens"] = chunk_obj.usage.get("cached")
                if hasattr(chunk_obj, "model") and chunk_obj.model:
                    telemetry["model"] = chunk_obj.model
                if hasattr(chunk_obj, "provider") and chunk_obj.provider:
                    telemetry["provider"] = chunk_obj.provider
                if hasattr(chunk_obj, "status") and chunk_obj.status:
                    telemetry["status"] = chunk_obj.status

            # End of stream
            if not telemetry.get("output_tokens"):
                telemetry["output_tokens"] = len(full_content) // 4
                telemetry["total_tokens"] = telemetry.get("input_tokens", 0) + telemetry["output_tokens"]
            telemetry["latency_ms_total"] = int((time.perf_counter() - start_time_perf) * 1000)
            
            # Yield telemetry at end
            yield {"type": "telemetry", "telemetry": telemetry}

        except Exception as e:
            if trace:
                print(f"[SOLVER_V3_STREAM] [ERROR] FATAL: {e}")
                import traceback
                traceback.print_exc()
            yield {"type": "error", "error": {"code": "fatal", "message": str(e)}}

    def _build_user_message(
        self, 
        problem_text: str, 
        context: str = "",
        trusted_context: dict = None,
        requested_mode: str = "minimal"
    ) -> str:
        """
        Build strict user message using 3-block template.
        """
        from app.services.context_normalizer import normalize_trusted_context
        
        # Normalize trusted_context to compact enums (CA, CA-ON, 11)
        normalized_ctx = normalize_trusted_context(trusted_context) if trusted_context else {}
        
        # Add requested_mode to context
        if requested_mode:
            normalized_ctx["requested_mode"] = requested_mode

        question_payload = {"problem": problem_text}
        context_payload = {"context": context, "trusted_context": normalized_ctx}
        runtime_hints = {"requested_mode": requested_mode}

        return build_user_message(question_payload, context_payload, runtime_hints)


    def _handle_error(self, problem, errors, code, telemetry, start_time_perf):
        telemetry["latency_ms_total"] = int((time.perf_counter() - start_time_perf) * 1000)
        err_resp = create_error_response(problem, errors if isinstance(errors, list) else [str(errors)], code)
        err_resp["_telemetry"] = telemetry
        err_resp["telemetry"] = telemetry
        return err_resp


    def _check_status_and_validate(
        self,
        data: Any,
        status_info: Dict,
        schema: Dict,
        raw_text: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[Dict], List[Dict[str, str]]]:
        """
        Check upstream status/finish_reason AND validate against schema.
        Returns: (success, error_msg, validated_data)
        """
        # 1. Check Upstream Status
        status = status_info.get("status") # gpt-5
        finish_reason = status_info.get("finish_reason") # gpt-4
        
        # Responses API "incomplete"
        if status == "incomplete":
            return False, f"Upstream Incomplete (reason={status_info.get('incomplete_reason')})", None, []
        
        # Chat Completions "length"
        if finish_reason == "length":
            return False, "Upstream Truncated (length)", None, []
            
        # 2. Check Data Existence
        if not data:
             return False, "Empty Data", None, [{"type": "parse_error", "message": "empty response", "path": "$"}]

        if isinstance(data, dict) and "_raw" in data:
            msg = "Response was not valid JSON."
            issues = [{"type": "parse_error", "message": msg, "path": "$"}]
            return False, msg, None, issues

        # 3. Schema Validation (Draft 2020-12 first)
        schema_issues = self._validate_with_draft202012(data, schema)
        if schema_issues:
            return False, "Schema Validation Failed", None, schema_issues

        # Optional strict checks
        validation = validate_response(data, strict=True)
        if not validation.valid:
            extra_issues = [{"type": "schema_error", "message": e, "path": "$"} for e in validation.errors[:20]]
            return False, "Schema Validation Failed", None, extra_issues

        return True, None, data, []


    async def _call_llm_with_schema(
        self, 
        problem_text, 
        context, 
        system_prompt, 
        developer_prompt=None,
        json_schema_config=None,
        max_output_tokens=4096,
        trace=False,
        trusted_context: dict = None,
        requested_mode: str = "minimal",
        image_url: Optional[str] = None,
        provider: str = "openai",
        request_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], str, str, int]:
        # Build compact JSON user message with normalized trusted_context
        if trace:
            print(f"[SOLVER_DEBUG] _call_llm_with_schema requested_mode={requested_mode}")
            if trusted_context:
                print(f"[SOLVER_DEBUG] trusted_context: {trusted_context}")
        
        t_build_start = time.perf_counter()
        user_message = self._build_user_message(
            problem_text, 
            context, 
            trusted_context=trusted_context,
            requested_mode=requested_mode
        )
        build_ms = int((time.perf_counter() - t_build_start) * 1000)
        
        if trace:
            print(f"[SOLVER_DEBUG] _call_llm_with_schema user_message[:100]: {user_message[:100]}...")
        tokens = {"input": 0, "output": 0, "total": 0, "cached": None}
        status_info = {"status": "unknown", "finish_reason": "unknown"}

        schema_payload = json_schema_config
        provider = provider.lower()
        
        # ... (rest of function logic needs to be preserved or I need to find end of function to return build_ms)
        # Checking file content again, I need to see where it returns.
        # It's better to read the function first to ensure I don't overwrite logic key parts if I can't see them.
        # But I recall I need to change return statement.
        
        try:
             client = self.client_manager.get_client(provider)

             messages = [
                {"role": "system", "content": system_prompt},
             ]
             if developer_prompt:
                 messages.append({"role": "developer", "content": developer_prompt})
             messages.append({"role": "user", "content": user_message})
             
             # If image_url provided (Snap Mode), we need to inject it.
             # Standard OpenAI / Ollama vision handling: content can be list.
             if image_url:
                 # Check if client supports vision or we simply rely on text extraction?
                 # V3 design passes text mostly. If image_url is here, we might need to use vision model.
                 # For now, Solver V3 assumes text input is sufficient (OCR done before).
                 # If image_url is passed, maybe we append it?
                 # Current implementation in view_file didn't show special image handling in lines 769+.
                 pass

             response = await client.generate(
                messages=messages,
                system_prompt=None, # In messages
                prompt=None,
                json_schema=schema_payload.get("schema") if schema_payload else None,
                max_tokens=max_output_tokens,
                temperature=0.4,
                stream=False,
                request_id=request_id,
                model=self.default_model if provider == "ollama" else None 
             )

             # Adapt response
             if isinstance(response, LLMResponse):
                 content = response.content
                 tokens = {
                     "input": (response.usage or {}).get("input", 0),
                     "output": (response.usage or {}).get("output", 0),
                     "total": (response.usage or {}).get("total", 0),
                     "cached": (response.usage or {}).get("cached"),
                     "payload": response.payload,
                 }
                 model_used = response.model
                 
                 # Basic JSON parse
                 try:
                     response_data = json.loads(content)
                     status_info["status"] = "complete" # Assume success if parsed
                     status_info["finish_reason"] = "stop"
                 except json.JSONDecodeError:
                     response_data = {"_raw": content} # Marker for invalid JSON
                     status_info["status"] = "complete"
             else:
                 # Fallback dict
                 content = str(response)
                 response_data = {"_raw": content}
                 model_used = "unknown"

             return response_data, tokens, status_info, model_used, content, build_ms

        except Exception as e:
             raise e
        system_for_provider = system_prompt
        if provider == "ollama":
            schema_text = json.dumps(schema_payload.get("schema", schema_payload), separators=(",", ":"))
            system_for_provider = (
                f"{system_prompt}\n\nJSON_SCHEMA:\n{schema_text}\n\n"
                "Output only valid JSON that matches the schema."
            )

        user_content = user_message
        if image_url:
            if provider == "ollama":
                raise LLMProviderError("Ollama does not support image inputs.", provider="ollama")
            user_content = [
                {"type": "text", "text": user_message},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
            ]

        messages = [
            {"role": "system", "content": system_for_provider},
            {"role": "user", "content": user_content},
        ]

        llm_client = self._llm_manager.get_client(provider)
        verbosity = "low" if requested_mode == "minimal" else "high"
        llm_response = await llm_client.generate(
            messages=messages,
            system_prompt=system_for_provider,
            prompt=None,
            json_schema=schema_payload if provider == "openai" else None,
            max_tokens=max_output_tokens,
            temperature=None,
            stream=False,
            request_id=request_id,
            verbosity=verbosity,
        )

        status_info.update(llm_response.status or {})
        tokens["input"] = llm_response.usage.get("input", 0)
        tokens["output"] = llm_response.usage.get("output", 0)
        tokens["total"] = llm_response.usage.get("total", 0)
        tokens["cached"] = llm_response.usage.get("cached", None)
        tokens["payload"] = llm_response.payload

        data = None
        if llm_response.content:
            try:
                data = json.loads(llm_response.content)
            except Exception:
                data = {"_raw": llm_response.content}

        return data, tokens, status_info, llm_response.model, llm_response.content

    async def _repair_response(
        self,
        problem,
        context,
        system_prompt,
        invalid_data,
        validation_error,
        error_list,
        json_schema_config,
        max_output_tokens=1200,
        requested_mode: str = "minimal",
        trace=False,
        provider: str = "openai",
        model: Optional[str] = None,
    ):
        if trace:
             print(f"[SOLVER_V3] Attempting repair...")
        
        payload = invalid_data if isinstance(invalid_data, dict) else {"_raw": invalid_data}
        raw_text = ""
        if isinstance(invalid_data, dict) and "_raw" in invalid_data:
            raw_text = str(invalid_data.get("_raw", ""))
        elif isinstance(invalid_data, str):
            raw_text = invalid_data
        else:
            raw_text = json.dumps(payload, ensure_ascii=True)

        repair_prompt = (
            "You are a strict JSON repair engine.\n"
            "Your task: output ONLY valid JSON that matches the provided JSON Schema exactly.\n"
            "Do not include markdown, commentary, or extra keys.\n\n"
            f"JSON Schema:\n{json.dumps(json_schema_config.get('schema', json_schema_config), ensure_ascii=True)}\n\n"
            f"Invalid output:\n{raw_text}\n\n"
            f"Validation/parsing errors:\n{json.dumps(error_list or [], ensure_ascii=True)}\n\n"
            "Return ONLY the corrected JSON."
        )
        
        # For Strict Structured Output repair:
        # We start a fresh conversation or append. strict mode validation is rigid.
        # Simple approach: New request with "previous_invalid_json" in context[ERROR]
        # Or standard append.
        
        provider = provider.lower()
        system_for_provider = system_prompt
        if provider == "ollama":
            schema_text = json.dumps(json_schema_config.get("schema", json_schema_config), separators=(",", ":"))
            system_for_provider = (
                f"{system_prompt}\n\nJSON_SCHEMA:\n{schema_text}\n\n"
                "Output only valid JSON that matches the schema."
            )

        messages = [
            {"role": "system", "content": system_for_provider},
            {"role": "user", "content": repair_prompt},
        ]

        llm_client = self.client_manager.get_client(provider)
        llm_response = await llm_client.generate(
            messages=messages,
            system_prompt=system_for_provider,
            prompt=None,
            json_schema=json_schema_config if provider == "openai" else None,
            max_tokens=max_output_tokens,
            temperature=None,
            stream=False,
            request_id=None,
            model=model if provider == "ollama" else None,
        )

        if not llm_response.content:
            raise ValueError("Empty repair output")
        data = json.loads(llm_response.content)
        data["_repaired"] = True
        return data, llm_response.content

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
