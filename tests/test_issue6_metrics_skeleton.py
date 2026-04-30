from __future__ import annotations

import unittest

from simula_research.evaluation_metrics import (
    build_gate_report,
    compute_complexity_metrics,
    compute_coverage_metrics,
    compute_quality_metrics,
)


class Issue6MetricsSkeletonTests(unittest.TestCase):
    def test_coverage_metrics_include_ratio_depth_profile_and_balance(self) -> None:
        eligible_nodes = [
            {"taxonomy_node_id": "root", "depth": 0},
            {"taxonomy_node_id": "a", "depth": 1},
            {"taxonomy_node_id": "b", "depth": 1},
        ]
        accepted_samples = [
            {"taxonomy_node_id": "root"},
            {"taxonomy_node_id": "a"},
            {"taxonomy_node_id": "a"},
        ]

        result = compute_coverage_metrics(eligible_nodes=eligible_nodes, accepted_samples=accepted_samples)

        self.assertEqual(result["eligible_nodes"], 3)
        self.assertEqual(result["covered_nodes"], 2)
        self.assertAlmostEqual(result["node_coverage_ratio"], 2 / 3)
        self.assertEqual(result["depth_coverage_profile"], {"0": 1.0, "1": 0.5})
        self.assertGreaterEqual(result["coverage_balance"], 0.0)
        self.assertLessEqual(result["coverage_balance"], 1.0)

    def test_complexity_metrics_include_calibrated_distribution_and_shift(self) -> None:
        result = compute_complexity_metrics(
            run_complexity_scores=[0.6, 0.8, 0.9],
            baseline_complexity_scores=[0.3, 0.4, 0.5],
            complexification_pairs=[
                {"is_successful": True},
                {"is_successful": False},
                {"is_successful": True},
            ],
        )

        self.assertIn("calibrated_score_distribution", result)
        self.assertEqual(
            set(result["calibrated_score_distribution"].keys()),
            {"p25", "p50", "p75"},
        )
        self.assertGreater(result["complexity_shift"], 0.0)
        self.assertAlmostEqual(result["complexification_precision"], 2 / 3)

    def test_quality_metrics_return_explicit_issue5_stubs_when_missing(self) -> None:
        result = compute_quality_metrics(issue5_outputs=None)

        self.assertIsNone(result["acceptance_rate"])
        self.assertIsNone(result["critic_agreement"])
        self.assertIsNone(result["disagreement_rate"])
        self.assertIsNone(result["regen_burden"])
        self.assertTrue(result["requires_issue_5_outputs"])
        self.assertGreater(len(result["todo_after_issue_5"]), 0)

    def test_gate_report_schema_maps_thresholds_to_gate_status(self) -> None:
        coverage = {
            "node_coverage_ratio": 0.81,
            "depth_coverage_profile": {"0": 1.0, "1": 0.65},
            "coverage_balance": 0.7,
        }
        complexity = {
            "calibrated_score_distribution": {"p25": 0.2, "p50": 0.4, "p75": 0.8},
            "complexity_shift": 0.1,
            "complexification_precision": 0.72,
        }
        quality = {
            "acceptance_rate": 0.52,
            "critic_agreement": 0.77,
            "disagreement_rate": 0.23,
            "regen_burden": 0.95,
            "requires_issue_5_outputs": False,
            "todo_after_issue_5": [],
        }

        report = build_gate_report(
            run_identity={"run_id": "run-1", "seed": 7, "branch": "feature/test", "commit_hash": "abc"},
            protocol={
                "domain_objective": "pilot-domain",
                "taxonomy_policy": "default",
                "complexification_policy": "default",
                "critic_policy": "dual-critic",
            },
            coverage_metrics=coverage,
            complexity_metrics=complexity,
            quality_metrics=quality,
            notes=["bootstrapped test"],
        )

        self.assertIn("gate_decision", report)
        self.assertEqual(report["gate_decision"]["coverage.node_coverage_ratio"]["status"], "pass")
        self.assertEqual(report["gate_decision"]["coverage.min_depth_coverage"]["status"], "pass")
        self.assertEqual(report["gate_decision"]["complexity.complexification_precision"]["status"], "pass")
        self.assertEqual(report["gate_decision"]["quality.critic_agreement"]["status"], "pass")
        self.assertEqual(report["gate_decision"]["overall_status"], "pass")


if __name__ == "__main__":
    unittest.main()
