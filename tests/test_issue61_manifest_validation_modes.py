from __future__ import annotations

import tempfile
import unittest

from simula_research.manifest import BOOT_REQUIRED_MANIFEST_FIELDS, validate_manifest
from simula_research.pipeline import PROTOCOL_VERSION, ARTIFACT_SCHEMA_VERSION, run_pipeline
from simula_research.validators import (
    REQUIRED_MANIFEST_FIELDS,
    validate_manifest_by_mode,
    validate_manifest_schema,
)


class Issue61ManifestValidationModesTests(unittest.TestCase):
    def _pipeline_boot_manifest(self) -> dict[str, object]:
        """Shape produced by run_pipeline before persistence (boot-only fields)."""
        return {
            "run_id": "run-20260526T010000Z-abc12345",
            "created_at_utc": "2026-05-26T01:00:00Z",
            "seed": 7,
            "domain_objective": "pilot-domain",
            "model_ids": {"generator": "stub", "critic_a": "stub", "critic_b": "stub"},
            "protocol_version": PROTOCOL_VERSION,
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "pipeline_config": {"dual_critic_enabled": True},
        }

    def _full_reproducibility_manifest(self) -> dict[str, object]:
        boot = self._pipeline_boot_manifest()
        return {
            **boot,
            "owner": "agent",
            "branch": "main",
            "commit_hash": "abc123def456",
            "baseline_or_ablation_tag": "B0",
        }

    def test_boot_required_fields_are_subset_of_full_schema(self) -> None:
        boot_set = set(BOOT_REQUIRED_MANIFEST_FIELDS)
        full_set = set(REQUIRED_MANIFEST_FIELDS)
        self.assertTrue(boot_set.issubset(full_set))
        self.assertEqual(
            full_set - boot_set,
            {
                "owner",
                "branch",
                "commit_hash",
                "pipeline_config",
                "baseline_or_ablation_tag",
            },
        )

    def test_pipeline_boot_manifest_passes_boot_validator(self) -> None:
        validate_manifest(self._pipeline_boot_manifest())  # raises on failure

    def test_pipeline_boot_manifest_fails_full_schema(self) -> None:
        result = validate_manifest_schema(self._pipeline_boot_manifest())
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("missing required field: owner" in issue for issue in result["issues"])
        )

    def test_full_manifest_passes_boot_and_full_validators(self) -> None:
        manifest = self._full_reproducibility_manifest()
        validate_manifest(manifest)
        result = validate_manifest_schema(manifest)
        self.assertTrue(result["ok"])

    def test_validate_manifest_by_mode_boot_matches_raise_semantics(self) -> None:
        boot_result = validate_manifest_by_mode(self._pipeline_boot_manifest(), mode="boot")
        self.assertTrue(boot_result["ok"])
        self.assertEqual(boot_result["validation_mode"], "boot")

        missing = self._pipeline_boot_manifest()
        missing.pop("run_id")
        boot_fail = validate_manifest_by_mode(missing, mode="boot")
        self.assertFalse(boot_fail["ok"])
        self.assertIn("run_id", boot_fail["issues"][0])

    def test_validate_manifest_by_mode_full_delegates_to_schema_validator(self) -> None:
        full_ok = validate_manifest_by_mode(self._full_reproducibility_manifest(), mode="full")
        self.assertTrue(full_ok["ok"])
        self.assertEqual(full_ok["validation_mode"], "full")

        boot_only = validate_manifest_by_mode(self._pipeline_boot_manifest(), mode="full")
        self.assertFalse(boot_only["ok"])

    def test_run_pipeline_still_uses_boot_validation_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=1,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                artifact_root=tmp_dir,
            )
        manifest = result["manifest"]
        validate_manifest(manifest)
        full_check = validate_manifest_schema(manifest)
        self.assertFalse(full_check["ok"])


if __name__ == "__main__":
    unittest.main()
