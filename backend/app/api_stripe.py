
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models import StripeEvent, TopUpProduct, User
from app.services.stripe_service import stripe_service
from app.services.stripe_webhook_processor import stripe_webhook_processor
from app.services.top_up_service import top_up_service
from jose import jwt, JWTError
from app.auth import SECRET_KEY, ALGORITHM
import logging
import json

router = APIRouter(prefix="/stripe", tags=["stripe"])


def get_current_user(
    authorization: str = Header(None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


class StripeCheckoutBody(BaseModel):
    pack_code: str

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    session: Session = Depends(get_session)
):
    """
    Idempotently record Stripe webhooks and process fulfillment.
    """
    payload_bytes = await request.body()
    payload_str = payload_bytes.decode("utf-8")
    
    try:
        # 1. Verify and parse event
        # In development without signature, verify_webhook handles it gracefully if secret is missing
        event = stripe_service.verify_webhook(payload_str, stripe_signature)
        
        # 2. Idempotently record event
        from sqlmodel import select
        existing = session.exec(select(StripeEvent).where(StripeEvent.stripe_event_id == event.id)).first()
        if existing:
            logging.info(f"Stripe event {event.id} already received, skipping.")
            return {"status": "already_received"}
            
        stripe_event = StripeEvent(
            stripe_event_id=event.id,
            type=event.type,
            api_version=event.api_version,
            created_ts=event.created,
            livemode=event.livemode,
            payload_json=event.to_dict(),
            process_status="RECEIVED"
        )
        session.add(stripe_event)
        session.commit()
        session.refresh(stripe_event)
        
        # 3. Trigger processing inline
        try:
            stripe_webhook_processor.process_event(session, stripe_event)
        except Exception as e:
            logging.error(f"Error processing Stripe event {event.id}: {e}", exc_info=True)
            # We return 200 because the event is recorded. 
            # Failed process_status will be visible in Admin Dashboard for retry.
            
        return {"status": "ok"}
        
    except ValueError as e:
        # Invalid payload
        logging.error(f"Invalid Stripe Webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        logging.error(f"Stripe Webhook error: {e}", exc_info=True)
        # Always return 200-ish to Stripe unless it's a retryable system failure
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create_checkout_session")
async def create_checkout_session(
    body: StripeCheckoutBody,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    pack_code = (body.pack_code or "").strip()
    if not pack_code:
        raise HTTPException(status_code=400, detail="pack_code is required")

    product = session.exec(select(TopUpProduct).where(TopUpProduct.code == pack_code).where(TopUpProduct.is_active == True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="Top-up product not found or inactive")

    origin = request.headers.get("origin") or "http://localhost:3000"
    success_url = f"{origin}/billing/success?pack={pack_code}&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing/payment?status=cancelled"

    try:
        created = top_up_service.create_stripe_checkout_session(
            session=session,
            user_id=user.id,
            product_code=product.code,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"checkout_url": created.get("checkout_url"), "pack_code": pack_code}
