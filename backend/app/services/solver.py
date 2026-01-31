import os
import json
from app.utils import get_active_prompt
from openai import AsyncOpenAI

class SolverService:
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        if not self._client:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("WARNING: OPENAI_API_KEY not set. Solver features will fail.")
                return None
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client
    
    def _build_completion_params(self, model: str, messages: list, temperature: float = None, use_json: bool = True) -> dict:
        """
        Build completion parameters based on model type.
        GPT-5 models don't support temperature parameter.
        """
        params = {
            "model": model,
            "messages": messages,
            "timeout": 30
        }
        
        # Only add JSON format if requested
        if use_json:
            params["response_format"] = {"type": "json_object"}
        
        # Only add temperature for non-GPT-5 models
        if temperature is not None and "gpt-5" not in model.lower():
            params["temperature"] = temperature
        
        return params

    async def solve_problem(self, problem_text: str, context: str = "", db = None) -> dict:
        """
        Orchestrates the solving process using OpenAI.
        """
        if not self.client:
            return {
                "summary": "Error: API Key Missing",
                "steps": [],
                "final_answer": "Please configure OPENAI_API_KEY on the backend."
            }


        # Fallback to hardcoded if not in DB
        if db:
            system_prompt = get_active_prompt("math-solver", db)
        else:
            from app.database import engine, Session
            with Session(engine) as session:
                system_prompt = get_active_prompt("math-solver", session)
        
        if not system_prompt:
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
  "visuals": [
    {
      "id": "v1",
      "type": "function_plot_request", 
      "title": "Graph of y=x^2",
      "function": { "latex": "y=x^2", "variable": "x" },
      "domain": { "x_min_latex": "-5", "x_max_latex": "5" }
    },
    {
      "id": "v2",
      "type": "line_plot",
      "title": "Line through points",
      "markers": [
         { "label": "A", "x": 0, "y": 1 },
         { "label": "B", "x": 2, "y": 5 }
      ]
    }
  ],
  "response_intent": ["step_by_step", "visual_required"]
}

RULES:
- Use LaTeX for match.
- If visual_required is set, you MUST provide at least one visual.
- For function requests, provide valid LaTeX for the function (e.g. "y=\\sin(x)").
"""

        try:
            model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Problem: {problem_text}\nContext: {context}"}
            ]
            params = self._build_completion_params(model, messages, temperature=0.2)
            response = await self.client.chat.completions.create(**params)
            
            data = json.loads(response.choices[0].message.content)
            # Include actual model name from OpenAI response
            data["_model"] = response.model
            return data
            
        except Exception as e:
            print(f"Solver Error: {e}")
            return {
                "summary": "Error generating solution",
                "steps": [{"title": "Error", "content": str(e)}],
                "final_answer": "Could not solve."
            }

    async def get_chat_response(self, query: str, session_context: dict, db = None) -> dict:
        """
        Handles follow-up questions from the student.
        Returns { "relevant": bool, "content": str }
        """
        if not self.client:
            return {"relevant": True, "content": "API Key Missing. Check backend config."}
        
        # Extract problem context from various potential sources
        problem_text = (
            session_context.get('original_problem') or 
            session_context.get('problem', {}).get('original_text') or
            session_context.get('problem', {}).get('normalized_text') or
            session_context.get('problem', {}).get('goal') or 
            "Unknown Problem"
        )
        
        topic = (
            session_context.get('classification', {}).get('topic') or 
            session_context.get('problem', {}).get('topic') or 
            "Math"
        )
        
        # Extract steps if available
        steps_info = ""
        if 'steps' in session_context and session_context['steps']:
            steps_list = session_context['steps']
            if isinstance(steps_list, list) and len(steps_list) > 0:
                steps_info = "\n\nSOLUTION STEPS:\n"
                for step in steps_list:
                    if isinstance(step, dict):
                        step_num = step.get('index', '?')
                        step_title = step.get('title', 'Step')
                        steps_info += f"Step {step_num}: {step_title}\n"
        
        # Log full context for debugging
        print(f"[CHAT_DEBUG] Full context keys: {list(session_context.keys())}")
        print(f"[CHAT_DEBUG] Context: {json.dumps(session_context, indent=2, default=str)[:500]}...")
        print(f"[CHAT_DEBUG] Problem: {problem_text[:50]}...")
        print(f"[CHAT_DEBUG] Topic: {topic}")
        print(f"[CHAT_DEBUG] Steps available: {len(session_context.get('steps', []))}")
        print(f"[CHAT_DEBUG] Query: {query}")

        system_prompt = f"""You are a friendly and helpful math tutor assisting a student who just solved this problem:

Problem: {problem_text}
Topic: {topic}{steps_info}

The student is asking questions to better understand the solution. Your job is to:
- Answer their questions clearly and helpfully
- Explain concepts, steps, or methods used in the solution
- Provide alternative explanations or approaches when asked
- Use encouraging language
- Use LaTeX for math expressions (wrap in $ or $$)

Always answer questions about the problem, steps, concepts, or related topics.
Only politely decline if asked something completely unrelated (e.g., write a poem, unrelated trivia).

Respond in plain text. Be conversational and helpful."""


        try:
            model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-4o-mini")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            params = self._build_completion_params(model, messages, temperature=0.7, use_json=False)
            response = await self.client.chat.completions.create(**params)
            content = response.choices[0].message.content
            # Return in expected format
            return {"relevant": True, "content": content}
        except Exception as e:
            print(f"Chat Response Error: {e}")
            return {"relevant": True, "content": "I'm having trouble thinking right now. Could you ask again?"}

solver_service = SolverService()

