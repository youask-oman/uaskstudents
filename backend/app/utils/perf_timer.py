from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Iterator, Optional

_LOGGER = logging.getLogger("uask.perf")
_LOCK = threading.Lock()


def perf_enabled() -> bool:
    return os.environ.get("UASK_PERF_PROFILE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def perf_emit(
    *,
    label: str,
    file_function: str,
    elapsed_ms: float,
    request_id: Optional[str] = None,
    extra: Optional[str] = None,
) -> None:
    if not perf_enabled():
        return
    rid = request_id or "-"
    line = f"{_timestamp_utc()} | {rid} | {label} | {file_function} | {elapsed_ms:.3f}"
    if extra:
        line = f"{line} | {extra}"

    log_path = os.environ.get("UASK_PERF_LOG_PATH", "").strip()
    if log_path:
        try:
            with _LOCK:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            return
        except Exception:
            # Fall back to logger if file write fails.
            pass
    _LOGGER.info(line)


@contextmanager
def perf_timer(
    *,
    label: str,
    file_function: str,
    request_id: Optional[str] = None,
    extra: Optional[str] = None,
) -> Iterator[None]:
    if not perf_enabled():
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - started) * 1000.0
        perf_emit(
            label=label,
            file_function=file_function,
            elapsed_ms=elapsed_ms,
            request_id=request_id,
            extra=extra,
        )
