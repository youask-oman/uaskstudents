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
            "summary": "Brief 1-sentence summary of the approach",
            "steps": [
                {
                    "title": "Step Title",
                    "content": "Explanation with LaTeX math in $...$ or $$...$$"
                }
            ],
            "related_concepts": ["Concept 1", "Concept 2"],
            "final_answer": "The final result"
        }
        
        RULES:
        - Use LaTeX for ALL math expressions.
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

solver_service = SolverService()
