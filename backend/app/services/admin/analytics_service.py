from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import os
import time

from sqlmodel import Session, select

from app.models import RequestEvent, UsageLedger, User, OCRJob


_OVERVIEW_CACHE: Dict[str, Any] = {
    "key": None,
    "expires_at": 0.0,
    "payload": None
}


def _parse_range_days(range_key: Optional[str], default_days: int = 7) -> int:
    if not range_key:
        return default_days
    value = range_key.strip().lower()
    if value.endswith("d"):
        value = value[:-1]
    try:
        days = int(value)
    except ValueError:
        return default_days
    return max(1, min(days, 90))


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return float(min(values))
    if pct >= 100:
        return float(max(values))
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


MODEL_PRICING_PER_MILLION = {
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-5-mini": {"input": 0.15, "output": 0.60}
}


def _normalize_model_key(model: Optional[str]) -> Optional[str]:
    if not model:
        return None
    return model.strip().lower()


def _load_pricing_table() -> Dict[str, Dict[str, float]]:
    table = dict(MODEL_PRICING_PER_MILLION)
    env_override = os.getenv("MODEL_PRICING_PER_MILLION")
    if not env_override:
        return table
    try:
        override = json.loads(env_override)
        if isinstance(override, dict):
            for key, value in override.items():
                if not isinstance(value, dict):
                    continue
                table[str(key).lower()] = {
                    "input": float(value.get("input", 0.0)),
                    "output": float(value.get("output", 0.0))
                }
    except Exception:
        return table
    return table


def _calc_cost(
    tokens_total: Optional[int],
    model: Optional[str] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None
) -> float:
    if tokens_total is None and tokens_in is None and tokens_out is None:
        return 0.0
    table = _load_pricing_table()
    model_key = _normalize_model_key(model)
    pricing = table.get(model_key)
    fallback_rate = float(os.getenv("OPENAI_COST_PER_1M_TOKENS", "0.50"))
    if not pricing:
        pricing = {"input": fallback_rate, "output": fallback_rate}
    in_tokens = tokens_in if tokens_in is not None else 0
    out_tokens = tokens_out if tokens_out is not None else 0
    total_tokens = tokens_total if tokens_total is not None else in_tokens + out_tokens
    if in_tokens == 0 and out_tokens == 0:
        average_rate = (pricing["input"] + pricing["output"]) / 2
        return (total_tokens / 1_000_000) * average_rate
    return ((in_tokens / 1_000_000) * pricing["input"]) + ((out_tokens / 1_000_000) * pricing["output"])


def _classify_question_mode(event: RequestEvent) -> str:
    if (event.learning_mode or "").lower() == "study":
        return "study"
    if (event.mode or "").lower() == "minimal":
        return "quick"
    return "solve"


def _error_category(error_type: Optional[str]) -> str:
    if not error_type:
        return "internal"
    value = error_type.lower()
    if "ocr" in value:
        return "ocr"
    if "schema" in value or "validation" in value:
        return "schema"
    if "stream" in value or "sse" in value or "disconnect" in value:
        return "streaming"
    if "llm" in value or "openai" in value:
        return "llm"
    return "internal"


def _apply_event_filters(stmt, filters: Dict[str, Optional[str]]):
    mode = filters.get("mode")
    model = filters.get("model")
    provider = filters.get("provider")
    route = filters.get("route")

    if mode:
        stmt = stmt.where(RequestEvent.mode == mode)
    if model:
        stmt = stmt.where(RequestEvent.model == model)
    if provider:
        stmt = stmt.where(RequestEvent.provider == provider)
    if route:
        stmt = stmt.where(RequestEvent.route == route)
    return stmt


def record_request_event(session: Session, payload: Dict[str, Any]) -> RequestEvent:
    event = RequestEvent(**payload)
    session.add(event)
    session.commit()
    return event


def _collect_events(
    session: Session,
    start_at: datetime,
    end_at: datetime,
    filters: Dict[str, Optional[str]]
) -> List[RequestEvent]:
    stmt = select(RequestEvent).where(
        RequestEvent.created_at >= start_at,
        RequestEvent.created_at <= end_at
    )
    stmt = _apply_event_filters(stmt, filters)
    return list(session.exec(stmt).all())


def _delta_pct(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100.0, 2)


def get_overview(session: Session, range_key: Optional[str], filters: Dict[str, Optional[str]]) -> Dict[str, Any]:
    range_days = _parse_range_days(range_key)
    cache_key = f"{range_days}:{json.dumps(filters, sort_keys=True)}"
    now_ts = time.time()
    if _OVERVIEW_CACHE["key"] == cache_key and _OVERVIEW_CACHE["expires_at"] > now_ts:
        return _OVERVIEW_CACHE["payload"]

    now = datetime.utcnow()
    range_start = now - timedelta(days=range_days)
    prev_start = range_start - timedelta(days=range_days)
    prev_end = range_start

    events_current = _collect_events(session, range_start, now, filters)
    events_prev = _collect_events(session, prev_start, prev_end, filters)

    today_start = now - timedelta(days=1)
    events_today = [e for e in events_current if e.created_at >= today_start]
    events_prev_day = [e for e in events_prev if e.created_at >= (prev_start + timedelta(days=range_days - 1))]

    total_students = session.exec(select(User.id)).all()
    total_students_count = len(total_students)
    total_students_prev = session.exec(select(User.id).where(User.created_at < range_start)).all()

    active_students_today = len({e.user_id for e in events_today if e.user_id})
    active_students_prev = len({e.user_id for e in events_prev_day if e.user_id})

    online_now = len(
        session.exec(
            select(User.id).where(User.last_active_at >= now - timedelta(minutes=5))
        ).all()
    )
    online_prev = len(
        session.exec(
            select(User.id).where(
                User.last_active_at >= prev_end - timedelta(minutes=5),
                User.last_active_at < prev_end
            )
        ).all()
    )

    new_users_today = len(
        session.exec(select(User.id).where(User.created_at >= today_start)).all()
    )
    new_users_prev = len(
        session.exec(
            select(User.id).where(
                User.created_at >= prev_end - timedelta(days=1),
                User.created_at < prev_end
            )
        ).all()
    )

    questions_today = len(events_today)
    questions_prev = len(events_prev_day)
    avg_questions_today = round(questions_today / active_students_today, 2) if active_students_today else 0.0
    avg_questions_prev = round(questions_prev / active_students_prev, 2) if active_students_prev else 0.0

    tokens_in_today = sum([e.tokens_in or 0 for e in events_today])
    tokens_out_today = sum([e.tokens_out or 0 for e in events_today])
    tokens_in_prev = sum([e.tokens_in or 0 for e in events_prev_day])
    tokens_out_prev = sum([e.tokens_out or 0 for e in events_prev_day])

    cost_today = sum([
        e.cost_usd if e.cost_usd is not None else _calc_cost(e.tokens_total, e.model, e.tokens_in, e.tokens_out)
        for e in events_today
    ])
    cost_prev = sum([
        e.cost_usd if e.cost_usd is not None else _calc_cost(e.tokens_total, e.model, e.tokens_in, e.tokens_out)
        for e in events_prev_day
    ])
    cost_per_question = round(cost_today / questions_today, 4) if questions_today else 0.0
    cost_per_question_prev = round(cost_prev / questions_prev, 4) if questions_prev else 0.0

    credit_deductions_today = len(
        session.exec(
            select(UsageLedger.id).where(
                UsageLedger.transaction_type == "DEBIT",
                UsageLedger.created_at >= today_start
            )
        ).all()
    )
    credit_deductions_prev = len(
        session.exec(
            select(UsageLedger.id).where(
                UsageLedger.transaction_type == "DEBIT",
                UsageLedger.created_at >= prev_end - timedelta(days=1),
                UsageLedger.created_at < prev_end
            )
        ).all()
    )

    deduction_failures_today = len([
        e for e in events_today
        if not e.is_cached and e.status == "ok" and e.credit_deducted is False
    ])
    deduction_failures_prev = len([
        e for e in events_prev_day
        if not e.is_cached and e.status == "ok" and e.credit_deducted is False
    ])

    questions_series = defaultdict(lambda: {"quick": 0, "study": 0, "solve": 0, "total": 0})
    cost_series = defaultdict(lambda: {"total": 0.0})
    latency_series: Dict[str, List[int]] = defaultdict(list)
    error_series = defaultdict(lambda: {"total": 0, "ocr": 0, "llm": 0, "schema": 0, "streaming": 0, "internal": 0})

    for event in events_current:
        day_key = event.created_at.date().isoformat()
        mode_key = _classify_question_mode(event)
        questions_series[day_key][mode_key] += 1
        questions_series[day_key]["total"] += 1

        cost_series[day_key]["total"] += (
            event.cost_usd if event.cost_usd is not None
            else _calc_cost(event.tokens_total, event.model, event.tokens_in, event.tokens_out)
        )
        if event.latency_ms is not None:
            latency_series[day_key].append(event.latency_ms)

        error_series[day_key]["total"] += 1
        if event.status == "error":
            category = _error_category(event.error_type)
            error_series[day_key][category] += 1

    subjects = defaultdict(int)
    grades = defaultdict(int)
    models = defaultdict(int)
    verified_count = 0
    schema_fail_count = 0
    schema_seen = 0
    stream_total = 0
    stream_errors = 0
    stream_truncated = 0
    provider_stats = defaultdict(lambda: {"total": 0, "errors": 0, "timeouts": 0, "rate_limits": 0})

    for event in events_current:
        if event.subject:
            subjects[event.subject] += 1
        if event.grade_level:
            grades[event.grade_level] += 1
        model_key = event.model or event.route or "unknown"
        models[model_key] += 1

        if event.verification_pass:
            verified_count += 1
        if event.schema_valid is not None:
            schema_seen += 1
            if event.schema_valid is False:
                schema_fail_count += 1

        if event.is_stream:
            stream_total += 1
            if event.status == "error":
                stream_errors += 1
            if event.response_truncated:
                stream_truncated += 1

        provider_key = event.provider or "unknown"
        provider_stats[provider_key]["total"] += 1
        if event.status == "error":
            provider_stats[provider_key]["errors"] += 1
        if event.error_type and "timeout" in event.error_type.lower():
            provider_stats[provider_key]["timeouts"] += 1
        if event.error_type and "rate" in event.error_type.lower():
            provider_stats[provider_key]["rate_limits"] += 1

    questions_trend = []
    cost_trend = []
    latency_trend = []
    error_trend = []

    for i in range(range_days):
        day = (range_start.date() + timedelta(days=i)).isoformat()
        q = questions_series.get(day, {"quick": 0, "study": 0, "solve": 0, "total": 0})
        questions_trend.append({"date": day, **q})

        c = cost_series.get(day, {"total": 0.0})
        cost_trend.append({"date": day, "total": round(c["total"], 6)})

        lat_list = latency_series.get(day, [])
        latency_trend.append({
            "date": day,
            "p50": round(_percentile(lat_list, 50), 2),
            "p95": round(_percentile(lat_list, 95), 2),
            "p99": round(_percentile(lat_list, 99), 2)
        })

        err = error_series.get(day, {"total": 0, "ocr": 0, "llm": 0, "schema": 0, "streaming": 0, "internal": 0})
        total = err["total"] or 1
        error_trend.append({
            "date": day,
            "ocr": round((err["ocr"] / total) * 100, 2),
            "llm": round((err["llm"] / total) * 100, 2),
            "schema": round((err["schema"] / total) * 100, 2),
            "streaming": round((err["streaming"] / total) * 100, 2),
            "internal": round((err["internal"] / total) * 100, 2)
        })

    subject_breakdown = [
        {"subject": key, "count": value}
        for key, value in sorted(subjects.items(), key=lambda kv: kv[1], reverse=True)[:10]
    ]
    grade_breakdown = [
        {"grade": key, "count": value}
        for key, value in sorted(grades.items(), key=lambda kv: kv[1], reverse=True)
    ]
    model_routing = []
    total_models = sum(models.values()) or 1
    for key, value in sorted(models.items(), key=lambda kv: kv[1], reverse=True):
        model_routing.append({
            "model": key,
            "count": value,
            "share": round((value / total_models) * 100, 2)
        })

    verified_rate = round((verified_count / len(events_current)) * 100, 2) if events_current else 0.0
    schema_violation_rate = round((schema_fail_count / schema_seen) * 100, 2) if schema_seen else 0.0

    provider_status = []
    for key, stats in provider_stats.items():
        total = stats["total"] or 1
        provider_status.append({
            "provider": key,
            "error_rate": round((stats["errors"] / total) * 100, 2),
            "timeouts": stats["timeouts"],
            "rate_limits": stats["rate_limits"]
        })

    streaming_disconnect_rate = round((stream_errors / stream_total) * 100, 2) if stream_total else 0.0
    streaming_truncated_rate = round((stream_truncated / stream_total) * 100, 2) if stream_total else 0.0

    payload = {
        "generated_at": now.isoformat(),
        "range_days": range_days,
        "kpis": {
            "total_students": {
                "value": total_students_count,
                "delta_pct": _delta_pct(total_students_count, len(total_students_prev))
            },
            "active_students_today": {
                "value": active_students_today,
                "delta_pct": _delta_pct(active_students_today, active_students_prev)
            },
            "online_now": {
                "value": online_now,
                "delta_pct": _delta_pct(online_now, online_prev)
            },
            "new_users_today": {
                "value": new_users_today,
                "delta_pct": _delta_pct(new_users_today, new_users_prev)
            },
            "questions_today": {
                "value": questions_today,
                "delta_pct": _delta_pct(questions_today, questions_prev)
            },
            "avg_questions_per_active": {
                "value": avg_questions_today,
                "delta_pct": _delta_pct(avg_questions_today, avg_questions_prev)
            },
            "tokens_in_today": {
                "value": tokens_in_today,
                "delta_pct": _delta_pct(tokens_in_today, tokens_in_prev)
            },
            "tokens_out_today": {
                "value": tokens_out_today,
                "delta_pct": _delta_pct(tokens_out_today, tokens_out_prev)
            },
            "llm_cost_today": {
                "value": round(cost_today, 6),
                "delta_pct": _delta_pct(cost_today, cost_prev)
            },
            "cost_per_question": {
                "value": cost_per_question,
                "delta_pct": _delta_pct(cost_per_question, cost_per_question_prev)
            },
            "credit_deductions_today": {
                "value": credit_deductions_today,
                "delta_pct": _delta_pct(credit_deductions_today, credit_deductions_prev)
            },
            "deduction_failures_today": {
                "value": deduction_failures_today,
                "delta_pct": _delta_pct(deduction_failures_today, deduction_failures_prev)
            }
        },
        "trends": {
            "questions": questions_trend,
            "cost": cost_trend,
            "latency": latency_trend,
            "error_rate": error_trend
        },
        "breakdowns": {
            "subjects": subject_breakdown,
            "grades": grade_breakdown,
            "model_routing": model_routing
        },
        "quality": {
            "verified_rate": verified_rate,
            "schema_violation_rate": schema_violation_rate,
            "user_feedback_rate": None,
            "flagged_reports": None
        },
        "health": {
            "providers": provider_status,
            "streaming": {
                "disconnect_rate": streaming_disconnect_rate,
                "truncated_rate": streaming_truncated_rate,
                "truncated_count": stream_truncated
            },
            "queue_backlog_depth": None
        }
    }

    _OVERVIEW_CACHE["key"] = cache_key
    _OVERVIEW_CACHE["expires_at"] = now_ts + 60.0
    _OVERVIEW_CACHE["payload"] = payload
    return payload


def get_errors(session: Session, range_key: Optional[str], severity: Optional[str], filters: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    range_days = _parse_range_days(range_key, default_days=1)
    now = datetime.utcnow()
    start_at = now - timedelta(days=range_days)

    stmt = select(RequestEvent).where(
        RequestEvent.created_at >= start_at,
        RequestEvent.status == "error"
    )
    stmt = _apply_event_filters(stmt, filters)
    events = session.exec(stmt).all()

    severity_map = {
        "low": {"validation", "schema"},
        "medium": {"llm", "streaming"},
        "high": {"internal", "ocr"}
    }
    filtered = []
    for event in events:
        category = _error_category(event.error_type)
        if severity:
            if category not in severity_map.get(severity.lower(), set()):
                continue
        filtered.append({
            "request_id": event.request_id,
            "service": event.provider or "unknown",
            "endpoint": event.route,
            "error_type": event.error_type or category,
            "severity": severity or category,
            "timestamp": event.created_at.isoformat(),
            "user_id": event.user_id
        })
    return filtered[:50]


def get_anomalies(session: Session, range_key: Optional[str], filters: Dict[str, Optional[str]]) -> Dict[str, Any]:
    range_days = _parse_range_days(range_key, default_days=1)
    now = datetime.utcnow()
    start_at = now - timedelta(days=range_days)

    stmt = select(RequestEvent).where(RequestEvent.created_at >= start_at)
    stmt = _apply_event_filters(stmt, filters)
    events = list(session.exec(stmt).all())

    cost_by_user = defaultdict(float)
    for event in events:
        if event.user_id is None:
            continue
        cost = (
            event.cost_usd if event.cost_usd is not None
            else _calc_cost(event.tokens_total, event.model, event.tokens_in, event.tokens_out)
        )
        cost_by_user[event.user_id] += cost

    top_users = [
        {"user_id": user_id, "cost_usd": round(cost, 6)}
        for user_id, cost in sorted(cost_by_user.items(), key=lambda kv: kv[1], reverse=True)[:10]
    ]

    token_spikes = sorted(
        [
            {
                "request_id": e.request_id,
                "endpoint": e.route,
                "model": e.model,
                "tokens_total": e.tokens_total or 0,
                "user_id": e.user_id
            }
            for e in events
        ],
        key=lambda item: item["tokens_total"],
        reverse=True
    )[:10]

    ocr_failures = session.exec(
        select(OCRJob.error_code, OCRJob.error_message)
        .where(OCRJob.created_at >= start_at, OCRJob.status == "failed")
    ).all()
    ocr_counts = defaultdict(int)
    for error_code, error_message in ocr_failures:
        key = error_code or (error_message[:80] if error_message else "unknown")
        ocr_counts[key] += 1
    top_ocr = [
        {"reason": reason, "count": count}
        for reason, count in sorted(ocr_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    ]

    return {
        "top_cost_users": top_users,
        "token_spike_requests": token_spikes,
        "ocr_failures": top_ocr
    }
