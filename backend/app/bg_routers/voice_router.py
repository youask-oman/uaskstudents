
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
from app.services.voice.voice_service import voice_service
from app.schemas.voice_schemas import (
    TranscribeResponse, 
    VoiceCommandRequest, 
    VoiceCommandResponse, 
    FindErrorRequest, 
    FindErrorResponse
)
import uuid
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_AUDIO_BYTES = 5 * 1024 * 1024 # 5MB

@router.post("/audio/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form(None)
):
    """Transcribe uploaded audio blob to text."""
    request_id = str(uuid.uuid4())
    
    # Size check
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    
    if size > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large")
        
    try:
        # Read into memory (safe due to size limit)
        audio_bytes = await file.read()
        
        # In a real implementation we might pass the file-like object directly
        # dependent on the OpenAI library version, but bytes is safest wrapper.
        from io import BytesIO
        file_obj = BytesIO(audio_bytes)
        
        # Determine extension from original filename
        import os
        _, ext = os.path.splitext(file.filename or "")
        if not ext:
            # Fallback based on content type
            if file.content_type == "audio/wav": ext = ".wav"
            elif file.content_type == "audio/mp4": ext = ".mp4"
            elif file.content_type == "audio/mpeg": ext = ".mp3"
            else: ext = ".webm" # Default safe bet for web audio
            
        file_obj.name = f"audio{ext}" # Hint for Whisper
        
        transcript = await voice_service.transcribe_audio(file_obj, filename=file_obj.name)
        
        return TranscribeResponse(
            ok=True, 
            transcript=transcript, 
            request_id=request_id
        )
    except Exception as e:
        logger.exception("Transcription endpoint failed")
        return TranscribeResponse(ok=False, error=str(e), request_id=request_id)

@router.post("/voice/command", response_model=VoiceCommandResponse)
async def resolve_voice_command(req: VoiceCommandRequest):
    """Resolve intent from transcript and context."""
    request_id = str(uuid.uuid4())
    start = time.time()
    
    try:
        context = {
            "selection_bbox": req.selection_bbox.dict() if req.selection_bbox else None,
            "question_ids": req.question_ids,
            "page": req.page_context.dict() if req.page_context else None
        }
        
        intent = await voice_service.resolve_intent(req.transcript, context)
        
        return VoiceCommandResponse(
            ok=True,
            command=intent,
            request_id=request_id,
            timings={"total_ms": (time.time() - start) * 1000}
        )
    except Exception as e:
        logger.exception("Voice command resolution failed")
        return VoiceCommandResponse(ok=False, error={"message": str(e)}, request_id=request_id)

@router.post("/find_error", response_model=FindErrorResponse)
async def find_first_error(
    file: UploadFile = File(...),
    transcript: str = Form(""),
    selection_coords: str = Form(None) # Metadata if needed
):
    """Analyze the uploaded image crop for the first mistake."""
    # Size check
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    
    if size > MAX_AUDIO_BYTES: # Reusing 5MB limit which is fine for crop
        raise HTTPException(status_code=413, detail="Image file too large")
        
    try:
        image_bytes = await file.read()
        result = await voice_service.find_error(image_bytes, transcript)
        return result
    except Exception as e:
        logger.exception("Find error endpoint failed")
        return FindErrorResponse(ok=False, error=str(e))
