import os
import json
import asyncio
from openai import AsyncOpenAI

async def test_full_cycle():
    """
    Demonstrates the complete request/response cycle with OpenAI.
    Shows both the system prompt sent and the JSON response received.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No API key found")
        return
    
    client = AsyncOpenAI(api_key=api_key)
    model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
    
    # This is the EXACT system prompt sent to OpenAI
    system_prompt = """You are an expert math and physics tutor.
Your goal is to solve the student's problem step-by-step.

VISUALS:
You MUST include a "visuals" array if either:
1. The user explicitly asks for it (keywords: graph, plot, draw, sketch).
2. The problem is about finding the equation of a line passing through specific points (always draw the graph at the end).
Use "function_plot_request" type for curves or "line_plot" for lines between points.
DO NOT use "function_plot" directly yourself.

OUTPUT FORMAT:
Return ONLY valid JSON with this structure:
{
  "problem": {
    "goal": "Brief description",
    "latex": "Original problem latex"
  },
  "solution": {
    "steps": [
      {
        "index": 1,
        "title": "Step Title",
        "explanation": "Explanation text...",
        "math": { "latex_lines": ["..."] },
        "visual_refs": ["v1"]
      }
    ],
    "final_answer": "Concise answer"
  },
  "verification": {
    "methods_used": [
      {
        "name": "Substitution Check",
        "description": "Verify by substituting the solution back into the original equation",
        "steps": ["2(6)+7 = 12+7 = 19 ✓"]
      }
    ]
  },
  "concepts": [
    {
      "name": "Linear Equations",
      "description": "Equations where the variable has an exponent of 1"
    },
    {
      "name": "Inverse Operations",
      "description": "Using opposite operations (subtraction/division) to isolate variables"
    }
  ],
  "visuals": [
    {
      "id": "v1",
      "type": "function_plot_request", 
      "title": "Graph of y=x^2",
      "function": { "latex": "y=x^2", "variable": "x" },
      "domain": { "x_min_latex": "-5", "x_max_latex": "5" }
    }
  ],
  "response_intent": ["step_by_step"]
}

RULES:
- Use LaTeX for math.
- ALWAYS include "verification" with at least one method (substitution, graphical check, etc.)
- ALWAYS include "concepts" array with 2-4 relevant mathematical concepts
- If visual_required is set, you MUST provide at least one visual.
- For function requests, provide valid LaTeX for the function (e.g. "y=\\sin(x)").
"""
    
    user_query = "Problem: Solve for x: 2x+7=19\\nContext: "
    
    print("=" * 80)
    print("OPENAI API REQUEST")
    print("=" * 80)
    print(f"Model: {model}")
    print(f"Response Format: json_object")
    print(f"Temperature: NOT SENT (GPT-5 doesn't support it)")
    print()
    print("System Prompt:")
    print("-" * 80)
    print(system_prompt)
    print("-" * 80)
    print()
    print("User Query:")
    print("-" * 80)
    print(user_query)
    print("-" * 80)
    print()
    
    # Build params (same logic as solver.py)
    params = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "timeout": 30
    }
    
    # Only add temperature for non-GPT-5 models
    if "gpt-5" not in model.lower():
        params["temperature"] = 0.2
    
    print("Making OpenAI API call...")
    print()
    
    try:
        response = await client.chat.completions.create(**params)
        
        print("=" * 80)
        print("OPENAI API RESPONSE")
        print("=" * 80)
        print(f"Model Used: {response.model}")
        print(f"Finish Reason: {response.choices[0].finish_reason}")
        print(f"Total Tokens: {response.usage.total_tokens if response.usage else 'N/A'}")
        print()
        print("JSON Content:")
        print("-" * 80)
        
        # Parse and pretty-print the JSON response
        data = json.loads(response.choices[0].message.content)
        print(json.dumps(data, indent=2))
        print("-" * 80)
        print()
        
        # Validation
        print("=" * 80)
        print("VALIDATION")
        print("=" * 80)
        print(f"✓ Has 'problem' field: {('problem' in data)}")
        print(f"✓ Has 'solution' field: {('solution' in data)}")
        print(f"✓ Has 'verification' field: {('verification' in data)}")
        print(f"✓ Has 'concepts' field: {('concepts' in data)}")
        print(f"✓ Has 'visuals' field: {('visuals' in data)}")
        print(f"✓ Number of steps: {len(data.get('solution', {}).get('steps', []))}")
        print(f"✓ Number of concepts: {len(data.get('concepts', []))}")
        print(f"✓ Final answer: {data.get('solution', {}).get('final_answer', 'N/A')}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_full_cycle())
