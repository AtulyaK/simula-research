from __future__ import annotations

from math import pow
from typing import Any

from simula_research.provider_protocols import ComplexityJudgmentProviderFn

COMPLEXITY_JUDGMENT_DEFAULTS: dict[str, int] = {
    "initial_rating": 1000,
    "k_factor": 32,
    "minimum_comparisons_per_sample": 5,
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
