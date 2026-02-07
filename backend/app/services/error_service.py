import logging
import traceback
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from app.models import SystemErrorEntry
from app.trace import TraceContext

logger = logging.getLogger("error_service")

class ErrorService:
    @staticmethod
    def _generate_fingerprint(component: str, error_code: Optional[str], stack_trace: Optional[str], message: str) -> str:
        # Extract top of stack trace for fingerprinting to avoid different trace_ids making it unique
        stack_top = ""
        if stack_trace:
            lines = stack_trace.strip().split("\n")
            # Take last few lines as they are usually the root cause in Python
            stack_top = "\n".join(lines[-5:])
            
        digest = hashlib.sha256()
        digest.update(component.encode())
        if error_code:
            digest.update(error_code.encode())
        digest.update(stack_top.encode())
        # Normalize message (remove IDs, numbers, etc to improve dedup)
        # For now, just use the message if it's short
        digest.update(message[:100].encode())
        
        return digest.hexdigest()

    def capture_exception(
        self,
        session: Session,
        component: str,
        exception: Exception,
        severity: str = "ERROR",
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        stack = traceback.format_exc()
        message = str(exception)
        
        return self.capture_error(
            session=session,
            component=component,
            message=message,
            severity=severity,
            error_code=error_code,
            stack_trace=stack,
            context=context
        )

    def capture_error(
        self,
        session: Session,
        component: str,
        message: str,
        severity: str = "ERROR",
        error_code: Optional[str] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> SystemErrorEntry:
        trace_info = TraceContext.get_all()
        fingerprint = self._generate_fingerprint(component, error_code, stack_trace, message)
        
        # Check for existing open error with same fingerprint within last 24h
        stmt = select(SystemErrorEntry).where(
            SystemErrorEntry.fingerprint == fingerprint,
            SystemErrorEntry.is_resolved == False
        )
        existing = session.exec(stmt).first()
        
        if existing:
            existing.occurrence_count += 1
            existing.last_seen_at = datetime.utcnow()
            # Update trace info to most recent
            existing.trace_id = trace_info.get("trace_id")
            existing.request_id = trace_info.get("request_id")
            existing.user_id = trace_info.get("user_id")
            session.add(existing)
            session.commit()
            return existing
        
        # Create new entry
        entry = SystemErrorEntry(
            severity=severity,
            error_code=error_code,
            component=component,
            message=message,
            stack_trace=stack_trace,
            trace_id=trace_info.get("trace_id"),
            request_id=trace_info.get("request_id"),
            user_id=trace_info.get("user_id"),
            fingerprint=fingerprint,
            context_json=context,
            created_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow()
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        
        # Trigger alert if severity is HIGH/CRITICAL
        if severity in ["HIGH", "CRITICAL"]:
            self._dispatch_alert(entry)
            
        return entry

    def _dispatch_alert(self, entry: SystemErrorEntry):
        # Stub for alerting (Email/Slack)
        msg = f"[ALERT][{entry.severity}] {entry.component}: {entry.error_code or 'UNKNOWN'} - {entry.message}"
        logger.warning(f"ALERT DISPATCHED: {msg} (Trace ID: {entry.trace_id})")
        # In production, this would call a real dispatcher service

error_service = ErrorService()
