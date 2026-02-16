from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.params import Form as FormParam, Param
from sqlmodel import Session, select
from pydantic import BaseModel, Field, confloat
from typing import Optional, Dict, Any, List
import time
import uuid
import os
import base64
import io
from PIL import Image
import logging

from app.database import get_session
from app.models import Crop, User, ChatSession, ChatMessage
from app.services.ocr.ocr_service import ocr_service
from app.services.ocr.crop_service import STORAGE_DIR
from app.services.solver_v3 import get_solver_v3
from app.services.solve_text_pipeline import solve_text_questions, SolveTextPipelineError
from app.services.tier_utils import get_user_effective_tier_slug
from app.services.math.error_localizer import (
    OCRPayload, Budget, find_first_error_from_ocr
)
from app.services.math.step_generator import generate_local_steps

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = int(os.getenv("SNAP_SOLVE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_DIM = int(os.getenv("SNAP_SOLVE_MAX_IMAGE_DIM", "2000"))
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_UPLOAD_MIME = ALLOWED_IMAGE_MIME | {"application/pdf"}
_TIER_ORDER = {"short_steps": 0, "final": 1, "standard": 2, "research": 3}

class BBox(BaseModel):
    x: confloat(ge=0.0, le=1.0)
    y: confloat(ge=0.0, le=1.0)
    w: confloat(gt=0.0, le=1.0)
    h: confloat(gt=0.0, le=1.0)

class FindErrorLocalRequest(BaseModel):
    crop_hash: Optional[str] = Field(None, min_length=8, max_length=128)
    image_data: Optional[str] = None
    selection_bbox: BBox
    ocr_hint: Optional[str] = Field(default="math")
    max_lines: int = Field(default=6, ge=1, le=12)

class FindErrorLocalResponse(BaseModel):
    ok: bool
    request_id: str
    selection_bbox: BBox
    ocr: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    local_steps: Optional[List[str]] = None
    error: Optional[Dict[str, Any]] = None
    timings_ms: Dict[str, int]


class SolveFromImageOrSketchResponse(BaseModel):
    answer_markdown: str
    answer_latex: Optional[str] = None
    meta: Dict[str, Any]


class SolveTextQuestionItem(BaseModel):
    question_id: str
    text: str


class SolveTextBatchRequest(BaseModel):
    requested_mode: str
    tier: str
    questions: List[SolveTextQuestionItem]


class SolveTextBatchResponse(BaseModel):
    ok: bool
    request_id: str
    attempt_id: str
    requested_mode: str
    schema_name: str
    response_language: str
    question_count: int
    solutions: List[Dict[str, Any]]
    telemetry: Dict[str, Any]
    session_id: Optional[int] = None


def _normalize_tier_slug(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    if raw in {"research", "enterprise"}:
        return "research"
    if raw in {"family", "family_standard", "short", "final"}:
        return "final"
    if raw in {"standard", "student_standard", "pro", "premium"}:
        return "standard"
    if raw in {"three_step", "free", "short_steps"}:
        return "short_steps"
    return "short_steps"


def _clamp_requested_tier(requested_tier: Optional[str], entitled_tier: str) -> str:
    entitled = _normalize_tier_slug(entitled_tier)
    requested = _normalize_tier_slug(requested_tier) if requested_tier else entitled
    if _TIER_ORDER[requested] <= _TIER_ORDER[entitled]:
        return requested
    return entitled


def _resolve_requested_mode(requested_mode: Optional[str], effective_tier: str) -> str:
    mode = (requested_mode or "").strip().lower()
    if mode in {"minimal", "detailed"}:
        return mode
    return "minimal" if _normalize_tier_slug(effective_tier) in {"short_steps", "final"} else "detailed"


def _resolve_fastapi_default(value: Any) -> Any:
    # Direct unit tests sometimes invoke the endpoint function directly, so
    # FastAPI Form default objects can leak into runtime values.
    if isinstance(value, (Param, FormParam)):
        return None
    return value

def load_cropped_image_by_hash(crop_hash: str, session: Session):
    """
    Return PIL image for the cropped image cached in pipeline.
    """
    # 1. Look up in DB
    crop_record = session.exec(select(Crop).where(Crop.crop_image_hash == crop_hash)).first()
    
    file_path = None
    if crop_record:
        file_path = crop_record.cropped_storage_url
    else:
        # Fallback to filesystem prediction
        filename = f"crop_{crop_hash[:16]}.png"
        file_path = os.path.join(STORAGE_DIR, filename)
    
    if file_path and os.path.exists(file_path):
        return Image.open(file_path)
    
    return None

def crop_region(pil_img, bbox: BBox):
    """
    Convert normalized bbox to pixel box and crop safely with clamping.
    """
    W, H = pil_img.size
    x0 = int(max(0, min(W-1, bbox.x * W)))
    y0 = int(max(0, min(H-1, bbox.y * H)))
    x1 = int(max(0, min(W, (bbox.x + bbox.w) * W)))
    y1 = int(max(0, min(H, (bbox.y + bbox.h) * H)))

    if (x1 - x0) < 25 or (y1 - y0) < 25:
        return None, {"code": "BBOX_TOO_SMALL", "message": "Selection too small. Re-circle a larger area."}

    return pil_img.crop((x0, y0, x1, y1)), None

def ocr_region_with_pix2text(pil_region):
    """
    Use LocalEngine (Pix2Text) from ocr_service.py.
    Return (raw_text, normalized_text, confidence).
    """
    # Convert PIL to bytes
    region_bytes_io = io.BytesIO()
    pil_region.save(region_bytes_io, format="PNG")
    region_bytes = region_bytes_io.getvalue()
    
    # Recognize
    ocr_out = ocr_service.recognize_region(region_bytes, engine_name="local")
    
    # Map result
    raw = ocr_out.get("raw", "")
    text = ocr_out.get("text", "")
    conf = ocr_out.get("confidence", 0.0)
    
    return raw, text, conf


def _dependency_unavailable_error(message: str) -> Dict[str, Any]:
    return {
        "code": "DEPENDENCY_UNAVAILABLE",
        "status": "dependency_unavailable",
        "reason": message,
        "retryable": True,
    }


def _validate_mime(mode: str, mime_type: str) -> None:
    if mode == "sketch":
        if mime_type != "image/png":
            raise HTTPException(status_code=400, detail="Sketch mode requires image/png.")
        return
    if mode == "upload":
        if mime_type not in ALLOWED_UPLOAD_MIME:
            raise HTTPException(status_code=400, detail="Unsupported upload MIME type.")
        return
    raise HTTPException(status_code=400, detail="mode must be 'upload' or 'sketch'.")


def _normalize_to_rgb(image: Image.Image, white_bg: bool = True) -> Image.Image:
    if image.mode in ("RGBA", "LA") and white_bg:
        alpha = image.convert("RGBA")
        background = Image.new("RGB", alpha.size, (255, 255, 255))
        background.paste(alpha, mask=alpha.split()[-1])
        return background
    if image.mode == "P":
        converted = image.convert("RGBA")
        background = Image.new("RGB", converted.size, (255, 255, 255))
        background.paste(converted, mask=converted.split()[-1])
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _downscale_if_needed(image: Image.Image, max_dim: int = MAX_IMAGE_DIM) -> Image.Image:
    w, h = image.size
    if max(w, h) <= max_dim:
        return image
    scale = max_dim / float(max(w, h))
    target = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(target, Image.Resampling.LANCZOS)


def _render_answer_markdown(result: Dict[str, Any]) -> Dict[str, Optional[str]]:
    content = result.get("_content")
    if isinstance(content, str) and content.strip():
        answer_latex = (
            result.get("final_answer", {}).get("answer_latex")
            if isinstance(result.get("final_answer"), dict)
            else None
        )
        return {"markdown": content.strip(), "latex": answer_latex}

    lines: List[str] = []
    problem = result.get("problem", {})
    if isinstance(problem, dict):
        original = problem.get("original_text") or problem.get("goal")
        if original:
            lines.append(f"**Problem**: {original}")

    steps = result.get("steps", [])
    if isinstance(steps, list) and steps:
        lines.append("")
        lines.append("### Steps")
        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            title = step.get("title") or f"Step {idx}"
            explanation = step.get("explanation") or ""
            lines.append(f"{idx}. **{title}**")
            if explanation:
                lines.append(f"   - {explanation}")

    final_answer = result.get("final_answer")
    answer_latex = None
    if isinstance(final_answer, dict):
        answer_text = final_answer.get("answer_text") or final_answer.get("answer") or ""
        answer_latex = final_answer.get("answer_latex")
    else:
        answer_text = str(final_answer or "")

    if answer_text or answer_latex:
        lines.append("")
        lines.append("### Final Answer")
        if answer_text:
            lines.append(answer_text)
        if answer_latex:
            lines.append(f"$$ {answer_latex} $$")

    markdown = "\n".join(lines).strip() or "No answer returned."
    return {"markdown": markdown, "latex": answer_latex}


def _map_legacy_mode_to_text_pipeline_mode(effective_tier_slug: str, effective_requested_mode: str) -> str:
    tier = _normalize_tier_slug(effective_tier_slug)
    mode = (effective_requested_mode or "").strip().lower()
    if tier == "research":
        return "research_detailed"
    if tier == "final":
        return "final_only"
    if tier == "standard":
        return "standard_detailed" if mode == "detailed" else "free_minimal"
    return "free_minimal"


def _render_solution_item_markdown(solution_item: Dict[str, Any]) -> Dict[str, Optional[str]]:
    if not isinstance(solution_item, dict):
        return {"markdown": "No answer returned.", "latex": None}

    final_answer = solution_item.get("final_answer") if isinstance(solution_item.get("final_answer"), dict) else {}
    answer_text = str(final_answer.get("answer_text") or "").strip()
    answer_latex = final_answer.get("answer_latex")

    lines: List[str] = []
    if answer_text:
        lines.append("### Final Answer")
        lines.append(answer_text)

    steps = solution_item.get("steps") if isinstance(solution_item.get("steps"), list) else []
    if steps:
        lines.append("")
        lines.append("### Steps")
        for idx, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                title = str(step.get("title") or f"Step {idx}")
                explanation = str(step.get("explanation") or "").strip()
                if explanation:
                    lines.append(f"{idx}. **{title}**: {explanation}")
                else:
                    lines.append(f"{idx}. **{title}**")
            elif isinstance(step, str) and step.strip():
                lines.append(f"{idx}. {step.strip()}")

    markdown = "\n".join(lines).strip() or (answer_text or "No answer returned.")
    return {"markdown": markdown, "latex": answer_latex if isinstance(answer_latex, str) else None}


@router.post("/math/solve_text_batch", response_model=SolveTextBatchResponse)
async def solve_text_batch(
    body: SolveTextBatchRequest,
    user_id: int = Param(...),
    session: Session = Depends(get_session),
):
    from app.services.solve.batch_tier_runtime import BatchSolveError, execute_batch_solve

    try:
        tier_slug = _normalize_tier_slug(body.tier)
        tier_external = "FINAL" if tier_slug == "final" else ("SHORT_STEPS" if tier_slug == "short_steps" else tier_slug.upper())
        questions_json = [
            {
                "question_id": q.question_id,
                "question_text": q.text,
                "mode": "SOLVE",
                "graph_mode": "AUTO",
                "domain_mode": "reals",
            }
            for q in body.questions
        ]
        payload, telemetry = await execute_batch_solve(
            session=session,
            tier=tier_external,
            request_id=str(uuid.uuid4()),
            attempt_id=str(uuid.uuid4()),
            mode="SOLVE",
            graph_mode="AUTO",
            domain_mode="reals",
            preferred_response_language="English",
            questions_json=questions_json,
        )
        # Persist a chat session so frontend can route to /chat/{session_id}
        user_prompt_lines = ["Solve the selected questions:"]
        for q in body.questions:
            user_prompt_lines.append(f"- ({q.question_id}) {q.text}")
        user_prompt = "\n".join(user_prompt_lines)

        assistant_sections: List[str] = []
        solutions = payload.get("items") if isinstance(payload.get("items"), list) else []
        for idx, solution in enumerate(solutions, start=1):
            item = _render_solution_item_markdown(solution if isinstance(solution, dict) else {})
            question_id = str((solution or {}).get("question_id") or f"q{idx}")
            assistant_sections.append(f"## {question_id}\n{item.get('markdown') or 'No answer returned.'}")
        assistant_markdown = "\n\n".join(assistant_sections).strip() or "No answer returned."

        new_chat = ChatSession(
            user_id=user_id,
            title=f"Batch solve ({len(solutions)})",
            subject="Math",
            is_saved=False,
            learning_mode="solve",
            requested_mode="minimal" if body.requested_mode in {"free_minimal", "final_only"} else "detailed",
            solve_tier=(body.tier or "short_steps").lower(),
        )
        session.add(new_chat)
        session.commit()
        session.refresh(new_chat)

        session.add(ChatMessage(session_id=new_chat.id, role="user", content=user_prompt))
        session.add(
            ChatMessage(
                session_id=new_chat.id,
                role="assistant",
                content=assistant_markdown,
                structured_data={
                    "mode": "batch_text_solve",
                    "requested_mode": body.requested_mode,
                    "response_language": ((payload.get("language") or {}).get("response_language") if isinstance(payload.get("language"), dict) else "English"),
                    "question_count": len(solutions),
                    "solutions": solutions,
                },
                telemetry=telemetry or {},
                model_used=str((telemetry or {}).get("model") or ""),
            )
        )
        session.commit()

        return SolveTextBatchResponse(
            ok=True,
            request_id=str(telemetry.get("request_id") or ""),
            attempt_id=str(telemetry.get("attempt_id") or ""),
            requested_mode=body.requested_mode,
            schema_name=str(telemetry.get("schema_name") or ""),
            response_language=((payload.get("language") or {}).get("response_language") if isinstance(payload.get("language"), dict) else "English"),
            question_count=len(solutions),
            solutions=solutions,
            telemetry=telemetry or {},
            session_id=new_chat.id,
        )
    except BatchSolveError as exc:
        detail = {"code": exc.code, "message": str(exc), **(exc.details or {})}
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
    except SolveTextPipelineError as exc:
        detail = {"code": exc.code, "message": exc.message, **(exc.details or {})}
        raise HTTPException(status_code=exc.http_status, detail=detail) from exc


@router.post("/find_error_local", response_model=FindErrorLocalResponse)
def find_error_local(req: FindErrorLocalRequest, session: Session = Depends(get_session)):
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    # Feature flag
    if not os.getenv("FEATURE_LOCAL_FIND_ERROR", "false").lower() == "true":
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            selection_bbox=req.selection_bbox,
            error={"code": "DISABLED", "message": "Local find-error is disabled."},
            timings_ms={"total": int((time.perf_counter()-t0)*1000)}
        )

    try:
        img = None
        # Load Image (Hash or Base64)
        if req.image_data:
            try:
                img_bytes = base64.b64decode(req.image_data)
                img = Image.open(io.BytesIO(img_bytes))
            except Exception as e:
                 return FindErrorLocalResponse(
                    ok=False, request_id=request_id, selection_bbox=req.selection_bbox,
                    error={"code": "INVALID_IMAGE", "message": "Invalid base64 data"},
                    timings_ms={"total": int((time.perf_counter()-t0)*1000)}
                )
        elif req.crop_hash:
            img = load_cropped_image_by_hash(req.crop_hash, session)
            
        if not img:
            return FindErrorLocalResponse(
                ok=False, request_id=request_id, selection_bbox=req.selection_bbox,
                error={"code": "IMAGE_NOT_FOUND", "message": "Could not retrieve source image"},
                timings_ms={"total": int((time.perf_counter()-t0)*1000)}
            )

        t_crop0 = time.perf_counter()
        if req.image_data:
            # If base64 is provided, the frontend already cropped to the selection
            region = img
            crop_err = None
        else:
            # Hash-based lookup requires cropping relative to the source image
            region, crop_err = crop_region(img, req.selection_bbox)
        
        crop_ms = int((time.perf_counter()-t_crop0)*1000)
        if crop_err:
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=req.selection_bbox,
                error=crop_err,
                timings_ms={"crop": crop_ms, "total": int((time.perf_counter()-t0)*1000)}
            )

        t_ocr0 = time.perf_counter()
        try:
            raw_text, norm_text, ocr_conf = ocr_region_with_pix2text(region)
        except Exception as exc:
            return FindErrorLocalResponse(
                ok=False,
                request_id=request_id,
                selection_bbox=req.selection_bbox,
                error=_dependency_unavailable_error(f"OCR service unavailable: {type(exc).__name__}"),
                timings_ms={"crop": crop_ms, "total": int((time.perf_counter()-t0)*1000)},
            )
        ocr_ms = int((time.perf_counter()-t_ocr0)*1000)

        # Cap raw text to avoid flooding logs/clients
        raw_text = (raw_text or "")[:500]
        norm_text = (norm_text or "")[:500]

        # Run local SymPy/SciPy checks
        t_chk0 = time.perf_counter()
        ocr_payload = OCRPayload(raw=raw_text, text=norm_text, confidence=float(ocr_conf or 0.0))
        budget = Budget(
            total_ms=int(os.getenv("LOCAL_FINDERR_TOTAL_MS", "1500")),
            sympy_ms=int(os.getenv("LOCAL_FINDERR_SYMPY_MS", "700")),
            numeric_ms=int(os.getenv("LOCAL_FINDERR_NUMERIC_MS", "700")),
        )
        result = find_first_error_from_ocr(ocr_payload, transcript_hint="find_error", max_lines=req.max_lines, budget=budget)
        chk_ms = int((time.perf_counter()-t_chk0)*1000)

        # Generate local steps if no definite error or if solving a prompt
        local_steps = []
        if not result.first_wrong_line_index or result.confidence < 0.3:
            local_steps = generate_local_steps(norm_text)


        return FindErrorLocalResponse(
            ok=True,
            request_id=request_id,
            selection_bbox=req.selection_bbox,
            ocr={
                "raw": raw_text[:120],          # keep UI readable
                "text": norm_text,
                "confidence": float(ocr_payload.confidence)
            },
            analysis={
                "detected_format": result.detected_format,
                "first_wrong_line_index": result.first_wrong_line_index,
                "what_is_wrong": result.what_is_wrong,
                "minimal_fix": result.minimal_fix,
                "confidence": float(result.confidence),
                "per_line": [
                    {
                        "ok": r.ok,
                        "confidence": float(r.confidence),
                        "reason": r.reason,
                        "minimal_fix": r.minimal_fix
                    } for r in result.per_line
                ]
            },
            local_steps=local_steps,
            timings_ms={
                "crop": crop_ms,
                "ocr": ocr_ms,
                "check": chk_ms,
                "total": int((time.perf_counter()-t0)*1000)
            }
        )

    except Exception as e:
        return FindErrorLocalResponse(
            ok=False,
            request_id=request_id,
            selection_bbox=req.selection_bbox,
            error={"code": "INTERNAL_ERROR", "message": f"Failed to analyze selection: {str(e)}"},
            timings_ms={"total": int((time.perf_counter()-t0)*1000)}
        )


@router.post("/math/solve_from_image_or_sketch", response_model=SolveFromImageOrSketchResponse)
async def solve_from_image_or_sketch(
    request: Request,
    mode: str = Form(...),
    question_text: str = Form(""),
    image: Optional[UploadFile] = File(default=None),
    tier: Optional[str] = Form(default=None),
    requested_mode: Optional[str] = Form(default=None),
    user_id_form: Optional[int] = Form(default=None),
    original_filename: Optional[str] = Form(default=None),
    client_context: Optional[str] = Form(default=None),
    user_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    mode_normalized = (mode or "").strip().lower()
    image_mime = image.content_type if image else "text/plain"

    if mode_normalized not in {"upload", "sketch"}:
        raise HTTPException(status_code=400, detail="mode must be upload or sketch.")

    image_text = ""
    if image is not None:
        _validate_mime(mode_normalized, image_mime or "")
        raw_bytes = await image.read()
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds max upload size.")

        if image_mime == "application/pdf":
            raise HTTPException(status_code=400, detail="PDF is not enabled on this endpoint yet. Use legacy Snap flow.")

        try:
            pil_image = Image.open(io.BytesIO(raw_bytes))
            pil_image = _normalize_to_rgb(pil_image, white_bg=True)
            pil_image = _downscale_if_needed(pil_image, max_dim=MAX_IMAGE_DIM)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            preprocessed = buffer.getvalue()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image payload: {exc}") from exc

        ocr_result = ocr_service.recognize_region(preprocessed, engine_name=os.getenv("OCR_ENGINE", "auto"))
        image_text = (ocr_result.get("text") or "").strip()
        logger.info(
            "[snap_solve] request_id=%s mode=%s mime=%s extracted_chars=%s filename=%s",
            request_id,
            mode_normalized,
            image_mime,
            len(image_text),
            original_filename or getattr(image, "filename", None),
        )

    question_text = (question_text or "").strip()
    if not image_text and not question_text:
        raise HTTPException(status_code=400, detail="Provide an image/sketch or question text.")

    resolved_tier = _resolve_fastapi_default(tier)
    resolved_mode = _resolve_fastapi_default(requested_mode)
    resolved_user_id_form = _resolve_fastapi_default(user_id_form)
    resolved_user_id_query = _resolve_fastapi_default(user_id)
    resolved_user_id = resolved_user_id_query if resolved_user_id_query is not None else resolved_user_id_form
    entitled_tier_slug = "short_steps"
    if resolved_user_id:
        user_obj = session.get(User, resolved_user_id)
        if user_obj:
            entitled_tier_slug = get_user_effective_tier_slug(user_obj)
    effective_tier_slug = _clamp_requested_tier(resolved_tier, entitled_tier_slug)
    effective_requested_mode = _resolve_requested_mode(resolved_mode, effective_tier_slug)

    combined_prompt = question_text
    if image_text:
        combined_prompt = f"{question_text}\n\nExtracted content:\n{image_text}".strip()

    rendered: Dict[str, Optional[str]] = {"markdown": "No answer returned.", "latex": None}
    pipeline_mode = _map_legacy_mode_to_text_pipeline_mode(effective_tier_slug, effective_requested_mode)
    try:
        if not resolved_user_id:
            raise SolveTextPipelineError("USER_NOT_FOUND", "User is required for text solve", 400)

        batch_result = await solve_text_questions(
            session=session,
            user_id=resolved_user_id,
            requested_mode=pipeline_mode,
            tier=effective_tier_slug.upper(),
            questions=[{"question_id": request_id, "text": combined_prompt}],
        )
        first_solution = (batch_result.get("solutions") or [{}])[0]
        rendered = _render_solution_item_markdown(first_solution if isinstance(first_solution, dict) else {})
    except Exception:
        # Safe fallback: preserve old single-question path.
        solver = get_solver_v3()
        solve_result = await solver.solve(
            problem_text=combined_prompt,
            context="",
            request_id=request_id,
            user_tier=effective_tier_slug,
            user_id=resolved_user_id,
            requested_mode=effective_requested_mode,
            db_session=session,
            trusted_context={"client_context": client_context} if client_context else None,
        )
        rendered = _render_answer_markdown(solve_result if isinstance(solve_result, dict) else {})
    latency_ms = int((time.perf_counter() - start) * 1000)

    return SolveFromImageOrSketchResponse(
        answer_markdown=rendered["markdown"] or "No answer returned.",
        answer_latex=rendered["latex"],
        meta={
            "mode": mode_normalized,
            "mime": image_mime,
            "latency_ms": latency_ms,
            "request_id": request_id,
            "requested_tier": _normalize_tier_slug(resolved_tier) if resolved_tier else None,
            "effective_tier": effective_tier_slug,
            "requested_mode": effective_requested_mode,
            "user_id": resolved_user_id,
        },
    )
