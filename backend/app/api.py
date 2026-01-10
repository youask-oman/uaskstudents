from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
import uuid
import hashlib

from app.database import get_session
from app.models import User, ChatSession, ChatMessage, UsageLog, OCRJob, Payment, PromoCode
from app.services.vision import VisionService, vision_service
from app.services.solver import solver_service
from app.services.rag import rag_service



from app.auth import verify_password, create_access_token, Token, get_password_hash

api_router = APIRouter()



# --- Schemas ---
class SolveRequest(BaseModel):
    image_url: Optional[str] = None
    text_query: Optional[str] = None
    subject: Optional[str] = None
    mode: Optional[str] = "general"
    user_id: Optional[int] = None

class SolveResponse(BaseModel):
    session_id: int
    solution: dict
    concepts: List[dict]

class ChatHistoryItem(BaseModel):
    id: int
    title: str
    created_at: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    academic_level: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    academic_level: Optional[str] = None
    timezone: Optional[str] = None
    is_public: Optional[bool] = None
    learning_interests: Optional[List[str]] = None

class PreferenceUpdateRequest(BaseModel):
    theme: Optional[str] = None
    preferred_language: Optional[str] = None
    solving_mode: Optional[str] = None

class UserUsageStats(BaseModel):
    questions_count: int
    questions_total: int
    scans_count: int
    scans_total: int

class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    academic_level: Optional[str]
    timezone: str
    theme: str
    preferred_language: str
    solving_mode: str
    subscription_tier: str
    subscription_status: str
    
    # Advanced Profile
    is_public: bool
    learning_interests: Optional[List[str]]
    
    usage: UserUsageStats

@api_router.post("/signup")
async def signup(form_data: SignupRequest, session: Session = Depends(get_session)):
    # Check if user already exists
    existing_user = session.exec(select(User).where(User.email == form_data.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists"
        )
    
    # Create new user
    new_user = User(
        email=form_data.email,
        full_name=form_data.full_name,
        password_hash=get_password_hash(form_data.password),
        academic_level=form_data.academic_level,
        is_verified=False # Setting to false as frontend mentions a verification link
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return {"status": "ok", "message": "User created successfully. Please check your email for verification.", "user_id": new_user.id}

@api_router.post("/login", response_model=Token)
async def login_for_access_token(form_data: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form_data.email)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Session & Security
    session_token = str(uuid.uuid4())
    user.session_token = session_token
    # In a real app, retrieve IP from request.client.host
    # Here we mock or pass it via header if critical
    user.last_ip = "127.0.0.1" 
    
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token = create_access_token(data={"sub": user.email})
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
        avatar_url=user.avatar_url,
        session_token=session_token # Return to client
    )




class LatexResponse(BaseModel):
    latex: str

@api_router.post("/latex-from-image", response_model=LatexResponse)
async def extract_latex_from_image(
    file: UploadFile, 
    user_id: int = 1, 
    session: Session = Depends(get_session)
):
    """
    Directly extracts LaTeX from an image using OpenAI Vision.
    No background jobs, no polling.
    """
    content = await file.read()
    
    # Optional: Validate size/dimensions here to prevent huge costs
    
    latex_result = await vision_service.extract_latex(content)
    
    # Log usage
    session.add(UsageLog(user_id=user_id, action_type="vision_ocr", tokens_used=500))
    session.commit()
    
    return LatexResponse(latex=latex_result)

# ... (omitted lines)


@api_router.post("/solve", response_model=SolveResponse)
async def solve_problem(
    request: SolveRequest, 
    session: Session = Depends(get_session)
):
    """
    Main Orchestrator Endpoint:
    1. Check token limit
    2. OCR (if image)
    3. RAG Retrieval
    4. Solver (LLM)
    5. DB Persistence
    6. Track tokens
    """
    try:
        # Check token limit BEFORE processing
        # Use user_id from request body (pydantic), default to 1 if missing
        user_id = request.user_id or 1
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check and reset monthly tokens if needed
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if (now - user.last_token_reset).days >= 30:
            user.tokens_used_this_month = 0
            user.last_token_reset = now
            session.add(user)
            session.commit()
            session.refresh(user)
        
        # Enforce 1M token limit
        MONTHLY_LIMIT = 1_000_000
        if user.tokens_used_this_month >= MONTHLY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly token limit of {MONTHLY_LIMIT:,} tokens exceeded. Resets on {(user.last_token_reset + timedelta(days=30)).strftime('%Y-%m-%d')}."
            )
        
        # 1. OCR Processing (Legacy/Vision fallback if needed, but mostly handled by frontend passing text now)
        # The frontend now calls /latex-from-image first, then passes the text here.
        # So we don't need to call ocr_service here anymore.
        extracted_text = ""
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    base_query = f"{request.text_query or ''}\n{extracted_text}".strip()
    
    # ... (rest of logic) ...

    # 2. Retrieval
    # Prepend Mode Context
    if request.mode and request.mode != "general":
        base_query = f"[MODE: {request.mode.upper()}] {base_query}"
    
    if not base_query.strip():
        raise HTTPException(status_code=400, detail="No input provided")

    concepts = await rag_service.search_related_concepts(base_query)

    # 3. Solve
    solution_data = await solver_service.solve_problem(base_query)

    # 4. Persistence
    # Create Session (NOT SAVED by default)
    new_chat = ChatSession(
        user_id=user_id,
        title=solution_data.get("problem", {}).get("goal", "New Problem")[:50],
        subject=request.subject or "General",
        is_saved=False
    )
    session.add(new_chat)
    session.commit()
    session.refresh(new_chat)

    # Save User Query
    user_msg = ChatMessage(
        session_id=new_chat.id,
        role="user",
        content=base_query,
        media_url=request.image_url
    )
    session.add(user_msg)

    # Save Assistant Response
    ai_msg = ChatMessage(
        session_id=new_chat.id,
        role="assistant",
        content=solution_data.get("solution", {}).get("final_answer", ""),
        structured_data=solution_data
    )
    session.add(ai_msg)
    
    # Estimate tokens used (rough estimate: ~500 tokens per solve)
    estimated_tokens = 500
    
    # Update user's token count
    user.tokens_used_this_month += estimated_tokens
    session.add(user)
    
    # Log Solve Usage
    session.add(UsageLog(user_id=user_id, action_type="solve_request", tokens_used=estimated_tokens))
    
    session.commit()

    return SolveResponse(
        session_id=new_chat.id,
        solution=solution_data,
        concepts=solution_data.get("concepts") or []
    )
    
    # ------------------------------------------------------------------
# Billing & User Location Endpoints
# ------------------------------------------------------------------

class SubscribeRequest(BaseModel):
    user_id: int
    plan_id: str # pro, ultra
    payment_method: str = "card"
    card_last4: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None

class LocationUpdateRequest(BaseModel):
    user_id: int
    ip_address: Optional[str] = None
    country: Optional[str] = None

@api_router.post("/billing/subscribe")
async def subscribe_user(request: SubscribeRequest, session: Session = Depends(get_session)):
    user = session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Simulate Payment Processing
    transaction_id = f"tx_{datetime.utcnow().timestamp()}_{user.id}"
    amount = 9.99 if request.plan_id == "pro" else 0.00
    
    # Create Payment Record
    payment = Payment(
        user_id=user.id,
        amount=amount,
        currency="USD",
        status="completed",
        transaction_id=transaction_id,
        payment_method=request.payment_method,
        ip_address=request.ip_address
    )
    session.add(payment)
    
    # Update User Location if provided
    if request.ip_address:
        user.ip_address = request.ip_address
    if request.country:
        user.country = request.country
        
    # Update Subscription
    user.subscription_tier = request.plan_id
    user.subscription_status = "active"
    user.subscription_expiry = datetime.utcnow() + timedelta(days=30)
    
    session.add(user)
    session.commit()
    session.refresh(payment)
    
    return {"status": "success", "transaction_id": transaction_id, "plan": request.plan_id}

@api_router.get("/billing/history")
async def get_billing_history(user_id: int, session: Session = Depends(get_session)):
    payments = session.exec(select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())).all()
    return payments

@api_router.post("/user/location")
async def update_user_location(request: LocationUpdateRequest, session: Session = Depends(get_session)):
    """Update user IP and country for security logging"""
    user = session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.ip_address:
        user.ip_address = request.ip_address
    if request.country:
        user.country = request.country
        
    session.add(user)
    session.commit()
    return {"status": "updated", "ip": user.ip_address, "country": user.country}

# ------------------------------------------------------------------
# Promo Code Endpoints
# ------------------------------------------------------------------

class PromoValidateRequest(BaseModel):
    code: str

class PromoCreateRequest(BaseModel):
    code: str
    discount_percent: int
    max_uses: Optional[int] = None

@api_router.post("/billing/validate-promo")
async def validate_promo(request: PromoValidateRequest, session: Session = Depends(get_session)):
    code_upper = request.code.upper().strip()
    promo = session.exec(select(PromoCode).where(PromoCode.code == code_upper)).first()
    
    if not promo:
        return {"valid": False, "message": "Invalid code"}
        
    if not promo.is_active:
        return {"valid": False, "message": "Code is inactive"}
        
    if promo.valid_until and promo.valid_until < datetime.utcnow():
        return {"valid": False, "message": "Code expired"}
        
    if promo.max_uses and promo.current_uses >= promo.max_uses:
        return {"valid": False, "message": "Code usage limit reached"}
        
    return {
        "valid": True, 
        "message": "Valid code", 
        "discount_percent": promo.discount_percent,
        "code": promo.code
    }

@api_router.post("/admin/promo-codes")
async def create_promo_code(request: PromoCreateRequest, session: Session = Depends(get_session)):
    # In prod, check admin role here
    new_promo = PromoCode(
        code=request.code.upper().strip(),
        discount_percent=request.discount_percent,
        max_uses=request.max_uses
    )
    session.add(new_promo)
    try:
        session.commit()
        return {"status": "created", "code": new_promo.code}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail="Code already exists or invalid")
    # (End of promo codes)

@api_router.get("/history", response_model=List[ChatHistoryItem])
async def get_history(
    user_id: int, 
    saved_only: bool = True,
    session: Session = Depends(get_session)
):
    # Filter based on saved_only flag
    if saved_only:
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.is_saved == True
        ).order_by(ChatSession.created_at.desc())
    else:
        # Return ALL sessions for this user
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.created_at.desc())
        
    results = session.exec(stmt).all()
    
    return [
        ChatHistoryItem(
            id=chat.id, 
            title=chat.title, 
            created_at=chat.created_at.isoformat(),
            subject=chat.subject or "Math",
            is_saved=chat.is_saved 
        ) 
        for chat in results
    ]

class ChatMessageSchema(BaseModel):
    role: str
    content: str
    media_url: Optional[str] = None
    structured_data: Optional[dict] = None
    created_at: str

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    subject: Optional[str] = None
    created_at: str
    messages: List[ChatMessageSchema]

@api_router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session_details(session_id: int, session: Session = Depends(get_session)):
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return ChatSessionResponse(
        id=chat_session.id,
        title=chat_session.title,
        subject=chat_session.subject,
        created_at=chat_session.created_at.isoformat(),
        messages=[
            ChatMessageSchema(
                role=msg.role,
                content=msg.content,
                media_url=msg.media_url,
                structured_data=msg.structured_data,
                created_at=msg.created_at.isoformat()
            )
            for msg in chat_session.messages
        ]
    )

class QuestionRequest(BaseModel):
    session_id: int
    user_id: int
    query: str

@api_router.post("/ask-question")
async def ask_question(request: QuestionRequest, db: Session = Depends(get_session)):
    # 1. Fetch Context
    chat_session = db.get(ChatSession, request.session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get the last assistant message structure for context
    last_assistant_msg = db.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == request.session_id)
        .where(ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc())
    ).first()
    
    context = last_assistant_msg.structured_data if last_assistant_msg else {}
    
    # 2. Get Response from SolverService
    result = await solver_service.get_chat_response(request.query, context)
    
    # 3. Save User Message
    db.add(ChatMessage(
        session_id=request.session_id,
        role="user",
        content=request.query
    ))
    
    # 4. Save AI Response
    ai_msg = ChatMessage(
        session_id=request.session_id,
        role="assistant",
        content=result.get("content", "I am sorry, I could not process that.")
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    
    return {
        "relevant": result.get("relevant", True),
        "content": ai_msg.content,
        "created_at": ai_msg.created_at.isoformat()
    }

# --- Profile & Preferences ---

@api_router.get("/user/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate usage (Conceptual/Simplified for now)
    # Questions count: count solve_request in UsageLog in last 30 days
    questions_count = db.exec(
        select(UsageLog)
        .where(UsageLog.user_id == user_id)
        .where(UsageLog.action_type == "solve_request")
    ).all() # Should ideally filter by date
    
    scans_count = db.exec(
        select(OCRJob)
        .where(OCRJob.user_id == user_id)
    ).all()
    
    return UserProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        academic_level=user.academic_level,
        timezone=user.timezone,
        theme=user.theme,
        preferred_language=user.preferred_language,
        solving_mode=user.solving_mode,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        
        is_public=user.is_public,
        learning_interests=user.learning_interests or [],
        
        usage=UserUsageStats(
            questions_count=len(questions_count),
            questions_total=user.quota_questions_total,
            scans_count=len(scans_count),
            scans_total=user.quota_scans_total
        )
    )

@api_router.post("/user/profile")
async def update_user_profile(request: ProfileUpdateRequest, user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.email is not None:
        user.email = request.email
    if request.academic_level is not None:
        user.academic_level = request.academic_level
    if request.timezone is not None:
        user.timezone = request.timezone
    if request.is_public is not None:
        user.is_public = request.is_public
    if request.learning_interests is not None:
        user.learning_interests = request.learning_interests
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "message": "Profile updated"}

@api_router.post("/user/preferences")
async def update_user_preferences(request: PreferenceUpdateRequest, user_id: int = Query(...), db: Session = Depends(get_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.theme is not None:
        user.theme = request.theme
    if request.preferred_language is not None:
        user.preferred_language = request.preferred_language
    if request.solving_mode is not None:
        user.solving_mode = request.solving_mode
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "ok", "message": "Preferences updated"}

# --- Token Tracking & Save Functionality ---

from datetime import datetime, timedelta

def check_and_reset_monthly_tokens(user: User, db: Session) -> User:
    """Check if we need to reset monthly token count"""
    now = datetime.utcnow()
    # Reset if it's been more than 30 days
    if (now - user.last_token_reset).days >= 30:
        user.tokens_used_this_month = 0
        user.last_token_reset = now
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@api_router.post("/user/heartbeat")
async def update_heartbeat(
    user_id: int = Query(...), 
    session_token: Optional[str] = Query(None),
    db: Session = Depends(get_session)
):
    """Update user's last active timestamp and validate session"""
    user = db.get(User, user_id)
    if user:
        # Enforce Single Session
        if session_token and user.session_token:
            if session_token != user.session_token:
                raise HTTPException(status_code=401, detail="Session expired. New login detected.")
        
        user.last_active_at = datetime.utcnow()
        db.add(user)
        db.commit()
    return {"status": "ok"}

@api_router.get("/users/online")
async def get_online_users(db: Session = Depends(get_session)):
    """Get list of public users active in the last 15 minutes"""
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    
    # Select users who are public AND active recently
    statement = select(User).where(User.is_public == True).where(User.last_active_at >= cutoff)
    users = db.exec(statement).all()
    
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "learning_interests": u.learning_interests
        }
        for u in users
    ]

def add_tokens_to_user(user_id: int, tokens: int, db: Session):
    """Add tokens to user's monthly count"""
    user = db.get(User, user_id)
    if user:
        user = check_and_reset_monthly_tokens(user, db)
        user.tokens_used_this_month += tokens
        db.add(user)
        db.commit()

class TokenUsageResponse(BaseModel):
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    reset_date: str
    is_over_limit: bool

@api_router.get("/user/token-usage", response_model=TokenUsageResponse)
async def get_token_usage(user_id: int = Query(...), db: Session = Depends(get_session)):
    """Get current month's token usage for a user"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = check_and_reset_monthly_tokens(user, db)
    
    MONTHLY_LIMIT = 1_000_000  # 1M tokens per month
    tokens_remaining = max(0, MONTHLY_LIMIT - user.tokens_used_this_month)
    reset_date = (user.last_token_reset + timedelta(days=30)).isoformat()
    
    return TokenUsageResponse(
        tokens_used=user.tokens_used_this_month,
        tokens_limit=MONTHLY_LIMIT,
        tokens_remaining=tokens_remaining,
        reset_date=reset_date,
        is_over_limit=user.tokens_used_this_month >= MONTHLY_LIMIT
    )

@api_router.post("/sessions/{session_id}/save")
async def save_session(session_id: int, db: Session = Depends(get_session)):
    """Mark a session as saved so it appears in history"""
    chat_session = db.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    chat_session.is_saved = True
    db.add(chat_session)
    db.commit()
    
    return {"status": "ok", "message": "Session saved successfully", "session_id": session_id}

class SessionDetailResponse(BaseModel):
    id: int
    title: str
    is_saved: bool
    created_at: str

@api_router.get("/sessions/{session_id}/details", response_model=SessionDetailResponse)
async def get_session_save_status(session_id: int, db: Session = Depends(get_session)):
    """Get session details including save status"""
    chat_session = db.get(ChatSession, session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionDetailResponse(
        id=chat_session.id,
        title=chat_session.title,
        is_saved=chat_session.is_saved,
        created_at=chat_session.created_at.isoformat()
    )


