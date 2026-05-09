from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


def _dump_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


class RunArtifactStore(Protocol):
    """Persist stage payloads under a single run root (see docs/reproducibility-ops.md)."""

    def persist_taxonomy(self, taxonomy: dict[str, Any]) -> dict[str, str]:
        """Write Stage 1 artifacts; return logical paths (string paths) for stage_outputs."""

    def persist_local_diversification(self, local_diversification: dict[str, Any]) -> dict[str, str]:
        """Write Stage 2 artifacts."""

    def persist_complexification(self, complexification: dict[str, Any]) -> dict[str, str]:
        """Write Stage 3 artifacts."""

    def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
        """Write Stage 4 artifacts."""


class FileSystemRunArtifactStore:
    """Default on-disk layout matching the historical pipeline paths (Issue #28)."""

    def __init__(self, run_root: Path) -> None:
        self._run_root = run_root

    def persist_taxonomy(self, taxonomy: dict[str, Any]) -> dict[str, str]:
        taxonomy_dir = self._run_root / "10_taxonomy"
        taxonomy_dir.mkdir(parents=True, exist_ok=True)

        graph_path = taxonomy_dir / "taxonomy_graph.json"
        nodes_path = taxonomy_dir / "taxonomy_nodes.json"

        graph_path.write_text(
            _dump_json(
                {
                    "domain_namespace": taxonomy["domain_namespace"],
                    "root_taxonomy_node_id": taxonomy["root_taxonomy_node_id"],
                    "edges": taxonomy["edges"],
                    "generation_policy": taxonomy["generation_policy"],
                }
            ),
            encoding="utf-8",
        )
        nodes_path.write_text(_dump_json(taxonomy["nodes"]), encoding="utf-8")

        return {
            "taxonomy_graph": str(graph_path),
            "taxonomy_nodes": str(nodes_path),
        }

    def persist_local_diversification(self, local_diversification: dict[str, Any]) -> dict[str, str]:
        local_dir = self._run_root / "20_local_diversification"
        local_dir.mkdir(parents=True, exist_ok=True)

        instantiations_path = local_dir / "instantiations.json"
        rejections_path = local_dir / "rejections.json"

        instantiations_path.write_text(
            _dump_json(local_diversification["instantiations"]),
            encoding="utf-8",
        )
        rejections_path.write_text(
            _dump_json(local_diversification["rejections"]),
            encoding="utf-8",
        )

        return {
            "instantiations": str(instantiations_path),
            "rejections": str(rejections_path),
        }

    def persist_complexification(self, complexification: dict[str, Any]) -> dict[str, str]:
        complex_dir = self._run_root / "30_complexification"
        complex_dir.mkdir(parents=True, exist_ok=True)

        samples_path = complex_dir / "samples.json"
        failures_path = complex_dir / "semantic_preservation_failures.json"

        samples_path.write_text(_dump_json(complexification["samples"]), encoding="utf-8")
        failures_path.write_text(
            _dump_json(complexification["semantic_preservation_failures"]),
            encoding="utf-8",
        )

        return {
            "samples": str(samples_path),
            "semantic_preservation_failures": str(failures_path),
        }

    def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
        critic_dir = self._run_root / "40_dual_critic_quality"
        critic_dir.mkdir(parents=True, exist_ok=True)

        decisions_path = critic_dir / "critic_decisions.json"
        rejections_path = critic_dir / "rejections.json"
        regenerations_path = critic_dir / "regenerations.json"

        decisions_path.write_text(_dump_json(adjudication["decisions"]), encoding="utf-8")
        rejections_path.write_text(_dump_json(adjudication["rejection_log"]), encoding="utf-8")
        regenerations_path.write_text(_dump_json(adjudication["regeneration_log"]), encoding="utf-8")

        return {
            "critic_decisions": str(decisions_path),
            "rejections": str(rejections_path),
            "regenerations": str(regenerations_path),
        }
