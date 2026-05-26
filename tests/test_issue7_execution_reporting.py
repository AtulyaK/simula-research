from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.issue7_execution_reporting import execute_issue7_matrix


class Issue7ExecutionReportingTests(unittest.TestCase):
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
                self.assertTrue(run_report_path.exists())
                self.assertTrue(gate_report_path.exists())

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

    def test_track_d_remediation_improves_critic_agreement_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="track-d-gate-remediation",
                commit_hash="deadbeef",
            )

            for preset_id in ("B0", "A1", "A4"):
                gates = output["run_reports"][preset_id]["gate_report"]["gate_decision"]
                self.assertEqual(gates["quality.critic_agreement"]["status"], "pass")
                self.assertGreaterEqual(
                    float(gates["quality.critic_agreement"]["actual"]),
                    0.75,
                )

    def test_milestone1_a1_gate_passes_complexification_precision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="milestone1-a1-complexity-gate",
                commit_hash="deadbeef",
            )
            gates = output["run_reports"]["A1"]["gate_report"]["gate_decision"]
            self.assertEqual(gates["complexity.complexification_precision"]["status"], "pass")
            self.assertGreaterEqual(
                float(gates["complexity.complexification_precision"]["actual"]),
                0.70,
            )

    def test_milestone1_matrix_all_presets_pass_overall_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="milestone1-matrix-all-pass",
                commit_hash="deadbeef",
            )
            for preset_id in ("B0", "A1", "A4"):
                self.assertEqual(
                    output["run_reports"][preset_id]["gate_report"]["gate_decision"]["overall_status"],
                    "pass",
                    msg=f"{preset_id} gate failed",
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
            self.assertEqual(gates["overall_status"], "pass")

    def test_complexity_metrics_use_complexification_stage_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="feature/issue-7-complexity-evidence",
                commit_hash="deadbeef",
            )

            complexity = output["run_reports"]["B0"]["complexity"]

            self.assertGreater(complexity["complexification_precision"], 0.0)
            self.assertGreater(complexity["calibrated_score_distribution"]["p50"], 0.45)


if __name__ == "__main__":
    unittest.main()
