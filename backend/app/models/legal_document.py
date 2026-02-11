from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Text, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class LegalDocument(SQLModel, table=True):
    __tablename__ = "legal_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, max_length=100)
    version: str = Field(index=True, max_length=32)
    status: str = Field(default="draft", index=True, max_length=20)  # draft|published
    content_md: str = Field(default="", sa_column=Column(Text, nullable=False))
    content_html: str = Field(default="", sa_column=Column(Text, nullable=False))
    effective_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    published_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_by: Optional[int] = Field(default=None, index=True)
    updated_by: Optional[int] = Field(default=None, index=True)
    checksum_sha256: str = Field(default="", index=True, max_length=64)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
        ),
    )

    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_legal_documents_key_version"),
        Index("ix_legal_documents_key_status", "key", "status"),
    )
