"""
Admin Billing: Credit Programs API

Endpoints for managing credit program definitions and viewing enrollments.
"""

from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlmodel import Session, select, func

from app.database import get_session
from app.models import User
from app.models.credit_program_models import (
    CreditProgramDefinition, CreditProgramEnrollment, CreditProgramGrantLog
)
from app.admin_billing.deps import get_admin_user, get_superadmin_user
from app.services.audit_log_service import audit_log_service

router = APIRouter(prefix="/api/admin/billing/programs", tags=["admin-billing-programs"])


# Request/Response Models
class ProgramResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    status: str
    monthly_gift_credits: Optional[float]
    gift_expiry_window_days: int
    entitlements: Optional[dict]
    effective_from: datetime
    effective_to: Optional[datetime]
    created_at: datetime
    enrollment_count: int = 0

    class Config:
        from_attributes = True


class CreateProgramRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    status: str = "active"
    monthly_gift_credits: Optional[float] = None
    gift_expiry_window_days: int = 30
    entitlements: Optional[dict] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    reason: str
    idempotency_key: Optional[str] = None


class UpdateProgramRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    monthly_gift_credits: Optional[float] = None
    gift_expiry_window_days: Optional[int] = None
    entitlements: Optional[dict] = None
    effective_to: Optional[datetime] = None
    reason: str
    idempotency_key: Optional[str] = None


class EnrollUserRequest(BaseModel):
    user_id: int
    program_id: int
    reason: str
    idempotency_key: Optional[str] = None


class UnenrollUserRequest(BaseModel):
    user_id: int
    program_id: int
    reason: str
    idempotency_key: Optional[str] = None


class DeleteProgramRequest(BaseModel):
    reason: str
    idempotency_key: Optional[str] = None





class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    program_id: int
    program_name: Optional[str] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    last_grant_month: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List
    total: int
    limit: int
    offset: int


@router.get("", response_model=PaginatedResponse)
async def list_programs(
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """List all credit program definitions."""
    query = select(CreditProgramDefinition)
    
    if status:
        query = query.where(CreditProgramDefinition.status == status)
    
    # Count total
    count_query = select(func.count(CreditProgramDefinition.id))
    if status:
        count_query = count_query.where(CreditProgramDefinition.status == status)
    total = session.exec(count_query).one()
    
    # Get programs
    programs = session.exec(
        query.order_by(CreditProgramDefinition.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    
    # Get enrollment counts
    results = []
    for program in programs:
        count = session.exec(
            select(func.count(CreditProgramEnrollment.id))
            .where(CreditProgramEnrollment.program_id == program.id)
            .where(CreditProgramEnrollment.status == "active")
        ).one()
        
        results.append(ProgramResponse(
            id=program.id,
            name=program.name,
            slug=program.slug,
            description=program.description,
            status=program.status,
            monthly_gift_credits=float(program.monthly_gift_credits) if program.monthly_gift_credits else None,
            gift_expiry_window_days=program.gift_expiry_window_days,
            entitlements=program.entitlements,
            effective_from=program.effective_from,
            effective_to=program.effective_to,
            created_at=program.created_at,
            enrollment_count=count,
        ))
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.post("", response_model=ProgramResponse)
async def create_program(
    body: CreateProgramRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Create a new credit program definition."""
    # Check slug uniqueness
    existing = session.exec(
        select(CreditProgramDefinition).where(CreditProgramDefinition.slug == body.slug)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Program with slug '{body.slug}' already exists")
    
    program = CreditProgramDefinition(
        name=body.name,
        slug=body.slug,
        description=body.description,
        status=body.status,
        monthly_gift_credits=Decimal(str(body.monthly_gift_credits)) if body.monthly_gift_credits else None,
        gift_expiry_window_days=body.gift_expiry_window_days,
        entitlements=body.entitlements,
        effective_from=body.effective_from or datetime.utcnow(),
        effective_to=body.effective_to,
        created_by=admin.id,
    )
    session.add(program)
    session.flush()
    
    # Audit log
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="CREDIT_PROGRAM",
        entity_id=str(program.id),
        before_json={"status": "new"},
        after_json={"name": program.name, "slug": program.slug},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()
    
    return ProgramResponse(
        id=program.id,
        name=program.name,
        slug=program.slug,
        description=program.description,
        status=program.status,
        monthly_gift_credits=float(program.monthly_gift_credits) if program.monthly_gift_credits else None,
        gift_expiry_window_days=program.gift_expiry_window_days,
        entitlements=program.entitlements,
        effective_from=program.effective_from,
        effective_to=program.effective_to,
        created_at=program.created_at,
        enrollment_count=0,
    )


@router.get("/{program_id}", response_model=ProgramResponse)
async def get_program(
    program_id: int,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Get a specific credit program."""
    program = session.get(CreditProgramDefinition, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    count = session.exec(
        select(func.count(CreditProgramEnrollment.id))
        .where(CreditProgramEnrollment.program_id == program.id)
        .where(CreditProgramEnrollment.status == "active")
    ).one()
    
    return ProgramResponse(
        id=program.id,
        name=program.name,
        slug=program.slug,
        description=program.description,
        status=program.status,
        monthly_gift_credits=float(program.monthly_gift_credits) if program.monthly_gift_credits else None,
        gift_expiry_window_days=program.gift_expiry_window_days,
        entitlements=program.entitlements,
        effective_from=program.effective_from,
        effective_to=program.effective_to,
        created_at=program.created_at,
        enrollment_count=count,
    )


@router.put("/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: int,
    body: UpdateProgramRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Update a credit program."""
    program = session.get(CreditProgramDefinition, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    before = {"name": program.name, "status": program.status}
    
    if body.name is not None:
        program.name = body.name
    if body.description is not None:
        program.description = body.description
    if body.status is not None:
        program.status = body.status
    if body.monthly_gift_credits is not None:
        program.monthly_gift_credits = Decimal(str(body.monthly_gift_credits))
    if body.gift_expiry_window_days is not None:
        program.gift_expiry_window_days = body.gift_expiry_window_days
    if body.entitlements is not None:
        program.entitlements = body.entitlements
    if body.effective_to is not None:
        program.effective_to = body.effective_to
    
    program.updated_at = datetime.utcnow()
    session.add(program)
    
    after = {"name": program.name, "status": program.status}
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="UPDATE",
        entity_type="CREDIT_PROGRAM",
        entity_id=str(program.id),
        before_json=before,
        after_json=after,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()
    
    return ProgramResponse(
        id=program.id,
        name=program.name,
        slug=program.slug,
        description=program.description,
        status=program.status,
        monthly_gift_credits=float(program.monthly_gift_credits) if program.monthly_gift_credits else None,
        gift_expiry_window_days=program.gift_expiry_window_days,
        entitlements=program.entitlements,
        effective_from=program.effective_from,
        effective_to=program.effective_to,
        created_at=program.created_at,
        enrollment_count=0,
    )


@router.get("/{program_id}/enrollments", response_model=PaginatedResponse)
async def list_program_enrollments(
    program_id: int,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """List enrollments for a specific program."""
    program = session.get(CreditProgramDefinition, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    query = select(CreditProgramEnrollment).where(CreditProgramEnrollment.program_id == program_id)
    count_query = select(func.count(CreditProgramEnrollment.id)).where(CreditProgramEnrollment.program_id == program_id)
    
    if status:
        query = query.where(CreditProgramEnrollment.status == status)
        count_query = count_query.where(CreditProgramEnrollment.status == status)
    
    total = session.exec(count_query).one()
    enrollments = session.exec(query.order_by(CreditProgramEnrollment.created_at.desc()).offset(offset).limit(limit)).all()
    
    # Get user emails
    user_ids = {e.user_id for e in enrollments}
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(list(user_ids)))).all()}
    
    results = []
    for e in enrollments:
        user = users.get(e.user_id)
        results.append(EnrollmentResponse(
            id=e.id,
            user_id=e.user_id,
            user_email=user.email if user else None,
            program_id=e.program_id,
            program_name=program.name,
            status=e.status,
            started_at=e.started_at,
            ended_at=e.ended_at,
            last_grant_month=e.last_grant_month,
            created_at=e.created_at,
        ))
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/enrollments/all", response_model=PaginatedResponse)
async def list_all_enrollments(
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """List all program enrollments across all programs."""
    query = select(CreditProgramEnrollment)
    count_query = select(func.count(CreditProgramEnrollment.id))
    
    if status:
        query = query.where(CreditProgramEnrollment.status == status)
        count_query = count_query.where(CreditProgramEnrollment.status == status)
    
    total = session.exec(count_query).one()
    enrollments = session.exec(query.order_by(CreditProgramEnrollment.created_at.desc()).offset(offset).limit(limit)).all()
    
    # Get user emails and program names
    user_ids = {e.user_id for e in enrollments}
    program_ids = {e.program_id for e in enrollments}
    
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(list(user_ids)))).all()}
    programs = {p.id: p for p in session.exec(select(CreditProgramDefinition).where(CreditProgramDefinition.id.in_(list(program_ids)))).all()}
    
    results = []
    for e in enrollments:
        user = users.get(e.user_id)
        program = programs.get(e.program_id)
        results.append(EnrollmentResponse(
            id=e.id,
            user_id=e.user_id,
            user_email=user.email if user else None,
            program_id=e.program_id,
            program_name=program.name if program else "Unknown",
            status=e.status,
            started_at=e.started_at,
            ended_at=e.ended_at,
            last_grant_month=e.last_grant_month,
            created_at=e.created_at,
        ))
    
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.delete("/{program_id}")
async def delete_program(
    program_id: int,
    body: DeleteProgramRequest,
    request: Request,
    admin: User = Depends(get_superadmin_user),
    session: Session = Depends(get_session),
):
    """Soft delete (archive) a credit program."""
    program = session.get(CreditProgramDefinition, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    before = {"status": program.status}
    program.status = "archived"
    program.updated_at = datetime.utcnow()
    session.add(program)
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="DELETE",
        entity_type="CREDIT_PROGRAM",
        entity_id=str(program.id),
        before_json=before,
        after_json={"status": "archived"},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()
    return {"status": "ok", "message": "Program archived"}


@router.post("/enrollments")
async def enroll_user(
    body: EnrollUserRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Enroll a user in a credit program."""
    # Check user
    user = session.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check program
    program = session.get(CreditProgramDefinition, body.program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    # Check existing active enrollment
    existing = session.exec(
        select(CreditProgramEnrollment)
        .where(CreditProgramEnrollment.user_id == body.user_id)
        .where(CreditProgramEnrollment.program_id == body.program_id)
        .where(CreditProgramEnrollment.status == "active")
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already enrolled in this program")
    
    enrollment = CreditProgramEnrollment(
        user_id=body.user_id,
        program_id=body.program_id,
        status="active",
        started_at=datetime.utcnow(),
    )
    session.add(enrollment)
    session.flush()
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="CREATE",
        entity_type="ENROLLMENT",
        entity_id=str(enrollment.id),
        before_json={"status": "none"},
        after_json={"user_id": body.user_id, "program_id": body.program_id, "status": "active"},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()
    return {"status": "ok", "enrollment_id": enrollment.id}


@router.post("/enrollments/unenroll")
async def unenroll_user(
    body: UnenrollUserRequest,
    request: Request,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Unenroll a user from a credit program."""
    enrollment = session.exec(
        select(CreditProgramEnrollment)
        .where(CreditProgramEnrollment.user_id == body.user_id)
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
        entity_type="ENROLLMENT",
        entity_id=str(enrollment.id),
        before_json=before,
        after_json={"status": "ended", "ended_at": str(enrollment.ended_at)},
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        request=request,
    )
    
    session.commit()
    return {"status": "ok", "message": "User unenrolled"}
