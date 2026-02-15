from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select, desc

from app.database import get_session
from app.admin_billing.deps import get_admin_user
from app.models import SystemConfigVersion, User
from app.services.admin_config_service import admin_config_service
from app.services.audit_log_service import audit_log_service
from app.services.ocr.ocr_runtime_config_service import (
    OCR_CONFIG_TYPE,
    OcrRuntimeConfig,
    get_active_ocr_config,
    resolve_prompt_entry,
    resolve_schema_entry,
    list_active_prompt_entries,
    list_active_schema_entries,
)


router = APIRouter(prefix="/api/admin/ocr-configuration", tags=["admin", "ocr"])


class OcrConfigPayload(BaseModel):
    local_engine_enabled: bool = True
    openai_engine_enabled: bool = True
    openai_model: str = Field(default="gpt-5-mini")
    openai_system_prompt_key: str = Field(default="openai_ocr_system_prompt_v1.txt")
    openai_schema_key: str = Field(default="openai_image_extract_v1.schema.json")
    dedupe_window_hours: int = Field(default=24, ge=1)
    ocr_hold_ttl_minutes: int = Field(default=10, ge=1)
    rate_limit_extract_per_min: int = Field(default=10, ge=1)
    local_ocr_credit: int = Field(default=2, ge=1)
    openai_ocr_credit: int = Field(default=3, ge=1)
    solve_credit: int = Field(default=3, ge=1)


class OcrConfigUpdateRequest(BaseModel):
    reason: str = Field(min_length=3)
    local_engine_enabled: Optional[bool] = None
    openai_engine_enabled: Optional[bool] = None
    openai_model: Optional[str] = None
    openai_system_prompt_key: Optional[str] = None
    openai_schema_key: Optional[str] = None
    dedupe_window_hours: Optional[int] = Field(default=None, ge=1)
    ocr_hold_ttl_minutes: Optional[int] = Field(default=None, ge=1)
    rate_limit_extract_per_min: Optional[int] = Field(default=None, ge=1)
    local_ocr_credit: Optional[int] = Field(default=None, ge=1)
    openai_ocr_credit: Optional[int] = Field(default=None, ge=1)
    solve_credit: Optional[int] = Field(default=None, ge=1)


class ActivateConfigRequest(BaseModel):
    reason: str = Field(min_length=3)


def _config_to_payload(config: OcrRuntimeConfig) -> OcrConfigPayload:
    return OcrConfigPayload(
        local_engine_enabled=config.local_engine_enabled,
        openai_engine_enabled=config.openai_engine_enabled,
        openai_model=config.resolved_openai_model(),
        openai_system_prompt_key=config.openai_system_prompt_key,
        openai_schema_key=config.openai_schema_key,
        dedupe_window_hours=config.dedupe_window_hours,
        ocr_hold_ttl_minutes=config.ocr_hold_ttl_minutes,
        rate_limit_extract_per_min=config.rate_limit_extract_per_min,
        local_ocr_credit=config.local_ocr_credit,
        openai_ocr_credit=config.openai_ocr_credit,
        solve_credit=config.solve_credit,
    )


def _validate_config(session: Session, payload: OcrConfigPayload) -> Dict[str, Any]:
    if not (payload.local_engine_enabled or payload.openai_engine_enabled):
        raise HTTPException(status_code=422, detail="At least one OCR engine must be enabled")
    if payload.openai_engine_enabled and not payload.openai_model:
        raise HTTPException(status_code=422, detail="openai_model is required when OpenAI OCR is enabled")

    prompt_key = (payload.openai_system_prompt_key or "").strip()
    schema_key = (payload.openai_schema_key or "").strip()
    prompt_entry = resolve_prompt_entry(session, prompt_key)
    if not prompt_entry:
        raise HTTPException(status_code=422, detail="Invalid openai_system_prompt_key")

    schema_entry = resolve_schema_entry(session, schema_key)
    if not schema_entry:
        raise HTTPException(status_code=422, detail="Invalid openai_schema_key")

    return {
        "prompt_entry": prompt_entry,
        "schema_entry": schema_entry,
    }


def _latest_version(session: Session) -> Optional[SystemConfigVersion]:
    return session.exec(
        select(SystemConfigVersion)
        .where(SystemConfigVersion.config_type == OCR_CONFIG_TYPE)
        .order_by(desc(SystemConfigVersion.version))
    ).first()


@router.get("", response_model=Dict[str, Any])
def get_ocr_configuration(
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    runtime_cfg = get_active_ocr_config(session)
    latest = _latest_version(session)

    prompt_entry = resolve_prompt_entry(session, runtime_cfg.openai_system_prompt_key)
    schema_entry = resolve_schema_entry(session, runtime_cfg.openai_schema_key)

    prompt_entries = list_active_prompt_entries(session)
    schema_entries = list_active_schema_entries(session)

    return {
        "config": _config_to_payload(runtime_cfg).model_dump(),
        "meta": {
            "version_id": latest.id if latest else None,
            "version": latest.version if latest else None,
            "updated_at": latest.created_at if latest else None,
            "updated_by_user_id": latest.created_by if latest else None,
        },
        "resolved": {
            "prompt_template": {
                "id": getattr(prompt_entry, "id", None),
                "key": getattr(prompt_entry, "prompt_id", None),
                "version": getattr(prompt_entry, "version", None),
                "updated_at": getattr(prompt_entry, "updated_at", None),
            } if prompt_entry else None,
            "json_schema": {
                "id": getattr(schema_entry, "id", None),
                "key": getattr(schema_entry, "schema_id", None),
                "version": getattr(schema_entry, "version", None),
                "updated_at": getattr(schema_entry, "updated_at", None),
            } if schema_entry else None,
        },
        "prompt_templates": [
            {
                "id": p.id,
                "key": p.prompt_id,
                "version": p.version,
                "updated_at": p.updated_at,
                "mode": str(p.mode),
                "role": str(p.role),
            }
            for p in prompt_entries
        ],
        "json_schemas": [
            {
                "id": s.id,
                "key": s.schema_id,
                "version": s.version,
                "updated_at": s.updated_at,
                "name": (s.content or {}).get("name") if isinstance(s.content, dict) else None,
            }
            for s in schema_entries
        ],
        "history": [
            {
                "id": v.id,
                "version": v.version,
                "created_at": v.created_at,
                "created_by": v.created_by,
                "change_msg": v.change_msg,
            }
            for v in admin_config_service.get_history(session, OCR_CONFIG_TYPE, limit=10)
        ],
    }


@router.put("", response_model=Dict[str, Any])
def update_ocr_configuration(
    body: OcrConfigUpdateRequest,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    runtime_cfg = get_active_ocr_config(session)
    current_payload = _config_to_payload(runtime_cfg)
    merged_dict = current_payload.model_dump()
    updates = body.model_dump(exclude_none=True)
    updates.pop("reason", None)
    merged_dict.update(updates)

    new_payload = OcrConfigPayload(**merged_dict)
    _validate_config(session, new_payload)

    new_version = admin_config_service.update_config(
        session=session,
        config_type=OCR_CONFIG_TYPE,
        new_value=new_payload.model_dump(),
        user_id=admin.id,
        change_msg=body.reason,
    )

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="UPDATE",
        entity_type="OCR_CONFIGURATION",
        entity_id=str(new_version.id),
        before_json=current_payload.model_dump(),
        after_json=new_payload.model_dump(),
        reason=body.reason,
        request=request,
    )
    session.commit()

    return {
        "status": "ok",
        "version_id": new_version.id,
        "version": new_version.version,
        "config": new_payload.model_dump(),
    }


@router.post("/activate/{config_id}", response_model=Dict[str, Any])
def activate_ocr_configuration(
    config_id: int,
    body: ActivateConfigRequest,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    current_cfg = get_active_ocr_config(session)
    current_payload = _config_to_payload(current_cfg)

    target_version = session.get(SystemConfigVersion, config_id)
    if not target_version:
        raise HTTPException(status_code=404, detail="Configuration version not found")
    if target_version.config_type != OCR_CONFIG_TYPE:
        raise HTTPException(status_code=400, detail="Selected version is not an OCR configuration")
    try:
        target_payload = OcrConfigPayload(**(target_version.value or {}))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid OCR configuration payload in version: {exc}")
    _validate_config(session, target_payload)

    new_version = admin_config_service.revert_config(
        session=session,
        version_id=config_id,
        user_id=admin.id,
        reason_msg=body.reason,
    )

    audit_log_service.log_action(
        session=session,
        admin_user_id=admin.id,
        action="ACTIVATE",
        entity_type="OCR_CONFIGURATION",
        entity_id=str(config_id),
        before_json=current_payload.model_dump(),
        after_json=new_version.value,
        reason=body.reason,
        request=request,
    )
    session.commit()

    return {
        "status": "ok",
        "version_id": new_version.id,
        "version": new_version.version,
        "config": new_version.value,
    }
