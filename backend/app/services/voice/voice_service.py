
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

    async def transcribe_audio(self, file_input, filename: str = "audio.webm") -> str:
        """Transcribe audio file using OpenAI Whisper."""
        
        # Debug logging for tracing
        def debug_log(msg):
            logger.info(f"[VOICE_DEBUG] {msg}")
        
        debug_log(f"=== transcribe_audio called ===")
        debug_log(f"API key present: {bool(self.api_key)}")
        debug_log(f"API key prefix: {self.api_key[:10] if self.api_key else 'None'}...")
        
        if not self.api_key:
             raise ValueError("OpenAI API key missing")
        
        start = time.time()
        try:
            # Handle both bytes and file-like objects
            debug_log(f"file_input type: {type(file_input)}")
            if isinstance(file_input, bytes):
                audio_data = file_input
            elif hasattr(file_input, "read"):
                if hasattr(file_input, "seek"):
                    file_input.seek(0)
                audio_data = file_input.read()
            else:
                audio_data = file_input

            debug_log(f"Transcribing audio: filename={filename}, size={len(audio_data)} bytes")
            debug_log(f"First 20 bytes (hex): {audio_data[:20].hex() if len(audio_data) >= 20 else audio_data.hex()}")
            
            if len(audio_data) == 0:
                raise ValueError("Audio file is empty (0 bytes)")

            # Explicit MIME type mapping
            mime_type = "audio/webm"
            if filename.endswith(".wav"): mime_type = "audio/wav"
            elif filename.endswith(".mp3"): mime_type = "audio/mpeg"
            elif filename.endswith(".m4a"): mime_type = "audio/mp4"
            elif filename.endswith(".ogg"): mime_type = "audio/ogg"
            
            debug_log(f"Using MIME type: {mime_type}")
            
            # Use the AsyncOpenAI client directly for proper multipart handling
            from io import BytesIO
            
            debug_log("Creating file object for OpenAI client...")
            # Create a proper file-like object with name attribute
            file_obj = BytesIO(audio_data)
            file_obj.name = filename
            
            debug_log(f"Sending POST to OpenAI Whisper API...")
            try:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=file_obj,
                    response_format="text"
                )
                
                # response is a string with the transcript
                transcript = response
                debug_log(f"Transcript received: {transcript[:100] if transcript else 'EMPTY'}...")
            except Exception as api_error:
                debug_log(f"ERROR: OpenAI API call failed: {api_error}")
                raise ValueError(f"Whisper transcription failed: {str(api_error)}")
            
            duration = time.time() - start
            debug_log(f"Transcription completed in {duration:.2f}s")
            return transcript
        except Exception as e:
            debug_log(f"EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            debug_log(f"Traceback: {traceback.format_exc()}")
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

    def _fix_latex(self, text: Optional[str]) -> Optional[str]:
        """Ensures LaTeX backslashes are properly escaped."""
        if not text:
            return text
        # If we see 'ext{' instead of '\text{', restore the backslash
        # This handles the case where \t was cleaned or stripped
        fixed = text.replace("ext{", "\\text{")
        
        # Ensure 'text{' commands are prefixed with backslash if missing
        import re
        fixed = re.sub(r'(?<!\\)text\{', r'\\text{', fixed)
        
        return fixed

    async def find_error(self, image_bytes: bytes, transcript: str = "") -> FindErrorResponse:
        """Analyze image crop for mathematical errors."""
        if not self.api_key:
             raise ValueError("OpenAI API key missing")
        
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        
        system_prompt = """You are an expert math tutor analyzing handwritten mathematical work.

CRITICAL: Read ALL text in the image VERY CAREFULLY. Pay special attention to:
- Every digit in every number (don't skip digits)
- All mathematical operators (+, -, ×, ÷, =)
- The complete equation from start to finish

Your task:
1. First, transcribe EXACTLY what you see written in the image
2. Then check if the mathematical statement is correct
3. If incorrect, explain what's wrong and provide the correct answer

Formatting Rules:
- Use LaTeX for all mathematical expressions
- CRITICAL: Use DOUBLE BACKSLASHES for all LaTeX commands to ensure validity in JSON.
  - Example: Use \\text{...} instead of \text{...}
  - Example: Use \\frac{...} instead of \frac{...}
- Keep explanations concise and helpful

Be extremely precise with numbers - if you see "93", don't read it as "43" or "3".
"""
        
        user_text = f"User asked: '{transcript or 'Find my mistake'}'\n\nPlease analyze this mathematical work carefully."
        
        try:
            completion = await self.client.beta.chat.completions.parse(
                model="gpt-5",  # Latest GPT-5 with vision
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
            
            # Post-process to fix LaTeX escaping issues
            result.what_is_wrong = self._fix_latex(result.what_is_wrong)
            result.minimal_fix = self._fix_latex(result.minimal_fix)
            
            # API level success, regardless of math correctness
            result.ok = True 
            return result
        except Exception as e:
            logger.error(f"Find error failed: {e}")
            return FindErrorResponse(ok=False, error=str(e))

    def run_voice_job(self, session, job_id: int):
        """
        Synchronous job runner for voice transcription.
        Called from Celery worker or threading fallback.
        """
        from app.models import VoiceJob, VoiceAudio, VoiceArtifact, VoiceSession
        from app.services.voice.normalizer import MathSpeechNormalizer
        from datetime import datetime
        import time
        
        job = session.get(VoiceJob, job_id)
        if not job:
            logger.error(f"Voice job {job_id} not found")
            return
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.attempts += 1
        session.add(job)
        session.commit()
        
        try:
            # 1. Get audio file
            audio = session.get(VoiceAudio, job.audio_id)
            if not audio:
                raise ValueError("Audio not found for job")
            
            audio_path = audio.storage_url
            logger.info(f"Processing voice job {job_id}: audio={audio_path}")
            
            # 2. Read audio file
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            
            if len(audio_bytes) == 0:
                raise ValueError("Audio file is empty")
            
            # 3. Transcribe using OpenAI Whisper
            start_time = time.time()
            
            # Run async transcription in sync context
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                transcript = loop.run_until_complete(
                    self.transcribe_audio(audio_bytes, filename=audio_path.split("/")[-1])
                )
            finally:
                loop.close()
            
            transcription_time = time.time() - start_time
            logger.info(f"Transcription completed in {transcription_time:.2f}s: {transcript[:100]}...")
            
            # 4. Normalize transcript (convert spoken math to symbols)
            normalizer = MathSpeechNormalizer()
            norm_result = normalizer.normalize(transcript)
            
            normalized_text = norm_result["normalized_text"]
            ambiguity_flags = norm_result.get("ambiguity_flags", [])
            clarifier = norm_result.get("clarifier")
            
            # 5. Create artifact
            artifact = VoiceArtifact(
                job_id=job.id,
                transcript_raw=transcript,
                transcript_confidence=0.95,  # Whisper doesn't return confidence, assume high
                normalized_math_text=normalized_text,
                ambiguity_flags=ambiguity_flags if ambiguity_flags else None,
                clarifier_question=clarifier,
                stt_provider="openai",
                stt_model="whisper-1",
                timings_json={"transcription_ms": int(transcription_time * 1000)}
            )
            session.add(artifact)
            
            # 6. Update job status
            job.status = "done"
            job.finished_at = datetime.utcnow()
            session.add(job)
            
            # 7. Update session status
            voice_session = session.get(VoiceSession, job.voice_session_id)
            if voice_session:
                voice_session.status = "done"
                session.add(voice_session)
            
            session.commit()
            logger.info(f"Voice job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Voice job {job_id} failed: {e}")
            import traceback
            traceback.print_exc()
            
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            session.add(job)
            
            voice_session = session.get(VoiceSession, job.voice_session_id)
            if voice_session:
                voice_session.status = "failed"
                session.add(voice_session)
            
            session.commit()

# Singleton
voice_service = VoiceService()
