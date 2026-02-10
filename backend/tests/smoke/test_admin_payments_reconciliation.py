import os

from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.database import engine
from app.main import app
from app.models import Payment, StripeEvent, Invoice, InvoiceLineItem, TopUpOrder, CreditLot, CreditLotConsumption, BillingLedger
from scripts.seed_production import run_seed
from tests.smoke.test_admin_routes import _auth_header


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

def test_payments_reconciliation_dry_run():
    os.environ["APP_ENV"] = "DEV"
    os.environ["SEED_DEV_DEFAULT_PASSWORD"] = os.environ.get("SEED_DEV_DEFAULT_PASSWORD", "DevOnlyChangeMe123!")
    _clear_payment_tables()
    run_seed(app_env="DEV", rotate_passwords=True, dev_fixtures=False)

    client = TestClient(app)
    admin_header = _auth_header("admin@uask.ai", os.environ["SEED_DEV_DEFAULT_PASSWORD"])

    resp = client.get("/api/admin/payments/reconciliation", headers=admin_header)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in [
        "missing_payment_rows",
        "missing_credit_lots_for_paid_orders",
        "duplicate_credit_lots",
        "mismatched_pack_amounts",
        "orphan_ledger_events",
        "stale_holds",
    ]:
        assert key in data
