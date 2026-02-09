"""
Production Plotting Pipeline Service

Implements two-stage plotting pipeline using DB-loaded prompts and schemas:
1. plot_trigger_v1 - Decides if visualization is needed
2. plot_spec_v1 - Generates Plotly JSON

All prompts/schemas loaded from database at runtime.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple, Literal
from dataclasses import dataclass
import numpy as np

from openai import AsyncOpenAI, BadRequestError
from sqlmodel import Session

from app.database import get_session
from app.models import PromptTemplateEntry, JsonSchemaEntry, PromptBinding, PromptModeEnum
from app.prompts.db_loader import resolve_prompt_bundle, PromptBindingLookupError, PromptBundle
from app.utils.token_utils import trim_messages
from app.utils.structured_output_builder import build_openai_structured_output, log_openai_request_trace

logger = logging.getLogger(__name__)


@dataclass
class PlotTriggerResult:
    """Result from plot trigger stage."""
    plot_needed: bool
    plot_type: str
    variables: list
    ranges: Dict[str, Any]
    reason: str
    series_plan: list
    key_points: list
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class PlotSpecResult:
    """Result from plot spec stage."""
    plot_id: str
    attach_to_step_id: Optional[int]
    plotly_json: Dict[str, Any]
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PlotPipelineService:
    """Service for production plotting pipeline with DB-loaded prompts."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.openai_client = AsyncOpenAI()
    
    async def execute_plotting_pipeline(
        self,
        problem_text: str,
        solve_result: Dict[str, Any],
        graph_mode: Literal["off", "auto", "on"],
        attach_to_step_id: Optional[int],
        tier: str = "STANDARD",
        question_id: Optional[str] = None,
        use_reliable_pipeline: bool = True,
    ) -> Tuple[Optional[PlotTriggerResult], Optional[PlotSpecResult]]:
        """
        Execute the complete plotting pipeline.
        
        Args:
            problem_text: Original problem text
            solve_result: The solve output (contains visuals.should_visualize, etc.)
            graph_mode: off | auto | on
            attach_to_step_id: Step to attach plot to
            tier: User's subscription tier
            question_id: Request/question ID for tracking
            use_reliable_pipeline: If False, skip trigger for speed
            
        Returns:
            Tuple of (trigger_result, spec_result) - either may be None
        """
        # Step 0: Check if plotting is wanted
        want_plot = self._should_plot(graph_mode, solve_result)
        
        if not want_plot:
            logger.info(f"[PLOT_PIPELINE] Skipping plot: graph_mode={graph_mode}, want_plot=false")
            return None, None
        
        trigger_result = None
        spec_result = None
        
        # Determine pipeline path
        if graph_mode == "on" and not use_reliable_pipeline:
            # FAST PIPELINE: Go straight to spec
            logger.info("[PLOT_PIPELINE] Using FAST pipeline (skip trigger)")
            spec_result = await self._call_plot_spec(
                problem_text=problem_text,
                solve_result=solve_result,
                attach_to_step_id=attach_to_step_id,
                tier=tier,
                question_id=question_id,
                trigger_result=None,
            )
        else:
            # RELIABLE PIPELINE: Trigger → Spec
            logger.info("[PLOT_PIPELINE] Using RELIABLE pipeline (trigger → spec)")
            trigger_result = await self._call_plot_trigger(
                problem_text=problem_text,
                solve_result=solve_result,
                tier=tier,
                question_id=question_id,
            )
            
            if trigger_result.error:
                logger.error(f"[PLOT_PIPELINE] Trigger failed: {trigger_result.error}")
                # Fallback based on graph_mode
                if graph_mode == "on":
                    # Try spec with safe defaults
                    logger.info("[PLOT_PIPELINE] Fallback: attempting spec directly")
                    spec_result = await self._call_plot_spec(
                        problem_text=problem_text,
                        solve_result=solve_result,
                        attach_to_step_id=attach_to_step_id,
                        tier=tier,
                        question_id=question_id,
                        trigger_result=None,
                    )
                # If auto and trigger failed, skip plot (don't fail solve)
            elif not trigger_result.plot_needed:
                logger.info("[PLOT_PIPELINE] Trigger says no plot needed")
                if graph_mode == "on":
                    # User explicitly wanted plot, but trigger says no
                    logger.warning("[PLOT_PIPELINE] User wanted plot but trigger refused")
            else:
                # Trigger says plot needed - call spec
                spec_result = await self._call_plot_spec(
                    problem_text=problem_text,
                    solve_result=solve_result,
                    attach_to_step_id=attach_to_step_id,
                    tier=tier,
                    question_id=question_id,
                    trigger_result=trigger_result,
                )
        
        return trigger_result, spec_result
    
    def _should_plot(self, graph_mode: str, solve_result: Dict[str, Any]) -> bool:
        """Determine if plotting should occur based on mode and solve result."""
        if graph_mode == "off":
            return False
        if graph_mode == "on":
            return True
        # auto: use solve's decision
        visuals = solve_result.get("visuals", {})
        return visuals.get("should_visualize", False)
    
    async def _call_plot_trigger(
        self,
        problem_text: str,
        solve_result: Dict[str, Any],
        tier: str,
        question_id: Optional[str],
    ) -> PlotTriggerResult:
        """Call plot_trigger_v1 using DB-loaded prompts."""
        try:
            # Load prompt bundle from DB (looks up binding by tier+mode)
            bundle = resolve_prompt_bundle(
                db_session=self.db,
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.PLOT_TRIGGER,
            )
            
            system_prompt = bundle.system_prompt_content
            developer_prompt = bundle.developer_prompt_content
            schema_config = bundle.output_schema_json
            
            # Build user message
            final_answer = solve_result.get("final_answer", {})
            user_content = {
                "question_id": question_id or "unknown",
                "problem_text": problem_text,
                "final_answer": final_answer.get("latex", final_answer.get("text", "")),
                "solve_visuals": solve_result.get("visuals", {}),
            }
            
            # Add constraints if available
            steps = solve_result.get("steps", [])
            if steps:
                # Extract constraints from steps
                constraints = []
                for step in steps:
                    if "domain" in step.get("explanation", "").lower():
                        constraints.append(step.get("explanation", ""))
                if constraints:
                    user_content["constraints"] = constraints
            
            # Build messages
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if developer_prompt:
                messages.append({"role": "developer", "content": developer_prompt})
            
            messages.append({
                "role": "user",
                "content": json.dumps(user_content, ensure_ascii=False)
            })

            # Apply input trimming
            messages = trim_messages(
                messages=messages,
                max_input_tokens=bundle.max_input_tokens or 30000,
                strategy=bundle.trim_strategy or "trim_context_first",
                model="gpt-4o"
            )
            
            # Get schema from bundle and build structured output using shared helper
            schema_wrapper = bundle.output_schema_json
            response_format = build_openai_structured_output(
                db_wrapper=schema_wrapper,
                endpoint="chat_completions",
                call_name="PLOT_TRIGGER"
            )
            
            # Call OpenAI
            log_openai_request_trace(
                call_name="PLOT_TRIGGER",
                user_id=None,
                tier=tier,
                binding_id=bundle.prompt_binding_id,
                model="gpt-4o-mini",
                endpoint="chat_completions",
                max_output_tokens=bundle.max_output_tokens or 800,
                schema_wrapper=schema_wrapper,
                structured_output_param=response_format,
                messages_info={"count": len(messages), "system": system_prompt[:50] if system_prompt else ""},
                request_id=question_id
            )

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=bundle.temperature if bundle.temperature is not None else 0.1,
                top_p=bundle.top_p if bundle.top_p is not None else 1.0,
                max_tokens=bundle.max_output_tokens or 800,
                response_format=response_format
            )
            
            result_json = self._extract_json_from_response(response.choices[0].message.content)
            
            return PlotTriggerResult(
                plot_needed=result_json.get("plot_needed", False),
                plot_type=result_json.get("plot_type", "function"),
                variables=result_json.get("variables", []),
                ranges=result_json.get("ranges", {}),
                reason=result_json.get("reason", ""),
                series_plan=result_json.get("series_plan", []),
                key_points=result_json.get("key_points", []),
                raw_response=result_json,
            )
            
        except PromptBindingLookupError as e:
            logger.error(f"[PLOT_TRIGGER] Prompt binding error: {e}")
            return PlotTriggerResult(
                plot_needed=False,
                plot_type="",
                variables=[],
                ranges={},
                reason=f"Config error: {str(e)}",
                series_plan=[],
                key_points=[],
                error=str(e),
            )
        except BadRequestError as e:
            logger.error(f"[PLOT_TRIGGER] OpenAI error: {e}")
            return PlotTriggerResult(
                plot_needed=False,
                plot_type="",
                variables=[],
                ranges={},
                reason=f"API error: {str(e)}",
                series_plan=[],
                key_points=[],
                error=str(e),
            )
        except Exception as e:
            logger.exception("[PLOT_TRIGGER] Unexpected error")
            return PlotTriggerResult(
                plot_needed=False,
                plot_type="",
                variables=[],
                ranges={},
                reason=f"Unexpected error: {str(e)}",
                series_plan=[],
                key_points=[],
                error=str(e),
            )
    
    async def _call_plot_spec(
        self,
        problem_text: str,
        solve_result: Dict[str, Any],
        attach_to_step_id: Optional[int],
        tier: str,
        question_id: Optional[str],
        trigger_result: Optional[PlotTriggerResult],
    ) -> PlotSpecResult:
        """Call plot_spec_v1 using DB-loaded prompts."""
        try:
            # Load prompt bundle from DB (looks up binding by tier+mode)
            bundle = resolve_prompt_bundle(
                db_session=self.db,
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.PLOT_SPEC,
            )
            
            system_prompt = bundle.system_prompt_content
            developer_prompt = bundle.developer_prompt_content
            
            # Build plot plan
            if trigger_result:
                plot_plan = {
                    "plot_type": trigger_result.plot_type,
                    "variables": trigger_result.variables,
                    "ranges": trigger_result.ranges,
                    "series_plan": trigger_result.series_plan,
                    "key_points": trigger_result.key_points,
                }
            else:
                # Build from solve result (fast pipeline fallback)
                plot_plan = self._infer_plot_plan_from_solve(solve_result)
            
            # Pre-compute sampled points for reliability
            plot_plan = self._precompute_samples(plot_plan, bundle.plot_points_cap)
            
            user_content = {
                "question_id": question_id or "unknown",
                "attach_to_step_id": attach_to_step_id,
                "plot_plan": plot_plan,
                "problem_summary": problem_text[:200],
            }
            
            # Build messages
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if developer_prompt:
                messages.append({"role": "developer", "content": developer_prompt})
            
            messages.append({
                "role": "user",
                "content": json.dumps(user_content, ensure_ascii=False)
            })

            # Apply input trimming
            messages = trim_messages(
                messages=messages,
                max_input_tokens=bundle.max_input_tokens or 30000,
                strategy=bundle.trim_strategy or "trim_context_first",
                model="gpt-4o"
            )
            
            # Get schema from bundle and build structured output using shared helper
            schema_wrapper = bundle.output_schema_json
            response_format = build_openai_structured_output(
                db_wrapper=schema_wrapper,
                endpoint="chat_completions",
                call_name="PLOT_SPEC"
            )
            
            # Call OpenAI
            log_openai_request_trace(
                call_name="PLOT_SPEC",
                user_id=None, 
                tier=tier,
                binding_id=bundle.prompt_binding_id,
                model="gpt-4o-mini",
                endpoint="chat_completions",
                max_output_tokens=bundle.max_output_tokens or 1400,
                schema_wrapper=schema_wrapper,
                structured_output_param=response_format,
                messages_info={"count": len(messages), "system": system_prompt[:50] if system_prompt else ""},
                request_id=question_id
            )

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=bundle.temperature if bundle.temperature is not None else 0.1,
                top_p=bundle.top_p if bundle.top_p is not None else 1.0,
                max_tokens=bundle.max_output_tokens or 1400,
                response_format=response_format
            )
            
            result_json = self._extract_json_from_response(response.choices[0].message.content)
            
            # Validate result structure
            if isinstance(result_json, list):
                if result_json and isinstance(result_json[0], dict):
                    result_json = result_json[0]
                else:
                    result_json = {}
            
            if not isinstance(result_json, dict):
                result_json = {}

            plot_node = result_json.get("plot")
            if not isinstance(plot_node, dict):
                plot_node = {}

            return PlotSpecResult(
                plot_id=plot_node.get("plot_id", "plot_1"),
                attach_to_step_id=plot_node.get("attach_to_step_id"),
                plotly_json=plot_node.get("plotly", {}),
                raw_response=result_json,
            )
            
        except PromptBindingLookupError as e:
            logger.error(f"[PLOT_SPEC] Prompt binding error: {e}")
            return PlotSpecResult(
                plot_id="",
                attach_to_step_id=attach_to_step_id,
                plotly_json={},
                error=str(e),
            )
        except Exception as e:
            logger.exception("[PLOT_SPEC] Error")
            return PlotSpecResult(
                plot_id="",
                attach_to_step_id=attach_to_step_id,
                plotly_json={},
                error=str(e),
            )
    
    def _get_schema(self, schema_id: str) -> Dict[str, Any]:
        """Load schema from database."""
        try:
            schema_entry = self.db.exec(
                select(JsonSchemaEntry).where(
                    JsonSchemaEntry.schema_id == schema_id,
                    JsonSchemaEntry.is_active == True
                )
            ).first()
            
            if schema_entry and schema_entry.content:
                # Handle OpenAI wrapper format
                inner = schema_entry.content.get("schema", schema_entry.content)
                return inner
            
            # Fallback: return permissive schema
            return {
                "type": "object",
                "properties": {},
                "additionalProperties": True
            }
        except Exception as e:
            logger.error(f"[PLOT_PIPELINE] Schema load error for {schema_id}: {e}")
            return {"type": "object", "additionalProperties": True}
    
    def _infer_plot_plan_from_solve(self, solve_result: Dict[str, Any]) -> Dict[str, Any]:
        """Infer plot plan from solve result when trigger is skipped."""
        visuals = solve_result.get("visuals", {})
        final_answer = solve_result.get("final_answer", {})
        
        # Try to extract expression from answer
        latex = final_answer.get("latex", "")
        text = final_answer.get("text", "")
        
        expressions = []
        if latex:
            expressions.append(latex)
        elif text and "=" in text:
            expressions.append(text)
        
        return {
            "plot_type": "function",
            "variables": ["x", "y"],
            "ranges": {"x": [-10, 10], "y": [-10, 10]},
            "series_plan": [{"expression": expr, "label": f"f(x)={expr[:20]}"} for expr in expressions[:3]],
            "key_points": []
        }
    
    def _precompute_samples(self, plot_plan: Dict[str, Any], points_cap: Optional[int] = None) -> Dict[str, Any]:
        """Pre-compute sampled points for numeric stability."""
        series_plan = plot_plan.get("series_plan", [])
        ranges = plot_plan.get("ranges", {})
        
        num_points = points_cap or 25
        
        x_range = ranges.get("x", [-10, 10])
        if isinstance(x_range, dict):
            x_range = [x_range.get("min", -10), x_range.get("max", 10)]
        
        for series in series_plan:
            expr = series.get("expression", "")
            if not expr:
                continue
            
            try:
                # Generate x points
                x_vals = np.linspace(x_range[0], x_range[1], num_points)
                
                # Simple evaluation for common functions
                y_vals = self._safe_eval(expr, x_vals)
                
                # Filter out infinities/NaN
                valid_mask = np.isfinite(y_vals)
                series["sampled_points"] = {
                    "x": x_vals[valid_mask].tolist()[:num_points],
                    "y": y_vals[valid_mask].tolist()[:num_points]
                }
            except Exception as e:
                logger.warning(f"[PLOT_PIPELINE] Sampling failed for {expr}: {e}")
                series["sampled_points"] = None
        
        return plot_plan
    
    def _safe_eval(self, expr: str, x_vals: np.ndarray) -> np.ndarray:
        """Safely evaluate expression over x values."""
        # Simple preprocessing
        expr = expr.replace('^', '**')
        
        results = []
        for x in x_vals:
            try:
                # Create safe namespace
                namespace = {
                    'x': x,
                    'sin': np.sin,
                    'cos': np.cos,
                    'tan': np.tan,
                    'sqrt': np.sqrt,
                    'log': np.log,
                    'ln': np.log,
                    'exp': np.exp,
                    'abs': np.abs,
                    'pi': np.pi,
                    'e': np.e,
                }
                result = eval(expr, {"__builtins__": {}}, namespace)
                results.append(float(result))
            except:
                results.append(np.nan)
        
        return np.array(results)
    
    def _extract_json_from_response(self, text: str) -> dict:
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


# Singleton instance
_plot_pipeline_service: Optional[PlotPipelineService] = None


def get_plot_pipeline_service(db_session: Session) -> PlotPipelineService:
    """Get or create plot pipeline service instance."""
    return PlotPipelineService(db_session)
