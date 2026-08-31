from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.validators import (
    REQUIRED_ARTIFACT_STAGES,
    validate_artifact_tree,
    validate_manifest_schema,
)


class ValidatorTests(unittest.TestCase):
    def test_required_artifact_stages_match_default_run_store_stage4_dir(self) -> None:
        """Stage 4 folder must match FileSystemRunArtifactStore (issue #33 / handoff drift fix)."""
        self.assertIn("40_dual_critic_quality", REQUIRED_ARTIFACT_STAGES)
        self.assertNotIn("40_dual_critic", REQUIRED_ARTIFACT_STAGES)

    def _valid_manifest(self, run_id: str = "run-20260430T190000Z-abcd1234") -> dict[str, object]:
        return {
            "run_id": run_id,
            "created_at_utc": "2026-04-30T19:00:00Z",
            "owner": "agent",
            "branch": "main",
            "commit_hash": "abc123def456",
            "artifact_schema_version": "v1",
            "domain_objective": "synthetic data generation",
            "seed": 7,
            "model_ids": {
                "generator": "gpt-4.1-mini",
                "critic_a": "gpt-4.1",
                "critic_b": "gpt-4.1",
            },
            "pipeline_config": {"max_nodes": 10},
            "protocol_version": "0.1.0",
            "baseline_or_ablation_tag": "B0",
        }

    def _write_valid_artifact_tree(self, run_root: Path) -> None:
        for stage_name in REQUIRED_ARTIFACT_STAGES:
            (run_root / stage_name).mkdir(parents=True, exist_ok=True)
        (run_root / "50_curated_dataset" / "accepted_samples.json").write_text("[]", encoding="utf-8")
        (run_root / "50_curated_dataset" / "dataset_manifest.json").write_text("{}", encoding="utf-8")
        (run_root / "60_evaluation" / "evaluation_handoff.json").write_text("{}", encoding="utf-8")
        (run_root / "70_diagnostics" / "diagnostics_summary.json").write_text("{}", encoding="utf-8")
        (run_root / "manifest.json").write_text(
            json.dumps(self._valid_manifest(run_root.name)),
            encoding="utf-8",
        )
        taxonomy_nodes = [
            {
                "taxonomy_node_id": "tax-root",
                "parent_taxonomy_node_id": None,
                "label": "pilot root",
                "depth": 0,
            },
            {
                "taxonomy_node_id": "tax-child",
                "parent_taxonomy_node_id": "tax-root",
                "label": "pilot child",
                "depth": 1,
            },
        ]
        (run_root / "10_taxonomy" / "taxonomy_nodes.json").write_text(
            json.dumps(taxonomy_nodes),
            encoding="utf-8",
        )
        (run_root / "10_taxonomy" / "taxonomy_graph.json").write_text(
            json.dumps(
                {
                    "domain_namespace": "pilot",
                    "root_taxonomy_node_id": "tax-root",
                    "edges": [
                        {
                            "parent_taxonomy_node_id": "tax-root",
                            "taxonomy_node_id": "tax-child",
                        }
                    ],
                    "generation_policy": {"max_depth": 1},
                }
            ),
            encoding="utf-8",
        )

        instantiations = [
            {
                "instantiation_id": "inst-accepted",
                "taxonomy_node_id": "tax-root",
                "meta_prompt_id": "mp-root",
                "lineage": {
                    "taxonomy_node_id": "tax-root",
                    "meta_prompt_id": "mp-root",
                    "instantiation_id": "inst-accepted",
                },
                "text": "accepted text",
            },
            {
                "instantiation_id": "inst-rejected",
                "taxonomy_node_id": "tax-child",
                "meta_prompt_id": "mp-child",
                "lineage": {
                    "taxonomy_node_id": "tax-child",
                    "meta_prompt_id": "mp-child",
                    "instantiation_id": "inst-rejected",
                },
                "text": "rejected text",
            },
        ]
        (run_root / "20_local_diversification" / "instantiations.json").write_text(
            json.dumps(instantiations),
            encoding="utf-8",
        )
        (run_root / "20_local_diversification" / "rejections.json").write_text("[]", encoding="utf-8")

        samples = [
            {
                **instantiation,
                "is_complexified": False,
                "complexity_source": "original",
            }
            for instantiation in instantiations
        ]
        (run_root / "30_complexification" / "samples.json").write_text(
            json.dumps(samples),
            encoding="utf-8",
        )
        (run_root / "30_complexification" / "semantic_preservation_failures.json").write_text(
            "[]",
            encoding="utf-8",
        )

        decisions = [
            {
                "instantiation_id": "inst-accepted",
                "taxonomy_node_id": "tax-root",
                "meta_prompt_id": "mp-root",
                "critic_a_decision": "accept",
                "critic_b_decision": "accept",
                "disagreement": False,
                "adjudication_policy": "reject",
                "quality_status": "accepted",
                "final_reason": "both_accept",
                "regeneration_count": 0,
                "review_status": "reviewed",
            },
            {
                "instantiation_id": "inst-rejected",
                "taxonomy_node_id": "tax-child",
                "meta_prompt_id": "mp-child",
                "critic_a_decision": "reject",
                "critic_b_decision": "reject",
                "disagreement": False,
                "adjudication_policy": "reject",
                "quality_status": "rejected",
                "final_reason": "both_reject",
                "regeneration_count": 0,
                "review_status": "reviewed",
            },
        ]
        (run_root / "40_dual_critic_quality" / "critic_decisions.json").write_text(
            json.dumps(decisions),
            encoding="utf-8",
        )
        (run_root / "40_dual_critic_quality" / "rejections.json").write_text(
            json.dumps(
                [
                    {
                        "instantiation_id": "inst-rejected",
                        "taxonomy_node_id": "tax-child",
                        "meta_prompt_id": "mp-child",
                        "reason": "both_reject",
                        "critic_a_decision": "reject",
                        "critic_b_decision": "reject",
                        "regeneration_count": 0,
                    }
                ]
            ),
            encoding="utf-8",
        )
        (run_root / "40_dual_critic_quality" / "regenerations.json").write_text(
            "[]",
            encoding="utf-8",
        )

    def test_manifest_validation_success(self) -> None:
        result = validate_manifest_schema(self._valid_manifest())
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "manifest")
        self.assertEqual(result["issues"], [])

    def test_manifest_validation_reports_missing_field(self) -> None:
        manifest = self._valid_manifest()
        manifest.pop("owner")
        result = validate_manifest_schema(manifest)
        self.assertFalse(result["ok"])
        self.assertIn("missing required field: owner", result["issues"])

    def test_manifest_validation_reports_incomplete_metadata(self) -> None:
        manifest = self._valid_manifest()
        manifest["created_at_utc"] = "not-a-timestamp"
        manifest["model_ids"] = {"generator": "g"}
        manifest["pipeline_config"] = {}

        result = validate_manifest_schema(manifest)

        self.assertFalse(result["ok"])
        self.assertIn("field created_at_utc must be an ISO-8601 timestamp", result["issues"])
        self.assertTrue(
            any("field model_ids missing required model roles" in issue for issue in result["issues"])
        )
        self.assertIn("field pipeline_config must be a non-empty object", result["issues"])

    def test_artifact_tree_validation_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-20260430T190000Z-abcd1234"
            self._write_valid_artifact_tree(run_root)

            result = validate_artifact_tree(run_root)

        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "artifacts")
        self.assertEqual(result["issues"], [])

    def test_artifact_tree_validation_reports_missing_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-2"
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / REQUIRED_ARTIFACT_STAGES[0]).mkdir()

            result = validate_artifact_tree(run_root)

        self.assertFalse(result["ok"])
        self.assertGreater(len(result["issues"]), 0)
        self.assertTrue(
            any("missing required artifact stage directory" in issue for issue in result["issues"])
        )

    def test_artifact_tree_validation_reports_graph_cycle_and_edge_parent_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-20260430T190000Z-abcd1234"
            self._write_valid_artifact_tree(run_root)
            graph_path = run_root / "10_taxonomy" / "taxonomy_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["edges"].append(
                {
                    "parent_taxonomy_node_id": "tax-child",
                    "taxonomy_node_id": "tax-root",
                }
            )
            graph_path.write_text(json.dumps(graph), encoding="utf-8")

            result = validate_artifact_tree(run_root)

        self.assertFalse(result["ok"])
        self.assertTrue(any("taxonomy graph must be acyclic" in issue for issue in result["issues"]))
        self.assertTrue(
            any("does not match child parent" in issue for issue in result["issues"])
        )

    def test_artifact_tree_validation_reports_lineage_and_cross_stage_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-20260430T190000Z-abcd1234"
            self._write_valid_artifact_tree(run_root)
            instantiations_path = run_root / "20_local_diversification" / "instantiations.json"
            instantiations = json.loads(instantiations_path.read_text(encoding="utf-8"))
            instantiations[0]["lineage"]["meta_prompt_id"] = "mp-drift"
            instantiations_path.write_text(json.dumps(instantiations), encoding="utf-8")

            samples_path = run_root / "30_complexification" / "samples.json"
            samples = json.loads(samples_path.read_text(encoding="utf-8"))
            samples.pop()
            samples_path.write_text(json.dumps(samples), encoding="utf-8")

            result = validate_artifact_tree(run_root)

        self.assertFalse(result["ok"])
        self.assertTrue(any("lineage.meta_prompt_id must match" in issue for issue in result["issues"]))
        self.assertTrue(any("instantiation_id sets must match" in issue for issue in result["issues"]))

    def test_artifact_tree_validation_reports_accepted_rejected_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-20260430T190000Z-abcd1234"
            self._write_valid_artifact_tree(run_root)
            rejections_path = run_root / "40_dual_critic_quality" / "rejections.json"
            rejections = json.loads(rejections_path.read_text(encoding="utf-8"))
            rejections.append(
                {
                    "instantiation_id": "inst-accepted",
                    "taxonomy_node_id": "tax-root",
                    "meta_prompt_id": "mp-root",
                    "reason": "drift",
                    "critic_a_decision": "accept",
                    "critic_b_decision": "accept",
                    "regeneration_count": 0,
                }
            )
            rejections_path.write_text(json.dumps(rejections), encoding="utf-8")

            result = validate_artifact_tree(run_root)

        self.assertFalse(result["ok"])
        self.assertTrue(any("accepted decision" in issue for issue in result["issues"]))
        self.assertTrue(any("rejected decision IDs must match" in issue for issue in result["issues"]))

    def test_end_to_end_cli_like_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-20260430T190000Z-abcd1234"
            self._write_valid_artifact_tree(run_root)

            manifest_path = run_root / "manifest.json"
            manifest_result = validate_manifest_schema(json.loads(manifest_path.read_text("utf-8")))
            artifact_result = validate_artifact_tree(run_root)

        self.assertTrue(manifest_result["ok"])
        self.assertTrue(artifact_result["ok"])


if __name__ == "__main__":
    unittest.main()
