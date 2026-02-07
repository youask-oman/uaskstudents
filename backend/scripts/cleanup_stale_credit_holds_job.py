"""
Cleanup Stale Credit Holds Job

Identifies and releases CreditHold records that have been stuck in HELD status
for longer than the threshold (default 30 minutes).

This prevents credits from being permanently locked due to failed requests.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlmodel import Session, select

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import CreditHold, ReconciliationFinding
from app.services.error_service import error_service
from app.trace import TraceContext
import logging

logger = logging.getLogger("reconciliation")

class CreditHoldCleanupJob:
    def __init__(self, session: Session, threshold_minutes: int = 30):
        self.session = session
        self.threshold_minutes = threshold_minutes
        self.findings: List[ReconciliationFinding] = []
        
    def run(self) -> Dict[str, Any]:
        """Find and release stuck credit holds."""
        trace_id = TraceContext.get_trace_id()
        logger.info(f"Starting credit hold cleanup (trace_id={trace_id})")
        
        start_time = datetime.utcnow()
        threshold_time = start_time - timedelta(minutes=self.threshold_minutes)
        
        # Find stuck holds
        stuck_holds = self.session.exec(
            select(CreditHold).where(
                CreditHold.status == "HELD",
                CreditHold.created_at < threshold_time
            )
        ).all()
        
        released_count = 0
        
        for hold in stuck_holds:
            # Create finding
            finding = ReconciliationFinding(
                finding_type="credit_hold_stuck",
                severity="MEDIUM",
                entity_type="credit_hold",
                entity_id=str(hold.id),
                trace_id=trace_id,
                details_json={
                    "hold_id": hold.id,
                    "user_id": hold.user_id,
                    "amount": hold.amount,
                    "request_id": hold.request_id,
                    "held_since": hold.created_at.isoformat(),
                    "age_minutes": int((start_time - hold.created_at).total_seconds() / 60)
                },
                status="OPEN"
            )
            self.findings.append(finding)
            
            # Release the hold
            hold.status = "RELEASED"
            hold.released_at = start_time
            self.session.add(hold)
            released_count += 1
            
            # Log error
            try:
                error_service.capture_error(
                    session=self.session,
                    component="CreditHoldCleanup",
                    message=f"Released stuck credit hold {hold.id} (age: {int((start_time - hold.created_at).total_seconds() / 60)}min)",
                    severity="MEDIUM",
                    error_code="credit_hold_stuck",
                    context={
                        "hold_id": hold.id,
                        "user_id": hold.user_id,
                        "amount": hold.amount
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log error entry: {e}")
        
        # Commit changes
        for finding in self.findings:
            self.session.add(finding)
        self.session.commit()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        summary = {
            "trace_id": trace_id,
            "started_at": start_time.isoformat(),
            "duration_seconds": duration,
            "threshold_minutes": self.threshold_minutes,
            "stuck_holds_found": len(stuck_holds),
            "holds_released": released_count
        }
        
        logger.info(f"Credit hold cleanup complete: {summary}")
        return summary

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup stale credit holds")
    parser.add_argument("--threshold", type=int, default=30, help="Age threshold in minutes (default: 30)")
    args = parser.parse_args()
    
    with Session(engine) as session:
        job = CreditHoldCleanupJob(session, threshold_minutes=args.threshold)
        result = job.run()
        
        print("\n=== CREDIT HOLD CLEANUP REPORT ===")
        print(f"Trace ID: {result['trace_id']}")
        print(f"Duration: {result['duration_seconds']:.2f}s")
        print(f"Threshold: {result['threshold_minutes']} minutes")
        print(f"Stuck Holds Found: {result['stuck_holds_found']}")
        print(f"Holds Released: {result['holds_released']}")
        
        if result['holds_released'] == 0:
            print("\n✓ No stuck holds found.")
        else:
            print(f"\n⚠ Released {result['holds_released']} stuck holds.")

if __name__ == "__main__":
    main()
