
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, desc
from pydantic import BaseModel
from jose import JWTError, jwt

from app.database import get_session
from app.models import User, SystemConfigVersion, BillingLedger
from app.services.admin_config_service import admin_config_service
from app.services.pricing_service import pricing_service
from app.auth import SECRET_KEY, ALGORITHM

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# --- Models ---
class ConfigUpdate(BaseModel):
    value: Dict[str, Any]
    change_msg: str

class RevertRequest(BaseModel):
    version_id: int
    reason: str

class CalculatorRequest(BaseModel):
    action_type: str
    est_input: int
    est_output: int
    act_input: int
    act_output: int

class CalculatorResponse(BaseModel):
    estimate: Dict[str, Any]
    actual: Dict[str, Any]
    delta_credits: float

# --- Auth Dependencies (Self-Contained) ---
def get_current_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session)
) -> User:
    """Extract user from JWT token in Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_admin_user(user: User = Depends(get_current_user)):
    if user.role not in ["admin", "devops"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

def get_staff_user(user: User = Depends(get_current_user)):
    if user.role not in ["admin", "devops", "support", "finance"]:
        raise HTTPException(status_code=403, detail="Staff privileges required")
    return user

# --- Endpoints ---
# IMPORTANT: Specific routes must come BEFORE parameterized routes

@admin_router.post("/calculator", response_model=CalculatorResponse)
def calculate_transaction(
    req: CalculatorRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Simulate a transaction with ACTIVE config"""
    
    # Estimate
    est_cred, est_usd, est_tok, est_fee, _ = pricing_service.calculate_estimate_token_cost(
        req.action_type, req.est_input, req.est_output, session
    )
    
    # Actual
    act_cred, act_usd, act_tok, act_fee, _ = pricing_service.calculate_actual_token_cost(
        req.action_type, req.act_input, req.act_output, session
    )
    
    delta = act_cred - est_cred
    
    return CalculatorResponse(
        estimate={
            "credits": est_cred, "usd": est_usd, "tokens": est_tok, "fee": est_fee
        },
        actual={
            "credits": act_cred, "usd": act_usd, "tokens": act_tok, "fee": act_fee
        },
        delta_credits=delta
    )

@admin_router.get("/transactions")
def get_transactions(
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[int] = None,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Search transaction ledger"""
    query = select(BillingLedger).order_by(desc(BillingLedger.created_at))
    
    if user_id:
        query = query.where(BillingLedger.user_id == user_id)
    if action_type:
        query = query.where(BillingLedger.action_type == action_type)
    if status:
        query = query.where(BillingLedger.status == status)
        
    # Pagination
    offset = (page - 1) * page_size
    results = session.exec(query.offset(offset).limit(page_size)).all()
    
    return {"data": results, "page": page, "page_size": page_size}

@admin_router.post("/config/revert")
def revert_config(
    req: RevertRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Revert to a previous version (creates new version)"""
    return admin_config_service.revert_config(session, req.version_id, user.id, req.reason)

@admin_router.get("/config/history/{config_type}")
def get_config_history(
    config_type: str,
    limit: int = 50,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get version history"""
    return admin_config_service.get_history(session, config_type, limit)

# Parameterized routes LAST
@admin_router.get("/config/{config_type}")
def get_config(
    config_type: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get active config (pricing/tokens)"""
    return admin_config_service.get_active_config(session, config_type)

@admin_router.put("/config/{config_type}")
def update_config(
    config_type: str,
    update: ConfigUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Update config (creates new version)"""
    new_version = admin_config_service.update_config(
        session, config_type, update.value, user.id, update.change_msg
    )
    return new_version
