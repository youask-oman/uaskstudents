from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON, BigInteger

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
    grade_level: Optional[str] = None  # 'Grade 1' to 'Grade 12'
    school_id: Optional[int] = Field(default=None, foreign_key="school.id", index=True)  # Optional school
    
    # Advanced Profile
    is_public: bool = Field(default=False)
    learning_interests: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Session Security
    session_token: Optional[str] = None
    last_ip: Optional[str] = None

    # Subscription Relationship
    subscription: Optional["Subscription"] = Relationship(back_populates="user")
    
    # Relationships
    school: Optional["School"] = Relationship(back_populates="students")
    sessions: List["ChatSession"] = Relationship(back_populates="user")
    usage_logs: List["UsageLog"] = Relationship(back_populates="user")
    payments: List["Payment"] = Relationship(back_populates="user")
    voice_sessions: List["VoiceSession"] = Relationship(back_populates="user")
    admin_notes: List["AdminNote"] = Relationship(back_populates="user")

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
    
    # For multimedia (images, voice urls)
    media_url: Optional[str] = None 
    
    # Structure for rich responses (steps, verification, etc) - stored as JSON
    structured_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Metadata for tracking
    model_used: Optional[str] = None
    tokens_used: int = Field(default=0)
    
    # Detailed Telemetry (Latency, detailed tokens, cached status)
    telemetry: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    session: ChatSession = Relationship(back_populates="messages")

class UsageLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    action_type: str # ocr_scan, solve_request, generating_image
    tokens_used: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="usage_logs")

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
    
    # Linked Prompts
    system_prompt_template_id: Optional[int] = Field(default=None, foreign_key="prompttemplate.id")
    schema_prompt_template_id: Optional[int] = Field(default=None, foreign_key="prompttemplate.id")
    
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
    Unified schools table for USA and Canada schools.
    Uses SHA256-based school_key for deduplication across reimports.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Location (required)
    country: str = Field(index=True)  # 'USA' or 'Canada'
    province_state: str = Field(index=True)  # State for USA, Province/Territory for Canada
    
    # Location (optional)
    district: Optional[str] = None
    city: Optional[str] = None
    
    # School Info (required)
    school_name: str = Field(index=True)
    
    # School Info (optional)
    school_type: Optional[str] = None  # public, private, charter, etc.
    grade_range: Optional[str] = None  # e.g., "K-12", "9-12"
    
    # Source tracking
    external_id: Optional[str] = None  # NCES ID for US, Source_ID for Canada
    source: str = Field(index=True)  # 'US_CSV' or 'CA_CSV'
    
    # Deduplication key: SHA256(lower(country)|lower(province_state)|lower(city or '')|lower(school_name))
    school_key: str = Field(unique=True, index=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
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


class PromptTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True) # e.g. "Math Solver"
    slug: str = Field(unique=True, index=True) # e.g. "math-solver"
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    versions: List["PromptVersion"] = Relationship(back_populates="template")

class PromptVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="prompttemplate.id")
    version: str # e.g. "v1.0.1" (previously version_string)
    content: str
    author: str
    is_production: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    template: PromptTemplate = Relationship(back_populates="versions")

class UserQuotaOverride(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_limit: Optional[int] = None
    ocr_concurrency: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SystemErrorEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    level: str = "ERROR" # INFO, WARNING, ERROR, CRITICAL
    component: str # e.g. "OCR-ENGINE", "API-ROUTER"
    message: str
    stack_trace: Optional[str] = None
    is_resolved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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


# --- Tier-Aware Prompt Routing Models ---

class PromptAsset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True) # e.g. "shared:minimal_system"
    kind: str = Field(index=True) # system, schema
    path: str # relative to backend/app, e.g. "llm_profiles/shared/minimal_system.txt"
    checksum: Optional[str] = None # sha256
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PlanPromptLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="plan.id", index=True)
    mode: str = Field(index=True) # minimal, detailed
    
    system_prompt_asset_id: Optional[int] = Field(default=None, foreign_key="promptasset.id")
    schema_prompt_asset_id: Optional[int] = Field(default=None, foreign_key="promptasset.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

