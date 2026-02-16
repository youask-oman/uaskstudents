
from typing import Optional, Any, Dict
from sqlmodel import Session
from app.models import User
from app.services.prompt_registry_service import prompt_registry_service, PromptRegistryError

class ProfileResolutionError(Exception):
    def __init__(self, message: str, code: str = "PROFILE_RESOLUTION_FAILED", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

class ProfileResolver:
    """
    Resolves the LLM profile (prompt binding) for a given user context.
    Acts as a bridge between high-level intent and low-level prompt binding.
    """
    
    def __init__(
        self, 
        prompt_binding_meta: Dict[str, Any], 
        mode: str,
        tier: str,
        system_prompt_content: str,
        developer_prompt_content: Optional[str],
        json_schema_content: Dict[str, Any],
    ):
        self.prompt_binding_meta = prompt_binding_meta
        self.mode = mode
        self.tier = tier
        self.system_prompt_content = system_prompt_content
        self.developer_prompt_content = developer_prompt_content
        self.json_schema_content = json_schema_content

    @property
    def max_output_tokens(self) -> Optional[int]:
        return self.prompt_binding_meta.get("max_output_tokens")

    @property
    def system_asset_path(self) -> Optional[str]:
        # DB-backed prompts do not have a file asset path
        return None

    @property
    def system_relative_path(self) -> Optional[str]:
        # Return ID as a proxy for the path for tracing
        return self.prompt_binding_meta.get("global_system_prompt_id")

    @property
    def schema_asset_path(self) -> Optional[str]:
        return None

    @property
    def schema_relative_path(self) -> Optional[str]:
        return self.prompt_binding_meta.get("output_schema_id")

    @classmethod
    def resolve_profile(
        cls,
        session: Session,
        user: User,
        requested_mode: str,
        learning_mode: str = "solve",
        force_tier: Optional[str] = None,
        mode_family: str = "SOLVE",
        provider: str = "openai",
    ) -> "ProfileResolver":
        """
        Resolves the appropriate profile based on the request context.
        """
        try:
            # Normalize tier and mode
            tier_slug = (force_tier or "SHORT_STEPS").upper()
            
            # Use resolve_binding_payload to validate and get binding
            # logic from prompt_registry_service handles validation of tier/mode existence
            system_prompt_combined, schema_content, binding = prompt_registry_service.resolve_binding_payload(
                session=session,
                tier_slug=tier_slug,
                mode=requested_mode
            )
            
            if not binding:
                 raise ProfileResolutionError(
                    f"No active binding found for tier={tier_slug}, mode={requested_mode}",
                    code="NO_BINDING_FOUND"
                )

            # Fetch prompt details to get versions and raw developer content
            global_prompt = prompt_registry_service.get_active_prompt(session, binding.global_system_prompt_id)
            developer_prompt = prompt_registry_service.get_active_prompt(session, binding.developer_prompt_id)
            schema_entry = prompt_registry_service.get_active_schema(session, binding.output_schema_id)

            meta = {
                "binding_id": binding.id,
                "global_system_prompt_id": binding.global_system_prompt_id,
                "developer_prompt_id": binding.developer_prompt_id,
                "output_schema_id": binding.output_schema_id,
                
                "global_system_prompt_version": global_prompt.version if global_prompt else None,
                "developer_prompt_version": developer_prompt.version if developer_prompt else None,
                "output_schema_version": schema_entry.version if schema_entry else None,

                # Token & Runtime Config
                "max_output_tokens": binding.max_output_tokens,
                "max_input_tokens": binding.max_input_tokens,
                "temperature": binding.temperature,
                "top_p": binding.top_p,
                "timeout_ms": binding.timeout_ms,
                "trim_strategy": binding.trim_strategy.value if binding.trim_strategy else None,
                
                # Budgets & Retries
                "system_schema_budget_tokens": binding.system_schema_budget_tokens,
                "context_budget_tokens": binding.context_budget_tokens,
                "json_retry_max_output_tokens": binding.json_retry_max_output_tokens,
                "json_retry_max_attempts": binding.json_retry_max_attempts,
                "retry_cap_tokens": binding.retry_cap_tokens,
                "max_steps": binding.max_steps,

                # Plot Caps
                "plot_points_cap": binding.plot_points_cap,
                "plot_traces_cap": binding.plot_traces_cap,
                "plot_annotations_cap": binding.plot_annotations_cap,
                "features": binding.features if isinstance(binding.features, dict) else {},
                "multipliers": binding.multipliers if isinstance(binding.multipliers, dict) else {},
            }
            
            # api.py expects .mode to be available on the instance.
            profile_mode = binding.mode.value if hasattr(binding.mode, 'value') else str(binding.mode)
            
            return cls(
                prompt_binding_meta=meta, 
                mode=profile_mode,
                tier=tier_slug,
                system_prompt_content=system_prompt_combined,
                developer_prompt_content=developer_prompt.content if developer_prompt else None,
                json_schema_content=schema_content or {}
            )

        except PromptRegistryError as e:
            raise ProfileResolutionError(str(e), details={"original_error": str(e)})
        except Exception as e:
            if isinstance(e, ProfileResolutionError):
                raise e
            raise ProfileResolutionError(f"Failed to resolve profile: {str(e)}", details={"original_error": str(e)})
