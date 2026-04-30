from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

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


def run_pipeline(
    seed: int,
    model_ids: dict[str, str],
    domain_objective: str = "pilot-domain",
    artifact_root: str | Path = "artifacts/runs",
    taxonomy_config: dict[str, int] | None = None,
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

    return {"manifest": manifest, "stage_outputs": stage_outputs, "taxonomy": taxonomy}
