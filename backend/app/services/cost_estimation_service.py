from typing import Optional, Tuple
from sqlmodel import Session
from app.models import RequestEvent
from app.services.provider_pricing_service import provider_pricing_service

class CostEstimationService:
    def estimate_provider_cost(
        self, 
        session: Session, 
        event: RequestEvent
    ) -> Tuple[float, Optional[int]]:
        """
        Calculates the ESTIMATED provider cost for a request event based on historical pricing.
        Returns (cost_usd, pricing_record_id).
        """
        if not event.provider or not event.model:
            return 0.0, None

        pricing = provider_pricing_service.get_active_price(
            session, 
            event.provider, 
            event.model, 
            event.created_at
        )

        if not pricing:
            # Fallback for unknown models to avoid 0 cost?
            # Or return 0 and log warning?
            # For Phase 0, let's look for a "default" fallback or return 0
            return 0.0, None

        in_tokens = event.tokens_in or 0
        out_tokens = event.tokens_out or 0
        
        # Logic: (tokens / 1M) * price_per_1M
        cost_in = (in_tokens / 1_000_000.0) * pricing.price_in_per_1m
        cost_out = (out_tokens / 1_000_000.0) * pricing.price_out_per_1m
        
        # Determine cached tokens if any (RequestEvent doesn't explicitly split cached/uncached input usually)
        # If we add cached tokens later, we use price_cached_in_per_1m.
        
        total_cost = cost_in + cost_out
        return total_cost, pricing.id

    def backfill_missing_costs(self, session: Session, limit: int = 1000):
        """
        Helper for Phase 0 to populate cost_usd on historical events if null.
        """
        # This would be a maintenance script logic
        pass

cost_estimation_service = CostEstimationService()
