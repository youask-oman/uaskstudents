from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.admin_billing.deps import get_admin_user
from app.database import get_session


router = APIRouter()

LEGACY_PROMPT_TABLES_REMOVED_DETAIL = (
    "Legacy prompt tables were removed. Use /api/v1/admin/prompt-registry/* endpoints."
)
LEGACY_PLAN_MUTATION_DETAIL = (
    "Legacy plan mutation endpoints are removed. Use /api/v1/admin/plans endpoints."
)


@router.post("/solve_questions_batch", include_in_schema=False)
async def solve_questions_batch_removed(
    request: Request,
    body: Dict[str, Any] = Body(...),
    user_id: int = Query(...),
    session: Session = Depends(get_session),
):
    raise HTTPException(
        status_code=410,
        detail={
            "code": "batch_disabled",
            "message": "Batch question splitting is disabled. Submit one question to /api/v1/solve_v3_stream.",
        },
    )


@router.post("/solve/batch", include_in_schema=False)
async def solve_batch_endpoint_removed(
    body: Dict[str, Any] = Body(...),
    user_id: int = Query(...),
    session: Session = Depends(get_session),
):
    raise HTTPException(
        status_code=410,
        detail={
            "code": "batch_disabled",
            "message": "Batch solve is disabled. Submit one question to /api/v1/solve_v3_stream.",
        },
    )


@router.get("/admin/prompt-assets", include_in_schema=False)
async def list_prompt_assets_removed():
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.put("/admin/plans/{plan_id}/prompt-links", include_in_schema=False)
async def update_plan_links_removed(plan_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.get("/admin/plans/{plan_id}/prompt-links", include_in_schema=False)
async def get_plan_links_removed(plan_id: int):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.get("/admin/prompts", include_in_schema=False)
async def admin_get_prompts_removed(admin=Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.get("/admin/prompts/{template_id}/versions", include_in_schema=False)
async def admin_get_prompt_versions_removed(template_id: int, admin=Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.post("/admin/prompts/{template_id}/save", include_in_schema=False)
async def admin_save_prompt_removed(template_id: int, admin=Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.post("/admin/prompts/versions/{version_id}/deploy", include_in_schema=False)
async def admin_deploy_prompt_removed(version_id: int, admin=Depends(get_admin_user)):
    raise HTTPException(status_code=410, detail=LEGACY_PROMPT_TABLES_REMOVED_DETAIL)


@router.post("/admin/plans", include_in_schema=False)
async def admin_save_plan_removed(
    plan: Dict[str, Any] = Body(...),
    db: Session = Depends(get_session),
    admin=Depends(get_admin_user),
):
    raise HTTPException(status_code=410, detail=LEGACY_PLAN_MUTATION_DETAIL)


@router.delete("/admin/plans/{plan_id}", include_in_schema=False)
async def admin_delete_plan_removed(
    plan_id: int,
    db: Session = Depends(get_session),
    admin=Depends(get_admin_user),
):
    raise HTTPException(status_code=410, detail=LEGACY_PLAN_MUTATION_DETAIL)
