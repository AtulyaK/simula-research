from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
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

_NIM_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_NIM_DEFAULT_MODEL = "llama-4-maverick-17b-128e-instruct"


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


def _parse_positive_int(name: str, raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def provider_runtime_from_env() -> dict[str, Any]:
    """Structured provider/runtime metadata for manifests (no secrets; env names only as strings)."""
    backend = (os.environ.get("SIMULA_CRITIC_BACKEND") or "").strip() or "hash_default"
    payload: dict[str, Any] = {
        "source": "environment",
        "critic_backend": backend,
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
    if backend.strip().lower() in {"nim", "nvidia"}:
        base_url = (
            (os.environ.get("SIMULA_NIM_BASE_URL") or "").strip()
            or (os.environ.get("SIMULA_NVIDIA_BASE_URL") or "").strip()
            or _NIM_DEFAULT_BASE_URL
        )
        default_model = (
            (os.environ.get("SIMULA_NIM_MODEL") or "").strip()
            or (os.environ.get("SIMULA_NVIDIA_MODEL") or "").strip()
            or _NIM_DEFAULT_MODEL
        )
        payload["nim_critic"] = {
            "base_url": base_url,
            "default_model": default_model,
            "api_key_env": (
                "NVIDIA_API_KEY"
                if os.environ.get("NVIDIA_API_KEY")
                else ("NVAPI_KEY" if os.environ.get("NVAPI_KEY") else None)
            ),
        }
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


def _nvidia_api_key_from_env() -> str:
    key = (os.environ.get("NVIDIA_API_KEY") or "").strip()
    if key:
        return key
    key = (os.environ.get("NVAPI_KEY") or "").strip()
    if key:
        return key
    raise ValueError("SIMULA_CRITIC_BACKEND=nim requires NVIDIA_API_KEY or NVAPI_KEY")


def _nvidia_model_for_critic(critic_id: str) -> str:
    if critic_id == "critic_a":
        if val := (os.environ.get("SIMULA_CRITIC_MODEL_A") or "").strip():
            return val
    if critic_id == "critic_b":
        if val := (os.environ.get("SIMULA_CRITIC_MODEL_B") or "").strip():
            return val
    if val := (os.environ.get("SIMULA_NIM_MODEL") or "").strip():
        return val
    if val := (os.environ.get("SIMULA_NVIDIA_MODEL") or "").strip():
        return val
    return _NIM_DEFAULT_MODEL


def _http_post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - url from env; used for API calls
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("nvidia_critic_invalid_response")
    return parsed


def _verdict_from_model_text(raw: str) -> CriticVerdict:
    text = (raw or "").strip().lower()
    if not text:
        raise ValueError("nvidia_critic_invalid_response")
    first = text.split()[0]
    if first.startswith("accept"):
        return "accept"
    if first.startswith("reject"):
        return "reject"
    has_accept = "accept" in text
    has_reject = "reject" in text
    if has_accept and not has_reject:
        return "accept"
    if has_reject and not has_accept:
        return "reject"
    raise ValueError("nvidia_critic_invalid_response")


def nvidia_critic_sample_evaluator(
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
    backoff_base_s: float | None = None,
    max_tokens: int | None = None,
    http_post_json: Callable[..., dict[str, Any]] = _http_post_json,
    event_log: list[dict[str, Any]] | None = None,
) -> CriticSampleEvaluatorFn:
    """
    Live NVIDIA NIM backend (OpenAI-compatible chat completions).

    NOTE: This evaluator intentionally avoids logging prompts/responses and sanitizes raised errors
    to prevent accidental leakage of sensitive content into operator logs.
    """

    resolved_base_url = (
        (base_url or "").strip()
        or (os.environ.get("SIMULA_NIM_BASE_URL") or "").strip()
        or (os.environ.get("SIMULA_NVIDIA_BASE_URL") or "").strip()
        or _NIM_DEFAULT_BASE_URL
    )
    resolved_timeout_s: float
    if timeout_s is not None:
        resolved_timeout_s = timeout_s
    elif raw := os.environ.get("SIMULA_HTTP_TIMEOUT_SECONDS"):
        resolved_timeout_s = _parse_positive_float("SIMULA_HTTP_TIMEOUT_SECONDS", raw)
    else:
        resolved_timeout_s = 30.0

    resolved_max_retries: int
    if max_retries is not None:
        resolved_max_retries = max_retries
    elif raw := os.environ.get("SIMULA_HTTP_MAX_RETRIES"):
        resolved_max_retries = _parse_non_negative_int("SIMULA_HTTP_MAX_RETRIES", raw)
    else:
        resolved_max_retries = 2

    resolved_backoff_base_s: float
    if backoff_base_s is not None:
        resolved_backoff_base_s = backoff_base_s
    elif raw := os.environ.get("SIMULA_HTTP_BACKOFF_BASE_SECONDS"):
        resolved_backoff_base_s = _parse_positive_float("SIMULA_HTTP_BACKOFF_BASE_SECONDS", raw)
    else:
        resolved_backoff_base_s = 0.5

    resolved_max_tokens: int
    if max_tokens is not None:
        resolved_max_tokens = max_tokens
    elif raw := os.environ.get("SIMULA_NVIDIA_MAX_TOKENS"):
        resolved_max_tokens = _parse_positive_int("SIMULA_NVIDIA_MAX_TOKENS", raw)
    else:
        resolved_max_tokens = 16

    api_key = _nvidia_api_key_from_env()

    def _eval(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        model = _nvidia_model_for_critic(critic_id)
        text = str(sample.get("text", ""))
        instantiation_id = str(sample.get("instantiation_id", ""))
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict binary classifier for a dataset curation pipeline. "
                        "Given the user's sample text, respond with exactly one token: accept or reject. "
                        "No punctuation, no explanation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": resolved_max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        def _op() -> CriticVerdict:
            try:
                resp = http_post_json(
                    url=resolved_base_url,
                    headers=headers,
                    payload=payload,
                    timeout_s=resolved_timeout_s,
                )
                choices = resp.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ValueError("nvidia_critic_invalid_response")
                msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                content = msg.get("content") if isinstance(msg, dict) else None
                return _verdict_from_model_text(str(content or ""))
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                raise RuntimeError(f"nvidia_critic_request_failed:{type(exc).__name__}") from exc

        try:
            return retry_with_backoff(
                _op,
                max_retries=resolved_max_retries,
                backoff_base_s=resolved_backoff_base_s,
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary must not fail open
            # Fail-closed: any inability to produce a clear verdict yields "reject".
            # Record structured metadata without leaking prompt text.
            if event_log is not None:
                event_log.append(
                    {
                        "backend": "nim",
                        "critic_id": critic_id,
                        "instantiation_id": instantiation_id,
                        "model": model,
                        "base_url": resolved_base_url,
                        "timeout_s": resolved_timeout_s,
                        "max_retries": resolved_max_retries,
                        "error_type": type(exc).__name__,
                        "error_code": (
                            str(exc).split(":", 1)[0]
                            if isinstance(exc, RuntimeError)
                            else "nvidia_critic_error"
                        ),
                        "verdict": "reject",
                    }
                )
            return "reject"

    return _eval


def critic_sample_evaluator_from_env() -> CriticSampleEvaluatorFn | None:
    """Return None to keep hash-based default; otherwise a non-network evaluator for smoke wiring."""
    mode = (os.environ.get("SIMULA_CRITIC_BACKEND") or "").strip().lower()
    if mode in {"", "hash", "default"}:
        return None
    if mode == "stub":
        return sample_evaluator_from_text_fn(hash_based_critic_verdict)
    if mode in {"nim", "nvidia"}:
        return nvidia_critic_sample_evaluator()
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
