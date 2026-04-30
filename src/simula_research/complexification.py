from __future__ import annotations

import re
from typing import Any


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    denominator = min(len(left_tokens), len(right_tokens))
    if denominator == 0:
        return 0.0
    return len(left_tokens.intersection(right_tokens)) / denominator


def _complexify_text(source_text: str, strategy: str) -> str:
    if strategy == "append_reasoning":
        return (
            f"{source_text} Include a multi-step justification, evaluate one plausible distractor, "
            "and articulate why the final decision resolves ambiguity."
        )
    if strategy == "semantic_drift_probe":
        return "Compute prime factorization of 163 and explain each arithmetic step."
    raise ValueError(f"Unsupported complexification strategy: {strategy}")


def apply_complexification(
    samples: list[dict[str, Any]],
    complexify_fraction: float = 0.5,
    semantic_overlap_threshold: float = 0.55,
    strategy: str = "append_reasoning",
) -> dict[str, Any]:
    if complexify_fraction < 0 or complexify_fraction > 1:
        raise ValueError("complexify_fraction must be between 0 and 1")

    target_count = int(round(len(samples) * complexify_fraction))
    complexified: list[dict[str, Any]] = []
    semantic_failures: list[dict[str, Any]] = []

    for idx, sample in enumerate(samples):
        source_text = sample["text"]
        should_complexify = idx < target_count
        if not should_complexify:
            untouched = {
                **sample,
                "is_complexified": False,
                "complexity_source": "original",
                "source_intent": source_text,
            }
            complexified.append(untouched)
            continue

        transformed_text = _complexify_text(source_text, strategy=strategy)
        overlap = _token_overlap_ratio(source_text, transformed_text)
        if overlap < semantic_overlap_threshold:
            semantic_failures.append(
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
            fallback = {
                **sample,
                "is_complexified": False,
                "complexity_source": "fallback_original_due_to_semantic_failure",
                "source_intent": source_text,
            }
            complexified.append(fallback)
            continue

        transformed = {
            **sample,
            "text": transformed_text,
            "is_complexified": True,
            "complexity_source": "complexification_transform_v1",
            "source_intent": source_text,
        }
        complexified.append(transformed)

    return {
        "samples": complexified,
        "complexification_policy": {
            "complexify_fraction": complexify_fraction,
            "semantic_overlap_threshold": semantic_overlap_threshold,
            "strategy": strategy,
        },
        "semantic_preservation_failures": semantic_failures,
    }
