
import asyncio
import json
import os
from sqlmodel import Session
from app.database import engine
from app.models import User
from app.services.solver_v3 import get_solver_v3
from app.llm_profiles.profile_resolver import ProfileResolver

async def test_specific_problem():
    problem = "Find and classify the critical points of f(x) = x^3 - 3x + ln(x) on its domain."
    print(f"Testing Problem: {problem}")
    
    with Session(engine) as session:
        # Resolve user (usually ID 1 is the admin/test user)
        user = session.get(User, 1)
        if not user:
            print("User 1 not found, trying to find any user...")
            from sqlmodel import select
            user = session.exec(select(User)).first()
        
        if not user:
            print("No users found in database.")
            return

        print(f"Using User: {user.email} (ID: {user.id})")
        
        solver = get_solver_v3()
        request_id = "test_research_manual"
        
        # We simulate what api.py does: resolve profile then call solver
        profile = ProfileResolver.resolve_profile(
            session=session,
            user=user,
            requested_mode="detailed",
            force_tier="RESEARCH"
        )
        
        print(f"Profile Resolved: Tier={profile.tier}, Mode={profile.mode}, MaxTokens={profile.max_output_tokens}")
        
        # Use solve_stream since we want to see if it holds up under the streaming logic
        full_content = ""
        print("--- START LLM OUTPUT ---")
        async for chunk in solver.solve_stream(
            problem_text=problem,
            context="Subject: Calculus",
            trace=True,
            request_id=request_id,
            max_output_tokens=profile.max_output_tokens,
            system_prompt=profile.system_prompt_content,
            developer_prompt=profile.developer_prompt_content,
            json_schema_config=profile.json_schema_content,
            requested_mode="detailed"
        ):
            if chunk["type"] == "delta":
                print(chunk["text"], end="", flush=True)
                full_content += chunk["text"]
            elif chunk["type"] == "error":
                print(f"\n[ERROR] {chunk['error']}")
            elif chunk["type"] == "telemetry":
                print("\n--- END LLM OUTPUT ---")
                print(f"Telemetry: {json.dumps(chunk['telemetry'], indent=2)}")
        
        # Validate final content
        try:
            data = json.loads(full_content)
            print("\n[SUCCESS] Final JSON is valid.")
            
            with open("scripts/solution_summary.txt", "w", encoding="utf-8") as f:
                f.write(f"Problem: {problem}\n")
                f.write(f"Tier: RESEARCH\n")
                f.write("-" * 40 + "\n")
                
                if "steps" in data:
                    f.write(f"Assumptions: {', '.join(data.get('assumptions', []))}\n\n")
                    f.write("Steps:\n")
                    for i, step in enumerate(data.get("steps", [])):
                        f.write(f"{i+1}. {step.get('title')}\n")
                        f.write(f"   {step.get('explanation')}\n")
                        if step.get("math_latex"):
                            f.write(f"   Latex: {' '.join(step.get('math_latex'))}\n")
                        f.write("\n")
                    
                    final = data.get("final_answer", {})
                    f.write(f"Final Answer: {final.get('answer_text')}\n")
                    f.write(f"Latex: {final.get('answer_latex')}\n")
                elif "solution" in data:
                    sol = data["solution"]
                    f.write(f"Assumptions: {', '.join(data.get('assumptions', []))}\n\n")
                    f.write("Steps:\n")
                    for i, step in enumerate(sol.get("steps", [])):
                        f.write(f"{i+1}. {step.get('title')}\n")
                        f.write(f"   {step.get('explanation')}\n")
                        if step.get("math_latex"):
                            f.write(f"   Latex: {' '.join(step.get('math_latex'))}\n")
                        f.write("\n")
                    
                    final = sol.get("final_answer", {})
                    f.write(f"Final Answer: {final.get('answer_text')}\n")
                    f.write(f"Latex: {final.get('answer_latex')}\n")
                
            print("Summary written to scripts/solution_summary.txt")
        except Exception as e:
            print(f"\n[FAIL] JSON Parsing Error: {e}")
            # If it failed, let's see why (truncation?)
            print(f"Total Content Length: {len(full_content)}")
            if len(full_content) > 0:
                print(f"Last 100 characters: ...{full_content[-100:]}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    
    asyncio.run(test_specific_problem())
