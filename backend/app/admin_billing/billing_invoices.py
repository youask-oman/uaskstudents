"""
Admin Billing: Invoices API

Endpoints for viewing invoices.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User, Invoice, InvoiceLineItem
from app.admin_billing.deps import get_admin_user

router = APIRouter(prefix="/api/admin/billing/invoices", tags=["admin-billing-invoices"])


# Note: Invoice model may need to be created if it doesn't exist
# For now, using a placeholder structure

class InvoiceLineItemResponse(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float


class InvoiceResponse(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    invoice_number: str
    status: str  # DRAFT, ISSUED, PAID, VOIDED
    subtotal: float
    tax: float
    total: float
    currency: str
    issued_at: Optional[datetime]
    due_at: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime
    line_items: List[InvoiceLineItemResponse] = []

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("", response_model=PaginatedResponse)
async def list_invoices(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """
    List invoices with filters.
    """
    query = select(Invoice)
    count_query = select(func.count(Invoice.id))

    if user_id:
        query = query.where(Invoice.user_id == user_id)
        count_query = count_query.where(Invoice.user_id == user_id)
    if status:
        query = query.where(Invoice.status == status)
        count_query = count_query.where(Invoice.status == status)
    if start_date:
        query = query.where(Invoice.created_at >= start_date)
        count_query = count_query.where(Invoice.created_at >= start_date)
    if end_date:
        query = query.where(Invoice.created_at <= end_date)
        count_query = count_query.where(Invoice.created_at <= end_date)

    total = session.exec(count_query).one()
    invoices = session.exec(
        query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    ).all()

    user_ids = {inv.user_id for inv in invoices}
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(list(user_ids)))).all()}

    results = []
    for inv in invoices:
        user = users.get(inv.user_id)
        results.append(
            InvoiceResponse(
                id=inv.id,
                user_id=inv.user_id,
                user_email=user.email if user else None,
                invoice_number=inv.invoice_number,
                status=inv.status,
                subtotal=inv.subtotal_amount,
                tax=inv.tax_amount,
                total=inv.total_amount,
                currency=inv.currency,
                issued_at=inv.issued_at,
                due_at=inv.due_at,
                paid_at=inv.paid_at,
                created_at=inv.created_at,
                line_items=[],
            )
        )

    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """
    Get a specific invoice.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    user = session.get(User, invoice.user_id)
    line_items = session.exec(
        select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)
    ).all()

    items = [
        InvoiceLineItemResponse(
            description=item.description,
            quantity=int(item.quantity),
            unit_price=item.unit_price,
            total=item.amount,
        )
        for item in line_items
    ]

    return InvoiceResponse(
        id=invoice.id,
        user_id=invoice.user_id,
        user_email=user.email if user else None,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        subtotal=invoice.subtotal_amount,
        tax=invoice.tax_amount,
        total=invoice.total_amount,
        currency=invoice.currency,
        issued_at=invoice.issued_at,
        due_at=invoice.due_at,
        paid_at=invoice.paid_at,
        created_at=invoice.created_at,
        line_items=items,
    )


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """
    Download invoice as PDF.
    
    Note: This endpoint requires PDF generation to be implemented.
    """
    # TODO: Implement PDF generation
    raise HTTPException(status_code=501, detail="PDF export not yet implemented")
