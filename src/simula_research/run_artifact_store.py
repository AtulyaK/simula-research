from __future__ import annotations

import json
from hashlib import sha256
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

    def persist_downstream_evaluation_results(
        self,
        evaluation_results: dict[str, Any],
    ) -> dict[str, str]:
        """Write benchmark result artifacts produced from the Stage 5 plan."""


class FileSystemRunArtifactStore:
    """Default on-disk layout matching the historical pipeline paths (Issue #28)."""

    def __init__(self, run_root: Path) -> None:
        self._run_root = run_root

    def persist_run_spec(
        self,
        manifest: dict[str, Any],
        *,
        stage_outputs: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        spec_dir = self._run_root / "00_spec"
        spec_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = spec_dir / "manifest.json"
        run_config_path = spec_dir / "run_config.json"
        stage_outputs_path = spec_dir / "stage_outputs.json"
        integrity_path = spec_dir / "artifact_integrity.json"

        run_config: dict[str, Any] = {
            "run_id": manifest["run_id"],
            "seed": manifest["seed"],
            "domain_objective": manifest["domain_objective"],
            "model_ids": manifest["model_ids"],
            "pipeline_config": manifest.get("pipeline_config", {}),
        }
        resolved_run_config = manifest.get("run_config")
        if isinstance(resolved_run_config, dict):
            run_config.update(resolved_run_config)
        if "provider_runtime" in manifest:
            run_config["provider_runtime"] = manifest["provider_runtime"]

        manifest_path.write_text(_dump_json(manifest), encoding="utf-8")
        run_config_path.write_text(_dump_json(run_config), encoding="utf-8")
        artifacts = {
            "manifest": str(manifest_path),
            "run_config": str(run_config_path),
        }
        if stage_outputs is not None:
            stage_outputs_path.write_text(_dump_json(stage_outputs), encoding="utf-8")
            artifacts["stage_outputs"] = str(stage_outputs_path)
        integrity = {
            "schema_version": "0.1.0",
            "run_id": manifest["run_id"],
            "algorithm": "sha256",
            "files": self._build_integrity_records(integrity_path),
        }
        integrity_path.write_text(_dump_json(integrity), encoding="utf-8")
        artifacts["artifact_integrity"] = str(integrity_path)
        return artifacts

    def _build_integrity_records(self, integrity_path: Path) -> dict[str, dict[str, int | str]]:
        records: dict[str, dict[str, int | str]] = {}
        for path in sorted(self._run_root.rglob("*")):
            if not path.is_file() or path == integrity_path:
                continue
            relative_path = path.relative_to(self._run_root).as_posix()
            digest = sha256()
            size_bytes = 0
            with path.open("rb") as file_handle:
                for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size_bytes += len(chunk)
            records[relative_path] = {
                "sha256": digest.hexdigest(),
                "size_bytes": size_bytes,
            }
        return records

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
        judgments_path = complex_dir / "pairwise_judgments.json"
        batchwise_path = complex_dir / "batchwise_complexity.json"

        samples_path.write_text(_dump_json(complexification["samples"]), encoding="utf-8")
        failures_path.write_text(
            _dump_json(complexification["semantic_preservation_failures"]),
            encoding="utf-8",
        )
        judgments_path.write_text(
            _dump_json(complexification.get("pairwise_judgments", [])),
            encoding="utf-8",
        )

        artifacts = {
            "samples": str(samples_path),
            "semantic_preservation_failures": str(failures_path),
            "pairwise_judgments": str(judgments_path),
        }
        if "batchwise_complexity" in complexification:
            batchwise_path.write_text(
                _dump_json(complexification["batchwise_complexity"]),
                encoding="utf-8",
            )
            artifacts["batchwise_complexity"] = str(batchwise_path)
        return artifacts

    def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
        critic_dir = self._run_root / "40_dual_critic_quality"
        critic_dir.mkdir(parents=True, exist_ok=True)

        decisions_path = critic_dir / "critic_decisions.json"
        rejections_path = critic_dir / "rejections.json"
        regenerations_path = critic_dir / "regenerations.json"
        provider_runtime_path = critic_dir / "provider_runtime.json"
        nim_event_log_path = critic_dir / "nim_event_log.json"

        decisions_path.write_text(_dump_json(adjudication["decisions"]), encoding="utf-8")
        rejections_path.write_text(_dump_json(adjudication["rejection_log"]), encoding="utf-8")
        regenerations_path.write_text(_dump_json(adjudication["regeneration_log"]), encoding="utf-8")

        artifacts: dict[str, str] = {
            "critic_decisions": str(decisions_path),
            "rejections": str(rejections_path),
            "regenerations": str(regenerations_path),
        }
        if "provider_runtime" in adjudication:
            provider_runtime_path.write_text(_dump_json(adjudication["provider_runtime"]), encoding="utf-8")
            artifacts["provider_runtime"] = str(provider_runtime_path)
        if "nim_event_log" in adjudication:
            nim_event_log_path.write_text(_dump_json(adjudication["nim_event_log"]), encoding="utf-8")
            artifacts["nim_event_log"] = str(nim_event_log_path)
        return artifacts

    def persist_curated_dataset(self, curated_dataset: dict[str, Any]) -> dict[str, str]:
        curated_dir = self._run_root / "50_curated_dataset"
        curated_dir.mkdir(parents=True, exist_ok=True)

        accepted_samples_path = curated_dir / "accepted_samples.json"
        manifest_path = curated_dir / "dataset_manifest.json"
        decontamination_report_path = curated_dir / "decontamination_report.json"
        decontamination_rejections_path = curated_dir / "decontamination_rejections.json"

        accepted_samples_path.write_text(
            _dump_json(curated_dataset["accepted_samples"]),
            encoding="utf-8",
        )
        manifest_path.write_text(_dump_json(curated_dataset), encoding="utf-8")

        artifacts = {
            "accepted_samples": str(accepted_samples_path),
            "dataset_manifest": str(manifest_path),
        }
        if "decontamination_report" in curated_dataset:
            decontamination_report_path.write_text(
                _dump_json(curated_dataset["decontamination_report"]),
                encoding="utf-8",
            )
            artifacts["decontamination_report"] = str(decontamination_report_path)
        if "decontamination_rejections" in curated_dataset:
            decontamination_rejections_path.write_text(
                _dump_json(curated_dataset["decontamination_rejections"]),
                encoding="utf-8",
            )
            artifacts["decontamination_rejections"] = str(decontamination_rejections_path)
        return artifacts

    def persist_evaluation_handoff(self, evaluation_handoff: dict[str, Any]) -> dict[str, str]:
        evaluation_dir = self._run_root / "60_evaluation"
        evaluation_dir.mkdir(parents=True, exist_ok=True)

        handoff_path = evaluation_dir / "evaluation_handoff.json"
        handoff_path.write_text(_dump_json(evaluation_handoff), encoding="utf-8")

        return {"evaluation_handoff": str(handoff_path)}

    def persist_downstream_evaluation_results(
        self,
        evaluation_results: dict[str, Any],
    ) -> dict[str, str]:
        evaluation_dir = self._run_root / "60_evaluation"
        evaluation_dir.mkdir(parents=True, exist_ok=True)

        results_path = evaluation_dir / "downstream_evaluation_results.json"
        results_path.write_text(_dump_json(evaluation_results), encoding="utf-8")
        return {"downstream_evaluation_results": str(results_path)}

    def persist_diagnostics(self, diagnostics: dict[str, Any]) -> dict[str, str]:
        diagnostics_dir = self._run_root / "70_diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)

        summary_path = diagnostics_dir / "diagnostics_summary.json"
        summary_path.write_text(_dump_json(diagnostics), encoding="utf-8")

        return {"diagnostics_summary": str(summary_path)}
