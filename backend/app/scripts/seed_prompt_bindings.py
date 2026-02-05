import logging
import sys
import os

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from sqlmodel import Session, select
from app.database import engine
from app.models import PromptBinding, PromptTierEnum, PromptModeEnum, TrimStrategyEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULTS = [
    # --- FREE TIER ---
    {
        "tier": PromptTierEnum.FREE,
        "mode": PromptModeEnum.SOLVE,
        "max_output_tokens": 600,
        "max_input_tokens": 1200,
        "system_schema_budget_tokens": 700,
        "context_budget_tokens": 100,
        "json_retry_max_output_tokens": 350,
        "json_retry_max_attempts": 1,
        "timeout_ms": 10000,
        "temperature": 0.1,
        "trim_strategy": TrimStrategyEnum.TRIM_CONTEXT_FIRST,
        "max_steps": 2,
    },
    {
        "tier": PromptTierEnum.FREE,
        "mode": PromptModeEnum.PLOT_TRIGGER,
        "max_output_tokens": 500,
        "max_input_tokens": 1200,
        "system_schema_budget_tokens": 700,
        "context_budget_tokens": 150,
        "json_retry_max_output_tokens": 300,
        "json_retry_max_attempts": 1,
        "timeout_ms": 8000,
        "temperature": 0.1,
        "trim_strategy": TrimStrategyEnum.TRIM_USER_FIRST,
        # Default Prompts for PLOT_TRIGGER if not exists
        "global_system_prompt_id": "plot_trigger_v1",
        "developer_prompt_id": "plot_trigger_v1", # Usually same for trigger
        "output_schema_id": "youask_plot_trigger_v1",
    },
    {
        "tier": PromptTierEnum.FREE,
        "mode": PromptModeEnum.PLOT_SPEC,
        "max_output_tokens": 1400,
        "max_input_tokens": 1600,
        "system_schema_budget_tokens": 800,
        "context_budget_tokens": 150,
        "json_retry_max_output_tokens": 900,
        "json_retry_max_attempts": 1,
        "timeout_ms": 12000,
        "temperature": 0.1,
        "plot_points_cap": 25,
        "plot_traces_cap": 2,
        "plot_annotations_cap": 3,
        # approximated as trim_user_first since trim_everything_except_plot_plan not in enum yet
        "trim_strategy": TrimStrategyEnum.TRIM_USER_FIRST, 
        "global_system_prompt_id": "plot_spec_v1",
        "developer_prompt_id": "plot_spec_v1",
        "output_schema_id": "youask_plot_spec_v1",
    },

    # --- STANDARD TIER ---
    {
        "tier": PromptTierEnum.STANDARD,
        "mode": PromptModeEnum.SOLVE,
        "max_output_tokens": 2600,
        "max_input_tokens": 2200,
        "system_schema_budget_tokens": 1200,
        "context_budget_tokens": 200,
        "json_retry_max_output_tokens": 1800,
        "json_retry_max_attempts": 1,
        "timeout_ms": 15000,
        "temperature": 0.1,
        "trim_strategy": TrimStrategyEnum.SUMMARIZE_CONTEXT,
        "max_steps": 6,
    },
    {
        "tier": PromptTierEnum.STANDARD,
        "mode": PromptModeEnum.PLOT_TRIGGER,
        "max_output_tokens": 500,
        "max_input_tokens": 1200,
        "system_schema_budget_tokens": 700,
        "context_budget_tokens": 150,
        "json_retry_max_output_tokens": 300,
        "json_retry_max_attempts": 1,
        "timeout_ms": 8000,
        "temperature": 0.1,
        "trim_strategy": TrimStrategyEnum.TRIM_USER_FIRST,
        "global_system_prompt_id": "plot_trigger_v1",
        "developer_prompt_id": "plot_trigger_v1",
        "output_schema_id": "youask_plot_trigger_v1",
    },
    {
        "tier": PromptTierEnum.STANDARD,
        "mode": PromptModeEnum.PLOT_SPEC,
        "max_output_tokens": 1400,
        "max_input_tokens": 1600,
        "system_schema_budget_tokens": 800,
        "context_budget_tokens": 150,
        "json_retry_max_output_tokens": 900,
        "json_retry_max_attempts": 1,
        "timeout_ms": 12000,
        "temperature": 0.1,
        "plot_points_cap": 25,
        "plot_traces_cap": 2,
        "plot_annotations_cap": 3,
        "trim_strategy": TrimStrategyEnum.TRIM_USER_FIRST,
        "global_system_prompt_id": "plot_spec_v1",
        "developer_prompt_id": "plot_spec_v1",
        "output_schema_id": "youask_plot_spec_v1",
    },

    # --- RESEARCH TIER ---
    {
        "tier": PromptTierEnum.RESEARCH,
        "mode": PromptModeEnum.SOLVE,
        "max_output_tokens": 3600,
        "max_input_tokens": 2600,
        "system_schema_budget_tokens": 1400,
        "context_budget_tokens": 250,
        "json_retry_max_output_tokens": 2400,
        "json_retry_max_attempts": 1,
        "timeout_ms": 20000,
        "temperature": 0.1,
        "trim_strategy": TrimStrategyEnum.SUMMARIZE_CONTEXT,
        "max_steps": 12,
    },
    {
        "tier": PromptTierEnum.RESEARCH,
        "mode": PromptModeEnum.PLOT_TRIGGER,
        "max_output_tokens": 500,
        "max_input_tokens": 1200,
        "system_schema_budget_tokens": 700,
        "context_budget_tokens": 150,
        "json_retry_max_output_tokens": 300,
        "json_retry_max_attempts": 1,
        "timeout_ms": 8000,
        "temperature": 0.1,
        "trim_strategy": TrimStrategyEnum.TRIM_USER_FIRST,
        "global_system_prompt_id": "plot_trigger_v1",
        "developer_prompt_id": "plot_trigger_v1",
        "output_schema_id": "youask_plot_trigger_v1",
    },
    {
        "tier": PromptTierEnum.RESEARCH,
        "mode": PromptModeEnum.PLOT_SPEC,
        "max_output_tokens": 1400,
        "max_input_tokens": 1600,
        "system_schema_budget_tokens": 800,
        "context_budget_tokens": 150,
        "json_retry_max_output_tokens": 900,
        "json_retry_max_attempts": 1,
        "timeout_ms": 12000,
        "temperature": 0.1,
        "plot_points_cap": 25,
        "plot_traces_cap": 2,
        "plot_annotations_cap": 3,
        "trim_strategy": TrimStrategyEnum.TRIM_USER_FIRST,
        "global_system_prompt_id": "plot_spec_v1",
        "developer_prompt_id": "plot_spec_v1",
        "output_schema_id": "youask_plot_spec_v1",
    },
]

def seed_bindings():
    with Session(engine) as session:
        for config in DEFAULTS:
            tier = config["tier"]
            mode = config["mode"]
            
            logger.info(f"Checking binding for {tier.value} - {mode.value}...")
            
            # Find existing active binding
            statement = select(PromptBinding).where(
                PromptBinding.tier == tier,
                PromptBinding.mode == mode,
                PromptBinding.is_active == True
            )
            existing = session.exec(statement).first()

            if existing:
                logger.info(f"Updating existing binding for {tier.value} - {mode.value}")
                for key, value in config.items():
                    # For plot bindings, we might be supplying IDs if they don't exist
                    # but if the binding exists, we mainly want to update token config
                    # UNLESS the prompt IDs are currently null/wrong
                    if key in ["global_system_prompt_id", "developer_prompt_id", "output_schema_id"]:
                         # Only update Prompt/Schema IDs if they are missing or if we want to enforce them
                         # For now, let's strictly update the token config fields
                         continue
                        
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                
                # Special handling for Plot prompt IDs if they were never set (e.g. creating new tiers)
                # But since 'existing' means we found one, we assume IDs are set. 
                # If you strictly want to force the prompt IDs too, uncomment:
                # if "global_system_prompt_id" in config:
                #     existing.global_system_prompt_id = config["global_system_prompt_id"]
                #     existing.developer_prompt_id = config["developer_prompt_id"]
                #     existing.output_schema_id = config["output_schema_id"]

                existing.updated_by = "seed_script"
                session.add(existing)
            else:
                logger.info(f"Creating NEW binding for {tier.value} - {mode.value}")
                # For new bindings, we MUST have the prompt IDs
                if "global_system_prompt_id" not in config:
                     # Fallback to defaults or skip if we can't find prompts?
                     # Inspecting api.py, standard defaults are often "youask_v3_system" etc.
                     # Let's try to infer or use placeholders if missing
                     if mode == PromptModeEnum.SOLVE:
                         config["global_system_prompt_id"] = "youask_v3_system"
                         config["developer_prompt_id"] = "youask_v3_developer"
                         config["output_schema_id"] = "youask_v3_schema"
                
                binding = PromptBinding(**config)
                binding.updated_by = "seed_script"
                session.add(binding)
        
        session.commit()
        logger.info("Seeding complete.")

if __name__ == "__main__":
    seed_bindings()
