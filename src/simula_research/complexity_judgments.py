from __future__ import annotations

from typing import Any

from simula_research.provider_protocols import ComplexityJudgmentProviderFn

COMPLEXITY_JUDGMENT_DEFAULTS: dict[str, int] = {
    "initial_rating": 1000,
    "k_factor": 32,
    "minimum_comparisons_per_sample": 5,
}
VALID_WINNERS = {"complexified", "baseline", "tie"}


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
                    "is_successful": winner == "complexified",
                }
            )
    return judgments


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
