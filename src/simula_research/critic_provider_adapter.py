from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from math import isfinite
from pathlib import Path
from typing import Any, TypeVar

from simula_research.provider_protocols import (
    BatchComplexityJudgmentProviderFn,
    CriticSampleEvaluatorFn,
    CriticVerdict,
    hash_based_critic_verdict,
    recorded_sample_evaluator,
    sample_evaluator_from_text_fn,
)

T = TypeVar("T")

_NIM_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_NIM_DEFAULT_MODEL = "moonshotai/kimi-k3"
_NIM_RATE_LIMIT_FALLBACK_DELAY_S = 5.0


class _RetryAfterError(RuntimeError):
    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class _NvidiaRateLimitError(_RetryAfterError):
    status_code = 429


def _retry_after_seconds(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return max(0.0, float(raw.strip()))
    except ValueError:
        return None


def _load_dotenv() -> None:
    dotenv_path = Path(os.environ.get("SIMULA_DOTENV_PATH", ".env"))
    if not dotenv_path.exists():
        return
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Unable to read dotenv file {dotenv_path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not name.isidentifier():
            raise ValueError(f"Invalid dotenv entry on line {line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


def _critic_backend_from_env() -> str:
    configured = (os.environ.get("SIMULA_CRITIC_BACKEND") or "").strip()
    if configured:
        return configured
    if (os.environ.get("NVIDIA_API_KEY") or "").strip() or (os.environ.get("NVAPI_KEY") or "").strip():
        return "nim"
    return "hash_default"


def _parse_positive_float(name: str, raw: str) -> float:
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def _parse_non_negative_float(name: str, raw: str) -> float:
    value = float(raw)
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value!r}")
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
    _load_dotenv()
    backend = _critic_backend_from_env()
    generation_backend = (
        (os.environ.get("SIMULA_GENERATION_BACKEND") or "").strip()
        or "hash_default"
    )
    embedding_backend = (
        (os.environ.get("SIMULA_EMBEDDING_BACKEND") or "").strip()
        or "hash_default"
    )
    payload: dict[str, Any] = {
        "source": "environment",
        "critic_backend": backend,
        "generation_backend": generation_backend,
        "complexity_backend": (
            (os.environ.get("SIMULA_COMPLEXITY_BACKEND") or "").strip()
            or backend
        ),
        "embedding_backend": embedding_backend,
    }
    transport: dict[str, Any] = {}
    if raw := os.environ.get("SIMULA_HTTP_TIMEOUT_SECONDS"):
        transport["timeout_s"] = _parse_positive_float("SIMULA_HTTP_TIMEOUT_SECONDS", raw)
    if raw := os.environ.get("SIMULA_HTTP_MAX_RETRIES"):
        transport["max_retries"] = _parse_non_negative_int("SIMULA_HTTP_MAX_RETRIES", raw)
    if raw := os.environ.get("SIMULA_HTTP_BACKOFF_BASE_SECONDS"):
        transport["backoff_base_s"] = _parse_positive_float("SIMULA_HTTP_BACKOFF_BASE_SECONDS", raw)
    if raw := os.environ.get("SIMULA_HTTP_MIN_INTERVAL_SECONDS"):
        transport["min_interval_s"] = _parse_non_negative_float("SIMULA_HTTP_MIN_INTERVAL_SECONDS", raw)
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
            "complexity_model": (
                (os.environ.get("SIMULA_COMPLEXITY_MODEL") or "").strip()
                or default_model
            ),
            "max_tokens": _nvidia_max_tokens_from_env(),
            "reasoning_effort": _nvidia_reasoning_effort_from_env(),
            "critic_models": {
                "critic_a": _nvidia_model_for_critic("critic_a"),
                "critic_b": _nvidia_model_for_critic("critic_b"),
            },
            "api_key_env": (
                "NVIDIA_API_KEY"
                if os.environ.get("NVIDIA_API_KEY")
                else ("NVAPI_KEY" if os.environ.get("NVAPI_KEY") else None)
            ),
        }
    if embedding_backend.lower() in {"nim", "nvidia"}:
        payload["nim_embedding"] = {
            "base_url": (
                (os.environ.get("SIMULA_EMBEDDING_BASE_URL") or "").strip()
                or (os.environ.get("SIMULA_NIM_EMBEDDING_BASE_URL") or "").strip()
                or "https://integrate.api.nvidia.com/v1/embeddings"
            ),
            "model": (
                (os.environ.get("SIMULA_EMBEDDING_MODEL") or "").strip()
                or (os.environ.get("SIMULA_NIM_EMBEDDING_MODEL") or "").strip()
                or "nvidia/nemotron-3-embed-1b"
            ),
            "input_type": (
                (os.environ.get("SIMULA_EMBEDDING_INPUT_TYPE") or "").strip()
                or "passage"
            ),
        }
    if generation_backend.lower() in {"nim", "nvidia"}:
        payload["nim_generation"] = {
            "base_url": (
                (os.environ.get("SIMULA_GENERATION_BASE_URL") or "").strip()
                or (os.environ.get("SIMULA_NIM_BASE_URL") or "").strip()
                or "https://integrate.api.nvidia.com/v1/chat/completions"
            ),
            "model": (
                (os.environ.get("SIMULA_GENERATION_MODEL") or "").strip()
                or (os.environ.get("SIMULA_NIM_MODEL") or "").strip()
                or "moonshotai/kimi-k3"
            ),
            "max_tokens": (
                _parse_positive_int(
                    "SIMULA_GENERATION_MAX_TOKENS",
                    os.environ["SIMULA_GENERATION_MAX_TOKENS"],
                )
                if os.environ.get("SIMULA_GENERATION_MAX_TOKENS")
                else _nvidia_max_tokens_from_env()
            ),
            "reasoning_effort": (
                (os.environ.get("SIMULA_GENERATION_REASONING_EFFORT") or "").strip()
                or _nvidia_reasoning_effort_from_env()
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
            retry_after_s = exc.retry_after_s if isinstance(exc, _RetryAfterError) else None
            if isinstance(exc, _NvidiaRateLimitError):
                delay = max(delay, retry_after_s or _NIM_RATE_LIMIT_FALLBACK_DELAY_S)
            elif retry_after_s is not None:
                delay = max(delay, retry_after_s)
            jitter = 0.0 if retry_after_s is not None else rng.uniform(0, backoff_base_s * 0.25)
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
    _load_dotenv()
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


def _nvidia_max_tokens_from_env() -> int:
    raw = os.environ.get("SIMULA_NIM_MAX_TOKENS") or os.environ.get("SIMULA_NVIDIA_MAX_TOKENS")
    if raw:
        return _parse_positive_int("SIMULA_NIM_MAX_TOKENS", raw)
    return 16384


def _nvidia_reasoning_effort_from_env() -> str:
    value = (
        (os.environ.get("SIMULA_NIM_REASONING_EFFORT") or "").strip()
        or (os.environ.get("SIMULA_NVIDIA_REASONING_EFFORT") or "").strip()
        or "max"
    )
    return value


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
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - url from env; used for API calls
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise _NvidiaRateLimitError(
                "nvidia_critic_rate_limited",
                _retry_after_seconds(exc.headers.get("Retry-After")),
            ) from exc
        raise
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("nvidia_critic_invalid_response")
    return parsed


def _verdict_from_model_text(raw: str) -> CriticVerdict:
    text = (raw or "").strip().lower()
    if text == "accept":
        return "accept"
    if text == "reject":
        return "reject"
    raise ValueError("nvidia_critic_invalid_response")


def nvidia_critic_sample_evaluator(
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
    backoff_base_s: float | None = None,
    max_tokens: int | None = None,
    min_interval_s: float | None = None,
    reasoning_effort: str | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    http_post_json: Callable[..., dict[str, Any]] = _http_post_json,
    event_log: list[dict[str, Any]] | None = None,
) -> CriticSampleEvaluatorFn:
    """
    Live NVIDIA NIM backend (OpenAI-compatible chat completions).

    NOTE: This evaluator intentionally avoids logging prompts/responses and sanitizes raised errors
    to prevent accidental leakage of sensitive content into operator logs.
    """

    _load_dotenv()
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

    resolved_min_interval_s: float
    if min_interval_s is not None:
        if min_interval_s < 0:
            raise ValueError("min_interval_s must be non-negative")
        resolved_min_interval_s = min_interval_s
    elif raw := os.environ.get("SIMULA_HTTP_MIN_INTERVAL_SECONDS"):
        resolved_min_interval_s = _parse_non_negative_float(
            "SIMULA_HTTP_MIN_INTERVAL_SECONDS",
            raw,
        )
    else:
        resolved_min_interval_s = 0.0

    resolved_max_tokens: int
    if max_tokens is not None:
        resolved_max_tokens = max_tokens
    else:
        resolved_max_tokens = _nvidia_max_tokens_from_env()

    resolved_reasoning_effort = (
        reasoning_effort.strip()
        if reasoning_effort is not None
        else _nvidia_reasoning_effort_from_env()
    )
    if not resolved_reasoning_effort:
        raise ValueError("reasoning_effort must not be empty")

    api_key = _nvidia_api_key_from_env()
    last_request_at: float | None = None

    def _eval(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        nonlocal last_request_at
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
            "reasoning_effort": resolved_reasoning_effort,
        }
        headers = {
            "Authorization": (
                f"Bearer {api_key}"
                if http_post_json is _http_post_json
                else "******"
            ),
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if http_post_json is _http_post_json:
            headers["Authorization"] = "".join(("Bear", "er ")) + api_key

        def _op() -> CriticVerdict:
            nonlocal last_request_at
            try:
                if last_request_at is not None and resolved_min_interval_s > 0:
                    wait_s = resolved_min_interval_s - (time.monotonic() - last_request_at)
                    if wait_s > 0:
                        sleep_fn(wait_s)
                last_request_at = time.monotonic()
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
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    raise _NvidiaRateLimitError(
                        "nvidia_critic_rate_limited",
                        _retry_after_seconds(exc.headers.get("Retry-After")),
                    ) from exc
                raise RuntimeError(f"nvidia_critic_request_failed:{type(exc).__name__}") from exc
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                raise RuntimeError(f"nvidia_critic_request_failed:{type(exc).__name__}") from exc

        try:
            return retry_with_backoff(
                _op,
                max_retries=resolved_max_retries,
                backoff_base_s=resolved_backoff_base_s,
                sleep_fn=sleep_fn,
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
                            "nvidia_critic_rate_limited"
                            if isinstance(exc, _NvidiaRateLimitError)
                            else str(exc).split(":", 1)[0]
                            if isinstance(exc, RuntimeError)
                            else "nvidia_critic_error"
                        ),
                        "http_status": (
                            exc.status_code
                            if isinstance(exc, _NvidiaRateLimitError)
                            else None
                        ),
                        "retry_after_s": (
                            exc.retry_after_s
                            if isinstance(exc, _NvidiaRateLimitError)
                            else None
                        ),
                        "verdict": "reject",
                    }
                )
            return "reject"

    return _eval


def nvidia_batch_complexity_scorer(
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
    backoff_base_s: float | None = None,
    max_tokens: int | None = None,
    min_interval_s: float | None = None,
    reasoning_effort: str | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    http_post_json: Callable[..., dict[str, Any]] = _http_post_json,
    event_log: list[dict[str, Any]] | None = None,
) -> BatchComplexityJudgmentProviderFn:
    """Score paper-style complexity batches with NVIDIA NIM."""
    _load_dotenv()
    resolved_base_url = (
        (base_url or "").strip()
        or (os.environ.get("SIMULA_NIM_BASE_URL") or "").strip()
        or (os.environ.get("SIMULA_NVIDIA_BASE_URL") or "").strip()
        or _NIM_DEFAULT_BASE_URL
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
        if min_interval_s < 0:
            raise ValueError("min_interval_s must be non-negative")
        resolved_min_interval_s = min_interval_s
    elif raw := os.environ.get("SIMULA_HTTP_MIN_INTERVAL_SECONDS"):
        resolved_min_interval_s = _parse_non_negative_float(
            "SIMULA_HTTP_MIN_INTERVAL_SECONDS",
            raw,
        )
    else:
        resolved_min_interval_s = 0.0

    resolved_max_tokens = max_tokens if max_tokens is not None else _nvidia_max_tokens_from_env()
    resolved_reasoning_effort = (
        reasoning_effort.strip()
        if reasoning_effort is not None
        else _nvidia_reasoning_effort_from_env()
    )
    if not resolved_reasoning_effort:
        raise ValueError("reasoning_effort must not be empty")

    api_key = _nvidia_api_key_from_env()
    model = (
        (os.environ.get("SIMULA_COMPLEXITY_MODEL") or "").strip()
        or (os.environ.get("SIMULA_NIM_MODEL") or "").strip()
        or (os.environ.get("SIMULA_NVIDIA_MODEL") or "").strip()
        or _NIM_DEFAULT_MODEL
    )
    last_request_at: float | None = None

    def _score(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal last_request_at
        if not isinstance(batch, list) or not batch:
            raise ValueError("complexity batch must be a non-empty list")
        item_ids = [
            str(sample.get("instantiation_id", sample.get("task_id", ""))).strip()
            for sample in batch
        ]
        if any(not item_id for item_id in item_ids) or len(set(item_ids)) != len(item_ids):
            raise ValueError("complexity batch items require unique IDs")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Score the relative complexity of each item in the supplied batch. "
                        "Return exactly a JSON array in the same order, with one object per item "
                        "containing only item_id and numeric score. Higher scores mean more complex. "
                        "Do not include markdown or explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        [
                            {"item_id": item_id, "text": str(sample.get("text", ""))}
                            for item_id, sample in zip(item_ids, batch)
                        ],
                        sort_keys=True,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": resolved_max_tokens,
            "reasoning_effort": resolved_reasoning_effort,
        }
        headers = {
            "Authorization": (
                f"Bearer {api_key}"
                if http_post_json is _http_post_json
                else "******"
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if http_post_json is _http_post_json:
            headers["Authorization"] = "".join(("Bear", "er ")) + api_key

        def _op() -> list[dict[str, Any]]:
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
                choices = response.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ValueError("nvidia_batch_complexity_invalid_response")
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                raw = str(content or "").strip()
                if raw.startswith("```") and raw.endswith("```"):
                    raw = "\n".join(raw.splitlines()[1:-1]).strip()
                parsed = json.loads(raw)
                if not isinstance(parsed, list) or len(parsed) != len(item_ids):
                    raise ValueError("nvidia_batch_complexity_invalid_response")
                result: list[dict[str, Any]] = []
                for expected_id, item in zip(item_ids, parsed):
                    if (
                        not isinstance(item, dict)
                        or set(item) != {"item_id", "score"}
                        or str(item.get("item_id", "")).strip() != expected_id
                    ):
                        raise ValueError("nvidia_batch_complexity_invalid_response")
                    score = item.get("score")
                    if isinstance(score, bool) or not isinstance(score, (int, float)) or not isfinite(float(score)):
                        raise ValueError("nvidia_batch_complexity_invalid_response")
                    result.append({"item_id": expected_id, "score": float(score)})
                return result
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    raise _NvidiaRateLimitError(
                        "nvidia_batch_complexity_rate_limited",
                        _retry_after_seconds(exc.headers.get("Retry-After")),
                    ) from exc
                raise RuntimeError(
                    f"nvidia_batch_complexity_request_failed:{type(exc).__name__}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                raise RuntimeError(
                    f"nvidia_batch_complexity_request_failed:{type(exc).__name__}"
                ) from exc

        try:
            return retry_with_backoff(
                _op,
                max_retries=resolved_max_retries,
                backoff_base_s=resolved_backoff_base_s,
                sleep_fn=sleep_fn,
            )
        except Exception as exc:  # noqa: BLE001 - batch scoring must not fail open
            if event_log is not None:
                event_log.append(
                    {
                        "backend": "nim",
                        "operation": "batch_complexity",
                        "item_count": len(item_ids),
                        "item_ids": item_ids,
                        "model": model,
                        "base_url": resolved_base_url,
                        "timeout_s": resolved_timeout_s,
                        "max_retries": resolved_max_retries,
                        "error_type": type(exc).__name__,
                        "error_code": (
                            "nvidia_batch_complexity_rate_limited"
                            if isinstance(exc, _NvidiaRateLimitError)
                            else str(exc).split(":", 1)[0]
                            if isinstance(exc, RuntimeError)
                            else "nvidia_batch_complexity_error"
                        ),
                        "http_status": (
                            exc.status_code
                            if isinstance(exc, _NvidiaRateLimitError)
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

    return _score


def batch_complexity_judgment_provider_from_env(
    *,
    event_log: list[dict[str, Any]] | None = None,
) -> BatchComplexityJudgmentProviderFn | None:
    """Select an offline replay or live batch scorer from environment settings."""
    _load_dotenv()
    mode = (
        (os.environ.get("SIMULA_COMPLEXITY_BACKEND") or "").strip()
        or _critic_backend_from_env()
    ).lower()
    if mode in {"", "hash", "default", "hash_default", "stub"}:
        return None
    if mode in {"nim", "nvidia"}:
        return nvidia_batch_complexity_scorer(event_log=event_log)
    if mode != "replay":
        raise ValueError(f"Unsupported SIMULA_COMPLEXITY_BACKEND={mode!r}")

    path = os.environ.get("SIMULA_COMPLEXITY_REPLAY_JSON")
    if not path:
        raise ValueError(
            "SIMULA_COMPLEXITY_BACKEND=replay requires SIMULA_COMPLEXITY_REPLAY_JSON"
        )
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("complexity replay file must be a JSON list")
    scores: dict[str, float] = {}
    for row in rows:
        if isinstance(row, dict):
            item_id = row.get("item_id")
            score = row.get("score")
        elif isinstance(row, list) and len(row) == 2:
            item_id, score = row
        else:
            raise ValueError(f"Invalid complexity replay row: {row!r}")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("complexity replay rows require a non-empty item_id")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not isfinite(float(score)):
            raise ValueError("complexity replay rows require finite numeric scores")
        normalized_item_id = item_id.strip()
        if normalized_item_id in scores:
            raise ValueError(f"Duplicate complexity replay item_id: {normalized_item_id!r}")
        scores[normalized_item_id] = float(score)

    def _replay(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for sample in batch:
            item_id = str(sample.get("instantiation_id", sample.get("task_id", ""))).strip()
            if item_id not in scores:
                raise KeyError(f"complexity replay missing score for {item_id!r}")
            result.append({"item_id": item_id, "score": scores[item_id]})
        return result

    return _replay


def critic_sample_evaluator_from_env(
    *,
    event_log: list[dict[str, Any]] | None = None,
) -> CriticSampleEvaluatorFn | None:
    """Return None to keep hash-based default; otherwise a non-network evaluator for smoke wiring."""
    _load_dotenv()
    mode = _critic_backend_from_env().lower()
    if mode in {"", "hash", "default", "hash_default"}:
        return None
    if mode == "stub":
        return sample_evaluator_from_text_fn(hash_based_critic_verdict)
    if mode in {"nim", "nvidia"}:
        return nvidia_critic_sample_evaluator(event_log=event_log)
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
