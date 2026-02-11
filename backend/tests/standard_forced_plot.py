"""
STANDARD Tier Test - Force Plot Spec Execution
Problem: Find the inverse of f(x) = (x-1)/(x+2)
Forces plot spec to run even if trigger says plot not needed.
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
from sqlmodel import Session, select

from app.database import engine
from app.models import PromptModeEnum, PromptTemplateEntry, JsonSchemaEntry
from app.prompts.db_loader import resolve_prompt_bundle, PromptBindingLookupError

PROBLEM = r"Find the equation of the line passing through points (2, 3) and (5, 9)"

def extract_json_from_response(text: str) -> dict:
    """Extract first valid JSON object from text, handling trailing garbage."""
    text = text.strip()
    
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Extract first JSON object using bracket counting
    depth = 0
    start = -1
    for i, char in enumerate(text):
        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    continue
    
    # Try finding JSON array
    depth = 0
    start = -1
    for i, char in enumerate(text):
        if char == '[':
            if depth == 0:
                start = i
            depth += 1
        elif char == ']':
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    continue
    
    raise ValueError(f"Could not extract valid JSON from: {text[:200]}...")


def sanitize_schema(obj, _depth=0):
    """Aggressive sanitization for OpenAI strict mode."""
    if _depth > 20:
        return obj
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in ('allOf', 'if', 'then', 'else'):
                continue
            if k == 'description' and '$ref' in obj:
                continue
            result[k] = sanitize_schema(v, _depth + 1)
        
        # Fix object schemas: properties, items, or type=object
        if 'properties' in result or result.get('type') == 'object':
            if 'properties' in result:
                props = set(result['properties'].keys())
                req = set(result.get('required', []))
                result['required'] = list(props | req)
            result['additionalProperties'] = False
            if 'type' not in result:
                result['type'] = 'object'
        
        # Fix items schemas deeply
        if 'items' in result:
            items = result['items']
            if isinstance(items, dict):
                if items.get('type') == 'object' or 'properties' in items:
                    items['additionalProperties'] = False
                    if 'type' not in items:
                        items['type'] = 'object'
                # Also fix nested items.properties
                if 'properties' in items:
                    for pk, pv in items['properties'].items():
                        if isinstance(pv, dict) and (pv.get('type') == 'object' or 'properties' in pv):
                            pv['additionalProperties'] = False
                            if 'type' not in pv:
                                pv['type'] = 'object'
                            if 'properties' in pv:
                                props = set(pv['properties'].keys())
                                req = set(pv.get('required', []))
                                pv['required'] = list(props | req)
                            items['properties'][pk] = pv
                result['items'] = items
        
        # Fix anyOf/oneOf schemas
        for key in ['anyOf', 'oneOf']:
            if key in result:
                for i, sub in enumerate(result[key]):
                    if isinstance(sub, dict) and (sub.get('type') == 'object' or 'properties' in sub):
                        sub['additionalProperties'] = False
                        if 'type' not in sub:
                            sub['type'] = 'object'
                        result[key][i] = sub
        
        return result
    elif isinstance(obj, list):
        return [sanitize_schema(item, _depth + 1) for item in obj]
    return obj


def load_plot_prompt_from_db(session: Session, prompt_id: str, system_prompt_id: str = "global_system_prompt_v1"):
    """Load plot prompt directly from prompt_templates table."""
    system_template = session.exec(
        select(PromptTemplateEntry).where(
            PromptTemplateEntry.prompt_id == system_prompt_id,
            PromptTemplateEntry.is_active == True
        )
    ).first()
    system_prompt = system_template.content if system_template else "You are a helpful math assistant."
    
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


async def test_standard_with_forced_plot_spec():
    """Test STANDARD tier with forced plot spec execution."""
    tier = "STANDARD"
    print(f"\n{'='*70}")
    print(f"TESTING {tier} - WITH FORCED PLOT SPEC")
    print(f"Problem: {PROBLEM}")
    print('='*70)
    
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    results = {"tier": tier, "problem": PROBLEM, "timestamp": datetime.now().isoformat()}
    
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
                "model": "gpt-5-mini",
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
                "parsed_result": result
            }
            
            print(f"✅ Solve SUCCESS")
            print(f"   Request ID: {response.id}")
            print(f"   Latency: {latency:.0f}ms")
            print(f"   Tokens: {results['solve']['tokens_in']} → {results['solve']['tokens_out']}")
            
        except Exception as e:
            results["solve"] = {"success": False, "error": str(e)}
            print(f"❌ Solve FAILED: {e}")
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
                "model": "gpt-5-mini",
                "messages": trigger_messages,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": db_wrapper.get("name", "plot_trigger"),
                        "strict": False,  # Disable strict for complex plot schemas
                        "schema": sanitized
                    }
                }
            }
            
            print(f"   Sending plot trigger request...")
            start = time.time()
            trigger_response = await client.chat.completions.create(**trigger_request)
            trigger_latency = (time.time() - start) * 1000
            
            trigger_raw = trigger_response.choices[0].message.content
            trigger_result = extract_json_from_response(trigger_raw)
            
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
            
        except Exception as e:
            results["plot_trigger"] = {"success": False, "error": str(e)}
            print(f"❌ Plot Trigger FAILED: {e}")
        
        # ========== PLOT SPEC (FORCED - always runs) ==========
        print(f"\n[PLOT SPEC - {tier}] - FORCED EXECUTION")
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
            # Build plot plan - either from trigger or default
            if results.get("plot_trigger", {}).get("success"):
                trigger_result = results["plot_trigger"]["parsed"]
                plot_plan = {
                    "plot_type": "function",
                    "variables": ["x", "y"],
                    "ranges": {"x": [-2, 10], "y": [-2, 12]},
                    "series_plan": [
                        {"expression": "2*x - 1", "label": "y = 2x - 1 (line through (2,3) and (5,9))"}
                    ],
                    "key_points": [
                        {"x": 2, "y": 3, "label": "Point 1 (2,3)"},
                        {"x": 5, "y": 9, "label": "Point 2 (5,9)"}
                    ]
                }
            else:
                # Default plot plan for line through two points
                plot_plan = {
                    "plot_type": "function",
                    "variables": ["x", "y"],
                    "ranges": {"x": [-2, 10], "y": [-2, 12]},
                    "series_plan": [
                        {"expression": "2*x - 1", "label": "y = 2x - 1 (line through (2,3) and (5,9))"}
                    ],
                    "key_points": [
                        {"x": 2, "y": 3, "label": "Point 1 (2,3)"},
                        {"x": 5, "y": 9, "label": "Point 2 (5,9)"}
                    ]
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
                "model": "gpt-5-mini",
                "messages": spec_messages,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": db_wrapper.get("name", "plot_spec"),
                        "strict": False,  # Disable strict for complex plot schemas
                        "schema": sanitized
                    }
                }
            }
            
            print(f"   Sending plot spec request...")
            print(f"   Plot plan: {json.dumps(plot_plan, ensure_ascii=False)[:100]}...")
            start = time.time()
            spec_response = await client.chat.completions.create(**spec_request)
            spec_latency = (time.time() - start) * 1000
            
            spec_raw = spec_response.choices[0].message.content
            spec_result = extract_json_from_response(spec_raw)
            
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
            
            plot_data = spec_result.get("plot", {}).get("plotly", {}) if isinstance(spec_result, dict) else {}
            print(f"✅ Plot Spec SUCCESS")
            print(f"   Request ID: {spec_response.id}")
            print(f"   Latency: {spec_latency:.0f}ms")
            if isinstance(spec_result, dict):
                print(f"   plot_id: {spec_result.get('plot', {}).get('plot_id')}")
            print(f"   traces: {len(plot_data.get('data', []))}")
            
            # Safely get layout title
            layout = plot_data.get("layout", {}) if isinstance(plot_data, dict) else {}
            title_text = layout.get("title", {}) if isinstance(layout, dict) else {}
            if isinstance(title_text, dict):
                title_text = title_text.get("text", "N/A")
            elif isinstance(title_text, str):
                title_text = title_text
            else:
                title_text = "N/A"
            print(f"   layout.title: {title_text}")
            
            # Save plotly JSON sample
            if plot_data.get('data'):
                print(f"\n   Sample trace[0]:")
                trace0 = plot_data['data'][0]
                print(f"     type: {trace0.get('type')}")
                print(f"     name: {trace0.get('name')}")
                print(f"     x length: {len(trace0.get('x', []))}")
                print(f"     y length: {len(trace0.get('y', []))}")
            
        except Exception as e:
            results["plot_spec"] = {"success": False, "error": str(e)}
            print(f"❌ Plot Spec FAILED: {e}")
    
    # Save results
    output_file = "standard_forced_plot_spec.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*70}")
    print(f"FULL RESULTS SAVED TO: {output_file}")
    print('='*70)
    
    # Summary
    print("\nSUMMARY:")
    solve = results.get("solve", {})
    trigger = results.get("plot_trigger", {})
    spec = results.get("plot_spec", {})
    
    # Get traces count safely
    traces_count = "N/A"
    if spec.get("success") and isinstance(spec.get("parsed"), dict):
        plotly_data = spec.get("parsed", {}).get("plot", {}).get("plotly", {}).get("data", [])
        traces_count = len(plotly_data)
    
    print(f"Solve:      {'✅' if solve.get('success') else '❌'} {solve.get('request_id', 'FAILED')}")
    print(f"Plot Trigger: {'✅' if trigger.get('success') else '❌'} plot_needed={trigger.get('parsed', {}).get('plot_needed', 'N/A')}")
    print(f"Plot Spec:  {'✅' if spec.get('success') else '❌'} traces={traces_count}")
    
    return results


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)
    
    asyncio.run(test_standard_with_forced_plot_spec())
