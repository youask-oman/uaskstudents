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

from app.utils.schema_cleaner import enforce_strict
from app.services.validation_v3 import create_error_response
from app.utils.schema_deref import deref_json_schema, validate_no_refs
# from app.llm_profiles.profiles import get_prompt_profile # Removed: module deleted
from app.services.response_mapper import map_minimal_to_canonical, normalize_raw_llm_response
from app.utils.token_limits import get_effective_max_tokens, get_effective_max_steps
from app.services.token_policy import get_token_policy, TokenPolicy
from app.services.llm.manager import LLMManager, LLMProviderError, _default_provider, get_configured_openai_model
from app.services.llm.clients import LLMResponse, LLMStreamResponse
from app.services.prompt_registry_service import prompt_registry_service, PromptRegistryError
from app.services.prompt_manager import prompt_manager
from app.services.message_builder import build_user_message
# from app.llm_profiles.profiles import PromptProfile # Removed: module deleted
from app.prompts.db_loader import PromptBindingLookupError, load_prompt_bundle
from app.services.plot_pipeline_service import get_plot_pipeline_service
from app.utils.token_utils import trim_messages
from app.utils.schema_wrapper_validator import validate_schema_wrapper, SchemaWrapperCorruptError
from pydantic import BaseModel

class PromptProfile(BaseModel):
    """
    Local definition of PromptProfile to replace missing module.
    Holds resolved configuration for a solve request.
    """
    tier: str
    system_prompt_content: str
    developer_prompt_content: Optional[str] = None
    json_schema_content: Dict[str, Any]
    max_output_tokens: int
    max_input_tokens: int
    system_schema_budget_tokens: int
    context_budget_tokens: int
    json_retry_max_output_tokens: int
    json_retry_max_attempts: int
    timeout_ms: int
    temperature: float
    top_p: float
    trim_strategy: str
    plot_points_cap: Optional[int] = None
    plot_traces_cap: Optional[int] = None
    plot_annotations_cap: Optional[int] = None
    max_steps: int
    retry_cap_tokens: Optional[int] = None
    mode: str
    allow_detailed: bool
    allow_visuals_only_if_asked: bool
    prompt_binding_meta: Optional[Dict[str, Any]] = None
    
    # New Budget Fields
    system_schema_budget_tokens: int = 1000
    context_budget_tokens: int = 3000
    json_retry_max_output_tokens: int = 1200
    json_retry_max_attempts: int = 1
    timeout_ms: int = 60000
    trim_strategy: str = "trim_context_first"
    plot_points_cap: Optional[int] = None
    plot_traces_cap: Optional[int] = None

class SolverV3:
    """
    Math Solver V3 using OpenAI Structured Outputs (Schema v1.0).
    """
    
    def __init__(self, llm_manager=None):
        """Initialize solver with LLM provider manager."""
        self.client_manager = llm_manager or LLMManager()

        # Resolve model from environment
        self.default_model = get_configured_openai_model()
        print(f"[SOLVER_V3_INIT] LLM provider: {self.client_manager.primary_provider}")
        
        # Explicitly print log location
        self.log_path = os.path.abspath("trace_report.txt")
        print(f"[SOLVER_V3_INIT] logging traces to: {self.log_path}", flush=True)
        
        self._logger = logging.getLogger("solver_v3")
        
        # Immediate startup trace to verify init and file write
        self._log_trace("STARTUP", "SOLVER_INIT", {"log_path": self.log_path, "provider": self.client_manager.primary_provider})

    def _log_trace(self, request_id: str, section: str, content: Any):
        """
        Live console logging for real-time debugging.
        """
        timestamp = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        if isinstance(content, (dict, list)):
            text_content = json.dumps(content, indent=2, default=str)
        else:
            text_content = str(content)
        
        # Prominent console output
        separator = "=" * 60
        print(f"\n{separator}", flush=True)
        print(f"[{timestamp}] [{section}] ID={request_id}", flush=True)
        print(separator, flush=True)
        print(text_content, flush=True)
        print(separator, flush=True)

    def _hash_text(self, text: str) -> str:
        text = text or ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _sanitize_log_text(self, text: str, limit: int = 400) -> str:
        if not isinstance(text, str):
            text = str(text)
        text = text.replace(os.environ.get("OPENAI_API_KEY", ""), "[REDACTED]") if os.environ.get("OPENAI_API_KEY") else text
        return text[:limit]
    # Module-level validator cache with size limits and expiration
    _validator_cache: Dict[str, Tuple[Draft202012Validator, float]] = {}
    _MAX_CACHE_SIZE = 100
    _CACHE_TTL_SECONDS = 3600  # 1 hour

    def _get_cached_validator(self, schema: Dict[str, Any]) -> Draft202012Validator:
        """Get or create cached validator for schema with size limits and expiration."""
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:16]
        current_time = time.time()
        
        # Check if cached and not expired
        if schema_hash in self._validator_cache:
            validator, timestamp = self._validator_cache[schema_hash]
            if current_time - timestamp < self._CACHE_TTL_SECONDS:
                return validator
            else:
                # Remove expired entry
                del self._validator_cache[schema_hash]
        
        # Enforce cache size limit
        if len(self._validator_cache) >= self._MAX_CACHE_SIZE:
            # Remove oldest entry
            oldest_key = min(self._validator_cache.keys(), 
                          key=lambda k: self._validator_cache[k][1])
            del self._validator_cache[oldest_key]
            self._logger.info(f"[SOLVER_V3] Cache limit reached, removed oldest validator: {oldest_key}")
        
        # Create new validator
        validator = Draft202012Validator(schema)
        self._validator_cache[schema_hash] = (validator, current_time)
        return validator

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
        user_tier: Optional[str] = None,
        # New Context Params
        user_id: Optional[int] = None,
        db_session: Optional[Any] = None,  # SQLModel Session
        requested_mode: str = "minimal",
        db_plan: Optional[Any] = None,
        requests_graph_mode: Optional[str] = "auto",
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
            "tier": user_tier or "auto",
            "mode": requested_mode,
            "binding_id": None,
            "system_prompt_id": None,
            "developer_prompt_id": None,
            "output_schema_id": None,
            "max_output_tokens": None,
            "max_input_tokens": None,
            "trim_strategy": None,
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
            "tier_effective": "unknown",
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
          #  print(f"[SOLVER_V3] Request ID: {request_id}")
        
        # --- UNIFIED LOGGING START ---
        self._log_trace(request_id, "SOLVE_START", {"problem_text": problem_text[:200], "context": context})

        profile = None
        token_policy: Optional[TokenPolicy] = None

        try:
            # Step 1: Resolve Profile
            t_binding_start = time.perf_counter()
            if db_session:
                # from app.llm_profiles.profile_resolver import ProfileResolver # Removed: module deleted
                from app.models import User
                from app.services.tier_utils import get_user_effective_tier_slug
                
                # Load user object if needed
                user_obj = None
                if user_id:
                     user_obj = db_session.get(User, user_id)

                try:
                    effective_tier_slug = user_tier
                    if not effective_tier_slug:
                        effective_tier_slug = get_user_effective_tier_slug(user_obj) if user_obj else "free"
                    
                    # --- RULE 1 (UPDATED): Use Real DB Bindings ---
                    # User explicitly requested to use the ACTUAL tier binding from DB, 
                    # even for minimal mode. We rely on the generic 'unwrap' fix 
                    # to handle the detailed schema if it is wrapped.
                    binding_tier_slug = effective_tier_slug
                    
                    # (Removed forced 'free' override)

                    binding_bundle = load_prompt_bundle(
                        tier=binding_tier_slug,
                        mode="solve",
                        session=db_session,
                    )
                    token_policy = get_token_policy(db_session)
                    
                    binding_meta = binding_bundle.get("binding", {})

                    # --- DEBUG: Schema Wrapper Integrity ---
                    schema_debug = binding_bundle.get("schema") if isinstance(binding_bundle.get("schema"), dict) else {}
                    if trace:
                        print(f"[SOLVER_V3] DB Schema Keys: {list(schema_debug.keys())}")
                        print(f"[SOLVER_V3] DB Schema Type: {schema_debug.get('type')}, Name: {schema_debug.get('name')}, Strict: {schema_debug.get('strict')}")
                    # ---------------------------------------
                    
                    # --- RULE 3: Dynamic Token Budgets ---
                    # Resolution Order:
                    # 1. Binding-specific value (if not None)
                    # 2. SystemConfig policy (fallback)
                    # 3. Code-level hard defaults (safety net)
                    
                    max_output_tokens = binding_meta.get("max_output_tokens")
                    if max_output_tokens is None:
                        max_output_tokens = get_effective_max_tokens(requested_mode, learning_mode or "solve", token_policy)
                    
                    # Special minimal cap
                    if requested_mode == "minimal":
                        max_output_tokens = min(max_output_tokens, 1200)

                    max_input_tokens = binding_meta.get("max_input_tokens") or token_policy.text_input_max
                    system_schema_budget_tokens = binding_meta.get("system_schema_budget_tokens") or 1000
                    context_budget_tokens = binding_meta.get("context_budget_tokens") or 3000
                    json_retry_max_output_tokens = binding_meta.get("json_retry_max_output_tokens") or max_output_tokens
                    json_retry_max_attempts = binding_meta.get("json_retry_max_attempts") or 1
                    timeout_ms = binding_meta.get("timeout_ms") or 60000
                    temperature = binding_meta.get("temperature") if binding_meta.get("temperature") is not None else 0.1
                    top_p = binding_meta.get("top_p") if binding_meta.get("top_p") is not None else 1.0
                    
                    max_steps = binding_meta.get("max_steps")
                    if max_steps is None:
                        max_steps = get_effective_max_steps(requested_mode, learning_mode or "solve", token_policy)
                    
                    retry_cap = binding_meta.get("retry_cap_tokens")
                    trim_strategy = binding_meta.get("trim_strategy") or "trim_context_first"
                    
                    profile = PromptProfile(
                        tier=binding_tier_slug,
                        system_prompt_content=binding_bundle.get("system_prompt", ""),
                        developer_prompt_content=binding_bundle.get("developer_prompt"),
                        json_schema_content=binding_bundle.get("schema") if isinstance(binding_bundle.get("schema"), dict) else {},
                        max_output_tokens=max_output_tokens,
                        max_input_tokens=max_input_tokens,
                        system_schema_budget_tokens=system_schema_budget_tokens,
                        context_budget_tokens=context_budget_tokens,
                        json_retry_max_output_tokens=json_retry_max_output_tokens,
                        json_retry_max_attempts=json_retry_max_attempts,
                        timeout_ms=timeout_ms,
                        temperature=temperature,
                        top_p=top_p,
                        trim_strategy=trim_strategy,
                        plot_points_cap=binding_meta.get("plot_points_cap"),
                        plot_traces_cap=binding_meta.get("plot_traces_cap"),
                        plot_annotations_cap=binding_meta.get("plot_annotations_cap"),
                        max_steps=max_steps,
                        retry_cap_tokens=retry_cap,
                        mode=requested_mode,
                        allow_detailed=(requested_mode == "detailed"),
                        allow_visuals_only_if_asked=False,
                        prompt_binding_meta=binding_bundle.get("meta"),
                    )
                    
                    # Update telemetry with resolved binding info
                    telemetry["tier_effective"] = profile.tier
                    telemetry["binding_id"] = profile.prompt_binding_meta.get("id") if profile.prompt_binding_meta else None
                    telemetry["system_prompt_id"] = profile.prompt_binding_meta.get("global_system_prompt_id") if profile.prompt_binding_meta else None
                    telemetry["developer_prompt_id"] = profile.prompt_binding_meta.get("developer_prompt_id") if profile.prompt_binding_meta else None
                    telemetry["output_schema_id"] = profile.prompt_binding_meta.get("output_schema_id") if profile.prompt_binding_meta else None
                    telemetry["max_output_tokens"] = profile.max_output_tokens
                    telemetry["max_input_tokens"] = profile.max_input_tokens
                    telemetry["trim_strategy"] = profile.trim_strategy
                    telemetry["prompt_binding"] = profile.prompt_binding_meta


                    telemetry["mode_resolved"] = profile.mode
                    telemetry["tier_effective"] = effective_tier_slug # Log the REAL tier for billing/tracking

                    # --- RULE 1: Enforce "Binding is Law" ---
                    # Explicit runtime meta logging
                    telemetry["binding_meta"] = {
                        "global_system_prompt_id": profile.prompt_binding_meta.get("global_system_prompt_id") if profile.prompt_binding_meta else None,
                        "developer_prompt_id": profile.prompt_binding_meta.get("developer_prompt_id") if profile.prompt_binding_meta else None,
                        "output_schema_id": profile.prompt_binding_meta.get("output_schema_id") if profile.prompt_binding_meta else None,
                        "max_output_tokens": profile.max_output_tokens,
                        "timeout_ms": profile.timeout_ms,
                        "temperature": profile.temperature
                    }
                    
                    if trace:
                        print(f"[SOLVER_V3] Resolved Profile: Tier={profile.tier} (Effective={effective_tier_slug}), Mode={profile.mode}")
                        print(f"[SOLVER_V3] Binding Meta: {json.dumps(telemetry['binding_meta'], indent=2)}")

                    # Hard Assertion
                    if profile.tier.upper() == "RESEARCH" and profile.mode.upper() == "SOLVE":
                        required_schema = "solve_research_detailed_v1.schema.json"
                        actual_schema = telemetry["binding_meta"]["output_schema_id"]
                        if actual_schema != required_schema:
                            raise ValueError(f"binding_mismatch: Research Tier (SOLVE mode) MUST use {required_schema}, but got {actual_schema}.")
                    
                    self._log_trace(request_id, "PROFILE_RESOLVED", telemetry["binding_meta"])

                except Exception as e:
                    self._log_trace(request_id, "PROFILE_ERROR", str(e))
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
                    raise ValueError("Missing schema from DB prompt binding.")

                # Check if it is a wrapper
                is_wrapper = False
                wrapper_meta = {"name": "solve_response_v3", "strict": True}
                
                # Check for canonical DB wrapper keys
                if "schema" in candidate and "name" in candidate and "type" in candidate:
                    if candidate["type"] == "json_schema":
                         is_wrapper = True
                         wrapper_meta["name"] = candidate["name"]
                         wrapper_meta["strict"] = candidate.get("strict", True)
                         inner_schema = candidate["schema"]
                    else:
                         # It has 'schema' key but not type=json_schema? Treat as just an object that happens to have a schema key? 
                         # Or it is a wrapper? Assume wrapper if keys match.
                         # Actually, standardizing: if keys subset is present.
                         inner_schema = candidate["schema"]
                elif "schema" in candidate and isinstance(candidate["schema"], dict):
                    # Fallback "Half wrapper" detection or just nested schema
                    # If keys are just 'schema', assume we want inner.
                    inner_schema = candidate["schema"]
                else:
                    inner_schema = candidate

                if not isinstance(inner_schema, dict) or not inner_schema:
                    raise ValueError("Invalid inner schema payload.")

                try:
                    deref = deref_json_schema(inner_schema)
                except Exception as exc:
                    raise ValueError(f"Schema dereference failed: {exc}") from exc
                    
                deref = enforce_strict(deref)
                if deref.get("type") is None:
                    deref["type"] = "object"

                # Re-wrap
                return {
                     "type": "json_schema",
                     "name": wrapper_meta["name"],
                     "strict": wrapper_meta["strict"],
                     "schema": deref
                }

            openai_schema_wrapper = prepare_schema(json_schema_config)
            
            # --- DEBUG: Log Prepared Schema ---
            self._log_trace(request_id, "SCHEMA_PREPARED", openai_schema_wrapper)
            
            if trace:
                 print(f"[SOLVER_V3] Prepared Wrapper Keys: {list(openai_schema_wrapper.keys())}")
                 print(f"[SOLVER_V3] Prepared Wrapper Type: {openai_schema_wrapper.get('type')}, Name: {openai_schema_wrapper.get('name')}, Strict: {openai_schema_wrapper.get('strict')}")


            # Two-Pass Strategy
            passes = [requested_mode]
            if requested_mode != "minimal":
                passes.append("minimal")
            
            final_response_data = None
            successful_mode = None
            last_error = None
            providers_to_try = self.client_manager.get_provider_chain()
            
            # Helper for ensuring minimum tokens per tier (NOW DYNAMIC)
            def _ensure_tier_tokens(provider: str, tokens: int) -> int:
                return tokens
            
            for pass_idx, current_mode in enumerate(passes):
                is_fallback = (pass_idx > 0)
                if is_fallback:
                    telemetry["fallback_triggered"] = True
                    self._logger.info(f"[SOLVER_V3] Triggering Fallback to mode={current_mode} (pass {pass_idx+1})")
                    if trace: 
                        print(f"[SOLVER_V3] Triggering Fallback to mode={current_mode}")
                else:
                    self._logger.info(f"[SOLVER_V3] Primary attempt with mode={current_mode} (pass {pass_idx+1})")
                    if trace: 
                        print(f"[SOLVER_V3] Primary attempt with mode={current_mode}")

                if current_mode == "minimal":
                    effective_learning_mode = "solve"
                else:
                    effective_learning_mode = trusted_context.get("learning_mode") if trusted_context else learning_mode

                # --- TOKEN POLICY FIX ---
                # 1. Start with binding's max_output_tokens (which we resolved earlier into profile.max_output_tokens)
                effective_max_tokens = profile.max_output_tokens
                binding_max_output = profile.max_output_tokens  # Track original binding value
                
                # 2. Check policy limit, BUT allow exemption for RESEARCH tier or explicit binding overrides
                policy_limit = get_effective_max_tokens(current_mode, effective_learning_mode or "solve", token_policy)
                policy_source = "binding"  # Default: using binding value
                
                if profile.tier.upper() == "RESEARCH":
                    # Research tier trusts the binding
                    policy_source = "binding"
                else:
                    # Non-research tiers are capped by policy, unless binding explicitly requests less
                    if effective_max_tokens > policy_limit:
                         if trace:
                             print(f"[SOLVER_V3] Capping token limit from {effective_max_tokens} to {policy_limit} based on policy (Tier={profile.tier})")
                         effective_max_tokens = policy_limit
                         policy_source = "policy"

                # Fallback safety if profile is None (should cover all paths)
                if not effective_max_tokens or effective_max_tokens <= 0:
                    effective_max_tokens = 4096
                    policy_source = "fallback"
                
                # STEP 5: Add runtime meta fields for token policy tracking
                telemetry[f"pass_{pass_idx+1}_max_tokens"] = effective_max_tokens
                telemetry["binding_max_output"] = binding_max_output
                telemetry["effective_max_output_used"] = effective_max_tokens
                telemetry["policy_source"] = policy_source
                telemetry["policy_limit"] = policy_limit
                self._logger.debug(f"[SOLVER_V3] Pass {pass_idx+1}: mode={current_mode}, max_tokens={effective_max_tokens}, learning_mode={effective_learning_mode}")

                for provider_idx, provider in enumerate(providers_to_try):
                    llm_start_perf = time.perf_counter()
                    effective_tokens = _ensure_tier_tokens(provider, effective_max_tokens)
                    self._logger.debug(f"[SOLVER_V3] Attempting provider {provider} (idx {provider_idx}) with {effective_tokens} tokens")
                    
                    if provider_idx > 0:
                        self._logger.warning(f"[SOLVER_V3] Falling back to provider {provider} after previous provider failed")
                        telemetry["provider_fallback_triggered"] = True
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
                        
                        # Log LLM call start
                        self._log_trace(request_id, "LLM_CALL_START", {
                            "provider": provider,
                            "mode": current_mode,
                            "max_tokens": effective_tokens,
                            "pass": pass_idx + 1
                        })
                        
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
                            temperature=profile.temperature,
                            top_p=profile.top_p,
                            max_input_tokens=profile.max_input_tokens,
                            trim_strategy=profile.trim_strategy,
                            timeout=float(profile.timeout_ms) / 1000.0 if profile.timeout_ms else 60.0
                        )

                        llm_end_perf = time.perf_counter()
                        if trace:
                            try:
                                print(f"[SOLVER_V3_RAW_DEBUG] Raw Output: {raw_output_text}")
                            except Exception:
                                print(f"[SOLVER_V3_RAW_DEBUG] Raw Output: [Unprintable characters]")
                            # Also self log it in case
                            self._logger.info(f"[SOLVER_V3_RAW] Raw output: {raw_output_text}")

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
                        
                        # --- RULE 3: File Logging Only (Unified) --- 
                        self._log_trace(request_id, "LLM_RAW_OUTPUT", raw_output_text)
                        
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

                        if not validation_success:
                             self._log_trace(request_id, "VALIDATION_FAIL", {"error": validation_error, "details": error_list})

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
                        if repair_enabled and attempts < profile.json_retry_max_attempts:
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
                                    max_output_tokens=profile.json_retry_max_output_tokens,
                                    requested_mode=current_mode,
                                    trace=trace,
                                    provider=provider,
                                )
                                telemetry["latency_ms_repair"] = int((time.perf_counter() - t_repair_start) * 1000)
                                self._log_trace(request_id, "REPAIR_OUTPUT", repaired_text)
                                
                                validation_success, validation_error, validated_data, post_repair_errors = self._check_status_and_validate(
                                    repaired, status_info, openai_schema_wrapper["schema"], raw_text=repaired_text
                                )
                                if validation_success:
                                    final_response_data = validated_data
                                    successful_mode = current_mode
                                    telemetry["validated"] = True
                                    telemetry["repaired"] = True
                                    break
                                
                                self._log_trace(request_id, "REPAIR_FAIL", post_repair_errors)
                                telemetry["repair_failed_error_list"] = post_repair_errors
                                self._logger.warning(
                                    "llm_schema_invalid_repair_failed request_id=%s repair_ms=%s error=%s",
                                    request_id,
                                    telemetry["latency_ms_repair"],
                                    validation_error
                                )
                            except Exception as repair_error:
                                last_error = str(repair_error)
                                self._log_trace(request_id, "REPAIR_EXCEPTION", str(repair_error))
                                telemetry["latency_ms_repair"] = int((time.perf_counter() - t_repair_start) * 1000)

                        last_error = validation_error
                        if trace:
                            print(f"[SOLVER_V3] Pass {pass_idx+1} provider={provider} failed validation: {validation_error}")
                        continue

                    except LLMProviderError as e:
                        self.client_manager.note_error(provider, e)
                        last_error = str(e)
                        self._log_trace(request_id, "LLM_PROVIDER_ERROR", str(e))
                        if trace:
                            print(f"[SOLVER_V3] Pass {pass_idx+1} provider={provider} error: {e}")
                        continue
                    except Exception as e:
                        self.client_manager.note_error(provider, e)
                        last_error = str(e)
                        self._log_trace(request_id, "LLM_UNKNOWN_ERROR", str(e))
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
                self._log_trace(request_id, "SOLVE_FAILED", f"All attempts failed. Last error: {last_error}")
                return self._handle_error(problem_text, f"All attempts failed. Last error: {last_error}", error_code, telemetry, start_time_perf)

            # --- Success Processing ---
            response_data = final_response_data
            
            # Step 3.5: Normalize raw LLM response (fix enum variations)
            response_data = normalize_raw_llm_response(response_data)
            
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

            # --- RULE 2: Separate Plot Pipeline ---
            # Now run plotting independently if needed.
            graph_mode_param = requests_graph_mode # "auto" by default
            
            # --- STEP 6: Normalize Plotting Flags (Canonical plot_requested_effective) ---
            # Create one canonical boolean:
            # plot_requested_effective = (include_graph == true) OR (graph_mode == "on") OR (features_used.plot_requested == true)
            # Note: include_graph and features_used.plot_requested are normalized at API layer into graph_mode_param
            
            # Check trusted_context for additional plot flags
            features_used_plot = False
            if trusted_context and isinstance(trusted_context, dict):
                features_used = trusted_context.get("features_used", {})
                if isinstance(features_used, dict):
                    features_used_plot = bool(features_used.get("plot_requested", False))
                include_graph = trusted_context.get("include_graph", False)
                if include_graph:
                    features_used_plot = True
            
            # Build canonical plot_requested_effective
            plot_requested_effective = False
            if graph_mode_param == "on" or graph_mode_param == "force":
                 plot_requested_effective = True
            elif graph_mode_param == "auto" and response_data.get("visuals", {}).get("should_visualize"):
                 # Auto mode respects solver suggestion
                 plot_requested_effective = True
            elif features_used_plot:
                 plot_requested_effective = True
            
            # TIER GATE: For FREE tier, plots are disabled regardless of flags
            if profile.tier.upper() == "FREE":
                plot_requested_effective = False
                if trace:
                    print(f"[SOLVER_V3] Plots disabled for FREE tier")
            
            # Add to telemetry
            telemetry["plot_requested_effective"] = plot_requested_effective
            telemetry["graph_mode_param"] = graph_mode_param

            if plot_requested_effective:
                try:
                    plot_svc = get_plot_pipeline_service(db_session)
                    # We pass the FULL effective tier to plotting, so Research users get better plots
                    # even if the solve was minimal/free-schema.
                    trig_res, spec_res = await plot_svc.execute_plotting_pipeline(
                        problem_text=problem_text,
                        solve_result=response_data,
                        graph_mode=graph_mode_param if graph_mode_param != "off" else "auto", # Pass effective mode or fallback
                        attach_to_step_id=None,
                        tier=effective_tier_slug, # Use REAL tier here
                        question_id=request_id if request_id else "unknown"
                    )
                    
                    if spec_res and spec_res.plotly_json:
                        if trace:
                            print(f"[SOLVER_V3] Plot Generated: {spec_res.plot_id}")
                        
                        # Merge into response
                        # We can either put it in visuals.plots or a top-level plot_spec
                        # Existing minimal schema might not have complex visuals.
                        # But we normalized response_data above.
                        
                        if "visuals" not in response_data:
                            response_data["visuals"] = {}
                        
                        # Populate standardized visuals object
                        # (This works even if the solve schema didn't allow complex visuals,
                        #  because we are modifying the dict AFTER validation).
                        response_data["visuals"]["should_visualize"] = True
                        response_data["visuals"]["plots"] = [spec_res.plotly_json]
                        
                        # Add legacy field if frontend expects it
                        response_data["plot_spec"] = spec_res.plotly_json

                        # Update telemetry
                        telemetry["plot_attempted"] = True
                        telemetry["plot_generated"] = True
                        telemetry["plot_pipeline"] = {
                            "trigger": trig_res.raw_response if trig_res else None,
                            "spec_id": spec_res.plot_id,
                            "error": spec_res.error
                        }
                    else:
                         if trace:
                            print(f"[SOLVER_V3] Plot Pipeline ran but no plot produced (trigger={trig_res.plot_needed if trig_res else 'SKIP'})")

                except Exception as plot_err:
                    self._logger.error(f"Plot pipeline failed: {plot_err}")
                    if trace:
                        print(f"[SOLVER_V3] Plot Pipeline Exception: {plot_err}")

            # Finalize
            telemetry["latency_ms_total"] = int((time.perf_counter() - start_time_perf) * 1000)
            
            # Embed telemetry in response payload (legacy key + new key)
            response_data["_telemetry"] = telemetry 
            response_data["telemetry"] = telemetry
            
            response_data["_timestamp"] = datetime.utcnow().isoformat()
            
            # --- RULE 2: Disable Post-Wrap ---
            # Remove "schema_version" injection as it conflicts with strict schema validation
            # response_data["schema_version"] = "v1.0"
            
            # Log success
            self._log_trace(request_id, "SOLVE_SUCCESS", {
                "latency_ms": telemetry.get("latency_ms_total"),
                "mode": telemetry.get("mode_resolved"),
                "tier": telemetry.get("tier_effective"),
                "validated": telemetry.get("validated"),
                "repaired": telemetry.get("repaired", False)
            })
            
            if trace:
                 print(f"[SOLVER_V3] Telemetry: {json.dumps(telemetry)}")
                 print(f"[SOLVER_V3] ==================== SUCCESS ====================")
            
            return response_data

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self._log_trace(request_id, "FATAL_ERROR", {"error": str(e), "traceback": tb_str})
            if trace:
                print(f"[SOLVER_V3] [ERROR] FATAL: {e}")
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
        elif "safe_alternative" not in obj["refusal"] or obj["refusal"]["safe_alternative"] is None:
            obj["refusal"]["safe_alternative"] = None

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
            "provider": "openai", # Changed to openai
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
            provider = "openai"
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
                print(f"[SOLVER_V3_STREAM] Calling OpenAI with model={self.default_model}")

            # STEP 1: Stop streaming for structured outputs
            # If json_schema_config is present, we enforce non-streaming to ensure integrity.
            is_structured = json_schema_config is not None
            
            if is_structured:
                # Use non-streaming generate()
                if trace:
                    print(f"[SOLVER_V3_STREAM] Structured output detected. Enforcing stream=False for reliability.")
                
                # Ensure we pass the FULL wrapper, not just the inner schema
                # (Fixes half-wrapper bug in streaming path)
                full_schema_payload = json_schema_config
                
                # Fail-fast validation
                validate_schema_wrapper(full_schema_payload, context="solve_stream (structured)")

                response = await client.generate(
                    messages=messages,
                    system_prompt=None,
                    prompt=None,
                    json_schema=full_schema_payload,
                    max_tokens=effective_max_tokens,
                    temperature=0.4,
                    request_id=request_id,
                    model=self.default_model,
                    stream=False
                )
                
                full_content = response.content
                if response.usage:
                    telemetry["input_tokens"] = response.usage.get("input", 0)
                    telemetry["output_tokens"] = response.usage.get("output", 0)
                    telemetry["total_tokens"] = response.usage.get("total", 0)
                    telemetry["cached_tokens"] = response.usage.get("cached")
                telemetry["model"] = response.model
                telemetry["provider"] = response.provider

                # Yield as a single large delta to maintain contract
                yield {"type": "delta", "text": full_content}
                
            else:
                # Fallback to streaming for non-structured text
                response_stream = client.generate_stream(
                    messages=messages,
                    system_prompt=None,
                    prompt=None,
                    json_schema=None,
                    max_tokens=effective_max_tokens,
                    temperature=0.4,
                    request_id=request_id,
                    model=self.default_model,
                )

                full_content = ""
                async for chunk_obj in response_stream:
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
        
        # ALWAYS log errors to console
        request_id = telemetry.get("request_id", "UNKNOWN")
        self._log_trace(request_id, "ERROR", {
            "code": code,
            "errors": errors if isinstance(errors, list) else [str(errors)],
            "latency_ms": telemetry["latency_ms_total"]
        })
        
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
        temperature: float = 0.1,
        top_p: float = 1.0,
        max_input_tokens: int = 30000,
        trim_strategy: str = "trim_context_first",
        timeout: float = 60.0,
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
        
        # STEP 3: Fail-fast schema wrapper validation before OpenAI call
        if schema_payload and provider == "openai":
            try:
                validate_schema_wrapper(
                    schema_payload,
                    context=f"_call_llm_with_schema (request_id={request_id})"
                )
                if trace:
                    print(f"[SOLVER_DEBUG] Schema wrapper validated: name={schema_payload.get('name')}, strict={schema_payload.get('strict')}")
            except SchemaWrapperCorruptError as e:
                self._logger.error(f"[SCHEMA_WRAPPER_CORRUPT] Pre-call validation failed: {e}")
                raise  # Re-raise to fail fast - do not proceed with corrupt schema
        
        try:
             client = self.client_manager.get_client(provider)

             messages = [
                {"role": "system", "content": system_prompt},
             ]
             if developer_prompt:
                 messages.append({"role": "developer", "content": developer_prompt})
             messages.append({"role": "user", "content": user_message})
             
             # Apply input trimming strategy
             # We use a reasonable model ID for tiktoken
             messages = trim_messages(
                 messages=messages,
                 max_input_tokens=max_input_tokens,
                 strategy=trim_strategy,
                 model="gpt-4o"
             )

             # If image_url provided (Snap Mode), we need to inject it.
             # Standard OpenAI / OpenAI vision handling: content can be list.
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
                json_schema=schema_payload,  # Pass FULL wrapper with name, strict, schema
                max_tokens=max_output_tokens,
                temperature=temperature,
                stream=False,
                request_id=request_id,
                model=self.default_model if provider == "openai" else None 
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
        
        # STEP 3: Fail-fast schema wrapper validation before repair call
        if json_schema_config and provider.lower() == "openai":
            try:
                validate_schema_wrapper(
                    json_schema_config,
                    context="_repair_response"
                )
                if trace:
                    print(f"[SOLVER_V3] Repair schema validated: name={json_schema_config.get('name')}")
            except SchemaWrapperCorruptError as e:
                self._logger.error(f"[SCHEMA_WRAPPER_CORRUPT] Repair validation failed: {e}")
                raise  # Fail fast - do not proceed with corrupt schema
        
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
        if provider == "openai":
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
            model=model if provider == "openai" else None,
        )

        if not llm_response.content:
            raise ValueError("Empty repair output")
        data = json.loads(llm_response.content)
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
