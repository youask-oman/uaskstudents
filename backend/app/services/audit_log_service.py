"""
Audit Log Service: Provides audit logging for all admin actions.

Usage:
    from app.services.audit_log_service import audit_log_service
    
    audit_log_service.log_action(
        session=session,
        admin_user_id=current_user.id,
        action="UPDATE",
        entity_type="FEATURE_FLAG",
        entity_id="billing_v2_enabled",
        before_json={"enabled": False},
        after_json={"enabled": True},
        reason="Enabling for 10% rollout",
        request=request,  # Optional FastAPI Request for IP/UA
    )
"""

from typing import Optional, Any
from datetime import datetime
from sqlmodel import Session
from fastapi import Request

from app.models.admin_audit_log import AdminAuditLog


class AuditLogService:
    """Service for creating audit log entries."""
    
    def log_action(
        self,
        session: Session,
        admin_user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        before_json: Optional[dict] = None,
        after_json: Optional[dict] = None,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AdminAuditLog:
        """
        Create an audit log entry.
        
        Args:
            session: Database session
            admin_user_id: ID of the admin performing the action
            action: Action type (CREATE, UPDATE, DELETE, EXECUTE, TOGGLE)
            entity_type: Type of entity (FEATURE_FLAG, CREDIT_PROGRAM, etc.)
            entity_id: ID of the affected entity
            before_json: State before the change
            after_json: State after the change
            reason: Why the action was performed
            idempotency_key: Optional key for idempotent operations
            request: Optional FastAPI Request for IP/UA extraction
        
        Returns:
            The created AdminAuditLog entry
        """
        # Extract request metadata
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        entry = AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=before_json,
            after_json=after_json,
            reason=reason,
            idempotency_key=idempotency_key,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow(),
        )
        
        session.add(entry)
        session.flush()  # Get ID immediately
        
        return entry
    
    def log_flag_change(
        self,
        session: Session,
        admin_user_id: int,
        flag_name: str,
        old_value: Any,
        new_value: Any,
        reason: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AdminAuditLog:
        """Convenience method for logging feature flag changes."""
        return self.log_action(
            session=session,
            admin_user_id=admin_user_id,
            action="TOGGLE",
            entity_type="FEATURE_FLAG",
            entity_id=flag_name,
            before_json={"value": old_value},
            after_json={"value": new_value},
            reason=reason,
            request=request,
        )


# Singleton instance
audit_log_service = AuditLogService()
