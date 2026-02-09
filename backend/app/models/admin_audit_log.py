"""
AdminAuditLog Model: Tracks all admin actions for auditing.

Every admin mutation (create, update, delete, execute) must create
an audit log entry with who/when/what/why.
"""

from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class AdminAuditLog(SQLModel, table=True):
    """
    Audit log for all admin actions.
    
    Every admin mutation must create an entry here before committing.
    """
    __tablename__ = "adminauditlog"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Who performed the action
    admin_user_id: int = Field(foreign_key="user.id", index=True)
    
    # What action was performed
    action: str = Field(index=True)  # CREATE, UPDATE, DELETE, EXECUTE, TOGGLE
    
    # What entity was affected
    entity_type: str = Field(index=True)  # FEATURE_FLAG, CREDIT_PROGRAM, CREDIT_LOT, etc.
    entity_id: Optional[str] = None  # ID of the affected entity (string for flexibility)
    
    # Before/after state for changes
    before_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    after_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Why the action was performed
    reason: Optional[str] = None
    
    # Request metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, index=True)
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
