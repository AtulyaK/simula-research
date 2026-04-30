from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.dual_critic import adjudicate_samples
from simula_research.evaluation_metrics import compute_quality_metrics
from simula_research.pipeline import run_pipeline


class Issue5DualCriticAdjudicationTests(unittest.TestCase):
    def test_adjudication_records_independent_critic_decisions(self) -> None:
        samples = [
            {
                "instantiation_id": "inst-1",
                "taxonomy_node_id": "tax-1",
                "meta_prompt_id": "mp-1",
                "text": "sample one",
            },
            {
                "instantiation_id": "inst-2",
                "taxonomy_node_id": "tax-2",
                "meta_prompt_id": "mp-2",
                "text": "sample two",
            },
        ]
        result = adjudicate_samples(samples=samples, policy={"disagreement_policy": "reject"})
        self.assertEqual(len(result["decisions"]), 2)
        for decision in result["decisions"]:
            self.assertIn(decision["critic_a_decision"], {"accept", "reject"})
            self.assertIn(decision["critic_b_decision"], {"accept", "reject"})
            self.assertEqual(decision["review_status"], "reviewed")

    def test_disagreement_policy_regenerate_is_deterministic(self) -> None:
        sample = {
            "instantiation_id": "inst-disagree",
            "taxonomy_node_id": "tax-9",
            "meta_prompt_id": "mp-9",
            "text": "abc",
        }
        first = adjudicate_samples(
            samples=[sample],
            policy={"disagreement_policy": "regenerate", "max_regenerations_per_sample": 1},
        )
        second = adjudicate_samples(
            samples=[sample],
            policy={"disagreement_policy": "regenerate", "max_regenerations_per_sample": 1},
        )
        self.assertEqual(first["decisions"], second["decisions"])
        self.assertEqual(first["regeneration_log"], second["regeneration_log"])
        self.assertEqual(first["rejection_log"], second["rejection_log"])

    def test_pipeline_persists_machine_readable_stage4_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=31,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="insurance claims triage",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                dual_critic_config={"disagreement_policy": "regenerate", "max_regenerations_per_sample": 1},
            )

            stage4 = result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
            self.assertEqual(stage4["status"], "completed")
            self.assertIn("stage4_artifacts", stage4)

            decisions_path = Path(stage4["stage4_artifacts"]["critic_decisions"])
            rejection_path = Path(stage4["stage4_artifacts"]["rejections"])
            regeneration_path = Path(stage4["stage4_artifacts"]["regenerations"])
            self.assertTrue(decisions_path.exists())
            self.assertTrue(rejection_path.exists())
            self.assertTrue(regeneration_path.exists())

            decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
            rejections = json.loads(rejection_path.read_text(encoding="utf-8"))
            regenerations = json.loads(regeneration_path.read_text(encoding="utf-8"))
            self.assertGreater(len(decisions), 0)
            self.assertIsInstance(rejections, list)
            self.assertIsInstance(regenerations, list)

            reviewed = len(decisions)
            agreements = sum(
                1
                for entry in decisions
                if entry["critic_a_decision"] == entry["critic_b_decision"]
            )
            self.assertEqual(stage4["reviewed_samples"], reviewed)
            self.assertEqual(stage4["agreements"], agreements)
            self.assertEqual(stage4["disagreements"], reviewed - agreements)

            quality_metrics = compute_quality_metrics(issue5_outputs=stage4)
            self.assertFalse(quality_metrics["requires_issue_5_outputs"])
            self.assertGreaterEqual(quality_metrics["acceptance_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
