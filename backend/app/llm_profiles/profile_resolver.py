
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
    
    def __init__(self, prompt_binding_meta: Dict[str, Any]):
        self.prompt_binding_meta = prompt_binding_meta

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
            tier_slug = (force_tier or "FREE").upper()
            
            # Use resolve_binding_payload to validate and get binding
            # logic from prompt_registry_service handles validation of tier/mode existence
            _, _, binding = prompt_registry_service.resolve_binding_payload(
                session=session,
                tier_slug=tier_slug,
                mode=requested_mode
            )
            
            if not binding:
                 raise ProfileResolutionError(
                    f"No active binding found for tier={tier_slug}, mode={requested_mode}",
                    code="NO_BINDING_FOUND"
                )

            # Fetch prompt details to get versions
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
            }
            
            return cls(prompt_binding_meta=meta)

        except PromptRegistryError as e:
            raise ProfileResolutionError(str(e), details={"original_error": str(e)})
        except Exception as e:
            if isinstance(e, ProfileResolutionError):
                raise e
            raise ProfileResolutionError(f"Failed to resolve profile: {str(e)}", details={"original_error": str(e)})
