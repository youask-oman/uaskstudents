from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlmodel import Session

from app.database import engine
from app.llm_profiles.profile_resolver import ProfileResolver
from app.models import PromptModeEnum, PromptTierEnum, User
from app.services.llm import get_llm_manager
from app.services.prompt_registry_service import prompt_registry_service
from app.services.solve.freeform_solver import (
    FREEFORM_OUTPUT_MODE,
    FREEFORM_PROMPT_ID,
    FREEFORM_PROMPT_VERSION,
    build_freeform_prompt,
    generate_freeform_solution,
    resolve_max_output_chars,
    resolve_num_predict,
    resolve_timeout_seconds,
)

try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass


TIER_ORDER = ["FREE", "STANDARD", "RESEARCH"]


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def _extract_output_text_from_response(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text:
        return text
    parts: List[str] = []
    for item in (getattr(response, "output", None) or []):
        for block in (getattr(item, "content", None) or []):
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str) and block_text:
                parts.append(block_text)
    return "".join(parts)


def _get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise RuntimeError(f"user_id={user_id} not found")
    return user


def _resolve_requested_mode_for_tier(tier: str) -> str:
    env_key = f"REPORT_MODE_{tier}"
    default_mode = "minimal" if tier == "FREE" else "detailed"
    mode = (os.environ.get(env_key) or default_mode).strip().lower()
    if mode not in {"minimal", "detailed", "improve", "concise"}:
        return default_mode
    return mode


def _resolve_num_predict_for_tier(
    tier: str,
    requested_mode: str,
    force_num_predict_all: Optional[int],
    force_num_predict_tier: Optional[int],
) -> int:
    if isinstance(force_num_predict_tier, int) and force_num_predict_tier > 0:
        return force_num_predict_tier
    if isinstance(force_num_predict_all, int) and force_num_predict_all > 0:
        return force_num_predict_all
    env_num_predict = int(os.environ.get("FREEFORM_NUM_PREDICT", "2500"))
    return resolve_num_predict(
        tier=tier,
        difficulty=None,
        requested_mode=requested_mode,
        env_default=env_num_predict,
    )


def _is_attempt_complete(
    captured_response: Optional[Dict[str, Any]],
    result_payload: Optional[Dict[str, Any]],
) -> bool:
    if not isinstance(captured_response, dict):
        return False
    status = str(captured_response.get("status") or "").strip().lower()
    incomplete_details = captured_response.get("incomplete_details")
    if status == "incomplete" or incomplete_details:
        return False
    if not isinstance(result_payload, dict):
        return False
    solution_doc = result_payload.get("solution_doc") or {}
    parse_status = str(solution_doc.get("parse_status") or "").strip().lower()
    final_answer = solution_doc.get("final_answer") or {}
    final_text = str(final_answer.get("text") or "").strip()
    final_latex = str(final_answer.get("latex") or "").strip()
    if parse_status not in {"ok", "partial"}:
        return False
    if not (final_text or final_latex):
        return False
    return True


async def _run_tier(
    *,
    session: Session,
    user: User,
    tier: str,
    question: str,
    model: str,
    forced_system_prompt: Optional[str],
    force_num_predict_all: Optional[int],
    force_num_predict_tier: Optional[int],
    max_attempts: int,
) -> Dict[str, Any]:
    requested_mode = _resolve_requested_mode_for_tier(tier)

    profile = ProfileResolver.resolve_profile(
        session=session,
        user=user,
        requested_mode=requested_mode,
        learning_mode="solve",
        force_tier=tier,
        mode_family="SOLVE",
        provider="openai",
    )
    binding_meta = getattr(profile, "prompt_binding_meta", {}) or {}

    tier_enum = PromptTierEnum[tier]
    freeform_prompt_entry = prompt_registry_service.get_active_freeform_prompt_for_tier(
        session=session,
        tier=tier_enum,
        provider="openai",
        model=model,
        mode=PromptModeEnum.SOLVE,
    )
    if not freeform_prompt_entry:
        raise RuntimeError(f"No active freeform prompt for tier={tier}")
    prompt_template = freeform_prompt_entry.content or ""
    prompt_id = freeform_prompt_entry.prompt_id or FREEFORM_PROMPT_ID
    prompt_version = str(freeform_prompt_entry.version or FREEFORM_PROMPT_VERSION)

    requires_graph = False
    prompt_sent = build_freeform_prompt(
        question,
        prompt_template,
        tier=tier,
        requested_mode=requested_mode,
        requires_graph=requires_graph,
    )

    base_num_predict = _resolve_num_predict_for_tier(
        tier=tier,
        requested_mode=requested_mode,
        force_num_predict_all=force_num_predict_all,
        force_num_predict_tier=force_num_predict_tier,
    )
    timeout_seconds = resolve_timeout_seconds(
        tier=tier,
        env_default=int(os.environ.get("FREEFORM_TIMEOUT_SECONDS", "120")),
    )
    max_output_chars = resolve_max_output_chars(
        tier=tier,
        env_default=int(os.environ.get("FREEFORM_MAX_OUTPUT_CHARS", "30000")),
    )

    llm_client = get_llm_manager().get_client("openai")
    sdk_client = llm_client.client

    captured: Dict[str, Any] = {
        "openai_payload_sent_full": None,
        "openai_response_full": None,
        "openai_raw_output_text_full": None,
    }

    original_responses_create = sdk_client.responses.create

    async def wrapped_responses_create(*args: Any, **kwargs: Any) -> Any:
        del args
        captured["openai_payload_sent_full"] = _json_safe(kwargs)
        response = await original_responses_create(**kwargs)
        captured["openai_response_full"] = _json_safe(response.model_dump() if hasattr(response, "model_dump") else str(response))
        captured["openai_raw_output_text_full"] = _extract_output_text_from_response(response)
        return response

    sdk_client.responses.create = wrapped_responses_create

    deltas: List[str] = []
    final_result = None
    run_started = datetime.utcnow().isoformat() + "Z"
    error_text: Optional[str] = None
    attempts_data: List[Dict[str, Any]] = []
    num_predict_used = base_num_predict
    final_attempt_num_predict = base_num_predict

    try:
        for attempt_number in range(1, max(1, max_attempts) + 1):
            final_attempt_num_predict = num_predict_used
            deltas = []
            final_result = None
            error_text = None
            captured["openai_payload_sent_full"] = None
            captured["openai_response_full"] = None
            captured["openai_raw_output_text_full"] = None

            try:
                async for event in generate_freeform_solution(
                    problem_text=question,
                    prompt_template=prompt_template,
                    model=model,
                    num_predict=num_predict_used,
                    timeout_seconds=timeout_seconds,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    tier=tier,
                    requested_mode=requested_mode,
                    requires_graph=requires_graph,
                    requires_domain_constraints=None,
                    system_prompt=forced_system_prompt
                    or (os.environ.get("FREEFORM_SYSTEM_PROMPT") or "").strip()
                    or None,
                ):
                    event_type = event.get("type")
                    if event_type == "delta":
                        text_chunk = str(event.get("text") or "")
                        if text_chunk:
                            deltas.append(text_chunk)
                    elif event_type == "result":
                        final_result = event.get("result")
            except Exception as exc:
                error_text = f"{exc.__class__.__name__}: {exc}"

            result_payload = asdict(final_result) if final_result is not None else None
            complete = _is_attempt_complete(captured.get("openai_response_full"), result_payload if isinstance(result_payload, dict) else None)
            attempts_data.append(
                {
                    "attempt_number": attempt_number,
                    "num_predict_used": num_predict_used,
                    "complete": complete,
                    "error": error_text,
                    "openai_status": (captured.get("openai_response_full") or {}).get("status")
                    if isinstance(captured.get("openai_response_full"), dict)
                    else None,
                    "openai_incomplete_details": (captured.get("openai_response_full") or {}).get("incomplete_details")
                    if isinstance(captured.get("openai_response_full"), dict)
                    else None,
                    "solution_parse_status": ((result_payload or {}).get("solution_doc") or {}).get("parse_status")
                    if isinstance(result_payload, dict)
                    else None,
                }
            )
            if complete:
                break
            num_predict_used = min(12000, int(num_predict_used * 1.8))
    finally:
        sdk_client.responses.create = original_responses_create

    run_finished = datetime.utcnow().isoformat() + "Z"

    system_prompt_sent = ""
    openai_payload = captured.get("openai_payload_sent_full")
    if isinstance(openai_payload, dict):
        for item in openai_payload.get("input", []):
            if item.get("role") != "system":
                continue
            parts = item.get("content") or []
            if isinstance(parts, list):
                combined = []
                for part in parts:
                    if isinstance(part, dict):
                        combined.append(str(part.get("text") or ""))
                system_prompt_sent = "".join(combined)
                break

    binding_snapshot = {
        "binding": {
            "id": binding_meta.get("binding_id"),
            "tier": profile.tier,
            "mode": "SOLVE",
            "global_system_prompt_id": binding_meta.get("global_system_prompt_id"),
            "developer_prompt_id": binding_meta.get("developer_prompt_id"),
            "output_schema_id": binding_meta.get("output_schema_id"),
            "global_system_prompt_version": binding_meta.get("global_system_prompt_version"),
            "developer_prompt_version": binding_meta.get("developer_prompt_version"),
            "output_schema_version": binding_meta.get("output_schema_version"),
        },
        "global_system_prompt": None,
        "developer_prompt": None,
        "output_schema": None,
    }
    if binding_meta.get("global_system_prompt_id"):
        entry = prompt_registry_service.get_active_prompt(session, binding_meta["global_system_prompt_id"])
        if entry:
            binding_snapshot["global_system_prompt"] = {
                "prompt_id": entry.prompt_id,
                "version": entry.version,
                "content": entry.content,
                "tier": str(entry.tier) if entry.tier is not None else None,
                "mode": str(entry.mode),
                "role": str(entry.role),
                "is_active": entry.is_active,
            }
    if binding_meta.get("developer_prompt_id"):
        entry = prompt_registry_service.get_active_prompt(session, binding_meta["developer_prompt_id"])
        if entry:
            binding_snapshot["developer_prompt"] = {
                "prompt_id": entry.prompt_id,
                "version": entry.version,
                "content": entry.content,
                "tier": str(entry.tier) if entry.tier is not None else None,
                "mode": str(entry.mode),
                "role": str(entry.role),
                "is_active": entry.is_active,
            }
    if binding_meta.get("output_schema_id"):
        entry = prompt_registry_service.get_active_schema(session, binding_meta["output_schema_id"])
        if entry:
            binding_snapshot["output_schema"] = {
                "schema_id": entry.schema_id,
                "version": entry.version,
                "content": entry.content,
                "is_active": entry.is_active,
            }

    result_payload = asdict(final_result) if final_result is not None else None
    normalized_output = result_payload.get("output_text") if isinstance(result_payload, dict) else None
    solution_doc = result_payload.get("solution_doc") if isinstance(result_payload, dict) else None
    validation = result_payload.get("validation") if isinstance(result_payload, dict) else None

    return {
        "tier": tier,
        "requested_mode_sent": requested_mode,
        "resolved_profile": {
            "tier": profile.tier,
            "mode": profile.mode,
            "max_output_tokens": profile.max_output_tokens,
            "max_steps": profile.max_steps,
            "prompt_binding_meta": binding_meta,
        },
        "output_format_route_selected": FREEFORM_OUTPUT_MODE.lower(),
        "provider": "openai",
        "model": model,
        "from_where_data_comes": {
            "system_prompt_used_source": "ProfileResolver.resolve_profile -> prompts/db_loader.py -> prompt_bindings + prompt_templates",
            "tier_freeform_prompt_template_source": "prompt_registry_service.get_active_freeform_prompt_for_tier -> prompt_templates",
            "json_schema_sent_to_openai_source": "generate_freeform_solution passes json_schema=None to OpenAIClient.generate",
            "openai_payload_shape_source": "app/services/llm/clients.py::OpenAIClient.generate",
            "runtime_flow_source": "app/api.py::solve_v3_stream_endpoint",
            "db_tables": ["prompt_bindings", "prompt_templates", "json_schemas"],
            "env_file": ".env",
        },
        "resolved_runtime_limits": {
            "num_predict": base_num_predict,
            "num_predict_used_final_attempt": final_attempt_num_predict,
            "timeout_seconds": timeout_seconds,
            "max_output_chars_post_cap": max_output_chars,
            "verbosity": "high" if requested_mode in {"detailed", "improve"} else "low",
            "reasoning_effort": (os.environ.get("OPENAI_REASONING_EFFORT") or "minimal").strip().lower(),
        },
        "forced_runtime_overrides": {
            "forced_system_prompt_applied": bool(forced_system_prompt),
            "forced_num_predict_all": force_num_predict_all,
            "forced_num_predict_tier": force_num_predict_tier,
            "max_attempts": max_attempts,
        },
        "system_prompt_used_full": system_prompt_sent or (profile.system_prompt_content or ""),
        "json_schema_used_in_openai_request": None,
        "json_schema_used_note": "No JSON schema is sent in freeform solve path.",
        "db_freeform_prompt_entry": {
            "id": str(freeform_prompt_entry.id),
            "prompt_id": freeform_prompt_entry.prompt_id,
            "version": freeform_prompt_entry.version,
            "tier": str(freeform_prompt_entry.tier),
            "mode": str(freeform_prompt_entry.mode),
            "role": str(freeform_prompt_entry.role),
            "is_active": freeform_prompt_entry.is_active,
        },
        "db_freeform_prompt_template_full": prompt_template,
        "user_prompt_sent_to_openai_full": prompt_sent,
        "exact_openai_payload_sent_full": openai_payload,
        "exact_output_from_openai_full": captured.get("openai_raw_output_text_full"),
        "exact_openai_response_object_full": captured.get("openai_response_full"),
        "normalized_output_after_backend_full": normalized_output,
        "solution_doc_after_backend_full": solution_doc,
        "validation_after_backend_full": validation,
        "streamed_delta_reconstruction_full": "".join(deltas),
        "run_window_utc": {
            "started_at": run_started,
            "finished_at": run_finished,
        },
        "attempts": attempts_data,
        "error": error_text,
        "db_active_solve_binding_for_tier_full": binding_snapshot,
    }


async def _run_report(
    question: str,
    user_id: int,
    output_file: Path,
    forced_system_prompt: Optional[str],
    force_num_predict_all: Optional[int],
    force_num_predict_per_tier: Dict[str, Optional[int]],
    max_attempts: int,
) -> Dict[str, Any]:
    model = (os.environ.get("OPENAI_MODEL_DEFAULT") or "").strip()
    if not model:
        raise RuntimeError("OPENAI_MODEL_DEFAULT is not configured")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    with Session(engine) as session:
        user = _get_user(session, user_id)

        tiers_data: List[Dict[str, Any]] = []
        for tier in TIER_ORDER:
            tiers_data.append(
                await _run_tier(
                    session=session,
                    user=user,
                    tier=tier,
                    question=question,
                    model=model,
                    forced_system_prompt=forced_system_prompt,
                    force_num_predict_all=force_num_predict_all,
                    force_num_predict_tier=force_num_predict_per_tier.get(tier),
                    max_attempts=max_attempts,
                )
            )

    report = {
        "report_generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "report_file": str(output_file.resolve()),
        "provider": "openai",
        "model": model,
        "problem_text_used_for_all_tiers": question,
        "important_note": "This report captures exact OpenAI request payloads and exact OpenAI outputs for current backend runtime.",
        "code_sources": {
            "openai_payload_builder": "backend/app/services/llm/clients.py::OpenAIClient.generate",
            "freeform_request_builder": "backend/app/services/solve/freeform_solver.py::generate_freeform_solution",
            "tier_prompt_selection": "backend/app/services/prompt_registry_service.py::get_active_freeform_prompt_for_tier",
            "profile_resolution": "backend/app/llm_profiles/profile_resolver.py::ProfileResolver.resolve_profile",
            "runtime_flow_reference": "backend/app/api.py::solve_v3_stream_endpoint",
        },
        "config_sources": {
            "env_file": ".env",
            "prompt_templates_table": "prompt_templates",
            "prompt_bindings_table": "prompt_bindings",
            "json_schemas_table": "json_schemas",
        },
        "forced_overrides_applied": {
            "forced_system_prompt": bool(forced_system_prompt),
            "force_num_predict_all": force_num_predict_all,
            "force_num_predict_per_tier": force_num_predict_per_tier,
            "max_attempts_per_tier": max_attempts,
        },
        "tiers": tiers_data,
    }
    return report


def _write_report_txt(report: Dict[str, Any], output_file: Path) -> None:
    lines: List[str] = []
    lines.append("=" * 120)
    lines.append("OPENAI FULL PAYLOAD REPORT (NO TRUNCATION)")
    lines.append("=" * 120)
    lines.append(json.dumps({k: v for k, v in report.items() if k != "tiers"}, ensure_ascii=False, indent=2))
    lines.append("")
    for tier_data in report.get("tiers", []):
        lines.append("-" * 120)
        lines.append(f"TIER REPORT: {tier_data.get('tier')}")
        lines.append("-" * 120)
        lines.append(json.dumps(tier_data, ensure_ascii=False, indent=2))
        lines.append("")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate full OpenAI freeform payload report for FREE/STANDARD/RESEARCH tiers.")
    parser.add_argument("--question", required=True, help="Math question to run for all tiers.")
    parser.add_argument("--user-id", type=int, default=3, help="Existing user id for profile resolution.")
    parser.add_argument("--output-file", default="", help="Optional output .txt file path.")
    parser.add_argument("--force-system-prompt", default="", help="Force this exact system prompt for all tiers.")
    parser.add_argument("--force-num-predict", type=int, default=0, help="Force num_predict for all tiers.")
    parser.add_argument("--force-num-predict-free", type=int, default=0, help="Force num_predict for FREE tier.")
    parser.add_argument("--force-num-predict-standard", type=int, default=0, help="Force num_predict for STANDARD tier.")
    parser.add_argument("--force-num-predict-research", type=int, default=0, help="Force num_predict for RESEARCH tier.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Max retry attempts per tier to obtain complete output.")
    args = parser.parse_args()

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    default_backend_dir = Path(__file__).resolve().parents[2]
    output_file = Path(args.output_file) if args.output_file else default_backend_dir / f"openai_full_payload_report_{timestamp}.txt"

    forced_system_prompt = (args.force_system_prompt or "").strip() or None
    force_num_predict_all = args.force_num_predict if args.force_num_predict > 0 else None
    force_num_predict_per_tier = {
        "FREE": args.force_num_predict_free if args.force_num_predict_free > 0 else None,
        "STANDARD": args.force_num_predict_standard if args.force_num_predict_standard > 0 else None,
        "RESEARCH": args.force_num_predict_research if args.force_num_predict_research > 0 else None,
    }

    report = asyncio.run(
        _run_report(
            args.question,
            args.user_id,
            output_file,
            forced_system_prompt,
            force_num_predict_all,
            force_num_predict_per_tier,
            max(1, args.max_attempts),
        )
    )
    _write_report_txt(report, output_file)
    print(str(output_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
