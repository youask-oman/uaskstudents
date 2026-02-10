"""
User Wallet API

Read-only wallet endpoints for authenticated users.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import (
    User,
    CreditLot,
    BillingLedger,
)
from app.models.credit_program_models import CreditProgramEnrollment, CreditProgramDefinition
from app.services.credit_program_service import credit_program_service
from app.api_billing import get_current_user
from app.admin_billing.billing_wallet import _build_wallet_summary, _month_start, _next_month_start

router = APIRouter(prefix="/wallet", tags=["wallet"])


class WalletSummaryResponse(BaseModel):
    user_id: int
    cached_balance: float
    computed_balance: float
    delta: float
    pending_holds: int
    pending_hold_credits: float
    expiring_soon_credits: float
    expiring_soon_lots: int
    entitlements: Dict[str, object]
    effective_tier: str
    active_programs: List[str]


class WalletLotResponse(BaseModel):
    id: int
    lot_type: Optional[str]
    credits_total: float
    credits_remaining: float
    status: str
    expires_at: Optional[datetime]
    created_at: datetime
    source_label: Optional[str] = None
    source_meta: Optional[dict] = None


class WalletLedgerEntryResponse(BaseModel):
    id: int
    event_type: str
    status: Optional[str]
    credits_delta: float
    credits_before: float
    credits_after: float
    reference: Optional[str]
    request_id: Optional[str]
    created_at: datetime


class WalletProgramEnrollmentResponse(BaseModel):
    id: int
    program_id: int
    program_name: Optional[str]
    program_slug: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    last_grant_month: Optional[str]
    next_grant_date: Optional[datetime]
    next_grant_status: Optional[str]
    monthly_gift_credits: Optional[float]
    gift_expiry_window_days: Optional[int]
    entitlements: Optional[dict]


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


def _effective_tier(entitlements: Dict[str, object], active_programs: List[str]) -> str:
    if entitlements.get("allow_research_tier"):
        return "RESEARCH"
    if active_programs:
        return "STANDARD"
    return "FREE"


def _lot_source_label(lot: CreditLot, program_map: Dict[int, CreditProgramDefinition]) -> str:
    lot_type = (lot.lot_type or "").upper()
    if lot.source == "DEV_FIXTURE" or lot_type == "DEV_FIXTURE":
        return f"DEV_FIXTURE:{lot.external_ref or lot.id}"
    if lot_type == "TOPUP":
        return f"TOPUP:{lot.source_payment_id or lot.external_ref or lot.id}"
    if lot_type in {"GIFT", "PROGRAM_GRANT", "SUBSCRIPTION_GRANT"}:
        program = program_map.get(lot.source_program_id) if lot.source_program_id else None
        label = program.slug if program else str(lot.source_program_id or "unknown")
        return f"PROGRAM:{label}"
    if lot_type == "PROMO":
        return "PROMO"
    if lot_type == "REFUND":
        return "REFUND"
    if lot_type == "ADJUSTMENT":
        return "ADMIN_ADJUSTMENT"
    return lot_type or "CREDITS"


def _ledger_delta(entry: BillingLedger) -> float:
    delta = Decimal(str(entry.delta_credits or 0))
    if delta != 0:
        return float(delta)
    charged = Decimal(str(entry.credits_charged or 0))
    if charged != 0:
        return float(-charged)
    actual = Decimal(str(entry.actual_credits or 0))
    if actual != 0:
        return float(-actual)
    return 0.0


@router.get("/summary", response_model=WalletSummaryResponse)
def get_wallet_summary(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    summary = _build_wallet_summary(session, user)
    entitlements = credit_program_service.get_user_entitlements(session, user.id)

    enrollments = session.exec(
        select(CreditProgramEnrollment)
        .where(CreditProgramEnrollment.user_id == user.id)
        .where(CreditProgramEnrollment.status == "active")
    ).all()
    program_ids = [e.program_id for e in enrollments]
    programs = {}
    if program_ids:
        programs = {
            p.id: p
            for p in session.exec(
                select(CreditProgramDefinition).where(CreditProgramDefinition.id.in_(program_ids))
            ).all()
        }

    active_programs = [programs[p].slug for p in program_ids if p in programs]
    tier = _effective_tier(entitlements, active_programs)

    return WalletSummaryResponse(
        user_id=user.id,
        cached_balance=summary.cached_balance,
        computed_balance=summary.computed_balance,
        delta=summary.delta,
        pending_holds=summary.pending_holds,
        pending_hold_credits=summary.pending_hold_credits,
        expiring_soon_credits=summary.expiring_soon_credits,
        expiring_soon_lots=summary.expiring_soon_lots,
        entitlements=entitlements,
        effective_tier=tier,
        active_programs=active_programs,
    )


@router.get("/lots", response_model=PaginatedResponse)
def list_wallet_lots(
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(CreditLot).where(CreditLot.user_id == user.id)
    count_query = select(func.count(CreditLot.id)).where(CreditLot.user_id == user.id)

    total = session.exec(count_query).one()
    lots = session.exec(
        query.order_by(CreditLot.created_at.desc()).offset(offset).limit(limit)
    ).all()

    program_ids = {lot.source_program_id for lot in lots if lot.source_program_id}
    program_map: Dict[int, CreditProgramDefinition] = {}
    if program_ids:
        program_map = {
            p.id: p
            for p in session.exec(
                select(CreditProgramDefinition).where(CreditProgramDefinition.id.in_(program_ids))
            ).all()
        }

    items = [
        WalletLotResponse(
            id=lot.id,
            lot_type=lot.lot_type,
            credits_total=float(lot.credits_total) if lot.credits_total is not None else 0.0,
            credits_remaining=float(lot.credits_remaining) if lot.credits_remaining is not None else 0.0,
            status=lot.status,
            expires_at=lot.expires_at,
            created_at=lot.created_at,
            source_label=_lot_source_label(lot, program_map),
            source_meta={"program_id": lot.source_program_id} if lot.source_program_id else None,
        )
        for lot in lots
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/ledger", response_model=PaginatedResponse)
def list_wallet_ledger(
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(BillingLedger).where(BillingLedger.user_id == user.id)
    count_query = select(func.count(BillingLedger.id)).where(BillingLedger.user_id == user.id)

    total = session.exec(count_query).one()
    entries = session.exec(
        query.order_by(BillingLedger.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = [
        WalletLedgerEntryResponse(
            id=entry.id,
            event_type=entry.action_type,
            status=entry.status,
            credits_delta=_ledger_delta(entry),
            credits_before=float(entry.credits_before or 0),
            credits_after=float(entry.credits_after or 0),
            reference=entry.request_id,
            request_id=entry.request_id,
            created_at=entry.created_at,
        )
        for entry in entries
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/programs", response_model=PaginatedResponse)
def list_wallet_programs(
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(CreditProgramEnrollment).where(CreditProgramEnrollment.user_id == user.id)
    count_query = select(func.count(CreditProgramEnrollment.id)).where(CreditProgramEnrollment.user_id == user.id)

    total = session.exec(count_query).one()
    enrollments = session.exec(
        query.order_by(CreditProgramEnrollment.created_at.desc()).offset(offset).limit(limit)
    ).all()

    program_ids = {e.program_id for e in enrollments}
    programs = {
        p.id: p
        for p in session.exec(
            select(CreditProgramDefinition).where(CreditProgramDefinition.id.in_(program_ids))
        ).all()
    } if program_ids else {}

    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")
    items: List[WalletProgramEnrollmentResponse] = []

    for e in enrollments:
        program = programs.get(e.program_id)
        next_grant_date = None
        next_grant_status = None
        if program and (program.monthly_gift_credits or 0) > 0 and e.status == "active":
            if e.last_grant_month == current_month:
                next_grant_date = _next_month_start(now)
                next_grant_status = "scheduled"
            else:
                next_grant_date = _month_start(now)
                next_grant_status = "due"

        items.append(
            WalletProgramEnrollmentResponse(
                id=e.id,
                program_id=e.program_id,
                program_name=program.name if program else None,
                program_slug=program.slug if program else None,
                status=e.status,
                started_at=e.started_at,
                ended_at=e.ended_at,
                last_grant_month=e.last_grant_month,
                next_grant_date=next_grant_date,
                next_grant_status=next_grant_status,
                monthly_gift_credits=float(program.monthly_gift_credits) if program and program.monthly_gift_credits else None,
                gift_expiry_window_days=program.gift_expiry_window_days if program else None,
                entitlements=program.entitlements if program else None,
            )
        )

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
