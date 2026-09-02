from __future__ import annotations

from collections.abc import Callable, Sequence
from hashlib import sha256
from math import isfinite, sqrt
from statistics import median
from typing import Any

DEFAULT_DIVERSITY_LOCAL_K = 10
DEFAULT_EMBEDDING_DIMENSION = 128

EmbeddingProviderFn = Callable[[list[str]], Sequence[Sequence[float]]]

DEFAULT_THRESHOLDS = {
    "node_coverage_ratio": 0.80,
    "min_depth_coverage": 0.60,
    "complexification_precision": 0.70,
    "critic_agreement": 0.75,
    "acceptance_rate": 0.50,
    "regen_burden_max": 1.00,
}


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile
    low_index = int(position)
    high_index = min(low_index + 1, len(sorted_values) - 1)
    fraction = position - low_index
    return sorted_values[low_index] + (sorted_values[high_index] - sorted_values[low_index]) * fraction


def _gini(values: list[int]) -> float:
    if not values:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    sorted_values = sorted(values)
    weighted_sum = 0.0
    length = len(sorted_values)
    for index, value in enumerate(sorted_values, start=1):
        weighted_sum += index * value
    return (2 * weighted_sum) / (length * total) - (length + 1) / length


def deterministic_hash_embedding_provider(
    texts: list[str],
    *,
    dimension: int = DEFAULT_EMBEDDING_DIMENSION,
) -> list[list[float]]:
    """Create stable, dependency-free embeddings for offline metric replay."""
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 0:
        raise ValueError("embedding dimension must be a positive integer")

    embeddings: list[list[float]] = []
    for text in texts:
        vector = [0.0] * dimension
        tokens = str(text).lower().split()
        for token_index, token in enumerate(tokens):
            digest = sha256(f"{token_index}:{token}".encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        embeddings.append(vector)
    return embeddings


def _cosine_distance(left: Sequence[float], right: Sequence[float]) -> float:
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0 if left_norm == right_norm else 1.0
    return max(0.0, min(2.0, 1.0 - dot_product / (left_norm * right_norm)))


def compute_intrinsic_diversity_metrics(
    samples: list[dict[str, Any]],
    *,
    embedding_provider: EmbeddingProviderFn | None = None,
    local_k: int = DEFAULT_DIVERSITY_LOCAL_K,
) -> dict[str, Any]:
    """Compute paper-style global and local embedding diversity distances."""
    if isinstance(local_k, bool) or not isinstance(local_k, int) or local_k <= 0:
        raise ValueError("local_k must be a positive integer")
    embedding_provider_name = (
        "hash_sha256_v1"
        if embedding_provider is None
        else str(getattr(embedding_provider, "__simula_embedding_provider_name__", "custom"))
    )
    if not samples:
        return {
            "sample_count": 0,
            "embedding_provider": embedding_provider_name,
            "embedding_dimension": None,
            "global_pairwise_cosine_distance": None,
            "local_knn_cosine_distance": None,
            "local_k": local_k,
            "effective_local_neighbor_count": 0,
            "evaluation_status": "not_evaluable",
            "not_evaluable_reason": "missing_samples",
        }

    texts = [str(sample.get("text", "")) for sample in samples]
    provider = embedding_provider or deterministic_hash_embedding_provider
    raw_embeddings = provider(texts)
    if not isinstance(raw_embeddings, Sequence) or isinstance(raw_embeddings, (str, bytes)):
        raise ValueError("embedding provider must return a sequence of vectors")
    if len(raw_embeddings) != len(texts):
        raise ValueError("embedding provider must return one vector per sample")

    embeddings: list[list[float]] = []
    dimension: int | None = None
    for embedding in raw_embeddings:
        if not isinstance(embedding, Sequence) or isinstance(embedding, (str, bytes)):
            raise ValueError("embedding provider vectors must be sequences")
        vector = [float(value) for value in embedding]
        if not vector:
            raise ValueError("embedding provider vectors must not be empty")
        if dimension is None:
            dimension = len(vector)
        elif len(vector) != dimension:
            raise ValueError("embedding provider vectors must have equal dimensions")
        if not all(isfinite(value) for value in vector):
            raise ValueError("embedding provider vectors must contain finite numbers")
        embeddings.append(vector)

    pairwise_distances = [
        _cosine_distance(embeddings[left_index], embeddings[right_index])
        for left_index in range(len(embeddings))
        for right_index in range(left_index + 1, len(embeddings))
    ]
    local_distances: list[float] = []
    effective_neighbor_counts: list[int] = []
    for index, embedding in enumerate(embeddings):
        neighbor_distances = sorted(
            _cosine_distance(embedding, other)
            for neighbor_index, other in enumerate(embeddings)
            if neighbor_index != index
        )
        neighbor_count = min(local_k, len(neighbor_distances))
        if neighbor_count:
            local_distances.append(sum(neighbor_distances[:neighbor_count]) / neighbor_count)
            effective_neighbor_counts.append(neighbor_count)

    return {
        "sample_count": len(samples),
        "embedding_provider": embedding_provider_name,
        "embedding_dimension": dimension,
        "global_pairwise_cosine_distance": (
            sum(pairwise_distances) / len(pairwise_distances)
            if pairwise_distances
            else 0.0
        ),
        "global_pairwise_comparison_count": len(pairwise_distances),
        "local_knn_cosine_distance": (
            sum(local_distances) / len(local_distances)
            if local_distances
            else None
        ),
        "local_k": local_k,
        "effective_local_neighbor_count": (
            sum(effective_neighbor_counts) / len(effective_neighbor_counts)
            if effective_neighbor_counts
            else 0
        ),
        "evaluation_status": "evaluated",
    }


def compute_coverage_metrics(
    eligible_nodes: list[dict[str, Any]], accepted_samples: list[dict[str, Any]]
) -> dict[str, Any]:
    eligible_ids = {str(node["taxonomy_node_id"]) for node in eligible_nodes}
    covered_ids = {
        str(sample["taxonomy_node_id"])
        for sample in accepted_samples
        if str(sample.get("taxonomy_node_id", "")) in eligible_ids
    }

    depth_totals: dict[int, int] = {}
    depth_covered: dict[int, int] = {}
    sample_counts_by_node: dict[str, int] = {node_id: 0 for node_id in eligible_ids}

    for node in eligible_nodes:
        depth = int(node["depth"])
        node_id = str(node["taxonomy_node_id"])
        depth_totals[depth] = depth_totals.get(depth, 0) + 1
        if node_id in covered_ids:
            depth_covered[depth] = depth_covered.get(depth, 0) + 1

    for sample in accepted_samples:
        node_id = str(sample.get("taxonomy_node_id", ""))
        if node_id in sample_counts_by_node:
            sample_counts_by_node[node_id] += 1

    depth_profile = {
        str(depth): _safe_ratio(depth_covered.get(depth, 0), total)
        for depth, total in sorted(depth_totals.items())
    }
    balance_score = 1.0 - _gini(list(sample_counts_by_node.values()))

    return {
        "eligible_nodes": len(eligible_ids),
        "covered_nodes": len(covered_ids),
        "node_coverage_ratio": _safe_ratio(len(covered_ids), len(eligible_ids)),
        "depth_coverage_profile": depth_profile,
        "coverage_balance": max(0.0, min(1.0, balance_score)),
    }


def compute_complexity_metrics(
    run_complexity_scores: list[float],
    baseline_complexity_scores: list[float],
    complexification_pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not complexification_pairs:
        return {
            "calibrated_score_distribution": {"p25": None, "p50": None, "p75": None},
            "complexity_shift": None,
            "complexification_precision": None,
            "complexification_pairs_evaluated": 0,
            "evaluation_status": "not_evaluable",
            "not_evaluable_reason": "missing_pairwise_complexity_judgments",
        }

    run_scores = sorted(float(score) for score in run_complexity_scores)
    baseline_scores = [float(score) for score in baseline_complexity_scores]
    pair_results = complexification_pairs
    successful_pairs = sum(1 for pair in pair_results if bool(pair.get("is_successful")))

    return {
        "calibrated_score_distribution": {
            "p25": _percentile(run_scores, 0.25),
            "p50": _percentile(run_scores, 0.50),
            "p75": _percentile(run_scores, 0.75),
        },
        "complexity_shift": median(run_scores) - median(baseline_scores)
        if run_scores and baseline_scores
        else 0.0,
        "complexification_precision": _safe_ratio(successful_pairs, len(pair_results)),
        "complexification_pairs_evaluated": len(pair_results),
        "evaluation_status": "evaluated",
    }


def compute_quality_metrics(issue5_outputs: dict[str, Any] | None) -> dict[str, Any]:
    if not issue5_outputs:
        return {
            "acceptance_rate": None,
            "critic_agreement": None,
            "disagreement_rate": None,
            "regen_burden": None,
            "requires_issue_5_outputs": True,
            "todo_after_issue_5": [
                "wire dual-critic per-sample decisions",
                "wire deterministic disagreement outcomes",
                "wire regeneration logs and accepted sample totals",
            ],
        }

    reviewed_samples = int(issue5_outputs.get("reviewed_samples", 0))
    accepted_samples = int(issue5_outputs.get("accepted_samples", 0))
    agreements = int(issue5_outputs.get("agreements", 0))
    disagreements = int(issue5_outputs.get("disagreements", 0))
    agreement_evaluable_samples = int(issue5_outputs.get("agreement_evaluable_samples", reviewed_samples))
    regenerated_samples = int(issue5_outputs.get("regenerated_samples", 0))
    critic_agreement = (
        None if agreement_evaluable_samples == 0 else _safe_ratio(agreements, agreement_evaluable_samples)
    )
    disagreement_rate = (
        None if agreement_evaluable_samples == 0 else _safe_ratio(disagreements, agreement_evaluable_samples)
    )

    return {
        "acceptance_rate": _safe_ratio(accepted_samples, reviewed_samples),
        "critic_agreement": critic_agreement,
        "disagreement_rate": disagreement_rate,
        "regen_burden": _safe_ratio(regenerated_samples, max(accepted_samples, 1)),
        "requires_issue_5_outputs": False,
        "todo_after_issue_5": [],
    }


def _threshold_status(actual: float | None, threshold: float, comparator: str) -> dict[str, Any]:
    if actual is None:
        return {"status": "todo", "actual": None, "threshold": threshold, "comparator": comparator}
    is_pass = actual >= threshold if comparator == ">=" else actual <= threshold
    return {
        "status": "pass" if is_pass else "fail",
        "actual": actual,
        "threshold": threshold,
        "comparator": comparator,
    }


def build_gate_report(
    run_identity: dict[str, Any],
    protocol: dict[str, Any],
    coverage_metrics: dict[str, Any],
    complexity_metrics: dict[str, Any],
    quality_metrics: dict[str, Any],
    notes: list[str] | None = None,
) -> dict[str, Any]:
    depth_profile = coverage_metrics.get("depth_coverage_profile", {})
    min_depth_coverage = min(depth_profile.values()) if depth_profile else 0.0

    complexity_precision = complexity_metrics.get("complexification_precision")
    if complexity_precision is not None:
        complexity_precision = float(complexity_precision)

    gates = {
        "coverage.node_coverage_ratio": _threshold_status(
            float(coverage_metrics.get("node_coverage_ratio", 0.0)),
            DEFAULT_THRESHOLDS["node_coverage_ratio"],
            ">=",
        ),
        "coverage.min_depth_coverage": _threshold_status(
            float(min_depth_coverage),
            DEFAULT_THRESHOLDS["min_depth_coverage"],
            ">=",
        ),
        "complexity.complexification_precision": _threshold_status(
            complexity_precision,
            DEFAULT_THRESHOLDS["complexification_precision"],
            ">=",
        ),
        "quality.critic_agreement": _threshold_status(
            quality_metrics.get("critic_agreement"),
            DEFAULT_THRESHOLDS["critic_agreement"],
            ">=",
        ),
        "quality.acceptance_rate": _threshold_status(
            quality_metrics.get("acceptance_rate"),
            DEFAULT_THRESHOLDS["acceptance_rate"],
            ">=",
        ),
        "quality.regen_burden": _threshold_status(
            quality_metrics.get("regen_burden"),
            DEFAULT_THRESHOLDS["regen_burden_max"],
            "<=",
        ),
    }

    gate_status_values = [entry["status"] for entry in gates.values()]
    if "fail" in gate_status_values:
        overall_status = "fail"
    elif "todo" in gate_status_values:
        overall_status = "todo"
    else:
        overall_status = "pass"

    gate_decision = {"overall_status": overall_status, **gates}

    return {
        "run_identity": run_identity,
        "protocol": protocol,
        "coverage": coverage_metrics,
        "complexity": complexity_metrics,
        "quality": quality_metrics,
        "gate_decision": gate_decision,
        "notes": notes or [],
    }
