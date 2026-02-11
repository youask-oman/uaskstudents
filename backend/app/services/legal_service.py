from __future__ import annotations

from typing import Dict, Optional, Tuple

from sqlmodel import Session, desc, select

from app.models import LegalAcceptance, LegalDocument


def get_latest_published_document(session: Session, key: str) -> Optional[LegalDocument]:
    return session.exec(
        select(LegalDocument)
        .where(LegalDocument.key == key, LegalDocument.status == "published")
        .order_by(desc(LegalDocument.published_at), desc(LegalDocument.id))
    ).first()


def has_user_accepted_document(
    session: Session, *, user_id: int, document_key: str, document_version: str
) -> bool:
    if not document_version:
        return False
    hit = session.exec(
        select(LegalAcceptance).where(
            LegalAcceptance.user_id == user_id,
            LegalAcceptance.document_key == document_key,
            LegalAcceptance.document_version == document_version,
        )
    ).first()
    return hit is not None


def get_latest_user_acceptance(session: Session, *, user_id: int, document_key: str) -> Optional[LegalAcceptance]:
    return session.exec(
        select(LegalAcceptance)
        .where(LegalAcceptance.user_id == user_id, LegalAcceptance.document_key == document_key)
        .order_by(desc(LegalAcceptance.accepted_at), desc(LegalAcceptance.id))
    ).first()


def get_terms_requirement_status(session: Session, *, user_id: int) -> Tuple[bool, Optional[str]]:
    latest_terms = get_latest_published_document(session, "terms_of_service")
    if not latest_terms:
        return False, None
    accepted = has_user_accepted_document(
        session,
        user_id=user_id,
        document_key="terms_of_service",
        document_version=latest_terms.version,
    )
    return (not accepted), latest_terms.version


def get_legal_status_payload(session: Session, *, user_id: int) -> Dict[str, object]:
    requires_terms_acceptance, required_terms_version = get_terms_requirement_status(session, user_id=user_id)

    latest_terms = get_latest_published_document(session, "terms_of_service")
    latest_privacy = get_latest_published_document(session, "privacy_policy")
    latest_terms_acceptance = get_latest_user_acceptance(session, user_id=user_id, document_key="terms_of_service")
    latest_privacy_acceptance = get_latest_user_acceptance(session, user_id=user_id, document_key="privacy_policy")

    return {
        "requires_terms_acceptance": requires_terms_acceptance,
        "required_terms_version": required_terms_version,
        "latest_published": {
            "terms_of_service": (
                {
                    "version": latest_terms.version,
                    "effective_at": latest_terms.effective_at,
                    "published_at": latest_terms.published_at,
                }
                if latest_terms
                else None
            ),
            "privacy_policy": (
                {
                    "version": latest_privacy.version,
                    "effective_at": latest_privacy.effective_at,
                    "published_at": latest_privacy.published_at,
                }
                if latest_privacy
                else None
            ),
        },
        "latest_accepted": {
            "terms_of_service": (
                {
                    "version": latest_terms_acceptance.document_version,
                    "accepted_at": latest_terms_acceptance.accepted_at,
                    "method": latest_terms_acceptance.method,
                }
                if latest_terms_acceptance
                else None
            ),
            "privacy_policy": (
                {
                    "version": latest_privacy_acceptance.document_version,
                    "accepted_at": latest_privacy_acceptance.accepted_at,
                    "method": latest_privacy_acceptance.method,
                }
                if latest_privacy_acceptance
                else None
            ),
        },
    }
