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


def _compatible_node_groups(
    nodes: list[dict[str, Any]],
    node_mix_size: int,
) -> list[list[dict[str, Any]]]:
    if node_mix_size <= 0:
        raise ValueError("node_mix_size must be positive")

    by_depth: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_depth.setdefault(int(node.get("depth", 0)), []).append(node)

    groups: list[list[dict[str, Any]]] = []
    for depth in sorted(by_depth):
        level_nodes = by_depth[depth]
        groups.extend(
            level_nodes[start : start + node_mix_size]
            for start in range(0, len(level_nodes), node_mix_size)
        )
    return groups


_LANE_TEMPLATES = (
    "Define baseline competencies for {label} in {domain} (trace {inst}).",
    "Contrast edge cases for {label} within {node_id} namespace {domain} (trace {inst}).",
    "Synthesize assessment rubric for {label} progression {idx} in {domain} (trace {inst}).",
)


def build_local_diversification(
    taxonomy: dict[str, Any],
    per_node_instantiation_count: int = 3,
    overlap_rejection_threshold: float = 0.8,
    node_mix_size: int = 1,
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    option_values = options or {}
    per_node_instantiation_count = int(
        option_values.get("per_node_instantiation_count", per_node_instantiation_count)
    )
    overlap_rejection_threshold = float(
        option_values.get("overlap_rejection_threshold", overlap_rejection_threshold)
    )
    node_mix_size = int(option_values.get("node_mix_size", node_mix_size))
    if node_mix_size <= 0:
        raise ValueError("node_mix_size must be positive")

    accepted: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []

    for node_group in _compatible_node_groups(taxonomy["nodes"], node_mix_size):
        taxonomy_node_ids = [str(node["taxonomy_node_id"]) for node in node_group]
        labels = [str(node["label"]) for node in node_group]
        taxonomy_node_id = taxonomy_node_ids[0]
        label = " / ".join(labels)
        domain = taxonomy["domain_namespace"]
        group_key = "|".join(taxonomy_node_ids)
        meta_prompt_id = f"mp-{_stable_id(group_key, label)}"

        kept_for_node: list[dict[str, Any]] = []
        for idx in range(per_node_instantiation_count):
            instantiation_id = f"inst-{_stable_id(group_key, str(idx))}"
            template = _LANE_TEMPLATES[idx % len(_LANE_TEMPLATES)]
            candidate_text = template.format(
                label=label,
                domain=domain,
                node_id=group_key,
                inst=instantiation_id,
                idx=idx,
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
            if len(taxonomy_node_ids) > 1:
                candidate["compatible_taxonomy_node_ids"] = taxonomy_node_ids
                candidate["lineage"]["compatible_taxonomy_node_ids"] = taxonomy_node_ids

            if is_duplicate:
                rejections.append(
                    {
                        "reason": "low_diversity",
                        "taxonomy_node_id": taxonomy_node_id,
                        "meta_prompt_id": meta_prompt_id,
                        "candidate_instantiation_id": instantiation_id,
                    }
                )
                if len(taxonomy_node_ids) > 1:
                    rejections[-1]["compatible_taxonomy_node_ids"] = taxonomy_node_ids
                continue

            accepted.append(candidate)
            kept_for_node.append(candidate)

    output = {
        "instantiations": accepted,
        "rejections": rejections,
        "anti_collapse_checks": {
            "executed": True,
            "check_name": "token_overlap_rejection",
            "threshold": overlap_rejection_threshold,
        },
    }
    if node_mix_size > 1:
        output["diversification_policy"] = {
            "node_mix_size": node_mix_size,
            "mixing_strategy": "same_depth_sequential_groups",
        }
    return output
