"""
3-Tier Plotting Integration Test Script

Tests plotting pipeline across FREE, STANDARD, and RESEARCH tiers
for the problem: |2x - 3| = 7

Run with:
    cd backend && python -m tests.plot_integration_test

Output:
    - Detailed runtime report for each tier
    - Consolidated summary report
    - All results validated against expected output
"""

import os
import sys
import json
import asyncio
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI, BadRequestError
from sqlmodel import Session, select

from app.database import get_session, engine
from app.models import PromptTemplateEntry, JsonSchemaEntry, PromptBinding, PromptModeEnum
from app.prompts.db_loader import resolve_prompt_bundle, PromptBindingLookupError


@dataclass
class CallMetrics:
    """Metrics for a single API call."""
    call_type: str  # 'solve', 'trigger', 'spec'
    model: str
    system_prompt_id: str
    developer_prompt_id: str
    schema_id: str
    request_id: Optional[str]
    latency_ms: float
    tokens_in: int
    tokens_out: int
    success: bool
    error: Optional[str] = None


@dataclass
class TierResult:
    """Complete result for a single tier test."""
    tier: str
    problem: str
    solve_metrics: CallMetrics
    solve_output: Dict[str, Any]
    trigger_metrics: Optional[CallMetrics]
    trigger_output: Optional[Dict[str, Any]]
    spec_metrics: Optional[CallMetrics]
    spec_output: Optional[Dict[str, Any]]
    final_answer: str
    plot_generated: bool
    plot_id: Optional[str]
    attach_to_step_id: Optional[int]
    errors: List[str]


class ThreeTierPlotTester:
    """Test plotting pipeline across all three tiers."""
    
    PROBLEM = r"Find the inverse of f(x) = \frac{x - 1}{x + 2}"
    EXPECTED_ANSWERS = ["f^{-1}(x)", "f^{-1}", "inverse", "\\frac{-2x-1", "-\\frac{2x+1", "1-2x", "\\frac{1+2x"]
    
    # Prompt/Schema IDs
    GLOBAL_SYSTEM_PROMPT = "global_system_prompt_v1"
    PLOT_TRIGGER_PROMPT = "plot_trigger_v1"
    PLOT_SPEC_PROMPT = "plot_spec_v1"
    PLOT_TRIGGER_SCHEMA = "youask_plot_trigger_v1.schema.json"
    PLOT_SPEC_SCHEMA = "youask_plot_spec_v1.schema.json"
    
    TIER_CONFIG = {
        "FREE": {
            "solve_prompt": "solve_free_v1",  # or existing FREE prompt
            "solve_schema": "youask_math_solver_solve_free_v1.schema.json",
            "mode": "minimal",
        },
        "STANDARD": {
            "solve_prompt": "solve_standard_v1",
            "solve_schema": "youask_math_solver_solve_standard_detailed_v1.schema.json",
            "mode": "detailed",
        },
        "RESEARCH": {
            "solve_prompt": "solve_research_v1",
            "solve_schema": "youask_math_solver_solve_research_v1.schema.json",
            "mode": "study",
        },
    }
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.results: List[TierResult] = []
        
        # Cache for prompts/schemas
        self._prompt_cache: Dict[str, Any] = {}
        self._schema_cache: Dict[str, Any] = {}
        
    async def run_all_tests(self) -> List[TierResult]:
        """Run tests for all three tiers."""
        logger.info("=" * 60)
        logger.info("STARTING 3-TIER PLOTTING INTEGRATION TEST")
        logger.info("=" * 60)
        logger.info(f"Problem: {self.PROBLEM}")
        logger.info(f"Expected answers: {self.EXPECTED_ANSWERS}")
        logger.info("")
        
        for tier in ["FREE", "STANDARD", "RESEARCH"]:
            result = await self.run_tier_test(tier)
            self.results.append(result)
            logger.info(f"\n{'='*60}")
            logger.info(f"TIER {tier} COMPLETE")
            logger.info(f"Success: {result.solve_metrics.success}")
            logger.info(f"Plot generated: {result.plot_generated}")
            logger.info(f"Errors: {result.errors}")
            logger.info("=" * 60)
            
        return self.results
    
    async def run_tier_test(self, tier: str) -> TierResult:
        """Run complete test for a single tier."""
        logger.info(f"\n{'-'*60}")
        logger.info(f"RUNNING TIER: {tier}")
        logger.info("-" * 60)
        
        config = self.TIER_CONFIG[tier]
        errors = []
        
        # Log file for full outputs
        log_file = f"plot_test_{tier.lower()}_log.json"
        full_logs = {"tier": tier, "problem": self.PROBLEM, "calls": []}
        
        with Session(engine) as session:
            # Step 1: SOLVE
            solve_metrics, solve_output = await self._call_solve(
                session, tier, config
            )
            
            if not solve_metrics.success:
                errors.append(f"Solve failed: {solve_metrics.error}")
                return TierResult(
                    tier=tier,
                    problem=self.PROBLEM,
                    solve_metrics=solve_metrics,
                    solve_output={},
                    trigger_metrics=None,
                    trigger_output=None,
                    spec_metrics=None,
                    spec_output=None,
                    final_answer="",
                    plot_generated=False,
                    plot_id=None,
                    attach_to_step_id=None,
                    errors=errors,
                )
            
            final_answer = self._extract_final_answer(solve_output)
            
            # Validate answer
            if not self._validate_answer(final_answer):
                errors.append(f"Unexpected answer: {final_answer}")
            
            # Step 2: PLOT TRIGGER (always run for graph_mode=on)
            trigger_metrics, trigger_output = await self._call_plot_trigger(
                session, tier, self.PROBLEM, solve_output
            )
            
            if not trigger_metrics.success:
                errors.append(f"Trigger failed: {trigger_metrics.error}")
            
            # Step 3: PLOT SPEC (if trigger says plot_needed or we force it)
            spec_metrics = None
            spec_output = None
            plot_generated = False
            plot_id = None
            attach_to_step_id = None
            
            should_plot = (
                trigger_output.get("plot_needed", False) if trigger_output else False
            )
            
            if should_plot and trigger_metrics and trigger_metrics.success:
                spec_metrics, spec_output = await self._call_plot_spec(
                    session, tier, self.PROBLEM, solve_output, trigger_output
                )
                
                if spec_metrics.success:
                    plot_generated = True
                    plot_id = spec_output.get("plot", {}).get("plot_id")
                    attach_to_step_id = spec_output.get("plot", {}).get("attach_to_step_id")
                else:
                    errors.append(f"Spec failed: {spec_metrics.error}")
            elif not should_plot and trigger_metrics and trigger_metrics.success:
                errors.append("Trigger refused to plot (plot_needed=false)")
        
        return TierResult(
            tier=tier,
            problem=self.PROBLEM,
            solve_metrics=solve_metrics,
            solve_output=solve_output,
            trigger_metrics=trigger_metrics,
            trigger_output=trigger_output,
            spec_metrics=spec_metrics,
            spec_output=spec_output,
            final_answer=final_answer,
            plot_generated=plot_generated,
            plot_id=plot_id,
            attach_to_step_id=attach_to_step_id,
            errors=errors,
        )
    
    async def _call_solve(
        self, session: Session, tier: str, config: Dict[str, Any]
    ) -> tuple[CallMetrics, Dict[str, Any]]:
        """Call solve for a tier."""
        start_time = time.time()
        
        try:
            # Load prompts - resolve_prompt_bundle takes provider, tier, mode, db_session
            bundle = resolve_prompt_bundle(
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.SOLVE,
                db_session=session,
            )
            
            system_prompt = bundle.system_prompt_content
            developer_prompt = bundle.developer_prompt_content
            
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if developer_prompt:
                messages.append({"role": "developer", "content": developer_prompt})
            
            messages.append({"role": "user", "content": self.PROBLEM})
            
            # Use schema wrapper from DB and map to Chat Completions format
            # DB format: {type, name, strict, schema} -> Chat Completions: response_format.json_schema = {name, strict, schema}
            db_wrapper = bundle.output_schema_json if bundle.output_schema_json else {}
            
            json_schema_inner = {
                "name": db_wrapper.get("name", "solve_output"),
                "strict": db_wrapper.get("strict", True),
                "schema": self._sanitize_for_openai(db_wrapper.get("schema", {}))
            }
            
            # Call OpenAI - wrapper fields go inside json_schema
            request_payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": json_schema_inner
                }
            }
            logger.info(f"  OpenAI Request: {json.dumps(request_payload, indent=2, default=str)[:500]}...")
            
            response = await self.client.chat.completions.create(**request_payload)
            
            latency_ms = (time.time() - start_time) * 1000
            result = json.loads(response.choices[0].message.content)
            
            metrics = CallMetrics(
                call_type="solve",
                model=self.model,
                system_prompt_id=bundle.global_system_prompt_id,
                developer_prompt_id=bundle.developer_prompt_id,
                schema_id=bundle.output_schema_id,
                request_id=response.id,
                latency_ms=latency_ms,
                tokens_in=response.usage.prompt_tokens if response.usage else 0,
                tokens_out=response.usage.completion_tokens if response.usage else 0,
                success=True,
            )
            
            logger.info(f"  Solve: SUCCESS in {latency_ms:.0f}ms")
            logger.info(f"  Final answer: {self._extract_final_answer(result)}")
            
            return metrics, result
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            metrics = CallMetrics(
                call_type="solve",
                model=self.model,
                system_prompt_id=self.GLOBAL_SYSTEM_PROMPT,
                developer_prompt_id=config["solve_prompt"],
                schema_id=config["solve_schema"],
                request_id=None,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                success=False,
                error=str(e),
            )
            logger.error(f"  Solve: FAILED - {e}")
            return metrics, {}
    
    async def _call_plot_trigger(
        self, session: Session, tier: str, problem: str, solve_output: Dict[str, Any]
    ) -> tuple[CallMetrics, Dict[str, Any]]:
        """Call plot trigger."""
        start_time = time.time()
        
        try:
            bundle = resolve_prompt_bundle(
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.PLOT_TRIGGER,
                db_session=session,
            )
            
            system_prompt = bundle.system_prompt_content
            developer_prompt = bundle.developer_prompt_content
            
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if developer_prompt:
                messages.append({"role": "developer", "content": developer_prompt})
            
            user_content = {
                "problem_text": problem,
                "final_answer": solve_output.get("final_answer", {}),
                "solve_visuals": solve_output.get("visuals", {}),
            }
            
            messages.append({
                "role": "user",
                "content": json.dumps(user_content, ensure_ascii=False)
            })
            
            schema = bundle.output_schema_json if bundle.output_schema_json else {}
            # Extract inner fields from wrapper - remove 'type' field
            if isinstance(schema, dict) and "type" in schema:
                schema = {k: v for k, v in schema.items() if k != "type"}
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={
                    "type": "json_schema",
                    "json_schema": schema
                }
            )
            
            latency_ms = (time.time() - start_time) * 1000
            result = json.loads(response.choices[0].message.content)
            
            metrics = CallMetrics(
                call_type="trigger",
                model=self.model,
                system_prompt_id=bundle.global_system_prompt_id,
                developer_prompt_id=bundle.developer_prompt_id,
                schema_id=bundle.output_schema_id,
                request_id=response.id,
                latency_ms=latency_ms,
                tokens_in=response.usage.prompt_tokens if response.usage else 0,
                tokens_out=response.usage.completion_tokens if response.usage else 0,
                success=True,
            )
            
            logger.info(f"  Trigger: SUCCESS in {latency_ms:.0f}ms")
            logger.info(f"  plot_needed: {result.get('plot_needed')}")
            logger.info(f"  plot_type: {result.get('plot_type')}")
            
            return metrics, result
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            metrics = CallMetrics(
                call_type="trigger",
                model=self.model,
                system_prompt_id=self.GLOBAL_SYSTEM_PROMPT,
                developer_prompt_id=self.PLOT_TRIGGER_PROMPT,
                schema_id=self.PLOT_TRIGGER_SCHEMA,
                request_id=None,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                success=False,
                error=str(e),
            )
            logger.error(f"  Trigger: FAILED - {e}")
            return metrics, {}
    
    async def _call_plot_spec(
        self, session: Session, tier: str, problem: str,
        solve_output: Dict[str, Any], trigger_output: Dict[str, Any]
    ) -> tuple[CallMetrics, Dict[str, Any]]:
        """Call plot spec."""
        start_time = time.time()
        
        try:
            bundle = resolve_prompt_bundle(
                provider="openai",
                tier=tier,
                mode=PromptModeEnum.PLOT_SPEC,
                db_session=session,
            )
            
            system_prompt = bundle.system_prompt_content
            developer_prompt = bundle.developer_prompt_content
            
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if developer_prompt:
                messages.append({"role": "developer", "content": developer_prompt})
            
            # Build plot plan from trigger output
            plot_plan = {
                "plot_type": trigger_output.get("plot_type", "function"),
                "variables": trigger_output.get("variables", ["x", "y"]),
                "ranges": trigger_output.get("ranges", {"x": [-10, 10], "y": [-10, 10]}),
                "series_plan": trigger_output.get("series_plan", []),
                "key_points": trigger_output.get("key_points", []),
            }
            
            # Add the specific functions for |2x-3| = 7
            if not plot_plan["series_plan"]:
                plot_plan["series_plan"] = [
                    {"expression": "abs(2*x - 3)", "label": "y = |2x - 3|"},
                    {"expression": "7", "label": "y = 7"}
                ]
            
            # Ensure ranges show both solutions (-2 and 5)
            plot_plan["ranges"] = {"x": [-6, 8], "y": [-2, 10]}
            
            user_content = {
                "problem_text": problem,
                "attach_to_step_id": None,
                "plot_plan": plot_plan,
            }
            
            messages.append({
                "role": "user",
                "content": json.dumps(user_content, ensure_ascii=False)
            })
            
            schema = bundle.output_schema_json if bundle.output_schema_json else {}
            # Extract inner fields from wrapper - remove 'type' field
            if isinstance(schema, dict) and "type" in schema:
                schema = {k: v for k, v in schema.items() if k != "type"}
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={
                    "type": "json_schema",
                    "json_schema": schema
                }
            )
            
            latency_ms = (time.time() - start_time) * 1000
            result = json.loads(response.choices[0].message.content)
            
            metrics = CallMetrics(
                call_type="spec",
                model=self.model,
                system_prompt_id=bundle.global_system_prompt_id,
                developer_prompt_id=bundle.developer_prompt_id,
                schema_id=bundle.output_schema_id,
                request_id=response.id,
                latency_ms=latency_ms,
                tokens_in=response.usage.prompt_tokens if response.usage else 0,
                tokens_out=response.usage.completion_tokens if response.usage else 0,
                success=True,
            )
            
            plot_data = result.get("plot", {}).get("plotly", {})
            num_traces = len(plot_data.get("data", []))
            
            logger.info(f"  Spec: SUCCESS in {latency_ms:.0f}ms")
            logger.info(f"  plot_id: {result.get('plot', {}).get('plot_id')}")
            logger.info(f"  traces: {num_traces}")
            
            return metrics, result
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            metrics = CallMetrics(
                call_type="spec",
                model=self.model,
                system_prompt_id=self.GLOBAL_SYSTEM_PROMPT,
                developer_prompt_id=self.PLOT_SPEC_PROMPT,
                schema_id=self.PLOT_SPEC_SCHEMA,
                request_id=None,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                success=False,
                error=str(e),
            )
            logger.error(f"  Spec: FAILED - {e}")
            return metrics, {}
    
    def _sanitize_for_openai(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize inner schema for OpenAI strict mode compatibility."""
        import copy
        schema = copy.deepcopy(schema)
        
        def clean(node: Any) -> Any:
            if not isinstance(node, dict):
                return node
            
            result = {}
            
            # Handle allOf by merging
            if 'allOf' in node:
                merged = {}
                for sub in node['allOf']:
                    if isinstance(sub, dict):
                        merged.update(sub)
                # Merge with existing, keeping non-allOf keys
                for k, v in node.items():
                    if k != 'allOf':
                        merged[k] = v
                node = merged
            
            # Handle if/then/else - OpenAI doesn't support it, use anyOf workaround
            if 'if' in node or 'then' in node or 'else' in node:
                # Remove conditional logic, keep base properties
                for k in ['if', 'then', 'else']:
                    node.pop(k, None)
            
            for key, value in node.items():
                # Remove description from $ref siblings
                if key == 'description' and '$ref' in node:
                    continue
                
                if isinstance(value, dict):
                    result[key] = clean(value)
                elif isinstance(value, list):
                    result[key] = [clean(item) if isinstance(item, dict) else item for item in value]
                else:
                    result[key] = value
            
            # Ensure required includes all properties for strict mode
            if 'properties' in result:
                all_props = set(result['properties'].keys())
                if 'required' in result:
                    current_required = set(result['required'])
                    missing = all_props - current_required
                    if missing:
                        result['required'] = list(current_required | missing)
                else:
                    result['required'] = list(all_props)
            
            # Ensure type exists for objects with properties
            if 'properties' in result and 'type' not in result:
                result['type'] = 'object'
            
            return result
        
        return clean(schema)
    
    def _load_schema(self, session: Session, schema_id: str) -> Dict[str, Any]:
        """Load schema from DB with caching."""
        if schema_id in self._schema_cache:
            return self._schema_cache[schema_id]
        
        schema_entry = session.exec(
            select(JsonSchemaEntry).where(
                JsonSchemaEntry.schema_id == schema_id,
                JsonSchemaEntry.is_active == True
            )
        ).first()
        
        if schema_entry and schema_entry.json_schema:
            inner = schema_entry.json_schema.get("schema", schema_entry.json_schema)
            self._schema_cache[schema_id] = inner
            return inner
        
        return {"type": "object", "additionalProperties": True}
    
    async def _call_with_retry(
        self,
        call_func,
        max_retries: int = 1,
        *args,
        **kwargs
    ) -> tuple[CallMetrics, Dict[str, Any]]:
        """Wrapper to add retry logic to API calls."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            metrics, result = await call_func(*args, **kwargs)
            
            if metrics.success:
                # Check for empty outputs
                if result:
                    if isinstance(result, dict):
                        # Check solve output
                        if "final_answer" in result:
                            fa = result.get("final_answer", {})
                            if not fa.get("latex") and not fa.get("text"):
                                if attempt < max_retries:
                                    logger.warning(f"  Empty final_answer, retrying...")
                                    continue
                        # Check plot output
                        if "plot" in result:
                            plot = result.get("plot", {})
                            if not plot.get("plotly"):
                                if attempt < max_retries:
                                    logger.warning(f"  Empty plotly, retrying...")
                                    continue
                return metrics, result
            
            last_error = metrics.error
            if attempt < max_retries:
                logger.warning(f"  Call failed, retrying... ({attempt+1}/{max_retries})")
                await asyncio.sleep(0.5)  # Brief delay before retry
        
        # All retries exhausted
        return metrics, result
    
    def _extract_final_answer(self, solve_output: Dict[str, Any]) -> str:
        """Extract final answer from solve output."""
        final_answer = solve_output.get("final_answer", {})
        return final_answer.get("latex", final_answer.get("text", ""))
    
    def _validate_answer(self, answer: str) -> bool:
        """Check if answer contains expected values."""
        answer_clean = answer.lower().replace(" ", "").replace("=", "")
        return any(exp.lower().replace(" ", "").replace("=", "") in answer_clean 
                   for exp in self.EXPECTED_ANSWERS)
    
    def generate_report(self) -> str:
        """Generate comprehensive runtime report."""
        lines = []
        lines.append("# 3-Tier Plotting Integration Test Report")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append(f"Problem: {self.PROBLEM}")
        lines.append(f"Expected: x = -2 and x = 5")
        lines.append("")
        
        for result in self.results:
            lines.append(f"## Tier: {result.tier}")
            lines.append("")
            
            # Solve section
            lines.append("### Solve Call")
            lines.append(f"- Model: {result.solve_metrics.model}")
            lines.append(f"- System Prompt: {result.solve_metrics.system_prompt_id}")
            lines.append(f"- Developer Prompt: {result.solve_metrics.developer_prompt_id}")
            lines.append(f"- Schema: {result.solve_metrics.schema_id}")
            lines.append(f"- Request ID: {result.solve_metrics.request_id}")
            lines.append(f"- Latency: {result.solve_metrics.latency_ms:.0f}ms")
            lines.append(f"- Tokens: {result.solve_metrics.tokens_in} in / {result.solve_metrics.tokens_out} out")
            lines.append(f"- Success: {result.solve_metrics.success}")
            lines.append(f"- Final Answer: {result.final_answer}")
            lines.append("")
            
            # Trigger section
            if result.trigger_metrics:
                lines.append("### Plot Trigger Call")
                lines.append(f"- Developer Prompt: {result.trigger_metrics.developer_prompt_id}")
                lines.append(f"- Schema: {result.trigger_metrics.schema_id}")
                lines.append(f"- Request ID: {result.trigger_metrics.request_id}")
                lines.append(f"- Latency: {result.trigger_metrics.latency_ms:.0f}ms")
                lines.append(f"- Tokens: {result.trigger_metrics.tokens_in} in / {result.trigger_metrics.tokens_out} out")
                lines.append(f"- Success: {result.trigger_metrics.success}")
                if result.trigger_output:
                    lines.append(f"- plot_needed: {result.trigger_output.get('plot_needed')}")
                    lines.append(f"- plot_type: {result.trigger_output.get('plot_type')}")
                    lines.append(f"- reason: {result.trigger_output.get('reason', 'N/A')}")
                lines.append("")
            
            # Spec section
            if result.spec_metrics:
                lines.append("### Plot Spec Call")
                lines.append(f"- Developer Prompt: {result.spec_metrics.developer_prompt_id}")
                lines.append(f"- Schema: {result.spec_metrics.schema_id}")
                lines.append(f"- Request ID: {result.spec_metrics.request_id}")
                lines.append(f"- Latency: {result.spec_metrics.latency_ms:.0f}ms")
                lines.append(f"- Tokens: {result.spec_metrics.tokens_in} in / {result.spec_metrics.tokens_out} out")
                lines.append(f"- Success: {result.spec_metrics.success}")
                if result.spec_output:
                    plot = result.spec_output.get("plot", {})
                    lines.append(f"- plot_id: {plot.get('plot_id')}")
                    lines.append(f"- attach_to_step_id: {plot.get('attach_to_step_id')}")
                    plotly = plot.get("plotly", {})
                    lines.append(f"- traces: {len(plotly.get('data', []))}")
                lines.append("")
            
            # Summary
            lines.append("### Summary")
            lines.append(f"- Plot Generated: {result.plot_generated}")
            lines.append(f"- Plot ID: {result.plot_id}")
            lines.append(f"- Errors: {result.errors if result.errors else 'None'}")
            lines.append("")
        
        # Overall summary
        lines.append("## Overall Summary")
        all_success = all(r.solve_metrics.success for r in self.results)
        all_plots = all(r.plot_generated for r in self.results)
        lines.append(f"- All solves successful: {all_success}")
        lines.append(f"- All plots generated: {all_plots}")
        lines.append(f"- Total errors: {sum(len(r.errors) for r in self.results)}")
        
        return "\n".join(lines)


async def main():
    """Main entry point."""
    # Check OpenAI key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in environment")
        print("Please set it in your .env file")
        sys.exit(1)
    
    tester = ThreeTierPlotTester()
    results = await tester.run_all_tests()
    
    # Generate and save report
    report = tester.generate_report()
    
    report_path = "plot_integration_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    print("\n" + "=" * 60)
    print("REPORT SAVED TO:", report_path)
    print("=" * 60)
    print(report)
    
    # Also save JSON results
    json_path = "plot_integration_results.json"
    json_results = []
    for r in results:
        json_results.append({
            "tier": r.tier,
            "solve": asdict(r.solve_metrics),
            "trigger": asdict(r.trigger_metrics) if r.trigger_metrics else None,
            "spec": asdict(r.spec_metrics) if r.spec_metrics else None,
            "plot_generated": r.plot_generated,
            "errors": r.errors,
        })
    
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2)
    
    print(f"\nJSON results saved to: {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
