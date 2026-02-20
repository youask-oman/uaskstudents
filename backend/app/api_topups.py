
from fastapi import APIRouter, Depends, HTTPException, Body, Header
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from jose import jwt, JWTError
from app.auth import SECRET_KEY, ALGORITHM

from app.database import get_session
from app.services.top_up_service import top_up_service
from app.models import User, TopUpOrder
from app.services.superadmin_policy import enforce_superadmin_role

# Define Router
router = APIRouter(prefix="/topups", tags=["topups"])

# Helper Auth (Duplicate to avoid circular import if api.py is complex)
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
        from sqlmodel import select
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        enforce_superadmin_role(session, user)
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid Token")

# Define Router
router = APIRouter(prefix="/topups", tags=["topups"])

# Schemas
class TopUpProductRead(BaseModel):
    code: str
    name: str
    credits: int
    price_usd: float
    stripe_price_id: Optional[str] = None

class CheckoutRequest(BaseModel):
    product_code: str

class StripeCheckoutRequest(BaseModel):
    product_code: str
    success_url: str
    cancel_url: str

class CheckoutResponse(BaseModel):
    checkout_url: str
    payment_intent_id: str

class ConfirmRequest(BaseModel):
    product_code: str
    external_ref: str # PaymentIntent ID
    # Idempotency key logic? We use external_ref as unique key for now.

class StripeConfirmSessionRequest(BaseModel):
    session_id: str

class ConfirmResponse(BaseModel):
    status: str
    lot_id: Optional[int] = None
    credits_added: float
    new_balance: float

# Dependency workaround if get_current_user not easily importable
from app.models import User
# We will assume caller imports this router and provides dependencies, 
# OR we define a local dep if auth logic is simple "header -> user_id".
# For now, let's try to import from api.
# "from app.api import get_current_user" might cause circular import if api imports this.
# Check auth.py.

@router.get("/products", response_model=List[TopUpProductRead])
async def list_products(session: Session = Depends(get_session)):
    """List available top-up bundles."""
    products = top_up_service.list_products(session)
    from app.models import StripePriceMap
    mappings = session.exec(
        select(StripePriceMap).where(StripePriceMap.kind == "TOPUP")
    ).all()
    map_by_code = {m.internal_code: m.stripe_price_id for m in mappings}
    return [
        TopUpProductRead(
            code=p.code,
            name=p.name,
            credits=p.credits,
            price_usd=p.price_usd,
            stripe_price_id=map_by_code.get(p.code)
        ) for p in products
    ]

@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest, 
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Initiate checkout. Defaults to simulation for now unless stripe is explicitly requested."""
    try:
        # For simulation compatibility
        return {
            "checkout_url": f"/api/v1/topups/mock_confirm?code={req.product_code}",
            "payment_intent_id": f"pi_mock_{int(datetime.utcnow().timestamp())}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stripe/checkout")
async def create_stripe_checkout(
    req: StripeCheckoutRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Initiate Stripe checkout session."""
    try:
        return top_up_service.create_stripe_checkout_session(
            session, user.id, req.product_code, req.success_url, req.cancel_url
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/confirm")
async def confirm_topup(
    req: ConfirmRequest,
    user_id: int = Body(..., embed=True),
    session: Session = Depends(get_session)
):
    """
    Confirm payment and grant credits.
    Idempotent based on external_ref.
    """
    try:
        result = top_up_service.confirm_topup(
            session, 
            user_id, 
            req.product_code, 
            req.external_ref, 
            source="MANUAL_ADMIN" # Or 'STRIPE' later
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stripe/confirm-session")
async def confirm_stripe_session(
    req: StripeConfirmSessionRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Confirm a Stripe checkout session and fulfill the top-up if paid.
    This is a fallback for when webhooks are delayed or missed.
    """
    from app.services.stripe_service import stripe_service
    from app.services.stripe_webhook_processor import stripe_webhook_processor

    try:
        stripe_session = stripe_service.get_checkout_session(req.session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe session: {e}")

    metadata = stripe_session.get("metadata", {}) or {}
    order_id = metadata.get("topup_order_id")
    if not order_id:
        raise HTTPException(status_code=400, detail="Missing top-up order id in Stripe session metadata")

    order = session.get(TopUpOrder, int(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Top-up order not found")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="Order does not belong to current user")

    # If already fulfilled, return current state
    if order.status == "FULFILLED":
        return {
            "status": "fulfilled",
            "order_id": order.id,
            "payment_intent_id": order.stripe_payment_intent_id,
        }

    if stripe_session.get("payment_status") != "paid":
        return {
            "status": "pending",
            "order_id": order.id,
            "payment_status": stripe_session.get("payment_status"),
        }

    order.stripe_checkout_session_id = stripe_session.get("id")
    order.stripe_payment_intent_id = stripe_session.get("payment_intent")
    session.add(order)
    session.commit()

    stripe_webhook_processor.fulfill_topup(session, order)
    return {
        "status": "fulfilled",
        "order_id": order.id,
        "payment_intent_id": order.stripe_payment_intent_id,
    }
