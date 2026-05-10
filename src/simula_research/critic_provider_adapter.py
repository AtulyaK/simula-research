from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from simula_research.provider_protocols import (
    CriticSampleEvaluatorFn,
    CriticVerdict,
    hash_based_critic_verdict,
    recorded_sample_evaluator,
    sample_evaluator_from_text_fn,
)

T = TypeVar("T")


def _parse_positive_float(name: str, raw: str) -> float:
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def _parse_non_negative_int(name: str, raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value!r}")
    return value


def provider_runtime_from_env() -> dict[str, Any]:
    """Structured provider/runtime metadata for manifests (no secrets; env names only as strings)."""
    payload: dict[str, Any] = {
        "source": "environment",
        "critic_backend": (os.environ.get("SIMULA_CRITIC_BACKEND") or "").strip() or "hash_default",
    }
    transport: dict[str, Any] = {}
    if raw := os.environ.get("SIMULA_HTTP_TIMEOUT_SECONDS"):
        transport["timeout_s"] = _parse_positive_float("SIMULA_HTTP_TIMEOUT_SECONDS", raw)
    if raw := os.environ.get("SIMULA_HTTP_MAX_RETRIES"):
        transport["max_retries"] = _parse_non_negative_int("SIMULA_HTTP_MAX_RETRIES", raw)
    if raw := os.environ.get("SIMULA_HTTP_BACKOFF_BASE_SECONDS"):
        transport["backoff_base_s"] = _parse_positive_float("SIMULA_HTTP_BACKOFF_BASE_SECONDS", raw)
    if transport:
        payload["http_transport"] = transport
    for key in ("SIMULA_CRITIC_MODEL_A", "SIMULA_CRITIC_MODEL_B"):
        if val := os.environ.get(key):
            payload.setdefault("model_env_aliases", {})[key] = val
    return payload


def retry_with_backoff(
    operation: Callable[[], T],
    *,
    max_retries: int,
    backoff_base_s: float,
    rng: random.Random | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Bounded retries with linear backoff (stdlib-only; suitable for transport wrappers)."""
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    rng = rng or random.Random()
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 — boundary for transport retries
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = backoff_base_s * (attempt + 1)
            jitter = rng.uniform(0, backoff_base_s * 0.25)
            sleep_fn(delay + jitter)
    assert last_exc is not None
    raise last_exc


def logging_critic_sample_evaluator(
    inner: CriticSampleEvaluatorFn,
    failure_log: list[dict[str, Any]],
) -> CriticSampleEvaluatorFn:
    """Capture structured failure rows (no raw prompts) for operator review."""

    def _wrapped(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        try:
            return inner(sample, critic_id)
        except Exception as exc:  # noqa: BLE001
            failure_log.append(
                {
                    "critic_id": critic_id,
                    "instantiation_id": str(sample.get("instantiation_id", "")),
                    "error_type": type(exc).__name__,
                }
            )
            raise

    return _wrapped


def critic_sample_evaluator_from_env() -> CriticSampleEvaluatorFn | None:
    """Return None to keep hash-based default; otherwise a non-network evaluator for smoke wiring."""
    mode = (os.environ.get("SIMULA_CRITIC_BACKEND") or "").strip().lower()
    if mode in {"", "hash", "default"}:
        return None
    if mode == "stub":
        return sample_evaluator_from_text_fn(hash_based_critic_verdict)
    if mode == "replay":
        path = os.environ.get("SIMULA_CRITIC_REPLAY_JSON")
        if not path:
            raise ValueError("SIMULA_CRITIC_BACKEND=replay requires SIMULA_CRITIC_REPLAY_JSON")
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("replay file must be a JSON list of [instantiation_id,critic_id,text,verdict]")
        table: dict[tuple[str, str, str], CriticVerdict] = {}
        for row in rows:
            if not isinstance(row, list) or len(row) != 4:
                raise ValueError(f"Invalid replay row: {row!r}")
            inst, critic, text, verdict = row
            if verdict not in ("accept", "reject"):
                raise ValueError(f"Invalid verdict in replay row: {verdict!r}")
            table[(str(inst), str(critic), str(text))] = verdict
        return recorded_sample_evaluator(table)
    raise ValueError(f"Unsupported SIMULA_CRITIC_BACKEND={mode!r}")
