import os
import time
import hashlib
from datetime import datetime
from typing import Optional
from openai import OpenAI
from app.models import VoiceSession, VoiceAudio, VoiceJob, VoiceArtifact
from app.services.voice.normalizer import MathSpeechNormalizer
from sqlmodel import Session, select

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class VoiceService:
    def __init__(self):
        self.normalizer = MathSpeechNormalizer()

    def transcribe_audio(self, db: Session, audio_id: int) -> VoiceArtifact:
        audio = db.get(VoiceAudio, audio_id)
        if not audio:
            raise ValueError(f"Audio {audio_id} not found")

        # In production: Download from storage_url
        # Use OpenAI Whisper STT
        start_time = time.time()
        with open(audio.storage_url, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        transcript_raw = response.text
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Normalize 
        norm_result = self.normalizer.normalize(transcript_raw)
        
        artifact = VoiceArtifact(
            job_id=0, # Set by run_voice_job
            transcript_raw=transcript_raw,
            transcript_confidence=0.95,
            normalized_math_text=norm_result["normalized_text"],
            ambiguity_flags={"flags": norm_result["ambiguity_flags"]},
            clarifier_question=norm_result["clarifier"],
            stt_provider="openai",
            stt_model="whisper-1",
            timings_json={"stt_ms": latency_ms}
        )
        return artifact

    def run_voice_job(self, db: Session, job_id: int):
        job = db.get(VoiceJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.add(job)
        db.commit()

        try:
            artifact = self.transcribe_audio(db, job.audio_id)
            artifact.job_id = job.id
            
            db.add(artifact)
            job.status = "done"
            job.finished_at = datetime.utcnow()
            
            # Update session status
            session = db.get(VoiceSession, job.voice_session_id)
            if session:
                session.status = "done"
                db.add(session)
                
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            
            session = db.get(VoiceSession, job.voice_session_id)
            if session:
                session.status = "failed"
                db.add(session)
        
        db.add(job)
        db.commit()

voice_service = VoiceService()
