from typing import Dict, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.database import get_session
from app.services.pricing_service import pricing_service


router = APIRouter()

TierValue = Literal["FREE", "STANDARD", "RESEARCH"]
InputTypeValue = Literal["text", "snap", "voice"]
AssetTypeValue = Literal["none", "image", "pdf"]


class EstimateAddons(BaseModel):
    ocr: bool = False
    voice: bool = False
    verify: bool = False
    plot: bool = False


class CreditsEstimateRequest(BaseModel):
    tier: TierValue
    input_type: InputTypeValue
    asset_type: AssetTypeValue = "none"
    question_count: int = Field(default=1, ge=1, le=100)
    addons: EstimateAddons = Field(default_factory=EstimateAddons)


class CreditsEstimateBreakdown(BaseModel):
    tier_base: float
    ocr: float
    voice: float
    verify: float
    plot: float
    asset_type_addon: float = 0.0


class CreditsEstimateResponse(BaseModel):
    total_credits: float
    per_question_credits: float
    breakdown: CreditsEstimateBreakdown
    pricing_version: str


def _resolve_pricing(session: Session) -> Dict[str, Any]:
    config = pricing_service.get_pricing_config(session)
    solve_pricing = dict(config.solve_pricing or {})
    if not solve_pricing:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PRICING_CONFIG_MISSING",
                "message": "Solve pricing config is missing from DB.",
            },
        )
    return solve_pricing


@router.post("/credits/estimate", response_model=CreditsEstimateResponse)
async def estimate_credits(
    body: CreditsEstimateRequest,
    session: Session = Depends(get_session),
):
    solve_pricing = _resolve_pricing(session)
    tiers = solve_pricing.get("tiers") or {}
    addons_cfg = solve_pricing.get("addons") or {}
    asset_addons = solve_pricing.get("asset_addons") or {}
    pricing_version = str(solve_pricing.get("pricing_version") or "unknown")

    if body.tier not in tiers:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_TIER", "message": f"No pricing configured for tier {body.tier}."},
        )

    ocr_enabled = bool(body.addons.ocr or body.input_type == "snap")
    voice_enabled = bool(body.addons.voice or body.input_type == "voice")
    verify_enabled = bool(body.addons.verify)
    plot_enabled = bool(body.addons.plot)

    tier_base = float(tiers.get(body.tier, 0.0))
    ocr_cost = float(addons_cfg.get("ocr", 0.0)) if ocr_enabled else 0.0
    voice_cost = float(addons_cfg.get("voice", 0.0)) if voice_enabled else 0.0
    verify_cost = float(addons_cfg.get("verify", 0.0)) if verify_enabled else 0.0
    plot_cost = float(addons_cfg.get("plot", 0.0)) if plot_enabled else 0.0
    asset_type_addon = float(asset_addons.get(body.asset_type, 0.0))

    per_question = tier_base + ocr_cost + voice_cost + verify_cost + plot_cost + asset_type_addon
    total = per_question * float(body.question_count)

    return CreditsEstimateResponse(
        total_credits=total,
        per_question_credits=per_question,
        pricing_version=pricing_version,
        breakdown=CreditsEstimateBreakdown(
            tier_base=tier_base,
            ocr=ocr_cost,
            voice=voice_cost,
            verify=verify_cost,
            plot=plot_cost,
            asset_type_addon=asset_type_addon,
        ),
    )

