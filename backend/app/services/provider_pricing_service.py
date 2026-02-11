from datetime import datetime
from typing import Optional, List, Dict
from sqlmodel import Session, select, desc
from app.models import ProviderModelPricing

class ProviderPricingService:
    def get_active_price(
        self, 
        session: Session, 
        provider: str, 
        model: str, 
        timestamp: Optional[datetime] = None
    ) -> Optional[ProviderModelPricing]:
        """
        Finds the pricing record active at the given timestamp (or now).
        """
        ts = timestamp or datetime.utcnow()
        provider = provider.strip().lower()
        model = model.strip().lower()

        # Find record where effective_from <= ts AND (effective_to IS NULL OR effective_to > ts)
        # We sort by effective_from desc to get the most recent valid start
        stmt = select(ProviderModelPricing).where(
            ProviderModelPricing.provider == provider,
            ProviderModelPricing.model == model,
            ProviderModelPricing.effective_from <= ts
        ).order_by(desc(ProviderModelPricing.effective_from))
        
        candidates = session.exec(stmt).all()
        
        for cand in candidates:
            if cand.effective_to is None or cand.effective_to > ts:
                return cand
                
        return None

    def list_pricing_history(
        self, 
        session: Session, 
        provider: str = None, 
        model: str = None
    ) -> List[ProviderModelPricing]:
        stmt = select(ProviderModelPricing)
        if provider:
            stmt = stmt.where(ProviderModelPricing.provider == provider)
        if model:
            stmt = stmt.where(ProviderModelPricing.model == model)
        stmt = stmt.order_by(desc(ProviderModelPricing.effective_from))
        return list(session.exec(stmt).all())

    def update_price(
        self,
        session: Session,
        provider: str,
        model: str,
        price_in_per_1m: float,
        price_out_per_1m: float,
        price_cached_in_per_1m: float = 0.0,
        admin_user_id: Optional[int] = None
    ) -> ProviderModelPricing:
        """
        Updates pricing by terminating the current active price and creating a new one.
        """
        now = datetime.utcnow()
        provider = provider.strip().lower()
        model = model.strip().lower()
        
        # 1. Close current active pricing
        current = self.get_active_price(session, provider, model, now)
        if current:
            # If the current price started effectively in the future (unlikely but possible), disable it?
            # Or if it started in the past, close it now.
            current.effective_to = now
            session.add(current)
        
        # 2. Create new pricing
        new_price = ProviderModelPricing(
            provider=provider,
            model=model,
            price_in_per_1m=price_in_per_1m,
            price_out_per_1m=price_out_per_1m,
            price_cached_in_per_1m=price_cached_in_per_1m,
            effective_from=now,
            effective_to=None,
            created_by=admin_user_id
        )
        session.add(new_price)
        session.commit()
        session.refresh(new_price)
        return new_price

    def seed_defaults(self, session: Session):
        """
        Seeds default pricing if table is empty.
        Using data from analytics_service.py
        """
        # Check if any data exists
        if session.exec(select(ProviderModelPricing)).first():
            return

        defaults = [
            # OpenAI
            ("openai", "gpt-4o", 5.0, 15.0),
            ("openai", "gpt-5-mini", 0.15, 0.60),
            ("openai", "o1-mini", 3.0, 12.0), # Approximate
            ("openai", "o1-preview", 15.0, 60.0), # Approximate
            ("gemini", "gemini-flash", 0.35, 1.05), # Aprox
        ]
        
        now = datetime.utcnow()
        for p, m, pin, pout in defaults:
            entry = ProviderModelPricing(
                provider=p,
                model=m,
                price_in_per_1m=pin,
                price_out_per_1m=pout,
                effective_from=now
            )
            session.add(entry)
        
        session.commit()

provider_pricing_service = ProviderPricingService()
