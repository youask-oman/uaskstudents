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
from app.models import User
from app.admin_billing.deps import get_admin_user

router = APIRouter(prefix="/admin/billing/invoices", tags=["admin-billing-invoices"])


# Note: Invoice model may need to be created if it doesn't exist
# For now, using a placeholder structure

class InvoiceLineItem(BaseModel):
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
    line_items: List[InvoiceLineItem] = []

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
    
    Note: This endpoint requires an Invoice model to be implemented.
    Currently returns empty results as placeholder.
    """
    # TODO: Implement when Invoice model exists
    # For now, return empty list
    return PaginatedResponse(items=[], total=0, limit=limit, offset=offset)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """
    Get a specific invoice.
    
    Note: This endpoint requires an Invoice model to be implemented.
    """
    # TODO: Implement when Invoice model exists
    raise HTTPException(status_code=404, detail="Invoice not found")


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
