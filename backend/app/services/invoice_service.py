from datetime import datetime
from typing import Optional, List
from sqlmodel import Session, select, func
from app.models import (
    Invoice, InvoiceLineItem, InvoiceSequence, InvoiceKind, InvoiceStatus, 
    InvoiceLineItemKind, TopUpOrder, Subscription, Payment, TaxMode
)
import logging

logger = logging.getLogger(__name__)

class InvoiceService:
    @staticmethod
    def _generate_invoice_number(session: Session) -> str:
        """Generates a monotonic invoice number: INV-YYYY-######"""
        year = datetime.utcnow().year
        # Atomic increment using select for update if possible, but for simplicity here we use a basic lock-like approach
        # In production this should use 'WITH ... UPDATE' or a dedicated sequence
        seq = session.exec(select(InvoiceSequence).where(InvoiceSequence.year == year).with_for_update()).first()
        if not seq:
            seq = InvoiceSequence(year=year, last_value=0)
            session.add(seq)
            session.flush()
        
        seq.last_value += 1
        return f"INV-{year}-{seq.last_value:06d}"

    @classmethod
    def create_topup_invoice(cls, session: Session, order: TopUpOrder, payment: Payment) -> Invoice:
        """Creates a PAID receipt invoice for a completed Top-up."""
        # Check idempotency
        existing = session.exec(select(Invoice).where(Invoice.topup_order_id == order.id)).first()
        if existing:
            logger.info(f"Top-up invoice already exists for order {order.id}")
            return existing

        invoice_num = cls._generate_invoice_number(session)
        invoice = Invoice(
            user_id=order.user_id,
            topup_order_id=order.id,
            stripe_payment_intent_id=order.stripe_payment_intent_id,
            invoice_number=invoice_num,
            kind=InvoiceKind.TOPUP,
            status=InvoiceStatus.PAID,
            currency=order.currency,
            subtotal_amount=order.price_usd,
            total_amount=order.price_usd,
            amount_paid=order.price_usd,
            amount_due=0.0,
            tax_mode=TaxMode.NONE,
            issued_at=datetime.utcnow(),
            paid_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(invoice)
        session.flush()

        line = InvoiceLineItem(
            invoice_id=invoice.id,
            kind=InvoiceLineItemKind.TOPUP_CREDITS,
            description=f"Purchase of {order.credits} Credits",
            quantity=1.0,
            unit_price=order.price_usd,
            amount=order.price_usd,
            payment_id=payment.id,
            metadata_json={"credits": order.credits}
        )
        session.add(line)
        session.commit()
        session.refresh(invoice)
        logger.info(f"Created top-up invoice {invoice_num} for order {order.id}")
        return invoice

    @classmethod
    def upsert_subscription_invoice(cls, session: Session, stripe_invoice: dict) -> Invoice:
        """Mirrors a Stripe Invoice into our local DB."""
        stripe_id = stripe_invoice.get("id")
        if not stripe_id:
            raise ValueError("Stripe invoice payload missing ID")

        # Find user by stripe_customer_id
        from app.models import SubscriptionBillingLink
        user_id_link = session.exec(select(SubscriptionBillingLink).where(SubscriptionBillingLink.stripe_customer_id == stripe_invoice.get("customer"))).first()
        if not user_id_link:
            logger.warning(f"Could not find local user for Stripe customer {stripe_invoice.get('customer')}")
            return None # Or handle differently

        invoice = session.exec(select(Invoice).where(Invoice.stripe_invoice_id == stripe_id)).first()
        
        status_map = {
            "draft": InvoiceStatus.DRAFT,
            "open": InvoiceStatus.OPEN,
            "paid": InvoiceStatus.PAID,
            "void": InvoiceStatus.VOID,
            "uncollectible": InvoiceStatus.UNCOLLECTIBLE
        }
        status = status_map.get(stripe_invoice.get("status"), InvoiceStatus.OPEN)

        subtotal = stripe_invoice.get("subtotal", 0) / 100.0
        tax = stripe_invoice.get("tax", 0) / 100.0
        total = stripe_invoice.get("total", 0) / 100.0
        paid = stripe_invoice.get("amount_paid", 0) / 100.0
        due = stripe_invoice.get("amount_remaining", 0) / 100.0

        if not invoice:
            invoice_num = cls._generate_invoice_number(session)
            invoice = Invoice(
                user_id=user_id_link.user_id,
                subscription_id=user_id_link.subscription_id,
                stripe_invoice_id=stripe_id,
                stripe_payment_intent_id=stripe_invoice.get("payment_intent"),
                invoice_number=invoice_num,
                kind=InvoiceKind.SUBSCRIPTION,
                status=status,
                currency=stripe_invoice.get("currency", "usd").upper(),
                period_start=datetime.fromtimestamp(stripe_invoice.get("period_start")),
                period_end=datetime.fromtimestamp(stripe_invoice.get("period_end")),
                subtotal_amount=subtotal,
                tax_amount=tax,
                total_amount=total,
                amount_paid=paid,
                amount_due=due,
                tax_mode=TaxMode.FINAL if stripe_invoice.get("status") != "draft" else TaxMode.ESTIMATED,
                created_at=datetime.utcnow()
            )
            session.add(invoice)
            session.flush()
            
            # Add line items from Stripe
            for item in stripe_invoice.get("lines", {}).get("data", []):
                li = InvoiceLineItem(
                    invoice_id=invoice.id,
                    kind=InvoiceLineItemKind.SUBSCRIPTION_FEE,
                    description=item.get("description", "Subscription Fee"),
                    quantity=item.get("quantity", 1.0),
                    unit_price=item.get("amount", 0) / 100.0,
                    amount=item.get("amount", 0) / 100.0,
                    metadata_json={"stripe_line_id": item.get("id")}
                )
                session.add(li)
        else:
            # Update existing
            invoice.status = status
            invoice.amount_paid = paid
            invoice.amount_due = due
            if status == InvoiceStatus.PAID:
                invoice.paid_at = datetime.utcnow()
            invoice.updated_at = datetime.utcnow()
            session.add(invoice)

        session.commit()
        session.refresh(invoice)
        return invoice

    @classmethod
    def create_adjustment_invoice(cls, session: Session, original_invoice: Invoice, amount: float, reason: str) -> Invoice:
        """Creates a negative adjustment (Credit Note) linked to an original invoice."""
        invoice_num = cls._generate_invoice_number(session)
        adjustment = Invoice(
            user_id=original_invoice.user_id,
            invoice_number=invoice_num,
            kind=InvoiceKind.ADJUSTMENT,
            status=InvoiceStatus.REFUNDED,
            currency=original_invoice.currency,
            subtotal_amount=-abs(amount),
            total_amount=-abs(amount),
            amount_paid=-abs(amount),
            amount_due=0.0,
            tax_mode=TaxMode.NONE,
            issued_at=datetime.utcnow(),
            paid_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(adjustment)
        session.flush()

        line = InvoiceLineItem(
            invoice_id=adjustment.id,
            kind=InvoiceLineItemKind.ADJUSTMENT,
            description=f"Adjustment for {original_invoice.invoice_number}: {reason}",
            quantity=1.0,
            unit_price=-abs(amount),
            amount=-abs(amount)
        )
        session.add(line)
        
        # Update original invoice status if needed
        if original_invoice.status == InvoiceStatus.PAID:
            original_invoice.status = InvoiceStatus.REFUNDED
            session.add(original_invoice)

        session.commit()
        session.refresh(adjustment)
        return adjustment

    @staticmethod
    def render_invoice_html(invoice: Invoice, lines: List[InvoiceLineItem], user_name: str, user_email: str) -> str:
        """Renders a premium HTML template for an invoice."""
        status_color = "#10b981" if invoice.status == InvoiceStatus.PAID else "#f59e0b"
        if invoice.status in [InvoiceStatus.VOID, InvoiceStatus.UNCOLLECTIBLE]:
            status_color = "#ef4444"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                body {{ 
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
                    color: #1e293b;
                    line-height: 1.5;
                    margin: 0;
                    padding: 40px;
                    background-color: #f8fafc;
                }}
                .invoice-card {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 50px;
                    border-radius: 16px;
                    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                }}
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    border-bottom: 2px solid #f1f5f9;
                    padding-bottom: 30px;
                    margin-bottom: 40px;
                }}
                .brand {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }}
                .logo-text {{
                    font-size: 24px;
                    font-weight: 700;
                    color: #2563eb;
                    letter-spacing: -0.025em;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 9999px;
                    font-size: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                    background-color: {status_color}20;
                    color: {status_color};
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 40px;
                    margin-bottom: 40px;
                }}
                .section-title {{
                    font-size: 12px;
                    font-weight: 600;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin-bottom: 8px;
                }}
                .info-text {{
                    font-size: 15px;
                    margin: 0;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 40px;
                }}
                th {{
                    text-align: left;
                    font-size: 13px;
                    font-weight: 600;
                    color: #64748b;
                    border-bottom: 2px solid #f1f5f9;
                    padding: 12px 0;
                }}
                td {{
                    padding: 16px 0;
                    border-bottom: 1px solid #f1f5f9;
                    vertical-align: top;
                }}
                .line-desc {{
                    font-weight: 600;
                    font-size: 14px;
                }}
                .line-sub {{
                    font-size: 12px;
                    color: #64748b;
                }}
                .totals {{
                    margin-left: auto;
                    width: 300px;
                }}
                .total-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                }}
                .grand-total {{
                    margin-top: 12px;
                    padding-top: 12px;
                    border-top: 2px solid #f1f5f9;
                    font-size: 18px;
                    font-weight: 700;
                }}
                .footer {{
                    margin-top: 60px;
                    text-align: center;
                    font-size: 13px;
                    color: #94a3b8;
                }}
            </style>
        </head>
        <body>
            <div class="invoice-card">
                <div class="header">
                    <div class="brand">
                        <span class="logo-text">uask.ai</span>
                    </div>
                    <div style="text-align: right">
                        <h2 style="margin: 0; font-size: 20px;">Invoice #{invoice.invoice_number}</h2>
                        <div class="status-badge" style="margin-top: 8px;">{invoice.status}</div>
                    </div>
                </div>

                <div class="grid">
                    <div>
                        <div class="section-title">Billed To</div>
                        <p class="info-text"><strong>{user_name}</strong></p>
                        <p class="info-text" style="color: #64748b;">{user_email}</p>
                    </div>
                    <div style="text-align: right">
                        <div class="section-title">Date Issued</div>
                        <p class="info-text">{invoice.created_at.strftime('%B %d, %Y')}</p>
                        { f'<div class="section-title" style="margin-top: 16px;">Paid At</div><p class="info-text">{invoice.paid_at.strftime("%B %d, %Y")}</p>' if invoice.paid_at else '' }
                    </div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th style="text-align: center">Qty</th>
                            <th style="text-align: right">Price</th>
                            <th style="text-align: right">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr>
                            <td>
                                <div class="line-desc">{l.description}</div>
                                <div class="line-sub">{l.kind}</div>
                            </td>
                            <td style="text-align: center">{l.quantity}</td>
                            <td style="text-align: right">${l.unit_price:.2f}</td>
                            <td style="text-align: right"><strong>${l.amount:.2f}</strong></td>
                        </tr>
                        ''' for l in lines])}
                    </tbody>
                </table>

                <div class="totals">
                    <div class="total-row">
                        <span style="color: #64748b;">Subtotal</span>
                        <span>${invoice.subtotal_amount:.2f}</span>
                    </div>
                    <div class="total-row">
                        <span style="color: #64748b;">Tax</span>
                        <span>${invoice.tax_amount:.2f}</span>
                    </div>
                    <div class="total-row grand-total">
                        <span>Total</span>
                        <span style="color: #2563eb;">{invoice.currency} ${invoice.total_amount:.2f}</span>
                    </div>
                </div>

                <div class="footer">
                    <p>Thank you for choosing <strong>uask.ai</strong>. We appreciate your business!</p>
                    <p style="margin-top: 8px;">If you have any questions, please contact support@uask.ai</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

invoice_service = InvoiceService()
