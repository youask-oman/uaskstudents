from typing import Optional, Tuple
from sqlmodel import Session
from app.models import RequestEvent
from app.services.provider_pricing_service import provider_pricing_service

class CostEstimationService:
    def estimate_provider_cost(
        self, 
        session: Session, 
        event: RequestEvent
    ) -> Tuple[Optional[float], Optional[int]]:
        """
        Calculates the ESTIMATED provider cost for a request event based on historical pricing.
        Returns (cost_usd, pricing_record_id).
        
        If pricing is missing, returns (None, None) and logs an error.
        Caller should mark the cost as NEEDS_REVIEW.
        """
        if not event.provider or not event.model:
            return None, None

        pricing = provider_pricing_service.get_active_price(
            session, 
            event.provider, 
            event.model, 
            event.created_at
        )

        if not pricing:
            # FAIL SAFE: No pricing available
            # Log error and return None to signal needs review
            from app.services.error_service import error_service
            from app.trace import TraceContext
            
            try:
                error_service.capture_error(
                    session=session,
                    component="CostEstimation",
                    message=f"No pricing found for {event.provider}/{event.model} at {event.created_at}",
                    severity="HIGH",
                    error_code="pricing_missing",
                    context={
                        "request_id": event.request_id,
                        "provider": event.provider,
                        "model": event.model,
                        "timestamp": event.created_at.isoformat()
                    }
                )
            except Exception as e:
                # Don't fail cost estimation if error logging fails
                import logging
                logging.getLogger("cost_estimation").error(f"Failed to log pricing_missing error: {e}")
            
            return None, None

        in_tokens = event.tokens_in or 0
        out_tokens = event.tokens_out or 0
        
        # Logic: (tokens / 1M) * price_per_1M
        cost_in = (in_tokens / 1_000_000.0) * pricing.price_in_per_1m
        cost_out = (out_tokens / 1_000_000.0) * pricing.price_out_per_1m
        
        # TODO: If we add cached tokens later, use price_cached_in_per_1m
        
        total_cost = cost_in + cost_out
        return total_cost, pricing.id

    def backfill_missing_costs(self, session: Session, limit: int = 1000):
        """
        Helper for Phase 0 to populate cost_usd on historical events if null.
        """
        # This would be a maintenance script logic
        pass

cost_estimation_service = CostEstimationService()
