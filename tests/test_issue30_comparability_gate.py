from __future__ import annotations

import unittest

from simula_research.issue9_reproducibility import MIXED_REASON_DOCUMENTED_ABLATION, evaluate_comparability_gate


def _axis_pass() -> dict[str, str]:
    return {"status": "pass", "details": "ok"}


def _base_review(comparability: dict[str, object]) -> dict[str, object]:
    return {"comparability_constraints_check": comparability}


class Issue30ComparabilityGateTests(unittest.TestCase):
    def test_all_pass_yields_ok(self) -> None:
        review = _base_review(
            {
                "artifact_schema_version": _axis_pass(),
                "domain_objective": _axis_pass(),
                "taxonomy_eligibility_policy": _axis_pass(),
                "complexity_judgment_protocol": _axis_pass(),
                "critic_adjudication_configuration": _axis_pass(),
            }
        )
        result = evaluate_comparability_gate(review)
        self.assertTrue(result["ok"])

    def test_mixed_with_documented_ablation_reason_yields_ok(self) -> None:
        review = _base_review(
            {
                "artifact_schema_version": _axis_pass(),
                "domain_objective": _axis_pass(),
                "taxonomy_eligibility_policy": _axis_pass(),
                "complexity_judgment_protocol": _axis_pass(),
                "critic_adjudication_configuration": {
                    "status": "mixed",
                    "mixed_reason": MIXED_REASON_DOCUMENTED_ABLATION,
                    "details": "A4 single critic by design",
                },
            }
        )
        result = evaluate_comparability_gate(review)
        self.assertTrue(result["ok"])

    def test_mixed_without_mixed_reason_fails(self) -> None:
        review = _base_review(
            {
                "artifact_schema_version": _axis_pass(),
                "domain_objective": _axis_pass(),
                "taxonomy_eligibility_policy": _axis_pass(),
                "complexity_judgment_protocol": _axis_pass(),
                "critic_adjudication_configuration": {
                    "status": "mixed",
                    "details": "Undocumented mixed axis",
                },
            }
        )
        result = evaluate_comparability_gate(review)
        self.assertFalse(result["ok"])
        self.assertIn("critic_adjudication_configuration", result["details"])

    def test_mixed_with_wrong_mixed_reason_fails(self) -> None:
        review = _base_review(
            {
                "artifact_schema_version": _axis_pass(),
                "domain_objective": _axis_pass(),
                "taxonomy_eligibility_policy": _axis_pass(),
                "complexity_judgment_protocol": _axis_pass(),
                "critic_adjudication_configuration": {
                    "status": "mixed",
                    "mixed_reason": "manual_override",
                    "details": "Not a documented ablation",
                },
            }
        )
        result = evaluate_comparability_gate(review)
        self.assertFalse(result["ok"])

    def test_non_pass_non_mixed_fails(self) -> None:
        review = _base_review(
            {
                "artifact_schema_version": {"status": "fail", "details": "broken"},
                "domain_objective": _axis_pass(),
                "taxonomy_eligibility_policy": _axis_pass(),
                "complexity_judgment_protocol": _axis_pass(),
                "critic_adjudication_configuration": _axis_pass(),
            }
        )
        result = evaluate_comparability_gate(review)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
