import os
import json
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

    async def solve_problem(self, problem_text: str, context: str = "") -> dict:
        """
        Orchestrates the solving process using OpenAI.
        """
        if not self.client:
             return {
                 "summary": "Error: API Key Missing",
                 "steps": [],
                 "final_answer": "Please configure OPENAI_API_KEY on the backend."
             }

        system_prompt = """You are an expert math and physics tutor. 
        Your goal is to solve the student's problem step-by-step.
        
        OUTPUT FORMAT:
        Return ONLY valid JSON with this structure:
        {
            "problem": {
                "goal": "Brief description of the objective (e.g. 'Solve for x')",
                "latex": "The original problem in LaTeX"
            },
            "solution": {
                "steps": [
                    {
                        "index": 1,
                        "title": "Step Heading",
                        "explanation": "Clear pedagogical explanation without math",
                        "math": {
                            "latex_lines": ["Line 1 of math", "Line 2 of math"]
                        }
                    }
                ],
                "final_answer": "The final concise result"
            },
            "verification": {
                "methods_used": [
                    {
                        "method": "substitution / sanity check / dimension matching",
                        "description": "How we verified",
                        "work": {
                            "latex_lines": ["Latex showing the check"]
                        },
                        "conclusion": "Pass/Fail statement"
                    }
                ]
            },
            "concepts": [
                {
                    "title": "Concept Name",
                    "category": "Subject area",
                    "description": "Brief explanation",
                    "tags": ["tag1", "tag2"]
                }
            ]
        }
        
        RULES:
        - Use LaTeX for ALL math expressions in latex_lines.
        - DO NOT put math inside 'explanation' if possible; use 'math.latex_lines'.
        - Be educational and clear.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Problem: {problem_text}\nContext: {context}"}
                ],
                temperature=0.2
            )
            
            data = json.loads(response.choices[0].message.content)
            return data
            
        except Exception as e:
            print(f"Solver Error: {e}")
            return {
                "summary": "Error generating solution",
                "steps": [{"title": "Error", "content": str(e)}],
                "final_answer": "Could not solve."
            }

    async def get_chat_response(self, query: str, session_context: dict) -> dict:
        """
        Handles follow-up questions from the student.
        Returns { "relevant": bool, "content": str }
        """
        if not self.client:
            return {"relevant": True, "content": "API Key Missing. Check backend config."}

        system_prompt = f"""You are an expert tutor. The current problem being discussed is:
        Goal: {session_context.get('problem', {}).get('goal')}
        Math: {session_context.get('problem', {}).get('latex')}
        
        RULES:
        1. Determine if the student's question is related to this math/physics problem or tutoring in general.
        2. If NOT related (e.g. asking about celebrities, general trivia, unrelated tasks), set "relevant" to false and briefly explain why you can only help with the current problem.
        3. If related, set "relevant" to true and provide a clear, encouraging answer using LaTeX for math.
        4. Return ONLY JSON: {{"relevant": boolean, "content": "string"}}
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Chat Response Error: {e}")
            return {"relevant": True, "content": "I'm having trouble thinking right now. Could you ask again?"}

solver_service = SolverService()
