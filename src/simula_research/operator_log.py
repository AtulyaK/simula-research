"""Sanitized stderr logging for operator runs (enable with SIMULA_VERBOSE=1 or SIMULA_LOG=1)."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any


def is_verbose() -> bool:
    raw = (os.environ.get("SIMULA_VERBOSE") or os.environ.get("SIMULA_LOG") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def log_step(message: str) -> None:
    if is_verbose():
        print(f"[simula {_timestamp()}] {message}", file=sys.stderr, flush=True)


def log_detail(key: str, value: Any) -> None:
    if is_verbose():
        print(f"[simula {_timestamp()}]   {key}={value}", file=sys.stderr, flush=True)


def log_stage_start(stage: str, **details: Any) -> None:
    if not is_verbose():
        return
    log_step(f"stage start: {stage}")
    for k, v in details.items():
        log_detail(k, v)


def log_stage_complete(stage: str, **details: Any) -> None:
    if not is_verbose():
        return
    log_step(f"stage complete: {stage}")
    for k, v in details.items():
        log_detail(k, v)
