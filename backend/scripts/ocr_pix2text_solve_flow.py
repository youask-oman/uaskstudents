import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.database import engine
from app.models import User, BillingLedger, CreditHold, OCRJob, SolverOutputAttempt, OcrExtractionCache
from app.jobs.nightly_reconciliation import compute_user_balance
from app.services.credit_wallet_service import credit_wallet_service


def _pick_user(session: Session, email: str | None) -> User:
    if email:
        user = session.exec(select(User).where(User.email == email)).first()
        if user:
            return user

    # Try common dev users
    for candidate in ("student@uask.ai", "admin@uask.ai"):
        user = session.exec(select(User).where(User.email == candidate)).first()
        if user:
            return user

    # Fallback to first non-internal user
    user = session.exec(select(User).where(User.is_internal == False)).first()  # noqa: E712
    if user:
        return user

    # Last resort: any user
    user = session.exec(select(User)).first()
    if not user:
        raise RuntimeError("No users found in DB.")
    return user


def _ensure_credits(session: Session, user: User, required: float) -> None:
    current = float(compute_user_balance(session, user.id))
    if current >= required:
        return
    topup = max(required - current, 20.0)
    credit_wallet_service.add_credits(
        session=session,
        user_id=user.id,
        amount=topup,
        source="OCR_PIX2TEXT_TEST",
        lot_type="ADMIN_GRANT",
        external_ref=f"ocr_pix2text_test_{uuid.uuid4()}",
    )
    session.commit()


def _parse_sse(stream):
    meta = None
    telemetry = None
    done = None
    for line in stream.iter_lines():
        if not line:
            continue
        if line.startswith("data: "):
            payload_raw = line[len("data: ") :]
            try:
                payload = json.loads(payload_raw)
            except Exception:
                continue
            if payload.get("request_id") and payload.get("attempt_id"):
                meta = payload
            if payload.get("type") == "telemetry":
                telemetry = payload
            if payload.get("type") == "done":
                done = payload
                break
    return meta, telemetry, done


def run_flow(user_email: str | None, image_path: str, output_path: str | None) -> dict:
    start_at = datetime.utcnow()
    client = TestClient(app)
    run_id = str(uuid.uuid4())

    with Session(engine) as session:
        user = _pick_user(session, user_email)
        _ensure_credits(session, user, required=20.0)
        before_balance = float(compute_user_balance(session, user.id))

    with open(image_path, "rb") as f:
        raw_bytes = f.read()
    image_fingerprint = hashlib.sha256(raw_bytes).hexdigest()
    margin_pct = (uuid.uuid4().int % 3) + 1
    crop_signature = f"0.00000:0.00000:1.00000:1.00000:rot0:m{margin_pct}"
    dedupe_key = f"{user.id}:pix2text:{image_fingerprint}:{crop_signature}:local:local"
    with Session(engine) as session:
        cached = session.exec(
            select(OcrExtractionCache)
            .where(OcrExtractionCache.cache_key == dedupe_key)
            .where(OcrExtractionCache.user_id == user.id)
        ).all()
        if cached:
            for entry in cached:
                session.delete(entry)
            session.commit()

    with open(image_path, "rb") as f:
        files = {"file": ("test_image.jpg", f, "image/jpeg")}
        data = {
            "engine": "pix2text",
            "crop_x": 0,
            "crop_y": 0,
            "crop_w": 1,
            "crop_h": 1,
            "rotation": 0,
            "margin_pct": margin_pct,
        }
        ocr_res = client.post(f"/api/v1/ocr/extract?user_id={user.id}", files=files, data=data)

    if ocr_res.status_code != 200:
        raise RuntimeError(f"OCR extract failed: {ocr_res.status_code} {ocr_res.text}")

    ocr_payload = ocr_res.json()
    ocr_attempt_id = ocr_payload.get("ocr_attempt_id")
    extracted_text = ocr_payload.get("extracted_text") or ""
    if not ocr_attempt_id:
        raise RuntimeError("OCR response missing ocr_attempt_id")

    solve_body = {
        "confirmed_text": extracted_text or "Solve 2x+7=19",
        "tier": "standard",
        "requested_mode": "minimal",
        "input_modality": "text",
        "graph_mode": "auto",
        "features_used": {"ocr_used": True, "ocr_engine": "pix2text"},
        "source_type": "ocr",
        "source_id": ocr_attempt_id,
        "idempotency_key": f"solve:{user.id}:{ocr_attempt_id}:{uuid.uuid4()}",
    }

    with client.stream("POST", f"/api/v1/solve_v3_stream?user_id={user.id}", json=solve_body) as stream:
        meta, telemetry, done = _parse_sse(stream)

    if not done or not done.get("ok"):
        raise RuntimeError(f"Solve failed: {done}")

    with Session(engine) as session:
        after_balance = float(compute_user_balance(session, user.id))
        ocr_job = session.get(OCRJob, ocr_attempt_id)
        attempt = None
        if meta and meta.get("attempt_id"):
            attempt = session.exec(
                select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == meta["attempt_id"])
            ).first()
        ledgers = session.exec(
            select(BillingLedger)
            .where(BillingLedger.user_id == user.id)
            .where(BillingLedger.created_at >= start_at - timedelta(minutes=5))
            .order_by(BillingLedger.created_at.desc())
        ).all()
        holds = session.exec(
            select(CreditHold)
            .where(CreditHold.user_id == user.id)
            .where(CreditHold.created_at >= start_at - timedelta(minutes=5))
            .order_by(CreditHold.created_at.desc())
        ).all()

    report = {
        "run_id": run_id,
        "started_at": start_at.isoformat(),
        "user": {"id": user.id, "email": user.email},
        "crop_signature": crop_signature,
        "balance": {"before": before_balance, "after": after_balance},
        "ocr": ocr_payload,
        "solve": {
            "meta": meta,
            "telemetry": telemetry,
            "done": done,
        },
        "ocr_job": ocr_job.model_dump() if ocr_job else None,
        "attempt": attempt.model_dump() if attempt else None,
        "ledger_rows": [l.model_dump() for l in ledgers],
        "holds": [h.model_dump() for h in holds],
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    return report


def main():
    parser = argparse.ArgumentParser(description="Run OCR -> Solve flow using Pix2Text and dump ledger output.")
    parser.add_argument("--user-email", default=None)
    parser.add_argument("--image-path", default="backend/app/test_image.jpg")
    parser.add_argument("--output", default="reports/ocr_pix2text_flow_report.json")
    args = parser.parse_args()

    if not os.path.exists(args.image_path):
        raise FileNotFoundError(f"Image not found: {args.image_path}")

    report = run_flow(args.user_email, args.image_path, args.output)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
