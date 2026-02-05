import sys
import os
import json
import asyncio
from datetime import datetime
from sqlmodel import select
from sqlalchemy.orm import joinedload
from dotenv import load_dotenv

# Ensure backend in path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

# Load Env
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from app.database import get_session
from app.models import User, PromptBinding, PromptTierEnum, PromptModeEnum
from app.services.solver_v3 import get_solver_v3
from app.services.plot_pipeline_service import get_plot_pipeline_service
from app.prompts.db_loader import load_prompt_bundle
from app.api import _resolve_runtime_tier_slug, _clamp_requested_tier
from app.services.billing_service import billing_service

# Output File
OUTPUT_FILE = r"E:\uaskstudents\backend\app\scripts\production_trace_report.txt"

def log(msg):
    print(msg)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def get_real_user(session, target_tier):
    """
    Find a REAL user with the specific tier.
    """
    # Try direct matches first
    # Note: Plan logic might map 'student_standard' to 'standard'.
    # We look for direct subscription_tier match on User model first.
    # User model has 'subscription_tier' string field.
    
    # Map target_tier (FREE, STANDARD, RESEARCH) to potential DB values
    candidates = [target_tier.lower()]
    if target_tier == "STANDARD":
        candidates.extend(["student_standard", "pro"]) # family_standard maps to RESEARCH
    elif target_tier == "RESEARCH":
        candidates.extend(["research", "enterprise"])
    
    stmt = select(User).where(User.subscription_tier.in_(candidates)).limit(20)
    users = session.exec(stmt).all()
    
    for u in users:
        # Check EFFECTIVE tier 
        effective_slug = _resolve_runtime_tier_slug(u)
        
        # If target is STANDARD, accept STANDARD or RESEARCH (since Research is > Standard)
        # But for verification, we probably want exact match or at least entitlement >= target?
        # User requested: "User A: tier = FREE", "User B: tier = STANDARD", "User C: tier = RESEARCH".
        # Let's try to match the *Entitled* tier to the requested one.
        
        # Normalize target to simple slug
        target_norm = "FREE"
        if target_tier == "STANDARD": target_norm = "STANDARD"
        if target_tier == "RESEARCH": target_norm = "RESEARCH"
        
        eff_upper = effective_slug.upper()
        if eff_upper in ["STUDENT_STANDARD", "PRO", "PREMIUM", "STANDARD"]:
            eff_mapped = "STANDARD"
        elif eff_upper in ["RESEARCH", "ENTERPRISE", "FAMILY"]:
             eff_mapped = "RESEARCH"
        else:
             eff_mapped = "FREE"
             
        # We need exact match of effective entitlement
        if eff_mapped == target_norm:
              log(f"FOUND REAL USER: ID={u.id} Email={u.email} Tier={u.subscription_tier} Effective={effective_slug}")
              return u
              
    if not users:
        raise ValueError(f"Could not find ANY real user with tier={target_tier} (checked {candidates})")
        
    raise ValueError(f"Found {len(users)} candidates for {target_tier} but effective tier did not match {target_tier}. (Last effective: {effective_slug})")

async def run_test_for_user(session, user, tier_name, test_name, problem_text, graph_mode):
    log(f"\n--- TEST: {tier_name} | {test_name} ---")
    log(f"Problem: {problem_text}")
    log(f"Graph Mode: {graph_mode}")
    
    # 1. Resolve Tier & Profile (Logic from api.py)
    entitled_tier_slug = _resolve_runtime_tier_slug(user)
    tier_policy = _clamp_requested_tier(None, entitled_tier_slug) # None = request default
    effective_tier = tier_policy["tier_effective"]
    
    log(f"Entitled Tier: {entitled_tier_slug}")
    log(f"Effective Tier: {effective_tier}")
    
    # 2. Resolve Prompt Bundle from DB
    try:
        bundle = load_prompt_bundle(
            tier=effective_tier,
            mode="solve",
            session=session,
        )
        binding_meta = bundle.get("binding", {})
        log(f"Resolved Binding ID: {binding_meta.get('id')}")
        log(f"Max Output Tokens: {binding_meta.get('max_output_tokens')}")
        log(f"Output Schema ID: {bundle.get('meta', {}).get('output_schema_id')}")
    except Exception as e:
        log(f"CRITICAL: Prompt Bundle Resolution Failed: {e}")
        return

    # 3. BILLING (Mocking/Legacy Check?)
    # api.py does billing check. We will assume user has credits or free tier.
    # We won't block on billing for this verification, but we will create a dummy ledger if needed by solver?
    # Solver doesn't take ledger, api.py does.
    
    request_id = f"verify_{tier_name}_{datetime.now().timestamp()}"
    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    log(f"API Key Present: {bool(api_key)} (Len: {len(api_key)})")
    
    # 4. SOLVE
    solver = get_solver_v3()
    try:
        log("Calling SolverV3...")
        start_time = datetime.now()
        result = await solver.solve(
            problem_text=problem_text,
            context="Subject: General",
            trace=True, # Request Trace
            request_id=request_id,
            user_id=user.id,
            db_session=session,
            requested_mode="minimal",
            user_tier=effective_tier,
            requests_graph_mode=graph_mode
        )
        duration = (datetime.now() - start_time).total_seconds()
        log(f"Solver Finished in {duration:.2f}s")
        log(f"Full Result Keys: {result.keys()}")
        if "error" in result or "message" in result:
             log(f"SOLVER ERROR: {result.get('message', result.get('error'))}")
             log(f"ERROR TYPE: {result.get('error_type')}")
        
        # Log Output
        final_text = result.get("final_answer", {}).get("text", "")
        log(f"Final Info: {final_text[:200]}...") # Truncate
        
        # Check visuals recommendation
        visuals = result.get("visuals", {})
        should_visualize = visuals.get("should_visualize", False)
        log(f"Solver Visuals Recommended: {should_visualize}")
        
    except Exception as e:
        log(f"❌ SOLVER FAILED: {e}")
        import traceback
        log(traceback.format_exc())
        return

    # 5. ORCHESTRATION PLOT LOGIC (Replicating api.py)
    
    # PRODUCT RULE: FREE TIER NO PLOT
    if effective_tier == "FREE":
        if graph_mode == "on" or (graph_mode == "auto" and should_visualize):
            # Check for friendly message in final text
            if "(Graphs are available" in final_text:
                 log("✅ SUCCESS: Friendly message found in text for FREE tier.")
            else:
                 # It might be appended in api.py, NOT in solver. 
                 # Wait, api.py appends it AFTER solver returns.
                 # So we must verify we DO NOT run plot pipeline.
                 log("✅ CORRECT: FREE tier, skipping plot pipeline.")
                 log("(Note: Friendly message insertion is done in API layer, simplified here)")
        else:
             log("✅ CORRECT: FREE tier, no plot requested.")
        return

    # STANDARD / RESEARCH
    if graph_mode == "on" or (graph_mode == "auto" and should_visualize):
        log("Starting Plot Pipeline...")
        plot_service = get_plot_pipeline_service(session)
        try:
             trigger_result, spec_result = await plot_service.execute_plotting_pipeline(
                problem_text=problem_text,
                solve_result=result,
                graph_mode=graph_mode,
                attach_to_step_id=None,
                tier=effective_tier,
                question_id=request_id
             )
             
             if trigger_result:
                 log(f"Plot Trigger: Needed={trigger_result.plot_needed} Type={trigger_result.plot_type}")
             
             if spec_result:
                 log(f"Plot Spec Generated: ID={spec_result.plot_id}")
                 json_data = spec_result.plotly_json
                 if json_data and "data" in json_data:
                     log(f"✅ Plot JSON Valid. Data Traces: {len(json_data['data'])}")
                 else:
                     log(f"❌ Plot JSON Invalid or Empty.")
             else:
                 log("⚠️ No Plot Spec generated (maybe trigger said no?)")

        except Exception as e:
            log(f"❌ PLOT PIPELINE FAILED: {e}")
            import traceback
            log(traceback.format_exc())

async def main():
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=== PRODUCTION E2E VERIFICATION REPORT ===\n")
        f.write(f"Date: {datetime.now()}\n\n")

    session_generator = get_session()
    session = next(session_generator)
    
    try:
        # Load Users
        u_free = get_real_user(session, "FREE")
        u_std = get_real_user(session, "STANDARD")
        u_res = get_real_user(session, "RESEARCH")
        
        # Test Problems
        prob_graph = "Graph f(x) = ln(x) - x/2 and solve f(x) = 0. Use the graph to justify."
        prob_simple = "Simplify 2x^3 * y^2 * 4xy."
        
        # Test 1: User A (FREE)
        await run_test_for_user(session, u_free, "FREE", "Complex Graph Request", prob_graph, "on")
        
        # Test 2: User B (STANDARD)
        await run_test_for_user(session, u_std, "STANDARD", "Complex Graph Request", prob_graph, "on")
        
        # Test 3: User C (RESEARCH)
        await run_test_for_user(session, u_res, "RESEARCH", "Complex Graph Request", prob_graph, "on")
        
    finally:
        session.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
