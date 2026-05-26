from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.track_b_promotion import build_promotion_assessment


def _gate(preset: str, overall: str, node_cov: float, agreement: float) -> dict:
    return {
        "run_id": f"run-{preset}",
        "gate_decision": {
            "overall_status": overall,
            "coverage.node_coverage_ratio": {
                "actual": node_cov,
                "status": "pass" if node_cov >= 0.8 else "fail",
                "comparator": ">=",
                "threshold": 0.8,
            },
            "coverage.min_depth_coverage": {
                "actual": 1.0,
                "status": "pass",
                "comparator": ">=",
                "threshold": 0.6,
            },
            "quality.critic_agreement": {
                "actual": agreement,
                "status": "pass" if agreement >= 0.75 else "fail",
                "comparator": ">=",
                "threshold": 0.75,
            },
            "quality.acceptance_rate": {
                "actual": 0.6,
                "status": "pass",
                "comparator": ">=",
                "threshold": 0.5,
            },
        },
    }


class TrackBPromotionTests(unittest.TestCase):
    def test_build_promotion_assessment_from_matrix_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "comparison_tables.json").write_text(json.dumps({"presets": []}), encoding="utf-8")
            for preset, gate in (
                ("B0", _gate("B0", "pass", 1.0, 1.0)),
                ("A1", _gate("A1", "pass", 0.5, 1.0)),
                ("A4", _gate("A4", "pass", 1.0, 0.5)),
            ):
                pdir = root / preset
                pdir.mkdir()
                (pdir / "gate_report.json").write_text(json.dumps(gate), encoding="utf-8")

            report = build_promotion_assessment(
                matrix_root=root,
                deterministic_baseline_root="artifacts/reports/issue7/20260526T025931Z",
            )
            self.assertTrue(report["playbook_criteria"]["b0_gate_pass_on_this_packet"])
            h1 = next(r for r in report["hypothesis_assessment"] if r["hypothesis"] == "H1")
            self.assertEqual(h1["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
