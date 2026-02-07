
from sqlmodel import Session, select
from app.models import (
    StripeEvent, TopUpOrder, Payment, User, CreditLot, 
    UsageLedger, Subscription, SubscriptionBillingLink, SubscriptionPeriod
)
from app.services.credit_wallet_service import credit_wallet_service
from app.services.subscription_service import subscription_service
from datetime import datetime
import logging

class StripeWebhookProcessor:
    def process_event(self, session: Session, stripe_event: StripeEvent):
        try:
            event_type = stripe_event.type
            payload = stripe_event.payload_json
            data_object = payload.get("data", {}).get("object", {})
            
            logging.info(f"Processing Stripe event: {event_type} ({stripe_event.stripe_event_id})")
            
            if event_type == "checkout.session.completed":
                self.handle_checkout_session_completed(session, data_object)
            elif event_type in ["payment_intent.succeeded", "payment_intent.created"]:
                # user request: "Trigger on either: checkout.session.completed with payment_status=paid OR payment_intent.succeeded"
                if event_type == "payment_intent.succeeded":
                    self.handle_payment_intent_succeeded(session, data_object)
            elif event_type == "payment_intent.payment_failed":
                self.handle_payment_intent_failed(session, data_object)
            elif event_type in ["customer.subscription.created", "customer.subscription.updated"]:
                self.handle_subscription_updated(session, data_object)
            elif event_type == "customer.subscription.deleted":
                self.handle_subscription_deleted(session, data_object)
            elif event_type == "invoice.paid":
                self.handle_invoice_paid(session, data_object)
            elif event_type == "invoice.payment_failed":
                self.handle_invoice_payment_failed(session, data_object)
            else:
                logging.info(f"Stripe event {event_type} ignored.")
                stripe_event.process_status = "IGNORED"
                
            if stripe_event.process_status == "RECEIVED":
                stripe_event.process_status = "PROCESSED"
                
            stripe_event.processed_at = datetime.utcnow()
            session.add(stripe_event)
            session.commit()
            
        except Exception as e:
            logging.error(f"Failed to process Stripe event {stripe_event.stripe_event_id}: {e}", exc_info=True)
            stripe_event.process_status = "FAILED"
            stripe_event.last_error = str(e)
            session.add(stripe_event)
            session.commit()
            raise e

    def handle_checkout_session_completed(self, session: Session, session_obj: dict):
        mode = session_obj.get("mode")
        metadata = session_obj.get("metadata", {})
        
        if mode == "payment":
            order_id = metadata.get("topup_order_id")
            if order_id:
                order = session.get(TopUpOrder, int(order_id))
                if order:
                    order.stripe_checkout_session_id = session_obj.get("id")
                    order.stripe_payment_intent_id = session_obj.get("payment_intent")
                    session.add(order)
                    session.commit()
                    
                    if session_obj.get("payment_status") == "paid":
                        self.fulfill_topup(session, order)
        
        elif mode == "subscription":
            # Just ensure we have the billing link initiated
            self.handle_subscription_updated(session, session_obj.get("subscription", {}))

    def handle_payment_intent_succeeded(self, session: Session, pi_obj: dict):
        pi_id = pi_obj.get("id")
        order = session.exec(select(TopUpOrder).where(TopUpOrder.stripe_payment_intent_id == pi_id)).first()
        if not order:
            metadata = pi_obj.get("metadata", {})
            order_id = metadata.get("topup_order_id")
            if order_id:
                order = session.get(TopUpOrder, int(order_id))
        
        if order:
            if not order.stripe_payment_intent_id:
                order.stripe_payment_intent_id = pi_id
                session.add(order)
                session.commit()
            self.fulfill_topup(session, order)

    def handle_payment_intent_failed(self, session: Session, pi_obj: dict):
        pi_id = pi_obj.get("id")
        order = session.exec(select(TopUpOrder).where(TopUpOrder.stripe_payment_intent_id == pi_id)).first()
        if order:
            order.status = "FAILED"
            session.add(order)
            session.commit()

    def fulfill_topup(self, session: Session, order: TopUpOrder):
        if order.status == "FULFILLED":
            return
            
        # 1. Upsert Payment
        pi_id = order.stripe_payment_intent_id
        payment = session.exec(select(Payment).where(
            Payment.provider == "STRIPE",
            Payment.external_type == "PAYMENT_INTENT",
            Payment.external_id == pi_id
        )).first()
        
        if not payment:
            payment = Payment(
                user_id=order.user_id,
                amount=order.price_usd,
                currency=order.currency,
                status="SUCCEEDED",
                provider="STRIPE",
                external_id=pi_id,
                external_type="PAYMENT_INTENT",
                transaction_id=pi_id
            )
            session.add(payment)
            session.flush()
        else:
            payment.status = "SUCCEEDED"
            session.add(payment)

        # 2. Add Credits (CreditLot)
        lot = credit_wallet_service.add_credits(
            session,
            order.user_id,
            amount=order.credits,
            source="STRIPE",
            expiry_days=120,
            lot_type="TOPUP",
            external_ref=pi_id
        )
        session.flush()

        # 3. Update Balance and Ledger
        user = session.get(User, order.user_id)
        sub = subscription_service.get_or_create_subscription(session, user)
        sub.credits_balance += order.credits
        session.add(sub)
        
        ledger = UsageLedger(
            subscription_id=sub.id,
            transaction_type="CREDIT",
            amount=order.credits,
            balance_after=sub.credits_balance,
            reference_id=pi_id,
            meta={"topup_order_id": order.id, "source": "STRIPE"}
        )
        session.add(ledger)
        
        # 4. Mark Order FULFILLED
        order.status = "FULFILLED"
        order.fulfill_credit_lot_id = lot.id
        order.fulfill_usage_ledger_id = ledger.id
        session.add(order)
        
        session.commit()
        logging.info(f"Top-up fulfilled: Order {order.id}, User {order.user_id}, Credits {order.credits}")

    def handle_subscription_updated(self, session: Session, sub_obj: dict):
        if isinstance(sub_obj, str):
            # Might be just an ID if expanded=False
            return
            
        stripe_sub_id = sub_obj.get("id")
        customer_id = sub_obj.get("customer")
        metadata = sub_obj.get("metadata", {})
        
        billing_link = session.exec(select(SubscriptionBillingLink).where(
            SubscriptionBillingLink.stripe_subscription_id == stripe_sub_id
        )).first()
        
        if not billing_link:
            internal_sub_id = metadata.get("subscription_id")
            if internal_sub_id:
                items = sub_obj.get("items", {}).get("data", [])
                price_id = items[0].get("price", {}).get("id") if items else None
                billing_link = SubscriptionBillingLink(
                    subscription_id=int(internal_sub_id),
                    user_id=int(metadata.get("user_id")),
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=stripe_sub_id,
                    stripe_price_id=price_id or "unknown",
                    status=sub_obj.get("status").upper(),
                    current_period_start=datetime.fromtimestamp(sub_obj.get("current_period_start")),
                    current_period_end=datetime.fromtimestamp(sub_obj.get("current_period_end")),
                )
        else:
            billing_link.status = sub_obj.get("status").upper()
            billing_link.current_period_start = datetime.fromtimestamp(sub_obj.get("current_period_start"))
            billing_link.current_period_end = datetime.fromtimestamp(sub_obj.get("current_period_end"))
            billing_link.cancel_at_period_end = sub_obj.get("cancel_at_period_end", False)
            billing_link.updated_at = datetime.utcnow()
            
        if billing_link:
            session.add(billing_link)
            
            # Update internal Subscription status
            internal_sub = session.get(Subscription, billing_link.subscription_id)
            if internal_sub:
                internal_sub.status = self.map_stripe_status(billing_link.status)
                # Sync dates
                internal_sub.current_period_start = billing_link.current_period_start
                internal_sub.current_period_end = billing_link.current_period_end
                session.add(internal_sub)
                
                # Update current active period if it exists
                self.sync_subscription_period(session, internal_sub, billing_link)
            
            session.commit()

    def sync_subscription_period(self, session: Session, sub: Subscription, link: SubscriptionBillingLink):
        # find matching period
        period = session.exec(select(SubscriptionPeriod).where(
            SubscriptionPeriod.subscription_id == sub.id,
            SubscriptionPeriod.status == "OPEN"
        ).order_by(SubscriptionPeriod.period_start.desc())).first()
        
        if period:
            # We align the end date primarily. 
            # If Stripe pushed it back (e.g. trial ended), we update.
            period.period_end = link.current_period_end
            session.add(period)

    def map_stripe_status(self, stripe_status: str) -> str:
        s = stripe_status.upper()
        if s == "ACTIVE": return "active"
        if s in ["PAST_DUE", "UNPAID", "INCOMPLETE"]: return "past_due"
        if s == "CANCELED": return "cancelled"
        if s == "TRIALING": return "active"
        return "active"

    def handle_subscription_deleted(self, session: Session, sub_obj: dict):
        stripe_sub_id = sub_obj.get("id")
        billing_link = session.exec(select(SubscriptionBillingLink).where(
            SubscriptionBillingLink.stripe_subscription_id == stripe_sub_id
        )).first()
        if billing_link:
            billing_link.status = "CANCELED"
            billing_link.updated_at = datetime.utcnow()
            session.add(billing_link)
            
            internal_sub = session.get(Subscription, billing_link.subscription_id)
            if internal_sub:
                internal_sub.status = "cancelled"
                session.add(internal_sub)
            session.commit()

    def handle_invoice_paid(self, session: Session, invoice_obj: dict):
        stripe_sub_id = invoice_obj.get("subscription")
        if stripe_sub_id:
            billing_link = session.exec(select(SubscriptionBillingLink).where(
                SubscriptionBillingLink.stripe_subscription_id == stripe_sub_id
            )).first()
            if billing_link:
                billing_link.status = "ACTIVE"
                session.add(billing_link)
                
                internal_sub = session.get(Subscription, billing_link.subscription_id)
                if internal_sub:
                    internal_sub.status = "active"
                    session.add(internal_sub)
                session.commit()

    def handle_invoice_payment_failed(self, session: Session, invoice_obj: dict):
        stripe_sub_id = invoice_obj.get("subscription")
        if stripe_sub_id:
            billing_link = session.exec(select(SubscriptionBillingLink).where(
                SubscriptionBillingLink.stripe_subscription_id == stripe_sub_id
            )).first()
            if billing_link:
                billing_link.status = "PAST_DUE"
                session.add(billing_link)
                
                internal_sub = session.get(Subscription, billing_link.subscription_id)
                if internal_sub:
                    internal_sub.status = "past_due"
                    session.add(internal_sub)
                session.commit()

stripe_webhook_processor = StripeWebhookProcessor()
