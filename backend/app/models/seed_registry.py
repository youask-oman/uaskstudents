from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, func, String

class SeedRegistry(SQLModel, table=True):
    """
    Registry to track applied production seeds and their versions.
    Used to ensure idempotency and prevent redundant seed runs.
    """
    __tablename__ = "seed_registry"

    id: Optional[int] = Field(default=None, primary_key=True)
    seed_name: str = Field(unique=True, index=True)
    seed_version: int = Field(default=1)
    applied_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    git_sha: Optional[str] = None
    environment: str = Field(index=True) # DEV, STAGING, PROD
    row_count: Optional[int] = None
    checksum: Optional[str] = None
    notes: Optional[str] = None
