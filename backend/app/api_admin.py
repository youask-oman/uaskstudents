
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, desc, SQLModel
from sqlalchemy import text as sql_text
from pydantic import BaseModel
from jose import JWTError, jwt

from app.database import get_session
from app.models import User, SystemConfigVersion, BillingLedger, PromoCode
from app.services.admin_config_service import admin_config_service
from app.services.pricing_service import pricing_service
from app.auth import SECRET_KEY, ALGORITHM
from app.services.whatsapp import whatsapp_service
from app.services.whatsapp.whatsapp_state import get_whatsapp_events, get_redis
from app.worker import celery_app
from fastapi.responses import StreamingResponse
import asyncio
import io
from datetime import datetime
import os
from pathlib import Path

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# --- Models ---
class ConfigUpdate(BaseModel):
    value: Dict[str, Any]
    change_msg: str

class RevertRequest(BaseModel):
    version_id: int
    reason: str

class CalculatorRequest(BaseModel):
    action_type: str
    est_input: int
    est_output: int
    act_input: int
    act_output: int

class CalculatorResponse(BaseModel):
    estimate: Dict[str, Any]
    actual: Dict[str, Any]
    delta_credits: float

class PromoCodeCreateRequest(BaseModel):
    code: str
    discount_percent: int
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = True

class PromoCodeUpdateRequest(BaseModel):
    discount_percent: Optional[int] = None
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None

class RunJobRequest(BaseModel):
    task: str
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None

# --- Auth Dependencies (Self-Contained) ---
def get_current_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session)
) -> User:
    """Extract user from JWT token in Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        print("[Auth] Missing or invalid Authorization header")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            print("[Auth] Token missing 'sub'")
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError as e:
        print(f"[Auth] JWT Decode Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        print(f"[Auth] User not found for email: {email}")
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_admin_user(user: User = Depends(get_current_user)):
    if user.role not in ["admin", "devops", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

def get_staff_user(user: User = Depends(get_current_user)):
    if user.role not in ["admin", "devops", "support", "finance", "superadmin"]:
        raise HTTPException(status_code=403, detail="Staff privileges required")
    return user


def _resolve_admin_from_request(request: Request, session: Session) -> User:
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.replace("Bearer ", "")
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.role not in ["admin", "devops", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

# --- Endpoints ---
# IMPORTANT: Specific routes must come BEFORE parameterized routes

@admin_router.post("/calculator", response_model=CalculatorResponse)
def calculate_transaction(
    req: CalculatorRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Simulate a transaction with ACTIVE config"""
    
    # Estimate
    est_cred, est_usd, est_tok, est_fee, _ = pricing_service.calculate_estimate_token_cost(
        req.action_type, req.est_input, req.est_output, session
    )
    
    # Actual
    act_cred, act_usd, act_tok, act_fee, _ = pricing_service.calculate_actual_token_cost(
        req.action_type, req.act_input, req.act_output, session
    )
    
    delta = act_cred - est_cred
    
    return CalculatorResponse(
        estimate={
            "credits": est_cred, "usd": est_usd, "tokens": est_tok, "fee": est_fee
        },
        actual={
            "credits": act_cred, "usd": act_usd, "tokens": act_tok, "fee": act_fee
        },
        delta_credits=delta
    )

@admin_router.get("/diagnostics/credits")
def get_user_credit_diagnostics(
    email: str = Query(None),
    user_id: int = Query(None),
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Check credit status for a user by email or ID"""
    from app.services.credit_wallet_service import credit_wallet_service
    from app.models import CreditLot
    from datetime import datetime
    
    # Find user by email or ID
    target_user = None
    if email:
        target_user = session.exec(select(User).where(User.email == email)).first()
    elif user_id:
        target_user = session.exec(select(User).where(User.id == user_id)).first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    balance = credit_wallet_service.get_balance(session, target_user.id)
    
    # Get all credit lots
    lots = session.exec(
        select(CreditLot).where(CreditLot.user_id == target_user.id)
    ).all()
    
    now = datetime.utcnow()
    
    return {
        "user_id": target_user.id,
        "email": target_user.email,
        "name": target_user.name,
        "current_balance": balance,
        "total_lots": len(lots),
        "lots": [
            {
                "id": lot.id,
                "remaining": lot.credits_remaining,
                "total": lot.credits_total,
                "source": lot.source,
                "expires_at": lot.expires_at.isoformat() if lot.expires_at else None,
                "is_expired": lot.expires_at < now if lot.expires_at else False,
                "is_active": lot.is_active
            }
            for lot in lots
        ]
    }

@admin_router.post("/credits/seed")
def seed_user_credits(
    email: str = Query(None),
    user_id: int = Query(None),
    amount: float = Query(1000.0),
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Seed credits for testing by email or ID"""
    from app.services.credit_wallet_service import credit_wallet_service
    
    # Find user by email or ID
    target_user = None
    if email:
        target_user = session.exec(select(User).where(User.email == email)).first()
    elif user_id:
        target_user = session.exec(select(User).where(User.id == user_id)).first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    lot = credit_wallet_service.add_credits(
        session, target_user.id, amount, "admin_seed", expiry_days=365
    )
    
    new_balance = credit_wallet_service.get_balance(session, target_user.id)
    
    return {
        "success": True,
        "user_id": target_user.id,
        "email": target_user.email,
        "name": target_user.name,
        "lot_id": lot.id,
        "amount_added": amount,
        "new_balance": new_balance
    }

@admin_router.get("/diagnostics/transactions/{target_user_id}")
def get_user_transactions(
    target_user_id: int,
    limit: int = 20,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get recent transactions for a specific user"""
    results = session.exec(
        select(BillingLedger)
        .where(BillingLedger.user_id == target_user_id)
        .order_by(desc(BillingLedger.created_at))
        .limit(limit)
    ).all()
    
    return {"user_id": target_user_id, "count": len(results), "transactions": results}

@admin_router.get("/transactions")
def get_transactions(
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[int] = None,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Search transaction ledger"""
    query = select(BillingLedger).order_by(desc(BillingLedger.created_at))
    
    if user_id:
        query = query.where(BillingLedger.user_id == user_id)
    if action_type:
        query = query.where(BillingLedger.action_type == action_type)
    if status:
        query = query.where(BillingLedger.status == status)
        
    # Pagination
    offset = (page - 1) * page_size
    results = session.exec(query.offset(offset).limit(page_size)).all()
    
    return {"data": results, "page": page, "page_size": page_size}

@admin_router.post("/config/revert")
def revert_config(
    req: RevertRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Revert to a previous version (creates new version)"""
    return admin_config_service.revert_config(session, req.version_id, user.id, req.reason)

@admin_router.get("/config/history/{config_type}")
def get_config_history(
    config_type: str,
    limit: int = 50,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get version history"""
    return admin_config_service.get_history(session, config_type, limit)

# Parameterized routes LAST
@admin_router.get("/config/{config_type}")
def get_config(
    config_type: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_staff_user)
):
    """Get active config (pricing/tokens)"""
    return admin_config_service.get_active_config(session, config_type)

@admin_router.put("/config/{config_type}")
def update_config(
    config_type: str,
    update: ConfigUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_admin_user)
):
    """Update config (creates new version)"""
    new_version = admin_config_service.update_config(
        session, config_type, update.value, user.id, update.change_msg
    )
    return new_version


# ------------------------------------------------------------------
# WhatsApp Admin Aliases (Token-authenticated)
# ------------------------------------------------------------------

@admin_router.get("/whatsapp/status")
def admin_whatsapp_status(
    request: Request,
    session: Session = Depends(get_session),
):
    _resolve_admin_from_request(request, session)
    return whatsapp_service.get_status()


@admin_router.post("/whatsapp/initialize")
async def admin_whatsapp_initialize(
    request: Request,
    session: Session = Depends(get_session),
):
    _resolve_admin_from_request(request, session)
    return await whatsapp_service.initialize()


@admin_router.post("/whatsapp/disconnect")
async def admin_whatsapp_disconnect(
    request: Request,
    session: Session = Depends(get_session),
):
    _resolve_admin_from_request(request, session)
    return await whatsapp_service.disconnect()


@admin_router.get("/whatsapp/monitor")
def admin_whatsapp_monitor(
    request: Request,
    limit: int = 50,
    phone: Optional[str] = None,
    direction: Optional[str] = None,
    session: Session = Depends(get_session),
):
    _resolve_admin_from_request(request, session)
    queue_len = None
    queue_len_whatsapp = None
    try:
        queue_len = get_redis().llen("celery")
        queue_len_whatsapp = get_redis().llen("whatsapp")
    except Exception:
        queue_len = None
        queue_len_whatsapp = None
    return {
        "bot_status": whatsapp_service.get_status(),
        "queue_length": queue_len,
        "queue_length_whatsapp": queue_len_whatsapp,
        "events": get_whatsapp_events(limit=limit, phone=phone, direction=direction),
        "server_time": datetime.utcnow().isoformat() + "Z",
    }


@admin_router.get("/whatsapp/monitor/export")
def admin_whatsapp_monitor_export(
    request: Request,
    limit: int = 200,
    phone: Optional[str] = None,
    direction: Optional[str] = None,
    session: Session = Depends(get_session),
):
    _resolve_admin_from_request(request, session)
    events = get_whatsapp_events(limit=limit, phone=phone, direction=direction)
    rows = ["timestamp,direction,type,from,to,message_id,upload_id,ok,text,error"]
    for e in events:
        row = [
            str(e.get("timestamp", "")),
            str(e.get("direction", "")),
            str(e.get("type", "")),
            str(e.get("from", "")),
            str(e.get("to", "")),
            str(e.get("message_id", "")),
            str(e.get("upload_id", "")),
            str(e.get("ok", "")),
            str(e.get("text", "")).replace("\\n", " ").replace(",", " "),
            str(e.get("error", "")).replace("\\n", " ").replace(",", " "),
        ]
        rows.append(",".join(row))

    content = "\n".join(rows)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=whatsapp_monitor.csv"},
    )


@admin_router.get("/whatsapp/monitor/stream")
async def admin_whatsapp_monitor_stream(
    request: Request,
    session: Session = Depends(get_session),
):
    _resolve_admin_from_request(request, session)

    async def event_generator():
        pubsub = get_redis().pubsub()
        pubsub.subscribe("whatsapp:events:stream")
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"
                await asyncio.sleep(0.1)
        finally:
            try:
                pubsub.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ------------------------------------------------------------------
# Data Explorer Aliases
# ------------------------------------------------------------------

@admin_router.get("/db/tables", response_model=List[str])
def admin_list_db_tables_alias(
    admin: User = Depends(get_admin_user),
):
    return sorted(list(SQLModel.metadata.tables.keys()))


@admin_router.get("/db/table/{table_name}", response_model=List[Dict[str, Any]])
def admin_get_db_table_alias(
    table_name: str,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    if table_name not in SQLModel.metadata.tables:
        raise HTTPException(status_code=404, detail="Table not found")
    table = SQLModel.metadata.tables[table_name]
    if table.schema:
        qualified_name = f"\"{table.schema}\".\"{table.name}\""
    else:
        qualified_name = f"\"{table.name}\""
    try:
        if "id" in table.c:
            query = sql_text(
                f"SELECT * FROM {qualified_name} ORDER BY \"id\" {order.upper()} LIMIT :limit OFFSET :offset"
            )
        else:
            query = sql_text(f"SELECT * FROM {qualified_name} LIMIT :limit OFFSET :offset")
        result = db.execute(query, {"limit": limit, "offset": offset})
        rows = result.mappings().all()
        return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read table {table_name}: {exc}")


# ------------------------------------------------------------------
# Promo Codes (Admin)
# ------------------------------------------------------------------

@admin_router.get("/promo-codes")
def admin_list_promo_codes(
    limit: int = Query(200, ge=1, le=1000),
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    promos = session.exec(
        select(PromoCode)
        .order_by(desc(PromoCode.created_at))
        .limit(limit)
    ).all()
    return [
        {
            "id": promo.id,
            "code": promo.code,
            "discount_percent": promo.discount_percent,
            "valid_from": promo.valid_from.isoformat() if promo.valid_from else None,
            "valid_until": promo.valid_until.isoformat() if promo.valid_until else None,
            "is_active": promo.is_active,
            "max_uses": promo.max_uses,
            "current_uses": promo.current_uses,
            "created_at": promo.created_at.isoformat() if promo.created_at else None,
        }
        for promo in promos
    ]


@admin_router.post("/promo-codes")
def admin_create_promo_code(
    request: PromoCodeCreateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    code_upper = request.code.strip().upper()
    if not code_upper:
        raise HTTPException(status_code=400, detail="Promo code required")
    if request.discount_percent < 0 or request.discount_percent > 100:
        raise HTTPException(status_code=400, detail="discount_percent must be 0-100")

    existing = session.exec(select(PromoCode).where(PromoCode.code == code_upper)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Promo code already exists")

    promo = PromoCode(
        code=code_upper,
        discount_percent=request.discount_percent,
        valid_until=request.valid_until,
        max_uses=request.max_uses,
        is_active=True if request.is_active is None else request.is_active,
    )
    session.add(promo)
    session.commit()
    session.refresh(promo)
    return {"status": "created", "code": promo.code, "id": promo.id}


@admin_router.put("/promo-codes/{promo_id}")
def admin_update_promo_code(
    promo_id: int,
    request: PromoCodeUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    promo = session.get(PromoCode, promo_id)
    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    fields_set = request.model_fields_set

    if "discount_percent" in fields_set:
        if request.discount_percent is None:
            raise HTTPException(status_code=400, detail="discount_percent required")
        if request.discount_percent < 0 or request.discount_percent > 100:
            raise HTTPException(status_code=400, detail="discount_percent must be 0-100")
        promo.discount_percent = request.discount_percent

    if "valid_until" in fields_set:
        promo.valid_until = request.valid_until

    if "max_uses" in fields_set:
        promo.max_uses = request.max_uses

    if "is_active" in fields_set:
        promo.is_active = request.is_active if request.is_active is not None else promo.is_active

    session.add(promo)
    session.commit()
    session.refresh(promo)
    return {"status": "updated", "id": promo.id}


# ------------------------------------------------------------------
# Jobs & Workers (Admin)
# ------------------------------------------------------------------

_ALLOWED_ADMIN_TASKS = {
    "ocr_hold_release_job",
    "subscription_grant_job",
    "subscription_expiry_job",
}


@admin_router.get("/jobs/status")
def admin_jobs_status(
    admin: User = Depends(get_admin_user),
):
    server_time = datetime.utcnow().isoformat()
    queue_lengths: Dict[str, Optional[int]] = {}
    try:
        redis = get_redis()
        for queue in ["celery", "whatsapp"]:
            try:
                queue_lengths[queue] = redis.llen(queue)
            except Exception:
                queue_lengths[queue] = None
    except Exception:
        queue_lengths = {"celery": None, "whatsapp": None}

    workers = []
    inspect_error = None
    try:
        inspector = celery_app.control.inspect(timeout=1.0)
        ping = inspector.ping() or {}
        active = inspector.active() or {}
        scheduled = inspector.scheduled() or {}
        reserved = inspector.reserved() or {}
        stats = inspector.stats() or {}
        worker_names = sorted(set(list(ping.keys()) + list(active.keys()) + list(scheduled.keys()) + list(reserved.keys())))
        for name in worker_names:
            workers.append({
                "name": name,
                "ping": name in ping,
                "active": len(active.get(name, []) or []),
                "scheduled": len(scheduled.get(name, []) or []),
                "reserved": len(reserved.get(name, []) or []),
                "stats": stats.get(name) or {},
            })
    except Exception as exc:
        inspect_error = str(exc)

    beat_schedule = []
    try:
        for name, entry in (celery_app.conf.beat_schedule or {}).items():
            beat_schedule.append({
                "name": name,
                "task": entry.get("task"),
                "schedule": str(entry.get("schedule")),
                "args": entry.get("args", []),
                "kwargs": entry.get("kwargs", {}),
            })
    except Exception as exc:
        beat_schedule = []
        inspect_error = inspect_error or str(exc)

    return {
        "server_time": server_time,
        "queues": queue_lengths,
        "workers": workers,
        "beat_schedule": beat_schedule,
        "inspect_error": inspect_error,
    }


@admin_router.post("/jobs/run")
def admin_run_job(
    request: RunJobRequest,
    admin: User = Depends(get_admin_user),
):
    task = (request.task or "").strip()
    if task not in _ALLOWED_ADMIN_TASKS:
        raise HTTPException(status_code=400, detail="Task not allowed")
    try:
        result = celery_app.send_task(task, args=request.args or [], kwargs=request.kwargs or {})
        return {"status": "queued", "task": task, "task_id": result.id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {exc}")


@admin_router.get("/jobs/logs")
def admin_jobs_logs(
    log_type: str = Query("worker", pattern="^(worker|celery|whatsapp)$"),
    lines: int = Query(300, ge=50, le=5000),
    admin: User = Depends(get_admin_user),
):
    base_dir = Path(__file__).resolve().parents[1]
    logs_dir = base_dir / "logs"
    env_map = {
        "worker": os.environ.get("WORKER_LOG_PATH"),
        "celery": os.environ.get("CELERY_LOG_PATH"),
        "whatsapp": os.environ.get("WHATSAPP_LOG_PATH"),
    }
    candidate_paths = []
    if env_map.get(log_type):
        candidate_paths.append(Path(env_map[log_type]))

    if log_type == "worker":
        candidate_paths += [
            logs_dir / "worker.log",
            logs_dir / "celery.log",
        ]
    elif log_type == "celery":
        candidate_paths += [
            logs_dir / "celery.log",
            logs_dir / "worker.log",
        ]
    else:
        candidate_paths += [
            logs_dir / "whatsapp.log",
            logs_dir / "whatsapp_bot.log",
        ]

    log_path = None
    for path in candidate_paths:
        try:
            if path and path.exists() and path.is_file():
                log_path = path
                break
        except Exception:
            continue

    if not log_path:
        return {
            "path": None,
            "lines": [],
            "note": "No log file found. Set WORKER_LOG_PATH/CELERY_LOG_PATH/WHATSAPP_LOG_PATH.",
        }

    try:
        with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            content = handle.read().splitlines()
        return {
            "path": str(log_path),
            "lines": content[-lines:],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {exc}")
