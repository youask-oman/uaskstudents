"""
Legacy Admin Billing Packs API (retired).

This endpoint previously mutated CreditPack and created a second source of truth
beside TopUpProduct. It is intentionally retired.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.admin_billing.deps import get_admin_user

router = APIRouter(prefix="/api/admin/billing/packs", tags=["admin-billing-packs"])


def _retired(_: User = Depends(get_admin_user)) -> None:
    raise HTTPException(
        status_code=410,
        detail="Retired endpoint. Use /api/admin/payments/pricing (TOPUP_PACK) or /api/v1/admin/credits/packs.",
    )


@router.get("")
def list_packs(_: None = Depends(_retired)):
    return None


@router.post("")
def create_pack(_: None = Depends(_retired)):
    return None


@router.put("/{pack_id}")
def update_pack(pack_id: int, _: None = Depends(_retired)):
    return {"pack_id": pack_id}


@router.delete("/{pack_id}")
def deactivate_pack(pack_id: int, _: None = Depends(_retired)):
    return {"pack_id": pack_id}

