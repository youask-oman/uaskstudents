import sys
import os
import uuid
from datetime import datetime
from sqlmodel import Session, select

# Adjust path to import from app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import (
    User, TopUpOrder, Payment, Subscription, 
    SubscriptionBillingLink, Invoice, InvoiceLineItem,
    InvoiceKind, InvoiceStatus, TopUpProduct
)
from app.services.invoice_service import invoice_service

def create_demo_samples():
    with Session(engine) as session:
        print("--- PHASE 5 INVOICE SAMPLES GENERATOR ---")
        
        uid = str(uuid.uuid4())[:8]
        # 1. Create a unique demo user
        email = f"demo_{uid}@uask.ai"
        user = User(
            email=email,
            full_name=f"Demo User {uid}",
            password_hash="---"
        )
        session.add(user)
        session.flush()
        print(f"Created demo user: {user.email}")

        # 2. Sample 1: Top-Up Invoice
        print("\nCreating Top-Up Sample...")
        product = session.exec(select(TopUpProduct).where(TopUpProduct.code == "standard-60")).first()
        if not product:
            product = TopUpProduct(
                code="standard-60",
                name="Standard Pack",
                credits=60,
                price_usd=5.99
            )
            session.add(product)
            session.flush()

        order = TopUpOrder(
            user_id=user.id,
            topup_product_id=product.id,
            credits=60,
            price_usd=product.price_usd,
            currency="USD",
            status="PAID",
            stripe_payment_intent_id=f"pi_demo_topup_{uid}"
        )
        session.add(order)
        session.flush()

        payment = Payment(
            user_id=user.id,
            amount=5.99,
            currency="USD",
            transaction_id=f"pi_demo_topup_{uid}",
            external_id=f"pi_demo_topup_{uid}",
            external_type="PAYMENT_INTENT",
            status="SUCCEEDED",
            payment_method="card",
            provider="STRIPE"
        )
        session.add(payment)
        session.flush()

        topup_invoice = invoice_service.create_topup_invoice(session, order, payment)
        print(f"Generated Top-Up Invoice: {topup_invoice.invoice_number}")
        print(f"Total: {topup_invoice.currency} {topup_invoice.total_amount}")

        # 3. Sample 2: Subscription Invoice (Simulated Mirror)
        print("\nCreating Subscription Sample (Mirrored)...")
        # Need a subscription
        sub = session.exec(select(Subscription).where(Subscription.user_id == user.id)).first()
        if not sub:
            sub = Subscription(
                user_id=user.id,
                plan_id=1, # Assume plan 1 is standard
                status="active",
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow()
            )
            session.add(sub)
            session.flush()
        
        billing_link = session.exec(select(SubscriptionBillingLink).where(SubscriptionBillingLink.subscription_id == sub.id)).first()
        if not billing_link:
            billing_link = SubscriptionBillingLink(
                user_id=user.id,
                subscription_id=sub.id,
                stripe_customer_id=f"cus_demo_{uid}",
                stripe_subscription_id=f"sub_demo_{uid}",
                stripe_price_id=f"price_demo_{uid}",
                status="ACTIVE",
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow()
            )
            session.add(billing_link)
            session.flush()

        # Simulated Stripe Payload
        stripe_payload = {
            "id": f"in_demo_sub_{uid}",
            "customer": f"cus_demo_{uid}",
            "subscription": f"sub_demo_{uid}",
            "status": "paid",
            "currency": "usd",
            "subtotal": 999, # $9.99
            "tax": 0,
            "total": 999,
            "amount_paid": 999,
            "amount_remaining": 0,
            "period_start": int(datetime.utcnow().timestamp()),
            "period_end": int((datetime.utcnow().timestamp() + 2592000)),
            "lines": {
                "data": [{
                    "id": f"li_demo_{uid}",
                    "description": "Standard Monthly Subscription",
                    "amount": 999,
                    "quantity": 1
                }]
            },
            "payment_intent": f"pi_demo_sub_{uid}"
        }
        
        sub_invoice = invoice_service.upsert_subscription_invoice(session, stripe_payload)
        print(f"Generated Subscription Invoice: {sub_invoice.invoice_number}")
        print(f"Total: {sub_invoice.currency} {sub_invoice.total_amount}")

        # 4. Sample 3: Refund / Adjustment
        print("\nCreating Refund/Adjustment Sample...")
        reason = "Partial refund for late delivery"
        adjustment = invoice_service.create_adjustment_invoice(
            session, 
            topup_invoice, 
            amount=2.00, 
            reason=reason
        )
        print(f"Generated Adjustment Invoice (Credit Note): {adjustment.invoice_number}")
        print(f"Total: {adjustment.currency} {adjustment.total_amount}")
        print(f"Status of original invoice {topup_invoice.invoice_number}: {topup_invoice.status}")

        session.commit()
        print("\n--- ALL SAMPLES COMMITTED ---")

        # 5. Provider Cost Example (gpt-5-mini)
        print("\n--- PROVIDER COST EXAMPLE (gpt-5-mini) ---")
        input_tokens = 3917
        output_tokens = 1606
        cached_tokens = 0
        
        # Current logic/pricing values
        price_in = 0.25 / 1_000_000
        price_out = 2.00 / 1_000_000
        price_cached = 0.025 / 1_000_000
        
        cost = (input_tokens * price_in) + (output_tokens * price_out) + (cached_tokens * price_cached)
        
        print(f"Tokens: In={input_tokens}, Out={output_tokens}, Cached={cached_tokens}")
        print(f"Math: ({input_tokens} * {price_in}) + ({output_tokens} * {price_out})")
        print(f"Provider Cost USD: {cost:.8f}")

if __name__ == "__main__":
    create_demo_samples()
