from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.issue7_execution_reporting import execute_issue7_matrix
from simula_research.issue9_reproducibility import (
    _classify_baseline_rerun,
    _evaluate_comparability_gate,
    run_issue9_reproducibility_check,
)


class Issue9ReproducibilityTests(unittest.TestCase):
    def test_baseline_rerun_classification_detects_large_metric_drift(self) -> None:
        baseline_gate_report = {
            "coverage": {
                "node_coverage_ratio": 0.90,
                "depth_coverage_profile": {"0": 1.0, "1": 0.80},
            },
            "complexity": {
                "complexification_precision": 0.75,
                "calibrated_score_distribution": {"p50": 0.65},
            },
            "quality": {"acceptance_rate": 0.80, "critic_agreement": 0.90},
        }
        rerun_gate_report = {
            "coverage": {
                "node_coverage_ratio": 0.40,
                "depth_coverage_profile": {"0": 1.0, "1": 0.20},
            },
            "complexity": {
                "complexification_precision": 0.75,
                "calibrated_score_distribution": {"p50": 0.65},
            },
            "quality": {"acceptance_rate": 0.80, "critic_agreement": 0.90},
        }

        result = _classify_baseline_rerun(baseline_gate_report, rerun_gate_report)

        self.assertEqual(result["classification"], "mismatch")
        self.assertAlmostEqual(result["max_metric_delta"], 0.60)

    def test_comparability_gate_rejects_mixed_non_ablation_axis(self) -> None:
        milestone_review = {
            "comparability_constraints_check": {
                "taxonomy_eligibility_policy": {
                    "status": "mixed",
                    "details": "A1 changes taxonomy eligibility by ablation design.",
                },
                "critic_adjudication_configuration": {
                    "status": "mixed",
                    "details": "A4 single_critic by documented ablation design.",
                },
            }
        }

        result = _evaluate_comparability_gate(milestone_review)

        self.assertFalse(result["ok"])
        self.assertIn("taxonomy_eligibility_policy", result["details"])

    def test_issue9_reproducibility_check_validates_manifests_and_updates_milestone_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            reports_root = temp_root / "reports"
            artifacts_root = temp_root / "runs"
            matrix_output = execute_issue7_matrix(
                artifact_root=artifacts_root,
                report_root=reports_root,
                branch_name="feature/issue-9-repro-checks",
                commit_hash="deadbeef",
            )

            gate_reports = []
            run_ids = {}
            for preset_id, report in matrix_output["run_reports"].items():
                gate_reports.append(report["artifacts"]["gate_report"])
                run_ids[preset_id] = report["run_identity"]["run_id"]

            milestone_review_path = reports_root / "issue8" / "milestone_gate_review.json"
            milestone_review_path.parent.mkdir(parents=True, exist_ok=True)
            milestone_review_path.write_text(
                json.dumps(
                    {
                        "review_metadata": {
                            "issue_id": 8,
                            "review_type": "milestone-1-hitl-gate-review",
                            "decision": "fail",
                            "review_timestamp_utc": "2026-04-30T21:10:00Z",
                            "evidence_packet": matrix_output["matrix_root"],
                            "review_scope_constraints": [
                                "No protocol or experiment recompute",
                                "Preserve milestone-1 comparability constraints",
                            ],
                        },
                        "evidence_intake": {
                            "sources": {
                                "comparison_tables": matrix_output["comparison_tables_path"],
                                "gate_reports": gate_reports,
                            },
                            "run_ids": run_ids,
                            "reproducibility_status": {
                                "status": "incomplete",
                                "detail": "Deferred to Issue #9",
                                "blocked_by_issue": 9,
                            },
                        },
                        "comparability_constraints_check": {
                            "artifact_schema_version": {"status": "pass", "details": "all v1"},
                            "domain_objective": {"status": "pass", "details": "all pilot-domain"},
                            "taxonomy_eligibility_policy": {"status": "pass", "details": "fixed policy"},
                            "complexity_judgment_protocol": {"status": "pass", "details": "fixed protocol"},
                            "critic_adjudication_configuration": {
                                "status": "mixed",
                                "details": "A4 single_critic by documented ablation design",
                            },
                        },
                        "threshold_adjustment_recommendation": {
                            "recommendation": "keep_thresholds_as_is",
                            "rationale": "Initial issue #8 review",
                            "proposed_changes": [],
                            "adr_required": False,
                            "adr_note": "No threshold changes in issue #8",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = run_issue9_reproducibility_check(
                milestone_review_json_path=milestone_review_path,
                issue9_report_root=reports_root / "issue9",
                artifact_root=artifacts_root,
                branch_name="feature/issue-9-repro-checks",
                commit_hash="deadbeef",
            )

            self.assertEqual(set(result["manifest_validation"].keys()), {"B0", "A1", "A4"})
            self.assertTrue(all(item["ok"] for item in result["manifest_validation"].values()))
            self.assertIn(
                result["baseline_rerun"]["classification"],
                {"exact", "acceptable_drift", "mismatch"},
            )

            persisted = json.loads(milestone_review_path.read_text(encoding="utf-8"))
            repro = persisted["evidence_intake"]["reproducibility_status"]
            self.assertIn(repro["status"], {"exact", "acceptable_drift", "mismatch"})
            self.assertIn("manifest_validation", repro)
            self.assertEqual(repro["manifest_validation"]["all_ok"], True)
            self.assertIn("hard_gates", repro)
            self.assertEqual(repro["hard_gates"]["all_pass"], True)
            self.assertIn("threshold_tuning_guard", repro)
            self.assertEqual(repro["threshold_tuning_guard"]["eligible"], True)
            self.assertIn("paper_alignment", repro)
            self.assertEqual(
                set(repro["paper_alignment"].keys()),
                {"traceability_auditability", "fixed_protocol_comparability", "control_axis_interpretability"},
            )


if __name__ == "__main__":
    unittest.main()
