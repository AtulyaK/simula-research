from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Literal, Protocol

from simula_research.complexification import apply_complexification
from simula_research.local_diversification import build_local_diversification
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy

CriticVerdict = Literal["accept", "reject"]


class CriticVerdictFn(Protocol):
    """Callable used by dual-critic adjudication (Issue #29); swap for tests or real providers."""

    def __call__(self, text: str, critic_id: str) -> CriticVerdict: ...


class CriticSampleEvaluatorFn(Protocol):
    """Provider-facing hook (Issue #22): full Stage-3 sample dict (lineage, flags, text) per critic."""

    def __call__(self, sample: dict[str, Any], critic_id: str) -> CriticVerdict: ...


class TaxonomyProviderFn(Protocol):
    """Stage 1 hook (Issue #60): taxonomy / global diversification."""

    def __call__(self, domain_objective: str, config: TaxonomyConfig | None = None) -> dict[str, Any]: ...


class LocalDiversificationProviderFn(Protocol):
    """Stage 2 hook (Issue #60): local diversification from taxonomy handoff."""

    def __call__(self, taxonomy: dict[str, Any], *, options: dict[str, Any] | None = None) -> dict[str, Any]: ...


class ComplexificationProviderFn(Protocol):
    """Stage 3 hook (Issue #60): complexification from local instantiations."""

    def __call__(
        self,
        samples: list[dict[str, Any]],
        *,
        complexify_fraction: float = 0.75,
        semantic_overlap_threshold: float = 0.55,
        strategy: str = "append_reasoning",
    ) -> dict[str, Any]: ...


def default_taxonomy_provider(domain_objective: str, config: TaxonomyConfig | None = None) -> dict[str, Any]:
    return build_taxonomy(domain_objective, config)


def default_local_diversification_provider(
    taxonomy: dict[str, Any],
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_local_diversification(taxonomy=taxonomy, options=options)


def default_complexification_provider(
    samples: list[dict[str, Any]],
    *,
    complexify_fraction: float = 0.75,
    semantic_overlap_threshold: float = 0.55,
    strategy: str = "append_reasoning",
) -> dict[str, Any]:
    return apply_complexification(
        samples=samples,
        complexify_fraction=complexify_fraction,
        semantic_overlap_threshold=semantic_overlap_threshold,
        strategy=strategy,
    )


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


def hash_based_critic_sample_evaluator(sample: dict[str, Any], critic_id: str) -> CriticVerdict:
    """Offline default: sample-content verdict with dual-critic parity (critic_id ignored)."""
    _ = critic_id
    sample_key = (
        f"{sample.get('taxonomy_node_id', '')}::"
        f"{sample.get('instantiation_id', '')}::"
        f"{sample.get('text', '')}"
    )
    digest = hashlib.sha1(sample_key.encode("utf-8")).hexdigest()
    return "accept" if int(digest[:2], 16) % 10 < 8 else "reject"
