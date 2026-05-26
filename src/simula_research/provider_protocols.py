from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Literal, Protocol

CriticVerdict = Literal["accept", "reject"]


class CriticVerdictFn(Protocol):
    """Callable used by dual-critic adjudication (Issue #29); swap for tests or real providers."""

    def __call__(self, text: str, critic_id: str) -> CriticVerdict: ...


class CriticSampleEvaluatorFn(Protocol):
    """Provider-facing hook (Issue #22): full Stage-3 sample dict (lineage, flags, text) per critic."""

    def __call__(self, sample: dict[str, Any], critic_id: str) -> CriticVerdict: ...


def sample_evaluator_from_text_fn(text_fn: CriticVerdictFn) -> CriticSampleEvaluatorFn:
    """Bridge text-only verdicts to the sample-aware evaluator path (parity / thin wrappers)."""

    def _eval(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        return text_fn(str(sample.get("text", "")), critic_id)

    return _eval


def recorded_sample_evaluator(
    table: Mapping[tuple[str, str, str], CriticVerdict],
) -> CriticSampleEvaluatorFn:
    """Offline replay from a fixed verdict table keyed by (instantiation_id, critic_id, text)."""

    def _eval(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
        key = (str(sample.get("instantiation_id", "")), critic_id, str(sample.get("text", "")))
        if key not in table:
            raise KeyError(f"recorded_sample_evaluator: missing verdict for {key!r}")
        return table[key]

    return _eval


def hash_based_critic_verdict(text: str, critic_id: str) -> CriticVerdict:
    """Deterministic offline stub with high dual-critic agreement (text-only hash)."""
    _ = critic_id
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return "accept" if int(digest[:2], 16) % 2 == 0 else "reject"
