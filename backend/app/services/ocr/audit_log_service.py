from datetime import datetime
from typing import Optional, List
from sqlmodel import Session
from app.models import OCRAuditEvent

class AuditLogService:
    def log_ocr_decision(
        self,
        session: Session,
        user_id: Optional[int],
        upload_id: Optional[int],
        crop_id: Optional[int],
        job_id: Optional[str],
        routing_engine: str,
        reasons: List[str],
        vlm_type: Optional[str] = None,
        confidence_before: Optional[float] = None,
        cost_estimate: Optional[float] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ):
        event = OCRAuditEvent(
            user_id=user_id,
            upload_id=upload_id,
            crop_id=crop_id,
            job_id=job_id,
            routing_engine_chosen=routing_engine,
            vlm_type_chosen=vlm_type,
            reasons=reasons,
            confidence_score_before=confidence_before,
            cost_estimate_usd=cost_estimate,
            provider=provider,
            provider_model=model
        )
        session.add(event)
        session.flush()

    def update_latency(self, session: Session, job_id: str, latency_ms: int, artifact_id: int):
        from sqlmodel import select
        # Update most recent and relevant audit event
        stmt = select(OCRAuditEvent).where(OCRAuditEvent.job_id == job_id).order_by(OCRAuditEvent.created_at.desc())
        event = session.exec(stmt).first()
        if event:
            event.latency_ms = latency_ms
            event.artifact_id = artifact_id
            session.add(event)
            session.flush()

audit_log_service = AuditLogService()
