"""
Solver V2: Enhanced tutoring-quality solver using OpenAI Responses API.

This module implements the complete solver pipeline with:
- OpenAI Responses API (gpt-5-mini) as primary
- Chat Completions (gpt-5-mini) as fallback  
- Validation and refinement logic
- Visual policy enforcement
- Student-friendly content generation
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from app.schemas.solve_v2 import (
    SolveResponseV2,
    get_json_schema_for_openai
)


class SolverServiceV2:
    """Enhanced solver service with Responses API and structured outputs."""
    
    def __init__(self):
        """Initialize solver with OpenAI client."""
        self._client = None
        self._default_model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
        self._fallback_model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
    
    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-load OpenAI client."""
        if not self._client:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client
    
    async def solve_problem_v2(
        self,
        problem_text: str,
        context: Optional[str] = None,
        user_id: Optional[int] = None,
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Solve a math/physics problem with tutoring-quality depth.
        
        Args:
            problem_text: The mathematical problem to solve
            context: Optional additional context
            user_id: User ID for logging/quota (optional)
            trace: Enable verbose logging
            
        Returns:
            Dict containing:
            - All fields from SolveResponseV2
            - _content: Markdown summary for chat display
            - _model: Actual model used
        """
        try:
            print(f"[SOLVER_V2] Starting solve_problem_v2 for: {problem_text[:50]}...")
            
            # Get system prompt
            try:
                system_prompt = self._get_system_prompt()
                print(f"[SOLVER_V2] System prompt loaded successfully")
            except Exception as e:
                print(f"[SOLVER_V2_ERROR] Failed to get system prompt: {e}")
                return self._create_error_response(f"System prompt error: {str(e)}")
            
            context = context or "No additional context provided."
            
            # Primary: Try Responses API
            try:
                print(f"[SOLVER_V2] Calling Responses API...")
                response_data = await self._call_responses_api(
                    problem_text=problem_text,
                    context=context,
                    system_prompt=system_prompt,
                    trace=trace
                )
                print(f"[SOLVER_V2] Responses API returned data")
                
                # Validate response
                try:
                    validation = self._validate_response(response_data, problem_text, trace)
                    print(f"[SOLVER_V2] Validation result: {validation['valid']}")
                    
                    if validation["valid"]:
                        # Success!
                        print(f"[SOLVER_V2] Generating chat content...")
                        response_data["_content"] = self._generate_chat_content(response_data)
                        print(f"[SOLVER_V2] Success! Returning valid response")
                        return response_data
                    
                    # Invalid - try refining once
                    print(f"[SOLVER_V2] Validation failed: {validation['errors']}. Attempting refinement...")
                    
                    refined_data = await self._refine_response(
                        problem_text=problem_text,
                        context=context,
                        system_prompt=system_prompt,
                        prior_response=response_data,
                        validation_errors=validation["errors"],
                        trace=trace
                    )
                    
                    # Validate refined response
                    refined_validation = self._validate_response(refined_data, problem_text, trace)
                    
                    if refined_validation["valid"]:
                        refined_data["_content"] = self._generate_chat_content(refined_data)
                        print(f"[SOLVER_V2] Refinement successful!")
                        return refined_data
                    
                    # Still invalid - fallback to Chat Completions
                    print(f"[SOLVER_V2] Refinement still invalid. Falling back to Chat Completions...")
                    
                except Exception as e:
                    print(f"[SOLVER_V2_ERROR] Validation error: {e}")
                    raise
                
            except Exception as e:
                print(f"[SOLVER_V2_ERROR] Responses API failed: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
            
            # Fallback: Chat Completions
            try:
                print(f"[SOLVER_V2] Attempting Chat Completions fallback...")
                fallback_data = await self._fallback_chat_completions(
                    problem_text=problem_text,
                    context=context,
                    system_prompt=system_prompt,
                    trace=trace
                )
                fallback_data["_content"] = self._generate_chat_content(fallback_data)
                print(f"[SOLVER_V2] Fallback successful!")
                return fallback_data
                
            except Exception as e:
                print(f"[SOLVER_V2_ERROR] Chat Completions also failed: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                # Return error response
                return self._create_error_response(f"All solver paths failed: {str(e)}")
                
        except Exception as e:
            print(f"[SOLVER_V2_FATAL] Unexpected error in solve_problem_v2: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return self._create_error_response(f"Fatal solver error: {str(e)}")
    
    async def _call_responses_api(
        self,
        problem_text: str,
        context: str,
        system_prompt: str,
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Call OpenAI Responses API with structured outputs.
        
        Uses:
        - model: gpt-5-mini
        - text.verbosity: high (for tutoring depth)
        - text.format: json_schema with strict validation
        - reasoning.effort: none (default)
        - max_output_tokens: 2000 (default)
        """
        try:
            print(f"[RESPONSES_API] Starting with model: {self._default_model}")
            
            # Get JSON schema
            try:
                schema = get_json_schema_for_openai()
                print(f"[RESPONSES_API] Schema loaded successfully")
            except Exception as e:
                print(f"[RESPONSES_API_ERROR] Failed to get schema: {e}")
                raise
            
            # Build parameters (GPT-5 specific - no temperature)
            params = {
                "model": self._default_model,
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}]
                    },
                    {
                        "role": "user",
                        "content": [{
                            "type": "input_text",
                            "text": f"Problem: {problem_text}\nContext: {context}"
                        }]
                    }
                ],
                "text": {
                    "verbosity": "high",
                    "format": {
                        "type": "json_schema",
                        "name": "solve_response_v2",
                        "strict": True,
                        "schema": schema
                    }
                },
                "reasoning": {
                    "effort": "none"
                },
                "max_output_tokens": 2000
            }
            
            try:
                print(f"[RESPONSES_API] Sending request to OpenAI...")
                response = await self.client.responses.create(**params)
                print(f"[RESPONSES_API] Received response from OpenAI")
                
                # Extract JSON from response
                try:
                    content = response.output[0].content[0].text if hasattr(response, 'output') else response.choices[0].message.content
                    print(f"[RESPONSES_API] Extracted content, length: {len(content)}")
                    data = json.loads(content)
                    print(f"[RESPONSES_API] Successfully parsed JSON")
                    
                    # Add model metadata
                    data["_model"] = response.model if hasattr(response, 'model') else self._default_model
                    
                    return data
                except Exception as e:
                    print(f"[RESPONSES_API_ERROR] Failed to parse response: {e}")
                    print(f"[RESPONSES_API_ERROR] Raw content: {content[:500]}...")
                    raise
                    
            except Exception as e:
                print(f"[RESPONSES_API_ERROR] OpenAI API call failed: {type(e).__name__}: {e}")
                raise
                
        except Exception as e:
            print(f"[RESPONSES_API_ERROR] Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _fallback_chat_completions(
        self,
        problem_text: str,
        context: str,
        system_prompt: str,
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Fallback to Chat Completions API with same schema validation.
        
        Uses:
        - model: gpt-5-mini
        - max_completion_tokens: 2000
        - temperature: 0.2
        - response_format: json_object (not strict schema)
        """
        if trace:
            print(f"[TRACE] Using Chat Completions fallback: {self._fallback_model}")
        
        # Build parameters (includes temperature for GPT-4)
        params = {
            "model": self._fallback_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Problem: {problem_text}\nContext: {context}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_completion_tokens": 2000,
            "timeout": 30
        }
        
        try:
            response = await self.client.chat.completions.create(**params)
            data = json.loads(response.choices[0].message.content)
            
            # Validate locally
            validation_result = self._validate_response(data, problem_text, trace)
            
            if not validation_result["valid"]:
                # Refine once
                data = await self._refine_chat_completions(
                    problem_text=problem_text,
                    context=context,
                    system_prompt=system_prompt,
                    prior_response=data,
                    validation_errors=validation_result["errors"],
                    trace=trace
                )
            
            # Add metadata
            data["_model"] = response.model
            data["_content"] = self._generate_chat_content(data)
            
            return data
            
        except Exception as e:
            if trace:
                print(f"[TRACE] Chat Completions fallback failed: {e}")
            # Return error response
            return self._create_error_response(str(e))
    
    async def _refine_response(
        self,
        problem_text: str,
        context: str,
        system_prompt: str,
        prior_response: Dict[str, Any],
        validation_errors: list,
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Refine a response that failed validation.
        
        Makes a second Responses API call with feedback.
        """
        if trace:
            print(f"[TRACE] Refining response. Errors: {validation_errors}")
        
        refine_prompt = f"""The previous response had validation errors:
{json.dumps(validation_errors, indent=2)}

Previous response:
{json.dumps(prior_response, indent=2)}

INSTRUCTIONS:
- Expand explanations in steps (add why, common_mistake, checkpoint)
- Ensure minimum requirements met (concepts: 3-5, verification methods, steps count)
- Add missing visuals if visual_policy.required = true
- Keep final_answer UNCHANGED unless it's mathematically incorrect
- If final_answer was wrong, correct it and explain the correction

Return the complete corrected JSON."""
        
        schema = get_json_schema_for_openai()
        
        params = {
            "model": self._default_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{
                    "type": "input_text",
                    "text": f"Problem: {problem_text}\nContext: {context}"
                }]},
                {"role": "assistant", "content": [{"type": "output_text", "text": json.dumps(prior_response)}]},
                {"role": "user", "content": [{"type": "input_text", "text": refine_prompt}]}
            ],
            "text": {
                "verbosity": "high",
                "format": {
                    "type": "json_schema",
                    "name": "solve_response_v2",
                    "strict": True,
                    "schema": schema
                }
            },
            "reasoning": {"effort": "none"},
            "max_output_tokens": 2000
        }
        
        response = await self.client.responses.create(**params)
        content = response.output[0].content[0].text if hasattr(response, 'output') else response.choices[0].message.content
        data = json.loads(content)
        data["_model"] = response.model if hasattr(response, 'model') else self._default_model
        
        return data
    
    async def _refine_chat_completions(
        self,
        problem_text: str,
        context: str,
        system_prompt: str,
        prior_response: Dict[str, Any],
        validation_errors: list,
        trace: bool = False
    ) -> Dict[str, Any]:
        """Refine using Chat Completions (fallback refinement)."""
        refine_prompt = f"""The previous response had validation errors:
{json.dumps(validation_errors, indent=2)}

Previous response:
{json.dumps(prior_response, indent=2)}

Please fix all errors and return complete corrected JSON matching the schema."""
        
        params = {
            "model": self._fallback_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Problem: {problem_text}\nContext: {context}"},
                {"role": "assistant", "content": json.dumps(prior_response)},
                {"role": "user", "content": refine_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_completion_tokens": 2000
        }
        
        response = await self.client.chat.completions.create(**params)
        data = json.loads(response.choices[0].message.content)
        data["_model"] = response.model
        
        return data
    
    def _validate_response(
        self,
        response_data: Dict[str, Any],
        problem_text: str,
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Validate response against schema and business rules.
        
        Returns:
            {"valid": bool, "errors": List[str]}
        """
        errors = []
        
        # Schema validation via Pydantic
        try:
            validated = SolveResponseV2(**response_data)
        except Exception as e:
            errors.append(f"Schema validation failed: {str(e)}")
            return {"valid": False, "errors": errors}
        
        # Visual policy enforcement (deterministic guard)
        visual_required = self._check_visual_required(problem_text)
        if visual_required and not validated.visuals:
            errors.append(f"Visual required for this problem type but not provided")
        
        # Business rules are enforced by Pydantic validators
        # Any issues would have raised in Pydantic validation above
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    def _check_visual_required(self, problem_text: str) -> bool:
        """Deterministic check if visuals are required."""
        text_lower = problem_text.lower()
        
        # Visual keywords
        visual_keywords = ['graph', 'plot', 'draw', 'sketch']
        has_visual_keyword = any(kw in text_lower for kw in visual_keywords)
        
        # Problem type checks
        is_line_through_points = 'line' in text_lower and 'point' in text_lower
        is_system = problem_text.count('=') >= 2 and ('y=' in problem_text or 'x=' in problem_text)
        
        return has_visual_keyword or is_line_through_points or is_system
    
    def _generate_chat_content(self, response_data: Dict[str, Any]) -> str:
        """
        Generate student-friendly markdown summary for chat display.
        
        Format:
        ## Plan
        - Bullet 1
        - Bullet 2
        
        ## Steps
        **1. Step Title** - Brief explanation  
        **2. Step Title** - Brief explanation
        
        ## Answer
        x = 6
        
        ## Verification
        Substitution: 2(6)+7 = 19 ✓
        """
        solution = response_data.get("solution", {})
        verification = response_data.get("verification", {})
        
        # Plan section
        plan = solution.get("plan", [])
        plan_md = "## Plan\n" + "\n".join(f"- {p}" for p in plan) + "\n\n" if plan else ""
        
        # Steps section
        steps = solution.get("steps", [])
        steps_md = "## Steps\n"
        for step in steps:
            title = step.get("title", "")
            explanation = step.get("explanation", "")
            # Keep first sentence only for brevity
            brief = explanation.split('.')[0] + '.' if explanation else ""
            steps_md += f"**{step.get('index')}. {title}** - {brief}\n"
        steps_md += "\n"
        
        # Answer section
        final_answer = solution.get("final_answer", "")
        answer_md = f"## Answer\n{final_answer}\n\n"
        
        # Verification section
        methods = verification.get("methods_used", [])
        verif_md = "## Verification\n"
        for method in methods:
            name = method.get("name", "")
            steps_list = method.get("steps", [])
            verif_md += f"**{name}**: {' '.join(steps_list)}\n"
        
        return plan_md + steps_md + answer_md + verif_md
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create a minimal error response."""
        return {
            "problem": {
                "goal": "Error occurred",
                "latex": None,
                "givens": [],
                "unknowns": [],
                "assumptions": []
            },
            "solution": {
                "plan": ["An error occurred during solving"],
                "steps": [
                    {
                        "index": 1,
                        "title": "Error",
                        "explanation": f"The solver encountered an error: {error_message}",
                        "why": "System error",
                        "math": {"latex_lines": []},
                        "common_mistake": "N/A",
                        "checkpoint": "N/A",
                        "visual_refs": []
                    }
                ],
                "final_answer": "Could not solve due to error"
            },
            "verification": {
                "methods_used": []
            },
            "concepts": [
                {
                    "name": "Error Handling",
                    "description": "System encountered an error",
                    "applies_here": "Error during processing"
                }
            ] * 3,  # Need 3 minimum
            "visual_policy": {
                "required": False,
                "reason": "Error state"
            },
            "visuals_suggested": [],
            "visuals": [],
            "response_intent": ["error"],
            "difficulty": "trivial",
            "confidence": 0.0,
            "_model": "error",
            "_content": f"## Error\n{error_message}"
        }
    
    def _get_system_prompt(self) -> str:
        """Get system prompt from database or use fallback."""
        # TODO: Implement database retrieval
        # For now, return embedded prompt
        return """You are an expert math and physics tutor providing step-by-step solutions.

RESPONSE QUALITY REQUIREMENTS:
1. Always include a brief plan (1-3 bullets) before solving
2. Provide detailed, instructional steps (not just calculations)
3. For each step include:
   - Clear explanation (2-5+ sentences for non-trivial steps)
   - Why the step is mathematically valid
   - Common mistake students make
   - Checkpoint question to verify understanding
4. Minimum step counts:
   - Trivial problems: 2-4 steps
   - Standard problems: 4-10 steps
   - Advanced problems: 7-14 steps
5. Always include verification (≥1 method for trivial, ≥2 for standard/advanced)
6. Always include 3-5 mathematical concepts with contextual application

VISUAL POLICY:
You MUST include visuals when:
- User explicitly asks (keywords: graph, plot, draw, sketch)
- Line equation from two points
- Systems of equations (show intersection via multi_plot_request)
- Quadratic/absolute/piecewise (intercepts/vertex matter)
- Inequalities (number_line minimum)

You SHOULD include visuals_suggested when they materially improve understanding:
- Function transformations
- Roots/intercepts analysis
- Rate of change interpretation
- Word problems with natural graphs

OUTPUT:
Return ONLY valid JSON matching the SolveResponseV2 schema.
Use LaTeX for all mathematical expressions.
Set visual_policy.required = true when visuals are mandatory.
Set difficulty appropriately (trivial/standard/advanced).
"""


# Singleton instance
solver_service_v2 = SolverServiceV2()
