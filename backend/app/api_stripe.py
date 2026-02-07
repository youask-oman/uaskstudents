
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from sqlmodel import Session
from app.database import get_session
from app.models import StripeEvent
from app.services.stripe_service import stripe_service
from app.services.stripe_webhook_processor import stripe_webhook_processor
import logging
import json

router = APIRouter(prefix="/stripe", tags=["stripe"])

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
