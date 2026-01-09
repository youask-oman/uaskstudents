from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
import uuid
import hashlib

from app.database import get_session
from app.models import User, ChatSession, ChatMessage, UsageLog
from app.services.vision import VisionService, vision_service
from app.services.solver import solver_service
from app.services.rag import rag_service



from app.auth import verify_password, create_access_token, Token

api_router = APIRouter()



# --- Schemas ---
class SolveRequest(BaseModel):
    image_url: Optional[str] = None
    text_query: Optional[str] = None
    subject: Optional[str] = None
    mode: Optional[str] = "general"

class SolveResponse(BaseModel):
    session_id: int
    solution: dict
    related_concepts: List[str]

class ChatHistoryItem(BaseModel):
    id: int
    title: str
    created_at: str

class LoginRequest(BaseModel):
    email: str
    password: str

@api_router.post("/login", response_model=Token)
async def login_for_access_token(form_data: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == form_data.email)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
        avatar_url=user.avatar_url
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
    user_id: int = 1, # Default to student for dev
    session: Session = Depends(get_session)
):
    """
    Main Orchestrator Endpoint:
    1. OCR (if image)
    2. RAG Retrieval
    3. Solver (LLM)
    4. DB Persistence
    """
    # 1. OCR Processing (Legacy/Vision fallback if needed, but mostly handled by frontend passing text now)
    # The frontend now calls /latex-from-image first, then passes the text here.
    # So we don't need to call ocr_service here anymore.
    extracted_text = ""

    base_query = f"{request.text_query or ''}\n{extracted_text}".strip()
    
    # Prepend Mode Context
    if request.mode and request.mode != "general":
        final_query = f"[MODE: {request.mode.upper()}] {base_query}"
    else:
        final_query = base_query

    if not final_query.strip():
        raise HTTPException(status_code=400, detail="No input provided")

    # 2. Retrieval
    concepts = await rag_service.search_related_concepts(final_query)

    # 3. Solve
    solution_data = await solver_service.solve_problem(final_query)

    # 4. Persistence
    # Create Session
    new_chat = ChatSession(
        user_id=user_id,
        title=solution_data.get("summary", "New Problem")[:50],
        subject=request.subject or "General"
    )
    session.add(new_chat)
    session.commit()
    session.refresh(new_chat)

    # Save User Query
    user_msg = ChatMessage(
        session_id=new_chat.id,
        role="user",
        content=final_query,
        media_url=request.image_url
    )
    session.add(user_msg)

    # Save Assistant Response
    ai_msg = ChatMessage(
        session_id=new_chat.id,
        role="assistant",
        content=solution_data.get("final_answer", ""),
        structured_data=solution_data
    )
    session.add(ai_msg)
    
    # Log Solve Usage
    session.add(UsageLog(user_id=user_id, action_type="solve_request", tokens_used=100))
    
    session.commit()

    return SolveResponse(
        session_id=new_chat.id,
        solution=solution_data,
        related_concepts=concepts
    )

@api_router.get("/history", response_model=List[ChatHistoryItem])
async def get_history(user_id: int, session: Session = Depends(get_session)):
    stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc())
    results = session.exec(stmt).all()
    
    return [
        ChatHistoryItem(
            id=chat.id, 
            title=chat.title, 
            created_at=chat.created_at.isoformat()
        ) 
        for chat in results
    ]

class ChatMessageSchema(BaseModel):
    role: str
    content: str
    media_url: Optional[str] = None
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
                created_at=msg.created_at.isoformat()
            )
            for msg in chat_session.messages
        ]
    )
