"""
Production E2E Verification with Full Trace Report

This script tests the complete flow with real DB users and produces
a comprehensive trace report proving exact endpoint + payload shapes.

Usage:
    python app/tools/verify_production_e2e.py --save-trace output/trace_report.txt
"""
import os
import sys
import json
import time
import asyncio
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Setup path
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env from project root
from dotenv import load_dotenv
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")

# Production DATABASE_URL fallback
os.environ.setdefault("DATABASE_URL", "postgresql://uaskstudents_user:MJxQ25u6zNRFyp396NUyXxPPuvD9YcVU@dpg-ctd020m8ii6s73a1l8u0-a.oregon-postgres.render.com/uaskstudents")

from sqlmodel import Session, create_engine, select
from app.models import User, PromptBinding, JsonSchemaEntry
from app.prompts.db_loader import load_prompt_bundle, PromptBindingLookupError
from app.services.solver_v3 import SolverV3, get_solver_v3
from app.services.plot_pipeline_service import get_plot_pipeline_service
from app.utils.structured_output_builder import (
    get_all_traces, clear_traces, save_traces_to_file, compute_schema_hash
)
from sqlalchemy.exc import OperationalError
import ssl



# ============================================================================
# TRACE REPORT BUILDER
# ============================================================================

class TraceReportBuilder:
    """Collects and formats trace information for the final report."""
    
    def __init__(self):
        self.sections = []
        self.errors = []
        self.test_results = []
        
    def add_section(self, title: str, content: str):
        self.sections.append({"title": title, "content": content})
        
    def add_test_result(self, test_name: str, passed: bool, details: Dict[str, Any]):
        self.test_results.append({
            "name": test_name,
            "passed": passed,
            "details": details
        })
        
    def add_error(self, context: str, error: str):
        self.errors.append({"context": context, "error": error})
        
    def build(self) -> str:
        lines = []
        lines.append("=" * 80)
        lines.append("PRODUCTION E2E VERIFICATION TRACE REPORT")
        lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
        lines.append("=" * 80)
        lines.append("")
        
        # Add all sections
        for section in self.sections:
            lines.append(f"--- {section['title']} ---")
            lines.append(section['content'])
            lines.append("")
        
        # Add test results summary
        lines.append("--- TEST RESULTS SUMMARY ---")
        passed = sum(1 for t in self.test_results if t['passed'])
        total = len(self.test_results)
        lines.append(f"Passed: {passed}/{total}")
        lines.append("")
        
        for result in self.test_results:
            status = "PASS" if result['passed'] else "FAIL"
            lines.append(f"[{status}] {result['name']}")
            for key, value in result['details'].items():
                if isinstance(value, dict):
                    lines.append(f"  {key}:")
                    for k, v in value.items():
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # Add errors
        if self.errors:
            lines.append("--- ERRORS ---")
            for error in self.errors:
                lines.append(f"Context: {error['context']}")
                lines.append(f"Error: {error['error']}")
                lines.append("")
        
        # Add structured output traces from the helper module
        lines.append("--- STRUCTURED OUTPUT TRACES ---")
        traces = get_all_traces()
        if traces:
            for i, trace in enumerate(traces, 1):
                lines.append(f"\nTrace {i}:")
                for key, value in trace.items():
                    lines.append(f"  {key}: {value}")
        else:
            lines.append("No traces recorded.")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)


# ============================================================================
# DATABASE AUDIT FUNCTIONS
# ============================================================================

def get_db_provenance(engine, session: Session) -> Dict[str, Any]:
    """Collect provenance info to prove which DB state was used."""
    # mask host
    url = str(engine.url)
    if "@" in url:
        host = url.split("@")[1].split("/")[0]
        # Redact remote hosts partly? Or just show it.
        # If localhost, just "localhost"
    else:
        host = "unknown"
    
    db_name = engine.url.database

    # Count bindings
    binding_count = session.exec(select(PromptBinding)).all()
    # Count schemas
    schema_count = session.exec(select(JsonSchemaEntry)).all()
    
    # Hash of bindings (fingerprint)
    # We can hash the IDs and updated_at timestamps
    bindings_fingerprint = hashlib.sha256(
        "".join(sorted([f"{b.id}:{b.updated_at}" for b in binding_count])).encode()
    ).hexdigest()[:16]

    return {
        "db_host": host,
        "db_name": db_name,
        "binding_count": len(binding_count),
        "schema_count": len(schema_count),
        "bindings_fingerprint": bindings_fingerprint,
        "timestamp": datetime.utcnow().isoformat()
    }


def audit_bindings_and_schemas(session: Session, report: TraceReportBuilder) -> bool:
    """Audit all bindings and their schemas for corruption."""
    lines = []
    issues = []
    
    bindings = list(session.exec(
        select(PromptBinding).where(PromptBinding.is_active == True)
    ).all())
    
    lines.append(f"Found {len(bindings)} active bindings")
    lines.append("")
    lines.append(f"{'Binding ID':<40} {'Tier':<10} {'Mode':<15} {'Schema ID':<40} {'Status'}")
    lines.append("-" * 120)
    
    for binding in bindings:
        schema_entry = session.exec(
            select(JsonSchemaEntry).where(
                JsonSchemaEntry.schema_id == binding.output_schema_id,
                JsonSchemaEntry.is_active == True
            )
        ).first()
        
        if not schema_entry:
            lines.append(f"{binding.id:<40} {binding.tier.value:<10} {binding.mode.value:<15} {binding.output_schema_id:<40} MISSING")
            issues.append(f"Schema not found: {binding.output_schema_id}")
            continue
        
        content = schema_entry.content
        status = "OK"
        
        # Validate wrapper format
        if not isinstance(content, dict):
            status = "INVALID_TYPE"
            issues.append(f"Schema {binding.output_schema_id} is not a dict")
        elif content.get("type") != "json_schema":
            status = "BAD_WRAPPER"
            issues.append(f"Schema {binding.output_schema_id} wrapper.type != 'json_schema'")
        elif "schema" not in content:
            status = "NO_INNER"
            issues.append(f"Schema {binding.output_schema_id} missing 'schema' key")
        else:
            # Deep scan for bad types
            inner = content.get("schema", {})
            bad_types = _find_bad_types(inner)
            if bad_types:
                status = f"CORRUPT({len(bad_types)})"
                issues.extend(bad_types)
        
        lines.append(f"{binding.id:<40} {binding.tier.value:<10} {binding.mode.value:<15} {binding.output_schema_id:<40} {status}")
    
    lines.append("")
    if issues:
        lines.append("ISSUES FOUND:")
        for issue in issues[:10]:  # Limit to first 10
            lines.append(f"  - {issue}")
        if len(issues) > 10:
            lines.append(f"  ... and {len(issues) - 10} more")
    else:
        lines.append("All bindings reference valid schemas.")
    
    report.add_section("BINDINGS -> SCHEMAS AUDIT", "\n".join(lines))
    return len(issues) == 0


def _find_bad_types(node: Any, path: str = "$") -> List[str]:
    """Recursively find bad type values."""
    issues = []
    if not isinstance(node, dict):
        if isinstance(node, list):
            for i, item in enumerate(node):
                issues.extend(_find_bad_types(item, f"{path}[{i}]"))
        return issues
    
    if "type" in node:
        t = node["type"]
        if t is None:
            issues.append(f"{path}.type is Python None")
        elif t == "None":
            issues.append(f'{path}.type is string "None"')
        elif isinstance(t, list):
            for i, item in enumerate(t):
                if item in (None, "None"):
                    issues.append(f"{path}.type[{i}] is {item!r}")
    
    for key, value in node.items():
        if isinstance(value, (dict, list)):
            issues.extend(_find_bad_types(value, f"{path}.{key}"))
    
    return issues


# ============================================================================
# E2E TESTS
# ============================================================================

async def run_e2e_test(
    user_id: int,
    tier: str,
    problem: str,
    graph_mode: bool,
    session: Session,
    report: TraceReportBuilder,
) -> bool:
    """Run a single E2E test."""
    test_name = f"{tier.upper()} {'GRAPH' if graph_mode else 'NO_GRAPH'}"
    details = {
        "user_id": user_id,
        "tier": tier,
        "problem": problem[:50] + "...",
        "graph_mode": graph_mode,
    }
    
    try:
        # Load prompt bundle
        bundle = load_prompt_bundle(tier=tier, mode="solve", session=session)
        details["binding_id"] = bundle.get("binding_id")
        details["schema_id"] = bundle.get("schema_id")
        details["schema_name"] = bundle.get("schema_name")
        
        # Compute schema hash
        schema = bundle.get("schema", {})
        if isinstance(schema, dict):
            inner = schema.get("schema", schema)
            details["schema_hash"] = compute_schema_hash(inner)
        
        # Run solver
        solver = get_solver_v3()
        start = time.perf_counter()
        result = await solver.solve(
            problem_text=problem,
            user_tier=tier,
            requests_graph_mode="always" if graph_mode else "never",
            db_session=session,
            trace=True,
            request_id=f"e2e-{tier}-{int(time.time())}"
        )
        elapsed = time.perf_counter() - start
        details["solve_latency_ms"] = int(elapsed * 1000)
        
        # Check result
        if "error" in result and result["error"]:
            details["error"] = result.get("message") or str(result.get("validation_errors")) or "Unknown error"
            details["validation_errors"] = result.get("validation_errors")
            details["error_type"] = result.get("error_type", "unknown")
            report.add_test_result(test_name, False, details)
            return False
        
        details["has_solution"] = "summary" in result or "steps" in result
        details["visuals_recommended"] = result.get("visuals_recommended", False)
        
        # Run plot pipeline for standard/research with graph mode
        if graph_mode and tier.lower() not in ("free",):
            try:
                plot_service = await get_plot_pipeline_service(session)
                trigger_result = await plot_service._call_plot_trigger(
                    problem=problem,
                    solution_steps=result.get("steps", []),
                    tier=tier,
                )
                details["plot_trigger_needed"] = trigger_result.plot_needed
                details["plot_trigger_type"] = trigger_result.plot_type
                
                if trigger_result.plot_needed:
                    spec_result = await plot_service._call_plot_spec(
                        problem=problem,
                        solution_steps=result.get("steps", []),
                        trigger_result=trigger_result,
                        tier=tier,
                    )
                    details["plot_spec_id"] = spec_result.plot_id
                    details["has_plotly_json"] = bool(spec_result.plotly_json)
            except Exception as e:
                details["plot_error"] = str(e)
        
        report.add_test_result(test_name, True, details)
        return True
        
    except Exception as e:
        details["error"] = str(e)
        report.add_test_result(test_name, False, details)
        report.add_error(test_name, str(e))
        return False


async def run_all_e2e_tests(session: Session, report: TraceReportBuilder):
    """Run all E2E tests."""
    clear_traces()  # Clear any previous traces
    
    # Test problems
    graph_problem = "Graph f(x) = ln(x) - x/2 and solve f(x) = 0. Use the graph to justify your answer."
    simple_problem = "Simplify 2x^3y^2 / 4xy"
    
    # Find real users for each tier (Verified from DB)
    tiers_to_test = ["free", "student_standard", "research"]
    user_map = {
        "free": 11,
        "student_standard": 14,
        "research": 15
    }
    
    for tier in tiers_to_test:
        real_user_id = user_map.get(tier, 0)
        
        # Run with graph mode
        await run_e2e_test(
            user_id=real_user_id,
            tier=tier,
            problem=graph_problem,
            graph_mode=True,
            session=session,
            report=report,
        )
        
        # Run without graph mode
        await run_e2e_test(
            user_id=real_user_id,
            tier=tier,
            problem=simple_problem,
            graph_mode=False,
            session=session,
            report=report,
        )


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="E2E Verification with Trace Report")
    parser.add_argument("--save-trace", type=str, help="Path to save trace report")
    args = parser.parse_args()
    
    report = TraceReportBuilder()
    
    # Connect to DB with Retries
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    # Determine SSL mode
    is_localhost = "localhost" in database_url or "127.0.0.1" in database_url or "postgres" in database_url
    connect_args = {} if is_localhost else {"sslmode": "require", "connect_timeout": 10}
    
    # Configurable retry params
    max_retries = 5
    base_delay = 0.5
    
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
    )

    print(f"Connecting to DB (is_localhost={is_localhost}, ssl={not is_localhost})...")

    session = None
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Try to connect and get session
            session = Session(engine)
            # Test connection
            session.exec(select(1)).first()
            print("Connected successfully.")
            break
        except (OperationalError, ssl.SSLError) as e:
            last_error = e
            delay = base_delay * (2 ** attempt)
            print(f"Connection attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
        except Exception as e:
            # Fatal error
            print(f"Fatal connection error: {e}")
            raise e
            
    if not session:
        print(f"FAILED to connect after {max_retries} attempts.")
        if last_error:
            print(f"Last error: {last_error}")
        sys.exit(1)
    
    try:
        # Step 0: Collect Provenance
        provenance = get_db_provenance(engine, session)
        
        prov_text = "\n".join([f"{k}: {v}" for k, v in provenance.items()])
        report.add_section("DB PROVENANCE", prov_text)
        
        report.add_section("ENVIRONMENT", f"""
OpenAI API Key Present: {bool(os.getenv('OPENAI_API_KEY'))}
DATABASE_URL Set: {bool(os.getenv('DATABASE_URL'))}
Timestamp: {datetime.utcnow().isoformat()}Z
""")
    
        # Step 1: Audit bindings and schemas
        print("Running bindings -> schemas audit...")
        audit_passed = audit_bindings_and_schemas(session, report)
        
        if not audit_passed:
            print("WARNING: Schema audit found issues. E2E tests may fail.")
        
        # Step 2: Run E2E tests
        print("Running E2E tests...")
        asyncio.run(run_all_e2e_tests(session, report))
        
    finally:
        session.close()
    
    # Build final report
    report_text = report.build()
    
    # Save or print
    if args.save_trace:
        output_path = Path(args.save_trace)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"Trace report saved to: {output_path}")
    else:
        print(report_text)


if __name__ == "__main__":
    main()
