
import stripe
from sqlmodel import Session, select
from app.database import engine
from app.models import Payment, TopUpOrder, SubscriptionBillingLink, Subscription, SystemErrorEntry
from app.config import get_settings
from datetime import datetime, timedelta
import logging

settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

def nightly_stripe_reconciliation():
    """
    Nightly job to verify consistency between Stripe and local DB.
    """
    if not settings.STRIPE_ENABLED:
        logging.info("Stripe not enabled, skipping reconciliation.")
        return

    with Session(engine) as session:
        logging.info("Starting Stripe reconciliation job...")
        
        # 1. Check recent Payment Intents
        recent_cutoff = int((datetime.utcnow() - timedelta(days=7)).timestamp())
        
        try:
            # Check Succeeded PIs
            intents = stripe.PaymentIntent.list(created={'gt': recent_cutoff}, limit=100)
            
            for pi in intents.auto_paging_iter():
                if pi.status == "succeeded":
                    # Verify we have a Payment record
                    payment = session.exec(select(Payment).where(
                        Payment.provider == "STRIPE",
                        Payment.external_id == pi.id
                    )).first()
                    
                    if not payment:
                        msg = f"Reconciliation Error: Succeeded Stripe PI {pi.id} has no matching local Payment record."
                        logging.error(msg)
                        session.add(SystemErrorEntry(
                            level="ERROR",
                            component="StripeReconciler",
                            message=msg
                        ))
                    
                    # Verify TopUpOrder if it was a topup
                    order_id = pi.metadata.get("topup_order_id")
                    if order_id:
                        order = session.get(TopUpOrder, int(order_id))
                        if not order or order.status != "FULFILLED":
                            msg = f"Reconciliation Error: Succeeded Stripe PI {pi.id} linked to TopUpOrder {order_id} but status is {order.status if order else 'MISSING'}."
                            logging.error(msg)
                            session.add(SystemErrorEntry(
                                level="ERROR",
                                component="StripeReconciler",
                                message=msg
                            ))

            # 2. Check active Subscriptions
            stripe_subs = stripe.Subscription.list(status='active', limit=100)
            for ssub in stripe_subs.auto_paging_iter():
                billing_link = session.exec(select(SubscriptionBillingLink).where(
                    SubscriptionBillingLink.stripe_subscription_id == ssub.id
                )).first()
                
                if not billing_link:
                    msg = f"Reconciliation Error: Active Stripe Subscription {ssub.id} has no local SubscriptionBillingLink."
                    logging.error(msg)
                    session.add(SystemErrorEntry(
                        level="ERROR",
                        component="StripeReconciler",
                        message=msg
                    ))
                else:
                    internal_sub = session.get(Subscription, billing_link.subscription_id)
                    if not internal_sub or internal_sub.status != "active":
                         msg = f"Reconciliation Error: Stripe sub {ssub.id} is active but local sub {billing_link.subscription_id} is {internal_sub.status if internal_sub else 'MISSING'}."
                         logging.error(msg)
                         session.add(SystemErrorEntry(
                            level="ERROR",
                            component="StripeReconciler",
                            message=msg
                        ))

            session.commit()
            logging.info("Stripe reconciliation job complete.")
            
        except Exception as e:
            logging.error(f"Stripe reconciliation job failed: {e}", exc_info=True)
            session.add(SystemErrorEntry(
                level="CRITICAL",
                component="StripeReconciler",
                message=f"Job failed: {str(e)}"
            ))
            session.commit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    nightly_stripe_reconciliation()
