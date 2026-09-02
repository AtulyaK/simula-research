from __future__ import annotations

import re
from typing import Any

DECONTAMINATION_PROTOCOL_VERSION = "13gram_jaccard_v1"
DEFAULT_NGRAM_SIZE = 13
DEFAULT_JACCARD_THRESHOLD = 0.8
_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _validate_parameters(ngram_size: int, threshold: float) -> None:
    if isinstance(ngram_size, bool) or not isinstance(ngram_size, int) or ngram_size <= 0:
        raise ValueError("ngram_size must be a positive integer")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("threshold must be numeric")
    if not 0.0 <= float(threshold) <= 1.0:
        raise ValueError("threshold must be between 0 and 1")


def _normalized_tokens(text: Any) -> list[str]:
    return _TOKEN_PATTERN.findall(str(text).lower())


def _ngrams(tokens: list[str], ngram_size: int) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index : index + ngram_size])
        for index in range(len(tokens) - ngram_size + 1)
    }


def ngram_jaccard_similarity(
    left_text: Any,
    right_text: Any,
    *,
    ngram_size: int = DEFAULT_NGRAM_SIZE,
) -> float:
    """Calculate token n-gram Jaccard similarity with exact-short-text handling."""
    _validate_parameters(ngram_size, 0.0)
    left_tokens = _normalized_tokens(left_text)
    right_tokens = _normalized_tokens(right_text)
    if left_tokens == right_tokens:
        return 1.0
    left_ngrams = _ngrams(left_tokens, ngram_size)
    right_ngrams = _ngrams(right_tokens, ngram_size)
    if not left_ngrams and not right_ngrams:
        return 0.0
    return len(left_ngrams & right_ngrams) / len(left_ngrams | right_ngrams)


def deduplicate_and_decontaminate(
    samples: list[dict[str, Any]],
    reference_samples: list[dict[str, Any]],
    *,
    ngram_size: int = DEFAULT_NGRAM_SIZE,
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
) -> dict[str, Any]:
    """Remove generated duplicates and samples overlapping a held-out reference set."""
    _validate_parameters(ngram_size, threshold)
    accepted_samples: list[dict[str, Any]] = []
    rejection_log: list[dict[str, Any]] = []
    seen_texts: dict[str, int] = {}

    for sample_index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError("samples must contain objects")
        sample_text = str(sample.get("text", sample.get("prompt", "")))
        normalized_text = " ".join(sample_text.lower().split())
        sample_id = str(
            sample.get("task_id", sample.get("instantiation_id", f"sample-{sample_index:06d}"))
        )
        if normalized_text in seen_texts:
            rejection_log.append(
                {
                    "sample_id": sample_id,
                    "reason": "duplicate_generated",
                    "matched_sample_index": seen_texts[normalized_text],
                }
            )
            continue
        seen_texts[normalized_text] = sample_index

        best_match: tuple[int, float] | None = None
        for reference_index, reference in enumerate(reference_samples):
            if not isinstance(reference, dict):
                raise ValueError("reference_samples must contain objects")
            reference_text = str(reference.get("text", reference.get("prompt", "")))
            similarity = ngram_jaccard_similarity(
                sample_text,
                reference_text,
                ngram_size=ngram_size,
            )
            if best_match is None or similarity > best_match[1]:
                best_match = (reference_index, similarity)
        if best_match is not None and best_match[1] >= float(threshold):
            rejection_log.append(
                {
                    "sample_id": sample_id,
                    "reason": "test_set_contamination",
                    "matched_reference_index": best_match[0],
                    "jaccard_similarity": best_match[1],
                }
            )
            continue
        accepted_samples.append(sample)

    duplicate_count = sum(
        1 for rejection in rejection_log if rejection["reason"] == "duplicate_generated"
    )
    contamination_count = sum(
        1 for rejection in rejection_log if rejection["reason"] == "test_set_contamination"
    )
    return {
        "accepted_samples": accepted_samples,
        "rejection_log": rejection_log,
        "report": {
            "protocol_version": DECONTAMINATION_PROTOCOL_VERSION,
            "ngram_size": ngram_size,
            "jaccard_threshold": float(threshold),
            "input_sample_count": len(samples),
            "reference_sample_count": len(reference_samples),
            "accepted_sample_count": len(accepted_samples),
            "duplicate_rejection_count": duplicate_count,
            "contamination_rejection_count": contamination_count,
            "rejection_count": len(rejection_log),
        },
    }
