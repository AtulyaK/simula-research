from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from simula_research.issue9_reproducibility import run_issue9_reproducibility_check
from simula_research.provider_phase4_review import build_provider_phase4_review


def _gate(preset: str, overall: str = "pass") -> dict:
    protocol = {
        "artifact_schema_version": "v1",
        "baseline_or_ablation_tag": preset,
        "complexity_judgment_protocol": {
            "initial_rating": 1000,
            "k_factor": 32,
            "minimum_comparisons_per_sample": 5,
            "version": "milestone-1",
        },
        "critic_adjudication_config": {
            "mode": "single_critic" if preset == "A4" else "dual_critic",
            "policy": "reject_on_disagreement",
        },
        "domain_objective": "pilot-domain",
        "evaluation_protocol_version": "milestone-1",
        "provider_runtime": {
            "critic_backend": "nim",
            "nim_critic": {"base_url": "https://example.test", "default_model": "m", "max_rpm": 40.0},
            "source": "environment",
        },
        "protocol_version": "0.1.0",
        "taxonomy_eligibility_policy": "instantiated-nodes-from-stage3-samples",
    }
    return {
        "complexity": {
            "complexification_pairs_evaluated": 3,
            "complexification_precision": 1.0,
            "complexity_shift": 0.0,
        },
        "coverage": {
            "coverage_balance": 1.0,
            "node_coverage_ratio": 1.0,
        },
        "gate_decision": {
            "overall_status": overall,
            "coverage.min_depth_coverage": {
                "actual": 1.0,
                "comparator": ">=",
                "status": "pass",
                "threshold": 0.6,
            },
            "coverage.node_coverage_ratio": {
                "actual": 1.0,
                "comparator": ">=",
                "status": "pass",
                "threshold": 0.8,
            },
            "quality.critic_agreement": {
                "actual": 1.0,
                "comparator": ">=",
                "status": "pass",
                "threshold": 0.75,
            },
        },
        "protocol": protocol,
        "quality": {
            "acceptance_rate": 1.0,
            "critic_agreement": 1.0,
            "regen_burden": 0.0,
        },
        "run_identity": {
            "branch": "provider-test",
            "commit_hash": "abc123",
            "run_id": f"run-{preset}",
            "seed": 7,
            "timestamp_utc": "2026-05-26T00:00:00+00:00",
        },
    }


def _write_matrix(root: Path) -> dict[str, dict]:
    (root / "comparison_tables.json").write_text(json.dumps({"gate_comparison": []}), encoding="utf-8")
    gates = {preset: _gate(preset) for preset in ("B0", "A1", "A4")}
    for preset, gate in gates.items():
        preset_dir = root / preset
        preset_dir.mkdir()
        (preset_dir / "gate_report.json").write_text(json.dumps(gate), encoding="utf-8")
        (preset_dir / "run_report.json").write_text(
            json.dumps({"protocol": gate["protocol"], "run_identity": gate["run_identity"]}),
            encoding="utf-8",
        )
    return gates


class ProviderPhase4ReviewTests(unittest.TestCase):
    def test_build_provider_review_contains_issue9_evidence_and_gate_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_matrix(root)

            review = build_provider_phase4_review(
                matrix_root=root,
                commit_hash="abc123",
                timestamp_utc="20260526T000000Z",
            )

            self.assertIn("evidence_intake", review)
            self.assertEqual(len(review["evidence_intake"]["sources"]["gate_reports"]), 3)
            self.assertEqual(review["evidence_intake"]["run_ids"]["B0"], "run-B0")
            self.assertEqual(review["gate_outcomes"]["B0"]["overall_status"], "pass")
            self.assertEqual(review["gate_outcomes"]["B0"]["run_id"], "run-B0")
            self.assertEqual(
                review["comparability_constraints_check"]["critic_adjudication_configuration"]["mixed_reason"],
                "documented_ablation",
            )

    def test_provider_review_can_drive_issue9_without_schema_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "matrix"
            root.mkdir()
            gates = _write_matrix(root)
            review_path = Path(tmp) / "provider_addendum.json"
            review_path.write_text(json.dumps(build_provider_phase4_review(matrix_root=root)), encoding="utf-8")

            rerun = {
                "matrix_root": str(Path(tmp) / "issue9" / "issue7" / "rerun"),
                "run_reports": {"B0": {"gate_report": gates["B0"]}},
            }
            with mock.patch("simula_research.issue9_reproducibility.execute_issue7_matrix", return_value=rerun):
                result = run_issue9_reproducibility_check(
                    milestone_review_json_path=review_path,
                    issue9_report_root=Path(tmp) / "issue9",
                    artifact_root=Path(tmp) / "runs",
                )

            updated = json.loads(review_path.read_text(encoding="utf-8"))
            hard_gates = updated["evidence_intake"]["reproducibility_status"]["hard_gates"]
            self.assertTrue(hard_gates["all_pass"])
            self.assertEqual(result["baseline_rerun"]["classification"], "exact")


if __name__ == "__main__":
    unittest.main()
