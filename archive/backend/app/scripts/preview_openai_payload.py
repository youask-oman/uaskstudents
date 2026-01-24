import json
import os
import sys
from app.prompts import get_prompt
from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3

def generate_preview():
    # 1. Define the Input Problem
    problem_text = "Find the value(s) of x that satisfy the linear equation 3(x - 2) = 15"
    
    # 2. Simulate Student Context (replicating api.py logic)
    # Using a typical Grade 10 student profile in California, USA
    country = "USA"
    province = "CA"
    grade = "Grade 10"
    curriculum = "California Common Core State Standards" 
    
    student_context_parts = []
    if grade:
        student_context_parts.append(f"Grade Level: {grade}")
    
    student_context_parts.append(f"Location: {province}, {country}")
    student_context_parts.append(f"Curriculum: {curriculum}")
    
    context_str = ""
    context_str += f"\n\n[STUDENT CONTEXT - Trusted metadata, adapt to local conventions]\n"
    context_str += "\n".join(student_context_parts)
    context_str += "\n\nNOTE: Use appropriate units (metric for Canada, customary for USA), spelling conventions, and grade-appropriate terminology."
    
    # 3. Construct User Message (Exact logic from SolverV3)
    user_message = f"""Problem: {problem_text}

Context: {context_str if context_str else "No additional context provided."}

**CRITICAL**: Return ONLY strictly valid JSON matching the schema (v1.0).
- visuals.should_visualize = true for any graphable content
- verification is a SINGLE object (method, work_latex, conclusion)
- refusal.is_refusal = true ONLY if safety policy requires it
- Avoid nulls where possible
"""
    # 4. Get System Prompt (from Registry)
    try:
        system_prompt = get_prompt("solver_system", "v3")
    except Exception as e:
        system_prompt = f"Error loading system prompt: {e}"

    # 5. Get JSON Schema (Strict Mode)
    try:
        json_schema = get_json_schema_for_openai_v3()
    except Exception as e:
        json_schema = {"error": str(e)}

    # 6. Prepare Output Structure
    output = {
        "meta": {
            "description": "Preview of OpenAI API Payload",
            "problem": problem_text,
            "generated_at": "Pre-flight check"
        },
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "solve_response_v3",
                "strict": True,
                "schema": json_schema
            }
        }
    }
    
    # Write to file inside container
    output_path = "/tmp/openai_payload_preview.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"Preview successfully generated at {output_path}")

if __name__ == "__main__":
    generate_preview()
