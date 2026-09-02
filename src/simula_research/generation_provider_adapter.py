from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from hashlib import sha1
from math import isfinite
from typing import Any

from simula_research.critic_provider_adapter import (
    _NIM_DEFAULT_BASE_URL,
    _NIM_DEFAULT_MODEL,
    _NvidiaRateLimitError,
    _http_post_json,
    _load_dotenv,
    _nvidia_api_key_from_env,
    _nvidia_max_tokens_from_env,
    _nvidia_reasoning_effort_from_env,
    _parse_non_negative_float,
    _parse_non_negative_int,
    _parse_positive_float,
    retry_with_backoff,
)
from simula_research.local_diversification import _token_overlap_ratio
from simula_research.provider_protocols import (
    ComplexificationProviderFn,
    LocalDiversificationProviderFn,
    TaxonomyProviderFn,
)
from simula_research.taxonomy import (
    TaxonomyConfig,
    _normalize_label,
    _taxonomy_node_id,
)


def _stable_id(*parts: str) -> str:
    return sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]


def _json_content(response: dict[str, Any], *, operation: str) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"{operation}_invalid_response")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{operation}_invalid_response")
    return content.strip()


def _parse_json_content(raw: str, *, operation: str) -> Any:
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{operation}_invalid_json") from error


def _text_completion_settings(
    *,
    base_url: str | None,
    timeout_s: float | None,
    max_retries: int | None,
    backoff_base_s: float | None,
    max_tokens: int | None,
    min_interval_s: float | None,
    reasoning_effort: str | None,
    model: str | None,
) -> dict[str, Any]:
    _load_dotenv()
    resolved_timeout = (
        timeout_s
        if timeout_s is not None
        else _parse_positive_float(
            "SIMULA_HTTP_TIMEOUT_SECONDS",
            os.environ["SIMULA_HTTP_TIMEOUT_SECONDS"],
        )
        if os.environ.get("SIMULA_HTTP_TIMEOUT_SECONDS")
        else 30.0
    )
    resolved_retries = (
        max_retries
        if max_retries is not None
        else _parse_non_negative_int(
            "SIMULA_HTTP_MAX_RETRIES",
            os.environ["SIMULA_HTTP_MAX_RETRIES"],
        )
        if os.environ.get("SIMULA_HTTP_MAX_RETRIES")
        else 2
    )
    resolved_backoff = (
        backoff_base_s
        if backoff_base_s is not None
        else _parse_positive_float(
            "SIMULA_HTTP_BACKOFF_BASE_SECONDS",
            os.environ["SIMULA_HTTP_BACKOFF_BASE_SECONDS"],
        )
        if os.environ.get("SIMULA_HTTP_BACKOFF_BASE_SECONDS")
        else 0.5
    )
    resolved_interval = (
        min_interval_s
        if min_interval_s is not None
        else _parse_non_negative_float(
            "SIMULA_HTTP_MIN_INTERVAL_SECONDS",
            os.environ["SIMULA_HTTP_MIN_INTERVAL_SECONDS"],
        )
        if os.environ.get("SIMULA_HTTP_MIN_INTERVAL_SECONDS")
        else 0.0
    )
    if resolved_interval < 0:
        raise ValueError("min_interval_s must be non-negative")
    resolved_reasoning = (
        reasoning_effort.strip()
        if reasoning_effort is not None
        else (
            (os.environ.get("SIMULA_GENERATION_REASONING_EFFORT") or "").strip()
            or _nvidia_reasoning_effort_from_env()
        )
    )
    if not resolved_reasoning:
        raise ValueError("reasoning_effort must not be empty")
    resolved_model = (
        (model or "").strip()
        or (os.environ.get("SIMULA_GENERATION_MODEL") or "").strip()
        or (os.environ.get("SIMULA_NIM_MODEL") or "").strip()
        or (os.environ.get("SIMULA_NVIDIA_MODEL") or "").strip()
        or _NIM_DEFAULT_MODEL
    )
    resolved_base = (
        (base_url or "").strip()
        or (os.environ.get("SIMULA_GENERATION_BASE_URL") or "").strip()
        or (os.environ.get("SIMULA_NIM_BASE_URL") or "").strip()
        or (os.environ.get("SIMULA_NVIDIA_BASE_URL") or "").strip()
        or _NIM_DEFAULT_BASE_URL
    )
    resolved_tokens = (
        max_tokens
        if max_tokens is not None
        else _parse_non_negative_int(
            "SIMULA_GENERATION_MAX_TOKENS",
            os.environ["SIMULA_GENERATION_MAX_TOKENS"],
        )
        if os.environ.get("SIMULA_GENERATION_MAX_TOKENS")
        else _nvidia_max_tokens_from_env()
    )
    if resolved_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    return {
        "base_url": resolved_base,
        "timeout_s": resolved_timeout,
        "max_retries": resolved_retries,
        "backoff_base_s": resolved_backoff,
        "max_tokens": resolved_tokens,
        "min_interval_s": resolved_interval,
        "reasoning_effort": resolved_reasoning,
        "model": resolved_model,
    }


def nvidia_json_completion(
    *,
    system_prompt: str,
    user_content: str,
    operation: str,
    model: str | None = None,
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
) -> Any:
    """Request one strict JSON response from an OpenAI-compatible NVIDIA NIM endpoint."""
    settings = _text_completion_settings(
        base_url=base_url,
        timeout_s=timeout_s,
        max_retries=max_retries,
        backoff_base_s=backoff_base_s,
        max_tokens=max_tokens,
        min_interval_s=min_interval_s,
        reasoning_effort=reasoning_effort,
        model=model,
    )
    api_key = _nvidia_api_key_from_env()
    last_request_at: float | None = None
    payload = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        "max_tokens": settings["max_tokens"],
        "reasoning_effort": settings["reasoning_effort"],
    }
    headers = {
        "Authorization": "******",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if http_post_json is _http_post_json:
        headers["Authorization"] = "Bearer " + api_key

    def _op() -> Any:
        nonlocal last_request_at
        if last_request_at is not None and settings["min_interval_s"] > 0:
            wait_s = settings["min_interval_s"] - (time.monotonic() - last_request_at)
            if wait_s > 0:
                sleep_fn(wait_s)
        last_request_at = time.monotonic()
        try:
            response = http_post_json(
                url=settings["base_url"],
                headers=headers,
                payload=payload,
                timeout_s=settings["timeout_s"],
            )
            return _parse_json_content(_json_content(response, operation=operation), operation=operation)
        except _NvidiaRateLimitError:
            raise
        except Exception as error:
            raise RuntimeError(f"{operation}_request_failed:{type(error).__name__}") from error

    try:
        return retry_with_backoff(
            _op,
            max_retries=settings["max_retries"],
            backoff_base_s=settings["backoff_base_s"],
            sleep_fn=sleep_fn,
        )
    except Exception as error:
        if event_log is not None:
            event_log.append(
                {
                    "backend": "nim",
                    "operation": operation,
                    "model": settings["model"],
                    "base_url": settings["base_url"],
                    "timeout_s": settings["timeout_s"],
                    "max_retries": settings["max_retries"],
                    "error_type": type(error).__name__,
                    "error_code": str(error).split(":", 1)[0],
                    "http_status": getattr(error, "status_code", None),
                    "retry_after_s": getattr(error, "retry_after_s", None),
                }
            )
        raise


def _labels_from_response(response: Any, *, branching_factor: int) -> list[str]:
    if not isinstance(response, dict) or set(response) != {"labels"}:
        raise ValueError("nvidia_taxonomy_invalid_response")
    labels = response["labels"]
    if not isinstance(labels, list) or not labels or len(labels) > branching_factor:
        raise ValueError("nvidia_taxonomy_invalid_response")
    normalized: list[str] = []
    for label in labels:
        if not isinstance(label, str) or not label.strip():
            raise ValueError("nvidia_taxonomy_invalid_response")
        value = _normalize_label(label)
        if value and value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("nvidia_taxonomy_invalid_response")
    return normalized


def nvidia_taxonomy_provider(
    *,
    event_log: list[dict[str, Any]] | None = None,
    **completion_options: Any,
) -> TaxonomyProviderFn:
    """Generate taxonomy children with one strict NIM JSON request per expandable node."""

    def _generate(domain_objective: str, config: TaxonomyConfig | None = None) -> dict[str, Any]:
        resolved_config = config or TaxonomyConfig()
        namespace = _normalize_label(domain_objective) or "domain"
        root_label = f"{namespace} root"
        root_id = _taxonomy_node_id(namespace, None, root_label)
        nodes: list[dict[str, Any]] = [
            {
                "taxonomy_node_id": root_id,
                "parent_taxonomy_node_id": None,
                "label": root_label,
                "depth": 0,
                "branch_source": "nvidia_nim",
                "confidence": 0.8,
                "notes": "root taxonomy node",
            }
        ]
        edges: list[dict[str, str]] = []
        queue = [nodes[0]]
        while queue:
            parent = queue.pop(0)
            depth = int(parent["depth"])
            if depth >= resolved_config.max_depth:
                continue
            response = nvidia_json_completion(
                system_prompt=(
                    "Expand a domain taxonomy. Return only a JSON object with a labels array. "
                    "Each label must be a distinct actionable factor of variation; do not include "
                    "the parent label or explanations."
                ),
                user_content=json.dumps(
                    {
                        "domain": domain_objective,
                        "parent_label": parent["label"],
                        "parent_depth": depth,
                        "requested_children": resolved_config.branching_factor,
                    },
                    sort_keys=True,
                ),
                operation="nvidia_taxonomy",
                event_log=event_log,
                **completion_options,
            )
            for label in _labels_from_response(response, branching_factor=resolved_config.branching_factor):
                child_id = _taxonomy_node_id(namespace, str(parent["taxonomy_node_id"]), label)
                child = {
                    "taxonomy_node_id": child_id,
                    "parent_taxonomy_node_id": parent["taxonomy_node_id"],
                    "label": label,
                    "depth": depth + 1,
                    "branch_source": "nvidia_nim",
                    "confidence": 0.8,
                    "notes": f"generated from parent {parent['taxonomy_node_id']}",
                }
                nodes.append(child)
                edges.append(
                    {
                        "parent_taxonomy_node_id": str(parent["taxonomy_node_id"]),
                        "taxonomy_node_id": child_id,
                    }
                )
                queue.append(child)
        return {
            "domain_namespace": namespace,
            "root_taxonomy_node_id": root_id,
            "nodes": nodes,
            "edges": edges,
            "generation_policy": {
                "max_depth": resolved_config.max_depth,
                "branching_factor": resolved_config.branching_factor,
                "merge_filter_strategy": "provider-label-normalize+deduplicate",
                "provider": "nvidia_nim",
            },
        }

    return _generate


def _local_rows_from_response(response: Any, *, expected_count: int) -> list[dict[str, Any]]:
    if not isinstance(response, list) or len(response) != expected_count:
        raise ValueError("nvidia_local_diversification_invalid_response")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(response):
        if (
            not isinstance(row, dict)
            or set(row) != {"index", "text"}
            or row.get("index") != index
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
        ):
            raise ValueError("nvidia_local_diversification_invalid_response")
        rows.append({"index": index, "text": row["text"].strip()})
    return rows


def nvidia_local_diversification_provider(
    *,
    event_log: list[dict[str, Any]] | None = None,
    **completion_options: Any,
) -> LocalDiversificationProviderFn:
    """Generate local instantiations in ordered per-node NIM batches."""

    def _generate(
        taxonomy: dict[str, Any],
        *,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = options or {}
        count = int(values.get("per_node_instantiation_count", 3))
        threshold = float(values.get("overlap_rejection_threshold", 0.8))
        if count <= 0 or not 0 <= threshold <= 1:
            raise ValueError("invalid local diversification options")
        accepted: list[dict[str, Any]] = []
        rejections: list[dict[str, Any]] = []
        for node in taxonomy["nodes"]:
            node_id = str(node["taxonomy_node_id"])
            label = str(node["label"])
            meta_prompt_id = f"mp-{_stable_id(node_id, label)}"
            response = nvidia_json_completion(
                system_prompt=(
                    "Generate diverse assessment scenarios for one taxonomy node. Return only a "
                    "JSON array in index order; each object must contain only index and text."
                ),
                user_content=json.dumps(
                    {
                        "domain": taxonomy["domain_namespace"],
                        "taxonomy_node_id": node_id,
                        "taxonomy_label": label,
                        "requested_count": count,
                    },
                    sort_keys=True,
                ),
                operation="nvidia_local_diversification",
                event_log=event_log,
                **completion_options,
            )
            rows = _local_rows_from_response(response, expected_count=count)
            kept_for_node: list[dict[str, Any]] = []
            for row in rows:
                instantiation_id = f"inst-{_stable_id(node_id, str(row['index']))}"
                candidate = {
                    "instantiation_id": instantiation_id,
                    "taxonomy_node_id": node_id,
                    "meta_prompt_id": meta_prompt_id,
                    "lineage": {
                        "taxonomy_node_id": node_id,
                        "meta_prompt_id": meta_prompt_id,
                        "instantiation_id": instantiation_id,
                    },
                    "text": row["text"],
                }
                if any(
                    _token_overlap_ratio(candidate["text"], prior["text"]) >= threshold
                    for prior in kept_for_node
                ):
                    rejections.append(
                        {
                            "reason": "low_diversity",
                            "taxonomy_node_id": node_id,
                            "meta_prompt_id": meta_prompt_id,
                            "candidate_instantiation_id": instantiation_id,
                        }
                    )
                    continue
                accepted.append(candidate)
                kept_for_node.append(candidate)
        return {
            "instantiations": accepted,
            "rejections": rejections,
            "anti_collapse_checks": {
                "executed": True,
                "check_name": "token_overlap_rejection",
                "threshold": threshold,
                "provider": "nvidia_nim",
            },
        }

    return _generate


def _complexification_rows_from_response(
    response: Any,
    *,
    expected_ids: list[str],
) -> dict[str, str]:
    if not isinstance(response, list) or len(response) != len(expected_ids):
        raise ValueError("nvidia_complexification_invalid_response")
    rows: dict[str, str] = {}
    for expected_id, row in zip(expected_ids, response):
        if (
            not isinstance(row, dict)
            or set(row) != {"instantiation_id", "text"}
            or row.get("instantiation_id") != expected_id
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
        ):
            raise ValueError("nvidia_complexification_invalid_response")
        rows[expected_id] = row["text"].strip()
    return rows


def nvidia_complexification_provider(
    *,
    event_log: list[dict[str, Any]] | None = None,
    **completion_options: Any,
) -> ComplexificationProviderFn:
    """Complexify selected samples in one ordered NIM batch while preserving lineage."""

    def _generate(
        samples: list[dict[str, Any]],
        *,
        complexify_fraction: float = 0.75,
        semantic_overlap_threshold: float = 0.55,
        strategy: str = "append_reasoning",
    ) -> dict[str, Any]:
        if not 0 <= complexify_fraction <= 1:
            raise ValueError("complexify_fraction must be between 0 and 1")
        target_count = int(round(len(samples) * complexify_fraction))
        selected = samples[:target_count]
        transformed_by_id: dict[str, str] = {}
        if selected:
            expected_ids = [str(sample["instantiation_id"]) for sample in selected]
            response = nvidia_json_completion(
                system_prompt=(
                    "Complexify each supplied assessment scenario without changing its intended "
                    "answer. Return only an ordered JSON array of objects with instantiation_id "
                    "and text; do not include explanations."
                ),
                user_content=json.dumps(
                    {
                        "strategy": strategy,
                        "items": [
                            {
                                "instantiation_id": str(sample["instantiation_id"]),
                                "text": str(sample["text"]),
                            }
                            for sample in selected
                        ],
                    },
                    sort_keys=True,
                ),
                operation="nvidia_complexification",
                event_log=event_log,
                **completion_options,
            )
            transformed_by_id = _complexification_rows_from_response(
                response,
                expected_ids=expected_ids,
            )

        transformed_samples: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for index, sample in enumerate(samples):
            source_text = str(sample["text"])
            should_complexify = index < target_count
            transformed_text = transformed_by_id.get(str(sample["instantiation_id"]))
            if not should_complexify or transformed_text is None:
                transformed_samples.append(
                    {
                        **sample,
                        "is_complexified": False,
                        "complexity_source": "original",
                        "source_intent": source_text,
                    }
                )
                continue
            overlap = _token_overlap_ratio(source_text, transformed_text)
            if not isfinite(overlap) or overlap < semantic_overlap_threshold:
                failures.append(
                    {
                        "instantiation_id": sample["instantiation_id"],
                        "taxonomy_node_id": sample["taxonomy_node_id"],
                        "meta_prompt_id": sample["meta_prompt_id"],
                        "reason": "semantic_preservation_failed",
                        "source_intent": source_text,
                        "candidate_text": transformed_text,
                        "semantic_overlap_ratio": overlap,
                    }
                )
                transformed_samples.append(
                    {
                        **sample,
                        "is_complexified": False,
                        "complexity_source": "fallback_original_due_to_semantic_failure",
                        "source_intent": source_text,
                    }
                )
                continue
            transformed_samples.append(
                {
                    **sample,
                    "text": transformed_text,
                    "is_complexified": True,
                    "complexity_source": "nvidia_nim",
                    "source_intent": source_text,
                }
            )
        return {
            "samples": transformed_samples,
            "complexification_policy": {
                "complexify_fraction": complexify_fraction,
                "semantic_overlap_threshold": semantic_overlap_threshold,
                "strategy": strategy,
                "provider": "nvidia_nim",
            },
            "semantic_preservation_failures": failures,
        }

    return _generate


def generation_providers_from_env(
    *,
    event_log: list[dict[str, Any]] | None = None,
) -> dict[str, Callable[..., Any]] | None:
    """Select opt-in provider-backed Stages 1–3; deterministic defaults remain unchanged."""
    _load_dotenv()
    mode = (os.environ.get("SIMULA_GENERATION_BACKEND") or "").strip().lower()
    if mode in {"", "hash", "default", "hash_default", "stub"}:
        return None
    if mode not in {"nim", "nvidia"}:
        raise ValueError(f"Unsupported SIMULA_GENERATION_BACKEND={mode!r}")
    return {
        "taxonomy": nvidia_taxonomy_provider(event_log=event_log),
        "local_diversification": nvidia_local_diversification_provider(event_log=event_log),
        "complexification": nvidia_complexification_provider(event_log=event_log),
    }
