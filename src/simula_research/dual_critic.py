from __future__ import annotations

from typing import Any

from simula_research.provider_protocols import (
    CriticSampleEvaluatorFn,
    CriticVerdict,
    CriticVerdictFn,
    RegenerationProviderFn,
    hash_based_critic_sample_evaluator,
    hash_based_critic_verdict,
)


def _normalized_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    configured = policy or {}
    disagreement_policy = str(configured.get("disagreement_policy", "reject"))
    if disagreement_policy not in {"reject", "accept", "regenerate"}:
        raise ValueError("disagreement_policy must be one of: reject, accept, regenerate")
    max_regenerations = int(configured.get("max_regenerations_per_sample", 1))
    if max_regenerations < 0:
        raise ValueError("max_regenerations_per_sample must be >= 0")
    single_critic_mode = configured.get("single_critic_mode")
    if single_critic_mode is not None and str(single_critic_mode) not in {"critic_a", "critic_b"}:
        raise ValueError("single_critic_mode must be one of: critic_a, critic_b")
    return {
        "disagreement_policy": disagreement_policy,
        "max_regenerations_per_sample": max_regenerations,
        "single_critic_mode": None if single_critic_mode is None else str(single_critic_mode),
    }


def adjudicate_samples(
    samples: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
    critic_verdict: CriticVerdictFn | None = None,
    critic_sample_evaluator: CriticSampleEvaluatorFn | None = None,
    regeneration_provider: RegenerationProviderFn | None = None,
) -> dict[str, Any]:
    if critic_verdict is not None and critic_sample_evaluator is not None:
        raise ValueError("critic_verdict and critic_sample_evaluator are mutually exclusive")

    adjudication_policy = _normalized_policy(policy)
    disagreement_policy = adjudication_policy["disagreement_policy"]
    max_regenerations = adjudication_policy["max_regenerations_per_sample"]
    single_critic_mode = adjudication_policy["single_critic_mode"]

    sample_evaluator = critic_sample_evaluator
    if sample_evaluator is None and critic_verdict is None:
        sample_evaluator = hash_based_critic_sample_evaluator

    text_decide: CriticVerdictFn = critic_verdict or hash_based_critic_verdict

    def _verdict_for_sample(sample_row: dict[str, Any], critic_id: str) -> CriticVerdict:
        if sample_evaluator is not None:
            return sample_evaluator(sample_row, critic_id)
        return text_decide(str(sample_row.get("text", "")), critic_id)

    def _dual_verdicts(sample_row: dict[str, Any]) -> tuple[CriticVerdict, CriticVerdict, bool]:
        if single_critic_mode == "critic_a":
            a = _verdict_for_sample(sample_row, "critic_a")
            return a, a, False
        if single_critic_mode == "critic_b":
            b = _verdict_for_sample(sample_row, "critic_b")
            return b, b, False
        return _verdict_for_sample(sample_row, "critic_a"), _verdict_for_sample(sample_row, "critic_b"), True

    def _agreement_status(
        critic_a_decision: CriticVerdict,
        critic_b_decision: CriticVerdict,
        agreement_evaluable: bool,
    ) -> str:
        if not agreement_evaluable:
            return "not_evaluable_single_critic"
        return "agree" if critic_a_decision == critic_b_decision else "disagree"

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
        critic_a_decision, critic_b_decision, agreement_evaluable = _dual_verdicts(sample)
        final_text = source_text
        final_critic_a_decision = critic_a_decision
        final_critic_b_decision = critic_b_decision

        if not agreement_evaluable:
            final_status = "accepted" if critic_a_decision == "accept" else "rejected"
            final_reason = "single_critic_accept" if final_status == "accepted" else "single_critic_reject"
        elif critic_a_decision == critic_b_decision:
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
                if regeneration_provider is None:
                    regen_text = f"{regen_text} [regen-{regeneration_index + 1}]"
                else:
                    regen_text = regeneration_provider(sample, regeneration_index + 1)
                    if not isinstance(regen_text, str) or not regen_text.strip():
                        raise ValueError("regeneration provider must return non-empty text")
                    regen_text = regen_text.strip()
                regen_row = {**sample, "text": regen_text}
                regen_a_decision, regen_b_decision, regen_agreement_evaluable = _dual_verdicts(regen_row)
                regenerations.append(
                    {
                        "instantiation_id": sample_id,
                        "taxonomy_node_id": taxonomy_node_id,
                        "meta_prompt_id": meta_prompt_id,
                        "regeneration_index": regeneration_index + 1,
                        "regenerated_text": regen_text,
                        "critic_a_decision": regen_a_decision,
                        "critic_b_decision": regen_b_decision,
                        "agreement_evaluable": regen_agreement_evaluable,
                        "agreement_status": _agreement_status(
                            regen_a_decision,
                            regen_b_decision,
                            regen_agreement_evaluable,
                        ),
                    }
                )
                if regen_a_decision == "accept" and regen_b_decision == "accept":
                    final_status = "accepted"
                    final_reason = "regeneration_consensus_accept"
                    final_text = regen_text
                    final_critic_a_decision = regen_a_decision
                    final_critic_b_decision = regen_b_decision
                    break

        decisions.append(
            {
                "instantiation_id": sample_id,
                "taxonomy_node_id": taxonomy_node_id,
                "meta_prompt_id": meta_prompt_id,
                "critic_a_decision": critic_a_decision,
                "critic_b_decision": critic_b_decision,
                "disagreement": critic_a_decision != critic_b_decision,
                "agreement_evaluable": agreement_evaluable,
                "agreement_status": _agreement_status(
                    critic_a_decision,
                    critic_b_decision,
                    agreement_evaluable,
                ),
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
                    **sample,
                    "text": final_text,
                    "critic_a_decision": final_critic_a_decision,
                    "critic_b_decision": final_critic_b_decision,
                    "agreement_evaluable": agreement_evaluable,
                    "agreement_status": _agreement_status(
                        final_critic_a_decision,
                        final_critic_b_decision,
                        agreement_evaluable,
                    ),
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
                    "agreement_evaluable": agreement_evaluable,
                    "agreement_status": _agreement_status(
                        critic_a_decision,
                        critic_b_decision,
                        agreement_evaluable,
                    ),
                    "regeneration_count": regen_count,
                }
            )

    evaluable_decisions = [decision for decision in decisions if bool(decision["agreement_evaluable"])]
    agreements = sum(
        1
        for decision in evaluable_decisions
        if decision["critic_a_decision"] == decision["critic_b_decision"]
    )
    disagreements = len(evaluable_decisions) - agreements

    return {
        "decisions": decisions,
        "accepted_samples": accepted_samples,
        "rejection_log": rejections,
        "regeneration_log": regenerations,
        "agreement_summary": {
            "evaluable_samples": len(evaluable_decisions),
            "non_evaluable_samples": len(decisions) - len(evaluable_decisions),
            "agreements": agreements,
            "disagreements": disagreements,
        },
        "policy": adjudication_policy,
    }
