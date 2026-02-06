"""
E2E Integration Test for Structured Output Production Fixes

This script tests the complete solver pipeline with real DB data.
It validates all the production fixes across FREE, STANDARD, and RESEARCH tiers.

Usage:
    python tests/e2e_test_structured_outputs.py [--tier FREE|STANDARD|RESEARCH]
    
Outputs:
    Trace report saved to: e2e_structured_output_trace_report.json
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment
os.environ.setdefault("TESTING", "1")

# Load .env from parent directory
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


async def run_e2e_test(tier: str = "STANDARD") -> Dict[str, Any]:
    """Run E2E test for a specific tier."""
    from sqlmodel import Session, select
    from app.database import engine
    from app.services.solver_v3 import get_solver_v3
    from app.llm_profiles.profile_resolver import ProfileResolver
    from app.models import User
    
    trace_report = {
        "test_id": f"e2e_{tier}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "tier": tier,
        "started_at": datetime.utcnow().isoformat(),
        "tests": [],
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    }
    
    # Test cases
    test_cases = [
        {
            "name": "simple_arithmetic",
            "problem": "Solve: 2 + 2 = ?",
            "mode": "minimal",
            "learning_mode": "solve",
            "expect_plot": False
        },
        {
            "name": "algebra_equation",
            "problem": "Solve for x: 3x + 5 = 20",
            "mode": "detailed",
            "learning_mode": "solve",
            "expect_plot": False
        },
        {
            "name": "quadratic_with_plot",
            "problem": "Graph f(x) = x^2 - 4x + 3 and find the roots",
            "mode": "detailed",
            "learning_mode": "solve",
            "expect_plot": tier != "FREE"  # FREE tier has plots disabled
        },
    ]
    
    with Session(engine) as session:
        # Find a test user for the given tier
        test_user = None
        try:
            # Try to find user with matching subscription tier
            from app.models import Subscription, Plan
            stmt = (
                select(User)
                .join(Subscription, User.id == Subscription.user_id)
                .join(Plan, Subscription.plan_id == Plan.id)
                .where(Plan.slug.ilike(f"%{tier.lower()}%"))
                .limit(1)
            )
            test_user = session.exec(stmt).first()
        except Exception as e:
            trace_report["summary"]["errors"].append(f"Failed to find test user: {e}")
        
        solver = get_solver_v3()
        
        for i, test_case in enumerate(test_cases):
            test_result = {
                "name": test_case["name"],
                "tier": tier,
                "mode": test_case["mode"],
                "started_at": datetime.utcnow().isoformat(),
                "request_id": f"e2e_{tier}_{i}_{datetime.utcnow().strftime('%H%M%S')}",
                "passed": False,
                "checks": [],
                "telemetry": {},
                "error": None
            }
            
            try:
                # Resolve profile from DB
                profile = ProfileResolver.resolve_profile(
                    session,
                    test_user,
                    requested_mode=test_case["mode"],
                    learning_mode=test_case["learning_mode"],
                    force_tier=tier,
                    mode_family="SOLVE",
                    provider="openai"
                )
                
                # Check 1: Profile resolution
                test_result["checks"].append({
                    "name": "profile_resolution",
                    "passed": profile is not None,
                    "details": {
                        "tier": profile.tier if profile else None,
                        "mode": profile.mode if profile else None,
                        "max_output_tokens": profile.max_output_tokens if profile else None,
                        "has_system_prompt": bool(profile.system_prompt_content) if profile else False,
                        "has_schema": bool(profile.json_schema_content) if profile else False
                    }
                })
                
                if not profile:
                    test_result["error"] = "Profile resolution failed"
                    trace_report["tests"].append(test_result)
                    continue
                
                # Check 2: Schema wrapper is valid (no half-wrapper)
                schema_valid = True
                schema_error = None
                if profile.json_schema_content:
                    from app.utils.schema_wrapper_validator import validate_schema_wrapper, SchemaWrapperCorruptError
                    try:
                        validate_schema_wrapper(profile.json_schema_content, context="e2e_test")
                    except SchemaWrapperCorruptError as e:
                        schema_valid = False
                        schema_error = str(e)
                
                test_result["checks"].append({
                    "name": "schema_wrapper_valid",
                    "passed": schema_valid,
                    "details": {
                        "wrapper_keys": list(profile.json_schema_content.keys()) if isinstance(profile.json_schema_content, dict) else None,
                        "schema_name": profile.json_schema_content.get("name") if isinstance(profile.json_schema_content, dict) else None,
                        "error": schema_error
                    }
                })
                
                if not schema_valid:
                    test_result["error"] = f"Schema wrapper corrupt: {schema_error}"
                    trace_report["tests"].append(test_result)
                    continue
                
                # Run the solver
                result = await solver.solve(
                    problem_text=test_case["problem"],
                    context=f"Test tier: {tier}",
                    trace=True,
                    request_id=test_result["request_id"],
                    user_id=test_user.id if test_user else None,
                    db_session=session,
                    trusted_context={
                        "tier": tier,
                        "learning_mode": test_case["learning_mode"],
                        "features_used": {"plot_requested": test_case["expect_plot"]}
                    },
                    requested_mode=test_case["mode"],
                    requests_graph_mode="auto" if test_case["expect_plot"] else "off"
                )
                
                # Check 3: Response structure valid
                is_error = "error" in result and result.get("error")
                has_solution = "solution" in result or "steps" in result
                
                test_result["checks"].append({
                    "name": "response_structure",
                    "passed": not is_error and has_solution,
                    "details": {
                        "has_error": is_error,
                        "has_solution": has_solution,
                        "has_telemetry": "_telemetry" in result or "telemetry" in result
                    }
                })
                
                # Extract telemetry
                telemetry = result.get("_telemetry") or result.get("telemetry") or {}
                test_result["telemetry"] = {
                    k: v for k, v in telemetry.items()
                    if k in [
                        "binding_max_output", "effective_max_output_used", "policy_source",
                        "policy_limit", "plot_requested_effective", "graph_mode_param",
                        "mode_resolved", "tier_effective", "validated", "repaired"
                    ]
                }
                
                # Check 4: Token policy fields present (STEP 5)
                has_token_fields = all(k in telemetry for k in ["binding_max_output", "effective_max_output_used", "policy_source"])
                test_result["checks"].append({
                    "name": "token_policy_fields",
                    "passed": has_token_fields,
                    "details": {
                        "binding_max_output": telemetry.get("binding_max_output"),
                        "effective_max_output_used": telemetry.get("effective_max_output_used"),
                        "policy_source": telemetry.get("policy_source")
                    }
                })
                
                # Check 5: Plot flags normalized (STEP 6)
                plot_field_present = "plot_requested_effective" in telemetry
                test_result["checks"].append({
                    "name": "plot_flags_normalized",
                    "passed": plot_field_present,
                    "details": {
                        "plot_requested_effective": telemetry.get("plot_requested_effective"),
                        "graph_mode_param": telemetry.get("graph_mode_param")
                    }
                })
                
                # Check 6: RESEARCH tier uses binding, not policy cap
                if tier == "RESEARCH":
                    binding = telemetry.get("binding_max_output", 0)
                    effective = telemetry.get("effective_max_output_used", 0)
                    source = telemetry.get("policy_source", "")
                    research_ok = source == "binding" or effective == binding
                    test_result["checks"].append({
                        "name": "research_tier_binding",
                        "passed": research_ok,
                        "details": {
                            "binding": binding,
                            "effective": effective,
                            "source": source
                        }
                    })
                
                # Check 7: FREE tier has plots disabled
                if tier == "FREE":
                    plot_effective = telemetry.get("plot_requested_effective", True)
                    free_plot_ok = plot_effective is False
                    test_result["checks"].append({
                        "name": "free_tier_plots_disabled",
                        "passed": free_plot_ok,
                        "details": {
                            "plot_requested_effective": plot_effective
                        }
                    })
                
                # Determine overall pass/fail
                all_checks_passed = all(c["passed"] for c in test_result["checks"])
                test_result["passed"] = all_checks_passed
                test_result["finished_at"] = datetime.utcnow().isoformat()
                
            except Exception as e:
                import traceback
                test_result["error"] = str(e)
                test_result["traceback"] = traceback.format_exc()
                test_result["finished_at"] = datetime.utcnow().isoformat()
            
            trace_report["tests"].append(test_result)
            trace_report["summary"]["total"] += 1
            if test_result["passed"]:
                trace_report["summary"]["passed"] += 1
            else:
                trace_report["summary"]["failed"] += 1
                if test_result.get("error"):
                    trace_report["summary"]["errors"].append(f"{test_case['name']}: {test_result['error']}")
    
    trace_report["finished_at"] = datetime.utcnow().isoformat()
    return trace_report


async def main():
    parser = argparse.ArgumentParser(description="E2E Structured Output Tests")
    parser.add_argument("--tier", choices=["FREE", "STANDARD", "RESEARCH", "ALL"], default="STANDARD")
    args = parser.parse_args()
    
    output_dir = Path(__file__).parent.parent / "artifacts"
    output_dir.mkdir(exist_ok=True)
    
    all_reports = []
    
    tiers = ["FREE", "STANDARD", "RESEARCH"] if args.tier == "ALL" else [args.tier]
    
    for tier in tiers:
        print(f"\n{'='*60}")
        print(f"Running E2E tests for {tier} tier...")
        print("="*60)
        
        report = await run_e2e_test(tier)
        all_reports.append(report)
        
        # Print summary
        print(f"\n{tier} Results: {report['summary']['passed']}/{report['summary']['total']} passed")
        for test in report["tests"]:
            status = "✅" if test["passed"] else "❌"
            print(f"  {status} {test['name']}")
            for check in test.get("checks", []):
                c_status = "✓" if check["passed"] else "✗"
                print(f"      {c_status} {check['name']}")
    
    # Save combined report
    combined_report = {
        "generated_at": datetime.utcnow().isoformat(),
        "tiers_tested": tiers,
        "reports": all_reports,
        "overall_summary": {
            "total": sum(r["summary"]["total"] for r in all_reports),
            "passed": sum(r["summary"]["passed"] for r in all_reports),
            "failed": sum(r["summary"]["failed"] for r in all_reports),
        }
    }
    
    output_file = output_dir / "e2e_structured_output_trace_report.json"
    with open(output_file, "w") as f:
        json.dump(combined_report, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Trace report saved to: {output_file}")
    print(f"Overall: {combined_report['overall_summary']['passed']}/{combined_report['overall_summary']['total']} passed")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
