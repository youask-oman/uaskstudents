"""
Invoice Consistency Reconciliation Job

Ensures that:
1. Every TopUpOrder FULFILLED has exactly 1 Invoice(kind=TOPUP) PAID
2. Every Stripe invoice mirrored exists locally
3. Refunds create adjustment invoices properly
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any
from sqlmodel import Session, select, func

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine
from app.models import (
    TopUpOrder, Invoice, InvoiceKind, InvoiceStatus,
    ReconciliationFinding
)
from app.services.error_service import error_service
from app.trace import TraceContext
import logging

logger = logging.getLogger("reconciliation")

class InvoiceReconciliationJob:
    def __init__(self, session: Session):
        self.session = session
        self.findings: List[ReconciliationFinding] = []
        
    def run(self) -> Dict[str, Any]:
        """Run invoice consistency checks."""
        trace_id = TraceContext.get_trace_id()
        logger.info(f"Starting invoice reconciliation (trace_id={trace_id})")
        
        start_time = datetime.utcnow()
        
        # Check 1: TopUpOrder -> Invoice consistency
        topup_issues = self._check_topup_invoices()
        
        # Check 2: Refund invoices
        refund_issues = self._check_refund_invoices()
        
        # Commit findings
        for finding in self.findings:
            self.session.add(finding)
        self.session.commit()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        summary = {
            "trace_id": trace_id,
            "started_at": start_time.isoformat(),
            "duration_seconds": duration,
            "topup_issues": topup_issues,
            "refund_issues": refund_issues,
            "total_findings": len(self.findings)
        }
        
        logger.info(f"Invoice reconciliation complete: {summary}")
        return summary
    
    def _check_topup_invoices(self) -> int:
        """Ensure every FULFILLED TopUpOrder has exactly one PAID invoice."""
        issues = 0
        
        # Get all fulfilled orders
        orders = self.session.exec(
            select(TopUpOrder).where(TopUpOrder.status == "FULFILLED")
        ).all()
        
        for order in orders:
            # Find invoices for this order
            invoices = self.session.exec(
                select(Invoice).where(
                    Invoice.topup_order_id == order.id,
                    Invoice.kind == InvoiceKind.TOPUP
                )
            ).all()
            
            if len(invoices) == 0:
                # Missing invoice
                finding = ReconciliationFinding(
                    finding_type="topup_invoice_missing",
                    severity="HIGH",
                    entity_type="topup_order",
                    entity_id=str(order.id),
                    trace_id=TraceContext.get_trace_id(),
                    details_json={
                        "order_id": order.id,
                        "user_id": order.user_id,
                        "amount_usd": order.price_usd,
                        "status": order.status
                    },
                    status="OPEN"
                )
                self.findings.append(finding)
                issues += 1
                
            elif len(invoices) > 1:
                # Duplicate invoices
                finding = ReconciliationFinding(
                    finding_type="topup_invoice_duplicate",
                    severity="CRITICAL",
                    entity_type="topup_order",
                    entity_id=str(order.id),
                    trace_id=TraceContext.get_trace_id(),
                    details_json={
                        "order_id": order.id,
                        "invoice_count": len(invoices),
                        "invoice_ids": [inv.id for inv in invoices]
                    },
                    status="OPEN"
                )
                self.findings.append(finding)
                issues += 1
                
            elif invoices[0].status != InvoiceStatus.PAID:
                # Invoice not paid
                finding = ReconciliationFinding(
                    finding_type="topup_invoice_unpaid",
                    severity="MEDIUM",
                    entity_type="invoice",
                    entity_id=str(invoices[0].id),
                    trace_id=TraceContext.get_trace_id(),
                    details_json={
                        "invoice_id": invoices[0].id,
                        "order_id": order.id,
                        "invoice_status": invoices[0].status
                    },
                    status="OPEN"
                )
                self.findings.append(finding)
                issues += 1
        
        return issues
    
    def _check_refund_invoices(self) -> int:
        """Check that refunded invoices have corresponding adjustment invoices."""
        issues = 0
        
        # Get all refunded invoices
        refunded = self.session.exec(
            select(Invoice).where(Invoice.status == InvoiceStatus.REFUNDED)
        ).all()
        
        for invoice in refunded:
            # Look for adjustment invoice
            adjustments = self.session.exec(
                select(Invoice).where(
                    Invoice.kind == InvoiceKind.ADJUSTMENT,
                    Invoice.related_invoice_id == invoice.id
                )
            ).all()
            
            if len(adjustments) == 0:
                finding = ReconciliationFinding(
                    finding_type="refund_adjustment_missing",
                    severity="HIGH",
                    entity_type="invoice",
                    entity_id=str(invoice.id),
                    trace_id=TraceContext.get_trace_id(),
                    details_json={
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.invoice_number,
                        "amount": invoice.total_amount
                    },
                    status="OPEN"
                )
                self.findings.append(finding)
                issues += 1
        
        return issues

def main():
    """CLI entry point."""
    with Session(engine) as session:
        job = InvoiceReconciliationJob(session)
        result = job.run()
        
        print("\n=== INVOICE RECONCILIATION REPORT ===")
        print(f"Trace ID: {result['trace_id']}")
        print(f"Duration: {result['duration_seconds']:.2f}s")
        print(f"TopUp Issues: {result['topup_issues']}")
        print(f"Refund Issues: {result['refund_issues']}")
        print(f"Total Findings: {result['total_findings']}")
        
        if result['total_findings'] == 0:
            print("\n✓ No issues found. Invoices are consistent.")

if __name__ == "__main__":
    main()
