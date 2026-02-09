"""
Credit Program models for replacing subscription billing.

Credit Programs provide:
1. Monthly gift credits with configurable expiry
2. Feature entitlements (allow_ocr, allow_plot, etc.)
3. Purchase bonus rules (discount credits on packs)

This is Phase 3 of the Billing Redesign.
"""

from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON, Numeric, UniqueConstraint


class CreditProgramDefinition(SQLModel, table=True):
    """
    Defines a credit program (replaces subscription Plans).
    
    Programs define:
    - Monthly credit gifts
    - Feature entitlements
    - Purchase bonus rules
    """
    __tablename__ = "creditprogramdefinition"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    description: Optional[str] = None
    
    # Status
    status: str = Field(default="active", index=True)  # active, inactive, archived
    
    # Monthly Gift Config
    monthly_gift_credits: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(20, 10), default=0)
    )
    gift_expiry_window_days: int = Field(default=30)
    
    # Entitlements (feature flags)
    entitlements: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # Example: {"allow_ocr": true, "allow_plot": true, "allow_voice": false, "max_research_per_day": 10}
    
    # Purchase Bonus Rules
    purchase_bonus_rules: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # Example: {"100_credits": {"bonus_credits": 10, "bonus_expiry_days": 60}}
    
    # Validity Period
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    effective_to: Optional[datetime] = None  # Null = no end date
    
    # Pricing (for display, not enforceable billing)
    display_price_monthly_usd: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(20, 10))
    )
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    
    # Relationships
    enrollments: List["CreditProgramEnrollment"] = Relationship(back_populates="program")


class CreditProgramEnrollment(SQLModel, table=True):
    """
    Tracks a user's enrollment in a credit program.
    
    A user can only have one active enrollment per program.
    """
    __tablename__ = "creditprogramenrollment"
    __table_args__ = (
        UniqueConstraint("user_id", "program_id", name="uq_user_program_active"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    program_id: int = Field(foreign_key="creditprogramdefinition.id", index=True)
    
    # Status
    status: str = Field(default="active", index=True)  # active, paused, ended, cancelled
    
    # Dates
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    
    # Grant Tracking (for idempotency)
    last_grant_month: Optional[str] = Field(default=None, index=True)  # "2026-02" format
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    program: Optional[CreditProgramDefinition] = Relationship(back_populates="enrollments")


class CreditProgramGrantLog(SQLModel, table=True):
    """
    Log of credit grants issued by credit programs.
    
    Used for:
    - Auditing grant history
    - Idempotency (prevent duplicate grants)
    """
    __tablename__ = "creditprogramgrantlog"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "grant_month", name="uq_enrollment_grant_month"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    enrollment_id: int = Field(foreign_key="creditprogramenrollment.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    program_id: int = Field(foreign_key="creditprogramdefinition.id", index=True)
    
    # Grant Details
    grant_month: str = Field(index=True)  # "2026-02" format
    credits_granted: Decimal = Field(sa_column=Column(Numeric(20, 10), nullable=False))
    credit_lot_id: int = Field(foreign_key="creditlot.id", index=True)
    
    # Metadata
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationRecord(SQLModel, table=True):
    """
    Records from nightly reconciliation jobs.
    
    Tracks discrepancies between cached and computed balances.
    """
    __tablename__ = "reconciliationrecord"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # Balances
    cached_balance: Decimal = Field(sa_column=Column(Numeric(20, 10), nullable=False))
    computed_balance: Decimal = Field(sa_column=Column(Numeric(20, 10), nullable=False))
    delta: Decimal = Field(sa_column=Column(Numeric(20, 10), nullable=False))
    
    # Actions
    auto_fixed: bool = Field(default=False)
    job_run_id: str = Field(index=True)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
