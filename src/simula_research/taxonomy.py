from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any


@dataclass(frozen=True)
class TaxonomyConfig:
    max_depth: int = 2
    branching_factor: int = 2


def _normalize_label(label: str) -> str:
    return " ".join(label.strip().lower().split())


def _taxonomy_node_id(namespace: str, parent_node_id: str | None, label: str) -> str:
    canonical_parent = parent_node_id or "root"
    canonical_label = _normalize_label(label)
    digest = sha1(f"{namespace}|{canonical_parent}|{canonical_label}".encode("utf-8")).hexdigest()[:12]
    return f"tax-{digest}"


def _seed_terms(domain_objective: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in domain_objective)
    tokens = [_normalize_label(token) for token in cleaned.split() if token.strip()]
    unique_tokens: list[str] = []
    for token in tokens:
        if token not in unique_tokens:
            unique_tokens.append(token)
    if not unique_tokens:
        return ["core"]
    return unique_tokens[:3]


def _candidate_labels(parent_label: str, depth: int, seed_terms: list[str]) -> list[str]:
    # Intentionally emits near-duplicates so merge/filter checks are exercised.
    term = seed_terms[depth % len(seed_terms)]
    return [
        f"{parent_label} {term} fundamentals",
        f"{parent_label} {term} advanced",
        f"  {parent_label} {term} fundamentals  ",
    ]


def _merge_and_filter(parent_label: str, candidate_labels: list[str], branching_factor: int) -> list[str]:
    merged: list[str] = []
    parent_norm = _normalize_label(parent_label)
    for label in candidate_labels:
        normalized = _normalize_label(label)
        if not normalized or normalized == parent_norm:
            continue
        if normalized not in merged:
            merged.append(normalized)
        if len(merged) >= branching_factor:
            break
    return merged


def build_taxonomy(domain_objective: str, config: TaxonomyConfig | None = None) -> dict[str, Any]:
    config = config or TaxonomyConfig()
    namespace = _normalize_label(domain_objective) or "domain"
    root_label = f"{namespace} root"
    root_id = _taxonomy_node_id(namespace, parent_node_id=None, label=root_label)

    nodes: list[dict[str, Any]] = [
        {
            "taxonomy_node_id": root_id,
            "parent_taxonomy_node_id": None,
            "label": root_label,
            "depth": 0,
            "branch_source": "seed",
            "confidence": 1.0,
            "notes": "root taxonomy node",
        }
    ]
    edges: list[dict[str, str]] = []

    seed_terms = _seed_terms(domain_objective)
    queue: list[dict[str, Any]] = [nodes[0]]

    while queue:
        parent = queue.pop(0)
        parent_depth = int(parent["depth"])
        if parent_depth >= config.max_depth:
            continue

        raw_candidates = _candidate_labels(str(parent["label"]), parent_depth, seed_terms)
        candidate_labels = _merge_and_filter(
            parent_label=str(parent["label"]),
            candidate_labels=raw_candidates,
            branching_factor=config.branching_factor,
        )

        for label in candidate_labels:
            child_id = _taxonomy_node_id(namespace, str(parent["taxonomy_node_id"]), label)
            child = {
                "taxonomy_node_id": child_id,
                "parent_taxonomy_node_id": parent["taxonomy_node_id"],
                "label": label,
                "depth": parent_depth + 1,
                "branch_source": "recursive-expansion",
                "confidence": 0.8,
                "notes": f"generated from parent {parent['taxonomy_node_id']}",
            }
            nodes.append(child)
            edges.append(
                {"parent_taxonomy_node_id": str(parent["taxonomy_node_id"]), "taxonomy_node_id": child_id}
            )
            queue.append(child)

    return {
        "domain_namespace": namespace,
        "root_taxonomy_node_id": root_id,
        "nodes": nodes,
        "edges": edges,
        "generation_policy": {
            "max_depth": config.max_depth,
            "branching_factor": config.branching_factor,
            "merge_filter_strategy": "normalize+deduplicate+parent-filter",
        },
    }
