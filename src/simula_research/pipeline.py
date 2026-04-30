from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from simula_research.complexification import apply_complexification
from simula_research.dual_critic import adjudicate_samples
from simula_research.local_diversification import build_local_diversification
from simula_research.manifest import validate_manifest
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy

PROTOCOL_VERSION = "0.1.0"
ARTIFACT_SCHEMA_VERSION = "0.1.0"

STAGE_NAMES = [
    "stage_0_domain_run_spec",
    "stage_1_global_diversification",
    "stage_2_local_diversification",
    "stage_3_complexification",
    "stage_4_dual_critic_quality_verification",
    "stage_5_evaluation_handoff",
]


def _persist_taxonomy_artifacts(run_root: Path, taxonomy: dict[str, Any]) -> dict[str, str]:
    taxonomy_dir = run_root / "10_taxonomy"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)

    graph_path = taxonomy_dir / "taxonomy_graph.json"
    nodes_path = taxonomy_dir / "taxonomy_nodes.json"

    graph_path.write_text(
        json.dumps(
            {
                "domain_namespace": taxonomy["domain_namespace"],
                "root_taxonomy_node_id": taxonomy["root_taxonomy_node_id"],
                "edges": taxonomy["edges"],
                "generation_policy": taxonomy["generation_policy"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    nodes_path.write_text(json.dumps(taxonomy["nodes"], indent=2, sort_keys=True), encoding="utf-8")

    return {
        "taxonomy_graph": str(graph_path),
        "taxonomy_nodes": str(nodes_path),
    }


def _persist_local_diversification_artifacts(
    run_root: Path, local_diversification: dict[str, Any]
) -> dict[str, str]:
    local_dir = run_root / "20_local_diversification"
    local_dir.mkdir(parents=True, exist_ok=True)

    instantiations_path = local_dir / "instantiations.json"
    rejections_path = local_dir / "rejections.json"

    instantiations_path.write_text(
        json.dumps(local_diversification["instantiations"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    rejections_path.write_text(
        json.dumps(local_diversification["rejections"], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "instantiations": str(instantiations_path),
        "rejections": str(rejections_path),
    }


def _persist_complexification_artifacts(run_root: Path, complexification: dict[str, Any]) -> dict[str, str]:
    complex_dir = run_root / "30_complexification"
    complex_dir.mkdir(parents=True, exist_ok=True)

    samples_path = complex_dir / "samples.json"
    failures_path = complex_dir / "semantic_preservation_failures.json"

    samples_path.write_text(json.dumps(complexification["samples"], indent=2, sort_keys=True), encoding="utf-8")
    failures_path.write_text(
        json.dumps(complexification["semantic_preservation_failures"], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "samples": str(samples_path),
        "semantic_preservation_failures": str(failures_path),
    }


def _persist_dual_critic_artifacts(run_root: Path, adjudication: dict[str, Any]) -> dict[str, str]:
    critic_dir = run_root / "40_dual_critic_quality"
    critic_dir.mkdir(parents=True, exist_ok=True)

    decisions_path = critic_dir / "critic_decisions.json"
    rejections_path = critic_dir / "rejections.json"
    regenerations_path = critic_dir / "regenerations.json"

    decisions_path.write_text(json.dumps(adjudication["decisions"], indent=2, sort_keys=True), encoding="utf-8")
    rejections_path.write_text(
        json.dumps(adjudication["rejection_log"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    regenerations_path.write_text(
        json.dumps(adjudication["regeneration_log"], indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "critic_decisions": str(decisions_path),
        "rejections": str(rejections_path),
        "regenerations": str(regenerations_path),
    }


def run_pipeline(
    seed: int,
    model_ids: dict[str, str],
    domain_objective: str = "pilot-domain",
    artifact_root: str | Path = "artifacts/runs",
    taxonomy_config: dict[str, int] | None = None,
    complexification_config: dict[str, Any] | None = None,
    dual_critic_config: dict[str, Any] | None = None,
) -> dict[str, object]:
    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

    manifest = {
        "run_id": run_id,
        "seed": seed,
        "model_ids": model_ids,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
    }
    validate_manifest(manifest)

    stage_outputs: dict[str, Any] = {
        stage_name: {"status": "placeholder", "run_id": run_id} for stage_name in STAGE_NAMES
    }

    cfg = taxonomy_config or {}
    taxonomy = build_taxonomy(
        domain_objective=domain_objective,
        config=TaxonomyConfig(
            max_depth=int(cfg.get("max_depth", 2)),
            branching_factor=int(cfg.get("branching_factor", 2)),
        ),
    )

    run_root = Path(artifact_root) / run_id
    artifacts = _persist_taxonomy_artifacts(run_root=run_root, taxonomy=taxonomy)
    local_diversification = build_local_diversification(taxonomy=taxonomy)
    local_artifacts = _persist_local_diversification_artifacts(
        run_root=run_root, local_diversification=local_diversification
    )
    complex_cfg = complexification_config or {}
    complexification = apply_complexification(
        samples=local_diversification["instantiations"],
        complexify_fraction=float(complex_cfg.get("complexify_fraction", 0.5)),
        semantic_overlap_threshold=float(complex_cfg.get("semantic_overlap_threshold", 0.55)),
        strategy=str(complex_cfg.get("strategy", "append_reasoning")),
    )
    complex_artifacts = _persist_complexification_artifacts(
        run_root=run_root, complexification=complexification
    )
    adjudication = adjudicate_samples(
        samples=complexification["samples"],
        policy=dual_critic_config,
    )
    dual_critic_artifacts = _persist_dual_critic_artifacts(run_root=run_root, adjudication=adjudication)

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
    stage_outputs["stage_4_dual_critic_quality_verification"] = {
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

    return {"manifest": manifest, "stage_outputs": stage_outputs, "taxonomy": taxonomy}
