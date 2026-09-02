from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline


class Issue3LocalDiversificationTest(unittest.TestCase):
    def test_local_diversification_produces_traceable_instantiations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=21,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="fraud detection workflow",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
            )

            stage_output = result["stage_outputs"]["stage_2_local_diversification"]
            self.assertEqual(stage_output["status"], "completed")
            self.assertTrue(stage_output["anti_collapse_checks"]["executed"])

            instantiations_path = Path(stage_output["local_diversification_artifacts"]["instantiations"])
            payload = json.loads(instantiations_path.read_text(encoding="utf-8"))
            self.assertGreater(len(payload), 0)

            for instantiation in payload:
                self.assertEqual(
                    instantiation["lineage"]["taxonomy_node_id"], instantiation["taxonomy_node_id"]
                )
                self.assertEqual(instantiation["lineage"]["meta_prompt_id"], instantiation["meta_prompt_id"])
                self.assertIn("instantiation_id", instantiation)

    def test_low_diversity_candidates_are_rejected_and_logged(self) -> None:
        taxonomy = {
            "domain_namespace": "customer-support",
            "root_taxonomy_node_id": "tax-root",
            "nodes": [
                {
                    "taxonomy_node_id": "tax-root",
                    "parent_taxonomy_node_id": None,
                    "label": "root support",
                    "depth": 0,
                }
            ],
            "edges": [],
            "generation_policy": {"max_depth": 0, "branching_factor": 1},
        }
        result = build_local_diversification(
            taxonomy=taxonomy,
            per_node_instantiation_count=4,
            overlap_rejection_threshold=0.8,
        )
        self.assertGreater(len(result["rejections"]), 0)
        rejection = result["rejections"][0]
        self.assertEqual(rejection["reason"], "low_diversity")
        self.assertEqual(rejection["taxonomy_node_id"], "tax-root")
        self.assertIn("meta_prompt_id", rejection)
        self.assertIn("candidate_instantiation_id", rejection)

    def test_compatible_node_mixes_preserve_all_node_lineage(self) -> None:
        taxonomy = {
            "domain_namespace": "customer-support",
            "root_taxonomy_node_id": "tax-root",
            "nodes": [
                {
                    "taxonomy_node_id": "tax-root",
                    "parent_taxonomy_node_id": None,
                    "label": "root support",
                    "depth": 0,
                },
                {
                    "taxonomy_node_id": "tax-a",
                    "parent_taxonomy_node_id": "tax-root",
                    "label": "routing",
                    "depth": 1,
                },
                {
                    "taxonomy_node_id": "tax-b",
                    "parent_taxonomy_node_id": "tax-root",
                    "label": "resolution",
                    "depth": 1,
                },
            ],
            "edges": [
                {"parent_taxonomy_node_id": "tax-root", "taxonomy_node_id": "tax-a"},
                {"parent_taxonomy_node_id": "tax-root", "taxonomy_node_id": "tax-b"},
            ],
            "generation_policy": {"max_depth": 1, "branching_factor": 2},
        }

        result = build_local_diversification(
            taxonomy=taxonomy,
            per_node_instantiation_count=1,
            node_mix_size=2,
        )

        mixed = [
            item
            for item in result["instantiations"]
            if "compatible_taxonomy_node_ids" in item
        ]
        self.assertEqual(len(mixed), 1)
        self.assertEqual(mixed[0]["compatible_taxonomy_node_ids"], ["tax-a", "tax-b"])
        self.assertEqual(
            mixed[0]["lineage"]["compatible_taxonomy_node_ids"],
            ["tax-a", "tax-b"],
        )


if __name__ == "__main__":
    unittest.main()
