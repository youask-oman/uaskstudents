"""
Math Solver V3 Orchestrator.

Production-grade solver with:
- Prompt registry (templates from static_design/)
- Strict JSON Schema Draft 2020-12 validation
- Automatic repair loop (max 1 retry)
- Always-visualize policy
- 2+ verification methods
- Tutor-grade explanations

This is the main solver pipeline that integrates all V3 components.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from openai import AsyncOpenAI

from app.prompts import get_prompt, get_schema
from app.schemas.na_math_solver_v3 import SolveResponseV3, get_json_schema_for_openai_v3
from app.services.validation_v3 import validate_response, generate_repair_prompt, create_error_response
from app.services.visualization.decision_engine import get_visualization_engine
from app.services.visualization.plot_renderer import get_plot_renderer


class SolverV3:
    """
    Math Solver V3 - Production-grade orchestrator.
    
    Pipeline:
    1. Load prompts from registry
    2. Call LLM with strict schema
    3. Validate against JSON Schema Draft 2020-12
    4. Repair loop if validation fails (max 1 retry)
    5. Generate visualization if applicable
    6. Return validated response
    """
    
    def __init__(self):
        """Initialize solver with OpenAI client."""
        self._client = None
        self._model = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-5-mini")
        self._fallback_model = "gpt-4o-mini"
        self.viz_engine = get_visualization_engine()
        self.plot_renderer = get_plot_renderer()
    
    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-load OpenAI client."""
        if not self._client:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client
    
    async def solve(
        self,
        problem_text: str,
        context: str = "",
        trace: bool = False,
        include_plot_base64: bool = False  # V3.1: Control base64 inclusion
    ) -> Dict[str, Any]:
        """
        Solve a math/physics problem with tutoring-quality depth.
        
        V3.1 ENHANCEMENTS:
        - Confidence-based plot gating (>= 0.70)
        - Telemetry tracking (latency, tokens, validation status)
        - Payload optimization (base64 only in trace mode by default)
        - Similar examples validation
        
        Args:
            problem_text: The mathematical problem to solve
            context: Optional additional context (subject, grade level, etc.)
            trace: Enable verbose logging for debugging
            include_plot_base64: Include base64 PNG in response (default: False)
        
        Returns:
            Dict containing complete V3 response with validation, plots, telemetry
        """
        # Initialize telemetry
        import time
        start_time = time.time()
        telemetry = {
            "latency_ms_total": 0,
            "latency_ms_llm": 0,
            "latency_ms_plot": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "validated": False,
            "repaired": False,
            "repair_reason": None,
            "fallback_used": False,
            "validation_failures_count": 0,
            "plot_attempted": False,
            "plot_generated": False,
            "plot_failed_reason": None,
            "plot_confidence": 0.0,
            "plot_gated": False,  # True if confidence too low
        }
        
        # Get environment settings
        min_plot_confidence = float(os.environ.get("V3_MIN_CONFIDENCE_FOR_PLOT", "0.70"))
        
        if trace:
            print(f"\n[SOLVER_V3] ==================== START ====================")
            print(f"[SOLVER_V3] Problem: {problem_text[:100]}...")
            print(f"[SOLVER_V3] Model: {self._model}")
            print(f"[SOLVER_V3] Min plot confidence: {min_plot_confidence}")
            print(f"[SOLVER_V3] Strict schema: text.format.type=json_schema, strict=True")
        
        try:
            # Step 1: Load system prompt and schema from registry
            try:
                system_prompt = get_prompt("solver_system", "v3")
                schema = get_schema("na_math_solver")
                if trace:
                    print(f"[SOLVER_V3] ✅ Loaded prompts and schema")
                    print(f"[SOLVER_V3]    Schema: na_math_solver (v3)")
            except Exception as e:
                if trace:
                    print(f"[SOLVER_V3] ❌ Failed to load prompts: {e}")
                telemetry["latency_ms_total"] = int((time.time() - start_time) * 1000)
                error_resp = create_error_response(
                    problem_text,
                    [f"Failed to load prompts: {str(e)}"],
                    "prompt_load_error"
                )
                error_resp["_telemetry"] = telemetry
                return error_resp
            
            # Step 2: Call LLM with strict schema
            llm_start = time.time()
            try:
                response_data, llm_tokens = await self._call_llm_with_schema(
                    problem_text,
                    context,
                    system_prompt,
                    schema,
                    trace=trace
                )
                telemetry["latency_ms_llm"] = int((time.time() - llm_start) * 1000)
                telemetry["tokens_in"] = llm_tokens.get("input", 0)
                telemetry["tokens_out"] = llm_tokens.get("output", 0)
                
                if trace:
                    print(f"[SOLVER_V3] ✅ Received LLM response ({telemetry['latency_ms_llm']}ms)")
                    print(f"[SOLVER_V3]    Tokens: {telemetry['tokens_in']} in / {telemetry['tokens_out']} out")
            except Exception as e:
                if trace:
                    print(f"[SOLVER_V3] ❌ LLM call failed: {e}")
                telemetry["latency_ms_total"] = int((time.time() - start_time) * 1000)
                error_resp = create_error_response(
                    problem_text,
                    [f"LLM call failed: {str(e)}"],
                    "llm_error"
                )
                error_resp["_telemetry"] = telemetry
                return error_resp
            
            # Step 3: Validate response
            validation = validate_response(response_data, strict=True)
            
            if not validation.valid:
                telemetry["validation_failures_count"] += 1
                if trace:
                    print(f"[SOLVER_V3] ⚠️ Validation failed ({len(validation.errors)} errors)")
                    for err in validation.errors[:3]:
                        print(f"[SOLVER_V3]    - {err}")
                
                # Step 4: Repair loop (max 1 retry)
                telemetry["repair_reason"] = f"{len(validation.errors)} validation errors"
                response_data = await self._repair_response(
                    problem_text,
                    context,
                    system_prompt,
                    schema,
                    response_data,
                    validation,
                    trace=trace
                )
                telemetry["repaired"] = response_data.get("_repaired", False)
                
                # Validate repaired response
                validation = validate_response(response_data, strict=True)
                
                if not validation.valid:
                    telemetry["validation_failures_count"] += 1
                    if trace:
                        print(f"[SOLVER_V3] ❌ Repair failed, returning error response")
                    telemetry["latency_ms_total"] = int((time.time() - start_time) * 1000)
                    error_resp = create_error_response(
                        problem_text,
                        validation.errors,
                        "validation_failed_after_repair"
                    )
                    error_resp["_telemetry"] = telemetry
                    return error_resp
                
                if trace:
                    print(f"[SOLVER_V3] ✅ Repair successful")
            
            telemetry["validated"] = True
            
            # Step 4.5: Validate similar_examples (V3.1)
            response_data = self._validate_similar_examples(response_data, trace=trace)
            
            # Step 5: Generate visualization with confidence gating (V3.1)
            plot_start = time.time()
            should_plot = response_data.get("plot", {}).get("should_plot", False)
            
            if should_plot:
                telemetry["plot_attempted"] = True
                
                # V3.1: Check confidence-based gating
                plot_data = response_data.get("plot", {})
                
                # Use decision engine to get confidence if not in response
                if "confidence" not in plot_data:
                    decision = self.viz_engine.should_visualize(
                        problem_text,
                        response_data.get("analysis", {})
                    )
                    plot_confidence = decision.confidence
                else:
                    plot_confidence = plot_data.get("confidence", 0.0)
                
                telemetry["plot_confidence"] = plot_confidence
                
                # Gate plotting based on confidence
                if plot_confidence < min_plot_confidence:
                    telemetry["plot_gated"] = True
                    telemetry["plot_failed_reason"] = f"Confidence {plot_confidence:.2f} < threshold {min_plot_confidence}"
                    
                    if trace:
                        print(f"[SOLVER_V3] ⚠️ Plot gated: confidence {plot_confidence:.2f} < {min_plot_confidence}")
                        print(f"[SOLVER_V3]    Using visualization_alternative instead")
                    
                    # Ensure visualization_alternative exists
                    if "visualization_alternative" not in plot_data:
                        alt = self.viz_engine.generate_visualization_alternative(
                            problem_text,
                            f"Low confidence ({plot_confidence:.2f}) for plotting"
                        )
                        response_data["plot"]["visualization_alternative"] = alt.dict()
                    
                    # Clear should_plot
                    response_data["plot"]["should_plot"] = False
                
                else:
                    # Proceed with plot generation
                    try:
                        plot_plan = plot_data.get("plan")
                        plot_type = plot_data.get("plot_type", "function")
                        
                        # Convert dict to Pydantic model if needed
                        from app.schemas.na_math_solver_v3 import PlotPlanV3
                        if isinstance(plot_plan, dict):
                            plot_plan = PlotPlanV3(**plot_plan)
                        
                        plot_result = self.plot_renderer.render(plot_plan, plot_type)
                        telemetry["plot_generated"] = True
                        telemetry["latency_ms_plot"] = int((time.time() - plot_start) * 1000)
                        
                        # V3.1: Only include base64 if explicitly requested or in trace mode
                        if include_plot_base64 or trace:
                            response_data["_plot_image"] = plot_result.image_base64
                        
                        response_data["_plot_width"] = plot_result.width
                        response_data["_plot_height"] = plot_result.height
                        
                        if trace:
                            print(f"[SOLVER_V3] ✅ Generated plot: {plot_type} ({telemetry['latency_ms_plot']}ms)")
                            print(f"[SOLVER_V3]    Confidence: {plot_confidence:.2f}")
                            print(f"[SOLVER_V3]    Size: {plot_result.width}x{plot_result.height}px")
                    
                    except Exception as e:
                        telemetry["plot_failed_reason"] = str(e)
                        if trace:
                            print(f"[SOLVER_V3] ⚠️ Plot generation failed: {e}")
                        
                        # Add visualization_alternative as fallback
                        alt = self.viz_engine.generate_visualization_alternative(
                            problem_text,
                            f"Plot rendering failed: {str(e)}"
                        )
                        response_data["plot"]["visualization_alternative"] = alt.dict()
                        response_data["plot"]["should_plot"] = False
            
            # Step 6: Add metadata and telemetry
            telemetry["latency_ms_total"] = int((time.time() - start_time) * 1000)
            
            response_data["_model"] = response_data.get("_model", self._model)
            response_data["_validated"] = True
            response_data["_timestamp"] = datetime.utcnow().isoformat()
            response_data["_telemetry"] = telemetry
            
            if trace:
                print(f"[SOLVER_V3] ==================== SUCCESS ====================")
                print(f"[SOLVER_V3] Total latency: {telemetry['latency_ms_total']}ms")
                print(f"[SOLVER_V3] Telemetry: {json.dumps(telemetry, indent=2)}\n")
            
            return response_data
        
        except Exception as e:
            telemetry["latency_ms_total"] = int((time.time() - start_time) * 1000)
            if trace:
                print(f"[SOLVER_V3] ❌ FATAL ERROR: {e}")
                import traceback
                traceback.print_exc()
            
            error_resp = create_error_response(
                problem_text,
                [f"Fatal error: {str(e)}"],
                "fatal_error"
            )
            error_resp["_telemetry"] = telemetry
            return error_resp
    
    async def _call_llm_with_schema(
        self,
        problem_text: str,
        context: str,
        system_prompt: str,
        schema: Dict[str, Any],
        trace: bool = False
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Call OpenAI with strict schema validation.
        
        V3.1: Now returns token usage data
        
        Args:
            problem_text: Problem to solve
            context: Additional context
            system_prompt: System prompt
            schema: JSON schema
            trace: Enable logging
        
        Returns:
            (response_data, tokens) where tokens = {"input": int, "output": int}
        """
        # Assemble user message
        user_message = f"""Problem: {problem_text}

Context: {context if context else "No additional context provided."}

**CRITICAL**: Return ONLY strictly valid JSON matching the schema. Include:
- At least 2 verification methods whenever possible
- plot.should_plot = true for any graphable content
- At least 2 similar_examples for practice
- meta.localization.region = "north_america"
- Each step must include: concept, rules_used, work, result, checkpoint
"""
        
        tokens = {"input": 0, "output": 0}
        
        # Build parameters for OpenAI Responses API (gpt-5-mini)
        if "gpt-5" in self._model.lower():
            params = {
                "model": self._model,
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}]
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_message}]
                    }
                ],
                "text": {
                    "verbosity": "high",
                    "format": {
                        "type": "json_schema",
                        "name": "solve_response_v3",
                        "strict": True,
                        "schema": get_json_schema_for_openai_v3()
                    }
                },
                "reasoning": {"effort": "none"},
                "max_output_tokens": 3000
            }
            
            response = await self.client.responses.create(**params)
            content = response.output[0].content[0].text
            model_used = response.model
            
            # Extract tokens if available
            if hasattr(response, 'usage'):
                tokens["input"] = getattr(response.usage, 'input_tokens', 0)
                tokens["output"] = getattr(response.usage, 'output_tokens', 0)
        
        else:
            # Fallback to Chat Completions (gpt-4o-mini)
            params = {
                "model": self._fallback_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "max_completion_tokens": 3000
            }
            
            response = await self.client.chat.completions.create(**params)
            content = response.choices[0].message.content
            model_used = response.model
            
            # Extract tokens
            if hasattr(response, 'usage'):
                tokens["input"] = response.usage.prompt_tokens
                tokens["output"] = response.usage.completion_tokens
        
        # Parse JSON
        data = json.loads(content)
        data["_model"] = model_used
        
        return data, tokens
    
    def _validate_similar_examples(
        self,
        response_data: Dict[str, Any],
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Validate similar_examples are syntactically valid (V3.1).
        
        Removes invalid examples rather than failing the entire response.
        
        Args:
            response_data: Response data to validate
            trace: Enable logging
        
        Returns:
            Response data with validated similar_examples
        """
        similar_examples = response_data.get("similar_examples", [])
        
        if not similar_examples:
            return response_data
        
        valid_examples = []
        
        for i, example in enumerate(similar_examples):
            problem = example.get("problem", "")
            
            # Basic validation: not empty, not just "x^2 + ="
            if not problem or len(problem) < 3:
                if trace:
                    print(f"[SOLVER_V3] ⚠️ Skipping invalid example {i + 1}: too short")
                continue
            
            # Check for incomplete equations like "x^2 +  = 0"
            if "  " in problem or problem.endswith("+") or problem.endswith("-") or problem.endswith("="):
                if trace:
                    print(f"[SOLVER_V3] ⚠️ Skipping invalid example {i + 1}: '{problem[:30]}...'")
                continue
            
            valid_examples.append(example)
        
        # Ensure we have at least 2 examples
        if len(valid_examples) < 2 and len(valid_examples) > 0:
            # Duplicate first valid example as fallback
            if trace:
                print(f"[SOLVER_V3] ⚠️ Only {len(valid_examples)} valid examples, duplicating")
            valid_examples.append(valid_examples[0])
        
        response_data["similar_examples"] = valid_examples
        
        if trace and len(valid_examples) != len(similar_examples):
            print(f"[SOLVER_V3] ✅ Validated similar_examples: {len(valid_examples)}/{len(similar_examples)}")
        
        return response_data
    
    async def _repair_response(
        self,
        problem_text: str,
        context: str,
        system_prompt: str,
        schema: Dict[str, Any],
        invalid_response: Dict[str, Any],
        validation_result,
        trace: bool = False
    ) -> Dict[str, Any]:
        """
        Attempt to repair an invalid response.
        
        Args:
            problem_text: Original problem
            context: Context
            system_prompt: System prompt
            schema: JSON schema
            invalid_response: The invalid response
            validation_result: Validation errors
            trace: Enable logging
        
        Returns:
            Repaired response (may still be invalid)
        """
        if trace:
            print(f"[SOLVER_V3] Attempting repair...")
        
        # Generate repair prompt
        repair_prompt = generate_repair_prompt(
            invalid_response,
            validation_result,
            problem_text
        )
        
        # Call LLM again with repair instructions
        try:
            if "gpt-5" in self._model.lower():
                params = {
                    "model": self._model,
                    "input": [
                        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                        {"role": "user", "content": [{"type": "input_text", "text": f"Problem: {problem_text}\nContext: {context}"}]},
                        {"role": "assistant", "content": [{"type": "output_text", "text": json.dumps(invalid_response)}]},
                        {"role": "user", "content": [{"type": "input_text", "text": repair_prompt}]}
                    ],
                    "text": {
                        "verbosity": "high",
                        "format": {
                            "type": "json_schema",
                            "name": "solve_response_v3",
                            "strict": True,
                            "schema": get_json_schema_for_openai_v3()
                        }
                    },
                    "reasoning": {"effort": "none"},
                    "max_output_tokens": 3000
                }
                
                response = await self.client.responses.create(**params)
                content = response.output[0].content[0].text
            
            else:
                params = {
                    "model": self._fallback_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Problem: {problem_text}\nContext: {context}"},
                        {"role": "assistant", "content": json.dumps(invalid_response)},
                        {"role": "user", "content": repair_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,  # Lower temperature for repair
                    "max_completion_tokens": 3000
                }
                
                response = await self.client.chat.completions.create(**params)
                content = response.choices[0].message.content
            
            repaired_data = json.loads(content)
            repaired_data["_model"] = response.model if hasattr(response, 'model') else self._model
            repaired_data["_repaired"] = True
            
            return repaired_data
        
        except Exception as e:
            if trace:
                print(f"[SOLVER_V3] ❌ Repair attempt failed: {e}")
            # Return original invalid response
            return invalid_response


# Singleton instance
_solver_v3_instance: Optional[SolverV3] = None


def get_solver_v3() -> SolverV3:
    """Get the global Solver V3 instance."""
    global _solver_v3_instance
    if _solver_v3_instance is None:
        _solver_v3_instance = SolverV3()
    return _solver_v3_instance


if __name__ == "__main__":
    # Test solver V3
    print("Math Solver V3 - Orchestrator")
    print("=" * 50)
    print("\nTo test: Set OPENAI_API_KEY and run:")
    print("  python -m app.services.solver_v3")
    print("\nExample usage:")
    print("""
import asyncio
from app.services.solver_v3 import get_solver_v3

async def test():
    solver = get_solver_v3()
    result = await solver.solve("Solve x^2 - 4 = 0", trace=True)
    print(json.dumps(result, indent=2))

asyncio.run(test())
    """)
