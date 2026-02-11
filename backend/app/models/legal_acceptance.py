from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class LegalAcceptance(SQLModel, table=True):
    __tablename__ = "legal_acceptances"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    document_key: str = Field(index=True, max_length=100)
    document_version: str = Field(index=True, max_length=32)
    accepted_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    ip: Optional[str] = Field(default=None, max_length=128)
    user_agent: Optional[str] = Field(default=None, max_length=1024)
    locale: Optional[str] = Field(default=None, max_length=64)
    method: str = Field(default="in_app_modal", max_length=32)  # signup|login|checkout|in_app_modal

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "document_key",
            "document_version",
            name="uq_legal_acceptances_user_doc_version",
        ),
        Index("ix_legal_acceptances_user_doc_key_time", "user_id", "document_key", "accepted_at"),
        Index("ix_legal_acceptances_doc_key_version", "document_key", "document_version"),
    )
