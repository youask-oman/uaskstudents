from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    full_name: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(default="student") # student, admin
    
    # Profile fields
    academic_level: Optional[str] = None # High School, University, etc.
    preferred_language: str = Field(default="English")
    timezone: str = Field(default="GMT (UTC +0:00)")
    theme: str = Field(default="light") # light, dark, auto
    solving_mode: str = Field(default="Full Solution") # Full Solution, Hint Ladder, Socratic

    # Subscription & Quotas
    subscription_tier: str = Field(default="free") # free, pro, enterprise
    subscription_status: str = Field(default="active") # active, cancelled, expired, past_due
    subscription_expiry: Optional[datetime] = None
    
    quota_questions_total: int = Field(default=100)
    quota_scans_total: int = Field(default=50)
    
    # Token Tracking (1M per month limit)
    tokens_used_this_month: int = Field(default=0)
    last_token_reset: datetime = Field(default_factory=datetime.utcnow)

    # Profile completeness
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    
    # Verification
    is_verified: bool = Field(default=False)
    verification_token: Optional[str] = Field(default=None)

    # Location & Security
    ip_address: Optional[str] = None
    country: Optional[str] = None

    sessions: List["ChatSession"] = Relationship(back_populates="user")
    usage_logs: List["UsageLog"] = Relationship(back_populates="user")
    payments: List["Payment"] = Relationship(back_populates="user")    

class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    title: str = Field(default="New Session")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata for subject/topic classification
    subject: Optional[str] = None
    topic: Optional[str] = None
    
    # Save functionality - only saved sessions appear in history
    is_saved: bool = Field(default=False, index=True)

    user: Optional[User] = Relationship(back_populates="sessions")
    messages: List["ChatMessage"] = Relationship(back_populates="session")

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chatsession.id")
    role: str # user, assistant, system
    content: str
    
    # For multimedia (images, voice urls)
    media_url: Optional[str] = None 
    
    # Structure for rich responses (steps, verification, etc) - stored as JSON
    structured_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    session: ChatSession = Relationship(back_populates="messages")

class UsageLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    action_type: str # ocr_scan, solve_request, generating_image
    tokens_used: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="usage_logs")

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    amount: float
    currency: str = Field(default="USD")
    status: str = Field(default="pending") # pending, completed, failed
    
    transaction_id: str = Field(index=True) # Stripe ID or similar
    payment_method: str = Field(default="card") # card, paypal
    
    # Security / Auditing
    ip_address: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="payments")

class OCRJob(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True) # UUID
    user_id: int = Field(foreign_key="user.id", index=True)
    file_hash: str = Field(index=True)
    file_path: str # Path to stored file (S3/Local)
    
    status: str = Field(default="queued") # queued, processing, completed, failed
    result: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # markdown, confidence
    error: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    completed_at: Optional[datetime] = None
    
    p2t_version: Optional[str] = None

class PromoCode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    discount_percent: int = Field(default=0) # 0-100
    
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    is_active: bool = Field(default=True)
    max_uses: Optional[int] = None
    current_uses: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Qdrant Concept Card Schema (Conceptual, not in Postgres)
# Collection: "concepts"
# Payload: { title, latex_def, subject, difficulty, common_misconceptions: [] }
