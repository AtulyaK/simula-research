from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from simula_research.issue7_execution_reporting import execute_issue7_matrix


class Issue7ExecutionReportingTests(unittest.TestCase):
    @staticmethod
    def _complexity_judgment_provider(
        complexified_sample: dict[str, object],
        baseline_sample: dict[str, object],
    ) -> list[dict[str, object]]:
        return [
            {
                "winner": "complexified",
                "complexified_score": 0.8,
                "baseline_score": 0.4,
            }
            for _ in range(5)
        ]

    def test_execute_matrix_persists_run_reports_gate_reports_and_comparison_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="feature/issue-7-execute-b0-a1-a4",
                commit_hash="deadbeef",
            )

            run_reports = output["run_reports"]
            self.assertEqual(set(run_reports.keys()), {"B0", "A1", "A4"})

            for preset_id in ("B0", "A1", "A4"):
                per_run = run_reports[preset_id]
                self.assertIn("run_id", per_run["run_identity"])
                self.assertEqual(per_run["run_identity"]["branch"], "feature/issue-7-execute-b0-a1-a4")
                self.assertEqual(per_run["run_identity"]["commit_hash"], "deadbeef")
                self.assertEqual(per_run["protocol"]["baseline_or_ablation_tag"], preset_id)
                self.assertIn("taxonomy_eligibility_policy", per_run["protocol"])
                self.assertIn("complexity_judgment_protocol", per_run["protocol"])
                self.assertIn("critic_adjudication_config", per_run["protocol"])
                self.assertIn("failure_analysis", per_run)

                run_report_path = Path(per_run["artifacts"]["run_report"])
                gate_report_path = Path(per_run["artifacts"]["gate_report"])
                manifest_path = Path(per_run["artifacts"]["manifest"])
                self.assertTrue(run_report_path.exists())
                self.assertTrue(gate_report_path.exists())
                self.assertTrue(manifest_path.exists())

                persisted_gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
                self.assertIn("gate_decision", persisted_gate_report)
                self.assertIn("overall_status", persisted_gate_report["gate_decision"])

            comparison_tables_path = Path(output["comparison_tables_path"])
            self.assertTrue(comparison_tables_path.exists())
            comparison_tables = json.loads(comparison_tables_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(comparison_tables.keys()),
                {"coverage_comparison", "complexity_comparison", "quality_comparison", "gate_comparison"},
            )
            self.assertEqual(len(comparison_tables["coverage_comparison"]), 3)

    def test_dual_critic_agreement_is_reported_and_single_critic_is_not_evaluable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="track-d-gate-remediation",
                commit_hash="deadbeef",
            )

            for preset_id in ("B0", "A1"):
                gates = output["run_reports"][preset_id]["gate_report"]["gate_decision"]
                self.assertIn(gates["quality.critic_agreement"]["status"], {"pass", "fail"})
                self.assertIsNotNone(gates["quality.critic_agreement"]["actual"])

            single_critic_gates = output["run_reports"]["A4"]["gate_report"]["gate_decision"]
            self.assertEqual(single_critic_gates["quality.critic_agreement"]["status"], "todo")
            self.assertIsNone(single_critic_gates["quality.critic_agreement"]["actual"])

    def test_milestone1_a1_complexification_precision_is_not_evaluable_without_pairwise_judgments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="milestone1-a1-complexity-gate",
                commit_hash="deadbeef",
            )
            gates = output["run_reports"]["A1"]["gate_report"]["gate_decision"]
            complexity_gate = gates["complexity.complexification_precision"]
            self.assertEqual(complexity_gate["status"], "not_evaluable")
            self.assertIsNone(complexity_gate["actual"])
            self.assertEqual(
                complexity_gate["not_evaluable_reason"],
                "missing_pairwise_complexity_judgments",
            )

    def test_milestone1_matrix_marks_presets_not_evaluable_without_pairwise_judgments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="milestone1-matrix-all-pass",
                commit_hash="deadbeef",
            )
            for preset_id in ("B0", "A1", "A4"):
                expected_statuses = {"not_evaluable"} if preset_id == "A4" else {"fail", "not_evaluable"}
                overall_status = output["run_reports"][preset_id]["gate_report"]["gate_decision"]["overall_status"]
                self.assertIn(
                    overall_status,
                    expected_statuses,
                    msg=f"{preset_id} gate status was {overall_status!r}",
                )

    def test_milestone1_b0_gate_passes_coverage_and_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="milestone1-gate-remediation",
                commit_hash="deadbeef",
            )
            gates = output["run_reports"]["B0"]["gate_report"]["gate_decision"]
            self.assertEqual(gates["coverage.node_coverage_ratio"]["status"], "pass")
            self.assertEqual(gates["coverage.min_depth_coverage"]["status"], "pass")
            self.assertEqual(gates["quality.acceptance_rate"]["status"], "pass")
            self.assertIn(gates["overall_status"], {"fail", "not_evaluable"})

    def test_complexity_metrics_report_proxy_tags_without_treating_them_as_judgments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="feature/issue-7-complexity-evidence",
                commit_hash="deadbeef",
            )

            complexity = output["run_reports"]["B0"]["complexity"]

            self.assertEqual(complexity["evaluation_status"], "not_evaluable")
            self.assertIsNone(complexity["complexification_precision"])
            self.assertIsNone(complexity["complexity_shift"])
            self.assertIsNone(complexity["calibrated_score_distribution"]["p50"])
            self.assertGreater(complexity["proxy_metrics"]["complexified_sample_count"], 0)

    def test_injected_complexity_judgments_enable_evaluation_and_persist_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="feature/complexity-judgment-seam",
                commit_hash="deadbeef",
                complexity_judgment_provider=self._complexity_judgment_provider,
            )

            b0 = output["run_reports"]["B0"]
            complexity = b0["complexity"]
            run_id = b0["run_identity"]["run_id"]
            pairwise_path = (
                Path(tmp_dir)
                / str(run_id)
                / "30_complexification"
                / "pairwise_judgments.json"
            )
            pairwise_judgments = json.loads(pairwise_path.read_text(encoding="utf-8"))

        self.assertEqual(complexity["evaluation_status"], "evaluated")
        self.assertEqual(complexity["complexification_pairs_evaluated"], len(pairwise_judgments))
        self.assertGreater(complexity["complexification_pairs_evaluated"], 0)
        self.assertAlmostEqual(complexity["complexification_precision"], 1.0)
        self.assertAlmostEqual(complexity["complexity_shift"], 0.4)
        self.assertEqual(b0["protocol"]["complexity_judgment_protocol"]["evidence_status"], "evaluated")
        self.assertNotIn("not_evaluable_reason", b0["protocol"]["complexity_judgment_protocol"])
        self.assertEqual(
            b0["gate_report"]["gate_decision"]["complexity.complexification_precision"]["status"],
            "pass",
        )

    def test_missing_stage3_taxonomy_nodes_stay_in_coverage_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            samples_path = Path(tmp_dir) / "samples.json"
            decisions_path = Path(tmp_dir) / "decisions.json"
            samples_path.write_text(
                json.dumps(
                    [
                        {
                            "instantiation_id": "i-root",
                            "taxonomy_node_id": "tax-root",
                            "meta_prompt_id": "mp-root",
                            "text": "root sample",
                            "is_complexified": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            decisions_path.write_text(
                json.dumps(
                    [
                        {
                            "instantiation_id": "i-root",
                            "taxonomy_node_id": "tax-root",
                            "quality_status": "accepted",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            pipeline_result = {
                "manifest": {"run_id": "run-fake", "seed": 7, "artifact_schema_version": "v1"},
                "taxonomy": {
                    "nodes": [
                        {"taxonomy_node_id": "tax-root", "parent_taxonomy_node_id": None, "label": "Root", "depth": 0},
                        {"taxonomy_node_id": "tax-missing", "parent_taxonomy_node_id": "tax-root", "label": "Missing", "depth": 1},
                    ]
                },
                "stage_outputs": {
                    "stage_3_complexification": {
                        "complexification_artifacts": {"samples": str(samples_path)},
                    },
                    "stage_4_dual_critic_quality_verification": {
                        "reviewed_samples": 1,
                        "accepted_samples": 1,
                        "agreements": 1,
                        "disagreements": 0,
                        "regenerated_samples": 0,
                        "stage4_artifacts": {"critic_decisions": str(decisions_path)},
                    },
                },
            }

            with (
                patch("simula_research.issue7_execution_reporting.PRESET_IDS", ("B0",)),
                patch("simula_research.issue7_execution_reporting.validate_all_presets", return_value={"ok": True}),
                patch(
                    "simula_research.issue7_execution_reporting.build_run_request",
                    return_value={
                        "seed": 7,
                        "model_ids": {"generator": "g", "critic_a": "a", "critic_b": "b"},
                        "domain_objective": "pilot-domain",
                        "pipeline_config": {
                            "global_diversification_enabled": True,
                            "local_diversification_enabled": True,
                            "complexification_enabled": True,
                            "dual_critic_enabled": True,
                        },
                        "manifest_metadata": {
                            "baseline_or_ablation_tag": "B0",
                            "run_label": "baseline",
                            "hypothesis_focus": ["H1"],
                            "protocol_version": "0.1.0",
                            "artifact_schema_version": "v1",
                            "evaluation_protocol_version": "milestone-1",
                        },
                    },
                ),
                patch("simula_research.issue7_execution_reporting.run_pipeline", return_value=pipeline_result),
            ):
                output = execute_issue7_matrix(artifact_root=tmp_dir, report_root=tmp_dir)

            coverage = output["run_reports"]["B0"]["coverage"]
            self.assertEqual(coverage["eligible_nodes"], 2)
            self.assertEqual(coverage["covered_nodes"], 1)
            self.assertEqual(coverage["nodes_without_stage3_samples"], ["tax-missing"])
            self.assertEqual(coverage["node_coverage_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
