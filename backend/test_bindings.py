import json
from app.database import Session, engine
from app.prompts.db_loader import resolve_prompt_bundle
from app.models import PromptTierEnum, PromptModeEnum

def test_resolve():
    with Session(engine) as session:
        # Try to resolve FREE SOLVE binding
        try:
            bundle = resolve_prompt_bundle(
                provider="openai",
                tier="FREE",
                mode="SOLVE",
                db_session=session
            )
            print("Successfully resolved FREE SOLVE bundle")
            print(f"Binding ID: {bundle.prompt_binding_id}")
            print(f"Max Output Tokens: {bundle.max_output_tokens}")
            print(f"Max Input Tokens: {bundle.max_input_tokens}")
            print(f"Temperature: {bundle.temperature}")
            print(f"Trim Strategy: {bundle.trim_strategy}")
            print(f"Plot Points Cap: {bundle.plot_points_cap}")
            
            # Check if fields exist (even if None)
            fields = [
                "max_output_tokens", "max_input_tokens", "system_schema_budget_tokens",
                "context_budget_tokens", "json_retry_max_output_tokens",
                "json_retry_max_attempts", "timeout_ms", "temperature", "top_p",
                "plot_points_cap", "plot_traces_cap", "plot_annotations_cap",
                "trim_strategy"
            ]
            for f in fields:
                val = getattr(bundle, f, "MISSING")
                print(f"Field {f}: {val}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Resolution failed: {e}")

if __name__ == "__main__":
    test_resolve()
