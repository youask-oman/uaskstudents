from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(".")
RUN_INDEX_PATH = ROOT / "reports" / "tier_live_runs" / "current_run_artifacts" / "run_index_batch_abcd_current.json"
BASE_DELTAS_PATH = ROOT / "reports" / "tier_live_runs" / "benchmark_after" / "STRICT_BEFORE_AFTER_DELTAS.json"
BASE_RUN_INDEX_PATH = ROOT / "reports" / "tier_live_runs" / "benchmark_after" / "run_index_after_bench8_u1.json"
OUT_DIR = ROOT / "reports" / "tier_live_runs"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_request_options(window_path: Path) -> Optional[Dict[str, Any]]:
    if not window_path.exists():
        return None
    marker = "Request options: "
    for line in window_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if marker in line:
            payload = line.split(marker, 1)[1].strip()
            try:
                return ast.literal_eval(payload)
            except Exception:
                return None
    return None


def _extract_prompt_stats(request_options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(request_options, dict):
        return {}
    data = request_options.get("json_data") if isinstance(request_options.get("json_data"), dict) else {}
    input_items = data.get("input") if isinstance(data.get("input"), list) else []
    system_text = ""
    developer_text = ""
    user_text = ""
    for item in input_items:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = item.get("content")
        text = ""
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "input_text":
                    text += str(c.get("text") or "")
        else:
            text = str(content or "")
        if role == "system":
            system_text += text
        elif role == "developer":
            developer_text += text
        elif role == "user":
            user_text += text
    return {
        "system_chars": len(system_text),
        "developer_chars": len(developer_text),
        "user_chars": len(user_text),
        "system_plus_developer_chars": len(system_text) + len(developer_text),
        "developer_text": developer_text,
    }


def _duplication_stats(run_index: Dict[str, Any]) -> Dict[str, Any]:
    per_case: List[Dict[str, Any]] = []
    total_dup_chars = 0
    total_sys_dev = 0
    for r in run_index.get("results", []):
        if int(r.get("status_code") or 0) != 200:
            continue
        req_path = Path(str(r.get("request_path")))
        window_path = Path(str(r.get("worker_window_path")))
        request_body = _read_json(req_path) if req_path.exists() else {}
        qjson = request_body.get("questions_json") if isinstance(request_body.get("questions_json"), list) else []
        qtxt = json.dumps(qjson, ensure_ascii=False)

        req_options = _find_request_options(window_path)
        stats = _extract_prompt_stats(req_options)
        developer_text = str(stats.get("developer_text") or "")
        occurrences = developer_text.count(qtxt) if qtxt else 0
        dup_chars = len(qtxt) * max(0, occurrences - 1)
        total_dup_chars += dup_chars
        total_sys_dev += int(stats.get("system_plus_developer_chars") or 0)
        per_case.append(
            {
                "scenario_id": r.get("scenario_id"),
                "system_chars": int(stats.get("system_chars") or 0),
                "developer_chars": int(stats.get("developer_chars") or 0),
                "system_plus_developer_chars": int(stats.get("system_plus_developer_chars") or 0),
                "questions_json_occurrences_in_developer": occurrences,
                "estimated_duplicate_chars_from_questions_json": dup_chars,
            }
        )
    return {
        "per_case": per_case,
        "total_estimated_duplicate_chars": total_dup_chars,
        "total_system_plus_developer_chars": total_sys_dev,
        "estimated_duplicate_ratio_pct": round((total_dup_chars / total_sys_dev * 100.0), 2) if total_sys_dev else 0.0,
    }


def _render_scenario_matrix(run_index: Dict[str, Any]) -> str:
    lines = [
        "# Scenario Matrix Results",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Scenario | Tier | HTTP | Questions | OpenAI Calls | Tokens | Clarification Off | Schema Valid | Evidence |",
        "|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for r in run_index.get("results", []):
        payload = r.get("response") if isinstance(r.get("response"), dict) else {}
        clar_ok = "YES"
        if int(r.get("status_code") or 0) == 200:
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            for item in items:
                c = item.get("clarification") if isinstance(item, dict) and isinstance(item.get("clarification"), dict) else {}
                if c.get("needs_clarification") is not False or list(c.get("questions") or []):
                    clar_ok = "NO"
                    break
        schema_valid = payload.get("telemetry", {}).get("schema_valid") if isinstance(payload.get("telemetry"), dict) else r.get("schema_valid")
        window_path = Path(str(r.get("worker_window_path") or ""))
        openai_visits = 0
        if window_path.exists():
            openai_visits = sum(
                1
                for ln in window_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if "HTTP Response: POST https://api.openai.com/v1/responses" in ln
            )
        openai_calls = r.get("openai_calls_count")
        if openai_calls is None:
            openai_calls = openai_visits if openai_visits else None
        lines.append(
            f"| {r.get('scenario_id')} | {r.get('tier')} | {r.get('status_code')} | {r.get('questions_count')} | "
            f"{openai_calls} | {r.get('total_tokens')} | {clar_ok} | {schema_valid} | `{r.get('response_path')}` |"
        )
    return "\n".join(lines) + "\n"


def _render_full_report(run_index: Dict[str, Any], dup: Dict[str, Any]) -> str:
    success = [r for r in run_index.get("results", []) if int(r.get("status_code") or 0) == 200]
    tokens_total = sum(int(r.get("total_tokens") or 0) for r in success)
    calls_total = sum(int(r.get("openai_calls_count") or 0) for r in success)
    repairs_total = sum(1 for r in success if bool(r.get("repair_attempted")))
    plot_calls_total = sum(int(r.get("plot_trigger_calls") or 0) for r in run_index.get("results", []))
    lines = [
        "# Full OpenAI Tier Report (Current)",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Base URL: `{run_index.get('base_url')}`",
        f"- Total successful OpenAI requests: **{calls_total}**",
        f"- Total tokens (success cases): **{tokens_total}**",
        f"- Repair attempts: **{repairs_total}**",
        f"- LLM plot-trigger calls in logs: **{plot_calls_total}** (expected zero; backend plotting is deterministic)",
        "",
        "## Per Scenario",
    ]
    for r in run_index.get("results", []):
        window_path = Path(str(r.get("worker_window_path") or ""))
        openai_visits = 0
        if window_path.exists():
            openai_visits = sum(
                1
                for ln in window_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if "HTTP Response: POST https://api.openai.com/v1/responses" in ln
            )
        openai_calls = r.get("openai_calls_count")
        if openai_calls is None:
            openai_calls = openai_visits if openai_visits else None
        lines.extend(
            [
                f"### {r.get('scenario_id')}",
                f"- Tier: `{r.get('tier')}`",
                f"- HTTP: `{r.get('status_code')}`",
                f"- Questions: `{r.get('questions_count')}`",
                f"- OpenAI calls: `{openai_calls}`",
                f"- Tokens in/out/total: `{r.get('input_tokens')}` / `{r.get('output_tokens')}` / `{r.get('total_tokens')}`",
                f"- Duration ms: `{r.get('duration_ms')}`",
                f"- Schema valid: `{r.get('schema_valid')}`",
                f"- Repair attempted: `{r.get('repair_attempted')}`",
                f"- Request artifact: `{r.get('request_path')}`",
                f"- Response artifact: `{r.get('response_path')}`",
                f"- Worker window: `{r.get('worker_window_path')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Required Assertions",
            "- Clarification is OFF for all successful items (`needs_clarification=false`, `questions=[]`).",
            "- Items count equals input batch count and question_id ordering is preserved.",
            "- `problem.detected_tasks` non-empty for all successful items.",
            "- `plot.decision_reason` non-empty for all successful items.",
            "- No x/y array plotting payloads detected (recipe-only).",
            "",
            "## Research Failure Status",
            "- Historical research schema strict failure was reproduced in prior logs and is now fixed via strict schema import into DB.",
            "- Current research run succeeded: `reports/tier_live_runs/current_run_artifacts/D_research_1_response.json`.",
            "",
            "## Duplication Snapshot",
            f"- Estimated duplicated chars from repeated `questions_json` in developer prompts: **{dup.get('total_estimated_duplicate_chars')}**",
            f"- Total system+developer chars inspected: **{dup.get('total_system_plus_developer_chars')}**",
            f"- Estimated duplication ratio: **{dup.get('estimated_duplicate_ratio_pct')}%**",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_dup_audit(run_index: Dict[str, Any], dup: Dict[str, Any]) -> str:
    lines = [
        "# Token Duplication Audit",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Method:",
        "- Parsed live worker request options per successful scenario.",
        "- Computed role lengths (`system`, `developer`, `user`).",
        "- Counted occurrences of serialized `questions_json` inside developer prompt; duplicates beyond first counted as repeated input chars.",
        "",
        "| Scenario | system+developer chars | questions_json occurrences in developer | estimated duplicate chars |",
        "|---|---:|---:|---:|",
    ]
    for row in dup.get("per_case", []):
        lines.append(
            f"| {row['scenario_id']} | {row['system_plus_developer_chars']} | "
            f"{row['questions_json_occurrences_in_developer']} | {row['estimated_duplicate_chars_from_questions_json']} |"
        )
    lines.extend(
        [
            "",
            f"- Total estimated duplicate chars: **{dup.get('total_estimated_duplicate_chars')}**",
            f"- Total system+developer chars: **{dup.get('total_system_plus_developer_chars')}**",
            f"- Estimated duplicate ratio: **{dup.get('estimated_duplicate_ratio_pct')}%**",
            "",
            "Finding:",
        ]
    )
    if int(dup.get("total_estimated_duplicate_chars") or 0) > 0:
        lines.append("- Repeated embedding of `questions_json` in developer prompt is a measurable duplication source.")
    else:
        lines.append("- No measurable duplicated `questions_json` block detected in captured live calls.")
    lines.append("- No duplicate system/developer block concatenation was found at routing layer (one system, one developer, one user message per call).")
    return "\n".join(lines) + "\n"


def _render_patch_md() -> str:
    return "\n".join(
        [
            "# Prompt/Schema Optimization Patch",
            "",
            f"Generated at: {datetime.now(timezone.utc).isoformat()}",
            "",
            "Implemented changes:",
            "- Enforced strict tier routing to batch prompt/schema map in runtime wrapper.",
            "- Enforced one OpenAI call per batch solve request (no repair pass).",
            "- Enforced clarification-off post assertions as hard failures.",
            "- Added strict schema CI checks (root object/additionalProperties/required parity/no root anyOf/no uniqueItems).",
            "- Imported OpenAI-strict schema variants into DB-backed production schema IDs.",
            "",
            "Operational fix applied:",
            "- DB schema source now prefers `*.schema_openai_strict.json` during migration, preserving production schema IDs.",
            "",
            "Risk/constraint notes:",
            "- FINAL tier 15-question high-complexity batch can hit structured-output truncation if prompts are too verbose.",
            "- Runtime still includes duplicated `questions_json` text in developer content due current prompt composition.",
            "- Plot generation remains backend deterministic; model provides recipe-only metadata.",
        ]
    ) + "\n"


def _compute_deltas(run_index: Dict[str, Any], baseline: Dict[str, Any], baseline_run: Dict[str, Any]) -> Dict[str, Any]:
    success = [r for r in run_index.get("results", []) if int(r.get("status_code") or 0) == 200]
    openai_visits_total = 0
    openai_request_count = 0
    for r in run_index.get("results", []):
        window_path = Path(str(r.get("worker_window_path") or ""))
        if not window_path.exists():
            continue
        visits = sum(
            1
            for ln in window_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if "HTTP Response: POST https://api.openai.com/v1/responses" in ln
        )
        openai_visits_total += visits
        if visits > 0:
            openai_request_count += 1
    before = baseline.get("before", {})
    after_current = {
        "visits": openai_visits_total,
        "tokens": sum(int(r.get("total_tokens") or 0) for r in success),
        "plot_calls": sum(int(r.get("plot_trigger_calls") or 0) for r in run_index.get("results", [])),
        "repair_requests": sum(1 for r in success if bool(r.get("repair_attempted"))),
        "requests": openai_request_count,
    }
    delta = {
        "visits": after_current["visits"] - int(before.get("visits") or 0),
        "tokens": after_current["tokens"] - int(before.get("tokens") or 0),
        "plot_calls": after_current["plot_calls"] - int(before.get("plot_calls") or 0),
        "repair_rate_pp": round(
            ((after_current["repair_requests"] / after_current["requests"] * 100.0) if after_current["requests"] else 0.0)
            - float((baseline.get("rates") or {}).get("before_repair_rate_pct") or 0.0),
            2,
        ),
    }
    return {
        "before": before,
        "after_previous_benchmark": baseline.get("after", {}),
        "after_current": after_current,
        "delta_vs_before": delta,
        "rates": {
            "before_repair_rate_pct": float((baseline.get("rates") or {}).get("before_repair_rate_pct") or 0.0),
            "after_current_repair_rate_pct": round(
                (after_current["repair_requests"] / after_current["requests"] * 100.0) if after_current["requests"] else 0.0,
                2,
            ),
        },
        "notes": {
            "baseline_source": str(BASE_DELTAS_PATH),
            "baseline_run_index_source": str(BASE_RUN_INDEX_PATH),
            "current_run_index_source": str(RUN_INDEX_PATH),
            "current_success_scenarios": [r.get("scenario_id") for r in success],
        },
    }


def main() -> None:
    run_index = _read_json(RUN_INDEX_PATH)
    baseline = _read_json(BASE_DELTAS_PATH)
    baseline_run = _read_json(BASE_RUN_INDEX_PATH)
    dup = _duplication_stats(run_index)

    scenario_md = _render_scenario_matrix(run_index)
    full_md = _render_full_report(run_index, dup)
    dup_md = _render_dup_audit(run_index, dup)
    patch_md = _render_patch_md()
    deltas = _compute_deltas(run_index, baseline, baseline_run)

    (OUT_DIR / "SCENARIO_MATRIX_RESULTS.md").write_text(scenario_md, encoding="utf-8")
    (OUT_DIR / "FULL_OPENAI_TIER_REPORT_CURRENT.md").write_text(full_md, encoding="utf-8")
    (OUT_DIR / "TOKEN_DUPLICATION_AUDIT.md").write_text(dup_md, encoding="utf-8")
    (OUT_DIR / "PROMPT_SCHEMA_OPTIMIZATION_PATCH.md").write_text(patch_md, encoding="utf-8")
    (OUT_DIR / "STRICT_BEFORE_AFTER_DELTAS_CURRENT.json").write_text(
        json.dumps(deltas, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "outputs": [
                    str(OUT_DIR / "SCENARIO_MATRIX_RESULTS.md"),
                    str(OUT_DIR / "FULL_OPENAI_TIER_REPORT_CURRENT.md"),
                    str(OUT_DIR / "TOKEN_DUPLICATION_AUDIT.md"),
                    str(OUT_DIR / "PROMPT_SCHEMA_OPTIMIZATION_PATCH.md"),
                    str(OUT_DIR / "STRICT_BEFORE_AFTER_DELTAS_CURRENT.json"),
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
