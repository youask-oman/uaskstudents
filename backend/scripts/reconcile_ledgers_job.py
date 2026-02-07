"""
Ledger Balance Reconciliation Job

This job ensures that the credit ledger system is internally consistent:
- UsageLedger debits/credits match CreditLot balances
- Subscription grants are properly tracked
- No drift or double-charging has occurred

Run daily via cron or on-demand via admin endpoint.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlmodel import Session, select, func

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import (
    Subscription, CreditLot, UsageLedger, ReconciliationFinding,
    User
)
from app.services.error_service import error_service
from app.trace import TraceContext
import logging

logger = logging.getLogger("reconciliation")

class LedgerReconciliationJob:
    def __init__(self, session: Session):
        self.session = session
        self.findings: List[ReconciliationFinding] = []
        
    def run(self, subscription_ids: List[int] = None) -> Dict[str, Any]:
        """
        Run reconciliation for all subscriptions or specific ones.
        Returns summary of findings.
        """
        trace_id = TraceContext.get_trace_id()
        logger.info(f"Starting ledger reconciliation (trace_id={trace_id})")
        
        start_time = datetime.utcnow()
        
        # Get subscriptions to check
        query = select(Subscription)
        if subscription_ids:
            query = query.where(Subscription.id.in_(subscription_ids))
        
        subscriptions = self.session.exec(query).all()
        
        checked_count = 0
        mismatch_count = 0
        
        for sub in subscriptions:
            checked_count += 1
            has_mismatch = self._check_subscription_balance(sub)
            if has_mismatch:
                mismatch_count += 1
        
        # Commit all findings
        for finding in self.findings:
            self.session.add(finding)
        self.session.commit()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        summary = {
            "trace_id": trace_id,
            "started_at": start_time.isoformat(),
            "duration_seconds": duration,
            "subscriptions_checked": checked_count,
            "mismatches_found": mismatch_count,
            "findings": [
                {
                    "id": f.id,
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "entity_type": f.entity_type,
                    "entity_id": f.entity_id
                }
                for f in self.findings
            ]
        }
        
        logger.info(f"Ledger reconciliation complete: {summary}")
        return summary
    
    def _check_subscription_balance(self, subscription: Subscription) -> bool:
        """
        Check if subscription's credit balance matches lot balances.
        Returns True if mismatch found.
        """
        user_id = subscription.user_id
        subscription_id = subscription.id
        
        # Calculate expected balance from UsageLedger
        # DEBIT entries reduce balance, CREDIT/REFUND entries increase it
        usage_debits = self.session.exec(
            select(func.sum(UsageLedger.amount))
            .where(
                UsageLedger.subscription_id == subscription_id,
                UsageLedger.transaction_type == "DEBIT"
            )
        ).one() or 0.0
        
        usage_credits = self.session.exec(
            select(func.sum(UsageLedger.amount))
            .where(
                UsageLedger.subscription_id == subscription_id,
                UsageLedger.transaction_type.in_(["CREDIT", "REFUND"])
            )
        ).one() or 0.0
        
        # Calculate actual balance from CreditLots
        lot_balance = self.session.exec(
            select(func.sum(CreditLot.credits_remaining))
            .where(
                CreditLot.user_id == user_id,
                CreditLot.status == "ACTIVE"
            )
        ).one() or 0.0
        
        # Expected balance = lot_balance should equal (initial credits - debits + credits)
        # But we need initial credits. Let's use total credits from lots instead.
        total_lot_credits = self.session.exec(
            select(func.sum(CreditLot.credits_total))
            .where(CreditLot.user_id == user_id)
        ).one() or 0.0
        
        # Expected remaining = total - debits + credits
        expected_remaining = total_lot_credits - usage_debits + usage_credits
        
        # Allow small floating point tolerance
        tolerance = 0.01
        mismatch = abs(expected_remaining - lot_balance)
        
        if mismatch > tolerance:
            # Create finding
            finding = ReconciliationFinding(
                finding_type="ledger_balance_mismatch",
                severity="HIGH",
                entity_type="subscription",
                entity_id=str(subscription.id),
                trace_id=TraceContext.get_trace_id(),
                details_json={
                    "user_id": user_id,
                    "subscription_id": subscription.id,
                    "expected_remaining": round(expected_remaining, 2),
                    "actual_lot_balance": round(lot_balance, 2),
                    "mismatch_amount": round(mismatch, 2),
                    "total_lot_credits": round(total_lot_credits, 2),
                    "usage_debits": round(usage_debits, 2),
                    "usage_credits": round(usage_credits, 2)
                },
                status="OPEN"
            )
            self.findings.append(finding)
            
            # Also log as SystemErrorEntry
            try:
                error_service.capture_error(
                    session=self.session,
                    component="LedgerReconciliation",
                    message=f"Balance mismatch for subscription {subscription.id}: expected {expected_remaining:.2f}, actual {lot_balance:.2f}",
                    severity="HIGH",
                    error_code="ledger_reconcile_mismatch",
                    context={
                        "subscription_id": subscription.id,
                        "user_id": user_id,
                        "mismatch": mismatch
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log error entry: {e}")
            
            return True
        
        return False

def main():
    """CLI entry point for manual execution."""
    with Session(engine) as session:
        job = LedgerReconciliationJob(session)
        result = job.run()
        
        print("\n=== LEDGER RECONCILIATION REPORT ===")
        print(f"Trace ID: {result['trace_id']}")
        print(f"Duration: {result['duration_seconds']:.2f}s")
        print(f"Subscriptions Checked: {result['subscriptions_checked']}")
        print(f"Mismatches Found: {result['mismatches_found']}")
        
        if result['findings']:
            print("\nFINDINGS:")
            for f in result['findings']:
                print(f"  - [{f['severity']}] {f['finding_type']}: {f['entity_type']} {f['entity_id']}")
        else:
            print("\n✓ No issues found. Ledger is healthy.")

if __name__ == "__main__":
    main()
