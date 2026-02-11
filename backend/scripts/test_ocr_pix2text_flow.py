import json
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.database import engine
from app.models import User, BillingLedger


def _pick_user(session: Session) -> User:
    user = session.exec(select(User).where(User.email == "admin@uask.ai")).first()
    if user:
        return user
    user = session.exec(select(User).where(User.role == "student")).first()
    if user:
        return user
    raise RuntimeError("No user found for OCR test")


def _parse_sse(text: str) -> dict:
    payload = {}
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line.replace("data: ", "", 1))
                if isinstance(data, dict) and data.get("type") == "done":
                    payload["done"] = data
                if "attempt_id" in data and "request_id" in data:
                    payload["meta"] = data
            except Exception:
                continue
    return payload


def main() -> None:
    image_path = Path("backend/app/test_image.jpg")
    if not image_path.exists():
        image_path = Path("backend/uploads/test_image.jpg")
    if not image_path.exists():
        raise RuntimeError("Test image not found. Place an image at backend/app/test_image.jpg")

    with Session(engine) as session:
        user = _pick_user(session)
        user_id = user.id

    client = TestClient(app)

    with image_path.open("rb") as f:
        files = {"file": ("test_image.jpg", f, "image/jpeg")}
        data = {"engine": "pix2text"}
        res = client.post(f"/api/v1/ocr/extract?user_id={user_id}", files=files, data=data)
    if res.status_code != 200:
        raise RuntimeError(f"OCR extract failed: {res.status_code} {res.text}")
    ocr_payload = res.json()
    ocr_attempt_id = ocr_payload.get("ocr_attempt_id")
    extracted_text = (ocr_payload.get("extracted_text") or "").strip()
    if not extracted_text:
        raise RuntimeError("OCR returned empty text")

    idempotency_key = str(uuid.uuid4())
    solve_body = {
        "confirmed_text": extracted_text,
        "tier": "standard",
        "requested_mode": "detailed",
        "source_type": "ocr",
        "source_id": ocr_attempt_id,
        "question_text": extracted_text,
        "idempotency_key": idempotency_key,
    }

    with client.stream("POST", f"/api/v1/solve_v3_stream?user_id={user_id}", json=solve_body) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"Solve failed: {resp.status_code} {resp.text}")
        sse_text = ""
        for chunk in resp.iter_text():
            sse_text += chunk

    parsed = _parse_sse(sse_text)
    meta = parsed.get("meta", {})
    done = parsed.get("done", {})
    request_id = meta.get("request_id")

    with Session(engine) as session:
        entries = session.exec(
            select(BillingLedger)
            .where(BillingLedger.user_id == user_id)
            .order_by(BillingLedger.created_at.desc())
            .limit(10)
        ).all()
        ledger_rows = [
            {
                "id": e.id,
                "action_type": e.action_type,
                "request_id": e.request_id,
                "status": e.status,
                "credits_charged": float(e.credits_charged or 0),
                "credits_before": float(e.credits_before or 0),
                "credits_after": float(e.credits_after or 0),
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    print("OCR attempt:", ocr_attempt_id)
    print("Solve request_id:", request_id)
    print("Solve done:", done)
    print("Recent ledger entries:")
    print(json.dumps(ledger_rows, indent=2))


if __name__ == "__main__":
    main()

