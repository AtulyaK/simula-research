from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from simula_research.complexification import apply_complexification
from simula_research.dataset_adapters import load_split_manifest
from simula_research.downstream_evaluation import build_paper_downstream_evaluation_plan
from simula_research.dual_critic import adjudicate_samples
from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline
from simula_research.run_artifact_store import FileSystemRunArtifactStore
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy
from simula_research.validators import validate_artifact_tree


class FileSystemRunArtifactStoreTests(unittest.TestCase):
    def test_writes_expected_paths_and_round_trip_json(self) -> None:
        taxonomy = build_taxonomy("pilot", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        comp = apply_complexification(samples=local["instantiations"])
        adj = adjudicate_samples(samples=comp["samples"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run-test"
            store = FileSystemRunArtifactStore(root)

            t_paths = store.persist_taxonomy(taxonomy)
            graph_path = Path(t_paths["taxonomy_graph"])
            self.assertEqual(graph_path.parent.parent, root)
            self.assertEqual(graph_path.parent.name, "10_taxonomy")

            l_paths = store.persist_local_diversification(local)
            self.assertEqual(Path(l_paths["instantiations"]).parent.name, "20_local_diversification")

            c_paths = store.persist_complexification(comp)
            self.assertEqual(Path(c_paths["samples"]).parent.name, "30_complexification")

            d_paths = store.persist_dual_critic(adj)
            self.assertEqual(Path(d_paths["critic_decisions"]).parent.name, "40_dual_critic_quality")

            loaded = json.loads(Path(t_paths["taxonomy_nodes"]).read_text(encoding="utf-8"))
            self.assertEqual(len(loaded), len(taxonomy["nodes"]))

    def test_persists_optional_decontamination_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run-test"
            paths = FileSystemRunArtifactStore(root).persist_curated_dataset(
                {
                    "accepted_samples": [{"task_id": "kept"}],
                    "decontamination_report": {
                        "protocol_version": "13gram_jaccard_v1",
                        "accepted_sample_count": 1,
                    },
                    "decontamination_rejections": [
                        {"sample_id": "removed", "reason": "test_set_contamination"}
                    ],
                }
            )

            self.assertTrue(Path(paths["decontamination_report"]).is_file())
            self.assertTrue(Path(paths["decontamination_rejections"]).is_file())
            self.assertEqual(
                json.loads(Path(paths["decontamination_report"]).read_text(encoding="utf-8"))[
                    "protocol_version"
                ],
                "13gram_jaccard_v1",
            )


class RunPipelineArtifactStoreFactoryTests(unittest.TestCase):
    def test_pipeline_persists_fixed_dataset_split_manifest_with_curated_dataset(self) -> None:
        split_manifest = load_split_manifest(
            Path(__file__).parents[1] / "configs" / "paper_dataset_splits.json"
        )
        downstream_plan = build_paper_downstream_evaluation_plan(
            split_manifest,
            dataset_sizes=[1000],
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 0, "branching_factor": 1},
                dataset_protocol_config={
                    "benchmark_split_manifest": split_manifest,
                    "task_schema_version": "0.1.0",
                },
                downstream_evaluation_plan=downstream_plan,
            )
            run_root = Path(tmp) / str(result["manifest"]["run_id"])
            persisted = json.loads(
                (run_root / "50_curated_dataset" / "dataset_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            evaluation_handoff = json.loads(
                (run_root / "60_evaluation" / "evaluation_handoff.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            persisted["dataset_protocol"]["benchmark_split_manifest"]["manifest_id"],
            "simula-paper-benchmark-splits",
        )
        self.assertEqual(
            result["manifest"]["run_config"]["dataset_protocol_config"]["task_schema_version"],
            "0.1.0",
        )
        self.assertEqual(
            result["manifest"]["run_config"]["downstream_evaluation_plan"]["seeds"],
            list(range(10)),
        )
        self.assertEqual(evaluation_handoff["downstream_evaluation"]["status"], "planned")

    def test_pipeline_rejects_invalid_dataset_split_manifest(self) -> None:
        with self.assertRaisesRegex(ValueError, "split manifest entry"):
            run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                dataset_protocol_config={
                    "benchmark_split_manifest": {
                        "schema_version": "0.1.0",
                        "splits": [{}],
                    }
                },
            )

    def test_pipeline_can_persist_opt_in_decontamination_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 0, "branching_factor": 1},
                local_diversification_config={"per_node_instantiation_count": 1},
                critic_sample_evaluator=lambda sample, critic_id: "accept",
                decontamination_reference_samples=[{"text": "held out reference"}],
            )

            run_root = Path(tmp) / str(result["manifest"]["run_id"])
            curated_dir = run_root / "50_curated_dataset"
            report = json.loads(
                (curated_dir / "decontamination_report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["protocol_version"], "13gram_jaccard_v1")
        self.assertEqual(
            result["stage_outputs"]["stage_5_evaluation_handoff"]["decontamination"][
                "reference_sample_count"
            ],
            1,
        )

    def test_run_pipeline_persists_documented_artifact_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 1},
            )

            run_root = Path(tmp) / str(result["manifest"]["run_id"])
            for stage_dir in (
                "00_spec",
                "10_taxonomy",
                "20_local_diversification",
                "30_complexification",
                "40_dual_critic_quality",
                "50_curated_dataset",
                "60_evaluation",
                "70_diagnostics",
            ):
                self.assertTrue((run_root / stage_dir).is_dir(), msg=stage_dir)

            persisted_manifest = json.loads(
                (run_root / "00_spec" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted_manifest, result["manifest"])

            persisted_run_config = json.loads(
                (run_root / "00_spec" / "run_config.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted_run_config["run_id"], result["manifest"]["run_id"])
            self.assertEqual(
                persisted_run_config["taxonomy_config"],
                {"max_depth": 1, "branching_factor": 1},
            )
            self.assertEqual(
                persisted_run_config["local_diversification_config"]["per_node_instantiation_count"],
                3,
            )
            self.assertEqual(
                persisted_run_config["complexification_config"]["complexify_fraction"],
                0.75,
            )
            self.assertEqual(
                persisted_run_config["dual_critic_config"]["disagreement_policy"],
                "reject",
            )
            persisted_integrity = json.loads(
                (run_root / "00_spec" / "artifact_integrity.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted_integrity["run_id"], result["manifest"]["run_id"])
            self.assertIn("10_taxonomy/taxonomy_nodes.json", persisted_integrity["files"])

            persisted_stage_outputs = json.loads(
                (run_root / "00_spec" / "stage_outputs.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted_stage_outputs["stage_0_domain_run_spec"]["status"], "completed")
            self.assertEqual(
                persisted_stage_outputs["stage_5_evaluation_handoff"]["status"],
                "ready_for_evaluation",
            )

            stage4 = result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
            accepted_samples = json.loads(
                (run_root / "50_curated_dataset" / "accepted_samples.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(accepted_samples), stage4["accepted_samples"])

            evaluation_handoff = json.loads(
                (run_root / "60_evaluation" / "evaluation_handoff.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evaluation_handoff["status"], "ready_for_evaluation")
            self.assertEqual(evaluation_handoff["metrics_status"], "not_computed_by_pipeline")

            diagnostics = json.loads(
                (run_root / "70_diagnostics" / "diagnostics_summary.json").read_text(encoding="utf-8")
            )
            stage4_rejections = json.loads(
                Path(stage4["stage4_artifacts"]["rejections"]).read_text(encoding="utf-8")
            )
            self.assertEqual(diagnostics["stage4_rejection_count"], len(stage4_rejections))
            self.assertEqual(diagnostics["semantic_preservation_failure_count"], 0)

    def test_run_config_records_effective_pipeline_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 4, "branching_factor": 3},
                local_diversification_config={
                    "per_node_instantiation_count": 5,
                    "overlap_rejection_threshold": 0.4,
                },
                complexification_config={
                    "complexify_fraction": 1.0,
                    "semantic_overlap_threshold": 0.2,
                    "strategy": "custom",
                },
                dual_critic_config={
                    "disagreement_policy": "accept",
                    "max_regenerations_per_sample": 4,
                },
                pipeline_config={
                    "global_diversification_enabled": False,
                    "local_diversification_enabled": False,
                    "complexification_enabled": False,
                    "dual_critic_enabled": False,
                    "single_critic_mode": "critic_b",
                },
            )
            run_root = Path(tmp) / str(result["manifest"]["run_id"])
            persisted = json.loads(
                (run_root / "00_spec" / "run_config.json").read_text(encoding="utf-8")
            )

        self.assertEqual(
            persisted["pipeline_config"],
            {
                "global_diversification_enabled": False,
                "local_diversification_enabled": False,
                "complexification_enabled": False,
                "dual_critic_enabled": False,
                "single_critic_mode": "critic_b",
            },
        )
        self.assertEqual(persisted["taxonomy_config"], {"max_depth": 0, "branching_factor": 1})
        self.assertEqual(
            persisted["local_diversification_config"]["per_node_instantiation_count"],
            1,
        )
        self.assertEqual(
            persisted["local_diversification_config"]["overlap_rejection_threshold"],
            0.4,
        )
        self.assertEqual(persisted["complexification_config"]["complexify_fraction"], 0.0)
        self.assertEqual(persisted["complexification_config"]["strategy"], "custom")
        self.assertEqual(persisted["dual_critic_config"]["disagreement_policy"], "accept")
        self.assertEqual(persisted["dual_critic_config"]["single_critic_mode"], "critic_b")

    def test_artifact_integrity_validation_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 1},
            )
            run_root = Path(tmp) / str(result["manifest"]["run_id"])
            samples_path = run_root / "30_complexification" / "samples.json"
            samples_path.write_text(
                samples_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            validation = validate_artifact_tree(run_root)

        self.assertFalse(validation["ok"])
        self.assertTrue(
            any(
                issue == "artifact_integrity.json: sha256 mismatch: 30_complexification/samples.json"
                for issue in validation["issues"]
            )
        )

    def test_pipeline_artifacts_validate_with_full_manifest_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 1},
                manifest_metadata={
                    "owner": "test",
                    "branch": "main",
                    "commit_hash": "abc123",
                    "baseline_or_ablation_tag": "B0",
                },
            )

            run_root = Path(tmp) / str(result["manifest"]["run_id"])
            validation = validate_artifact_tree(run_root)

        self.assertTrue(validation["ok"], validation["issues"])

    def test_custom_factory_receives_run_root_and_can_noop_disk(self) -> None:
        seen: list[Path] = []

        class RecordingStore:
            def __init__(self, run_root: Path) -> None:
                self.run_root = run_root
                seen.append(run_root)

            def persist_taxonomy(self, taxonomy: dict[str, Any]) -> dict[str, str]:
                return {"taxonomy_graph": str(self.run_root / "g.json"), "taxonomy_nodes": str(self.run_root / "n.json")}

            def persist_local_diversification(self, local_diversification: dict[str, Any]) -> dict[str, str]:
                return {"instantiations": str(self.run_root / "i.json"), "rejections": str(self.run_root / "r.json")}

            def persist_complexification(self, complexification: dict[str, Any]) -> dict[str, str]:
                return {"samples": str(self.run_root / "s.json"), "semantic_preservation_failures": str(self.run_root / "f.json")}

            def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
                return {
                    "critic_decisions": str(self.run_root / "d.json"),
                    "rejections": str(self.run_root / "rj.json"),
                    "regenerations": str(self.run_root / "rg.json"),
                }

        with tempfile.TemporaryDirectory() as tmp:
            run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                artifact_store_factory=lambda root: RecordingStore(root),
            )

        self.assertEqual(len(seen), 1)
        self.assertTrue(str(seen[0]).startswith(tmp))


if __name__ == "__main__":
    unittest.main()
