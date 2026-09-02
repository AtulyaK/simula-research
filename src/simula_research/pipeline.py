from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from simula_research.complexity_judgments import (
    COMPLEXITY_JUDGMENT_DEFAULTS,
    collect_batchwise_complexity_judgments,
    collect_pairwise_complexity_judgments,
)
from simula_research.dataset_adapters import validate_split_manifest
from simula_research.dataset_verification import validate_local_dataset_manifest
from simula_research.downstream_evaluation import (
    validate_downstream_evaluation_plan,
    validate_downstream_evaluation_results,
)
from simula_research.decontamination import (
    deduplicate_and_decontaminate,
)
from simula_research.dual_critic import adjudicate_samples
from simula_research.manifest import validate_manifest
from simula_research.provider_protocols import (
    BatchComplexityJudgmentProviderFn,
    ComplexityJudgmentProviderFn,
    ComplexificationProviderFn,
    CriticSampleEvaluatorFn,
    CriticVerdictFn,
    LocalDiversificationProviderFn,
    RegenerationProviderFn,
    TaxonomyProviderFn,
    default_complexification_provider,
    default_local_diversification_provider,
    default_taxonomy_provider,
)
from simula_research.run_artifact_store import FileSystemRunArtifactStore, RunArtifactStore
from simula_research.stage_contracts import validate_stage_handoffs
from simula_research.taxonomy import TaxonomyConfig

PROTOCOL_VERSION = "0.1.0"
ARTIFACT_SCHEMA_VERSION = "0.1.0"

DEFAULT_PIPELINE_CONFIG: dict[str, Any] = {
    "global_diversification_enabled": True,
    "local_diversification_enabled": True,
    "complexification_enabled": True,
    "dual_critic_enabled": True,
}

STAGE_NAMES = [
    "stage_0_domain_run_spec",
    "stage_1_global_diversification",
    "stage_2_local_diversification",
    "stage_3_complexification",
    "stage_4_dual_critic_quality_verification",
    "stage_5_evaluation_handoff",
]


def _persist_optional(store: RunArtifactStore, method_name: str, *args: Any, **kwargs: Any) -> dict[str, str]:
    persist = getattr(store, method_name, None)
    if not callable(persist):
        return {}
    return dict(persist(*args, **kwargs))


def run_pipeline(
    seed: int,
    model_ids: dict[str, str],
    domain_objective: str = "pilot-domain",
    artifact_root: str | Path = "artifacts/runs",
    taxonomy_config: dict[str, int] | None = None,
    complexification_config: dict[str, Any] | None = None,
    dual_critic_config: dict[str, Any] | None = None,
    local_diversification_config: dict[str, Any] | None = None,
    pipeline_config: dict[str, Any] | None = None,
    manifest_metadata: dict[str, Any] | None = None,
    provider_runtime: dict[str, Any] | None = None,
    provider_event_log: list[dict[str, Any]] | None = None,
    artifact_store_factory: Callable[[Path], RunArtifactStore] | None = None,
    taxonomy_provider: TaxonomyProviderFn | None = None,
    local_diversification_provider: LocalDiversificationProviderFn | None = None,
    complexification_provider: ComplexificationProviderFn | None = None,
    critic_verdict: CriticVerdictFn | None = None,
    critic_sample_evaluator: CriticSampleEvaluatorFn | None = None,
    regeneration_provider: RegenerationProviderFn | None = None,
    complexity_judgment_provider: ComplexityJudgmentProviderFn | None = None,
    batch_complexity_judgment_provider: BatchComplexityJudgmentProviderFn | None = None,
    complexity_judgment_config: dict[str, int] | None = None,
    dataset_protocol_config: dict[str, Any] | None = None,
    downstream_evaluation_plan: dict[str, Any] | None = None,
    downstream_evaluation_results: list[dict[str, Any]] | None = None,
    decontamination_reference_samples: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    if critic_verdict is not None and critic_sample_evaluator is not None:
        raise ValueError("critic_verdict and critic_sample_evaluator are mutually exclusive")

    created_at = datetime.now(UTC)
    run_id = f"run-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

    manifest_pipeline = {
        **DEFAULT_PIPELINE_CONFIG,
        **dict(pipeline_config or {}),
    }

    taxonomy_cfg = dict(taxonomy_config or {})
    if pipeline_config is not None and not pipeline_config.get("global_diversification_enabled", True):
        taxonomy_cfg = {"max_depth": 0, "branching_factor": 1}
    resolved_taxonomy_config = {
        "max_depth": int(taxonomy_cfg.get("max_depth", 2)),
        "branching_factor": int(taxonomy_cfg.get("branching_factor", 2)),
    }

    local_options = dict(local_diversification_config or {})
    if pipeline_config is not None and not pipeline_config.get("local_diversification_enabled", True):
        local_options["per_node_instantiation_count"] = 1
    resolved_local_config = {
        **local_options,
        "per_node_instantiation_count": int(local_options.get("per_node_instantiation_count", 3)),
        "overlap_rejection_threshold": float(
            local_options.get("overlap_rejection_threshold", 0.8)
        ),
        "node_mix_size": int(local_options.get("node_mix_size", 1)),
    }
    if (
        resolved_local_config["per_node_instantiation_count"] <= 0
        or not 0 <= resolved_local_config["overlap_rejection_threshold"] <= 1
        or resolved_local_config["node_mix_size"] <= 0
    ):
        raise ValueError("invalid local diversification configuration")

    complex_cfg = dict(complexification_config or {})
    if pipeline_config is not None and not pipeline_config.get("complexification_enabled", True):
        complex_cfg["complexify_fraction"] = 0.0
    resolved_complexification_config = {
        **complex_cfg,
        "complexify_fraction": float(complex_cfg.get("complexify_fraction", 0.75)),
        "semantic_overlap_threshold": float(
            complex_cfg.get("semantic_overlap_threshold", 0.55)
        ),
        "strategy": str(complex_cfg.get("strategy", "append_reasoning")),
    }

    dual_cfg = dict(dual_critic_config or {})
    if pipeline_config is not None and not pipeline_config.get("dual_critic_enabled", True):
        dual_cfg["single_critic_mode"] = str(pipeline_config.get("single_critic_mode", "critic_a"))
    resolved_dual_critic_config = {
        "disagreement_policy": str(dual_cfg.get("disagreement_policy", "reject")),
        "max_regenerations_per_sample": int(
            dual_cfg.get("max_regenerations_per_sample", 1)
        ),
        "single_critic_mode": dual_cfg.get("single_critic_mode"),
    }
    resolved_dual_critic_config.update(
        {
            key: value
            for key, value in dual_cfg.items()
            if key not in resolved_dual_critic_config
        }
    )
    resolved_complexity_judgment_config = {
        **COMPLEXITY_JUDGMENT_DEFAULTS,
        **dict(complexity_judgment_config or {}),
    }
    resolved_dataset_protocol_config = dict(dataset_protocol_config or {})
    benchmark_split_manifest = resolved_dataset_protocol_config.get("benchmark_split_manifest")
    if benchmark_split_manifest is not None:
        validate_split_manifest(benchmark_split_manifest)
    local_dataset_manifest = resolved_dataset_protocol_config.get("local_dataset_manifest")
    if local_dataset_manifest is not None:
        validate_local_dataset_manifest(local_dataset_manifest)
    if decontamination_reference_samples is not None:
        resolved_dataset_protocol_config.setdefault(
            "decontamination_protocol", "13gram_jaccard_v1"
        )
    if downstream_evaluation_plan is not None:
        validate_downstream_evaluation_plan(downstream_evaluation_plan)
    if downstream_evaluation_results is not None:
        if downstream_evaluation_plan is None:
            raise ValueError("downstream_evaluation_results requires a downstream_evaluation_plan")
        validate_downstream_evaluation_results(
            downstream_evaluation_plan,
            downstream_evaluation_results,
        )

    resolved_run_config = {
        "pipeline_config": dict(manifest_pipeline),
        "taxonomy_config": resolved_taxonomy_config,
        "local_diversification_config": resolved_local_config,
        "complexification_config": resolved_complexification_config,
        "dual_critic_config": resolved_dual_critic_config,
        "complexity_judgment_config": resolved_complexity_judgment_config,
        "dataset_protocol_config": resolved_dataset_protocol_config,
    }
    if downstream_evaluation_plan is not None:
        resolved_run_config["downstream_evaluation_plan"] = dict(downstream_evaluation_plan)

    manifest: dict[str, Any] = {
        **dict(manifest_metadata or {}),
        "run_id": run_id,
        "created_at_utc": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "domain_objective": domain_objective,
        "model_ids": model_ids,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "pipeline_config": manifest_pipeline,
        "run_config": resolved_run_config,
    }
    if provider_runtime:
        manifest["provider_runtime"] = dict(provider_runtime)
    validate_manifest(manifest)

    stage_outputs: dict[str, Any] = {
        stage_name: {"status": "placeholder", "run_id": run_id} for stage_name in STAGE_NAMES
    }

    taxonomy_fn = taxonomy_provider or default_taxonomy_provider
    taxonomy = taxonomy_fn(
        domain_objective,
        TaxonomyConfig(
            max_depth=resolved_taxonomy_config["max_depth"],
            branching_factor=resolved_taxonomy_config["branching_factor"],
        ),
    )

    run_root = Path(artifact_root) / run_id
    store_factory = artifact_store_factory or (lambda root: FileSystemRunArtifactStore(root))
    store = store_factory(run_root)
    stage_outputs["stage_0_domain_run_spec"] = {
        "status": "completed",
        "run_id": run_id,
        "domain_objective": domain_objective,
        "seed": seed,
        "model_ids": dict(model_ids),
        "pipeline_config": dict(manifest_pipeline),
    }
    artifacts = store.persist_taxonomy(taxonomy)

    local_fn = local_diversification_provider or default_local_diversification_provider
    local_diversification = local_fn(taxonomy, options=local_options or None)
    local_artifacts = store.persist_local_diversification(local_diversification)

    complex_fn = complexification_provider or default_complexification_provider
    complexification = complex_fn(
        local_diversification["instantiations"],
        complexify_fraction=resolved_complexification_config["complexify_fraction"],
        semantic_overlap_threshold=resolved_complexification_config["semantic_overlap_threshold"],
        strategy=resolved_complexification_config["strategy"],
    )
    batchwise_complexity = (
        collect_batchwise_complexity_judgments(
            samples=complexification["samples"],
            provider=batch_complexity_judgment_provider,
            batch_size=int(resolved_complexity_judgment_config["batch_size"]),
            samples_per_item=int(resolved_complexity_judgment_config["samples_per_item"]),
            seed=seed,
            initial_rating=int(resolved_complexity_judgment_config["initial_rating"]),
            k_factor=int(resolved_complexity_judgment_config["k_factor"]),
        )
        if batch_complexity_judgment_provider is not None
        else None
    )
    pairwise_complexity_judgments = (
        collect_pairwise_complexity_judgments(
            samples=complexification["samples"],
            provider=complexity_judgment_provider,
        )
        if complexity_judgment_provider is not None
        else []
    )
    complexification_artifact_payload = dict(complexification)
    if batchwise_complexity is not None:
        complexification["batchwise_complexity"] = batchwise_complexity
        complexification_artifact_payload["batchwise_complexity"] = batchwise_complexity
    if complexity_judgment_provider is not None:
        complexification["pairwise_judgments"] = pairwise_complexity_judgments
        complexification_artifact_payload["pairwise_judgments"] = pairwise_complexity_judgments
    complex_artifacts = store.persist_complexification(complexification_artifact_payload)

    adjudication = adjudicate_samples(
        samples=complexification["samples"],
        policy=dual_cfg or None,
        critic_verdict=critic_verdict,
        critic_sample_evaluator=critic_sample_evaluator,
        regeneration_provider=regeneration_provider,
    )
    validate_stage_handoffs(
        taxonomy=taxonomy,
        local_diversification=local_diversification,
        complexification=complexification,
        adjudication=adjudication,
    )
    adjudication_artifact_payload = dict(adjudication)
    if provider_runtime:
        adjudication_artifact_payload["provider_runtime"] = dict(provider_runtime)
    if provider_event_log is not None:
        adjudication_artifact_payload["nim_event_log"] = list(provider_event_log)
    dual_critic_artifacts = store.persist_dual_critic(adjudication_artifact_payload)

    stage_outputs["stage_1_global_diversification"] = {
        "status": "completed",
        "run_id": run_id,
        "taxonomy_root_node_id": taxonomy["root_taxonomy_node_id"],
        "taxonomy_node_count": len(taxonomy["nodes"]),
        "taxonomy_edge_count": len(taxonomy["edges"]),
        "taxonomy_artifacts": artifacts,
        "handoff_contract_issue_3": {
            "required_fields_per_taxonomy_node": [
                "taxonomy_node_id",
                "parent_taxonomy_node_id",
                "label",
                "depth",
            ],
            "traceability_fields_for_local_diversification": [
                "taxonomy_node_id",
                "meta_prompt_id",
                "instantiation_id",
            ],
        },
    }
    stage_outputs["stage_2_local_diversification"] = {
        "status": "completed",
        "run_id": run_id,
        "instantiation_count": len(local_diversification["instantiations"]),
        "rejection_count": len(local_diversification["rejections"]),
        "anti_collapse_checks": local_diversification["anti_collapse_checks"],
        "local_diversification_artifacts": local_artifacts,
    }
    stage_outputs["stage_3_complexification"] = {
        "status": "completed",
        "run_id": run_id,
        "complexified_count": len(
            [sample for sample in complexification["samples"] if sample["is_complexified"]]
        ),
        "semantic_preservation_failure_count": len(complexification["semantic_preservation_failures"]),
        "complexification_policy": complexification["complexification_policy"],
        "complexification_artifacts": complex_artifacts,
    }
    reviewed_samples = len(adjudication["decisions"])
    accepted_samples = len(adjudication["accepted_samples"])
    fallback_agreements = sum(
        1
        for decision in adjudication["decisions"]
        if decision["critic_a_decision"] == decision["critic_b_decision"]
    )
    agreement_summary = adjudication.get("agreement_summary", {})
    agreement_evaluable_samples = int(agreement_summary.get("evaluable_samples", reviewed_samples))
    agreement_non_evaluable_samples = int(agreement_summary.get("non_evaluable_samples", 0))
    agreements = int(agreement_summary.get("agreements", fallback_agreements))
    disagreements = int(agreement_summary.get("disagreements", reviewed_samples - fallback_agreements))
    stage4_payload: dict[str, Any] = {
        "status": "completed",
        "run_id": run_id,
        "reviewed_samples": reviewed_samples,
        "accepted_samples": accepted_samples,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_evaluable_samples": agreement_evaluable_samples,
        "agreement_non_evaluable_samples": agreement_non_evaluable_samples,
        "regenerated_samples": len(adjudication["regeneration_log"]),
        "adjudication_policy": adjudication["policy"],
        "stage4_artifacts": dual_critic_artifacts,
    }
    if provider_runtime:
        stage4_payload["provider_runtime"] = dict(provider_runtime)
    stage_outputs["stage_4_dual_critic_quality_verification"] = stage4_payload

    accepted_samples = list(adjudication["accepted_samples"])
    decontamination_result: dict[str, Any] | None = None
    if decontamination_reference_samples is not None:
        decontamination_result = deduplicate_and_decontaminate(
            accepted_samples,
            decontamination_reference_samples,
        )
        accepted_samples = decontamination_result["accepted_samples"]

    curated_dataset: dict[str, Any] = {
        "run_id": run_id,
        "source_stage": "stage_4_dual_critic_quality_verification",
        "dataset_protocol": resolved_dataset_protocol_config,
        "accepted_sample_count": len(accepted_samples),
        "accepted_samples": accepted_samples,
    }
    if decontamination_result is not None:
        curated_dataset["pre_decontamination_accepted_sample_count"] = len(
            adjudication["accepted_samples"]
        )
        curated_dataset["decontamination_report"] = decontamination_result["report"]
        curated_dataset["decontamination_rejections"] = decontamination_result["rejection_log"]
    curated_artifacts = _persist_optional(store, "persist_curated_dataset", curated_dataset)

    diagnostics = {
        "run_id": run_id,
        "status": "completed",
        "semantic_preservation_failure_count": len(complexification["semantic_preservation_failures"]),
        "stage2_rejection_count": len(local_diversification["rejections"]),
        "stage4_rejection_count": len(adjudication["rejection_log"]),
        "regeneration_count": len(adjudication["regeneration_log"]),
        "diagnostic_sources": {
            "stage2_rejections": local_artifacts["rejections"],
            "semantic_preservation_failures": complex_artifacts["semantic_preservation_failures"],
            "stage4_rejections": dual_critic_artifacts["rejections"],
            "stage4_regenerations": dual_critic_artifacts["regenerations"],
        },
    }
    diagnostics_artifacts = _persist_optional(store, "persist_diagnostics", diagnostics)

    evaluation_handoff = {
        "run_id": run_id,
        "status": "ready_for_evaluation",
        "metrics_status": "not_computed_by_pipeline",
        "note": "run_pipeline persists evaluation inputs; gate metrics are computed by the evaluation/reporting layer.",
        "inputs": {
            "manifest": str(run_root / "00_spec" / "manifest.json"),
            "dataset_protocol": resolved_dataset_protocol_config,
            "taxonomy_nodes": artifacts["taxonomy_nodes"],
            "complexification_samples": complex_artifacts["samples"],
            "critic_decisions": dual_critic_artifacts["critic_decisions"],
            "accepted_samples": curated_artifacts.get("accepted_samples"),
        },
    }
    if downstream_evaluation_plan is not None:
        evaluation_handoff["downstream_evaluation"] = dict(downstream_evaluation_plan)
    downstream_evaluation_artifacts: dict[str, str] = {}
    if downstream_evaluation_results is not None:
        downstream_evaluation_artifacts = _persist_optional(
            store,
            "persist_downstream_evaluation_results",
            {
                "schema_version": downstream_evaluation_plan["schema_version"],
                "run_id": run_id,
                "results": list(downstream_evaluation_results),
            },
        )
        evaluation_handoff["downstream_evaluation"] = {
            **dict(downstream_evaluation_plan or {}),
            "results_status": "recorded",
            "result_count": len(downstream_evaluation_results),
            "artifacts": downstream_evaluation_artifacts,
        }
    evaluation_artifacts = _persist_optional(store, "persist_evaluation_handoff", evaluation_handoff)

    stage_outputs["stage_5_evaluation_handoff"] = {
        "status": "ready_for_evaluation",
        "run_id": run_id,
        "metrics_status": "not_computed_by_pipeline",
        "curated_dataset_artifacts": curated_artifacts,
        "decontamination": (
            decontamination_result["report"] if decontamination_result is not None else None
        ),
        "evaluation_artifacts": evaluation_artifacts,
        "downstream_evaluation_artifacts": downstream_evaluation_artifacts,
        "diagnostics_artifacts": diagnostics_artifacts,
    }

    spec_artifacts = _persist_optional(store, "persist_run_spec", manifest, stage_outputs=stage_outputs)
    if spec_artifacts:
        stage_outputs["stage_0_domain_run_spec"]["spec_artifacts"] = spec_artifacts
        _persist_optional(store, "persist_run_spec", manifest, stage_outputs=stage_outputs)

    return {
        "manifest": manifest,
        "stage_outputs": stage_outputs,
        "taxonomy": taxonomy,
        "decontamination": decontamination_result,
    }
