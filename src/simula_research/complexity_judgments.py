from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from math import isfinite, pow
from typing import Any

from simula_research.provider_protocols import ComplexityJudgmentProviderFn

COMPLEXITY_JUDGMENT_DEFAULTS: dict[str, int] = {
    "initial_rating": 1000,
    "k_factor": 32,
    "minimum_comparisons_per_sample": 5,
    "batch_size": 5,
    "samples_per_item": 5,
}
VALID_WINNERS = {"complexified", "baseline", "tie"}
VALID_ELO_WINNERS = {"left", "right", "tie"}


def calibrate_elo_ratings(
    comparisons: list[dict[str, Any]],
    *,
    initial_rating: int = COMPLEXITY_JUDGMENT_DEFAULTS["initial_rating"],
    k_factor: int = COMPLEXITY_JUDGMENT_DEFAULTS["k_factor"],
) -> dict[str, float]:
    """Compute deterministic Elo ratings from ordered pairwise comparisons."""
    if isinstance(initial_rating, bool) or not isinstance(initial_rating, (int, float)):
        raise ValueError("initial_rating must be numeric")
    if isinstance(k_factor, bool) or not isinstance(k_factor, (int, float)) or k_factor <= 0:
        raise ValueError("k_factor must be a positive number")

    ratings: dict[str, float] = {}
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            raise ValueError("Elo comparisons must contain objects")
        left_id = comparison.get("left_item_id")
        right_id = comparison.get("right_item_id")
        winner = comparison.get("winner")
        if not isinstance(left_id, str) or not left_id.strip():
            raise ValueError("Elo comparisons require a non-empty left_item_id")
        if not isinstance(right_id, str) or not right_id.strip():
            raise ValueError("Elo comparisons require a non-empty right_item_id")
        if winner not in VALID_ELO_WINNERS:
            raise ValueError("Elo comparison winner must be left, right, or tie")

        left_id = left_id.strip()
        right_id = right_id.strip()
        ratings.setdefault(left_id, float(initial_rating))
        ratings.setdefault(right_id, float(initial_rating))

        left_rating = ratings[left_id]
        right_rating = ratings[right_id]
        expected_left = 1.0 / (1.0 + pow(10.0, (right_rating - left_rating) / 400.0))
        if winner == "left":
            actual_left = 1.0
        elif winner == "right":
            actual_left = 0.0
        else:
            actual_left = 0.5
        actual_right = 1.0 - actual_left
        ratings[left_id] = left_rating + float(k_factor) * (actual_left - expected_left)
        ratings[right_id] = right_rating + float(k_factor) * (
            actual_right - (1.0 - expected_left)
        )

    return ratings


def build_elo_comparisons(
    judgments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Translate persisted complexified-vs-source judgments into Elo pairs."""
    comparisons: list[dict[str, Any]] = []
    for judgment in judgments:
        if not isinstance(judgment, dict):
            raise ValueError("complexity judgments must contain objects")
        sample_id = str(judgment.get("instantiation_id", "")).strip()
        if not sample_id:
            raise ValueError("complexity judgments require instantiation_id")
        winner = judgment.get("winner")
        winner_map = {"complexified": "left", "baseline": "right", "tie": "tie"}
        if winner not in winner_map:
            raise ValueError("complexity judgment winner must be complexified, baseline, or tie")
        comparisons.append(
            {
                "left_item_id": str(
                    judgment.get("complexified_item_id", f"{sample_id}:complexified")
                ),
                "right_item_id": str(
                    judgment.get("baseline_item_id", f"{sample_id}:baseline")
                ),
                "winner": winner_map[winner],
            }
        )
    return comparisons


def prepare_complexity_batch_schedule(
    item_ids: list[str],
    *,
    batch_size: int = COMPLEXITY_JUDGMENT_DEFAULTS["batch_size"],
    samples_per_item: int = COMPLEXITY_JUDGMENT_DEFAULTS["samples_per_item"],
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Schedule each item in N deterministic, varied scoring batches."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if (
        isinstance(samples_per_item, bool)
        or not isinstance(samples_per_item, int)
        or samples_per_item <= 0
    ):
        raise ValueError("samples_per_item must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    normalized_ids = [str(item_id).strip() for item_id in item_ids]
    if any(not item_id for item_id in normalized_ids):
        raise ValueError("item_ids must contain non-empty strings")
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("item_ids must be unique")

    schedule: list[dict[str, Any]] = []
    if not normalized_ids:
        return schedule
    for repetition in range(samples_per_item):
        rotation = (seed + repetition) % len(normalized_ids)
        ordered_ids = normalized_ids[rotation:] + normalized_ids[:rotation]
        if repetition % 2:
            ordered_ids.reverse()
        repetition_batches: list[list[str]] = []
        for start in range(0, len(ordered_ids), batch_size):
            batch = ordered_ids[start : start + batch_size]
            if len(batch) == 1 and repetition_batches:
                repetition_batches[-1].extend(batch)
            else:
                repetition_batches.append(batch)
        for batch_index, batch in enumerate(repetition_batches):
            schedule.append(
                {
                    "batch_id": f"batch-{repetition:03d}-{batch_index:03d}",
                    "repetition": repetition,
                    "item_ids": batch,
                }
            )
    return schedule


def collect_batchwise_complexity_judgments(
    samples: list[dict[str, Any]],
    provider: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    *,
    batch_size: int = COMPLEXITY_JUDGMENT_DEFAULTS["batch_size"],
    samples_per_item: int = COMPLEXITY_JUDGMENT_DEFAULTS["samples_per_item"],
    seed: int = 0,
    initial_rating: int = COMPLEXITY_JUDGMENT_DEFAULTS["initial_rating"],
    k_factor: int = COMPLEXITY_JUDGMENT_DEFAULTS["k_factor"],
) -> dict[str, Any]:
    """Run the paper-style batch scoring loop and derive Elo comparisons."""
    sample_by_id: dict[str, dict[str, Any]] = {}
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("complexity samples must contain objects")
        item_id = str(sample.get("instantiation_id", sample.get("task_id", ""))).strip()
        if not item_id:
            raise ValueError("complexity samples require instantiation_id or task_id")
        if item_id in sample_by_id:
            raise ValueError(f"complexity samples contain duplicate item id {item_id!r}")
        sample_by_id[item_id] = sample

    schedule = prepare_complexity_batch_schedule(
        list(sample_by_id),
        batch_size=batch_size,
        samples_per_item=samples_per_item,
        seed=seed,
    )
    raw_scores: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for batch in schedule:
        batch_samples = [sample_by_id[item_id] for item_id in batch["item_ids"]]
        scored_items = provider(batch_samples)
        if not isinstance(scored_items, list):
            raise ValueError("batch complexity provider must return a list")
        if any(not isinstance(item, dict) for item in scored_items):
            raise ValueError("batch complexity provider entries must be objects")
        expected_ids = batch["item_ids"]
        actual_ids = [
            str(item.get("item_id", "")).strip()
            for item in scored_items
        ]
        if actual_ids != expected_ids:
            raise ValueError(
                f"batch complexity provider must return scores in batch order: {expected_ids!r}"
            )
        scores: dict[str, float] = {}
        for item in scored_items:
            score = item.get("score")
            if not _is_number(score) or not isfinite(float(score)):
                raise ValueError("batch complexity scores must be finite numbers")
            item_id = str(item["item_id"]).strip()
            scores[item_id] = float(score)
            raw_scores.append(
                {
                    "batch_id": batch["batch_id"],
                    "repetition": batch["repetition"],
                    "item_id": item_id,
                    "score": float(score),
                }
            )
        for left_id, right_id in combinations(expected_ids, 2):
            left_score = scores[left_id]
            right_score = scores[right_id]
            winner = (
                "left"
                if left_score > right_score
                else "right"
                if right_score > left_score
                else "tie"
            )
            comparisons.append(
                {
                    "judgment_id": f"{batch['batch_id']}:{left_id}:{right_id}",
                    "batch_id": batch["batch_id"],
                    "repetition": batch["repetition"],
                    "left_item_id": left_id,
                    "right_item_id": right_id,
                    "left_score": left_score,
                    "right_score": right_score,
                    "winner": winner,
                }
            )

    ratings = calibrate_elo_ratings(
        comparisons,
        initial_rating=initial_rating,
        k_factor=k_factor,
    )
    rating_values = list(ratings.values())
    rating_min = min(rating_values, default=0.0)
    rating_span = max(rating_values, default=0.0) - rating_min
    normalized_ratings = {
        item_id: (
            50.0
            if rating_span == 0.0
            else (rating - rating_min) / rating_span * 100.0
        )
        for item_id, rating in ratings.items()
    }
    raw_score_values: dict[str, list[float]] = {}
    for row in raw_scores:
        raw_score_values.setdefault(row["item_id"], []).append(row["score"])
    raw_score_averages = {
        item_id: sum(scores) / len(scores)
        for item_id, scores in raw_score_values.items()
    }
    appearance_counts = {item_id: 0 for item_id in sample_by_id}
    for batch in schedule:
        for item_id in batch["item_ids"]:
            appearance_counts[item_id] += 1
    return {
        "protocol": {
            "version": "batchwise-elo-v1",
            "batch_size": batch_size,
            "samples_per_item": samples_per_item,
            "seed": seed,
            "item_count": len(sample_by_id),
            "batch_count": len(schedule),
            "comparison_count": len(comparisons),
            "appearance_counts": appearance_counts,
        },
        "batches": schedule,
        "raw_scores": raw_scores,
        "raw_score_averages": raw_score_averages,
        "comparisons": comparisons,
        "elo_calibration": {
            "method": "elo_v1",
            "initial_rating": initial_rating,
            "k_factor": k_factor,
            "comparison_count": len(comparisons),
            "ratings": ratings,
            "normalized_ratings": normalized_ratings,
        },
    }


def collect_pairwise_complexity_judgments(
    samples: list[dict[str, Any]],
    provider: ComplexityJudgmentProviderFn,
) -> list[dict[str, Any]]:
    judgments: list[dict[str, Any]] = []
    for sample in samples:
        if not bool(sample.get("is_complexified")):
            continue
        source_text = str(sample.get("source_intent", sample.get("text", "")))
        baseline_sample = {
            **sample,
            "text": source_text,
            "is_complexified": False,
            "complexity_source": "original",
        }
        raw_judgments = provider(sample, baseline_sample)
        if not isinstance(raw_judgments, list):
            raise ValueError("complexity judgment provider must return a list")
        sample_id = str(sample.get("instantiation_id", "unknown-sample"))
        for index, raw_judgment in enumerate(raw_judgments, start=1):
            if not isinstance(raw_judgment, dict):
                raise ValueError("complexity judgment provider entries must be objects")
            winner = raw_judgment.get("winner")
            if winner not in VALID_WINNERS:
                raise ValueError("complexity judgment winner must be complexified, baseline, or tie")
            complexified_score = raw_judgment.get("complexified_score")
            baseline_score = raw_judgment.get("baseline_score")
            if not _is_number(complexified_score) or not _is_number(baseline_score):
                raise ValueError("complexity judgments require numeric complexified_score and baseline_score")
            judgment_id = raw_judgment.get("judgment_id", f"{sample_id}-comparison-{index}")
            if not isinstance(judgment_id, str) or not judgment_id.strip():
                raise ValueError("complexity judgment judgment_id must be a non-empty string")
            judgments.append(
                {
                    **raw_judgment,
                    "judgment_id": judgment_id,
                    "instantiation_id": sample_id,
                    "taxonomy_node_id": str(sample.get("taxonomy_node_id", "")),
                    "meta_prompt_id": str(sample.get("meta_prompt_id", "")),
                    "winner": winner,
                    "complexified_score": float(complexified_score),
                    "baseline_score": float(baseline_score),
                    "complexified_item_id": str(
                        raw_judgment.get(
                            "complexified_item_id",
                            f"{sample_id}:complexified",
                        )
                    ),
                    "baseline_item_id": str(
                        raw_judgment.get(
                            "baseline_item_id",
                            f"{sample_id}:baseline",
                        )
                    ),
                    "is_successful": winner == "complexified",
                }
            )
    return judgments


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
