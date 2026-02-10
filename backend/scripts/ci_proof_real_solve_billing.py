"""
CI proof runner: real OpenAI solves + billing/ledger/holds proofs (backend-only).

Usage:
  python scripts/ci_proof_real_solve_billing.py --run-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("BILLING_V2_ENABLED", "true")
os.environ.setdefault("BILLING_V2_ROLLOUT_PERCENT", "100")
os.environ.setdefault("CREDIT_PROGRAMS_ENABLED", "true")

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
from app.database import engine
from app.auth import create_access_token, get_password_hash
from app.models import (
    User,
    BillingLedger,
    CreditHold,
    CreditLot,
    CreditLotConsumption,
    Payment,
    AdminAuditLog,
    SolverOutputAttempt,
    Plan,
    UsageLedger,
)
from app.jobs.nightly_reconciliation import compute_user_balance
from app.services.subscription_service import subscription_service


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _json_default(obj: Any):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if hasattr(row, "model_dump"):
        data = row.model_dump()
    elif hasattr(row, "dict"):
        data = row.dict()
    else:
        data = {k: getattr(row, k) for k in getattr(row, "__fields__", {})}
    return data


def _ensure_env() -> None:
    missing = []
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("STRIPE_SECRET_KEY"):
        missing.append("STRIPE_SECRET_KEY")
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    if os.getenv("STRIPE_LIVE_MODE", "false").lower() == "true":
        raise RuntimeError("STRIPE_LIVE_MODE must be false for this proof run")
    os.environ.setdefault("BILLING_V2_ENABLED", "true")
    os.environ.setdefault("BILLING_V2_ROLLOUT_PERCENT", "100")
    os.environ.setdefault("CREDIT_PROGRAMS_ENABLED", "true")
    from app.services.billing_feature_flags import get_feature_flags
    get_feature_flags().reload_from_env()


def _ensure_tables() -> None:
    SQLModel.metadata.create_all(engine)


def _pick_or_create_user(
    session: Session,
    email_prefix: str,
    full_name: str,
    role: str = "student",
    force_new: bool = False,
) -> User:
    if not force_new:
        user = session.exec(
            select(User)
            .where(User.email.like(f"{email_prefix}%@proof.local"))
            .where(User.is_internal == False)
        ).first()
        if user:
            return user
    email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@proof.local"
    user = User(
        email=email,
        full_name=full_name,
        password_hash=get_password_hash("ci_proof_password"),
        role=role,
        is_internal=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _admin_token(admin: User) -> str:
    return create_access_token({"sub": admin.email})


def _call_sse(client: TestClient, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    res = client.post(url, json=payload)
    if res.status_code != 200:
        raise RuntimeError(f"Solve call failed: {res.status_code} {res.text}")
    events = res.text.split("\n\n")
    meta = None
    telemetry = None
    done = None
    for e in events:
        if e.startswith("event: meta"):
            meta = json.loads(e.split("data: ", 1)[1])
        if e.startswith("event: telemetry"):
            telemetry = json.loads(e.split("data: ", 1)[1])
        if e.startswith("event: done"):
            done = json.loads(e.split("data: ", 1)[1])
    return {"meta": meta, "telemetry": telemetry, "done": done, "raw": events}


def run_ci_proof(run_id: str) -> Dict[str, Any]:
    _ensure_env()
    _ensure_tables()
    from app.main import app

    start_at = datetime.utcnow()
    reports_root = Path(os.getenv("PROOF_REPORTS_DIR", "/src/reports"))
    if not reports_root.exists():
        reports_root = Path("reports")
    out_dir = reports_root / "proof" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = TestClient(app)

    with Session(engine) as session:
        student_a = _pick_or_create_user(session, "ci_student_a", "CI Student A", force_new=True)
        student_b = _pick_or_create_user(session, "ci_student_b", "CI Student B", force_new=True)
        grant_user = _pick_or_create_user(session, "ci_grant_user", "CI Grant User", force_new=True)
        refund_user = _pick_or_create_user(session, "ci_refund_user", "CI Refund User", force_new=True)
        admin_user = _pick_or_create_user(session, "ci_admin", "CI Admin", role="superadmin", force_new=True)

        admin_token = _admin_token(admin_user)

        def ensure_plan(user: User, plan_slug: str) -> None:
            sub = subscription_service.get_or_create_subscription(session, user)
            plan = session.exec(select(Plan).where(Plan.slug == plan_slug)).first()
            if not plan:
                subscription_service.ensure_plans_exist(session)
                plan = session.exec(select(Plan).where(Plan.slug == plan_slug)).first()
            if plan and sub.plan_id != plan.id:
                sub.plan_id = plan.id
                session.add(sub)
                session.commit()
                session.refresh(sub)

        ensure_plan(student_a, "student_standard")
        ensure_plan(student_b, "student_standard")

        def grant_credits(user: User, credits: float, reason: str) -> None:
            res = client.post(
                f"/api/admin/billing/users/{user.id}/grant",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "credits": credits,
                    "reason": reason,
                    "expires_days": 60,
                    "lot_type": "ADJUSTMENT",
                    "idempotency_key": f"{reason}:{user.id}",
                },
            )
            if res.status_code != 200:
                raise RuntimeError(f"Grant failed: {res.status_code} {res.text}")

        required_a = 25
        required_b = 50
        bal_a = float(compute_user_balance(session, student_a.id))
        bal_b = float(compute_user_balance(session, student_b.id))

        if bal_a < required_a:
            grant_credits(student_a, required_a - bal_a + 5, f"CI_PROOF_TOPUP:{run_id}")
        if bal_b < required_b:
            grant_credits(student_b, required_b - bal_b + 5, f"CI_PROOF_TOPUP:{run_id}")

        wallet_before = {
            "student_a": float(compute_user_balance(session, student_a.id)),
            "student_b": float(compute_user_balance(session, student_b.id)),
            "grant_user": float(compute_user_balance(session, grant_user.id)),
            "refund_user": float(compute_user_balance(session, refund_user.id)),
        }

        solves = [
            {
                "label": "three_step",
                "user": student_a,
                "text": "Solve for x: 2x + 7 = 19",
                "tier": "three_step",
                "expected": 5,
            },
            {
                "label": "short",
                "user": student_b,
                "text": "Solve for x: sqrt(x + 5) = x - 1",
                "tier": "short",
                "expected": 7,
            },
            {
                "label": "standard",
                "user": student_b,
                "text": "Solve the system: 2x + y = 7, x - 2y = -1",
                "tier": "standard",
                "expected": 10,
            },
        ]

        solve_results = []
        for item in solves:
            req_id = f"ci-proof-{run_id}-{item['label']}"
            payload = {
                "confirmed_text": item["text"],
                "tier": item["tier"],
                "requested_mode": "minimal" if item["tier"] in {"three_step", "short"} else "detailed",
                "input_modality": "text",
                "graph_mode": "off",
                "features_used": {"ocr_used": False, "voice_used": False, "plot_requested": False},
                "idempotency_key": req_id,
            }
            events = _call_sse(client, f"/api/v1/solve_v3_stream?user_id={item['user'].id}", payload)
            meta = events["meta"] or {}
            telemetry = events["telemetry"] or {}
            done = events["done"] or {}
            if not done.get("ok"):
                raise RuntimeError(f"Solve failed: {done}")
            attempt_id = meta.get("attempt_id")
            solve_results.append(
                {
                    "label": item["label"],
                    "user_id": item["user"].id,
                    "request_id": req_id,
                    "attempt_id": attempt_id,
                    "telemetry": telemetry,
                    "expected_credits": item["expected"],
                }
            )

        res_grant = client.post(
            f"/api/admin/billing/users/{grant_user.id}/grant",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "credits": 100,
                "reason": f"CI_PROOF_GRANT:{run_id}",
                "expires_days": 60,
                "lot_type": "ADJUSTMENT",
                "idempotency_key": f"CI_PROOF_GRANT:{run_id}:{grant_user.id}",
            },
        )
        if res_grant.status_code != 200:
            raise RuntimeError(f"Grant failed: {res_grant.status_code} {res_grant.text}")

        res_refund = client.post(
            f"/api/admin/billing/users/{refund_user.id}/refund",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "credits": 50,
                "reason": f"CI_PROOF_REFUND:{run_id}",
                "reason_code": "MANUAL_REFUND",
                "idempotency_key": f"CI_PROOF_REFUND:{run_id}:{refund_user.id}",
            },
        )
        if res_refund.status_code != 200:
            raise RuntimeError(f"Refund failed: {res_refund.status_code} {res_refund.text}")

        wallet_after = {
            "student_a": float(compute_user_balance(session, student_a.id)),
            "student_b": float(compute_user_balance(session, student_b.id)),
            "grant_user": float(compute_user_balance(session, grant_user.id)),
            "refund_user": float(compute_user_balance(session, refund_user.id)),
        }

        admin_checks = {}
        for label, user in {
            "student_a": student_a,
            "student_b": student_b,
            "grant_user": grant_user,
            "refund_user": refund_user,
        }.items():
            res_wallet = client.get(
                f"/api/admin/billing/users/{user.id}/wallet",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            admin_checks[f"wallet_{label}"] = res_wallet.json() if res_wallet.status_code == 200 else {
                "status": res_wallet.status_code,
                "body": res_wallet.text,
            }
        res_ledger = client.get(
            "/api/admin/billing/ledger?limit=50",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        admin_checks["ledger"] = res_ledger.json() if res_ledger.status_code == 200 else {
            "status": res_ledger.status_code,
            "body": res_ledger.text,
        }
        res_holds = client.get(
            "/api/admin/billing/holds?limit=50",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        admin_checks["holds"] = res_holds.json() if res_holds.status_code == 200 else {
            "status": res_holds.status_code,
            "body": res_holds.text,
        }
        res_stripe = client.get(
            "/api/admin/payments/stripe/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        admin_checks["stripe_health"] = res_stripe.json() if res_stripe.status_code == 200 else {
            "status": res_stripe.status_code,
            "body": res_stripe.text,
        }

        attempts = session.exec(
            select(SolverOutputAttempt).where(SolverOutputAttempt.created_at >= start_at)
        ).all()
        ledger_rows = session.exec(
            select(BillingLedger).where(BillingLedger.created_at >= start_at)
        ).all()
        usage_rows = session.exec(
            select(UsageLedger).where(UsageLedger.created_at >= start_at)
        ).all()
        holds = session.exec(
            select(CreditHold).where(CreditHold.created_at >= start_at)
        ).all()
        credit_lots = session.exec(
            select(CreditLot).where(CreditLot.created_at >= start_at)
        ).all()
        consumptions = session.exec(
            select(CreditLotConsumption).where(CreditLotConsumption.created_at >= start_at)
        ).all()
        payments = session.exec(
            select(Payment).where(Payment.created_at >= start_at)
        ).all()
        audit_logs = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.created_at >= start_at)
        ).all()

        solve_request_ids = {r["request_id"] for r in solve_results}
        solve_ledger_rows = [r for r in ledger_rows if r.request_id in solve_request_ids]
        solve_usage_rows = [r for r in usage_rows if r.reference_id in solve_request_ids]

        summary = {
            "run_id": run_id,
            "generated_at": _now_iso(),
            "users": {
                "student_a": student_a.id,
                "student_b": student_b.id,
                "grant_user": grant_user.id,
                "refund_user": refund_user.id,
                "admin": admin_user.id,
            },
            "wallet_before": wallet_before,
            "wallet_after": wallet_after,
            "solve_results": solve_results,
            "solve_ledger_rows": [_row_to_dict(r) for r in solve_ledger_rows],
            "solve_usage_rows": [_row_to_dict(r) for r in solve_usage_rows],
            "admin_checks": admin_checks,
        }

        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=_json_default))
        (out_dir / "attempts.json").write_text(json.dumps([_row_to_dict(r) for r in attempts], indent=2, default=_json_default))
        (out_dir / "wallet_before_after.json").write_text(json.dumps({"before": wallet_before, "after": wallet_after}, indent=2, default=_json_default))
        (out_dir / "ledger_rows.json").write_text(json.dumps([_row_to_dict(r) for r in ledger_rows], indent=2, default=_json_default))
        (out_dir / "usage_rows.json").write_text(json.dumps([_row_to_dict(r) for r in usage_rows], indent=2, default=_json_default))
        (out_dir / "holds.json").write_text(json.dumps([_row_to_dict(r) for r in holds], indent=2, default=_json_default))
        (out_dir / "credit_lots.json").write_text(json.dumps([_row_to_dict(r) for r in credit_lots], indent=2, default=_json_default))
        (out_dir / "credit_lot_consumptions.json").write_text(json.dumps([_row_to_dict(r) for r in consumptions], indent=2, default=_json_default))
        (out_dir / "payments_rows.json").write_text(json.dumps([_row_to_dict(r) for r in payments], indent=2, default=_json_default))
        (out_dir / "audit_log_rows.json").write_text(json.dumps([_row_to_dict(r) for r in audit_logs], indent=2, default=_json_default))

        report_md = reports_root / "ci_proof_real_solve_billing_latest.md"
        report_md.write_text(
            "# CI Proof (Real OpenAI Solve + Billing)\n\n"
            f"Run ID: `{run_id}`\n\n"
            f"Generated: `{_now_iso()}`\n\n"
            "## Users\n"
            f"- Student A: {student_a.id}\n"
            f"- Student B: {student_b.id}\n"
            f"- Grant User: {grant_user.id}\n"
            f"- Refund User: {refund_user.id}\n"
            f"- Admin: {admin_user.id}\n\n"
            "## Solve Results\n"
            + "\n".join([
                f"- {r['label']}: request_id={r['request_id']} attempt_id={r['attempt_id']} expected_credits={r['expected_credits']}"
                for r in solve_results
            ])
            + "\n\n"
            "## Artifacts\n"
            f"- reports/proof/{run_id}/summary.json\n"
            f"- reports/proof/{run_id}/attempts.json\n"
            f"- reports/proof/{run_id}/ledger_rows.json\n"
            f"- reports/proof/{run_id}/usage_rows.json\n"
            f"- reports/proof/{run_id}/holds.json\n"
            f"- reports/proof/{run_id}/credit_lots.json\n"
            f"- reports/proof/{run_id}/credit_lot_consumptions.json\n"
            f"- reports/proof/{run_id}/payments_rows.json\n"
            f"- reports/proof/{run_id}/audit_log_rows.json\n"
            "\n"
        )

        return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=str, default=str(uuid.uuid4()))
    args = parser.parse_args()
    run_ci_proof(args.run_id)


if __name__ == "__main__":
    main()
