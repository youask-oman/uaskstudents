import os
import uuid

from sqlmodel import Session, select, delete

from app.database import engine
from app.models import User, TopUpProduct, TopUpOrder, CreditLot, BillingLedger, Payment, StripeEvent, Invoice, InvoiceLineItem, CreditLotConsumption
from app.services.stripe_webhook_processor import stripe_webhook_processor
from app.jobs.nightly_reconciliation import compute_user_balance
from scripts.seed_production import run_seed


def _clear_payment_tables():
    with Session(engine) as session:
        for model in [
            CreditLotConsumption,
            BillingLedger,
            CreditLot,
            InvoiceLineItem,
            Invoice,
            TopUpOrder,
            StripeEvent,
            Payment,
        ]:
            session.exec(delete(model))
        session.commit()

def test_stripe_topup_mints_creditlot_and_ledger():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
    _clear_payment_tables()
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "admin@uask.ai")).first()
        assert user is not None

        product = session.exec(select(TopUpProduct).where(TopUpProduct.code == "test_topup")).first()
        if not product:
            product = TopUpProduct(code="test_topup", name="Test Topup", credits=550, price_usd=5.0, is_active=True)
            session.add(product)
            session.commit()
            session.refresh(product)

        pi_id = f"pi_test_topup_{uuid.uuid4().hex}"
        order = TopUpOrder(
            user_id=user.id,
            topup_product_id=product.id,
            credits=float(product.credits),
            price_usd=float(product.price_usd),
            currency="USD",
            status="CREATED",
            stripe_payment_intent_id=pi_id,
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        stripe_webhook_processor.fulfill_topup(session, order)

        lot = session.exec(select(CreditLot).where(CreditLot.external_ref == pi_id)).first()
        assert lot is not None
        assert lot.lot_type == "TOPUP"

        ledger = session.exec(select(BillingLedger).where(BillingLedger.request_id == pi_id)).first()
        assert ledger is not None
        assert ledger.action_type == "TOPUP"

        computed = compute_user_balance(session, user.id)
        session.refresh(user)
        assert float(user.credits_balance) == float(computed)
