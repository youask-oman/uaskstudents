import contextvars
import uuid
from typing import Optional

# Context variables for tracing
_trace_id = contextvars.ContextVar("trace_id", default=None)
_request_id = contextvars.ContextVar("request_id", default=None)
_user_id = contextvars.ContextVar("user_id", default=None)
_subscription_id = contextvars.ContextVar("subscription_id", default=None)
_attempt_id = contextvars.ContextVar("attempt_id", default=None)
_phase = contextvars.ContextVar("phase", default=None)
_status = contextvars.ContextVar("status", default=None)

class TraceContext:
    @staticmethod
    def set(trace_id: str, request_id: Optional[str] = None, user_id: Optional[int] = None, 
            subscription_id: Optional[str] = None, attempt_id: Optional[str] = None, 
            phase: Optional[str] = None, status: Optional[str] = None):
        _trace_id.set(trace_id)
        _request_id.set(request_id)
        _user_id.set(user_id)
        _subscription_id.set(subscription_id)
        _attempt_id.set(attempt_id)
        _phase.set(phase)
        _status.set(status)

    @staticmethod
    def get_trace_id() -> str:
        tid = _trace_id.get()
        if not tid:
            tid = str(uuid.uuid4())
            _trace_id.set(tid)
        return tid

    @staticmethod
    def get_request_id() -> Optional[str]:
        return _request_id.get()

    @staticmethod
    def get_user_id() -> Optional[int]:
        return _user_id.get()
    
    @staticmethod
    def get_subscription_id() -> Optional[str]:
        return _subscription_id.get()

    @staticmethod
    def get_all() -> dict:
        return {
            "trace_id": _trace_id.get(),
            "request_id": _request_id.get(),
            "user_id": _user_id.get(),
            "subscription_id": _subscription_id.get(),
            "attempt_id": _attempt_id.get(),
            "phase": _phase.get(),
            "status": _status.get()
        }
