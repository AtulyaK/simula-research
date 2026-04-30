from __future__ import annotations

import hashlib
import re
from typing import Any


def _stable_id(*parts: str) -> str:
    joined = "::".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens.intersection(right_tokens)
    denominator = min(len(left_tokens), len(right_tokens))
    if denominator == 0:
        return 0.0
    return len(intersection) / denominator


def build_local_diversification(
    taxonomy: dict[str, Any],
    per_node_instantiation_count: int = 3,
    overlap_rejection_threshold: float = 0.8,
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []

    for node in taxonomy["nodes"]:
        taxonomy_node_id = node["taxonomy_node_id"]
        label = node["label"]
        domain = taxonomy["domain_namespace"]
        meta_prompt_id = f"mp-{_stable_id(taxonomy_node_id, label)}"
        meta_prompt_text = f"Generate samples for {domain} with focus on {label}"

        kept_for_node: list[dict[str, Any]] = []
        for idx in range(per_node_instantiation_count):
            instantiation_id = f"inst-{_stable_id(taxonomy_node_id, str(idx))}"
            candidate_text = (
                f"{domain}::{label} example {idx}. "
                f"Reasoning path for {label} under {taxonomy_node_id}."
            )

            is_duplicate = any(
                _token_overlap_ratio(candidate_text, prior["text"]) >= overlap_rejection_threshold
                for prior in kept_for_node
            )
            candidate = {
                "instantiation_id": instantiation_id,
                "taxonomy_node_id": taxonomy_node_id,
                "meta_prompt_id": meta_prompt_id,
                "lineage": {
                    "taxonomy_node_id": taxonomy_node_id,
                    "meta_prompt_id": meta_prompt_id,
                    "instantiation_id": instantiation_id,
                },
                "text": candidate_text,
            }

            if is_duplicate:
                rejections.append(
                    {
                        "reason": "low_diversity",
                        "taxonomy_node_id": taxonomy_node_id,
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
            "threshold": overlap_rejection_threshold,
        },
    }
