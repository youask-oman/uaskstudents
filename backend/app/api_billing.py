from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Session, select, desc
from typing import List, Optional
from jose import jwt, JWTError
from app.auth import SECRET_KEY, ALGORITHM
from app.database import get_session
from app.models import User, Invoice, InvoiceLineItem
from app.services.superadmin_policy import enforce_superadmin_role
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/billing", tags=["billing"])

# Auth Dependency (Reusing helper pattern)
def get_current_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session)
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    token = authorization.replace("Bearer ", "").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid Token")
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        enforce_superadmin_role(session, user)
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid Token")

@router.get("/invoices")
def list_my_invoices(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List authenticated user's invoices/receipts."""
    query = select(Invoice).where(Invoice.user_id == user.id).order_by(desc(Invoice.created_at))
    invoices = session.exec(query).all()
    return invoices

@router.get("/invoices/{invoice_id}")
def get_my_invoice_detail(
    invoice_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """View details for a specific invoice owned by the user."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.user_id != user.id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    lines = session.exec(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)).all()
    return {
        "invoice": invoice,
        "lines": lines
    }

@router.get("/invoices/{invoice_id}/html")
def get_my_invoice_html(
    invoice_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """View highly stylized HTML version of the invoice."""
    from app.services.invoice_service import invoice_service
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.user_id != user.id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    lines = session.exec(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)).all()
    
    html = invoice_service.render_invoice_html(
        invoice, 
        lines, 
        user.full_name or f"User #{user.id}", 
        user.email
    )
    return StreamingResponse(iter([html]), media_type="text/html")
