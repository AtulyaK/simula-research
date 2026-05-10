from __future__ import annotations

from collections.abc import Callable
from typing import Any

from simula_research.provider_protocols import (
    CriticSampleEvaluatorFn,
    CriticVerdict,
    CriticVerdictFn,
    hash_based_critic_verdict,
    sample_evaluator_from_text_fn,
)


def _normalized_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    configured = policy or {}
    disagreement_policy = str(configured.get("disagreement_policy", "reject"))
    if disagreement_policy not in {"reject", "accept", "regenerate"}:
        raise ValueError("disagreement_policy must be one of: reject, accept, regenerate")
    max_regenerations = int(configured.get("max_regenerations_per_sample", 1))
    if max_regenerations < 0:
        raise ValueError("max_regenerations_per_sample must be >= 0")
    return {
        "disagreement_policy": disagreement_policy,
        "max_regenerations_per_sample": max_regenerations,
    }


def _resolve_sample_evaluator(
    critic_verdict: CriticVerdictFn | None,
    critic_sample_evaluator: CriticSampleEvaluatorFn | None,
) -> Callable[[dict[str, Any], str], CriticVerdict]:
    if critic_sample_evaluator is not None and critic_verdict is not None:
        raise ValueError(
            "Pass only one of critic_sample_evaluator (sample-aware, GitHub #22) "
            "or critic_verdict (text-only, Issue #29)"
        )
    if critic_sample_evaluator is not None:
        return critic_sample_evaluator
    text_fn = critic_verdict or hash_based_critic_verdict
    return sample_evaluator_from_text_fn(text_fn)


def adjudicate_samples(
    samples: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
    critic_verdict: CriticVerdictFn | None = None,
    critic_sample_evaluator: CriticSampleEvaluatorFn | None = None,
) -> dict[str, Any]:
    adjudication_policy = _normalized_policy(policy)
    disagreement_policy = adjudication_policy["disagreement_policy"]
    max_regenerations = adjudication_policy["max_regenerations_per_sample"]
    decide = _resolve_sample_evaluator(critic_verdict, critic_sample_evaluator)

    decisions: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    regenerations: list[dict[str, Any]] = []
    accepted_samples: list[dict[str, Any]] = []

    for sample in samples:
        sample_id = str(sample.get("instantiation_id", "unknown-sample"))
        taxonomy_node_id = str(sample.get("taxonomy_node_id", "unknown-node"))
        meta_prompt_id = str(sample.get("meta_prompt_id", "unknown-meta"))
        source_text = str(sample.get("text", ""))
        regen_count = 0
        critic_a_decision = decide(sample, "critic_a")
        critic_b_decision = decide(sample, "critic_b")
        final_sample = sample

        if critic_a_decision == critic_b_decision:
            final_status = "accepted" if critic_a_decision == "accept" else "rejected"
            final_reason = "both_accept" if final_status == "accepted" else "both_reject"
        elif disagreement_policy == "accept":
            final_status = "accepted"
            final_reason = "policy_accept_on_disagreement"
        elif disagreement_policy == "reject":
            final_status = "rejected"
            final_reason = "policy_reject_on_disagreement"
        else:
            final_status = "rejected"
            final_reason = "policy_regenerate_exhausted"
            regen_text = source_text
            for regeneration_index in range(max_regenerations):
                regen_count += 1
                regen_text = f"{regen_text} [regen-{regeneration_index + 1}]"
                regen_sample = {**sample, "text": regen_text}
                regen_a_decision = decide(regen_sample, "critic_a")
                regen_b_decision = decide(regen_sample, "critic_b")
                regenerations.append(
                    {
                        "instantiation_id": sample_id,
                        "taxonomy_node_id": taxonomy_node_id,
                        "meta_prompt_id": meta_prompt_id,
                        "regeneration_index": regeneration_index + 1,
                        "regenerated_text": regen_text,
                        "critic_a_decision": regen_a_decision,
                        "critic_b_decision": regen_b_decision,
                    }
                )
                if regen_a_decision == "accept" and regen_b_decision == "accept":
                    final_status = "accepted"
                    final_reason = "regeneration_consensus_accept"
                    critic_a_decision = regen_a_decision
                    critic_b_decision = regen_b_decision
                    final_sample = regen_sample
                    break

        decisions.append(
            {
                "instantiation_id": sample_id,
                "taxonomy_node_id": taxonomy_node_id,
                "meta_prompt_id": meta_prompt_id,
                "critic_a_decision": critic_a_decision,
                "critic_b_decision": critic_b_decision,
                "disagreement": critic_a_decision != critic_b_decision,
                "adjudication_policy": disagreement_policy,
                "quality_status": final_status,
                "final_reason": final_reason,
                "regeneration_count": regen_count,
                "review_status": "reviewed",
            }
        )

        if final_status == "accepted":
            accepted_samples.append(
                {
                    **final_sample,
                    "critic_a_decision": critic_a_decision,
                    "critic_b_decision": critic_b_decision,
                    "quality_status": "accepted",
                    "regeneration_count": regen_count,
                }
            )
        else:
            rejections.append(
                {
                    "instantiation_id": sample_id,
                    "taxonomy_node_id": taxonomy_node_id,
                    "meta_prompt_id": meta_prompt_id,
                    "reason": final_reason,
                    "critic_a_decision": critic_a_decision,
                    "critic_b_decision": critic_b_decision,
                    "regeneration_count": regen_count,
                }
            )

    return {
        "decisions": decisions,
        "accepted_samples": accepted_samples,
        "rejection_log": rejections,
        "regeneration_log": regenerations,
        "policy": adjudication_policy,
    }
