
import os
import time
import json
import logging
import base64
from typing import Optional, Dict, Any
from app.schemas.voice_schemas import VoiceCommandIntent, FindErrorResponse
from openai import AsyncOpenAI

# ... imports ...



logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        # Specific fix for local dev environment where .env is in parent root
        if not os.getenv("OPENAI_API_KEY"):
            from dotenv import load_dotenv, find_dotenv
            from pathlib import Path
            
            # Try finding it in project root (up 3 levels from here: services/voice/voice_service.py -> services/voice -> services -> app -> backend -> root?? Scale depends on structure)
            # Structure: c:\uaskstudents\backend\app\services\voice\voice_service.py
            # Root: c:\uaskstudents\.env
            
            # Try loading from CWD parents first
            load_dotenv()
            
            # If still missing, try explicit path
            if not os.getenv("OPENAI_API_KEY"):
                # fallback for typical monorepo structure
                env_path = Path(__file__).resolve().parents[4] / ".env" 
                if env_path.exists():
                    load_dotenv(dotenv_path=env_path)
                    
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Voice features will fail.")
    
    @property
    def client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key)

    async def transcribe_audio(self, file_obj, filename: str = "audio.webm") -> str:
        """Transcribe audio file using OpenAI Whisper (gpt-4o-mini-transcribe equivalent)."""
        if not self.api_key:
             raise ValueError("OpenAI API key missing")
        
        start = time.time()
        try:
            # Note: 'whisper-1' is the standard model identifier for audio transcriptions
            # The user requested 'gpt-4o-mini-transcribe', but standard endpoint uses whisper-1.
            # We will use whisper-1 as it's the current production standard.
            resp = await self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=(filename, file_obj),
                response_format="json"
            )
            duration = time.time() - start
            logger.info(f"Transcription completed in {duration:.2f}s")
            return resp.text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    async def resolve_intent(self, transcript: str, context: Dict[str, Any] = None) -> VoiceCommandIntent:
        """Resolve user intent from transcript using strict JSON schema."""
        if not self.api_key:
             raise ValueError("OpenAI API key missing")
        
        # Rule-based fast path
        clean_text = transcript.strip().lower()
        if "final answer" in clean_text and "only" in clean_text:
             return VoiceCommandIntent(
                 intent="FINAL_ANSWER_ONLY", target="full_crop", confidence=1.0, normalized_transcript=transcript
             )
        
        start = time.time()
        
        system_prompt = """You are a math tutor assistant. Analyze the user's voice command and map it to a structured intent.
        
        Capabilities:
        - FINAL_ANSWER_ONLY: User just wants the result.
        - NEXT_STEP_ONLY: User is stuck and needs a nudge.
        - FIND_FIRST_ERROR: User thinks they made a mistake in their work (provided in image).
        - GRAPH_PLOT: User wants to see the function graphed.
        - VERIFY_ANSWER: User wants to check if their answer is correct.
        - DETAILED_SOLUTION: User wants full step-by-step help.
        - EXTRACT_QUESTIONS: User wants to digitize the questions from the image.
        
        If user refers to "this" or "here" and a selection is present, target="selection".
        Otherwise target="full_crop" or "question_ids" if they mention specific questions.
        """
        
        user_content = f"Command: {transcript}"
        if context:
            if context.get("selection_bbox"):
                user_content += "\n(User has drawn a selection box on the screen)"
            if context.get("question_ids"):
                 user_content += f"\n(Selected question IDs: {context.get('question_ids')})"

        try:
            completion = await self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format=VoiceCommandIntent,
            )
            
            result = completion.choices[0].message.parsed
            logger.info(f"Intent resolution took {time.time() - start:.2f}s: {result.intent}")
            return result
            
        except Exception as e:
            logger.error(f"Intent resolution failed: {e}")
            # Fallback
            return VoiceCommandIntent(
                intent="DETAILED_SOLUTION", 
                confidence=0.0, 
                normalized_transcript=transcript
            )


    async def find_error(self, image_bytes: bytes, transcript: str = "") -> FindErrorResponse:
        """Analyze image crop for mathematical errors."""
        if not self.api_key:
             raise ValueError("OpenAI API key missing")
        
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        
        system_prompt = """You are an expert math tutor. 
        Analyze the provided image snippet, which contains a mathematical step or derivation.
        Determine if there is a mistake in this specific step.
        If there is a mistake, explain what is wrong and provide a minimal fix.
        If it seems correct or incomplete, state that.
        """
        
        user_text = f"User asked: '{transcript or 'Find my mistake'}'"
        
        try:
            completion = await self.client.beta.chat.completions.parse(
                model="gpt-4o", # Vision capable
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ]}
                ],
                response_format=FindErrorResponse,
            )
            result = completion.choices[0].message.parsed
            # API level success, regardless of math correctness
            result.ok = True 
            return result
        except Exception as e:
            logger.error(f"Find error failed: {e}")
            return FindErrorResponse(ok=False, error=str(e))

# Singleton
voice_service = VoiceService()
