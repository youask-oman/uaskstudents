# -*- coding: utf-8 -*-
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.database import engine
from app.models import User, Subscription, ChatSession, ChatMessage, UsageLedgerV2, UsageLedger, BillingLedger
from app.services.llm.clients import OpenAIClient

QUESTION = """Problem: Real Analysis + Uniform Convergence + Differentiation Under the Limit

Define a sequence of functions on [0,1] by
f_n(x) = (x^n)/(1 + x^n).

Find the pointwise limit f(x) = lim_{n->infinity} f_n(x) on [0,1].
Determine whether f_n converges uniformly to f on [0,1] and justify rigorously.
Determine whether f_n converges uniformly to f on [0,a] for any a with 0 <= a < 1.
Compute f_n'(x) explicitly.
Determine whether f_n' converges pointwise on [0,1) and identify its pointwise limit there.
Check whether the limit function f is differentiable on [0,1] and where it fails to be differentiable.
Decide whether lim_{n->infinity} f_n'(x) = f'(x) holds on (0,1) and justify.
Compute integral_0^1 f_n(x) dx and determine its limit as n->infinity.
Compare lim_{n->infinity} integral_0^1 f_n with integral_0^1 lim_{n->infinity} f_n and explain any discrepancy.
Provide a correct theorem (DCT, uniform convergence, etc.) that applies or fails and why.
Estimate sup_{x in [0,1]} |f_n(x) - f(x)| and use it to support your uniform convergence claim.
Give a bound for |f_n(x) - f(x)| on [0,a] with a<1.
Discuss the behavior near x=1 and why it breaks or does not break uniform convergence.
State the final conclusions clearly in a summary table (pointwise, uniform, derivative, integral interchange).
Provide at least one short counterexample-style argument for any claim of non-uniform convergence."""


def d(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v)
    return str(v)

with Session(engine) as s:
    user = s.exec(select(User).where(User.email == "admin@uask.ai")).first()
    if not user:
        raise RuntimeError("admin@uask.ai not found")
    sub = s.exec(select(Subscription).where(Subscription.user_id == user.id)).first()

    before = {
        "user_id": user.id,
        "email": user.email,
        "user_credits_balance": d(user.credits_balance),
        "subscription_id": sub.id if sub else None,
        "subscription_credits_balance": d(sub.credits_balance) if sub else None,
        "chat_sessions_count": s.query(ChatSession).filter(ChatSession.user_id == user.id).count(),
        "chat_messages_count": s.query(ChatMessage).join(ChatSession, ChatMessage.session_id == ChatSession.id).filter(ChatSession.user_id == user.id).count(),
        "usage_ledger_v2_count": s.query(UsageLedgerV2).filter(UsageLedgerV2.user_id == user.id).count(),
        "usage_ledger_legacy_count": s.query(UsageLedger).filter(UsageLedger.subscription_id == (sub.id if sub else -1)).count() if sub else 0,
        "billing_ledger_count": s.query(BillingLedger).filter(BillingLedger.user_id == user.id).count(),
    }

captured = {"openai_calls": []}
orig_generate = OpenAIClient.generate

async def wrapped_generate(self, **kwargs):
    rec = {
        "request_id": kwargs.get("request_id"),
        "model": kwargs.get("model"),
        "max_tokens": kwargs.get("max_tokens"),
        "timeout_ms": kwargs.get("timeout_ms"),
        "reasoning_effort": kwargs.get("reasoning_effort"),
    }
    resp = await orig_generate(self, **kwargs)
    rec["provider"] = resp.provider
    rec["status"] = resp.status
    rec["usage"] = resp.usage
    rec["latency_ms"] = resp.latency_ms
    captured["openai_calls"].append(rec)
    return resp

OpenAIClient.generate = wrapped_generate

report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "scenario": "real_e2e_admin_final_real_analysis",
    "input": {
        "user_email": "admin@uask.ai",
        "tier": "FINAL",
        "question": QUESTION,
    },
    "before": before,
}

client = TestClient(app)
body = {
    "confirmed_text": QUESTION,
    "requested_mode": "minimal",
    "tier": "FINAL",
    "graph_mode": "off",
    "trusted_context": {"learning_mode": "solve"},
    "features_used": {"ocr_used": False, "voice_used": False, "plot_requested": False},
}

sse = ""
try:
    with client.stream("POST", f"/api/v1/solve_v3_stream?user_id={before['user_id']}", json=body) as r:
        report["http_status"] = r.status_code
        report["content_type"] = r.headers.get("content-type")
        for t in r.iter_text():
            sse += t
finally:
    OpenAIClient.generate = orig_generate

report["raw_sse"] = sse
report["openai"] = captured

meta = None
done = None
telemetry = None
for block in sse.split("\n\n"):
    if block.startswith("event: meta"):
        for ln in block.splitlines():
            if ln.startswith("data:"):
                try:
                    meta = json.loads(ln.split(":",1)[1].strip())
                except Exception:
                    pass
    if block.startswith("event: telemetry"):
        for ln in block.splitlines():
            if ln.startswith("data:"):
                try:
                    telemetry = json.loads(ln.split(":",1)[1].strip())
                except Exception:
                    pass
    if block.startswith("event: done"):
        for ln in block.splitlines():
            if ln.startswith("data:"):
                try:
                    done = json.loads(ln.split(":",1)[1].strip())
                except Exception:
                    done = ln

report["meta_event"] = meta
report["telemetry_event"] = telemetry
report["done_event"] = done
request_id = meta.get("request_id") if isinstance(meta, dict) else None
report["request_id"] = request_id

with Session(engine) as s:
    user = s.exec(select(User).where(User.email == "admin@uask.ai")).first()
    sub = s.exec(select(Subscription).where(Subscription.user_id == user.id)).first()

    sessions_after = s.query(ChatSession).filter(ChatSession.user_id == user.id).count()
    messages_after = s.query(ChatMessage).join(ChatSession, ChatMessage.session_id == ChatSession.id).filter(ChatSession.user_id == user.id).count()

    ul2_q = s.query(UsageLedgerV2).filter(UsageLedgerV2.user_id == user.id)
    ul2_req = ul2_q.filter(UsageLedgerV2.request_id == request_id).all() if request_id else []

    bl_q = s.query(BillingLedger).filter(BillingLedger.user_id == user.id)
    bl_req = bl_q.filter(BillingLedger.request_id == request_id).all() if request_id else []

    ul_legacy_q = s.query(UsageLedger).filter(UsageLedger.subscription_id == (sub.id if sub else -1)) if sub else None
    ul_legacy_req = ul_legacy_q.filter(UsageLedger.reference_id == request_id).all() if (request_id and ul_legacy_q is not None) else []

    after = {
        "user_credits_balance": d(user.credits_balance),
        "subscription_credits_balance": d(sub.credits_balance) if sub else None,
        "chat_sessions_count": sessions_after,
        "chat_messages_count": messages_after,
        "usage_ledger_v2_count": ul2_q.count(),
        "usage_ledger_legacy_count": ul_legacy_q.count() if ul_legacy_q is not None else 0,
        "billing_ledger_count": bl_q.count(),
        "usage_ledger_v2_for_request": [
            {
                "ledger_id": x.ledger_id,
                "request_id": x.request_id,
                "attempt_id": x.attempt_id,
                "total_cost": d(x.total_cost),
                "outcome": x.outcome,
                "question_id": x.question_id,
                "question_index": x.question_index,
            }
            for x in ul2_req
        ],
        "usage_ledger_legacy_for_request": [
            {
                "id": x.id,
                "reference_id": x.reference_id,
                "transaction_type": x.transaction_type,
                "amount": d(x.amount),
                "balance_after": d(x.balance_after),
            }
            for x in ul_legacy_req
        ],
        "billing_ledger_for_request": [
            {
                "id": x.id,
                "request_id": x.request_id,
                "action_type": x.action_type,
                "status": x.status,
                "credits_charged": d(x.credits_charged),
                "credits_before": d(x.credits_before),
                "credits_after": d(x.credits_after),
                "delta_credits": d(x.delta_credits),
            }
            for x in bl_req
        ],
    }

report["after"] = after

try:
    b_sub = Decimal(before["subscription_credits_balance"] or "0") if before.get("subscription_credits_balance") is not None else None
    a_sub = Decimal(after["subscription_credits_balance"] or "0") if after.get("subscription_credits_balance") is not None else None
    report["credit_delta_subscription"] = str(a_sub - b_sub) if (a_sub is not None and b_sub is not None) else None
except Exception:
    report["credit_delta_subscription"] = None

try:
    b_user = Decimal(before["user_credits_balance"] or "0") if before.get("user_credits_balance") is not None else None
    a_user = Decimal(after["user_credits_balance"] or "0") if after.get("user_credits_balance") is not None else None
    report["credit_delta_user"] = str(a_user - b_user) if (a_user is not None and b_user is not None) else None
except Exception:
    report["credit_delta_user"] = None

out = "backend/tmp_real_e2e_admin_final_real_analysis_report.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(out)
print("done:", report.get("done_event"))
print("openai_calls:", len(report.get("openai", {}).get("openai_calls", [])))
print("credit_delta_subscription:", report.get("credit_delta_subscription"))
print("credit_delta_user:", report.get("credit_delta_user"))
