from __future__ import annotations

import unittest

from simula_research.run_config_presets import (
    PRESET_IDS,
    REQUIRED_PRESET_FIELDS,
    build_run_request,
    get_config_preset,
    validate_all_presets,
)


class Wave2ConfigScaffoldingTest(unittest.TestCase):
    def test_required_presets_exist_with_labels(self) -> None:
        self.assertEqual(PRESET_IDS, ("B0", "A1", "A2", "A3", "A4", "A5"))
        for preset_id in PRESET_IDS:
            preset = get_config_preset(preset_id)
            self.assertEqual(preset["baseline_or_ablation_tag"], preset_id)
            self.assertIsInstance(preset["run_label"], str)
            self.assertTrue(preset["run_label"])

    def test_preset_validation_enforces_frozen_comparability_fields(self) -> None:
        result = validate_all_presets()
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["missing_fields"], {})
        self.assertEqual(result["non_comparable_fields"], [])

    def test_a1_preset_uses_full_complexify_fraction_for_small_n_ablation(self) -> None:
        preset = get_config_preset("A1")
        self.assertEqual(preset["complexification_config"]["complexify_fraction"], 1.0)
        request = build_run_request("A1")
        self.assertEqual(request["complexification_config"]["complexify_fraction"], 1.0)

    def test_runner_request_contains_required_manifest_metadata(self) -> None:
        request = build_run_request("A4")
        self.assertEqual(request["seed"], 7)
        self.assertEqual(
            request["model_ids"],
            {"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
        )
        self.assertEqual(request["manifest_metadata"]["baseline_or_ablation_tag"], "A4")
        self.assertEqual(request["manifest_metadata"]["protocol_version"], "0.1.0")
        self.assertEqual(request["manifest_metadata"]["artifact_schema_version"], "v1")
        self.assertEqual(request["manifest_metadata"]["evaluation_protocol_version"], "milestone-1")
        self.assertEqual(
            set(request["manifest_metadata"].keys()),
            set(REQUIRED_PRESET_FIELDS),
        )

    def test_a2_disables_local_diversification(self) -> None:
        preset = get_config_preset("A2")
        self.assertFalse(preset["pipeline_config"]["local_diversification_enabled"])
        self.assertEqual(preset["hypothesis_focus"], ["H2"])

    def test_a3_disables_complexification(self) -> None:
        preset = get_config_preset("A3")
        self.assertFalse(preset["pipeline_config"]["complexification_enabled"])
        self.assertEqual(preset["hypothesis_focus"], ["H3"])

    def test_a5_accepts_critic_disagreements(self) -> None:
        preset = get_config_preset("A5")
        self.assertEqual(
            preset["dual_critic_config"]["disagreement_policy"],
            "accept",
        )
        self.assertEqual(preset["hypothesis_focus"], ["H4"])


if __name__ == "__main__":
    unittest.main()
