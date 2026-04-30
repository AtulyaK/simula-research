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

    def test_failed_gate_includes_threshold_failure_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = execute_issue7_matrix(
                artifact_root=tmp_dir,
                report_root=tmp_dir,
                branch_name="feature/issue-7-execute-b0-a1-a4",
                commit_hash="deadbeef",
            )

            has_failed_gate = False
            for per_run in output["run_reports"].values():
                gate_status = per_run["gate_report"]["gate_decision"]["overall_status"]
                if gate_status == "fail":
                    has_failed_gate = True
                    self.assertGreater(len(per_run["failure_analysis"]), 0)
                    self.assertTrue(
                        any("failed threshold" in note.lower() for note in per_run["failure_analysis"])
                    )

            self.assertTrue(has_failed_gate)


if __name__ == "__main__":
    unittest.main()
