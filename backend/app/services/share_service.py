from __future__ import annotations

import hashlib
import os
import secrets
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Optional

from sqlmodel import Session, select

from app.models import ChatMessage, ChatSession, SolutionShare, SolverOutputAttempt


_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 60
_rate_lock = threading.Lock()
_rate_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _sanitize_public_payload(value: Any) -> Any:
    if isinstance(value, dict):
        banned_keys = {
            "user_id",
            "email",
            "full_name",
            "role",
            "credits",
            "credits_balance",
            "wallet",
            "plan",
            "subscription",
            "telemetry",
            "_telemetry",
            "request_id",
            "provider",
            "provider_model",
            "model",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "latency_ms",
            "debug",
            "debug_info",
            "token",
            "session_token",
            "ip_address",
            "last_ip",
            "billing",
        }
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            key_norm = str(key).strip().lower()
            if key_norm in banned_keys:
                continue
            cleaned[key] = _sanitize_public_payload(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_public_payload(item) for item in value]
    return value


class ShareService:
    def get_attempt_by_attempt_id(self, session: Session, attempt_id: str) -> Optional[SolverOutputAttempt]:
        if not attempt_id:
            return None
        return session.exec(
            select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)
        ).first()

    def get_owner_attempt(self, session: Session, attempt_id: str, owner_user_id: int) -> Optional[SolverOutputAttempt]:
        if not attempt_id:
            return None
        return session.exec(
            select(SolverOutputAttempt).where(
                SolverOutputAttempt.attempt_id == attempt_id,
                SolverOutputAttempt.user_id == owner_user_id,
            )
        ).first()

    def get_share_for_attempt(self, session: Session, attempt_id: str, owner_user_id: int) -> Optional[SolutionShare]:
        return session.exec(
            select(SolutionShare).where(
                SolutionShare.attempt_id == attempt_id,
                SolutionShare.owner_user_id == owner_user_id,
            )
        ).first()

    def _new_token(self) -> str:
        # >= 128 bits entropy (token_urlsafe(24) ~= 192 bits raw before encoding)
        return secrets.token_urlsafe(24)

    def _build_share_url(self, token: str, request_origin: Optional[str] = None) -> str:
        base = (
            os.environ.get("PUBLIC_APP_URL")
            or os.environ.get("NEXT_PUBLIC_APP_URL")
            or request_origin
            or "http://localhost:3000"
        )
        return f"{base.rstrip('/')}/share/{token}"

    def read_state(
        self,
        *,
        share: Optional[SolutionShare],
        attempt_id: str,
        request_origin: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not share:
            return {
                "attempt_id": attempt_id,
                "visibility": "PRIVATE",
                "share_url": None,
                "revoked": False,
            }
        is_public = share.visibility == "PUBLIC" and share.revoked_at is None and bool(share.share_token)
        share_url = self._build_share_url(share.share_token, request_origin) if is_public and share.share_token else None
        return {
            "attempt_id": attempt_id,
            "visibility": "PUBLIC" if is_public else "PRIVATE",
            "share_url": share_url,
            "revoked": bool(share.revoked_at),
        }

    def upsert_visibility(
        self,
        *,
        session: Session,
        attempt: SolverOutputAttempt,
        owner_user_id: int,
        visibility: str,
    ) -> SolutionShare:
        share = self.get_share_for_attempt(session, attempt.attempt_id, owner_user_id)
        now = _utcnow()
        if not share:
            share = SolutionShare(
                solver_output_attempt_id=int(attempt.id or 0),
                attempt_id=attempt.attempt_id,
                owner_user_id=owner_user_id,
                visibility="PRIVATE",
                created_at=now,
                updated_at=now,
            )
            session.add(share)

        visibility_norm = (visibility or "PRIVATE").strip().upper()
        share.visibility = "PUBLIC" if visibility_norm == "PUBLIC" else "PRIVATE"
        share.updated_at = now
        share.solver_output_attempt_id = int(attempt.id or share.solver_output_attempt_id)

        if share.visibility == "PUBLIC":
            if not share.share_token:
                token = self._new_token()
                share.share_token = token
                share.share_token_hash = _sha256(token)
            share.revoked_at = None
        else:
            share.revoked_at = now

        session.add(share)
        session.commit()
        session.refresh(share)
        return share

    def resolve_public_share(self, session: Session, token: str) -> Optional[SolutionShare]:
        token_hash = _sha256(token or "")
        share = session.exec(
            select(SolutionShare).where(SolutionShare.share_token_hash == token_hash)
        ).first()
        if not share:
            # Backward-compatible fallback for rows created before hash population.
            share = session.exec(
                select(SolutionShare).where(SolutionShare.share_token == token)
            ).first()
            if share and not share.share_token_hash and share.share_token:
                share.share_token_hash = _sha256(share.share_token)
                share.updated_at = _utcnow()
                session.add(share)
                try:
                    session.commit()
                except Exception:
                    session.rollback()
        if not share:
            return None
        if not share.share_token or not secrets.compare_digest(share.share_token, token):
            return None
        if share.visibility != "PUBLIC":
            return None
        if share.revoked_at is not None:
            return None
        if share.expires_at is not None and share.expires_at <= _utcnow():
            return None
        return share

    def mark_view(self, session: Session, share: SolutionShare) -> None:
        share.last_viewed_at = _utcnow()
        share.view_count = int(share.view_count or 0) + 1
        share.updated_at = _utcnow()
        session.add(share)
        session.commit()

    def allow_public_request(self, client_ip: str) -> bool:
        ip = (client_ip or "unknown").strip() or "unknown"
        now_ts = datetime.utcnow().timestamp()
        with _rate_lock:
            bucket = _rate_hits[ip]
            while bucket and now_ts - bucket[0] > _RATE_WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= _RATE_MAX_REQUESTS:
                return False
            bucket.append(now_ts)
            return True

    def _resolve_attempt_for_share(self, session: Session, share: SolutionShare) -> Optional[SolverOutputAttempt]:
        attempt = session.get(SolverOutputAttempt, share.solver_output_attempt_id)
        if not attempt:
            attempt = self.get_attempt_by_attempt_id(session, share.attempt_id)
        if not attempt:
            return None
        if attempt.status != "success":
            return None
        if attempt.session_id:
            exists = session.get(ChatSession, attempt.session_id)
            if not exists:
                return None
        return attempt

    def _resolve_public_paper(self, session: Session, attempt: SolverOutputAttempt) -> Dict[str, Any]:
        if attempt.message_id:
            message = session.get(ChatMessage, attempt.message_id)
            if message and isinstance(message.structured_data, dict):
                return _sanitize_public_payload(message.structured_data)

        if isinstance(attempt.validation_json, dict):
            return _sanitize_public_payload(attempt.validation_json)
        if isinstance(attempt.llm_raw_response, dict):
            return _sanitize_public_payload(attempt.llm_raw_response)

        return {
            "result": attempt.extracted_answer or "",
            "raw_solution_text": attempt.raw_solution_text or "",
            "status": attempt.status,
        }

    def build_public_view_model(self, session: Session, share: SolutionShare) -> Optional[Dict[str, Any]]:
        attempt = self._resolve_attempt_for_share(session, share)
        if not attempt:
            return None
        paper = self._resolve_public_paper(session, attempt)
        problem = {
            "original": attempt.input_text_raw,
            "normalized": attempt.input_text_normalized,
        }
        return {
            "attempt_id": attempt.attempt_id,
            "paper": paper,
            "problem": _sanitize_public_payload(problem),
            "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
            "visibility": "PUBLIC",
        }


share_service = ShareService()
