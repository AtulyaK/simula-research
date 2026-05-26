from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from simula_research.dual_critic import adjudicate_samples
from simula_research.manifest import validate_manifest
from simula_research.operator_log import log_detail, log_stage_complete, log_stage_start, log_step
from simula_research.provider_protocols import (
    ComplexificationProviderFn,
    CriticSampleEvaluatorFn,
    CriticVerdictFn,
    LocalDiversificationProviderFn,
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
    provider_runtime: dict[str, Any] | None = None,
    artifact_store_factory: Callable[[Path], RunArtifactStore] | None = None,
    taxonomy_provider: TaxonomyProviderFn | None = None,
    local_diversification_provider: LocalDiversificationProviderFn | None = None,
    complexification_provider: ComplexificationProviderFn | None = None,
    critic_verdict: CriticVerdictFn | None = None,
    critic_sample_evaluator: CriticSampleEvaluatorFn | None = None,
) -> dict[str, object]:
    if critic_verdict is not None and critic_sample_evaluator is not None:
        raise ValueError("critic_verdict and critic_sample_evaluator are mutually exclusive")

    created_at = datetime.now(UTC)
    run_id = f"run-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

    manifest_pipeline = dict(pipeline_config) if pipeline_config is not None else dict(DEFAULT_PIPELINE_CONFIG)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "created_at_utc": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "domain_objective": domain_objective,
        "model_ids": model_ids,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "pipeline_config": manifest_pipeline,
    }
    if provider_runtime:
        manifest["provider_runtime"] = dict(provider_runtime)
    validate_manifest(manifest)

    log_step(f"pipeline run_id={run_id} seed={seed}")
    if provider_runtime:
        backend = provider_runtime.get("critic_backend", "unknown")
        log_detail("critic_backend", backend)

    stage_outputs: dict[str, Any] = {
        stage_name: {"status": "placeholder", "run_id": run_id} for stage_name in STAGE_NAMES
    }

    taxonomy_cfg = dict(taxonomy_config or {})
    if pipeline_config is not None and not pipeline_config.get("global_diversification_enabled", True):
        taxonomy_cfg = {"max_depth": 0, "branching_factor": 1}

    log_stage_start("10_taxonomy", max_depth=taxonomy_cfg.get("max_depth", 2))
    taxonomy_fn = taxonomy_provider or default_taxonomy_provider
    taxonomy = taxonomy_fn(
        domain_objective,
        TaxonomyConfig(
            max_depth=int(taxonomy_cfg.get("max_depth", 2)),
            branching_factor=int(taxonomy_cfg.get("branching_factor", 2)),
        ),
    )

    run_root = Path(artifact_root) / run_id
    store_factory = artifact_store_factory or (lambda root: FileSystemRunArtifactStore(root))
    store = store_factory(run_root)
    artifacts = store.persist_taxonomy(taxonomy)
    log_stage_complete(
        "10_taxonomy",
        node_count=len(taxonomy["nodes"]),
        edge_count=len(taxonomy["edges"]),
    )

    local_options = dict(local_diversification_config or {})
    if pipeline_config is not None and not pipeline_config.get("local_diversification_enabled", True):
        local_options["per_node_instantiation_count"] = 1

    log_stage_start("20_local_diversification")
    local_fn = local_diversification_provider or default_local_diversification_provider
    local_diversification = local_fn(taxonomy, options=local_options or None)
    local_artifacts = store.persist_local_diversification(local_diversification)
    log_stage_complete(
        "20_local_diversification",
        instantiations=len(local_diversification["instantiations"]),
        rejections=len(local_diversification["rejections"]),
    )

    complex_cfg = dict(complexification_config or {})
    if pipeline_config is not None and not pipeline_config.get("complexification_enabled", True):
        complex_cfg["complexify_fraction"] = 0.0

    log_stage_start("30_complexification", complexify_fraction=complex_cfg.get("complexify_fraction", 0.75))
    complex_fn = complexification_provider or default_complexification_provider
    complexification = complex_fn(
        local_diversification["instantiations"],
        complexify_fraction=float(complex_cfg.get("complexify_fraction", 0.75)),
        semantic_overlap_threshold=float(complex_cfg.get("semantic_overlap_threshold", 0.55)),
        strategy=str(complex_cfg.get("strategy", "append_reasoning")),
    )
    complex_artifacts = store.persist_complexification(complexification)
    log_stage_complete(
        "30_complexification",
        samples=len(complexification["samples"]),
        complexified=sum(1 for s in complexification["samples"] if s["is_complexified"]),
    )

    dual_cfg = dict(dual_critic_config or {})
    if pipeline_config is not None and not pipeline_config.get("dual_critic_enabled", True):
        dual_cfg["single_critic_mode"] = str(pipeline_config.get("single_critic_mode", "critic_a"))

    log_stage_start(
        "40_dual_critic_quality",
        sample_count=len(complexification["samples"]),
        dual_critic=manifest_pipeline.get("dual_critic_enabled", True),
    )
    adjudication = adjudicate_samples(
        samples=complexification["samples"],
        policy=dual_cfg or None,
        critic_verdict=critic_verdict,
        critic_sample_evaluator=critic_sample_evaluator,
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
    dual_critic_artifacts = store.persist_dual_critic(adjudication_artifact_payload)
    log_stage_complete(
        "40_dual_critic_quality",
        reviewed=len(adjudication["decisions"]),
        accepted=len(adjudication["accepted_samples"]),
        regenerations=len(adjudication["regeneration_log"]),
    )

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
    agreements = sum(
        1
        for decision in adjudication["decisions"]
        if decision["critic_a_decision"] == decision["critic_b_decision"]
    )
    reviewed_samples = len(adjudication["decisions"])
    accepted_samples = len(adjudication["accepted_samples"])
    stage4_payload: dict[str, Any] = {
        "status": "completed",
        "run_id": run_id,
        "reviewed_samples": reviewed_samples,
        "accepted_samples": accepted_samples,
        "agreements": agreements,
        "disagreements": reviewed_samples - agreements,
        "regenerated_samples": len(adjudication["regeneration_log"]),
        "adjudication_policy": adjudication["policy"],
        "stage4_artifacts": dual_critic_artifacts,
    }
    if provider_runtime:
        stage4_payload["provider_runtime"] = dict(provider_runtime)
    stage_outputs["stage_4_dual_critic_quality_verification"] = stage4_payload

    log_step("pipeline complete")
    return {"manifest": manifest, "stage_outputs": stage_outputs, "taxonomy": taxonomy}
