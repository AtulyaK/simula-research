from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.complexification import apply_complexification
from simula_research.pipeline import run_pipeline


class Issue4ComplexificationTest(unittest.TestCase):
    def test_complexification_applies_fraction_and_preserves_lineage(self) -> None:
        samples = [
            {
                "instantiation_id": "inst-1",
                "taxonomy_node_id": "tax-a",
                "meta_prompt_id": "mp-a",
                "lineage": {
                    "taxonomy_node_id": "tax-a",
                    "meta_prompt_id": "mp-a",
                    "instantiation_id": "inst-1",
                },
                "text": "Classify account takeover incidents with clear evidence.",
            },
            {
                "instantiation_id": "inst-2",
                "taxonomy_node_id": "tax-b",
                "meta_prompt_id": "mp-b",
                "lineage": {
                    "taxonomy_node_id": "tax-b",
                    "meta_prompt_id": "mp-b",
                    "instantiation_id": "inst-2",
                },
                "text": "Escalate suspicious card transaction patterns.",
            },
            {
                "instantiation_id": "inst-3",
                "taxonomy_node_id": "tax-c",
                "meta_prompt_id": "mp-c",
                "lineage": {
                    "taxonomy_node_id": "tax-c",
                    "meta_prompt_id": "mp-c",
                    "instantiation_id": "inst-3",
                },
                "text": "Audit policy exceptions for payment disputes.",
            },
            {
                "instantiation_id": "inst-4",
                "taxonomy_node_id": "tax-d",
                "meta_prompt_id": "mp-d",
                "lineage": {
                    "taxonomy_node_id": "tax-d",
                    "meta_prompt_id": "mp-d",
                    "instantiation_id": "inst-4",
                },
                "text": "Review merchant onboarding for compliance gaps.",
            },
        ]
        result = apply_complexification(samples=samples, complexify_fraction=0.5)

        self.assertEqual(len(result["samples"]), 4)
        complexified = [sample for sample in result["samples"] if sample["is_complexified"]]
        self.assertEqual(len(complexified), 2)
        for sample in result["samples"]:
            self.assertEqual(sample["lineage"]["taxonomy_node_id"], sample["taxonomy_node_id"])
            self.assertEqual(sample["lineage"]["meta_prompt_id"], sample["meta_prompt_id"])
            self.assertIn("complexity_source", sample)
        self.assertEqual(result["complexification_policy"]["strategy"], "append_reasoning")

    def test_semantic_preservation_failures_are_recorded_for_analysis(self) -> None:
        samples = [
            {
                "instantiation_id": "inst-1",
                "taxonomy_node_id": "tax-a",
                "meta_prompt_id": "mp-a",
                "lineage": {
                    "taxonomy_node_id": "tax-a",
                    "meta_prompt_id": "mp-a",
                    "instantiation_id": "inst-1",
                },
                "text": "Resolve abnormal payroll transfer requests.",
            }
        ]
        result = apply_complexification(
            samples=samples,
            complexify_fraction=1.0,
            semantic_overlap_threshold=0.6,
            strategy="semantic_drift_probe",
        )

        self.assertEqual(len(result["semantic_preservation_failures"]), 1)
        self.assertFalse(result["samples"][0]["is_complexified"])
        self.assertEqual(
            result["samples"][0]["complexity_source"],
            "fallback_original_due_to_semantic_failure",
        )
        self.assertEqual(
            result["semantic_preservation_failures"][0]["taxonomy_node_id"],
            "tax-a",
        )

    def test_pipeline_stage_3_persists_complexification_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=13,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="payments disputes",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 1, "branching_factor": 1},
                complexification_config={
                    "complexify_fraction": 1.0,
                    "semantic_overlap_threshold": 0.6,
                    "strategy": "semantic_drift_probe",
                },
            )
            stage_3 = result["stage_outputs"]["stage_3_complexification"]
            self.assertEqual(stage_3["status"], "completed")
            self.assertIn("complexification_artifacts", stage_3)
            failures_path = Path(stage_3["complexification_artifacts"]["semantic_preservation_failures"])
            failures_payload = json.loads(failures_path.read_text(encoding="utf-8"))
            self.assertGreater(len(failures_payload), 0)


if __name__ == "__main__":
    unittest.main()
