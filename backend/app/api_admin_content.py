"""
Admin Content API

Read-only endpoints for canonical content inventory.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select, func
from sqlalchemy import or_

from app.database import get_session
from app.models import CanonicalProblem, User
from app.admin_billing.deps import get_admin_user


router = APIRouter(prefix="/api/admin/content", tags=["admin-content"])


class ConceptItem(BaseModel):
    id: int
    normalized_problem_hash: str
    subject: Optional[str]
    intent: str
    normalized_text: str
    created_at: datetime
    last_seen_at: datetime
    seen_count: int

    class Config:
        from_attributes = True


class ConceptResponse(BaseModel):
    items: List[ConceptItem]
    total: int
    limit: int
    offset: int
    subjects: List[str]


@router.get("/concepts", response_model=ConceptResponse)
def list_concepts(
    search: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = Query(default=25, le=200),
    offset: int = 0,
    admin: User = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    query = select(CanonicalProblem)
    count_query = select(func.count(CanonicalProblem.id))

    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            or_(
                CanonicalProblem.normalized_problem_hash.ilike(like),
                CanonicalProblem.normalized_text.ilike(like),
            )
        )
        count_query = count_query.where(
            or_(
                CanonicalProblem.normalized_problem_hash.ilike(like),
                CanonicalProblem.normalized_text.ilike(like),
            )
        )

    if subject:
        query = query.where(CanonicalProblem.subject == subject)
        count_query = count_query.where(CanonicalProblem.subject == subject)

    total = session.exec(count_query).one()
    items = session.exec(
        query.order_by(CanonicalProblem.last_seen_at.desc()).offset(offset).limit(limit)
    ).all()

    subject_rows = session.exec(
        select(CanonicalProblem.subject)
        .where(CanonicalProblem.subject != None)
        .distinct()
        .order_by(CanonicalProblem.subject.asc())
    ).all()
    subjects = [s for s in subject_rows if s]

    return ConceptResponse(
        items=[
            ConceptItem(
                id=item.id,
                normalized_problem_hash=item.normalized_problem_hash,
                subject=item.subject,
                intent=item.intent,
                normalized_text=item.normalized_text,
                created_at=item.created_at,
                last_seen_at=item.last_seen_at,
                seen_count=item.seen_count,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
        subjects=subjects,
    )
