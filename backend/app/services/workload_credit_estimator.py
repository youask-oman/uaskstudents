from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


MIN_TOTAL_CREDITS = 1
MAX_TOTAL_CREDITS_DEFAULT = 40
BUNDLE_FACTOR_DEFAULT = 0.85
CONTEXT_CREDITS_DEFAULT = 1


DERIVATIVE_RE = re.compile(r"(f'\(x\)|derivative|critical point|optimi[sz]e|maximi[sz]e|minimi[sz]e)", re.IGNORECASE)
SECOND_DERIV_RE = re.compile(r"(f''\(x\)|concavity|inflection)", re.IGNORECASE)
GRAPH_RE = re.compile(r"(plot|graph|shade|legend|grid|title|label|dashed|annotate|mark)", re.IGNORECASE)
INTERVAL_RE = re.compile(r"(sign|interval|asymptote|classif)", re.IGNORECASE)
VERIFY_RE = re.compile(r"(verify|check|justify|prove)", re.IGNORECASE)


@dataclass
class TaskCreditEstimate:
    task_id: str
    credits: float
    reasons: List[str]


def _normalize_task_text(task_text: str) -> str:
    return str(task_text or "").strip()


def _task_credits(task_text: str) -> Tuple[float, List[str]]:
    text = _normalize_task_text(task_text)
    credits = 1.0
    reasons: List[str] = ["base_task=1"]
    if DERIVATIVE_RE.search(text):
        credits += 1.0
        reasons.append("derivative_or_critical=+1")
    if SECOND_DERIV_RE.search(text):
        credits += 1.0
        reasons.append("second_derivative_or_concavity=+1")
    if GRAPH_RE.search(text):
        credits += 2.0
        reasons.append("graphing=+2")
    if INTERVAL_RE.search(text):
        credits += 1.0
        reasons.append("interval_or_asymptote=+1")
    if VERIFY_RE.search(text):
        credits += 1.0
        reasons.append("verify_or_justify=+1")
    return credits, reasons


def estimate_task_bundle_credits(
    *,
    context_text: str,
    tasks: List[Dict[str, Any]],
    selected_task_ids: List[str],
    bundle_factor: float = BUNDLE_FACTOR_DEFAULT,
    context_credits: float = CONTEXT_CREDITS_DEFAULT,
    min_total: int = MIN_TOTAL_CREDITS,
    max_total: int = MAX_TOTAL_CREDITS_DEFAULT,
) -> Dict[str, Any]:
    selected = set(str(tid) for tid in (selected_task_ids or []))
    if not tasks:
        tasks = [{
            "task_id": "t1",
            "task_text": str(context_text or ""),
            "order_index": 1,
        }]
        selected = {"t1"}

    estimates: List[TaskCreditEstimate] = []
    per_task: Dict[str, float] = {}
    reasons: Dict[str, List[str]] = {}
    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        if not task_id or task_id not in selected:
            continue
        credit_value, reason_list = _task_credits(str(task.get("task_text") or ""))
        estimates.append(TaskCreditEstimate(task_id=task_id, credits=credit_value, reasons=reason_list))
        per_task[task_id] = credit_value
        reasons[task_id] = reason_list

    if not estimates:
        # enforce at least one selected billable unit
        per_task = {"t1": 1.0}
        reasons = {"t1": ["base_task=1", "implicit_selection_fallback"]}
        selected = {"t1"}
        task_sum = 1.0
    else:
        task_sum = sum(e.credits for e in estimates)

    scaled = math.ceil(task_sum * float(bundle_factor))
    total = float(context_credits) + float(scaled)
    total = float(max(min_total, min(max_total, int(total))))

    hash_src = str(context_text or "") + "|" + "|".join(sorted(selected))
    original_input_hash = hashlib.sha256(hash_src.encode("utf-8")).hexdigest()

    return {
        "billing_version": "work_units_v1",
        "context_credits": float(context_credits),
        "per_task_credits": per_task,
        "bundle_factor": float(bundle_factor),
        "estimated_total_credits": total,
        "charged_total_credits": total,
        "selected_task_ids": sorted(selected),
        "breakdown_reasons": reasons,
        "original_input_hash": original_input_hash,
    }

