from __future__ import annotations

from statistics import median
from typing import Any

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
    run_scores = sorted(float(score) for score in run_complexity_scores)
    baseline_scores = [float(score) for score in baseline_complexity_scores]
    pair_results = complexification_pairs or []
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
    regenerated_samples = int(issue5_outputs.get("regenerated_samples", 0))

    return {
        "acceptance_rate": _safe_ratio(accepted_samples, reviewed_samples),
        "critic_agreement": _safe_ratio(agreements, reviewed_samples),
        "disagreement_rate": _safe_ratio(disagreements, reviewed_samples),
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
            float(complexity_metrics.get("complexification_precision", 0.0)),
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
