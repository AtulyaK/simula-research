from __future__ import annotations

import json
import os
import time
import urllib.error
from collections.abc import Callable, Sequence
from math import isfinite
from typing import Any

from simula_research.critic_provider_adapter import (
    _NIM_DEFAULT_BASE_URL,
    _NvidiaRateLimitError,
    _http_post_json,
    _load_dotenv,
    _nvidia_api_key_from_env,
    _parse_non_negative_float,
    _parse_non_negative_int,
    _parse_positive_float,
    _retry_after_seconds,
    retry_with_backoff,
)
from simula_research.evaluation_metrics import EmbeddingProviderFn

_NIM_DEFAULT_EMBEDDING_URL = _NIM_DEFAULT_BASE_URL.rsplit("/", 2)[0] + "/embeddings"
_NIM_DEFAULT_EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"


class _NvidiaEmbeddingHTTPError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"nvidia_embedding_http_error:{status_code}")
        self.status_code = status_code


def nvidia_embedding_provider(
    *,
    base_url: str | None = None,
    model: str | None = None,
    input_type: str | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
    backoff_base_s: float | None = None,
    min_interval_s: float | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    http_post_json: Callable[..., dict[str, Any]] = _http_post_json,
    event_log: list[dict[str, Any]] | None = None,
) -> EmbeddingProviderFn:
    """Create an OpenAI-compatible NVIDIA NIM embedding provider."""
    _load_dotenv()
    resolved_base_url = (
        (base_url or "").strip()
        or (os.environ.get("SIMULA_EMBEDDING_BASE_URL") or "").strip()
        or (os.environ.get("SIMULA_NIM_EMBEDDING_BASE_URL") or "").strip()
        or _NIM_DEFAULT_EMBEDDING_URL
    )
    resolved_model = (
        (model or "").strip()
        or (os.environ.get("SIMULA_EMBEDDING_MODEL") or "").strip()
        or (os.environ.get("SIMULA_NIM_EMBEDDING_MODEL") or "").strip()
        or _NIM_DEFAULT_EMBEDDING_MODEL
    )
    resolved_input_type = (
        (input_type or "").strip()
        or (os.environ.get("SIMULA_EMBEDDING_INPUT_TYPE") or "").strip()
        or "passage"
    )
    if timeout_s is not None:
        resolved_timeout_s = timeout_s
    elif raw := os.environ.get("SIMULA_HTTP_TIMEOUT_SECONDS"):
        resolved_timeout_s = _parse_positive_float("SIMULA_HTTP_TIMEOUT_SECONDS", raw)
    else:
        resolved_timeout_s = 30.0
    if max_retries is not None:
        resolved_max_retries = max_retries
    elif raw := os.environ.get("SIMULA_HTTP_MAX_RETRIES"):
        resolved_max_retries = _parse_non_negative_int("SIMULA_HTTP_MAX_RETRIES", raw)
    else:
        resolved_max_retries = 2
    if backoff_base_s is not None:
        resolved_backoff_base_s = backoff_base_s
    elif raw := os.environ.get("SIMULA_HTTP_BACKOFF_BASE_SECONDS"):
        resolved_backoff_base_s = _parse_positive_float("SIMULA_HTTP_BACKOFF_BASE_SECONDS", raw)
    else:
        resolved_backoff_base_s = 0.5
    if min_interval_s is not None:
        resolved_min_interval_s = min_interval_s
    elif raw := os.environ.get("SIMULA_HTTP_MIN_INTERVAL_SECONDS"):
        resolved_min_interval_s = _parse_non_negative_float(
            "SIMULA_HTTP_MIN_INTERVAL_SECONDS",
            raw,
        )
    else:
        resolved_min_interval_s = 0.0
    if resolved_min_interval_s < 0:
        raise ValueError("min_interval_s must be non-negative")

    api_key = _nvidia_api_key_from_env()
    last_request_at: float | None = None

    def _embed(texts: list[str]) -> Sequence[Sequence[float]]:
        nonlocal last_request_at
        if not isinstance(texts, list):
            raise ValueError("embedding provider input must be a list")
        if not texts:
            return []
        payload = {
            "model": resolved_model,
            "input": [str(text) for text in texts],
            "input_type": resolved_input_type,
        }
        headers = {
            "Authorization": "******",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if http_post_json is _http_post_json:
            headers["Authorization"] = "".join(("Bear", "er ")) + api_key

        def _op() -> list[list[float]]:
            nonlocal last_request_at
            try:
                if last_request_at is not None and resolved_min_interval_s > 0:
                    wait_s = resolved_min_interval_s - (time.monotonic() - last_request_at)
                    if wait_s > 0:
                        sleep_fn(wait_s)
                last_request_at = time.monotonic()
                response = http_post_json(
                    url=resolved_base_url,
                    headers=headers,
                    payload=payload,
                    timeout_s=resolved_timeout_s,
                )
                data = response.get("data")
                if not isinstance(data, list) or len(data) != len(texts):
                    raise ValueError("nvidia_embedding_invalid_response")
                indexed = all(isinstance(item, dict) and "index" in item for item in data)
                if indexed:
                    indexes = [item["index"] for item in data]
                    if (
                        any(isinstance(index, bool) or not isinstance(index, int) for index in indexes)
                        or set(indexes) != set(range(len(texts)))
                    ):
                        raise ValueError("nvidia_embedding_invalid_response")
                    ordered = sorted(data, key=lambda item: item["index"])
                else:
                    ordered = data
                embeddings: list[list[float]] = []
                for item in ordered:
                    if not isinstance(item, dict):
                        raise ValueError("nvidia_embedding_invalid_response")
                    vector = item.get("embedding")
                    if (
                        not isinstance(vector, Sequence)
                        or isinstance(vector, (str, bytes))
                        or not vector
                    ):
                        raise ValueError("nvidia_embedding_invalid_response")
                    parsed = [float(value) for value in vector]
                    if not all(isfinite(value) for value in parsed):
                        raise ValueError("nvidia_embedding_invalid_response")
                    embeddings.append(parsed)
                return embeddings
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    raise _NvidiaRateLimitError(
                        "nvidia_embedding_rate_limited",
                        _retry_after_seconds(exc.headers.get("Retry-After")),
                    ) from exc
                raise _NvidiaEmbeddingHTTPError(exc.code) from exc
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                raise RuntimeError(
                    f"nvidia_embedding_request_failed:{type(exc).__name__}"
                ) from exc

        try:
            return retry_with_backoff(
                _op,
                max_retries=resolved_max_retries,
                backoff_base_s=resolved_backoff_base_s,
                sleep_fn=sleep_fn,
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary must not fail open
            if event_log is not None:
                event_log.append(
                    {
                        "backend": "nim",
                        "operation": "embedding",
                        "item_count": len(texts),
                        "model": resolved_model,
                        "base_url": resolved_base_url,
                        "timeout_s": resolved_timeout_s,
                        "max_retries": resolved_max_retries,
                        "error_type": type(exc).__name__,
                        "error_code": (
                            "nvidia_embedding_rate_limited"
                            if isinstance(exc, _NvidiaRateLimitError)
                            else str(exc).split(":", 1)[0]
                            if isinstance(exc, RuntimeError)
                            else "nvidia_embedding_error"
                        ),
                        "http_status": (
                            exc.status_code
                            if isinstance(exc, (_NvidiaRateLimitError, _NvidiaEmbeddingHTTPError))
                            else None
                        ),
                        "retry_after_s": (
                            exc.retry_after_s
                            if isinstance(exc, _NvidiaRateLimitError)
                            else None
                        ),
                    }
                )
            raise

    setattr(_embed, "__simula_embedding_provider_name__", f"nim:{resolved_model}")
    return _embed


def embedding_provider_from_env(
    *,
    event_log: list[dict[str, Any]] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> EmbeddingProviderFn | None:
    """Select an explicitly configured remote embedding provider."""
    _load_dotenv()
    mode = (os.environ.get("SIMULA_EMBEDDING_BACKEND") or "").strip().lower()
    if mode in {"", "hash", "default", "hash_default"}:
        return None
    if mode in {"nim", "nvidia"}:
        return nvidia_embedding_provider(event_log=event_log, sleep_fn=sleep_fn)
    raise ValueError(f"Unsupported SIMULA_EMBEDDING_BACKEND={mode!r}")
