from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Literal, Protocol

CriticVerdict = Literal["accept", "reject"]


class CriticVerdictFn(Protocol):
    """Callable used by dual-critic adjudication (Issue #29); swap for tests or legacy text-only hooks."""

    def __call__(self, text: str, critic_id: str) -> CriticVerdict: ...


class CriticSampleEvaluatorFn(Protocol):
    """Provider-facing hook (GitHub #22): full Stage-3 sample dict + critic id → verdict.

    Use this for LLM-backed critics that need lineage fields (`instantiation_id`, taxonomy ids,
    `is_complexified`, …). Stage 4 on-disk JSON schema is unchanged; only the decision source differs.
    """

    def __call__(self, sample: dict[str, Any], critic_id: str) -> CriticVerdict: ...


def hash_based_critic_verdict(text: str, critic_id: str) -> CriticVerdict:
    """Deterministic stub matching historical `dual_critic._decision_from_text` behavior."""
    digest = hashlib.sha1(f"{critic_id}::{text}".encode("utf-8")).hexdigest()
    return "accept" if int(digest[:2], 16) % 2 == 0 else "reject"


def sample_evaluator_from_text_fn(fn: CriticVerdictFn) -> CriticSampleEvaluatorFn:
    """Wrap a text-only verdict function as a sample evaluator (replay / parity with Issue #29)."""

    def evaluate(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        return fn(str(sample.get("text", "")), critic_id)

    return evaluate


def recorded_sample_evaluator(
    table: Mapping[tuple[str, str, str], CriticVerdict],
) -> CriticSampleEvaluatorFn:
    """Deterministic replay: map (instantiation_id, critic_id, text) → verdict.

    Intended for reruns that must match a prior provider-backed session without calling APIs again.
    """
    frozen = dict(table)

    def evaluate(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        key = (
            str(sample.get("instantiation_id", "unknown-sample")),
            critic_id,
            str(sample.get("text", "")),
        )
        if key not in frozen:
            msg = f"recorded_sample_evaluator: missing verdict for {key!r}"
            raise KeyError(msg)
        return frozen[key]

    return evaluate
