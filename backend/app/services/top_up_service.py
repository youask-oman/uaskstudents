
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime
from app.models import TopUpProduct, User, Payment, CreditLot, UsageLedger, TopUpOrder, BillingLedger
from app.services.credit_wallet_service import credit_wallet_service
from app.services.subscription_service import subscription_service
from app.services.invoice_service import invoice_service
from app.jobs.nightly_reconciliation import compute_user_balance

class TopUpService:
    def list_products(self, session: Session) -> List[TopUpProduct]:
        return session.exec(select(TopUpProduct).where(TopUpProduct.is_active == True)).all()

    def create_stripe_checkout_session(
        self, 
        session: Session, 
        user_id: int, 
        product_code: str,
        success_url: str,
        cancel_url: str
    ) -> dict:
        """
        Phase 4: Create Stripe Checkout Session.
        - Create TopUpOrder (CREATED).
        - Call Stripe API.
        - Update TopUpOrder (CHECKOUT_CREATED).
        """
        product = session.exec(select(TopUpProduct).where(TopUpProduct.code == product_code)).first()
        if not product:
            raise ValueError("Invalid product code")
            
        from app.models import TopUpOrder
        order = TopUpOrder(
            user_id=user_id,
            topup_product_id=product.id,
            credits=float(product.credits),
            price_usd=product.price_usd,
            currency="USD",
            status="CREATED"
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        
        from app.services.stripe_service import stripe_service
        try:
            stripe_session = stripe_service.create_topup_checkout_session(
                user_id=user_id,
                order_id=order.id,
                product_name=product.name,
                amount_usd=product.price_usd,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            order.status = "CHECKOUT_CREATED"
            order.stripe_checkout_session_id = stripe_session.id
            session.add(order)
            session.commit()
            
            return {
                "checkout_url": stripe_session.url,
                "stripe_session_id": stripe_session.id,
                "order_id": order.id
            }
        except Exception as e:
            order.status = "FAILED"
            session.add(order)
            session.commit()
            raise e

    def confirm_topup(
        self, 
        session: Session, 
        user_id: int, 
        product_code: str, 
        external_ref: str,
        source: str = "MANUAL_ADMIN"
    ) -> dict:
        """
        Idempotent confirmation of top-up.
        1. Check if external_ref used.
        2. Create Payment (Succeeded).
        3. Add Credits (Lot + UsageLedger).
        """
        # 0. Idempotency on CreditLot via external_ref
        existing = session.exec(select(CreditLot).where(CreditLot.external_ref == external_ref)).first()
        if existing:
            return {"status": "already_processed", "lot_id": existing.id}
            
        product = session.exec(select(TopUpProduct).where(TopUpProduct.code == product_code)).first()
        if not product:
            raise ValueError("Invalid product code")
            
        # 1. Create Payment Record
        payment = Payment(
            user_id=user_id,
            amount=product.price_usd,
            status="completed", # Phase 2 manual
            transaction_id=external_ref,
            payment_method="card" # or mock
        )
        session.add(payment)
        
        # 2. Add Credits (Creates Lot)
        computed_before = compute_user_balance(session, user_id)
        lot = credit_wallet_service.add_credits(
            session,
            user_id,
            amount=float(product.credits),
            source=source,
            expiry_days=120, # Policy
            lot_type="TOPUP",
            external_ref=external_ref
        )
        lot.amount_paid = product.price_usd
        lot.currency = "USD"
        lot.source_payment_id = external_ref
        
        # 3. Create Usage Ledger (CREDIT)
        # We need to sync Subscription balance here too.
        # credit_wallet_service.add_credits only creates Lot.
        # It does NOT update subscription balance in my implementation (Step 354 flush only).
        # So we must do it here.
        user = session.get(User, user_id)
        sub = subscription_service.get_or_create_subscription(session, user)
        
        sub.credits_balance += product.credits
        # Do we reset effective date? No.
        session.add(sub)
        
        ledger = UsageLedger(
            subscription_id=sub.id,
            transaction_type="CREDIT",
            amount=float(product.credits),
            balance_after=sub.credits_balance,
            reference_id=external_ref,
            meta={"product_code": product_code, "type": "TOPUP"}
        )
        session.add(ledger)
        
        # 4. Create/Complete TopUpOrder (For Invoicing)
        order = session.exec(select(TopUpOrder).where(
            (TopUpOrder.stripe_payment_intent_id == external_ref) | 
            (TopUpOrder.stripe_checkout_session_id == external_ref)
        )).first()
        
        if not order:
            # Create a manual order record for the invoice
            order = TopUpOrder(
                user_id=user_id,
                topup_product_id=product.id,
                credits=float(product.credits),
                price_usd=product.price_usd,
                status="FULFILLED",
                stripe_payment_intent_id=external_ref
            )
            session.add(order)
            session.flush()
        else:
            order.status = "FULFILLED"
            session.add(order)

        # 5. Billing ledger + cached balance
        computed_after = compute_user_balance(session, user_id)
        ledger = BillingLedger(
            user_id=user_id,
            action_type="TOPUP",
            request_id=external_ref,
            status="SETTLED",
            credits_charged=0,
            estimated_credits=0,
            actual_credits=0,
            delta_credits=float(product.credits),
            credits_before=computed_before,
            credits_after=computed_after,
        )
        session.add(ledger)
        session.flush()

        order.fulfill_credit_lot_id = lot.id
        order.fulfill_usage_ledger_id = ledger.id
        session.add(order)

        user = session.get(User, user_id)
        if user:
            user.credits_balance = float(computed_after)
            session.add(user)

        # 5. Create Invoice
        try:
            invoice_service.create_topup_invoice(session, order, payment)
        except Exception as e:
            import logging
            logging.error(f"Error creating manual top-up invoice: {e}")

        session.commit()
        session.refresh(lot)
        
        return {
            "status": "success",
            "lot_id": lot.id,
            "credits_added": product.credits,
            "new_balance": float(computed_after),
            "ledger_id": ledger.id,
        }

top_up_service = TopUpService()
