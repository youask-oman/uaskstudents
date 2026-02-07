from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON, BigInteger, Enum as SAEnum, Text, UniqueConstraint, DateTime, func, Index
from uuid import uuid4
from enum import Enum

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

    # Location & Security (IP-detected, not profile)
    ip_address: Optional[str] = None
    country: Optional[str] = None  # IP-detected country (for security/analytics)
    
    # Student Location Profile (user-selected, required for curriculum context)
    profile_country: Optional[str] = None  # 'USA' or 'Canada' - required after onboarding
    profile_province_state: Optional[str] = None  # State (USA) or Province/Territory (Canada)
    grade_level: Optional[str] = None  # Grade 4-12, College, or University
    school_id: Optional[int] = Field(default=None, foreign_key="school.id", index=True)  # Optional school
    
    # Advanced Profile
    is_public: bool = Field(default=False)
    learning_interests: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Session Security
    session_token: Optional[str] = None
    last_ip: Optional[str] = None
    
    # WhatsApp Integration
    whatsapp_number: Optional[str] = Field(default=None, index=True)  # Verified WhatsApp number
    whatsapp_secret: Optional[str] = None  # Unique code for verification
    whatsapp_enabled: bool = Field(default=True)  # Can be disabled by user or admin

    # Subscription Relationship
    subscription: Optional["Subscription"] = Relationship(back_populates="user")
    
    # Relationships
    school: Optional["School"] = Relationship(back_populates="students")
    sessions: List["ChatSession"] = Relationship(back_populates="user")
    usage_logs: List["UsageLog"] = Relationship(back_populates="user")
    payments: List["Payment"] = Relationship(back_populates="user")
    voice_sessions: List["VoiceSession"] = Relationship(back_populates="user")
    admin_notes: List["AdminNote"] = Relationship(back_populates="user")
    solve_sessions: List["SolveSession"] = Relationship(back_populates="user")


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

    # Tier & Goal Tracking
    learning_mode: Optional[str] = Field(default="solve") # solve, study
    requested_mode: Optional[str] = Field(default="minimal") # minimal, detailed
    solve_tier: Optional[str] = Field(default="free") # free, standard

    user: Optional[User] = Relationship(back_populates="sessions")
    messages: List["ChatMessage"] = Relationship(back_populates="session")

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chatsession.id")
    role: str # user, assistant, system
    content: str
    
    # Structured Data & Telemetry
    structured_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    telemetry: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Metadata for tracking
    model_used: Optional[str] = None
    tokens_used: int = Field(default=0)
    
    # Content Metadata (Requested by user)
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    difficulty: Optional[str] = None
    topics: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    session: ChatSession = Relationship(back_populates="messages")

class UsageLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    action_type: str # ocr_scan, solve_request, generating_image
    tokens_used: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="usage_logs")

class SolveSession(SQLModel, table=True):
    """Immutable snapshot of a solved problem for follow-up chat context."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    problem_text: str
    topic: str
    solution_steps_text: str # plain text steps or structured steps rendered to text
    final_answer_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: "User" = Relationship(back_populates="solve_sessions")
    followups: List["FollowupChatTurn"] = Relationship(back_populates="solve_session")
    usage_records: List["LlmUsageLedger"] = Relationship(back_populates="solve_session")

class FollowupChatTurn(SQLModel, table=True):
    """Each follow-up request/response stored as an auditable record."""
    id: Optional[int] = Field(default=None, primary_key=True)
    solve_session_id: int = Field(foreign_key="solvesession.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    turn_index: int # 1..10
    user_message: str
    assistant_message: str
    refused_out_of_scope: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    solve_session: SolveSession = Relationship(back_populates="followups")
    usage_record: Optional["LlmUsageLedger"] = Relationship(back_populates="followup_turn")

class LlmUsageLedger(SQLModel, table=True):
    """Log token usage per follow-up call."""
    id: Optional[int] = Field(default=None, primary_key=True)
    solve_session_id: int = Field(foreign_key="solvesession.id", index=True)
    followup_turn_id: Optional[int] = Field(default=None, foreign_key="followupchatturn.id", index=True, unique=True)
    
    provider: str # "openai"
    model: str
    request_id: Optional[str] = None # provider request id if available
    
    system_prompt_tokens: int
    input_tokens: int # total input tokens
    output_tokens: int
    total_tokens: int
    latency_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    solve_session: SolveSession = Relationship(back_populates="usage_records")
    followup_turn: Optional[FollowupChatTurn] = Relationship(back_populates="usage_record")


# --- Subscription System Models ---

class Plan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str  # Free, Student Standard, Family Standard
    slug: str = Field(unique=True, index=True)
    credits_per_month: int
    price_monthly_cents: int
    price_yearly_cents: int
    seats: int = Field(default=1)
    
    # Configuration JSONs
    features: dict = Field(default_factory=dict, sa_column=Column(JSON))
    multipliers: dict = Field(default_factory=dict, sa_column=Column(JSON))
    
    is_active: bool = Field(default=True)
    version: int = Field(default=1) # Optimistic locking
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True) # One sub per user
    plan_id: int = Field(foreign_key="plan.id")
    
    status: str = Field(default="active") # active, past_due, cancelled
    current_period_start: datetime = Field(default_factory=datetime.utcnow)
    current_period_end: datetime
    
    # Balance & Usage
    credits_balance: float = Field(default=0.0)
    credits_used_this_period: float = Field(default=0.0)
    
    # Feature Usage Counters (reset monthly)
    feature_usage: dict = Field(default_factory=dict, sa_column=Column(JSON))
    
    auto_renew: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="subscription")
    plan: Plan = Relationship()
    ledger_entries: List["UsageLedger"] = Relationship(back_populates="subscription")
    periods: List["SubscriptionPeriod"] = Relationship(back_populates="subscription")

class SubscriptionPeriod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    
    period_start: datetime = Field(index=True)
    period_end: datetime = Field(index=True)
    status: str = Field(default="OPEN", index=True) # OPEN, CLOSED
    
    granted_credits: int
    grant_lot_id: Optional[int] = Field(default=None, foreign_key="creditlot.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    subscription: Subscription = Relationship(back_populates="periods")
    # Enforce uniqueness of period per subscription
    __table_args__ = (UniqueConstraint("subscription_id", "period_start", name="uq_sub_period_start"),)

class UsageLedger(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    
    transaction_type: str # DEBIT, CREDIT, REFUND, RESET
    amount: float
    balance_after: float
    
    reference_id: Optional[str] = Field(default=None, index=True) # question_id, payment_id
    meta: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # reason, details
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    subscription: Subscription = Relationship(back_populates="ledger_entries")


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id", index=True)
    
    amount: float
    currency: str = Field(default="USD")
    status: str = Field(default="pending", index=True) # REQUIRES_ACTION, PROCESSING, SUCCEEDED, FAILED, CANCELED, REFUNDED
    
    transaction_id: str = Field(index=True) # Legacy alias for external_id
    payment_method: str = Field(default="card") # card, paypal, stripe
    
    # Phase 4 Additions
    provider: str = Field(default="STRIPE", index=True) # STRIPE, MANUAL, DEV
    external_id: Optional[str] = Field(default=None, index=True) # Stripe PaymentIntent ID or Invoice ID
    external_type: Optional[str] = Field(default=None, index=True) # PAYMENT_INTENT, INVOICE, CHECKOUT_SESSION, SUBSCRIPTION
    idempotency_key: Optional[str] = Field(default=None, index=True)
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Security / Auditing
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    user: "User" = Relationship(back_populates="payments")

    __table_args__ = (
        UniqueConstraint("provider", "external_type", "external_id", name="uq_payment_external"),
    )

# --- OCR Subsystem Tables ---

class Upload(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    storage_url: str
    file_hash: str = Field(index=True)
    content_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship()
    crops: List["Crop"] = Relationship(back_populates="upload")

class Crop(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    upload_id: int = Field(foreign_key="upload.id", index=True)
    crop_rect: dict = Field(default_factory=dict, sa_column=Column(JSON)) # {x, y, w, h} normalized
    rotation: int = Field(default=0) # 0, 90, 180, 270
    margin_pct: int = Field(default=0)
    crop_image_hash: str = Field(index=True, unique=True)
    cropped_storage_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    upload: Upload = Relationship(back_populates="crops")
    jobs: List["OCRJob"] = Relationship(back_populates="crop")
    artifacts: List["OCRArtifact"] = Relationship(back_populates="crop")

class OCRJob(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True) # UUID
    user_id: int = Field(foreign_key="user.id", index=True)
    crop_id: int = Field(foreign_key="crop.id", index=True)
    requested_engine: str = Field(default="auto") # auto, local, vlm
    status: str = Field(default="queued") # queued, processing, completed, failed
    priority: str = Field(default="normal") # normal, high
    attempts: int = Field(default=0)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    user: User = Relationship()
    crop: "Crop" = Relationship(back_populates="jobs")
    artifacts: List["OCRArtifact"] = Relationship(back_populates="job")

class OCRArtifact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    crop_id: int = Field(foreign_key="crop.id", index=True)
    job_id: str = Field(foreign_key="ocrjob.id", index=True)
    engine_used: str = Field(index=True) # local, vlm
    doc_type: Optional[str] = None # quiz, worksheet, exam, mixed
    page_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    instructions: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    
    raw_markdown: str
    plain_text: str
    latex_blocks: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    confidence_score: float = 0.0
    
    pix2text_version: Optional[str] = None
    provider: Optional[str] = None
    provider_model: Optional[str] = None
    
    usage_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # {input_tokens, output_tokens, cost}
    blocks: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON)) # [{type: 'text'|'math'|'figure', content: '...'}]
    derived_json: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # ProblemJSON structure
    coverage_checklist: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    timings: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # preprocess_ms, ocr_ms, etc.
    warnings: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    crop: Crop = Relationship(back_populates="artifacts")
    job: OCRJob = Relationship(back_populates="artifacts")
    questions: List["OCRQuestion"] = Relationship(back_populates="artifact")
    figures: List["OCRFigure"] = Relationship(back_populates="artifact")

class OCRQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="ocrartifact.id", index=True)
    external_id: str # e.g. "1" from LLM
    prompt: str
    has_figure: bool = Field(default=False)
    math_expressions: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    artifact: OCRArtifact = Relationship(back_populates="questions")
    choices: List["OCRChoice"] = Relationship(back_populates="question")

class OCRChoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="ocrquestion.id", index=True)
    label: str # A, B, C
    text: str
    
    question: OCRQuestion = Relationship(back_populates="choices")

class OCRFigure(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="ocrartifact.id", index=True)
    external_id: str # e.g. "fig1"
    type: str # graph, diagram, table, image
    description: Optional[str] = None
    data_json: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # axes, points, etc.
    
    artifact: OCRArtifact = Relationship(back_populates="figures")

class OCRConfirmation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="ocrartifact.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    confirmed_markdown: str
    confirmed_text: str
    confirmed_latex_blocks: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    
    normalized_problem_hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CanonicalProblem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    normalized_problem_hash: str = Field(index=True, unique=True)
    
    # Core Canonical Fields
    normalized_text: str # Original normalized text (backward compat)
    intent: str = Field(default="unknown", index=True)
    canonical_math_object: str = Field(default="")
    assumptions_hash: Optional[str] = None
    
    # Versioning (Part of Key)
    prompt_version: Optional[str] = None
    solver_version: Optional[str] = None
    schema_version: Optional[str] = None
    
    # Metadata
    normalized_latex_blocks: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    subject: Optional[str] = None
    language: str = Field(default="en")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    seen_count: int = Field(default=1)

class CanonicalSolution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="canonicalproblem.id", index=True)
    solution_json: dict = Field(sa_column=Column(JSON))
    verification_status: str = Field(default="pending") # pass, partial, fail
    verification_report: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Redundant version info for easy access
    prompt_version: Optional[str] = None
    model_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_served_at: datetime = Field(default_factory=datetime.utcnow)
    served_count: int = Field(default=1)

class UserSavedSolution(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    solution_id: int = Field(foreign_key="canonicalsolution.id", primary_key=True)
    saved_at: datetime = Field(default_factory=datetime.utcnow)
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    notes: Optional[str] = None

class OCRAuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(foreign_key="user.id", index=True)
    upload_id: Optional[int] = Field(foreign_key="upload.id")
    crop_id: Optional[int] = Field(foreign_key="crop.id")
    job_id: Optional[str] = Field(foreign_key="ocrjob.id")
    artifact_id: Optional[int] = Field(foreign_key="ocrartifact.id")
    
    routing_engine_chosen: str = Field(index=True) # local, vlm
    vlm_type_chosen: Optional[str] = None
    reasons: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    
    confidence_score_before: Optional[float] = None
    cost_estimate_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    
    provider: Optional[str] = None
    provider_model: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

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

# --- Voice Mode Models ---

class VoiceSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    language: str = Field(default="en")
    preferred_stt: str = Field(default="openai")
    status: str = Field(default="created", index=True) # created, uploaded, processing, done, failed
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    user: User = Relationship(back_populates="voice_sessions")
    audios: List["VoiceAudio"] = Relationship(back_populates="session")
    jobs: List["VoiceJob"] = Relationship(back_populates="session")

class VoiceAudio(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    voice_session_id: int = Field(foreign_key="voicesession.id")
    storage_url: str
    audio_hash: str = Field(index=True)
    duration_ms: Optional[int] = None
    codec: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    session: VoiceSession = Relationship(back_populates="audios")
    jobs: List["VoiceJob"] = Relationship(back_populates="audio")

class VoiceJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    voice_session_id: int = Field(foreign_key="voicesession.id")
    audio_id: int = Field(foreign_key="voiceaudio.id")
    status: str = Field(default="queued") # queued, running, done, failed
    attempts: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    session: VoiceSession = Relationship(back_populates="jobs")
    audio: VoiceAudio = Relationship(back_populates="jobs")
    artifacts: List["VoiceArtifact"] = Relationship(back_populates="job")

class VoiceArtifact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="voicejob.id")
    transcript_raw: str
    transcript_confidence: Optional[float] = None
    normalized_math_text: str
    ambiguity_flags: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    clarifier_question: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    stt_provider: str
    stt_model: str
    timings_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    job: VoiceJob = Relationship(back_populates="artifacts")
    confirmations: List["VoiceConfirmation"] = Relationship(back_populates="artifact")

class VoiceConfirmation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="voiceartifact.id")
    user_id: int = Field(foreign_key="user.id")
    confirmed_transcript_text: str
    confirmed_normalized_text: str
    problem_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    normalized_problem_hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    artifact: VoiceArtifact = Relationship(back_populates="confirmations")
    user: User = Relationship()

class AdminNote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    admin_name: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="admin_notes")

# --- School Directory Models ---

class School(SQLModel, table=True):
    """
    Unified schools directory across Canada + United States sources.
    """
    __table_args__ = (
        UniqueConstraint("country", "source", "external_id", name="uq_school_country_source_external_id"),
        Index("idx_school_country_province_city", "country", "province_state", "city"),
        Index("idx_school_external_id", "external_id"),
        Index("idx_school_school_key", "school_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Location
    country: str = Field(index=True)  # 'US' or 'CA'
    province_state: str = Field(index=True)  # State for US, Province/Territory for CA
    
    # Compatibility fields
    district: Optional[str] = None
    city: Optional[str] = None
    
    # School info
    school_name: str = Field(index=True)
    school_type: Optional[str] = None  # public, private, charter, etc.
    grade_range: Optional[str] = None

    # Source / identifiers
    external_id: Optional[str] = Field(default=None)  # Text: NCES ID (US) or Source_ID (CA)
    source: str = Field(index=True)  # e.g. nces_csv, canada_csv
    school_key: str = Field(index=True)
    
    # Unified CA/US fields
    website_url: Optional[str] = None
    address_line1: Optional[str] = None
    full_address: Optional[str] = None
    street_no: Optional[str] = None
    street_name: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    csdname: Optional[str] = None
    csduid: Optional[str] = None
    normalized_name: Optional[str] = None
    normalized_address: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )
    
    # Relationships
    students: List["User"] = Relationship(back_populates="school")


class SchoolImportRun(SQLModel, table=True):
    """
    Audit table for school CSV import runs.
    Tracks each import operation for debugging and monitoring.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    
    # Status
    status: str = Field(default="running", index=True)  # running, completed, failed
    
    # Totals
    us_rows_processed: int = Field(default=0)
    ca_rows_processed: int = Field(default=0)
    inserted_count: int = Field(default=0)
    updated_count: int = Field(default=0)
    skipped_count: int = Field(default=0)
    error_count: int = Field(default=0)
    
    # Error details (stored as JSON)
    errors_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Options used
    reset_before_import: bool = Field(default=False)


class SystemConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SystemConfigVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    config_type: str = Field(index=True) # pricing, tokens
    version: int = Field(index=True)
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))
    diff_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    check_sum: str
    created_by: int = Field(foreign_key="user.id", index=True) # User ID of admin
    change_msg: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Prompt & Schema Registry (DB-backed) ---

class PromptTierEnum(str, Enum):
    FREE = "FREE"
    STANDARD = "STANDARD"
    RESEARCH = "RESEARCH"

class PromptModeEnum(str, Enum):
    SOLVE = "SOLVE"
    VERIFY = "VERIFY"
    PLOT_TRIGGER = "PLOT_TRIGGER"
    PLOT_SPEC = "PLOT_SPEC"
    OCR_EXTRACT = "OCR_EXTRACT"

class TrimStrategyEnum(str, Enum):
    NONE = "none"
    TRIM_CONTEXT_FIRST = "trim_context_first"
    TRIM_USER_FIRST = "trim_user_first"
    SUMMARIZE_CONTEXT = "summarize_context"
    TRIM_EVERYTHING_EXCEPT_PLOT_PLAN = "trim_everything_except_plot_plan"

class PromptRoleEnum(str, Enum):
    SYSTEM = "SYSTEM"
    DEVELOPER = "DEVELOPER"
    USER = "USER"
    INTERNAL = "INTERNAL"

class PromptTemplateEntry(SQLModel, table=True):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("prompt_id", "version"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    prompt_id: str = Field(index=True)
    tier: Optional[PromptTierEnum] = Field(default=None, sa_column=Column(SAEnum(PromptTierEnum)))
    mode: PromptModeEnum = Field(sa_column=Column(SAEnum(PromptModeEnum)))
    role: PromptRoleEnum = Field(sa_column=Column(SAEnum(PromptRoleEnum)))
    content: str = Field(sa_column=Column(Text))
    version: int = Field(default=1, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None

class JsonSchemaEntry(SQLModel, table=True):
    __tablename__ = "json_schemas"
    __table_args__ = (UniqueConstraint("schema_id", "version"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    schema_id: str = Field(index=True)
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    version: int = Field(default=1, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None

class PromptBinding(SQLModel, table=True):
    __tablename__ = "prompt_bindings"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tier: PromptTierEnum = Field(sa_column=Column(SAEnum(PromptTierEnum)))
    mode: PromptModeEnum = Field(sa_column=Column(SAEnum(PromptModeEnum)))
    global_system_prompt_id: str = Field(index=True)
    developer_prompt_id: str = Field(index=True)
    output_schema_id: str = Field(index=True)

    # Dynamic Token Configuration (Overrides SystemConfig Defaults if set)
    max_output_tokens: Optional[int] = Field(default=None)
    max_input_tokens: Optional[int] = Field(default=None)
    system_schema_budget_tokens: Optional[int] = Field(default=None)
    context_budget_tokens: Optional[int] = Field(default=None)
    json_retry_max_output_tokens: Optional[int] = Field(default=None)
    json_retry_max_attempts: Optional[int] = Field(default=None)
    timeout_ms: Optional[int] = Field(default=None)
    temperature: Optional[float] = Field(default=None)
    top_p: Optional[float] = Field(default=None)

    # Plot-only caps
    plot_points_cap: Optional[int] = Field(default=None)
    plot_traces_cap: Optional[int] = Field(default=None)
    plot_annotations_cap: Optional[int] = Field(default=None)

    # Trimming
    trim_strategy: Optional[TrimStrategyEnum] = Field(default=None, sa_column=Column(SAEnum(TrimStrategyEnum)))

    max_steps: Optional[int] = Field(default=None)
    retry_cap_tokens: Optional[int] = Field(default=None) # Legacy field, keeping for compatibility

    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None

class UserQuotaOverride(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_limit: Optional[int] = None
    ocr_concurrency: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SystemErrorEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    severity: str = "ERROR" # INFO, WARNING, ERROR, CRITICAL
    error_code: Optional[str] = Field(default=None, index=True) # e.g. payment_webhook_failed
    component: str = Field(index=True) # e.g. "OCR-ENGINE", "API-ROUTER"
    message: str
    stack_trace: Optional[str] = None
    
    # Traceability
    trace_id: Optional[str] = Field(default=None, index=True)
    request_id: Optional[str] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    
    # Fingerprinting for deduplication
    fingerprint: Optional[str] = Field(default=None, index=True)
    occurrence_count: int = Field(default=1)
    
    # Metadata
    context_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    is_resolved: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)


class QuestionIdentityCache(SQLModel, table=True):
    """
    OCR-proof cache for Snap & Solve questions.
    Prevents duplicate OpenAI calls for the same question.
    """
    __tablename__ = "question_identity_cache"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    question_key: str = Field(unique=True, index=True)  # SHA256 of fingerprint
    
    # Fingerprint components (for debugging/analysis)
    normalized_stem: str = Field(default="")
    normalized_options: Optional[str] = None  # JSON array of normalized options
    question_type: str = Field(default="unknown")
    
    # Cached result
    solution_json: dict = Field(sa_column=Column(JSON))
    
    # Debug & analytics
    original_variants: List[str] = Field(default=[], sa_column=Column(JSON))  # OCR texts that hit this key
    hit_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)


class OcrCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(unique=True, index=True)
    extracted_text: str
    extracted_markdown: Optional[str] = None
    questions: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    hit_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_hit_at: datetime = Field(default_factory=datetime.utcnow)


class OcrExtractionCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(unique=True, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    result_json: dict = Field(sa_column=Column(JSON))
    meta: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    hit_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_hit_at: datetime = Field(default_factory=datetime.utcnow)


class CreditHold(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    request_id: str = Field(index=True)
    question_id: Optional[str] = Field(default=None, index=True)
    reserved_credits: float = Field(default=0.0)
    status: str = Field(default="held")  # held, finalized, released, failed
    meta: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: Optional[datetime] = None


class DeviceSignupLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[int] = None


class RequestEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: Optional[str] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    mode: Optional[str] = Field(default=None, index=True) # minimal/detailed
    learning_mode: Optional[str] = Field(default=None, index=True) # solve/study
    subject: Optional[str] = Field(default=None, index=True)
    grade_level: Optional[str] = Field(default=None, index=True)
    model: Optional[str] = Field(default=None, index=True)
    provider: Optional[str] = Field(default=None, index=True)
    route: Optional[str] = Field(default=None, index=True)
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    tokens_total: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    status: Optional[str] = Field(default=None, index=True) # ok/error
    error_type: Optional[str] = Field(default=None, index=True)
    schema_valid: Optional[bool] = None
    verification_pass: Optional[bool] = None
    is_stream: bool = False
    is_cached: bool = False
    credit_deducted: Optional[bool] = None
    credit_amount: Optional[float] = None
    ocr_used: bool = False
    voice_used: bool = False
    response_truncated: bool = False


class SolverOutputAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: str = Field(index=True)
    attempt_id: str = Field(index=True, default_factory=lambda: str(uuid.uuid4())) # New UUID for unique attempt tracking
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    session_id: Optional[int] = Field(default=None, foreign_key="chatsession.id", index=True)
    message_id: Optional[int] = Field(default=None, foreign_key="chatmessage.id", index=True)

    user: Optional["User"] = Relationship()
    chat_session: Optional["ChatSession"] = Relationship()
    
    # Context
    output_format: str = Field(default="freeform", index=True)
    prompt_id: Optional[str] = Field(default=None, index=True)
    prompt_version: Optional[str] = None
    prompt_meta: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # Full prompt config snapshot
    
    attempt_number: int = Field(default=1, index=True)
    provider: Optional[str] = Field(default=None, index=True)
    model: Optional[str] = Field(default=None, index=True)
    
    # Inputs
    input_text_raw: Optional[str] = Field(default=None, sa_column=Column(Text))
    input_text_normalized: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Metrics
    latency_ms: Optional[int] = None
    char_count: int = Field(default=0)
    
    # Outputs
    extracted_answer: Optional[str] = Field(default=None, sa_column=Column(Text))
    raw_solution_text: str = Field(default="", sa_column=Column(Text)) # Primary output
    llm_raw_response: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # Full provider response dump
    
    # Validation & Repair
    validation_json: Optional[dict] = Field(default=None, sa_column=Column(JSON)) # Successful parse
    validation_errors: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON)) # Error list if failed
    
    # Clarification
    clarification_count: int = Field(default=0)
    clarification_history: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON)) # [{q:..., a:...}]
    
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    
    # Phase 1: Append-only History
    llm_responses: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON)) # Append-only history
    validation_events: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON)) # Validation history
    
    # Metrics (A5)
    latency_ms: Optional[int] = None
    time_to_first_token_ms: Optional[int] = None
    provider_model: Optional[str] = Field(default=None, index=True) # provider:model string

    
    # Archives & Status
    archive_path: Optional[str] = None
    status: str = Field(default="pending", index=True) # pending, success, failure, ambiguous
    failure_code: Optional[str] = Field(default=None, index=True) # SCHEMA_INVALID, etc.
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProviderPricingAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    RETIRE = "RETIRE"

class ProviderPricingAuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    admin_user_id: int = Field(foreign_key="user.id", index=True)
    provider_model_pricing_id: int = Field(foreign_key="providermodelpricing.id", index=True)
    action: ProviderPricingAction
    before_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    after_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ProviderModelPricing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True) # openai, anthropic
    model: str = Field(index=True)    # gpt-4o, claude-3-5-sonnet
    
    price_in_per_1m: float
    price_out_per_1m: float
    price_cached_in_per_1m: Optional[float] = Field(default=0.0)
    
    currency: str = Field(default="USD")
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    effective_to: Optional[datetime] = None # Null = current
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[int] = Field(default=None)
    status: str = Field(default="ACTIVE", index=True) # ACTIVE, INACTIVE
    change_reason: Optional[str] = None



class CreditLot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id", index=True)
    
    # Core Balance
    credits_total: float
    credits_remaining: float
    
    # Metadata
    lot_type: str = Field(default="TOPUP", index=True) # TOPUP, PROMO, GRANT, MIGRATION, SUBSCRIPTION_GRANT
    status: str = Field(default="ACTIVE", index=True) # ACTIVE, EXPIRED, DEPLETED, VOIDED
    source: str = Field(default="MANUAL_ADMIN", index=True)
    external_ref: Optional[str] = Field(default=None, index=True) # PaymentIntent ID or idempotency key
    
    currency: str = Field(default="USD")
    amount_paid: Optional[float] = None
    
    purchased_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    
    is_active: bool = Field(default=True) # Legacy toggle, use status='ACTIVE' primarily

class CreditLotConsumption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id")
    credit_lot_id: int = Field(foreign_key="creditlot.id", index=True)
    # Allows nullable for legacy or edge cases, but ideally FK enforced
    usage_ledger_id: Optional[int] = Field(default=None, foreign_key="usageledger.id", index=True) 
    
    direction: str = Field(index=True) # DEBIT, REFUND
    amount: float
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TopUpProduct(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    credits: int
    price_usd: float
    is_active: bool = Field(default=True)
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))

class BillingLedger(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    action_type: str = Field(index=True) # image_import, pdf_import, solve_quick, solve_tutor, voice_transcribe, etc.
    request_id: Optional[str] = Field(default=None, index=True)
    source_asset_id: Optional[str] = None
    question_id: Optional[str] = None
    
    # Status
    status: str = Field(default="SETTLED", index=True) # PENDING, SETTLED, FAILED_REFUNDED
    
    # Financials (Credits)
    credits_charged: float = 0.0 # Final effective charge (actual)
    estimated_credits: float = 0.0
    actual_credits: float = 0.0
    delta_credits: float = 0.0 # actual - estimate
    
    # Balances
    credits_before: float
    credits_after: float
    
    # Token Usage & Fees
    fee_tokens_applied: int = 0
    estimated_usage_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    actual_usage_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Legacy/Unified Usage (can mirror actual_usage_json)
    token_usage_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    pricing_snapshot_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    config_version_id: Optional[int] = Field(default=None, index=True) # Linked SystemConfigVersion
    
    # Phase 1: Definite Billing Fields
    provider_cost_usd: float = Field(default=0.0)
    markup_multiplier: float = Field(default=1.0)
    fixed_fee_usd: float = Field(default=0.0)
    charge_usd: float = Field(default=0.0)
    credit_value_usd: float = Field(default=0.0)
    tier: Optional[str] = Field(default=None) # FREE, STANDARD, RESEARCH
    finalized_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    ok: bool = Field(default=True)
    error_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))

class StripeEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stripe_event_id: str = Field(unique=True, index=True)
    type: str = Field(index=True)
    api_version: Optional[str] = None
    created_ts: int = Field(index=True)
    livemode: bool = False
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    process_status: str = Field(default="RECEIVED", index=True) # RECEIVED, PROCESSED, FAILED, IGNORED
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))

class TopUpOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    topup_product_id: int = Field(foreign_key="topupproduct.id")
    credits: float
    price_usd: float
    currency: str = Field(default="USD")
    status: str = Field(default="CREATED", index=True) # CREATED, CHECKOUT_CREATED, PAID, FULFILLED, CANCELED, FAILED
    stripe_checkout_session_id: Optional[str] = Field(default=None, unique=True, index=True)
    stripe_payment_intent_id: Optional[str] = Field(default=None, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    fulfill_usage_ledger_id: Optional[int] = Field(default=None)
    fulfill_credit_lot_id: Optional[int] = Field(default=None)

class SubscriptionBillingLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="subscription.id")
    user_id: int = Field(foreign_key="user.id", index=True)
    stripe_customer_id: str = Field(index=True)
    stripe_subscription_id: str = Field(unique=True, index=True)
    stripe_price_id: str = Field(index=True)
    status: str = Field(index=True) # ACTIVE, PAST_DUE, CANCELED, INCOMPLETE, UNPAID
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class StripePriceMap(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(index=True) # TOPUP, SUBSCRIPTION
    internal_code: str = Field(index=True) # product code or plan slug
    stripe_price_id: str = Field(index=True)
    currency: str = Field(default="USD")
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InvoiceKind(str, Enum):
    TOPUP = "TOPUP"
    SUBSCRIPTION = "SUBSCRIPTION"
    ADJUSTMENT = "ADJUSTMENT"

class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAID = "PAID"
    VOID = "VOID"
    UNCOLLECTIBLE = "UNCOLLECTIBLE"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"

class TaxMode(str, Enum):
    NONE = "NONE"
    ESTIMATED = "ESTIMATED"
    FINAL = "FINAL"

class InvoiceLineItemKind(str, Enum):
    TOPUP_CREDITS = "TOPUP_CREDITS"
    SUBSCRIPTION_FEE = "SUBSCRIPTION_FEE"
    USAGE_CHARGE = "USAGE_CHARGE"
    REFUND = "REFUND"
    DISCOUNT = "DISCOUNT"
    TAX = "TAX"
    ADJUSTMENT = "ADJUSTMENT"

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id", index=True)
    topup_order_id: Optional[int] = Field(default=None, foreign_key="topuporder.id", index=True) 
    
    stripe_invoice_id: Optional[str] = Field(default=None, unique=True, index=True)
    stripe_payment_intent_id: Optional[str] = Field(default=None, index=True)
    
    invoice_number: str = Field(unique=True, index=True)
    kind: InvoiceKind = Field(index=True)
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT, index=True)
    
    currency: str = Field(default="USD")
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    subtotal_amount: float = Field(default=0.0)
    tax_amount: float = Field(default=0.0)
    total_amount: float = Field(default=0.0)
    
    amount_paid: float = Field(default=0.0)
    amount_due: float = Field(default=0.0)
    
    tax_mode: TaxMode = Field(default=TaxMode.NONE)
    tax_rate: Optional[float] = None
    
    billing_address_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class InvoiceLineItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    
    kind: InvoiceLineItemKind
    description: str
    quantity: float = Field(default=1.0)
    unit_price: float
    amount: float
    currency: str = Field(default="USD")
    
    billing_ledger_id: Optional[int] = Field(default=None, foreign_key="billingledger.id")
    payment_id: Optional[int] = Field(default=None, foreign_key="payment.id")
    
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InvoiceSequence(SQLModel, table=True):
    """Simple atomic sequence for invoice numbering per year."""
    id: Optional[int] = Field(default=None, primary_key=True)
    year: int = Field(unique=True, index=True)
    last_value: int = Field(default=0)

class ReconciliationFinding(SQLModel, table=True):
    """Tracks issues found during automated system reconciliation."""
    id: Optional[int] = Field(default=None, primary_key=True)
    finding_type: str = Field(index=True) # e.g. ledger_mismatch, invoice_missing
    severity: str = "HIGH" # LOW, MEDIUM, HIGH, CRITICAL
    
    entity_type: str = Field(index=True) # subscription, request, user, invoice, lot
    entity_id: str = Field(index=True) # External ID or Primary Key
    
    trace_id: Optional[str] = Field(default=None, index=True)
    details_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    status: str = Field(default="OPEN", index=True) # OPEN, ACKED, RESOLVED
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None # Admin user ID

