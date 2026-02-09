"""
Credit Program Service: Manages credit programs and monthly grants.

This service provides:
1. Program enrollment/unenrollment
2. Monthly credit grant issuance (idempotent)
3. Entitlement checks
4. Purchase bonus application

Phase 3 of Billing Redesign.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select

from app.models import User, CreditLot
from app.models.credit_program_models import (
    CreditProgramDefinition,
    CreditProgramEnrollment,
    CreditProgramGrantLog,
)
from app.services.billing_logger import log_grant, log_billing_error
from app.services.billing_metrics import inc_granted, inc_billing_error


class CreditProgramService:
    """
    Manages credit programs, enrollments, and grants.
    """
    
    def get_program_by_slug(
        self,
        session: Session,
        slug: str,
    ) -> Optional[CreditProgramDefinition]:
        """Fetch a program by its slug."""
        return session.exec(
            select(CreditProgramDefinition)
            .where(CreditProgramDefinition.slug == slug)
        ).first()
    
    def enroll_user(
        self,
        session: Session,
        user_id: int,
        program_id: int,
    ) -> CreditProgramEnrollment:
        """
        Enroll a user in a credit program.
        
        If already enrolled, returns existing enrollment.
        """
        # Check for existing active enrollment
        existing = session.exec(
            select(CreditProgramEnrollment)
            .where(
                CreditProgramEnrollment.user_id == user_id,
                CreditProgramEnrollment.program_id == program_id,
                CreditProgramEnrollment.status == "active",
            )
        ).first()
        
        if existing:
            return existing
        
        # Create new enrollment
        enrollment = CreditProgramEnrollment(
            user_id=user_id,
            program_id=program_id,
            status="active",
            started_at=datetime.utcnow(),
        )
        session.add(enrollment)
        session.flush()
        
        return enrollment
    
    def end_enrollment(
        self,
        session: Session,
        enrollment_id: int,
    ) -> CreditProgramEnrollment:
        """End a user's enrollment in a program."""
        enrollment = session.get(CreditProgramEnrollment, enrollment_id)
        if enrollment and enrollment.status == "active":
            enrollment.status = "ended"
            enrollment.ended_at = datetime.utcnow()
            session.add(enrollment)
            session.flush()
        return enrollment
    
    def grant_monthly_credits(
        self,
        session: Session,
        user_id: int,
        program_id: int,
        month: str,  # Format: "2026-02"
    ) -> Optional[CreditLot]:
        """
        Grant monthly credits for a program enrollment.
        
        This is idempotent - calling multiple times for the same
        (user_id, program_id, month) returns the existing lot.
        
        Args:
            session: Database session
            user_id: User to grant credits to
            program_id: Program granting the credits
            month: Month string (e.g., "2026-02")
        
        Returns:
            CreditLot if granted, None if already granted or not enrolled
        """
        # 1. Find active enrollment
        enrollment = session.exec(
            select(CreditProgramEnrollment)
            .where(
                CreditProgramEnrollment.user_id == user_id,
                CreditProgramEnrollment.program_id == program_id,
                CreditProgramEnrollment.status == "active",
            )
        ).first()
        
        if not enrollment:
            return None
        
        # 2. Idempotency check
        existing_grant = session.exec(
            select(CreditProgramGrantLog)
            .where(
                CreditProgramGrantLog.enrollment_id == enrollment.id,
                CreditProgramGrantLog.grant_month == month,
            )
        ).first()
        
        if existing_grant:
            # Already granted - return existing lot
            return session.get(CreditLot, existing_grant.credit_lot_id)
        
        # 3. Get program config
        program = session.get(CreditProgramDefinition, program_id)
        if not program or program.status != "active":
            return None
        
        if program.monthly_gift_credits <= 0:
            return None
        
        # 4. Calculate expiry
        expiry_days = program.gift_expiry_window_days or 30
        expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        
        # 5. Create credit lot
        lot = CreditLot(
            user_id=user_id,
            credits_total=program.monthly_gift_credits,
            credits_remaining=program.monthly_gift_credits,
            lot_type="GIFT",
            status="ACTIVE",
            source="CREDIT_PROGRAM",
            source_program_id=program_id,
            expires_at=expires_at,
            purchased_at=datetime.utcnow(),
        )
        session.add(lot)
        session.flush()
        
        # 6. Create grant log (for idempotency)
        grant_log = CreditProgramGrantLog(
            enrollment_id=enrollment.id,
            user_id=user_id,
            program_id=program_id,
            grant_month=month,
            credits_granted=program.monthly_gift_credits,
            credit_lot_id=lot.id,
            expires_at=expires_at,
        )
        session.add(grant_log)
        
        # 7. Update enrollment
        enrollment.last_grant_month = month
        enrollment.updated_at = datetime.utcnow()
        session.add(enrollment)
        
        session.flush()
        
        # 8. Log and metrics
        log_grant(
            user_id=user_id,
            credits_granted=program.monthly_gift_credits,
            grant_type="GIFT",
            program_id=program_id,
        )
        inc_granted("GIFT")
        
        return lot
    
    def get_user_entitlements(
        self,
        session: Session,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Get combined entitlements for a user from all active enrollments.
        
        Entitlements are merged from all active programs.
        For boolean flags, True takes precedence.
        For numeric limits, the maximum is used.
        
        Returns:
            Dict of entitlement flags and limits
        """
        # Default entitlements
        entitlements = {
            "allow_ocr": False,
            "allow_plot": False,
            "allow_voice": False,
            "allow_verify": False,
            "allow_research_tier": False,
            "max_daily_solves": 10,
            "max_daily_research": 0,
        }
        
        # Get all active enrollments with programs
        enrollments = session.exec(
            select(CreditProgramEnrollment)
            .where(
                CreditProgramEnrollment.user_id == user_id,
                CreditProgramEnrollment.status == "active",
            )
        ).all()
        
        for enrollment in enrollments:
            program = session.get(CreditProgramDefinition, enrollment.program_id)
            if not program or not program.entitlements:
                continue
            
            prog_ent = program.entitlements
            
            # Merge boolean flags (True dominates)
            for key in ["allow_ocr", "allow_plot", "allow_voice", "allow_verify", "allow_research_tier"]:
                if prog_ent.get(key, False):
                    entitlements[key] = True
            
            # Merge numeric limits (max dominates)
            for key in ["max_daily_solves", "max_daily_research"]:
                prog_val = prog_ent.get(key, 0)
                if prog_val > entitlements.get(key, 0):
                    entitlements[key] = prog_val
        
        return entitlements
    
    def apply_purchase_bonus(
        self,
        session: Session,
        user_id: int,
        credits_purchased: Decimal,
        payment_id: Optional[str] = None,
    ) -> Optional[CreditLot]:
        """
        Apply purchase bonus based on enrolled program rules.
        
        Checks all active enrollments for bonus rules matching
        the purchased amount.
        
        Returns:
            Bonus CreditLot if applicable, None otherwise
        """
        enrollments = session.exec(
            select(CreditProgramEnrollment)
            .where(
                CreditProgramEnrollment.user_id == user_id,
                CreditProgramEnrollment.status == "active",
            )
        ).all()
        
        best_bonus = Decimal("0")
        best_expiry_days = 60
        
        for enrollment in enrollments:
            program = session.get(CreditProgramDefinition, enrollment.program_id)
            if not program or not program.purchase_bonus_rules:
                continue
            
            rules = program.purchase_bonus_rules
            # Rules format: {"100": {"bonus_credits": 10, "bonus_expiry_days": 60}}
            for threshold_str, rule in rules.items():
                threshold = Decimal(threshold_str)
                if credits_purchased >= threshold:
                    bonus = Decimal(str(rule.get("bonus_credits", 0)))
                    if bonus > best_bonus:
                        best_bonus = bonus
                        best_expiry_days = rule.get("bonus_expiry_days", 60)
        
        if best_bonus <= 0:
            return None
        
        # Create bonus lot
        expires_at = datetime.utcnow() + timedelta(days=best_expiry_days)
        lot = CreditLot(
            user_id=user_id,
            credits_total=best_bonus,
            credits_remaining=best_bonus,
            lot_type="PROMO",
            status="ACTIVE",
            source="PURCHASE_BONUS",
            source_payment_id=payment_id,
            expires_at=expires_at,
            purchased_at=datetime.utcnow(),
        )
        session.add(lot)
        session.flush()
        
        log_grant(
            user_id=user_id,
            credits_granted=best_bonus,
            grant_type="PROMO",
        )
        inc_granted("PROMO")
        
        return lot


# Singleton
credit_program_service = CreditProgramService()
