from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import json
import os
import random
import re
import time
import uuid
import logging
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.database import engine


RENDERER_VERSION = "mathjax_v4_components_v2"
_FORBIDDEN_TAG_RE = re.compile(r"<\s*(script|foreignObject)\b", re.IGNORECASE)
_FORBIDDEN_EVENT_ATTR_RE = re.compile(r"\son[a-zA-Z]+\s*=", re.IGNORECASE)
_FORBIDDEN_HREF_RE = re.compile(r"\s(?:href|xlink:href)\s*=\s*(['\"])\s*javascript:", re.IGNORECASE)
_SVG_TAG_RE = re.compile(r"<\s*svg\b", re.IGNORECASE)
logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_svg_server(svg: str) -> str:
    out = str(svg or "")
    out = re.sub(r"\son[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", out, flags=re.IGNORECASE | re.DOTALL)
    out = re.sub(r"\s(?:href|xlink:href)\s*=\s*(['\"])\s*javascript:.*?\1", "", out, flags=re.IGNORECASE | re.DOTALL)
    out = re.sub(r"<\s*script\b.*?<\s*/\s*script\s*>", "", out, flags=re.IGNORECASE | re.DOTALL)
    out = re.sub(r"<\s*foreignObject\b.*?<\s*/\s*foreignObject\s*>", "", out, flags=re.IGNORECASE | re.DOTALL)
    # Some sanitizer paths can emit malformed XML attributes like: <path d></path>.
    # Normalize these into XML-safe empty values.
    out = re.sub(r"<path([^>]*?)\sd(?=(\s|/?>))", r"<path\1 d=\"\"", out, flags=re.IGNORECASE)
    return out


def has_forbidden_svg(svg: str) -> bool:
    text_svg = str(svg or "")
    return bool(
        _FORBIDDEN_TAG_RE.search(text_svg)
        or _FORBIDDEN_EVENT_ATTR_RE.search(text_svg)
        or _FORBIDDEN_HREF_RE.search(text_svg)
    )


def _parse_svg_numeric(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = re.sub(r"(ex|em|px|pt|cm|mm|in|%)$", "", raw, flags=re.IGNORECASE)
    try:
        parsed = float(raw)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def validate_svg_output(svg: str) -> Tuple[bool, Optional[str], Dict[str, Optional[float]]]:
    """
    Strict SVG validation:
    - Well-formed XML.
    - Root element is <svg>.
    - Must have viewBox or both width/height.
    - Must not include forbidden constructs.
    """
    text_svg = str(svg or "").strip()
    if not text_svg:
        return False, "empty_svg", {}
    if not _SVG_TAG_RE.search(text_svg):
        return False, "missing_svg_root", {}
    if has_forbidden_svg(text_svg):
        return False, "forbidden_svg_content", {}

    try:
        root = ET.fromstring(text_svg)
    except Exception:
        return False, "invalid_xml", {}

    if not isinstance(root.tag, str) or not root.tag.lower().endswith("svg"):
        return False, "root_not_svg", {}

    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    width = _parse_svg_numeric(root.attrib.get("width"))
    height = _parse_svg_numeric(root.attrib.get("height"))
    parsed: Dict[str, Optional[float]] = {"width": width, "height": height}

    if view_box:
        parts = [p for p in re.split(r"\s+", str(view_box).strip()) if p]
        if len(parts) == 4:
            try:
                vb_w = float(parts[2])
                vb_h = float(parts[3])
                if vb_w > 0 and vb_h > 0:
                    parsed["viewbox_width"] = vb_w
                    parsed["viewbox_height"] = vb_h
            except Exception:
                pass

    has_viewbox = "viewbox_width" in parsed and "viewbox_height" in parsed
    has_dims = (parsed.get("width") or 0) > 0 and (parsed.get("height") or 0) > 0
    if not has_viewbox and not has_dims:
        return False, "missing_dimensions", parsed
    return True, None, parsed


def normalize_macros(macros: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not isinstance(macros, dict):
        return {}
    normalized: Dict[str, str] = {}
    for k in sorted(macros.keys()):
        key = str(k).strip()
        if not key:
            continue
        normalized[key] = str(macros[k])
    return normalized


def canonical_render_key(*, latex: str, display_mode: bool, macros: Dict[str, str], scale: float, font: str) -> str:
    payload = {
        "latex": str(latex or "").strip(),
        "display_mode": bool(display_mode),
        "macros": macros,
        "scale": float(scale),
        "font": str(font or "tex"),
        "renderer_version": RENDERER_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"texsvg:v1:{digest}"


def split_latex_segments(text_value: str) -> List[Dict[str, Any]]:
    s = str(text_value or "")
    out: List[Dict[str, Any]] = []
    i = 0
    n = len(s)
    in_code_block = False
    while i < n:
        if s.startswith("```", i):
            in_code_block = not in_code_block
            j = i + 3
            out.append({"kind": "text", "text": s[i:j]})
            i = j
            continue
        if in_code_block:
            j = i + 1
            out.append({"kind": "text", "text": s[i:j]})
            i = j
            continue
        if s.startswith("$$", i):
            j = i + 2
            while j < n and not s.startswith("$$", j):
                j += 1
            if j < n:
                out.append({"kind": "math", "display_mode": True, "latex": s[i + 2 : j]})
                i = j + 2
                continue
        if s.startswith("\\[", i):
            j = i + 2
            while j < n and not s.startswith("\\]", j):
                j += 1
            if j < n:
                out.append({"kind": "math", "display_mode": True, "latex": s[i + 2 : j]})
                i = j + 2
                continue
        if s.startswith("\\(", i):
            j = i + 2
            while j < n and not s.startswith("\\)", j):
                j += 1
            if j < n:
                out.append({"kind": "math", "display_mode": False, "latex": s[i + 2 : j]})
                i = j + 2
                continue
        if s[i] == "$":
            if i > 0 and s[i - 1] == "\\":
                out.append({"kind": "text", "text": "$"})
                i += 1
                continue
            j = i + 1
            while j < n:
                if s[j] == "$" and s[j - 1] != "\\":
                    break
                j += 1
            if j < n:
                out.append({"kind": "math", "display_mode": False, "latex": s[i + 1 : j]})
                i = j + 1
                continue
        out.append({"kind": "text", "text": s[i]})
        i += 1
    return out


class MemorySvgCache:
    def __init__(self, max_entries: int = 10000, ttl_hours: int = 24) -> None:
        self.max_entries = max_entries
        self.ttl = timedelta(hours=ttl_hours)
        self._data: OrderedDict[str, Tuple[datetime, Dict[str, Any]]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if _utc_now() > expires_at:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        async with self._lock:
            self._data[key] = (_utc_now() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)


@dataclass
class WorkerConfig:
    cmd: List[str]
    cwd: str
    timeout_ms: int = 1000
    max_inflight: int = 2


class MathJaxWorker:
    def __init__(self, cfg: WorkerConfig) -> None:
        self.cfg = cfg
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.pending: Dict[str, asyncio.Future] = {}
        self.sem = asyncio.Semaphore(self.cfg.max_inflight)
        self.write_lock = asyncio.Lock()
        self.reader_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
        self._alive = False

    async def start(self) -> None:
        if self.proc and self.proc.returncode is None:
            return
        self.proc = await asyncio.create_subprocess_exec(
            *self.cfg.cmd,
            cwd=self.cfg.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._alive = True
        self.reader_task = asyncio.create_task(self._reader_loop())
        self.stderr_task = asyncio.create_task(self._stderr_loop())

    async def stop(self) -> None:
        self._alive = False
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                self.proc.kill()
        if self.reader_task:
            self.reader_task.cancel()
        if self.stderr_task:
            self.stderr_task.cancel()

    async def _stderr_loop(self) -> None:
        if not self.proc or not self.proc.stderr:
            return
        while self._alive and self.proc.returncode is None:
            line = await self.proc.stderr.readline()
            if not line:
                break

    async def _reader_loop(self) -> None:
        if not self.proc or not self.proc.stdout:
            return
        while self._alive and self.proc.returncode is None:
            raw = await self.proc.stdout.readline()
            if not raw:
                break
            try:
                payload = json.loads(raw.decode("utf-8").strip())
            except Exception:
                continue
            rid = str(payload.get("id") or "")
            fut = self.pending.pop(rid, None)
            if fut and not fut.done():
                fut.set_result(payload)
        # fail pending futures on exit
        for rid, fut in list(self.pending.items()):
            if not fut.done():
                fut.set_result(
                    {
                        "id": rid,
                        "ok": False,
                        "error": {"code": "WORKER_DOWN", "message": "Renderer worker exited"},
                        "fallback_text": "",
                    }
                )
        self.pending.clear()

    async def render(self, request: Dict[str, Any]) -> Dict[str, Any]:
        await self.start()
        if not self.proc or not self.proc.stdin or self.proc.returncode is not None:
            return {
                "id": request.get("id"),
                "ok": False,
                "error": {"code": "WORKER_DOWN", "message": "Renderer worker unavailable"},
                "fallback_text": str(request.get("latex") or ""),
            }
        await self.sem.acquire()
        try:
            rid = str(request.get("id") or uuid.uuid4().hex)
            request["id"] = rid
            loop = asyncio.get_running_loop()
            fut: asyncio.Future = loop.create_future()
            self.pending[rid] = fut
            payload = (json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8")
            async with self.write_lock:
                self.proc.stdin.write(payload)
                await self.proc.stdin.drain()
            timeout_sec = max(0.1, float(self.cfg.timeout_ms) / 1000.0)
            try:
                result = await asyncio.wait_for(fut, timeout=timeout_sec + 0.2)
            except asyncio.TimeoutError:
                self.pending.pop(rid, None)
                return {
                    "id": rid,
                    "ok": False,
                    "error": {"code": "TIMEOUT", "message": "Renderer timed out"},
                    "fallback_text": str(request.get("latex") or ""),
                }
            return result
        finally:
            self.sem.release()


class MathJaxWorkerPool:
    def __init__(self, worker_count: int = 2, max_inflight_per_worker: int = 2, timeout_ms: int = 1000) -> None:
        self.worker_count = max(1, worker_count)
        self.max_inflight_per_worker = max(1, max_inflight_per_worker)
        self.timeout_ms = timeout_ms
        self._workers: List[MathJaxWorker] = []
        self._index = 0
        self._restart_count = 0
        self._lock = asyncio.Lock()

    def _build_worker_config(self) -> WorkerConfig:
        root = Path(__file__).resolve().parents[2]
        worker_dir = root / "tools" / "mathjax_renderer_v4"
        return WorkerConfig(
            cmd=["node", "renderer.mjs"],
            cwd=str(worker_dir),
            timeout_ms=self.timeout_ms,
            max_inflight=self.max_inflight_per_worker,
        )

    async def start(self) -> None:
        async with self._lock:
            if self._workers:
                return
            for _ in range(self.worker_count):
                w = MathJaxWorker(self._build_worker_config())
                await w.start()
                self._workers.append(w)

    async def stop(self) -> None:
        async with self._lock:
            workers = list(self._workers)
            self._workers.clear()
        for worker in workers:
            await worker.stop()

    async def render(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not self._workers:
            await self.start()
        if not self._workers:
            return {
                "id": request.get("id"),
                "ok": False,
                "error": {"code": "WORKER_POOL_DOWN", "message": "No math renderer workers"},
                "fallback_text": str(request.get("latex") or ""),
            }
        worker = self._workers[self._index % len(self._workers)]
        self._index += 1
        if not worker.proc or worker.proc.returncode is not None:
            self._restart_count += 1
            await worker.start()
        return await worker.render(request)

    @property
    def restart_count(self) -> int:
        return self._restart_count


class MathRenderService:
    def __init__(self) -> None:
        # 1s is too aggressive for cold/warm renderer workers on some environments.
        # Use a safer default and keep it configurable.
        default_timeout_ms = int(os.environ.get("MATH_RENDER_TIMEOUT_MS", "5000"))
        self.mem_cache = MemorySvgCache(max_entries=10000, ttl_hours=24)
        self.worker_pool = MathJaxWorkerPool(
            worker_count=int(os.environ.get("MATH_RENDER_WORKERS", "2")),
            max_inflight_per_worker=int(os.environ.get("MATH_RENDER_MAX_INFLIGHT", "2")),
            timeout_ms=default_timeout_ms,
        )
        self._hit_updates: Dict[str, int] = {}
        self._hit_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._disabled = os.environ.get("DISABLE_MATH_RENDER", "").strip().lower() in {"1", "true", "yes"}
        self._disable_reason: Optional[str] = "disabled_by_env" if self._disabled else None

    async def startup(self) -> None:
        if self._disabled:
            return
        await self.worker_pool.start()
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_hits_loop())

    async def shutdown(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
        await self.worker_pool.stop()

    async def _flush_hits_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            await self.flush_hit_updates()

    async def mark_hit(self, key: str) -> None:
        # Sample hit persistence to avoid write amplification
        if random.random() > 0.01:
            return
        async with self._hit_lock:
            self._hit_updates[key] = self._hit_updates.get(key, 0) + 1

    async def flush_hit_updates(self) -> None:
        async with self._hit_lock:
            pending = dict(self._hit_updates)
            self._hit_updates.clear()
        if not pending:
            return
        try:
            with engine.begin() as conn:
                for key, cnt in pending.items():
                    conn.execute(
                        text(
                            """
                            UPDATE math_svg_cache
                            SET hits = hits + :cnt, last_accessed_at = NOW()
                            WHERE key = :key
                            """
                        ),
                        {"key": key, "cnt": int(cnt)},
                    )
        except Exception:
            return

    def _db_get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            with engine.begin() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT svg_gzip, metrics
                        FROM math_svg_cache
                        WHERE key = :key
                        """
                    ),
                    {"key": key},
                ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        svg_raw = gzip.decompress(bytes(row[0])).decode("utf-8")
        metrics = row[1] if isinstance(row[1], dict) else {}
        return {"svg": svg_raw, "metrics": metrics}

    def _db_set(self, key: str, latex: str, config: Dict[str, Any], svg_text: str, metrics: Dict[str, Any]) -> None:
        svg_gzip = gzip.compress(svg_text.encode("utf-8"))
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO math_svg_cache (key, latex, config, svg_gzip, metrics, created_at, last_accessed_at, hits)
                        VALUES (:key, :latex, CAST(:config AS JSONB), :svg_gzip, CAST(:metrics AS JSONB), NOW(), NOW(), 0)
                        ON CONFLICT (key) DO NOTHING
                        """
                    ),
                    {
                        "key": key,
                        "latex": latex,
                        "config": json.dumps(config, ensure_ascii=False),
                        "svg_gzip": svg_gzip,
                        "metrics": json.dumps(metrics, ensure_ascii=False),
                    },
                )
        except Exception:
            # Never-break mode: cache persistence errors must not fail response path.
            return

    def _db_delete(self, key: str) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM math_svg_cache WHERE key = :key"),
                    {"key": key},
                )
        except Exception:
            return

    async def render_batch(self, items: List[Dict[str, Any]], options: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        font = str(options.get("font") or "tex")
        sanitize = bool(options.get("sanitize", True))
        request_records: List[Dict[str, Any]] = []
        for raw in items:
            latex = str(raw.get("latex") or "").strip()
            display_mode = bool(raw.get("display_mode", False))
            scale_raw = raw.get("scale", 1.0)
            try:
                scale = float(scale_raw)
            except Exception:
                scale = 1.0
            scale = max(0.5, min(2.0, scale))
            macros = normalize_macros(raw.get("macros"))
            key = canonical_render_key(latex=latex, display_mode=display_mode, macros=macros, scale=scale, font=font)
            request_records.append(
                {
                    "latex": latex,
                    "display_mode": display_mode,
                    "scale": scale,
                    "macros": macros,
                    "font": font,
                    "sanitize": sanitize,
                    "key": key,
                }
            )

        unique_by_key: Dict[str, Dict[str, Any]] = {}
        for record in request_records:
            unique_by_key.setdefault(record["key"], record)

        if self._disabled:
            results = [
                {
                    "ok": False,
                    "error": {
                        "code": "RENDER_DISABLED",
                        "message": f"Math renderer disabled ({self._disable_reason or 'runtime'}).",
                    },
                    "fallback_text": str(record["latex"] or ""),
                    "cache": "miss",
                    "key": record["key"],
                }
                for record in request_records
            ]
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "results": results,
                "stats": {
                    "requested": len(request_records),
                    "deduped": len(unique_by_key),
                    "cache_hits": 0,
                    "rendered": 0,
                    "latency_ms": latency_ms,
                    "worker_restarts": self.worker_pool.restart_count,
                },
            }

        cache_hits = 0
        rendered = 0
        resolved: Dict[str, Dict[str, Any]] = {}

        for key, record in unique_by_key.items():
            mem = await self.mem_cache.get(key)
            if mem is not None:
                svg_text = str(mem.get("svg") or "")
                valid_hit, _, hit_metrics = validate_svg_output(svg_text)
                if valid_hit:
                    cache_hits += 1
                    merged_metrics = (mem.get("metrics") or {}) if isinstance(mem.get("metrics"), dict) else {}
                    if hit_metrics:
                        merged_metrics = {**merged_metrics, **hit_metrics}
                    resolved[key] = {"ok": True, "svg": svg_text, "metrics": merged_metrics, "cache": "hit", "key": key}
                    await self.mark_hit(key)
                    continue
                # Bad in-memory cache entry; let re-render path repair it.

            db_row = self._db_get(key)
            if db_row is not None:
                db_svg = str(db_row.get("svg") or "")
                valid_db, _, db_metrics = validate_svg_output(db_svg)
                if valid_db:
                    cache_hits += 1
                    merged_metrics = (db_row.get("metrics") or {}) if isinstance(db_row.get("metrics"), dict) else {}
                    if db_metrics:
                        merged_metrics = {**merged_metrics, **db_metrics}
                    resolved[key] = {"ok": True, "svg": db_svg, "metrics": merged_metrics, "cache": "hit", "key": key}
                    await self.mem_cache.set(key, {"svg": db_svg, "metrics": merged_metrics})
                    await self.mark_hit(key)
                    continue
                # Invalid stale DB cache row; remove and re-render.
                self._db_delete(key)

            payload = {
                "id": uuid.uuid4().hex,
                "latex": record["latex"],
                "display_mode": record["display_mode"],
                "macros": record["macros"],
                "scale": record["scale"],
                "sanitize": sanitize,
                "font": font,
                # Keep worker-side timeout aligned with Python-side wait timeout.
                "timeout_ms": self.worker_pool.timeout_ms,
            }
            try:
                worker_result = await self.worker_pool.render(payload)
            except NotImplementedError:
                # Windows debug runtimes can lack asyncio subprocess support.
                # Fail open and return fallback text instead of surfacing 500s.
                self._disabled = True
                self._disable_reason = "subprocess_not_supported"
                logger.warning("Disabling math renderer: asyncio subprocess not supported on current runtime")
                worker_result = {
                    "ok": False,
                    "error": {"code": "RENDER_DISABLED", "message": "Renderer disabled (subprocess unsupported)."},
                    "fallback_text": record["latex"],
                }
            except Exception as exc:
                logger.warning("Math renderer worker failed, using fallback text: %s", exc)
                worker_result = {
                    "ok": False,
                    "error": {"code": "RENDER_FAIL", "message": str(exc)},
                    "fallback_text": record["latex"],
                }
            if worker_result.get("ok"):
                svg_text = str(worker_result.get("svg") or "")
                if sanitize:
                    svg_text = sanitize_svg_server(svg_text)
                is_valid, validation_error, validation_metrics = validate_svg_output(svg_text)
                if sanitize and has_forbidden_svg(svg_text):
                    resolved[key] = {
                        "ok": False,
                        "error": {"code": "SANITIZE_FAIL", "message": "Unsafe SVG content blocked"},
                        "fallback_text": record["latex"],
                        "cache": "miss",
                        "key": key,
                    }
                elif not is_valid:
                    resolved[key] = {
                        "ok": False,
                        "error": {
                            "code": "SVG_VALIDATE_FAIL",
                            "message": f"Invalid SVG output: {validation_error or 'unknown'}",
                        },
                        "fallback_text": record["latex"],
                        "cache": "miss",
                        "key": key,
                        "metrics": validation_metrics,
                    }
                else:
                    metrics = worker_result.get("metrics") if isinstance(worker_result.get("metrics"), dict) else {}
                    if validation_metrics:
                        metrics = {**metrics, **validation_metrics}
                    resolved[key] = {"ok": True, "svg": svg_text, "metrics": metrics, "cache": "miss", "key": key}
                    await self.mem_cache.set(key, {"svg": svg_text, "metrics": metrics})
                    self._db_set(
                        key=key,
                        latex=record["latex"],
                        config={
                            "display_mode": record["display_mode"],
                            "macros": record["macros"],
                            "scale": record["scale"],
                            "font": font,
                            "renderer_version": RENDERER_VERSION,
                        },
                        svg_text=svg_text,
                        metrics=metrics,
                    )
                    rendered += 1
            else:
                resolved[key] = {
                    "ok": False,
                    "error": worker_result.get("error") or {"code": "RENDER_FAIL", "message": "Render failed"},
                    "fallback_text": record["latex"],
                    "cache": "miss",
                    "key": key,
                }

        results: List[Dict[str, Any]] = []
        for record in request_records:
            entry = dict(resolved[record["key"]])
            if entry.get("ok"):
                if "svg" in entry and len(entry["svg"]) > 0:
                    pass
            results.append(entry)

        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "results": results,
            "stats": {
                "requested": len(request_records),
                "deduped": len(unique_by_key),
                "cache_hits": cache_hits,
                "rendered": rendered,
                "latency_ms": latency_ms,
                "worker_restarts": self.worker_pool.restart_count,
            },
        }

    async def get_svg_by_key(self, key: str) -> Optional[str]:
        mem = await self.mem_cache.get(key)
        if mem:
            await self.mark_hit(key)
            return str(mem.get("svg") or "")
        db_row = self._db_get(key)
        if not db_row:
            return None
        svg_text = str(db_row["svg"] or "")
        await self.mem_cache.set(key, {"svg": svg_text, "metrics": db_row.get("metrics") or {}})
        await self.mark_hit(key)
        return svg_text


_math_render_service: Optional[MathRenderService] = None


def get_math_render_service() -> MathRenderService:
    global _math_render_service
    if _math_render_service is None:
        _math_render_service = MathRenderService()
    return _math_render_service


def svg_to_data_url(svg_text: str) -> str:
    raw = str(svg_text or "").encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"
