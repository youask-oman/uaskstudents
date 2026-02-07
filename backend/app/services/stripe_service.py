
import stripe
from app.config import get_settings
from typing import Optional, Dict, Any
import logging

settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    def create_topup_checkout_session(
        self, 
        user_id: int, 
        order_id: int, 
        product_name: str, 
        amount_usd: float, 
        success_url: str, 
        cancel_url: str
    ) -> stripe.checkout.Session:
        return stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product_name,
                    },
                    'unit_amount': int(amount_usd * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': str(user_id),
                'topup_order_id': str(order_id)
            }
        )

    def create_subscription_checkout_session(
        self, 
        user_id: int, 
        subscription_id: int, 
        price_id: str, 
        success_url: str, 
        cancel_url: str
    ) -> stripe.checkout.Session:
        return stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': str(user_id),
                'subscription_id': str(subscription_id)
            }
        )

    def verify_webhook(self, payload: str, sig_header: str) -> stripe.Event:
        if not settings.STRIPE_WEBHOOK_SECRET:
            logging.warning("STRIPE_WEBHOOK_SECRET not set, skipping signature verification (NOT SECURE)")
            return stripe.Event.construct_from(import_json_if_needed(payload), stripe.api_key)
        
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

    def get_payment_intent(self, pi_id: str) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.retrieve(pi_id)

    def get_checkout_session(self, cs_id: str) -> stripe.checkout.Session:
        return stripe.checkout.Session.retrieve(cs_id)
        
    def get_subscription(self, sub_id: str) -> stripe.Subscription:
        return stripe.Subscription.retrieve(sub_id)

    def get_price_id(self, session, kind: str, internal_code: str) -> Optional[str]:
        from app.models import StripePriceMap
        from sqlmodel import select
        mapping = session.exec(select(StripePriceMap).where(
            StripePriceMap.kind == kind,
            StripePriceMap.internal_code == internal_code,
            StripePriceMap.active == True
        )).first()
        return mapping.stripe_price_id if mapping else None

def import_json_if_needed(payload):
    import json
    if isinstance(payload, str):
        return json.loads(payload)
    return payload

stripe_service = StripeService()
