"""
Admin Billing: User Wallet API

Endpoints for viewing and managing user credit wallets.
"""

from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import (
    User,
    CreditLot,
    CreditLotConsumption,
    CreditHold,
    BillingLedger,
)
from app.models.admin_audit_log import AdminAuditLog
from app.models.credit_program_models import (
    CreditProgramEnrollment,
    CreditProgramDefinition,
    CreditProgramGrantLog,
)
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service
from app.jobs.nightly_reconciliation import compute_user_balance
from app.services.refund_service import refund_service
from app.services.credit_program_service import credit_program_service

router = APIRouter(prefix="/api/admin/billing/users", tags=["admin-billing-wallet"])

EXPIRING_SOON_DAYS = 30
EPSILON = Decimal("0.0000001")


# Response Models
class WalletSummary(BaseModel):
    user_id: int
    user_email: str
    cached_balance: float
    computed_balance: float
    delta: float
    total_lots: int
    active_lots: int
    pending_holds: int
    pending_hold_credits: float
    expiring_soon_credits: float
    expiring_soon_lots: int


class CreditLotResponse(BaseModel):
    id: int
    lot_type: Optional[str]
    credits_total: float
    credits_remaining: float
    status: str
    source_program_id: Optional[int]
    source_payment_id: Optional[str]
    source_attempt_id: Optional[str]
    reason_code: Optional[str]
    purchased_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    source_label: Optional[str] = None
    source_meta: Optional[dict] = None

    class Config:
        from_attributes = True


class ConsumptionResponse(BaseModel):
    id: int
    credit_lot_id: int
    direction: str
    amount: float
    attempt_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GrantCreditsRequest(BaseModel):
    credits: float
    reason: str
    expires_days: int = 30
    lot_type: str = "ADJUSTMENT"
    idempotency_key: Optional[str] = None
    source_payment_id: Optional[str] = None
    source_attempt_id: Optional[str] = None


class RefundCreditsRequest(BaseModel):
    credits: float
    reason: str
    reason_code: str
    idempotency_key: Optional[str] = None
    source_payment_id: Optional[str] = None
    source_attempt_id: Optional[str] = None
    is_topup_reversal: bool = False


class ReconcileRequest(BaseModel):
    reason: str
    idempotency_key: Optional[str] = None


class EnrollmentRequest(BaseModel):
    program_id: int
    reason: str
    idempotency_key: Optional[str] = None


class GrantProgramRequest(BaseModel):
    program_id: int
    reason: str
    idempotency_key: Optional[str] = None
    grant_month: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


class LedgerEntryResponse(BaseModel):
    id: int
    event_type: str
    status: Optional[str]
    credits_delta: float
    credits_before: float
    credits_after: float
    reference: Optional[str]
    request_id: Optional[str]
    idempotency_key: Optional[str]
    created_at: datetime


class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    program_id: int
    program_name: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    last_grant_month: Optional[str]
    next_grant_date: Optional[datetime]
    next_grant_status: Optional[str]
    created_at: datetime


class WalletMutationResponse(BaseModel):
    success: bool
    wallet_summary: WalletSummary
    lot: Optional[CreditLotResponse] = None
    ledger_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    message: Optional[str] = None


def _month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


def _next_month_start(dt: datetime) -> datetime:
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return datetime(year, month, 1)


def _build_wallet_summary(session: Session, user: User) -> WalletSummary:
    computed = compute_user_balance(session, user.id)
    cached = Decimal(str(user.credits_balance or 0))

    total_lots = session.exec(
        select(func.count(CreditLot.id)).where(CreditLot.user_id == user.id)
    ).one()

    active_lots = session.exec(
        select(func.count(CreditLot.id))
        .where(CreditLot.user_id == user.id)
        .where(CreditLot.status == "ACTIVE")
        .where(CreditLot.credits_remaining > 0)
    ).one()

    holds = session.exec(
        select(CreditHold)
        .where(CreditHold.user_id == user.id)
        .where(CreditHold.status == "held")
    ).all()

    pending_hold_credits = sum(Decimal(str(h.reserved_credits)) for h in holds)

    # Expiring soon credits (30 days)
    now = datetime.utcnow()
    soon_cutoff = now + timedelta(days=EXPIRING_SOON_DAYS)
    expiring_lots = session.exec(
        select(CreditLot)
        .where(CreditLot.user_id == user.id)
        .where(CreditLot.status == "ACTIVE")
        .where(CreditLot.credits_remaining > 0)
        .where(CreditLot.expires_at != None)
    ).all()
    expiring_soon_credits = Decimal("0")
    expiring_soon_lots = 0
    for lot in expiring_lots:
        if lot.expires_at and now <= lot.expires_at <= soon_cutoff:
            expiring_soon_lots += 1
            expiring_soon_credits += Decimal(str(lot.credits_remaining))

    return WalletSummary(
        user_id=user.id,
        user_email=user.email,
        cached_balance=float(cached),
        computed_balance=float(computed),
        delta=float(cached - computed),
        total_lots=total_lots,
        active_lots=active_lots,
        pending_holds=len(holds),
        pending_hold_credits=float(pending_hold_credits),
        expiring_soon_credits=float(expiring_soon_credits),
        expiring_soon_lots=expiring_soon_lots,
    )


def _build_lot_source(
    lot: CreditLot,
    grant_log_id: Optional[int],
    audit_log: Optional[AdminAuditLog],
) -> Tuple[str, Dict[str, Optional[str]]]:
    meta: Dict[str, Optional[str]] = {}
    if lot.source == "DEV_FIXTURE" or (lot.lot_type or "").upper() == "DEV_FIXTURE":
        label = f"DEV_FIXTURE:{lot.external_ref or lot.id}"
        meta["fixture_ref"] = lot.external_ref or str(lot.id)
        return label, meta

    lot_type = (lot.lot_type or "").upper()

    if lot_type == "TOPUP":
        payment_ref = lot.source_payment_id or lot.external_ref or "unknown"
        label = f"PAYMENT:{payment_ref}"
        meta["payment_id"] = payment_ref
        return label, meta

    if lot_type in {"GIFT", "PROGRAM_GRANT", "SUBSCRIPTION_GRANT"}:
        prog_id = lot.source_program_id
        label = f"PROGRAM:{prog_id or 'unknown'} GRANT:{grant_log_id or 'n/a'}"
        meta["program_id"] = str(prog_id) if prog_id else None
        meta["grant_log_id"] = str(grant_log_id) if grant_log_id else None
        return label, meta

    if lot_type == "PROMO":
        campaign_ref = lot.external_ref or lot.source_payment_id or lot.source or "unknown"
        label = f"CAMPAIGN:{campaign_ref}"
        meta["campaign_id"] = campaign_ref
        return label, meta

    if lot_type == "ADJUSTMENT":
        admin_id = str(audit_log.admin_user_id) if audit_log else None
        audit_id = str(audit_log.id) if audit_log else None
        label = f"ADMIN:{admin_id or 'unknown'} AUDIT:{audit_id or 'n/a'}"
        meta["admin_user_id"] = admin_id
        meta["admin_audit_log_id"] = audit_id
        return label, meta

    if lot_type == "REFUND":
        ref = lot.source_attempt_id or lot.source_payment_id or lot.external_ref or "unknown"
        admin_id = str(audit_log.admin_user_id) if audit_log else None
        audit_id = str(audit_log.id) if audit_log else None
        label = f"REFUND:{ref} AUDIT:{audit_id or 'n/a'}"
        meta["refund_ref"] = ref
        meta["admin_user_id"] = admin_id
        meta["admin_audit_log_id"] = audit_id
        return label, meta

    label = lot.source or lot.lot_type or "unknown"
    return label, meta


def _lot_to_response(
    lot: CreditLot,
    grant_log_id: Optional[int] = None,
    audit_log: Optional[AdminAuditLog] = None,
) -> CreditLotResponse:
    source_label, source_meta = _build_lot_source(lot, grant_log_id, audit_log)
    return CreditLotResponse(
        id=lot.id,
        lot_type=lot.lot_type,
        credits_total=float(lot.credits_total) if lot.credits_total else 0,
        credits_remaining=float(lot.credits_remaining) if lot.credits_remaining else 0,
        status=lot.status,
        source_program_id=lot.source_program_id,
        source_payment_id=lot.source_payment_id,
        source_attempt_id=lot.source_attempt_id,
        reason_code=lot.reason_code,
        purchased_at=lot.purchased_at,
        expires_at=lot.expires_at,
        created_at=lot.created_at,
        source_label=source_label,
        source_meta=source_meta,
    )


@router.get("/{user_id}/wallet", response_model=WalletSummary)
async def get_wallet(
    user_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get wallet summary for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _build_wallet_summary(session, user)


@router.get("/{user_id}/wallet_summary", response_model=WalletSummary)
async def get_wallet_summary(
    user_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Alias for wallet summary (explicit endpoint)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _build_wallet_summary(session, user)


@router.get("/{user_id}/lots", response_model=PaginatedResponse)
async def get_lots(
    user_id: int,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get credit lots for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = select(CreditLot).where(CreditLot.user_id == user_id)
    count_query = select(func.count(CreditLot.id)).where(CreditLot.user_id == user_id)
    
    if status:
        query = query.where(CreditLot.status == status)
        count_query = count_query.where(CreditLot.status == status)
    
    total = session.exec(count_query).one()
    lots = session.exec(
        query.order_by(CreditLot.created_at.desc()).offset(offset).limit(limit)
    ).all()

    lot_ids = [lot.id for lot in lots]
    grant_logs = {}
    if lot_ids:
        grant_log_rows = session.exec(
            select(CreditProgramGrantLog)
            .where(CreditProgramGrantLog.credit_lot_id.in_(lot_ids))
        ).all()
        grant_logs = {row.credit_lot_id: row.id for row in grant_log_rows}

    audit_logs: Dict[str, AdminAuditLog] = {}
    audit_targets = [str(lot_id) for lot_id in lot_ids]
    if audit_targets:
        audit_rows = session.exec(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_id.in_(audit_targets))
            .where(AdminAuditLog.entity_type.in_(["CREDIT_LOT", "CREDIT_REFUND", "PROGRAM_GRANT"]))
            .order_by(AdminAuditLog.created_at.desc())
        ).all()
        for row in audit_rows:
            if row.entity_id not in audit_logs:
                audit_logs[row.entity_id] = row

    results = []
    for lot in lots:
        grant_log_id = grant_logs.get(lot.id)
        audit_log = audit_logs.get(str(lot.id))
        source_label, source_meta = _build_lot_source(lot, grant_log_id, audit_log)
        results.append(
            CreditLotResponse(
                id=lot.id,
                lot_type=lot.lot_type,
                credits_total=float(lot.credits_total) if lot.credits_total else 0,
                credits_remaining=float(lot.credits_remaining) if lot.credits_remaining else 0,
                status=lot.status,
                source_program_id=lot.source_program_id,
                source_payment_id=lot.source_payment_id,
                source_attempt_id=lot.source_attempt_id,
                reason_code=lot.reason_code,
                purchased_at=lot.purchased_at,
                expires_at=lot.expires_at,
                created_at=lot.created_at,
                source_label=source_label,
                source_meta=source_meta,
            )
        )

    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/{user_id}/consumptions", response_model=PaginatedResponse)
async def get_consumptions(
    user_id: int,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get credit consumptions for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    total = session.exec(
        select(func.count(CreditLotConsumption.id)).where(CreditLotConsumption.user_id == user_id)
    ).one()
    
    consumptions = session.exec(
        select(CreditLotConsumption)
        .where(CreditLotConsumption.user_id == user_id)
        .order_by(CreditLotConsumption.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    results = [
        ConsumptionResponse(
            id=c.id,
            credit_lot_id=c.credit_lot_id,
            direction=c.direction,
            amount=float(c.amount) if c.amount else 0,
            attempt_id=c.attempt_id,
            created_at=c.created_at,
        )
        for c in consumptions
    ]

    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/{user_id}/ledger", response_model=PaginatedResponse)
async def get_user_ledger(
    user_id: int,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get billing ledger entries for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total = session.exec(
        select(func.count(BillingLedger.id)).where(BillingLedger.user_id == user_id)
    ).one()

    entries = session.exec(
        select(BillingLedger)
        .where(BillingLedger.user_id == user_id)
        .order_by(BillingLedger.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    results: List[LedgerEntryResponse] = []
    for entry in entries:
        credits_before = Decimal(str(entry.credits_before or 0))
        credits_after = Decimal(str(entry.credits_after or 0))
        credits_delta = credits_after - credits_before
        reference = entry.request_id or entry.idempotency_key or entry.question_id or entry.source_asset_id
        results.append(
            LedgerEntryResponse(
                id=entry.id,
                event_type=entry.action_type,
                status=entry.status,
                credits_delta=float(credits_delta),
                credits_before=float(credits_before),
                credits_after=float(credits_after),
                reference=reference,
                request_id=entry.request_id,
                idempotency_key=entry.idempotency_key,
                created_at=entry.created_at,
            )
        )

    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/{user_id}/enrollments", response_model=PaginatedResponse)
async def get_user_enrollments(
    user_id: int,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get credit program enrollments for a user."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = select(CreditProgramEnrollment).where(CreditProgramEnrollment.user_id == user_id)
    count_query = select(func.count(CreditProgramEnrollment.id)).where(CreditProgramEnrollment.user_id == user_id)

    if status:
        query = query.where(CreditProgramEnrollment.status == status)
        count_query = count_query.where(CreditProgramEnrollment.status == status)

    total = session.exec(count_query).one()
    enrollments = session.exec(
        query.order_by(CreditProgramEnrollment.created_at.desc()).offset(offset).limit(limit)
    ).all()

    program_ids = {e.program_id for e in enrollments}
    programs = {}
    if program_ids:
        programs = {
            p.id: p
            for p in session.exec(
                select(CreditProgramDefinition).where(CreditProgramDefinition.id.in_(list(program_ids)))
            ).all()
        }

    results: List[EnrollmentResponse] = []
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")
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

        results.append(
            EnrollmentResponse(
                id=e.id,
                user_id=e.user_id,
                program_id=e.program_id,
                program_name=program.name if program else None,
                status=e.status,
                started_at=e.started_at,
                ended_at=e.ended_at,
                last_grant_month=e.last_grant_month,
                next_grant_date=next_grant_date,
                next_grant_status=next_grant_status,
                created_at=e.created_at,
            )
        )

    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.post("/{user_id}/lots", response_model=WalletMutationResponse)
async def grant_credits_legacy(
    user_id: int,
    body: GrantCreditsRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Legacy endpoint (kept for compatibility)."""
    return await grant_credits(user_id, body, request, admin, session)


@router.post("/{user_id}/grant", response_model=WalletMutationResponse)
async def grant_credits(
    user_id: int,
    body: GrantCreditsRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Grant adjustment credits to a user. Requires superadmin."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.credits <= 0:
        raise HTTPException(status_code=400, detail="credits must be > 0")

    if body.idempotency_key:
        existing_ledger = session.exec(
            select(BillingLedger).where(BillingLedger.idempotency_key == body.idempotency_key)
        ).first()
        if existing_ledger:
            summary = _build_wallet_summary(session, user)
            return WalletMutationResponse(
                success=True,
                wallet_summary=summary,
                ledger_id=existing_ledger.id,
                message="Idempotent replay (ledger already exists)",
            )

    computed_before = compute_user_balance(session, user_id)
    cached_before = Decimal(str(user.credits_balance or 0))

    lot = CreditLot(
        user_id=user_id,
        lot_type=body.lot_type,
        credits_total=Decimal(str(body.credits)),
        credits_remaining=Decimal(str(body.credits)),
        status="ACTIVE",
        source=f"ADMIN_{body.lot_type}",
        external_ref=body.idempotency_key,
        source_payment_id=body.source_payment_id,
        source_attempt_id=body.source_attempt_id,
        reason_code=body.reason,
        purchased_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=body.expires_days),
    )
    session.add(lot)
    session.flush()

    computed_after = compute_user_balance(session, user_id)

    ledger = BillingLedger(
        user_id=user_id,
        action_type=f"ADMIN_{body.lot_type}",
        request_id=body.source_attempt_id or body.source_payment_id,
        idempotency_key=body.idempotency_key,
        status="SETTLED",
        credits_charged=Decimal("0"),
        estimated_credits=Decimal("0"),
        actual_credits=Decimal("0"),
        delta_credits=Decimal(str(body.credits)),
        credits_before=Decimal(str(computed_before)),
        credits_after=Decimal(str(computed_after)),
    )
    session.add(ledger)
    session.flush()

    user.credits_balance = float(computed_after)
    session.add(user)

    audit_log = audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="CREDIT_LOT",
        entity_id=str(lot.id),
        before_json={
            "cached_balance": float(cached_before),
            "computed_balance": float(computed_before),
        },
        after_json={
            "credit_lot_id": lot.id,
            "ledger_id": ledger.id,
            "computed_balance": float(computed_after),
        },
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()

    summary = _build_wallet_summary(session, user)
    lot_response = _lot_to_response(lot, None, audit_log)
    return WalletMutationResponse(
        success=True,
        wallet_summary=summary,
        lot=lot_response,
        ledger_id=ledger.id,
    )


@router.post("/{user_id}/refund", response_model=WalletMutationResponse)
async def refund_credits(
    user_id: int,
    body: RefundCreditsRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Issue a refund credit lot. Requires superadmin."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.credits <= 0:
        raise HTTPException(status_code=400, detail="credits must be > 0")

    if body.idempotency_key:
        existing_ledger = session.exec(
            select(BillingLedger).where(BillingLedger.idempotency_key == body.idempotency_key)
        ).first()
        if existing_ledger:
            summary = _build_wallet_summary(session, user)
            return WalletMutationResponse(
                success=True,
                wallet_summary=summary,
                ledger_id=existing_ledger.id,
                message="Idempotent replay (ledger already exists)",
            )

    computed_before = compute_user_balance(session, user_id)
    cached_before = Decimal(str(user.credits_balance or 0))

    refund_id = body.idempotency_key or f"admin_refund_{user_id}_{int(datetime.utcnow().timestamp())}"
    lot = refund_service.create_refund(
        session=session,
        user_id=user_id,
        credits=Decimal(str(body.credits)),
        refund_id=refund_id,
        reason_code=body.reason_code,
        source_payment_id=body.source_payment_id,
        source_attempt_id=body.source_attempt_id,
        is_topup_reversal=body.is_topup_reversal,
    )
    session.flush()

    computed_after = compute_user_balance(session, user_id)

    ledger = BillingLedger(
        user_id=user_id,
        action_type="ADMIN_REFUND",
        request_id=body.source_attempt_id or body.source_payment_id,
        idempotency_key=body.idempotency_key,
        status="SETTLED",
        credits_charged=Decimal("0"),
        estimated_credits=Decimal("0"),
        actual_credits=Decimal("0"),
        delta_credits=Decimal(str(body.credits)),
        credits_before=Decimal(str(computed_before)),
        credits_after=Decimal(str(computed_after)),
    )
    session.add(ledger)
    session.flush()

    user.credits_balance = float(computed_after)
    session.add(user)

    audit_log = audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="CREDIT_REFUND",
        entity_id=str(lot.id),
        before_json={
            "cached_balance": float(cached_before),
            "computed_balance": float(computed_before),
        },
        after_json={
            "credit_lot_id": lot.id,
            "ledger_id": ledger.id,
            "computed_balance": float(computed_after),
        },
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()

    summary = _build_wallet_summary(session, user)
    lot_response = _lot_to_response(lot, None, audit_log)
    return WalletMutationResponse(
        success=True,
        wallet_summary=summary,
        lot=lot_response,
        ledger_id=ledger.id,
    )


@router.post("/{user_id}/enroll", response_model=WalletMutationResponse)
async def enroll_user_in_program(
    user_id: int,
    body: EnrollmentRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Enroll a user in a credit program."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    program = session.get(CreditProgramDefinition, body.program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    existing = session.exec(
        select(CreditProgramEnrollment)
        .where(CreditProgramEnrollment.user_id == user_id)
        .where(CreditProgramEnrollment.program_id == body.program_id)
        .where(CreditProgramEnrollment.status == "active")
    ).first()
    if existing:
        summary = _build_wallet_summary(session, user)
        return WalletMutationResponse(
            success=True,
            wallet_summary=summary,
            enrollment_id=existing.id,
            message="User already enrolled",
        )

    enrollment = credit_program_service.enroll_user(session, user_id, body.program_id)
    session.flush()

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="PROGRAM_ENROLLMENT",
        entity_id=str(enrollment.id),
        before_json={"status": "none"},
        after_json={"status": "active", "program_id": body.program_id},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()
    summary = _build_wallet_summary(session, user)
    return WalletMutationResponse(
        success=True,
        wallet_summary=summary,
        enrollment_id=enrollment.id,
    )


@router.post("/{user_id}/unenroll", response_model=WalletMutationResponse)
async def unenroll_user_from_program(
    user_id: int,
    body: EnrollmentRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Unenroll a user from a credit program."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    enrollment = session.exec(
        select(CreditProgramEnrollment)
        .where(CreditProgramEnrollment.user_id == user_id)
        .where(CreditProgramEnrollment.program_id == body.program_id)
        .where(CreditProgramEnrollment.status == "active")
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Active enrollment not found")

    before = {"status": enrollment.status}
    enrollment.status = "ended"
    enrollment.ended_at = datetime.utcnow()
    enrollment.updated_at = datetime.utcnow()
    session.add(enrollment)

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="UPDATE",
        entity_type="PROGRAM_ENROLLMENT",
        entity_id=str(enrollment.id),
        before_json=before,
        after_json={"status": "ended", "ended_at": str(enrollment.ended_at)},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()
    summary = _build_wallet_summary(session, user)
    return WalletMutationResponse(
        success=True,
        wallet_summary=summary,
        enrollment_id=enrollment.id,
    )


@router.post("/{user_id}/program-grant", response_model=WalletMutationResponse)
async def grant_program_now(
    user_id: int,
    body: GrantProgramRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Grant monthly program credits immediately. Requires superadmin."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.idempotency_key:
        existing_ledger = session.exec(
            select(BillingLedger).where(BillingLedger.idempotency_key == body.idempotency_key)
        ).first()
        if existing_ledger:
            summary = _build_wallet_summary(session, user)
            return WalletMutationResponse(
                success=True,
                wallet_summary=summary,
                ledger_id=existing_ledger.id,
                message="Idempotent replay (ledger already exists)",
            )

    program = session.get(CreditProgramDefinition, body.program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    grant_month = body.grant_month or datetime.utcnow().strftime("%Y-%m")

    computed_before = compute_user_balance(session, user_id)

    lot = credit_program_service.grant_monthly_credits(session, user_id, body.program_id, grant_month)
    if not lot:
        raise HTTPException(status_code=400, detail="No grant issued (not enrolled or program inactive)")

    session.flush()
    computed_after = compute_user_balance(session, user_id)

    request_id = f"program_grant_{lot.id}"
    idempotency_key = body.idempotency_key or request_id
    existing = session.exec(select(BillingLedger).where(BillingLedger.request_id == request_id)).first()
    if not existing:
        ledger = BillingLedger(
            user_id=user_id,
            action_type="PROGRAM_GRANT",
            request_id=request_id,
            idempotency_key=idempotency_key,
            status="SETTLED",
            credits_charged=Decimal("0"),
            estimated_credits=Decimal("0"),
            actual_credits=Decimal("0"),
            delta_credits=Decimal(str(lot.credits_total)),
            credits_before=Decimal(str(computed_before)),
            credits_after=Decimal(str(computed_after)),
        )
        session.add(ledger)
        session.flush()
        ledger_id = ledger.id
    else:
        ledger_id = existing.id

    user.credits_balance = float(computed_after)
    session.add(user)

    audit_log = audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="EXECUTE",
        entity_type="PROGRAM_GRANT",
        entity_id=str(lot.id),
        before_json={"computed_balance": float(computed_before)},
        after_json={"computed_balance": float(computed_after), "credit_lot_id": lot.id},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()

    summary = _build_wallet_summary(session, user)
    grant_log = session.exec(
        select(CreditProgramGrantLog).where(CreditProgramGrantLog.credit_lot_id == lot.id)
    ).first()
    lot_response = _lot_to_response(lot, grant_log.id if grant_log else None, audit_log)
    return WalletMutationResponse(
        success=True,
        wallet_summary=summary,
        lot=lot_response,
        ledger_id=ledger_id,
    )


@router.post("/{user_id}/reconcile", response_model=WalletMutationResponse)
async def force_reconcile(
    user_id: int,
    body: ReconcileRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Force reconcile a user's cached balance against computed balance."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.idempotency_key:
        existing = session.exec(
            select(AdminAuditLog).where(AdminAuditLog.idempotency_key == body.idempotency_key)
        ).first()
        if existing:
            summary = _build_wallet_summary(session, user)
            return WalletMutationResponse(
                success=True,
                wallet_summary=summary,
                message="Idempotent replay (audit already exists)",
            )

    cached = Decimal(str(user.credits_balance or 0))
    computed = compute_user_balance(session, user_id)

    user.credits_balance = float(computed)
    session.add(user)

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="EXECUTE",
        entity_type="RECONCILIATION",
        entity_id=str(user_id),
        before_json={"cached_balance": float(cached), "computed_balance": float(computed)},
        after_json={"cached_balance": float(computed), "computed_balance": float(computed)},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )

    session.commit()

    summary = _build_wallet_summary(session, user)
    return WalletMutationResponse(
        success=True,
        wallet_summary=summary,
        message=f"Reconciled cached balance from {float(cached)} to {float(computed)}",
    )
