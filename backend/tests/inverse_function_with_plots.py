"""
Complete 3-Tier Test with Plot Trigger + Spec
Problem: Find the inverse of f(x) = (x-1)/(x+2)
"""

import os
import sys
import json
import asyncio
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from sqlmodel import Session

from app.database import engine
from app.models import PromptModeEnum, PromptTemplateEntry, JsonSchemaEntry
from app.prompts.db_loader import resolve_prompt_bundle, PromptBindingLookupError
from sqlmodel import select

PROBLEM = r"Find the inverse of f(x) = \frac{x - 1}{x + 2}"

def sanitize_schema(obj):
    """Sanitize schema for OpenAI compatibility."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in ('allOf', 'if', 'then', 'else'):
                continue
            if k == 'description' and '$ref' in obj:
                continue
            result[k] = sanitize_schema(v)
        if 'properties' in result:
            props = set(result['properties'].keys())
            req = set(result.get('required', []))
            result['required'] = list(props | req)
            if 'type' not in result:
                result['type'] = 'object'
        return result
    elif isinstance(obj, list):
        return [sanitize_schema(item) for item in obj]
    return obj


def load_plot_prompt_from_db(session: Session, prompt_id: str, system_prompt_id: str = "global_system_prompt_v1"):
    """Load plot prompt directly from prompt_templates table."""
    # Get system prompt
    system_template = session.exec(
        select(PromptTemplateEntry).where(
            PromptTemplateEntry.prompt_id == system_prompt_id,
            PromptTemplateEntry.is_active == True
        )
    ).first()
    system_prompt = system_template.content if system_template else "You are a helpful math assistant."
    
    # Get developer prompt
    dev_template = session.exec(
        select(PromptTemplateEntry).where(
            PromptTemplateEntry.prompt_id == prompt_id,
            PromptTemplateEntry.is_active == True
        )
    ).first()
    
    if not dev_template:
        raise ValueError(f"Prompt template not found: {prompt_id}")
    
    return {
        "system_prompt_content": system_prompt,
        "developer_prompt_content": dev_template.content,
        "global_system_prompt_id": system_prompt_id,
        "developer_prompt_id": prompt_id
    }


def load_plot_schema_from_db(session: Session, schema_id: str):
    """Load plot schema directly from json_schemas table."""
    schema_entry = session.exec(
        select(JsonSchemaEntry).where(
            JsonSchemaEntry.schema_id == schema_id,
            JsonSchemaEntry.is_active == True
        )
    ).first()
    
    if not schema_entry:
        raise ValueError(f"Schema not found: {schema_id}")
    
    return {
        "output_schema_json": schema_entry.content,
        "output_schema_id": schema_id
    }

async def test_tier(tier: str, client: AsyncOpenAI, all_results: dict):
    """Test a single tier with solve + plot trigger + plot spec."""
    print(f"\n{'='*60}")
    print(f"TESTING TIER: {tier}")
    print(f"Problem: {PROBLEM}")
    print('='*60)
    
    results = {
        "tier": tier,
        "problem": PROBLEM,
        "timestamp": datetime.now().isoformat(),
        "solve": None,
        "plot_trigger": None,
        "plot_spec": None
    }
    
    with Session(engine) as session:
        # ========== SOLVE ==========
        print(f"\n[SOLVE - {tier}]")
        try:
            bundle = resolve_prompt_bundle(
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.SOLVE,
                db_session=session,
            )
            
            messages = [
                {"role": "system", "content": bundle.system_prompt_content},
                {"role": "developer", "content": bundle.developer_prompt_content},
                {"role": "user", "content": PROBLEM}
            ]
            
            db_wrapper = bundle.output_schema_json or {}
            inner_schema = db_wrapper.get("schema", {})
            sanitized = sanitize_schema(inner_schema)
            
            request_payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": db_wrapper.get("name", "solve_output"),
                        "strict": db_wrapper.get("strict", True),
                        "schema": sanitized
                    }
                }
            }
            
            start = time.time()
            response = await client.chat.completions.create(**request_payload)
            latency = (time.time() - start) * 1000
            
            raw_content = response.choices[0].message.content
            result = json.loads(raw_content)
            
            results["solve"] = {
                "success": True,
                "request_id": response.id,
                "latency_ms": latency,
                "tokens_in": response.usage.prompt_tokens if response.usage else 0,
                "tokens_out": response.usage.completion_tokens if response.usage else 0,
                "system_prompt_id": bundle.global_system_prompt_id,
                "developer_prompt_id": bundle.developer_prompt_id,
                "schema_id": bundle.output_schema_id,
                "raw_request": request_payload,
                "raw_response": raw_content,
                "parsed_result": result,
                "final_answer": str(result.get("final_answer", result.get("properties", {}).get("final_answer", "N/A")))
            }
            
            print(f"✅ Solve SUCCESS")
            print(f"   Request ID: {response.id}")
            print(f"   Latency: {latency:.0f}ms")
            print(f"   Tokens: {results['solve']['tokens_in']} → {results['solve']['tokens_out']}")
            print(f"   Final Answer: {results['solve']['final_answer'][:100]}")
            
        except Exception as e:
            results["solve"] = {"success": False, "error": str(e)}
            print(f"❌ Solve FAILED: {e}")
            all_results[tier] = results
            return results
        
        # ========== PLOT TRIGGER ==========
        print(f"\n[PLOT TRIGGER - {tier}]")
        trigger_bundle = None
        try:
            trigger_bundle = resolve_prompt_bundle(
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.PLOT_TRIGGER,
                db_session=session,
            )
            print(f"   Using binding for plot trigger")
        except PromptBindingLookupError:
            print(f"   No binding found, loading directly from DB tables...")
            prompt_data = load_plot_prompt_from_db(session, "plot_trigger_v1")
            schema_data = load_plot_schema_from_db(session, "youask_plot_trigger_v1.schema.json")
            # Create a simple object to hold the data
            class SimpleBundle:
                pass
            trigger_bundle = SimpleBundle()
            trigger_bundle.system_prompt_content = prompt_data["system_prompt_content"]
            trigger_bundle.developer_prompt_content = prompt_data["developer_prompt_content"]
            trigger_bundle.global_system_prompt_id = prompt_data["global_system_prompt_id"]
            trigger_bundle.developer_prompt_id = prompt_data["developer_prompt_id"]
            trigger_bundle.output_schema_json = schema_data["output_schema_json"]
            trigger_bundle.output_schema_id = schema_data["output_schema_id"]
        
        try:
            trigger_messages = [
                {"role": "system", "content": trigger_bundle.system_prompt_content},
                {"role": "developer", "content": trigger_bundle.developer_prompt_content},
                {"role": "user", "content": json.dumps({
                    "problem_text": PROBLEM,
                    "final_answer": result.get("final_answer", {}),
                    "solve_visuals": result.get("visuals", {})
                }, ensure_ascii=False)}
            ]
            
            db_wrapper = trigger_bundle.output_schema_json or {}
            inner_schema = db_wrapper.get("schema", {})
            sanitized = sanitize_schema(inner_schema)
            
            trigger_request = {
                "model": "gpt-4o-mini",
                "messages": trigger_messages,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": db_wrapper.get("name", "plot_trigger"),
                        "strict": db_wrapper.get("strict", True),
                        "schema": sanitized
                    }
                }
            }
            
            print(f"   Sending plot trigger request...")
            start = time.time()
            trigger_response = await client.chat.completions.create(**trigger_request)
            trigger_latency = (time.time() - start) * 1000
            
            trigger_raw = trigger_response.choices[0].message.content
            trigger_result = json.loads(trigger_raw)
            
            results["plot_trigger"] = {
                "success": True,
                "request_id": trigger_response.id,
                "latency_ms": trigger_latency,
                "tokens_in": trigger_response.usage.prompt_tokens if trigger_response.usage else 0,
                "tokens_out": trigger_response.usage.completion_tokens if trigger_response.usage else 0,
                "system_prompt_id": trigger_bundle.global_system_prompt_id,
                "developer_prompt_id": trigger_bundle.developer_prompt_id,
                "schema_id": trigger_bundle.output_schema_id,
                "raw_request": trigger_request,
                "raw_response": trigger_raw,
                "parsed": trigger_result
            }
            
            print(f"✅ Plot Trigger SUCCESS")
            print(f"   Request ID: {trigger_response.id}")
            print(f"   Latency: {trigger_latency:.0f}ms")
            print(f"   plot_needed: {trigger_result.get('plot_needed')}")
            print(f"   plot_type: {trigger_result.get('plot_type')}")
            print(f"   reason: {trigger_result.get('reason', 'N/A')[:80]}")
            
            # ========== PLOT SPEC ==========
            if trigger_result.get("plot_needed"):
                print(f"\n[PLOT SPEC - {tier}]")
                spec_bundle = None
                try:
                    spec_bundle = resolve_prompt_bundle(
                        provider="openai",
                        tier=tier,
                        mode=PromptModeEnum.PLOT_SPEC,
                        db_session=session,
                    )
                    print(f"   Using binding for plot spec")
                except PromptBindingLookupError:
                    print(f"   No binding found, loading directly from DB tables...")
                    prompt_data = load_plot_prompt_from_db(session, "plot_spec_v1")
                    schema_data = load_plot_schema_from_db(session, "youask_plot_spec_v1.schema.json")
                    class SimpleBundle:
                        pass
                    spec_bundle = SimpleBundle()
                    spec_bundle.system_prompt_content = prompt_data["system_prompt_content"]
                    spec_bundle.developer_prompt_content = prompt_data["developer_prompt_content"]
                    spec_bundle.global_system_prompt_id = prompt_data["global_system_prompt_id"]
                    spec_bundle.developer_prompt_id = prompt_data["developer_prompt_id"]
                    spec_bundle.output_schema_json = schema_data["output_schema_json"]
                    spec_bundle.output_schema_id = schema_data["output_schema_id"]
                
                try:
                    plot_plan = {
                        "plot_type": trigger_result.get("plot_type", "function"),
                        "variables": trigger_result.get("variables", ["x", "y"]),
                        "ranges": trigger_result.get("ranges", {"x": [-10, 10], "y": [-10, 10]}),
                        "series_plan": trigger_result.get("series_plan", [
                            {"expression": "(x-1)/(x+2)", "label": "f(x) = (x-1)/(x+2)"}
                        ]),
                        "key_points": trigger_result.get("key_points", [])
                    }
                    
                    spec_messages = [
                        {"role": "system", "content": spec_bundle.system_prompt_content},
                        {"role": "developer", "content": spec_bundle.developer_prompt_content},
                        {"role": "user", "content": json.dumps({
                            "problem_text": PROBLEM,
                            "attach_to_step_id": None,
                            "plot_plan": plot_plan
                        }, ensure_ascii=False)}
                    ]
                    
                    db_wrapper = spec_bundle.output_schema_json or {}
                    inner_schema = db_wrapper.get("schema", {})
                    sanitized = sanitize_schema(inner_schema)
                    
                    spec_request = {
                        "model": "gpt-4o-mini",
                        "messages": spec_messages,
                        "temperature": 0.1,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": db_wrapper.get("name", "plot_spec"),
                                "strict": db_wrapper.get("strict", True),
                                "schema": sanitized
                            }
                        }
                    }
                    
                    print(f"   Sending plot spec request...")
                    start = time.time()
                    spec_response = await client.chat.completions.create(**spec_request)
                    spec_latency = (time.time() - start) * 1000
                    
                    spec_raw = spec_response.choices[0].message.content
                    spec_result = json.loads(spec_raw)
                    
                    results["plot_spec"] = {
                        "success": True,
                        "request_id": spec_response.id,
                        "latency_ms": spec_latency,
                        "tokens_in": spec_response.usage.prompt_tokens if spec_response.usage else 0,
                        "tokens_out": spec_response.usage.completion_tokens if spec_response.usage else 0,
                        "system_prompt_id": spec_bundle.global_system_prompt_id,
                        "developer_prompt_id": spec_bundle.developer_prompt_id,
                        "schema_id": spec_bundle.output_schema_id,
                        "raw_request": spec_request,
                        "raw_response": spec_raw,
                        "parsed": spec_result
                    }
                    
                    plot_data = spec_result.get("plot", {}).get("plotly", {})
                    print(f"✅ Plot Spec SUCCESS")
                    print(f"   Request ID: {spec_response.id}")
                    print(f"   Latency: {spec_latency:.0f}ms")
                    print(f"   plot_id: {spec_result.get('plot', {}).get('plot_id')}")
                    print(f"   traces: {len(plot_data.get('data', []))}")
                    
                except Exception as e:
                    results["plot_spec"] = {"success": False, "error": str(e)}
                    print(f"❌ Plot Spec FAILED: {e}")
            else:
                results["plot_spec"] = {"success": False, "reason": "plot_not_needed_by_trigger"}
                print(f"   Plot not needed (trigger said plot_needed=false)")
                
        except Exception as e:
            results["plot_trigger"] = {"success": False, "error": str(e)}
            results["plot_spec"] = {"success": False, "error": f"Trigger failed: {e}"}
            print(f"❌ Plot Trigger FAILED: {e}")
    
    all_results[tier] = results
    return results

async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)
    
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    all_results = {}
    
    for tier in ["FREE", "STANDARD", "RESEARCH"]:
        await test_tier(tier, client, all_results)
    
    # Save all results
    output_file = "inverse_function_with_plots.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"FULL RESULTS SAVED TO: {output_file}")
    print('='*60)
    
    # Print summary
    print("\nSUMMARY:")
    for tier, res in all_results.items():
        solve = res.get("solve", {})
        trigger = res.get("plot_trigger") or {}
        spec = res.get("plot_spec") or {}
        
        solve_status = "✅" if solve.get("success") else "❌"
        trigger_status = "✅" if trigger.get("success") else "❌"
        spec_status = "✅" if spec.get("success") else "❌"
        
        print(f"\n{tier}:")
        print(f"  {solve_status} Solve: {solve.get('final_answer', 'FAILED')[:50]}")
        print(f"  {trigger_status} Plot Trigger: {trigger.get('parsed', {}).get('plot_needed', 'FAILED') if trigger.get('success') else trigger.get('error', 'FAILED')}")
        print(f"  {spec_status} Plot Spec: {'SUCCESS' if spec.get('success') else spec.get('error', 'FAILED')[:50]}")

if __name__ == "__main__":
    asyncio.run(main())
